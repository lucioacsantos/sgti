"""
Certification Service API Layer

API service for certification workflow.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from ..models.certification import (
    CertificationRequest, CertificationStatus, CertificationRole,
    CertificationDecision, CertificationComment
)
from ..models.reconciliation import Conflict
from ..models.entity import CollectedEntity
from ..certification.service import CertificationService as CoreCertificationService

logger = logging.getLogger(__name__)


class CertificationAPIService:
    """API service for certification workflow."""
    
    def __init__(self, db: Session):
        self.db = db
        self.core_service = CoreCertificationService(
            request_repository=self,
            conflict_repository=self,
            entity_repository=self,
            notification_service=None,  # TODO: implement
        )
    
    # Request repository methods
    async def create_request(self, request: CertificationRequest) -> CertificationRequest:
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request
    
    async def get_request(self, request_id: UUID) -> Optional[CertificationRequest]:
        return self.db.query(CertificationRequest).filter(
            CertificationRequest.id == request_id
        ).first()
    
    async def update_request(self, request: CertificationRequest):
        request.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(request)
    
    async def get_requests(
        self,
        status: Optional[CertificationStatus] = None,
        assignee_id: Optional[str] = None,
        role: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CertificationRequest]:
        query = self.db.query(CertificationRequest)
        
        if status:
            query = query.filter(CertificationRequest.status == status)
        if assignee_id:
            query = query.filter(
                (CertificationRequest.analyst_id == assignee_id) |
                (CertificationRequest.reviewer_id == assignee_id)
            )
        
        return query.order_by(
            CertificationRequest.priority,
            CertificationRequest.created_at.desc()
        ).offset(skip).limit(limit).all()
    
    async def get_by_assignee(
        self,
        user_id: str,
        role: CertificationRole,
        statuses: List[CertificationStatus]
    ) -> List[CertificationRequest]:
        query = self.db.query(CertificationRequest).filter(
            CertificationRequest.status.in_(statuses)
        )
        
        if role == CertificationRole.ANALYST:
            query = query.filter(CertificationRequest.analyst_id == user_id)
        elif role == CertificationRole.REVIEWER:
            query = query.filter(CertificationRequest.reviewer_id == user_id)
        
        return query.all()
    
    async def get_overdue(self) -> List[CertificationRequest]:
        return self.db.query(CertificationRequest).filter(
            CertificationRequest.due_at < datetime.utcnow(),
            CertificationRequest.status.in_([
                CertificationStatus.PENDING,
                CertificationStatus.IN_REVIEW_ANALYST,
                CertificationStatus.IN_REVIEW_REVIEWER,
            ]),
            CertificationRequest.sla_breached == False,
        ).all()
    
    async def get_stats(self):
        from ..models.certification import CertificationStats
        total = self.db.query(CertificationRequest).count()
        pending = self.db.query(CertificationRequest).filter(
            CertificationRequest.status == CertificationStatus.PENDING
        ).count()
        in_review = self.db.query(CertificationRequest).filter(
            CertificationRequest.status.in_([
                CertificationStatus.IN_REVIEW_ANALYST,
                CertificationStatus.IN_REVIEW_REVIEWER,
            ])
        ).count()
        approved = self.db.query(CertificationRequest).filter(
            CertificationRequest.status == CertificationStatus.APPROVED
        ).count()
        rejected = self.db.query(CertificationRequest).filter(
            CertificationRequest.status == CertificationStatus.REJECTED
        ).count()
        
        return CertificationStats(
            total_requests=total,
            pending=pending,
            in_review=in_review,
            approved=approved,
            rejected=rejected,
            escalated=0,
            expired=0,
            avg_resolution_hours=0.0,
            sla_compliance_rate=1.0,
            by_priority={},
            by_analyst={},
            by_reviewer={},
        )
    
    async def add_comment(self, comment: CertificationComment):
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
    
    # Conflict repository methods
    async def get_conflict(self, conflict_id: UUID) -> Optional[Conflict]:
        return self.db.query(Conflict).filter(Conflict.id == conflict_id).first()
    
    async def get_conflicts_by_session(
        self,
        session_id: UUID,
        requires_certification: bool = False
    ) -> List[Conflict]:
        query = self.db.query(Conflict).filter(
            Conflict.reconciliation_session_id == session_id
        )
        if requires_certification:
            query = query.filter(Conflict.requires_certification == True)
        return query.all()
    
    # Entity repository methods
    async def get_entity(self, entity_id: UUID) -> Optional[CollectedEntity]:
        return self.db.query(CollectedEntity).filter(
            CollectedEntity.id == entity_id
        ).first()
    
    async def update_entity(self, entity: CollectedEntity):
        entity.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(entity)
    
    # High-level API methods
    async def create_certification_request(
        self,
        title: str,
        description: str,
        requested_by: str,
        reconciliation_session_id: Optional[UUID] = None,
        conflict_ids: List[UUID] = None,
        entity_ids: List[UUID] = None,
        priority: int = 3,
        analyst_id: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        sla_hours: int = 72,
        tags: Dict[str, str] = None,
        correlation_id: Optional[str] = None,
    ) -> CertificationRequest:
        return await self.core_service.create_request(
            title=title,
            description=description,
            requested_by=requested_by,
            reconciliation_session_id=reconciliation_session_id,
            conflict_ids=conflict_ids,
            entity_ids=entity_ids,
            priority=priority,
            analyst_id=analyst_id,
            reviewer_id=reviewer_id,
            due_at=due_at,
            sla_hours=sla_hours,
            tags=tags,
            correlation_id=correlation_id,
        )
    
    async def create_from_reconciliation(
        self,
        reconciliation_session_id: UUID,
        requested_by: str,
        **kwargs
    ) -> CertificationRequest:
        return await self.core_service.create_from_reconciliation(
            reconciliation_session_id=reconciliation_session_id,
            requested_by=requested_by,
            **kwargs
        )
    
    async def get_queue(
        self,
        user_id: str,
        role: CertificationRole,
    ) -> List[Dict[str, Any]]:
        from ..models.certification import CertificationQueueItem
        items = await self.core_service.get_queue(user_id, role)
        return [item.model_dump() for item in items]
    
    async def take_action(
        self,
        request_id: UUID,
        role: CertificationRole,
        decision: CertificationDecision,
        notes: Optional[str] = None,
        decided_by: str = None
    ) -> CertificationRequest:
        return await self.core_service.take_action(
            request_id=request_id,
            role=role,
            decision=decision,
            notes=notes,
            decided_by=decided_by
        )
    
    async def add_comment(
        self,
        request_id: UUID,
        author_id: str,
        author_role: CertificationRole,
        content: str
    ) -> CertificationComment:
        return await self.core_service.add_comment(
            request_id=request_id,
            author_id=author_id,
            author_role=author_role,
            content=content
        )
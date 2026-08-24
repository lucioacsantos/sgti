"""
Certification Service

Manages the analyst/reviewer certification workflow for conflicted data.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging

from ..models.certification import (
    CertificationRequest, CertificationStatus, CertificationRole,
    CertificationDecision, CertificationAction, CertificationComment,
    CertificationQueueItem, CertificationStats
)
from ..models.reconciliation import Conflict

logger = logging.getLogger(__name__)


class CertificationService:
    """Service for managing certification workflow."""
    
    def __init__(
        self,
        request_repository,
        conflict_repository,
        entity_repository,
        notification_service=None
    ):
        self.request_repository = request_repository
        self.conflict_repository = conflict_repository
        self.entity_repository = entity_repository
        self.notification_service = notification_service
    
    async def create_request(
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
        """Create a new certification request."""
        
        request = CertificationRequest(
            reconciliation_session_id=reconciliation_session_id,
            conflict_ids=conflict_ids or [],
            entity_ids=entity_ids or [],
            title=title,
            description=description,
            priority=priority,
            requested_by=requested_by,
            analyst_id=analyst_id,
            reviewer_id=reviewer_id,
            due_at=due_at,
            sla_hours=sla_hours,
            tags=tags or {},
            correlation_id=correlation_id,
        )
        
        # Set default due date if not provided
        if not request.due_at:
            request.due_at = datetime.utcnow() + timedelta(hours=sla_hours)
        
        # Save request
        await self.request_repository.create(request)
        
        # Notify assignees
        if self.notification_service:
            if analyst_id:
                await self.notification_service.notify(
                    analyst_id,
                    "certification_assigned",
                    {"request_id": str(request.id), "role": "analyst"}
                )
            if reviewer_id:
                await self.notification_service.notify(
                    reviewer_id,
                    "certification_assigned",
                    {"request_id": str(request.id), "role": "reviewer"}
                )
        
        return request
    
    async def create_from_conflicts(
        self,
        conflicts: List[Conflict],
        requested_by: str,
        title: str = None,
        description: str = None,
        **kwargs
    ) -> CertificationRequest:
        """Create certification request from a list of conflicts."""
        
        if not conflicts:
            raise ValueError("No conflicts provided")
        
        # Group by severity
        critical = [c for c in conflicts if c.severity.value == "critical"]
        high = [c for c in conflicts if c.severity.value == "high"]
        
        # Determine priority
        priority = kwargs.get("priority", 3)
        if critical:
            priority = 1
        elif high:
            priority = 2
        
        # Generate title/description if not provided
        if not title:
            title = f"Certification for {len(conflicts)} conflicts"
            if critical:
                title += f" ({len(critical)} critical)"
        
        if not description:
            by_type = {}
            for c in conflicts:
                by_type[c.conflict_type.value] = by_type.get(c.conflict_type.value, 0) + 1
            
            description = f"Certification required for {len(conflicts)} conflicts:\n"
            for ctype, count in by_type.items():
                description += f"  - {ctype}: {count}\n"
            description += f"\nCritical: {len(critical)}, High: {len(high)}"
        
        conflict_ids = [c.id for c in conflicts]
        
        return await self.create_request(
            title=title,
            description=description,
            requested_by=requested_by,
            conflict_ids=conflict_ids,
            priority=priority,
            **kwargs
        )
    
    async def create_from_reconciliation(
        self,
        reconciliation_session_id: UUID,
        requested_by: str,
        **kwargs
    ) -> CertificationRequest:
        """Create certification request for all conflicts requiring certification in a session."""
        
        # Get conflicts requiring certification
        conflicts = await self.conflict_repository.get_by_session(
            reconciliation_session_id,
            requires_certification=True
        )
        
        if not conflicts:
            raise ValueError("No conflicts requiring certification in this session")
        
        return await self.create_from_conflicts(
            conflicts=conflicts,
            requested_by=requested_by,
            reconciliation_session_id=reconciliation_session_id,
            **kwargs
        )
    
    async def get_queue(
        self,
        user_id: str,
        role: CertificationRole,
        status: List[CertificationStatus] = None
    ) -> List[CertificationQueueItem]:
        """Get certification queue for a user."""
        
        statuses = status or [
            CertificationStatus.PENDING,
            CertificationStatus.IN_REVIEW_ANALYST,
            CertificationStatus.IN_REVIEW_REVIEWER,
        ]
        
        requests = await self.request_repository.get_by_assignee(user_id, role, statuses)
        
        queue_items = []
        for req in requests:
            # Calculate SLA remaining
            sla_remaining = None
            if req.due_at:
                remaining = req.due_at - datetime.utcnow()
                sla_remaining = max(0, remaining.total_seconds() / 3600)
            
            queue_items.append(CertificationQueueItem(
                request_id=req.id,
                title=req.title,
                priority=req.priority,
                status=req.status,
                assignee_id=user_id,
                assignee_role=role,
                created_at=req.created_at,
                due_at=req.due_at,
                sla_hours_remaining=sla_remaining,
                conflict_count=len(req.conflict_ids),
                entity_count=len(req.entity_ids),
            ))
        
        # Sort by priority and due date
        queue_items.sort(key=lambda x: (x.priority, x.due_at or datetime.max))
        
        return queue_items
    
    async def take_action(
        self,
        request_id: UUID,
        role: CertificationRole,
        decision: CertificationDecision,
        notes: Optional[str] = None,
        decided_by: str = None
    ) -> CertificationRequest:
        """Process a certification action (approve/reject/etc)."""
        
        request = await self.request_repository.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # Validate role can act
        if not self._can_act(request, role):
            raise ValueError(f"User not authorized to act as {role.value} on this request")
        
        # Check status allows action
        if not self._status_allows_action(request.status, role):
            raise ValueError(f"Request status {request.status} does not allow {role.value} action")
        
        # Record decision
        if role == CertificationRole.ANALYST:
            request.analyst_decision = decision
            request.analyst_notes = notes
            request.analyst_decided_at = datetime.utcnow()
            request.status = CertificationStatus.IN_REVIEW_REVIEWER
        elif role == CertificationRole.REVIEWER:
            request.reviewer_decision = decision
            request.reviewer_notes = notes
            request.reviewer_decided_at = datetime.utcnow()
        elif role == CertificationRole.MANAGER:
            request.manager_decision = decision
            request.manager_notes = notes
            request.manager_decided_at = datetime.utcnow()
        
        # Determine next state
        await self._evaluate_outcome(request)
        
        # Update timestamp
        request.updated_at = datetime.utcnow()
        
        # Save
        await self.request_repository.update(request)
        
        # Notify next assignee
        if self.notification_service:
            await self._notify_next_assignee(request)
        
        return request
    
    def _can_act(self, request: CertificationRequest, role: CertificationRole) -> bool:
        """Check if user can act in this role."""
        if role == CertificationRole.ANALYST:
            return request.analyst_id is None or request.analyst_id == decided_by
        elif role == CertificationRole.REVIEWER:
            return request.reviewer_id is None or request.reviewer_id == decided_by
        elif role == CertificationRole.MANAGER:
            return request.manager_id is None or request.manager_id == decided_by
        return False
    
    def _status_allows_action(self, status: CertificationStatus, role: CertificationRole) -> bool:
        """Check if current status allows action by role."""
        allowed = {
            CertificationStatus.PENDING: [CertificationRole.ANALYST],
            CertificationStatus.IN_REVIEW_ANALYST: [CertificationRole.ANALYST],
            CertificationStatus.IN_REVIEW_REVIEWER: [CertificationRole.REVIEWER],
            CertificationStatus.ESCALATED: [CertificationRole.MANAGER],
        }
        return role in allowed.get(status, [])
    
    async def _evaluate_outcome(self, request: CertificationRequest):
        """Evaluate the certification outcome based on decisions."""
        
        # Analyst decision made
        if request.analyst_decision and not request.reviewer_decision:
            if request.analyst_decision == CertificationDecision.REJECT:
                # Rejected by analyst - goes to reviewer for confirmation
                request.status = CertificationStatus.IN_REVIEW_REVIEWER
            elif request.analyst_decision == CertificationDecision.APPROVE:
                # Approved by analyst - needs reviewer
                request.status = CertificationStatus.IN_REVIEW_REVIEWER
            elif request.analyst_decision == CertificationDecision.REQUEST_CHANGES:
                # Changes requested - back to data owners
                request.status = CertificationStatus.IN_REVIEW_ANALYST
            elif request.analyst_decision == CertificationDecision.ESCALATE:
                # Escalated to manager
                request.status = CertificationStatus.ESCALATED
        
        # Reviewer decision made
        elif request.reviewer_decision:
            if request.reviewer_decision == CertificationDecision.APPROVE:
                # Both approved
                if request.analyst_decision == CertificationDecision.APPROVE:
                    request.final_decision = CertificationDecision.APPROVE
                    request.status = CertificationStatus.APPROVED
                    request.completed_at = datetime.utcnow()
                    request.decided_at = datetime.utcnow()
                    request.decided_by = request.reviewer_id
                else:
                    # Analyst had different decision - escalate
                    request.status = CertificationStatus.ESCALATED
            
            elif request.reviewer_decision == CertificationDecision.REJECT:
                # Rejected by reviewer
                request.final_decision = CertificationDecision.REJECT
                request.status = CertificationStatus.REJECTED
                request.completed_at = datetime.utcnow()
                request.decided_at = datetime.utcnow()
                request.decided_by = request.reviewer_id
            
            elif request.reviewer_decision == CertificationDecision.REQUEST_CHANGES:
                # Changes needed
                request.status = CertificationStatus.IN_REVIEW_ANALYST
            
            elif request.reviewer_decision == CertificationDecision.ESCALATE:
                request.status = CertificationStatus.ESCALATED
        
        # Manager decision (escalation)
        elif request.manager_decision:
            if request.manager_decision == CertificationDecision.APPROVE:
                request.final_decision = CertificationDecision.APPROVE
                request.status = CertificationStatus.APPROVED
            elif request.manager_decision == CertificationDecision.REJECT:
                request.final_decision = CertificationDecision.REJECT
                request.status = CertificationStatus.REJECTED
            elif request.manager_decision == CertificationDecision.REQUEST_CHANGES:
                request.status = CertificationStatus.IN_REVIEW_ANALYST
            
            if request.status in (CertificationStatus.APPROVED, CertificationStatus.REJECTED):
                request.completed_at = datetime.utcnow()
                request.decided_at = datetime.utcnow()
                request.decided_by = request.manager_id
    
    async def _notify_next_assignee(self, request: CertificationRequest):
        """Notify the next person who needs to act."""
        if request.status == CertificationStatus.IN_REVIEW_REVIEWER and request.reviewer_id:
            await self.notification_service.notify(
                request.reviewer_id,
                "certification_review_needed",
                {"request_id": str(request.id)}
            )
        elif request.status == CertificationStatus.ESCALATED and request.manager_id:
            await self.notification_service.notify(
                request.manager_id,
                "certification_escalated",
                {"request_id": str(request.id)}
            )
    
    async def add_comment(
        self,
        request_id: UUID,
        author_id: str,
        author_role: CertificationRole,
        content: str
    ) -> CertificationComment:
        """Add a comment to a certification request."""
        
        comment = CertificationComment(
            request_id=request_id,
            author_id=author_id,
            author_role=author_role,
            content=content,
        )
        
        await self.request_repository.add_comment(comment)
        
        # Notify other participants
        if self.notification_service:
            request = await self.request_repository.get(request_id)
            participants = set()
            if request.analyst_id:
                participants.add(request.analyst_id)
            if request.reviewer_id:
                participants.add(request.reviewer_id)
            if request.manager_id:
                participants.add(request.manager_id)
            
            for participant in participants:
                if participant != author_id:
                    await self.notification_service.notify(
                        participant,
                        "certification_comment",
                        {"request_id": str(request_id), "author": author_id}
                    )
        
        return comment
    
    async def get_stats(self) -> CertificationStats:
        """Get certification statistics."""
        return await self.request_repository.get_stats()
    
    async def check_sla_breaches(self):
        """Check for SLA breaches and escalate."""
        overdue = await self.request_repository.get_overdue()
        
        for request in overdue:
            if not request.sla_breached:
                request.sla_breached = True
                request.status = CertificationStatus.ESCALATED
                await self.request_repository.update(request)
                
                if self.notification_service and request.manager_id:
                    await self.notification_service.notify(
                        request.manager_id,
                        "certification_sla_breach",
                        {"request_id": str(request.id)}
                    )
    
    async def apply_certification(self, request: CertificationRequest) -> List[CollectedEntity]:
        """Apply certification decisions to entities."""
        if request.final_decision != CertificationDecision.APPROVE:
            return []
        
        # Get entities and conflicts
        entities = []
        for entity_id in request.entity_ids:
            entity = await self.entity_repository.get(entity_id)
            if entity:
                entity.is_certified = True
                entity.certified_at = datetime.utcnow()
                entity.certified_by = request.decided_by
                entities.append(entity)
        
        # Also apply to conflict-related entities
        for conflict_id in request.conflict_ids:
            conflict = await self.conflict_repository.get(conflict_id)
            if conflict:
                if conflict.entity_a_id:
                    entity = await self.entity_repository.get(conflict.entity_a_id)
                    if entity:
                        entity.is_certified = True
                        entity.certified_at = datetime.utcnow()
                        entity.certified_by = request.decided_by
                        entities.append(entity)
                if conflict.entity_b_id:
                    entity = await self.entity_repository.get(conflict.entity_b_id)
                    if entity:
                        entity.is_certified = True
                        entity.certified_at = datetime.utcnow()
                        entity.certified_by = request.decided_by
                        entities.append(entity)
        
        # Save all
        for entity in entities:
            await self.entity_repository.update(entity)
        
        return entities
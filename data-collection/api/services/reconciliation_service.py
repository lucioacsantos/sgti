"""
Reconciliation Service

High-level service for running reconciliations.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from ..models.reconciliation import ReconciliationSession, Conflict, ReconciliationRule
from ..models.entity import CollectedEntity
from ..models.source import DataSource
from ..reconciliation.engine import ReconciliationEngine

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Service for managing reconciliation sessions."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def run_reconciliation(self, session_id: UUID) -> ReconciliationSession:
        """Run a reconciliation session."""
        session = self.db.query(ReconciliationSession).filter(
            ReconciliationSession.id == session_id
        ).first()
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get sources
        sources = {}
        for source_id in session.source_ids:
            source = self.db.query(DataSource).filter(DataSource.id == source_id).first()
            if source:
                sources[source_id] = source
        
        # Get entities for each source
        entities_by_source = {}
        for source_id in session.source_ids:
            entities = self.db.query(CollectedEntity).filter(
                CollectedEntity.source_id == source_id,
                CollectedEntity.is_deleted == False,
            )
            
            if session.entity_types:
                entities = entities.filter(CollectedEntity.entity_type.in_(session.entity_types))
            
            # Apply filters
            if session.filters:
                for key, value in session.filters.items():
                    entities = entities.filter(getattr(CollectedEntity, key) == value)
            
            entities_by_source[source_id] = entities.all()
        
        # Get active rules
        rules = self.db.query(ReconciliationRule).filter(
            ReconciliationRule.enabled == True
        ).all()
        
        # Run engine
        engine = ReconciliationEngine(session, sources, entities_by_source, rules)
        result = await engine.run()
        
        # Store conflicts
        for conflict in engine.conflicts:
            self.db.add(conflict)
        
        self.db.commit()
        
        return result
    
    async def get_conflicts(
        self,
        session_id: UUID,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Conflict]:
        """Get conflicts for a session."""
        query = self.db.query(Conflict).filter(
            Conflict.reconciliation_session_id == session_id
        )
        
        if severity:
            query = query.filter(Conflict.severity == severity)
        if resolved is not None:
            if resolved:
                query = query.filter(Conflict.resolution.isnot(None))
            else:
                query = query.filter(Conflict.resolution.is_(None))
        
        return query.order_by(
            Conflict.severity.desc(),
            Conflict.detected_at.desc()
        ).offset(skip).limit(limit).all()
    
    async def resolve_conflict(
        self,
        conflict_id: UUID,
        resolution: str,
        resolved_value: Any = None,
        notes: Optional[str] = None,
        resolved_by: str = "api",
    ) -> Conflict:
        """Resolve a conflict."""
        conflict = self.db.query(Conflict).filter(Conflict.id == conflict_id).first()
        if not conflict:
            raise ValueError(f"Conflict {conflict_id} not found")
        
        conflict.resolution = resolution
        conflict.resolved_value = resolved_value
        conflict.resolution_notes = notes
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.utcnow()
        conflict.updated_at = datetime.utcnow()
        
        self.db.commit()
        return conflict
    
    async def bulk_resolve_conflicts(
        self,
        conflict_ids: List[UUID],
        resolution: str,
        resolved_value: Any = None,
        notes: Optional[str] = None,
        resolved_by: str = "api",
    ) -> int:
        """Bulk resolve conflicts."""
        count = 0
        for conflict_id in conflict_ids:
            conflict = self.db.query(Conflict).filter(Conflict.id == conflict_id).first()
            if conflict and conflict.resolution is None:
                conflict.resolution = resolution
                conflict.resolved_value = resolved_value
                conflict.resolution_notes = notes
                conflict.resolved_by = resolved_by
                conflict.resolved_at = datetime.utcnow()
                conflict.updated_at = datetime.utcnow()
                count += 1
        
        self.db.commit()
        return count
    
    async def create_rule(self, rule: ReconciliationRule) -> ReconciliationRule:
        """Create a reconciliation rule."""
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    async def list_rules(
        self,
        enabled: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ReconciliationRule]:
        """List reconciliation rules."""
        query = self.db.query(ReconciliationRule)
        
        if enabled is not None:
            query = query.filter(ReconciliationRule.enabled == enabled)
        
        return query.order_by(ReconciliationRule.priority).offset(skip).limit(limit).all()
"""
Reconciliation Models

Handles conflict detection and resolution between data sources.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4


class ConflictType(str, Enum):
    """Types of conflicts between sources."""
    # Attribute mismatches
    ATTRIBUTE_MISMATCH = "attribute_mismatch"  # Different values for same attribute
    MISSING_IN_SOURCE = "missing_in_source"    # Entity exists in one source but not another
    EXTRA_IN_SOURCE = "extra_in_source"        # Entity only in one source
    
    # Hierarchy conflicts
    PARENT_MISMATCH = "parent_mismatch"        # Different parent assignment
    HIERARCHY_DEPTH = "hierarchy_depth"        # Different hierarchy levels
    
    # Identity conflicts
    DUPLICATE_ENTITY = "duplicate_entity"      # Multiple entities mapping to same real asset
    IDENTITY_CONFUSION = "identity_confusion"  # Unclear if same or different entity
    
    # State conflicts
    STATE_MISMATCH = "state_mismatch"          # Different power/connection states
    CAPACITY_MISMATCH = "capacity_mismatch"    # Different capacity reporting


class ConflictSeverity(str, Enum):
    """Conflict severity levels."""
    LOW = "low"           # Cosmetic differences (description, tags)
    MEDIUM = "medium"     # Operational impact (IP, capacity, location)
    HIGH = "high"         # Critical (identity, ownership, compliance)
    CRITICAL = "critical" # Security/risk (duplicate assets, unauthorized changes)


class ResolutionAction(str, Enum):
    """How a conflict was resolved."""
    SOURCE_A_WINS = "source_a_wins"
    SOURCE_B_WINS = "source_b_wins"
    MERGE = "merge"              # Combine values (e.g., union of tags)
    MANUAL = "manual"            # Analyst decided
    AUTO_RULE = "auto_rule"      # Applied automatic rule
    DEFERRED = "deferred"        # Postponed for later
    ESCALATED = "escalated"      # Sent to certification


class Conflict(BaseModel):
    """A single conflict between sources."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    reconciliation_session_id: UUID
    
    # Conflict details
    conflict_type: ConflictType
    severity: ConflictSeverity
    
    # Entities involved
    entity_a_id: Optional[UUID] = None  # Entity from source A
    entity_b_id: Optional[UUID] = None  # Entity from source B
    entity_a_source_id: UUID
    entity_b_source_id: UUID
    
    # Attribute-level conflict
    attribute_name: Optional[str] = None
    value_a: Any = None
    value_b: Any = None
    
    # Description
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Resolution
    resolution: Optional[ResolutionAction] = None
    resolved_value: Any = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    # Certification
    requires_certification: bool = False
    certification_request_id: Optional[UUID] = None
    
    # Metadata
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationRule(BaseModel):
    """Automatic reconciliation rule."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    
    # Scope
    entity_types: List[str] = Field(default_factory=list)  # Empty = all
    source_types: List[str] = Field(default_factory=list)  # Empty = all
    attributes: List[str] = Field(default_factory=list)    # Empty = all
    
    # Conditions
    condition: Dict[str, Any] = Field(default_factory=dict)
    
    # Action
    action: ResolutionAction
    priority: int = 100  # Lower = higher priority
    
    # Parameters for action
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationSession(BaseModel):
    """A reconciliation session comparing multiple sources."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: Optional[str] = None
    
    # Sources being reconciled
    source_ids: List[UUID]
    primary_source_id: UUID  # Source of truth
    
    # Scope
    entity_types: List[str] = Field(default_factory=list)  # Empty = all
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    status: str = "pending"  # pending, running, completed, failed, cancelled
    progress_percent: float = 0.0
    
    # Stats
    total_entities_compared: int = 0
    conflicts_found: int = 0
    conflicts_resolved: int = 0
    conflicts_auto_resolved: int = 0
    conflicts_manual_resolved: int = 0
    conflicts_certification_required: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Results summary
    entities_matched: int = 0
    entities_only_in_primary: int = 0
    entities_only_in_secondary: int = 0
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    triggered_by: str = "scheduler"
    triggered_by_user: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationSessionCreate(BaseModel):
    """Create reconciliation session request."""
    name: str
    description: Optional[str] = None
    source_ids: List[UUID]
    primary_source_id: UUID
    entity_types: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = "manual"
    triggered_by_user: Optional[str] = None
    correlation_id: Optional[str] = None


class ConflictResolutionRequest(BaseModel):
    """Request to resolve a conflict."""
    conflict_id: UUID
    resolution: ResolutionAction
    resolved_value: Any = None
    resolution_notes: Optional[str] = None
    resolved_by: str


class BulkConflictResolutionRequest(BaseModel):
    """Bulk resolve conflicts."""
    conflict_ids: List[UUID]
    resolution: ResolutionAction
    resolved_value: Any = None
    resolution_notes: Optional[str] = None
    resolved_by: str


class ReconciliationReport(BaseModel):
    """Reconciliation session report."""
    session_id: UUID
    session_name: str
    status: str
    
    # Summary
    total_conflicts: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    by_resolution: Dict[str, int]
    
    # Entity stats
    entities_compared: int
    entities_matched: int
    entities_unmatched: int
    
    # Top conflicts
    top_conflicts: List[Conflict]
    
    # Recommendations
    recommendations: List[str]
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
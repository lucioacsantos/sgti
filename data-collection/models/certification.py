"""
Certification Models

Workflow for data certification by analyst and reviewer.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4


class CertificationStatus(str, Enum):
    """Certification request status."""
    PENDING = "pending"           # Awaiting analyst
    IN_REVIEW_ANALYST = "in_review_analyst"  # Analyst reviewing
    IN_REVIEW_REVIEWER = "in_review_reviewer"  # Reviewer reviewing
    APPROVED = "approved"         # Both approved
    REJECTED = "rejected"         # Rejected by either
    ESCALATED = "escalated"       # Escalated to manager
    EXPIRED = "expired"           # Timeout
    CANCELLED = "cancelled"       # Cancelled


class CertificationRole(str, Enum):
    """Roles in certification process."""
    ANALYST = "analyst"       # First reviewer - validates data
    REVIEWER = "reviewer"     # Second reviewer - approves/rejects
    MANAGER = "manager"       # Escalation point


class CertificationDecision(str, Enum):
    """Certification decision."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"


class CertificationRequest(BaseModel):
    """Certification request for conflicted or critical data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    
    # Source
    reconciliation_session_id: Optional[UUID] = None
    conflict_ids: List[UUID] = Field(default_factory=list)
    entity_ids: List[UUID] = Field(default_factory=list)
    
    # Request details
    title: str
    description: str
    priority: int = 3  # 1=critical, 2=high, 3=medium, 4=low
    
    # Status
    status: CertificationStatus = CertificationStatus.PENDING
    
    # Assignees
    analyst_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    manager_id: Optional[str] = None
    
    # Decisions
    analyst_decision: Optional[CertificationDecision] = None
    analyst_notes: Optional[str] = None
    analyst_decided_at: Optional[datetime] = None
    
    reviewer_decision: Optional[CertificationDecision] = None
    reviewer_notes: Optional[str] = None
    reviewer_decided_at: Optional[datetime] = None
    
    manager_decision: Optional[CertificationDecision] = None
    manager_notes: Optional[str] = None
    manager_decided_at: Optional[datetime] = None
    
    # Final outcome
    final_decision: Optional[CertificationDecision] = None
    final_notes: Optional[str] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # SLA
    sla_hours: int = 72
    sla_breached: bool = False
    
    # Metadata
    requested_by: str
    tags: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class CertificationRequestCreate(BaseModel):
    """Create certification request."""
    reconciliation_session_id: Optional[UUID] = None
    conflict_ids: List[UUID] = Field(default_factory=list)
    entity_ids: List[UUID] = Field(default_factory=list)
    title: str
    description: str
    priority: int = 3
    analyst_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    due_at: Optional[datetime] = None
    sla_hours: int = 72
    requested_by: str
    tags: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class CertificationAction(BaseModel):
    """Certification action (decision by analyst/reviewer)."""
    request_id: UUID
    role: CertificationRole
    decision: CertificationDecision
    notes: Optional[str] = None
    decided_by: str


class CertificationComment(BaseModel):
    """Comment on certification request."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    author_id: str
    author_role: CertificationRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CertificationCommentCreate(BaseModel):
    """Create comment."""
    content: str


class CertificationStats(BaseModel):
    """Certification statistics."""
    total_requests: int
    pending: int
    in_review: int
    approved: int
    rejected: int
    escalated: int
    expired: int
    avg_resolution_hours: float
    sla_compliance_rate: float
    by_priority: Dict[str, int]
    by_analyst: Dict[str, int]
    by_reviewer: Dict[str, int]


class CertificationQueueItem(BaseModel):
    """Item in certification queue."""
    request_id: UUID
    title: str
    priority: int
    status: CertificationStatus
    assignee_id: Optional[str] = None
    assignee_role: Optional[CertificationRole] = None
    created_at: datetime
    due_at: Optional[datetime] = None
    sla_hours_remaining: Optional[float] = None
    conflict_count: int
    entity_count: int
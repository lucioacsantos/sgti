"""
Collection Job Models

Represents data collection jobs from various sources.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4


class CollectionType(str, Enum):
    """Type of data collection."""
    FULL = "full"           # Complete inventory
    INCREMENTAL = "incremental"  # Changes only
    DELTA = "delta"         # Since last successful
    MANUAL = "manual"       # On-demand


class CollectionStatus(str, Enum):
    """Collection job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"     # Some entities collected, some failed


class CollectionJob(BaseModel):
    """Data collection job."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    collection_type: CollectionType = CollectionType.FULL
    status: CollectionStatus = CollectionStatus.PENDING
    
    # Trigger info
    triggered_by: str = "scheduler"  # scheduler, manual, api, webhook
    triggered_by_user: Optional[str] = None
    
    # Progress tracking
    total_entities: int = 0
    processed_entities: int = 0
    failed_entities: int = 0
    current_entity_type: Optional[str] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Results
    entities_collected: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    entities_unchanged: int = 0
    entities_deleted: int = 0
    
    # Errors
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    
    # Metadata
    correlation_id: Optional[str] = None
    parent_job_id: Optional[UUID] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CollectionJobCreate(BaseModel):
    """Create collection job request."""
    source_id: UUID
    collection_type: CollectionType = CollectionType.FULL
    triggered_by: str = "manual"
    triggered_by_user: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_job_id: Optional[UUID] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class CollectionJobStatus(BaseModel):
    """Collection job status response."""
    id: UUID
    source_id: UUID
    status: CollectionStatus
    progress_percent: float
    current_entity_type: Optional[str] = None
    entities_collected: int
    entities_created: int
    entities_updated: int
    errors_count: int
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None


class CollectionStats(BaseModel):
    """Collection statistics."""
    source_id: UUID
    source_name: str
    source_type: str
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    total_entities_collected: int
    avg_duration_seconds: float
    last_collection_at: Optional[datetime] = None
    success_rate: float
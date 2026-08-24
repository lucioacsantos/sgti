"""
Data Source Models

Represents external data sources like vCenter, Satellite, etc.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4


class SourceType(str, Enum):
    """Supported data source types."""
    VCENTER = "vcenter"
    SATELLITE = "satellite"
    ANSIBLE = "ansible"
    NIFI = "nifi"
    MANUAL = "manual"
    API = "api"


class SourceStatus(str, Enum):
    """Data source connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"


class DataSource(BaseModel):
    """External data source configuration."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Human-readable name")
    source_type: SourceType
    status: SourceStatus = SourceStatus.INACTIVE
    
    # Connection configuration (encrypted in storage)
    host: str
    port: Optional[int] = None
    username: str
    password_encrypted: str  # Encrypted at rest
    
    # Source-specific config
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Collection settings
    enabled: bool = True
    collection_interval_minutes: int = 60
    timeout_seconds: int = 300
    
    # Metadata
    description: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_collection_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Stats
    total_collections: int = 0
    successful_collections: int = 0
    failed_collections: int = 0


class DataSourceCreate(BaseModel):
    """Create data source request."""
    name: str
    source_type: SourceType
    host: str
    port: Optional[int] = None
    username: str
    password: str  # Will be encrypted
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    collection_interval_minutes: int = 60
    timeout_seconds: int = 300
    description: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class DataSourceUpdate(BaseModel):
    """Update data source request."""
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    collection_interval_minutes: Optional[int] = None
    timeout_seconds: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    status: Optional[SourceStatus] = None


class DataSourceTestResult(BaseModel):
    """Result of testing a data source connection."""
    success: bool
    message: str
    latency_ms: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
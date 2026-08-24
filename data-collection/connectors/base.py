"""
Base Connector Interface

All source connectors must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from ..models.entity import CollectedEntity, EntityType
from ..models.collection import CollectionJob, CollectionType
from ..models.source import DataSource


class CollectionResult:
    """Result of a collection operation."""
    def __init__(
        self,
        entities: List[CollectedEntity],
        stats: Dict[str, int],
        warnings: List[str] = None,
        errors: List[Dict[str, Any]] = None
    ):
        self.entities = entities
        self.stats = stats  # {"created": n, "updated": n, "unchanged": n, "deleted": n, "errors": n}
        self.warnings = warnings or []
        self.errors = errors or []


class BaseConnector(ABC):
    """Base class for all data source connectors."""
    
    def __init__(self, source: DataSource):
        self.source = source
        self.config = source.config or {}
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the source."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test connectivity and return diagnostics."""
        pass
    
    @abstractmethod
    async def collect(
        self,
        job: CollectionJob,
        collection_type: CollectionType,
        since: Optional[datetime] = None,
        entity_types: List[EntityType] = None
    ) -> AsyncIterator[CollectionResult]:
        """
        Collect entities from the source.
        
        Yields CollectionResult batches for progress tracking.
        """
        pass
    
    @abstractmethod
    async def get_entity(
        self,
        entity_type: EntityType,
        source_entity_id: str
    ) -> Optional[CollectedEntity]:
        """Get a single entity by its source ID."""
        pass
    
    @abstractmethod
    async def get_schema(self) -> Dict[str, Any]:
        """Return the schema/capabilities of this connector."""
        pass
    
    def get_connector_type(self) -> str:
        """Return the connector type identifier."""
        return self.__class__.__name__.replace("Connector", "").lower()
    
    def build_unique_key(self, entity: CollectedEntity) -> str:
        """Build a unique key for deduplication."""
        return f"{self.source.id}:{entity.entity_type.value}:{entity.source_entity_id}"


class ConnectorRegistry:
    """Registry of available connectors."""
    
    _connectors: Dict[str, type] = {}
    
    @classmethod
    def register(cls, source_type: str, connector_class: type):
        """Register a connector for a source type."""
        cls._connectors[source_type] = connector_class
    
    @classmethod
    def get(cls, source_type: str) -> Optional[type]:
        """Get connector class for source type."""
        return cls._connectors.get(source_type)
    
    @classmethod
    def create(cls, source: DataSource) -> Optional[BaseConnector]:
        """Create connector instance for source."""
        connector_class = cls.get(source.source_type.value)
        if connector_class:
            return connector_class(source)
        return None
    
    @classmethod
    def list_available(cls) -> List[str]:
        """List available connector types."""
        return list(cls._connectors.keys())
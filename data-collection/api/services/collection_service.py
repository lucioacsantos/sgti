"""
Collection Service

Orchestrates data collection from various sources.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import asyncio
import logging

from sqlalchemy.orm import Session

from ..models.source import DataSource
from ..models.collection import CollectionJob, CollectionStatus, CollectionType
from ..models.entity import CollectedEntity, EntityType
from ..connectors.base import ConnectorRegistry, BaseConnector, CollectionResult

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for managing data collection jobs."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def run_collection_job(self, job_id: UUID) -> CollectionJob:
        """Execute a collection job."""
        job = self.db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        source = self.db.query(DataSource).filter(DataSource.id == job.source_id).first()
        if not source:
            raise ValueError(f"Source {job.source_id} not found")
        
        # Create connector
        connector = ConnectorRegistry.create(source)
        if not connector:
            raise ValueError(f"No connector for source type: {source.source_type}")
        
        # Update job status
        job.status = CollectionStatus.RUNNING
        job.started_at = datetime.utcnow()
        self.db.commit()
        
        try:
            stats = {
                "entities_collected": 0,
                "entities_created": 0,
                "entities_updated": 0,
                "entities_unchanged": 0,
                "entities_deleted": 0,
                "errors": 0,
            }
            
            # Determine if incremental
            since = None
            if job.collection_type == CollectionType.INCREMENTAL:
                last_job = self.db.query(CollectionJob).filter(
                    CollectionJob.source_id == job.source_id,
                    CollectionJob.status == CollectionStatus.COMPLETED,
                    CollectionJob.id != job.id
                ).order_by(CollectionJob.completed_at.desc()).first()
                
                if last_job:
                    since = last_job.completed_at
            
            # Collect entities
            async for result in connector.collect(job, job.collection_type, since=since):
                # Process batch
                batch_stats = await self._process_batch(result.entities, job, source)
                
                for key, value in batch_stats.items():
                    stats[key] += value
                
                # Update progress
                job.processed_entities += len(result.entities)
                job.updated_at = datetime.utcnow()
                self.db.commit()
            
            # Update final stats
            job.entities_collected = stats["entities_collected"]
            job.entities_created = stats["entities_created"]
            job.entities_updated = stats["entities_updated"]
            job.entities_unchanged = stats["entities_unchanged"]
            job.entities_deleted = stats["entities_deleted"]
            job.failed_entities = stats["errors"]
            
            job.status = CollectionStatus.COMPLETED if stats["errors"] == 0 else CollectionStatus.PARTIAL
            job.completed_at = datetime.utcnow()
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            
            # Update source stats
            source.total_collections += 1
            source.last_collection_at = datetime.utcnow()
            if stats["errors"] == 0:
                source.successful_collections += 1
                source.last_success_at = datetime.utcnow()
            else:
                source.failed_collections += 1
                source.last_error = f"{stats['errors']} errors during collection"
            
            self.db.commit()
            
        except Exception as e:
            logger.exception(f"Collection job {job_id} failed")
            job.status = CollectionStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds() if job.started_at else 0
            
            source.failed_collections += 1
            source.last_error = str(e)
            
            self.db.commit()
        
        return job
    
    async def _process_batch(
        self,
        entities: List[CollectedEntity],
        job: CollectionJob,
        source: DataSource
    ) -> Dict[str, int]:
        """Process a batch of collected entities."""
        stats = {
            "entities_collected": 0,
            "entities_created": 0,
            "entities_updated": 0,
            "entities_unchanged": 0,
            "entities_deleted": 0,
            "errors": 0,
        }
        
        for entity in entities:
            try:
                # Set collection metadata
                entity.collection_job_id = job.id
                entity.source_id = source.id
                
                # Check if entity exists
                existing = self.db.query(CollectedEntity).filter(
                    CollectedEntity.source_id == entity.source_id,
                    CollectedEntity.source_unique_key == entity.source_unique_key
                ).first()
                
                if existing:
                    # Check if changed
                    if self._entity_changed(existing, entity):
                        # Update
                        for field, value in entity.model_dump(
                            exclude={"id", "created_at", "first_seen_at", "collection_job_id"}
                        ).items():
                            setattr(existing, field, value)
                        existing.last_seen_at = datetime.utcnow()
                        existing.updated_at = datetime.utcnow()
                        stats["entities_updated"] += 1
                    else:
                        # Unchanged
                        existing.last_seen_at = datetime.utcnow()
                        stats["entities_unchanged"] += 1
                else:
                    # New entity
                    entity.first_seen_at = datetime.utcnow()
                    self.db.add(entity)
                    stats["entities_created"] += 1
                
                stats["entities_collected"] += 1
                
            except Exception as e:
                logger.error(f"Failed to process entity {entity.source_unique_key}: {e}")
                stats["errors"] += 1
        
        self.db.commit()
        return stats
    
    def _entity_changed(self, existing: CollectedEntity, new: CollectedEntity) -> bool:
        """Check if entity has changed."""
        # Compare key attributes
        key_attrs = [
            "name", "datacenter", "rack", "manufacturer", "model",
            "serial_number", "cpu_cores", "cpu_threads", "cpu_model",
            "memory_gb", "primary_ip", "power_state", "connection_state",
            "total_storage_gb", "os", "network_interfaces", "disks",
            "tags", "annotations", "custom_fields", "raw_data",
        ]
        
        for attr in key_attrs:
            old_val = getattr(existing, attr, None)
            new_val = getattr(new, attr, None)
            
            if old_val != new_val:
                return True
        
        return False
    
    async def schedule_recurring_collections(self):
        """Schedule recurring collections for enabled sources."""
        sources = self.db.query(DataSource).filter(
            DataSource.enabled == True,
            DataSource.status == "active"
        ).all()
        
        for source in sources:
            # Check if it's time to run
            if source.last_collection_at:
                elapsed = datetime.utcnow() - source.last_collection_at
                if elapsed.total_seconds() < source.collection_interval_minutes * 60:
                    continue
            
            # Create job
            job = CollectionJob(
                source_id=source.id,
                collection_type=CollectionType.INCREMENTAL,
                triggered_by="scheduler",
            )
            self.db.add(job)
        
        self.db.commit()
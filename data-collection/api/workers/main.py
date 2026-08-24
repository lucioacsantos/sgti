"""
Worker Main Entry Point

Runs background workers for collection, reconciliation, and certification.
"""
import os
import asyncio
import signal
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..database import get_db, init_db
from ..services.collection_service import CollectionService
from ..services.reconciliation_service import ReconciliationService
from ..services.certification_service import CertificationAPIService
from ..models.collection import CollectionJob, CollectionStatus
from ..models.reconciliation import ReconciliationSession
from ..models.certification import CertificationRequest, CertificationStatus
from ..models.source import DataSource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages background workers."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.worker_type = os.getenv("WORKER_TYPE", "collection")
    
    async def start(self):
        """Start the worker."""
        logger.info(f"Starting {self.worker_type} worker...")
        
        # Initialize database
        init_db()
        
        # Register signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown)
        
        # Schedule jobs based on worker type
        if self.worker_type == "collection":
            self._schedule_collection_jobs()
        elif self.worker_type == "reconciliation":
            self._schedule_reconciliation_jobs()
        elif self.worker_type == "certification":
            self._schedule_certification_jobs()
        
        self.scheduler.start()
        self.running = True
        
        logger.info(f"{self.worker_type} worker started")
        
        # Keep running
        while self.running:
            await asyncio.sleep(60)
    
    def _shutdown(self):
        """Shutdown the worker."""
        logger.info("Shutting down worker...")
        self.running = False
        self.scheduler.shutdown(wait=True)
    
    def _schedule_collection_jobs(self):
        """Schedule collection jobs."""
        # Check for pending jobs every 30 seconds
        self.scheduler.add_job(
            self._process_pending_collection_jobs,
            IntervalTrigger(seconds=30),
            id="process_collection_jobs",
            max_instances=1,
            coalesce=True,
        )
        
        # Schedule recurring collections every 5 minutes
        self.scheduler.add_job(
            self._schedule_recurring_collections,
            IntervalTrigger(minutes=5),
            id="schedule_recurring",
            max_instances=1,
            coalesce=True,
        )
    
    def _schedule_reconciliation_jobs(self):
        """Schedule reconciliation jobs."""
        # Check for pending reconciliations every minute
        self.scheduler.add_job(
            self._process_pending_reconciliations,
            IntervalTrigger(minutes=1),
            id="process_reconciliations",
            max_instances=1,
            coalesce=True,
        )
    
    def _schedule_certification_jobs(self):
        """Schedule certification jobs."""
        # Check SLA breaches every 5 minutes
        self.scheduler.add_job(
            self._check_sla_breaches,
            IntervalTrigger(minutes=5),
            id="check_sla",
            max_instances=1,
            coalesce=True,
        )
        
        # Send reminders every hour
        self.scheduler.add_job(
            self._send_reminders,
            IntervalTrigger(hours=1),
            id="send_reminders",
            max_instances=1,
            coalesce=True,
        )
    
    async def _process_pending_collection_jobs(self):
        """Process pending collection jobs."""
        db = next(get_db())
        try:
            service = CollectionService(db)
            
            # Get pending jobs
            jobs = db.query(CollectionJob).filter(
                CollectionJob.status.in_(["pending", "running"])
            ).limit(10).all()
            
            for job in jobs:
                try:
                    logger.info(f"Processing collection job {job.id}")
                    await service.run_collection_job(job.id)
                except Exception as e:
                    logger.error(f"Failed to process job {job.id}: {e}")
        finally:
            db.close()
    
    async def _schedule_recurring_collections(self):
        """Schedule recurring collections for enabled sources."""
        db = next(get_db())
        try:
            service = CollectionService(db)
            await service.schedule_recurring_collections()
        finally:
            db.close()
    
    async def _process_pending_reconciliations(self):
        """Process pending reconciliation sessions."""
        db = next(get_db())
        try:
            service = ReconciliationService(db)
            
            sessions = db.query(ReconciliationSession).filter(
                ReconciliationSession.status == "pending"
            ).limit(5).all()
            
            for session in sessions:
                try:
                    logger.info(f"Processing reconciliation session {session.id}")
                    await service.run_reconciliation(session.id)
                    
                    # Auto-create certification requests for high/critical conflicts
                    await self._auto_create_certifications(session.id, db)
                except Exception as e:
                    logger.error(f"Failed to process session {session.id}: {e}")
        finally:
            db.close()
    
    async def _auto_create_certifications(self, session_id, db):
        """Auto-create certification requests for conflicts requiring certification."""
        from ..services.certification_service import CertificationAPIService
        
        cert_service = CertificationAPIService(db)
        
        # Get conflicts requiring certification
        conflicts = await cert_service.get_conflicts_by_session(
            session_id, requires_certification=True
        )
        
        if conflicts:
            # Group by session
            await cert_service.create_from_conflicts(
                conflicts=conflicts,
                requested_by="system",
                title=f"Auto-certification for session {session_id}",
                description=f"Automatically created for {len(conflicts)} conflicts requiring certification",
                priority=2,  # High priority for auto-created
            )
    
    async def _check_sla_breaches(self):
        """Check for certification SLA breaches."""
        db = next(get_db())
        try:
            from ..services.certification_service import CertificationAPIService
            cert_service = CertificationAPIService(db)
            await cert_service.check_sla_breaches()
        finally:
            db.close()
    
    async def _send_reminders(self):
        """Send certification reminders."""
        db = next(get_db())
        try:
            # TODO: Implement reminder notifications
            logger.info("Sending certification reminders...")
        finally:
            db.close()


async def main():
    """Main entry point."""
    worker = WorkerManager()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
"""
Data Collection Service API

FastAPI application exposing the data collection service functionality.
Independent from the main CMDB application.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from .database import engine, Base, get_db
from .models.source import DataSource, DataSourceCreate, DataSourceUpdate, SourceType, SourceStatus
from .models.collection import CollectionJob, CollectionJobCreate, CollectionStatus, CollectionType
from .models.entity import CollectedEntity, EntityType
from .models.reconciliation import ReconciliationSession, ReconciliationSessionCreate, Conflict, ConflictType
from .models.certification import CertificationRequest, CertificationRequestCreate, CertificationStatus
from .services.collection_service import CollectionService
from .services.reconciliation_service import ReconciliationService
from .services.certification_service import CertificationService
from .connectors.base import ConnectorRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    Base.metadata.create_all(bind=engine)
    print("Data Collection Service started")
    yield
    # Shutdown
    print("Data Collection Service stopped")


app = FastAPI(
    title="SGTI Data Collection Service",
    version="1.0.0",
    description="Independent service for collecting, reconciling, and certifying infrastructure data",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "path": request.url.path},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": request.url.path},
    )


# Health check
@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "degraded", "database": "disconnected", "error": str(e)}


@app.get("/health/detailed", tags=["Health"])
async def detailed_health(db: Session = Depends(get_db)):
    """Detailed health check with connector status."""
    connectors = ConnectorRegistry.list_available()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "connectors_available": connectors,
        "database": "connected",
    }


# Data Sources
@app.post("/api/v1/sources", response_model=DataSource, status_code=201, tags=["Data Sources"])
async def create_source(source: DataSourceCreate, db: Session = Depends(get_db)):
    """Create a new data source."""
    # Check if connector exists
    if not ConnectorRegistry.get(source.source_type.value):
        raise HTTPException(status_code=400, detail=f"Unsupported source type: {source.source_type}")
    
    # Encrypt password (placeholder - use proper encryption)
    import base64
    password_encrypted = base64.b64encode(source.password.encode()).decode()
    
    db_source = DataSource(
        **source.model_dump(exclude={"password"}),
        password_encrypted=password_encrypted,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@app.get("/api/v1/sources", response_model=List[DataSource], tags=["Data Sources"])
async def list_sources(
    source_type: Optional[SourceType] = None,
    status: Optional[SourceStatus] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List data sources with optional filters."""
    query = db.query(DataSource)
    
    if source_type:
        query = query.filter(DataSource.source_type == source_type)
    if status:
        query = query.filter(DataSource.status == status)
    if enabled is not None:
        query = query.filter(DataSource.enabled == enabled)
    
    return query.offset(skip).limit(limit).all()


@app.get("/api/v1/sources/{source_id}", response_model=DataSource, tags=["Data Sources"])
async def get_source(source_id: UUID, db: Session = Depends(get_db)):
    """Get a data source by ID."""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return source


@app.patch("/api/v1/sources/{source_id}", response_model=DataSource, tags=["Data Sources"])
async def update_source(source_id: UUID, source: DataSourceUpdate, db: Session = Depends(get_db)):
    """Update a data source."""
    db_source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    update_data = source.model_dump(exclude_unset=True)
    
    # Handle password encryption
    if "password" in update_data:
        import base64
        update_data["password_encrypted"] = base64.b64encode(update_data.pop("password").encode()).decode()
    
    for field, value in update_data.items():
        setattr(db_source, field, value)
    
    db_source.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_source)
    return db_source


@app.delete("/api/v1/sources/{source_id}", status_code=204, tags=["Data Sources"])
async def delete_source(source_id: UUID, db: Session = Depends(get_db)):
    """Delete a data source."""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    db.delete(source)
    db.commit()


@app.post("/api/v1/sources/{source_id}/test", tags=["Data Sources"])
async def test_source(source_id: UUID, db: Session = Depends(get_db)):
    """Test connection to a data source."""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    connector = ConnectorRegistry.create(source)
    if not connector:
        raise HTTPException(status_code=400, detail=f"No connector for source type: {source.source_type}")
    
    result = await connector.test_connection()
    return result


# Collection Jobs
@app.post("/api/v1/collection/jobs", response_model=CollectionJob, status_code=201, tags=["Collection Jobs"])
async def create_collection_job(job: CollectionJobCreate, db: Session = Depends(get_db)):
    """Create a new collection job."""
    db_job = CollectionJob(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # TODO: Queue job for async execution
    return db_job


@app.get("/api/v1/collection/jobs", response_model=List[CollectionJob], tags=["Collection Jobs"])
async def list_collection_jobs(
    source_id: Optional[UUID] = None,
    status: Optional[CollectionStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List collection jobs."""
    query = db.query(CollectionJob)
    
    if source_id:
        query = query.filter(CollectionJob.source_id == source_id)
    if status:
        query = query.filter(CollectionJob.status == status)
    
    return query.order_by(CollectionJob.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/v1/collection/jobs/{job_id}", response_model=CollectionJob, tags=["Collection Jobs"])
async def get_collection_job(job_id: UUID, db: Session = Depends(get_db)):
    """Get collection job details."""
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Collection job not found")
    return job


@app.patch("/api/v1/collection/jobs/{job_id}/progress", tags=["Collection Jobs"])
async def update_job_progress(
    job_id: UUID,
    processed_entities: int,
    current_entity_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update collection job progress."""
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Collection job not found")
    
    job.processed_entities = processed_entities
    if current_entity_type:
        job.current_entity_type = current_entity_type
    job.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "updated"}


@app.post("/api/v1/collection/jobs/{job_id}/complete", tags=["Collection Jobs"])
async def complete_job(
    job_id: UUID,
    status: CollectionStatus = CollectionStatus.COMPLETED,
    db: Session = Depends(get_db)
):
    """Mark collection job as complete."""
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Collection job not found")
    
    job.status = status
    job.completed_at = datetime.utcnow()
    if job.started_at:
        job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
    
    db.commit()
    return {"status": "completed"}


# Entities
@app.post("/api/v1/entities", response_model=CollectedEntity, status_code=201, tags=["Entities"])
async def create_entity(entity: CollectedEntity, db: Session = Depends(get_db)):
    """Create or update a collected entity."""
    # Check if entity already exists
    existing = db.query(CollectedEntity).filter(
        CollectedEntity.source_id == entity.source_id,
        CollectedEntity.source_unique_key == entity.source_unique_key
    ).first()
    
    if existing:
        # Update existing
        for field, value in entity.model_dump(exclude={"id", "created_at", "first_seen_at"}).items():
            setattr(existing, field, value)
        existing.last_seen_at = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity


@app.post("/api/v1/entities/batch", response_model=List[CollectedEntity], tags=["Entities"])
async def create_entities_batch(entities: List[CollectedEntity], db: Session = Depends(get_db)):
    """Create multiple entities in batch."""
    results = []
    for entity in entities:
        existing = db.query(CollectedEntity).filter(
            CollectedEntity.source_id == entity.source_id,
            CollectedEntity.source_unique_key == entity.source_unique_key
        ).first()
        
        if existing:
            for field, value in entity.model_dump(exclude={"id", "created_at", "first_seen_at"}).items():
                setattr(existing, field, value)
            existing.last_seen_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            results.append(existing)
        else:
            db.add(entity)
            results.append(entity)
    
    db.commit()
    for r in results:
        db.refresh(r)
    return results


@app.get("/api/v1/entities", response_model=List[CollectedEntity], tags=["Entities"])
async def list_entities(
    source_id: Optional[UUID] = None,
    entity_type: Optional[EntityType] = None,
    is_certified: Optional[bool] = None,
    is_deleted: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List collected entities with filters."""
    query = db.query(CollectedEntity)
    
    if source_id:
        query = query.filter(CollectedEntity.source_id == source_id)
    if entity_type:
        query = query.filter(CollectedEntity.entity_type == entity_type)
    if is_certified is not None:
        query = query.filter(CollectedEntity.is_certified == is_certified)
    if not is_deleted:
        query = query.filter(CollectedEntity.is_deleted == False)
    
    return query.order_by(CollectedEntity.collected_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/v1/entities/{entity_id}", response_model=CollectedEntity, tags=["Entities"])
async def get_entity(entity_id: UUID, db: Session = Depends(get_db)):
    """Get entity by ID."""
    entity = db.query(CollectedEntity).filter(CollectedEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


# Reconciliation
@app.post("/api/v1/reconciliation/sessions", response_model=ReconciliationSession, status_code=201, tags=["Reconciliation"])
async def create_reconciliation_session(session: ReconciliationSessionCreate, db: Session = Depends(get_db)):
    """Create a new reconciliation session."""
    db_session = ReconciliationSession(**session.model_dump())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    # TODO: Queue for async execution
    return db_session


@app.get("/api/v1/reconciliation/sessions", response_model=List[ReconciliationSession], tags=["Reconciliation"])
async def list_reconciliation_sessions(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List reconciliation sessions."""
    query = db.query(ReconciliationSession)
    
    if status:
        query = query.filter(ReconciliationSession.status == status)
    
    return query.order_by(ReconciliationSession.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/v1/reconciliation/sessions/{session_id}", response_model=ReconciliationSession, tags=["Reconciliation"])
async def get_reconciliation_session(session_id: UUID, db: Session = Depends(get_db)):
    """Get reconciliation session details."""
    session = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Reconciliation session not found")
    return session


@app.get("/api/v1/reconciliation/sessions/{session_id}/conflicts", response_model=List[Conflict], tags=["Reconciliation"])
async def get_session_conflicts(
    session_id: UUID,
    severity: Optional[ConflictType] = None,
    resolved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get conflicts for a reconciliation session."""
    query = db.query(Conflict).filter(Conflict.reconciliation_session_id == session_id)
    
    if severity:
        query = query.filter(Conflict.severity == severity)
    if resolved is not None:
        if resolved:
            query = query.filter(Conflict.resolution.isnot(None))
        else:
            query = query.filter(Conflict.resolution.is_(None))
    
    return query.order_by(Conflict.severity.desc(), Conflict.detected_at.desc()).offset(skip).limit(limit).all()


@app.post("/api/v1/reconciliation/conflicts/{conflict_id}/resolve", tags=["Reconciliation"])
async def resolve_conflict(
    conflict_id: UUID,
    resolution: str,
    resolved_value: Optional[str] = None,
    notes: Optional[str] = None,
    resolved_by: str = "api",
    db: Session = Depends(get_db)
):
    """Resolve a conflict."""
    conflict = db.query(Conflict).filter(Conflict.id == conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    conflict.resolution = resolution
    conflict.resolved_value = resolved_value
    conflict.resolution_notes = notes
    conflict.resolved_by = resolved_by
    conflict.resolved_at = datetime.utcnow()
    conflict.updated_at = datetime.utcnow()
    
    db.commit()
    return {"status": "resolved"}


# Certification
@app.post("/api/v1/certification/requests", response_model=CertificationRequest, status_code=201, tags=["Certification"])
async def create_certification_request(request: CertificationRequestCreate, db: Session = Depends(get_db)):
    """Create a certification request."""
    db_request = CertificationRequest(**request.model_dump())
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request


@app.get("/api/v1/certification/requests", response_model=List[CertificationRequest], tags=["Certification"])
async def list_certification_requests(
    status: Optional[CertificationStatus] = None,
    assignee_id: Optional[str] = None,
    role: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List certification requests."""
    query = db.query(CertificationRequest)
    
    if status:
        query = query.filter(CertificationRequest.status == status)
    if assignee_id:
        query = query.filter(
            (CertificationRequest.analyst_id == assignee_id) |
            (CertificationRequest.reviewer_id == assignee_id)
        )
    
    return query.order_by(CertificationRequest.priority, CertificationRequest.created_at.desc()).offset(skip).limit(limit).all()


@app.get("/api/v1/certification/requests/{request_id}", response_model=CertificationRequest, tags=["Certification"])
async def get_certification_request(request_id: UUID, db: Session = Depends(get_db)):
    """Get certification request details."""
    request = db.query(CertificationRequest).filter(CertificationRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Certification request not found")
    return request


@app.post("/api/v1/certification/requests/{request_id}/action", tags=["Certification"])
async def certification_action(
    request_id: UUID,
    role: str,
    decision: str,
    notes: Optional[str] = None,
    decided_by: str = "api",
    db: Session = Depends(get_db)
):
    """Take action on a certification request."""
    request = db.query(CertificationRequest).filter(CertificationRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Certification request not found")
    
    # Record decision
    if role == "analyst":
        request.analyst_decision = decision
        request.analyst_notes = notes
        request.analyst_decided_at = datetime.utcnow()
        request.status = "in_review_reviewer"
    elif role == "reviewer":
        request.reviewer_decision = decision
        request.reviewer_notes = notes
        request.reviewer_decided_at = datetime.utcnow()
        
        # Evaluate outcome
        if decision == "approve" and request.analyst_decision == "approve":
            request.final_decision = "approve"
            request.status = "approved"
            request.completed_at = datetime.utcnow()
            request.decided_at = datetime.utcnow()
            request.decided_by = decided_by
        elif decision == "reject":
            request.final_decision = "reject"
            request.status = "rejected"
            request.completed_at = datetime.utcnow()
            request.decided_at = datetime.utcnow()
            request.decided_by = decided_by
        else:
            request.status = "in_review_analyst"
    
    request.updated_at = datetime.utcnow()
    db.commit()
    return {"status": request.status}


# Connectors
@app.get("/api/v1/connectors", tags=["Connectors"])
async def list_connectors():
    """List available connectors."""
    return {"connectors": ConnectorRegistry.list_available()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
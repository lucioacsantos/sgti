-- Data Collection Service Database Initialization
-- Run on first container startup

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS datacollection;
SET search_path TO datacollection, public;

-- Data Sources table
CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'inactive',
    
    host VARCHAR(255) NOT NULL,
    port INTEGER,
    username VARCHAR(255) NOT NULL,
    password_encrypted TEXT NOT NULL,
    
    config JSONB DEFAULT '{}',
    
    enabled BOOLEAN DEFAULT TRUE,
    collection_interval_minutes INTEGER DEFAULT 60,
    timeout_seconds INTEGER DEFAULT 300,
    
    description TEXT,
    tags JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_collection_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    
    total_collections INTEGER DEFAULT 0,
    successful_collections INTEGER DEFAULT 0,
    failed_collections INTEGER DEFAULT 0
);

CREATE INDEX idx_data_sources_type ON data_sources(source_type);
CREATE INDEX idx_data_sources_status ON data_sources(status);
CREATE INDEX idx_data_sources_enabled ON data_sources(enabled);

-- Collection Jobs table
CREATE TABLE IF NOT EXISTS collection_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    collection_type VARCHAR(50) NOT NULL DEFAULT 'full',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    triggered_by VARCHAR(50) DEFAULT 'scheduler',
    triggered_by_user VARCHAR(255),
    
    total_entities INTEGER DEFAULT 0,
    processed_entities INTEGER DEFAULT 0,
    failed_entities INTEGER DEFAULT 0,
    current_entity_type VARCHAR(100),
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds REAL,
    
    entities_collected INTEGER DEFAULT 0,
    entities_created INTEGER DEFAULT 0,
    entities_updated INTEGER DEFAULT 0,
    entities_unchanged INTEGER DEFAULT 0,
    entities_deleted INTEGER DEFAULT 0,
    
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    warnings JSONB DEFAULT '[]',
    
    correlation_id VARCHAR(255),
    parent_job_id UUID REFERENCES collection_jobs(id),
    tags JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_collection_jobs_source ON collection_jobs(source_id);
CREATE INDEX idx_collection_jobs_status ON collection_jobs(status);
CREATE INDEX idx_collection_jobs_created ON collection_jobs(created_at DESC);

-- Collected Entities table
CREATE TABLE IF NOT EXISTS collected_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    entity_type VARCHAR(100) NOT NULL,
    source_entity_id VARCHAR(255) NOT NULL,
    source_unique_key VARCHAR(500) NOT NULL,
    
    name VARCHAR(500) NOT NULL,
    display_name VARCHAR(500),
    description TEXT,
    
    parent_id UUID REFERENCES collected_entities(id),
    parent_source_id VARCHAR(255),
    children_ids UUID[] DEFAULT '{}',
    
    datacenter VARCHAR(255),
    rack VARCHAR(100),
    rack_unit VARCHAR(50),
    
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    serial_number VARCHAR(255),
    uuid VARCHAR(255),
    
    cpu_cores INTEGER,
    cpu_threads INTEGER,
    cpu_model VARCHAR(255),
    cpu_mhz INTEGER,
    memory_gb INTEGER,
    
    os JSONB,
    
    network_interfaces JSONB DEFAULT '[]',
    primary_ip INET,
    
    disks JSONB DEFAULT '[]',
    total_storage_gb INTEGER,
    
    power_state VARCHAR(50) DEFAULT 'unknown',
    connection_state VARCHAR(100),
    
    tags JSONB DEFAULT '{}',
    annotations JSONB DEFAULT '{}',
    custom_fields JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',
    
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    collection_job_id UUID NOT NULL REFERENCES collection_jobs(id),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    
    reconciliation_id UUID,
    conflict_count INTEGER DEFAULT 0,
    is_certified BOOLEAN DEFAULT FALSE,
    certified_at TIMESTAMP WITH TIME ZONE,
    certified_by VARCHAR(255),
    
    UNIQUE(source_id, source_unique_key)
);

CREATE INDEX idx_entities_source ON collected_entities(source_id);
CREATE INDEX idx_entities_type ON collected_entities(entity_type);
CREATE INDEX idx_entities_unique_key ON collected_entities(source_unique_key);
CREATE INDEX idx_entities_name ON collected_entities(name);
CREATE INDEX idx_entities_datacenter ON collected_entities(datacenter);
CREATE INDEX idx_entities_certified ON collected_entities(is_certified);
CREATE INDEX idx_entities_deleted ON collected_entities(is_deleted);
CREATE INDEX idx_entities_parent ON collected_entities(parent_id);
CREATE INDEX idx_entities_job ON collected_entities(collection_job_id);

-- Reconciliation Sessions table
CREATE TABLE IF NOT EXISTS reconciliation_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    source_ids UUID[] NOT NULL,
    primary_source_id UUID NOT NULL REFERENCES data_sources(id),
    
    entity_types VARCHAR(100)[],
    filters JSONB DEFAULT '{}',
    
    status VARCHAR(50) DEFAULT 'pending',
    progress_percent REAL DEFAULT 0.0,
    
    total_entities_compared INTEGER DEFAULT 0,
    conflicts_found INTEGER DEFAULT 0,
    conflicts_resolved INTEGER DEFAULT 0,
    conflicts_auto_resolved INTEGER DEFAULT 0,
    conflicts_manual_resolved INTEGER DEFAULT 0,
    conflicts_certification_required INTEGER DEFAULT 0,
    
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds REAL,
    
    entities_matched INTEGER DEFAULT 0,
    entities_only_in_primary INTEGER DEFAULT 0,
    entities_only_in_secondary INTEGER DEFAULT 0,
    
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    
    triggered_by VARCHAR(50) DEFAULT 'scheduler',
    triggered_by_user VARCHAR(255),
    correlation_id VARCHAR(255),
    tags JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_reconciliation_status ON reconciliation_sessions(status);
CREATE INDEX idx_reconciliation_created ON reconciliation_sessions(created_at DESC);

-- Conflicts table
CREATE TABLE IF NOT EXISTS conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reconciliation_session_id UUID NOT NULL REFERENCES reconciliation_sessions(id),
    
    conflict_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    
    entity_a_id UUID REFERENCES collected_entities(id),
    entity_b_id UUID REFERENCES collected_entities(id),
    entity_a_source_id UUID NOT NULL REFERENCES data_sources(id),
    entity_b_source_id UUID NOT NULL REFERENCES data_sources(id),
    
    attribute_name VARCHAR(255),
    value_a JSONB,
    value_b JSONB,
    
    description TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    
    resolution VARCHAR(50),
    resolved_value JSONB,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    
    requires_certification BOOLEAN DEFAULT FALSE,
    certification_request_id UUID,
    
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conflicts_session ON conflicts(reconciliation_session_id);
CREATE INDEX idx_conflicts_severity ON conflicts(severity);
CREATE INDEX idx_conflicts_type ON conflicts(conflict_type);
CREATE INDEX idx_conflicts_resolution ON conflicts(resolution);
CREATE INDEX idx_conflicts_certification ON conflicts(requires_certification);

-- Reconciliation Rules table
CREATE TABLE IF NOT EXISTS reconciliation_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    entity_types VARCHAR(100)[] DEFAULT '{}',
    source_types VARCHAR(100)[] DEFAULT '{}',
    attributes VARCHAR(255)[] DEFAULT '{}',
    
    condition JSONB DEFAULT '{}',
    
    action VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 100,
    
    parameters JSONB DEFAULT '{}',
    
    enabled BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_rules_enabled ON reconciliation_rules(enabled);
CREATE INDEX idx_rules_priority ON reconciliation_rules(priority);

-- Certification Requests table
CREATE TABLE IF NOT EXISTS certification_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    reconciliation_session_id UUID REFERENCES reconciliation_sessions(id),
    conflict_ids UUID[] DEFAULT '{}',
    entity_ids UUID[] DEFAULT '{}',
    
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    
    status VARCHAR(50) DEFAULT 'pending',
    
    analyst_id VARCHAR(255),
    reviewer_id VARCHAR(255),
    manager_id VARCHAR(255),
    
    analyst_decision VARCHAR(50),
    analyst_notes TEXT,
    analyst_decided_at TIMESTAMP WITH TIME ZONE,
    
    reviewer_decision VARCHAR(50),
    reviewer_notes TEXT,
    reviewer_decided_at TIMESTAMP WITH TIME ZONE,
    
    manager_decision VARCHAR(50),
    manager_notes TEXT,
    manager_decided_at TIMESTAMP WITH TIME ZONE,
    
    final_decision VARCHAR(50),
    final_notes TEXT,
    decided_at TIMESTAMP WITH TIME ZONE,
    decided_by VARCHAR(255),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    due_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    sla_hours INTEGER DEFAULT 72,
    sla_breached BOOLEAN DEFAULT FALSE,
    
    requested_by VARCHAR(255) NOT NULL,
    tags JSONB DEFAULT '{}',
    correlation_id VARCHAR(255)
);

CREATE INDEX idx_cert_status ON certification_requests(status);
CREATE INDEX idx_cert_analyst ON certification_requests(analyst_id);
CREATE INDEX idx_cert_reviewer ON certification_requests(reviewer_id);
CREATE INDEX idx_cert_priority ON certification_requests(priority);
CREATE INDEX idx_cert_due ON certification_requests(due_at);
CREATE INDEX idx_cert_session ON certification_requests(reconciliation_session_id);

-- Certification Comments table
CREATE TABLE IF NOT EXISTS certification_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES certification_requests(id),
    
    author_id VARCHAR(255) NOT NULL,
    author_role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cert_comments_request ON certification_comments(request_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA datacollection TO datacollection;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA datacollection TO datacollection;
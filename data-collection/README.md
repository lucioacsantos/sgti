# SGTI Data Collection Service

Independent microservice for collecting, reconciling, and certifying infrastructure data from multiple sources (vCenter, Satellite, etc.) for the CMDB.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   vCenter       │     │   Satellite      │     │   Other Sources │
│   (VMware)      │     │   (Red Hat)      │     │   (Ansible,     │
└────────┬────────┘     └────────┬─────────┘     │    NiFi, API)   │
         │                       │                └────────┬────────┘
         ▼                       ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Collection Service                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Connectors  │  │  Engine     │  │  API        │             │
│  │ (vCenter,   │──│  (Reconcile │──│  (REST,     │             │
│  │  Satellite) │  │   & Rules)  │  │   Webhooks) │             │
│  └─────────────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────────────────────┼──────────────────┼────────────────────┘
                          │                  │
                          ▼                  ▼
              ┌─────────────────────┐  ┌─────────────────────┐
              │  Reconciliation     │  │  Certification      │
              │  Conflicts & Rules  │  │  (Analyst +         │
              │                     │  │   Reviewer)         │
              └─────────────────────┘  └─────────────────────┘
                          │                  │
                          └────────┬─────────┘
                                   ▼
                    ┌─────────────────────────┐
                    │      CMDB API           │
                    │   (Certified Data)      │
                    └─────────────────────────┘
```

## Components

### 1. Connectors (`connectors/`)
- **vCenter Connector** - Uses pyvmomi to collect clusters, hosts, VMs, datastores, networks
- **Satellite Connector** - Uses REST API to collect physical servers, subscriptions, facts
- **Extensible** - Add new connectors by implementing `BaseConnector`

### 2. Reconciliation Engine (`reconciliation/`)
- Compares entities from multiple sources
- Detects conflicts (attribute mismatches, missing entities, hierarchy differences)
- Applies automatic resolution rules
- Generates conflicts for manual review

### 3. Certification Workflow (`certification/`)
- Two-phase approval: Analyst validates → Reviewer approves
- SLA tracking and escalation
- Comments and audit trail
- Auto-creation from high-severity conflicts

### 4. API (`api/`)
- FastAPI REST API
- Async job processing with workers
- Prometheus metrics
- Health checks

### 5. Automation (`ansible/`, `nifi/`)
- **Ansible Roles** - vCenter and Satellite collection playbooks
- **NiFi Flows** - Visual data flow templates

## Quick Start

### With Docker Compose

```bash
cd data-collection
docker-compose up -d
```

Services:
- API: http://localhost:8001
- Prometheus: http://localhost:9091
- Grafana: http://localhost:3001 (admin/admin)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATA_COLLECTION_DATABASE_URL=postgresql://user:pass@localhost/db
export DATA_COLLECTION_REDIS_URL=redis://localhost:6379/0

# Run API
uvicorn api.main:app --reload --port 8001

# Run workers
python -m api.workers.main  # Collection worker
WORKER_TYPE=reconciliation python -m api.workers.main
WORKER_TYPE=certification python -m api.workers.main
```

## Configuration

### Data Sources

Create a data source via API:

```bash
curl -X POST http://localhost:8001/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production vCenter",
    "source_type": "vcenter",
    "host": "vcenter.example.com",
    "username": "svc-cmdb",
    "password": "secret",
    "config": {
      "datacenter_filter": ["DC1", "DC2"]
    }
  }'
```

### Collection Job

Trigger a collection:

```bash
curl -X POST http://localhost:8001/api/v1/collection/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "<source-uuid>",
    "collection_type": "full",
    "triggered_by": "manual"
  }'
```

### Reconciliation

Create a reconciliation session:

```bash
curl -X POST http://localhost:8001/api/v1/reconciliation/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily vCenter vs Satellite",
    "source_ids": ["<vcenter-uuid>", "<satellite-uuid>"],
    "primary_source_id": "<vcenter-uuid>",
    "entity_types": ["vcenter_vm", "physical_server"]
  }'
```

### Certification

Resolve conflicts:

```bash
# Get conflicts
curl http://localhost:8001/api/v1/reconciliation/sessions/<session-id>/conflicts

# Resolve conflict
curl -X POST http://localhost:8001/api/v1/reconciliation/conflicts/<conflict-id>/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "source_a_wins",
    "resolved_by": "analyst"
  }'

# Or create certification request
curl -X POST http://localhost:8001/api/v1/certification/requests \
  -H "Content-Type: application/json" \
  -d '{
    "reconciliation_session_id": "<session-id>",
    "title": "Review conflicts",
    "description": "Please review",
    "requested_by": "analyst",
    "analyst_id": "user1",
    "reviewer_id": "user2"
  }'
```

## Ansible Collection

### Install Collection

```bash
ansible-galaxy collection install git+https://github.com/sgti/ansible-collection-inventory.git
```

### Run vCenter Collection

```yaml
- hosts: localhost
  vars:
    vcenter_host: "vcenter.example.com"
    vcenter_username: "svc-cmdb"
    vcenter_password: "{{ vault_vcenter_password }}"
    collection_service_url: "http://data-collection:8001"
    collection_service_token: "{{ vault_collection_token }}"
    vcenter_source_id: "<source-uuid>"
  roles:
    - sgti.inventory.vcenter_collection
```

### Run Satellite Collection

```yaml
- hosts: localhost
  vars:
    satellite_host: "satellite.example.com"
    satellite_username: "svc-cmdb"
    satellite_password: "{{ vault_satellite_password }}"
    collection_service_url: "http://data-collection:8001"
    collection_service_token: "{{ vault_collection_token }}"
    satellite_source_id: "<source-uuid>"
  roles:
    - sgti.inventory.satellite_collection
```

## NiFi Flows

Import the flow JSON files in `nifi/flows/` into NiFi:
1. `vcenter_collection.json` - vCenter data collection
2. `satellite_collection.json` - Satellite data collection

Configure parameters:
- `collection.service.url` - Data Collection Service URL
- `collection.service.token` - API token
- `vcenter.host` / `satellite.host` - Source hostnames
- `vcenter.api.token` / `satellite.auth.basic` - Source credentials

## Data Models

### Entity Types
- `vcenter_cluster` - VMware cluster
- `vcenter_host` - ESXi host
- `vcenter_vm` - Virtual machine
- `vcenter_datastore` - Datastore
- `vcenter_network` - Network
- `physical_server` - Physical server (Satellite)
- `network_device` - Switch, router, firewall
- `storage_device` - SAN, NAS

### Conflict Types
- `attribute_mismatch` - Different values for same attribute
- `missing_in_source` - Entity exists in one source only
- `extra_in_source` - Entity only in secondary source
- `parent_mismatch` - Different parent assignment
- `duplicate_entity` - Multiple entities map to same asset
- `state_mismatch` - Different power/connection states

### Conflict Severity
- `critical` - Identity, security, compliance
- `high` - Operational impact (IP, capacity, location)
- `medium` - Configuration differences
- `low` - Cosmetic (description, tags)

## Monitoring

### Key Metrics
- `collection_jobs_total` - Total jobs by status
- `collection_duration_seconds` - Job duration histogram
- `entities_collected_total` - Entities by source/type
- `reconciliation_conflicts_total` - Conflicts by severity
- `certification_requests_total` - Requests by status
- `certification_sla_breach_total` - SLA breaches

### Grafana Dashboards
Import dashboards from `monitoring/grafana/dashboards/`

## Security

- All passwords encrypted at rest (bcrypt for tokens, AES for source passwords)
- API authentication via JWT tokens
- TLS for all external connections
- Audit logging for all changes

## Extending

### Add New Connector

```python
from connectors.base import BaseConnector, ConnectorRegistry
from models.entity import CollectedEntity, EntityType

class MyConnector(BaseConnector):
    async def connect(self): ...
    async def disconnect(self): ...
    async def test_connection(self): ...
    async def collect(self, job, collection_type, since, entity_types): ...
    async def get_entity(self, entity_type, source_entity_id): ...
    async def get_schema(self): ...

ConnectorRegistry.register("my_source", MyConnector)
```

### Add Reconciliation Rule

```sql
INSERT INTO reconciliation_rules (name, description, entity_types, action, priority)
VALUES (
  'Prefer vCenter for VM data',
  'vCenter is authoritative for VM attributes',
  '["vcenter_vm"]',
  'source_a_wins',
  10
);
```

## Integration with CMDB

The Data Collection Service pushes certified data to the main CMDB API:

```python
# In certification service, after approval
async def apply_certification(self, request):
    for entity in certified_entities:
        await cmdb_client.upsert_asset(entity)
```

## License

MIT
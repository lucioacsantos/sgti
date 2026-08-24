"""
Satellite Connector

Collects data from Red Hat Satellite Server using its REST API.
"""
import httpx
from typing import AsyncIterator, Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from .base import BaseConnector, CollectionResult, ConnectorRegistry
from ..models.entity import (
    CollectedEntity, EntityType, PhysicalServer, NetworkInterface, Disk,
    OperatingSystem, PowerState
)
from ..models.collection import CollectionJob, CollectionType
from ..models.source import DataSource


class SatelliteConnector(BaseConnector):
    """Satellite data collector using REST API."""
    
    def __init__(self, source: DataSource):
        super().__init__(source)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url: str = ""
    
    async def connect(self) -> bool:
        """Connect to Satellite API."""
        try:
            self.base_url = f"https://{self.source.host}:{self.source.port or 443}"
            
            # Decrypt password
            password = self._decrypt_password()
            
            # Create client with auth
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.source.username, password),
                verify=False,  # For self-signed certs
                timeout=self.source.timeout_seconds,
            )
            
            # Test with a simple API call
            response = await self.client.get("/api/v2/ping")
            return response.status_code == 200
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Close connection."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _decrypt_password(self) -> str:
        """Decrypt password."""
        import base64
        try:
            return base64.b64decode(self.source.password_encrypted).decode()
        except Exception:
            return self.source.password_encrypted
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Satellite connection."""
        start = datetime.utcnow()
        try:
            success = await self.connect()
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            if success:
                # Get version info
                response = await self.client.get("/api/v2/about")
                version_info = response.json() if response.status_code == 200 else {}
                await self.disconnect()
                return {
                    "success": True,
                    "message": "Connected successfully",
                    "latency_ms": int(latency),
                    "details": version_info,
                }
            else:
                return {
                    "success": False,
                    "message": self._last_error or "Connection failed",
                    "latency_ms": int(latency),
                }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "latency_ms": int((datetime.utcnow() - start).total_seconds() * 1000),
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Return connector schema."""
        return {
            "source_type": "satellite",
            "supported_entity_types": [
                EntityType.PHYSICAL_SERVER.value,
                EntityType.NETWORK_DEVICE.value,
            ],
            "supports_incremental": True,
            "supports_delta": True,
            "required_config": ["host", "username", "password"],
            "optional_config": ["organization_id", "location_id", "hostgroup_filter"],
        }
    
    async def collect(
        self,
        job: CollectionJob,
        collection_type: CollectionType,
        since: Optional[datetime] = None,
        entity_types: List[EntityType] = None
    ) -> AsyncIterator[CollectionResult]:
        """Collect hosts from Satellite."""
        if not await self.connect():
            yield CollectionResult(
                entities=[],
                stats={"errors": 1},
                errors=[{"message": self._last_error or "Failed to connect"}]
            )
            return
        
        try:
            entity_types = entity_types or [EntityType.PHYSICAL_SERVER]
            
            # Get organizations and locations
            orgs = await self._get_organizations()
            locations = await self._get_locations()
            
            all_entities = []
            
            if EntityType.PHYSICAL_SERVER in entity_types:
                # Collect hosts from each org/location
                for org in orgs:
                    for loc in locations:
                        hosts = await self._collect_hosts(org["id"], loc["id"], job, since)
                        all_entities.extend(hosts)
            
            # Yield in batches
            batch_size = 100
            for i in range(0, len(all_entities), batch_size):
                batch = all_entities[i:i + batch_size]
                yield CollectionResult(
                    entities=batch,
                    stats={"collected": len(batch)},
                )
        
        finally:
            await self.disconnect()
    
    async def _get_organizations(self) -> List[Dict[str, Any]]:
        """Get all organizations."""
        response = await self.client.get("/api/v2/organizations", params={"per_page": 1000})
        return response.json().get("results", [])
    
    async def _get_locations(self) -> List[Dict[str, Any]]:
        """Get all locations."""
        response = await self.client.get("/api/v2/locations", params={"per_page": 1000})
        return response.json().get("results", [])
    
    async def _collect_hosts(
        self,
        org_id: int,
        loc_id: int,
        job: CollectionJob,
        since: Optional[datetime] = None
    ) -> List[CollectedEntity]:
        """Collect hosts for an org/location."""
        entities = []
        
        params = {
            "organization_id": org_id,
            "location_id": loc_id,
            "per_page": 1000,
        }
        
        if since:
            params["search"] = f"updated_at > '{since.isoformat()}'"
        
        page = 1
        while True:
            params["page"] = page
            response = await self.client.get("/api/v2/hosts", params=params)
            data = response.json()
            
            for host in data.get("results", []):
                entity = self._map_host(host, org_id, loc_id, job)
                if entity:
                    entities.append(entity)
            
            if page >= data.get("total_pages", 1):
                break
            page += 1
        
        return entities
    
    def _map_host(
        self,
        host: Dict[str, Any],
        org_id: int,
        loc_id: int,
        job: CollectionJob
    ) -> Optional[PhysicalServer]:
        """Map Satellite host to our model."""
        try:
            # Get org/location names
            org_name = host.get("organization", {}).get("name")
            loc_name = host.get("location", {}).get("name")
            
            # Network interfaces
            nics = []
            primary_ip = None
            for iface in host.get("interfaces", []):
                if iface.get("type") == "interface":
                    nic = NetworkInterface(
                        name=iface.get("name", ""),
                        mac_address=iface.get("mac"),
                        ip_addresses=[iface.get("ip")] if iface.get("ip") else [],
                        ipv6_addresses=[iface.get("ip6")] if iface.get("ip6") else [],
                        network_name=iface.get("subnet", {}).get("name"),
                        vlan_id=iface.get("subnet", {}).get("vlanid"),
                        connected=iface.get("managed", True),
                    )
                    nics.append(nic)
                    if iface.get("primary") and iface.get("ip"):
                        primary_ip = iface["ip"]
            
            # Bonds
            bonds = []
            for iface in host.get("interfaces", []):
                if iface.get("type") == "bond":
                    bonds.append({
                        "name": iface.get("name"),
                        "mode": iface.get("mode"),
                        "slaves": [s.get("name") for s in iface.get("slaves", [])],
                        "ip": iface.get("ip"),
                    })
            
            # OS info
            os_info = None
            if host.get("operatingsystem"):
                os_info = OperatingSystem(
                    name=host["operatingsystem"].get("name", ""),
                    version=host["operatingsystem"].get("major", ""),
                    family=host["operatingsystem"].get("family", ""),
                )
            
            # Facts for additional hardware info
            facts = host.get("facts", {})
            
            return PhysicalServer(
                source_id=self.source.id,
                source_entity_id=str(host["id"]),
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.PHYSICAL_SERVER, source_entity_id=str(host["id"]))
                ),
                name=host["name"],
                display_name=host.get("name"),
                description=host.get("comment"),
                
                # Location
                datacenter=loc_name,
                rack=host.get("hostgroup", {}).get("title"),
                
                # Hardware
                manufacturer=facts.get("manufacturer"),
                model=facts.get("productname"),
                serial_number=facts.get("serialnumber"),
                uuid=facts.get("uuid"),
                bios_version=facts.get("bios_version"),
                bios_date=self._parse_date(facts.get("bios_release_date")),
                chassis_type=facts.get("chassis_type"),
                part_number=facts.get("part_number"),
                asset_tag=facts.get("asset_tag"),
                
                # Management
                ilo_ip=host.get("bmc", {}).get("ip"),
                ilo_username=host.get("bmc", {}).get("username"),
                
                # Satellite specific
                satellite_org=org_name,
                satellite_location=loc_name,
                satellite_hostgroup=host.get("hostgroup", {}).get("title"),
                content_view=host.get("content_view", {}).get("name"),
                lifecycle_environment=host.get("lifecycle_environment", {}).get("name"),
                puppet_environment=host.get("puppet_environment", {}).get("name"),
                
                # Compute
                cpu_cores=facts.get("processorcount"),
                cpu_threads=facts.get("processorcount"),  # Satellite doesn't distinguish
                cpu_model=facts.get("processor0"),
                cpu_mhz=facts.get("processor_mhz"),
                memory_gb=facts.get("memorysize_mb", 0) // 1024 if facts.get("memorysize_mb") else None,
                
                # OS
                os=os_info,
                
                # Network
                network_interfaces=nics,
                primary_ip=primary_ip or host.get("ip"),
                bonds=bonds,
                
                # Subscriptions
                subscriptions=host.get("subscriptions", []),
                
                # Power state
                power_state=PowerState.POWERED_ON if host.get("status", {}).get("label") == "Active" else PowerState.UNKNOWN,
                connection_state=host.get("status", {}).get("label"),
                
                # Tags
                tags={t["name"]: "" for t in host.get("host_parameters", [])},
                annotations={p["name"]: p["value"] for p in host.get("host_parameters", [])},
                
                # Collection metadata
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data=host,
            )
        except Exception as e:
            self._log_error(f"Failed to map host {host.get('name')}: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string."""
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d %Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    async def get_entity(
        self,
        entity_type: EntityType,
        source_entity_id: str
    ) -> Optional[CollectedEntity]:
        """Get a single host by ID."""
        if not await self.connect():
            return None
        
        try:
            response = await self.client.get(f"/api/v2/hosts/{source_entity_id}")
            if response.status_code == 200:
                host = response.json()
                # Need org/location context
                org_id = host.get("organization", {}).get("id", 1)
                loc_id = host.get("location", {}).get("id", 1)
                return self._map_host(host, org_id, loc_id, CollectionJob(id=UUID(int=0), source_id=self.source.id, collection_type=CollectionType.MANUAL))
            return None
        finally:
            await self.disconnect()
    
    def _log_error(self, message: str):
        """Log error."""
        print(f"[ERROR] {message}")


# Register the connector
ConnectorRegistry.register("satellite", SatelliteConnector)
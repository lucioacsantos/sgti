"""
Collected Entity Models

Normalized representation of infrastructure entities from various sources.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4
from ipaddress import IPv4Address, IPv6Address


class EntityType(str, Enum):
    """Types of infrastructure entities."""
    # VMware
    VCENTER_CLUSTER = "vcenter_cluster"
    VCENTER_HOST = "vcenter_host"
    VCENTER_VM = "vcenter_vm"
    VCENTER_DATASTORE = "vcenter_datastore"
    VCENTER_NETWORK = "vcenter_network"
    VCENTER_FOLDER = "vcenter_folder"
    VCENTER_RESOURCE_POOL = "vcenter_resource_pool"
    
    # Satellite / Physical
    PHYSICAL_SERVER = "physical_server"
    NETWORK_DEVICE = "network_device"
    STORAGE_DEVICE = "storage_device"
    RACK = "rack"
    PDU = "pdu"
    
    # Generic
    APPLICATION = "application"
    SERVICE = "service"
    DATABASE = "database"


class PowerState(str, Enum):
    """Power state of compute resources."""
    POWERED_ON = "powered_on"
    POWERED_OFF = "powered_off"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class OperatingSystem(BaseModel):
    """Operating system information."""
    name: str
    version: Optional[str] = None
    architecture: Optional[str] = None
    family: Optional[str] = None  # linux, windows, etc.


class NetworkInterface(BaseModel):
    """Network interface details."""
    name: str
    mac_address: Optional[str] = None
    ip_addresses: List[str] = Field(default_factory=list)
    ipv6_addresses: List[str] = Field(default_factory=list)
    network_name: Optional[str] = None
    vlan_id: Optional[int] = None
    speed_mbps: Optional[int] = None
    connected: bool = True


class Disk(BaseModel):
    """Disk/storage device."""
    name: str
    size_gb: int
    type: str  # SSD, HDD, NVMe, etc.
    mount_point: Optional[str] = None
    filesystem: Optional[str] = None
    datastore: Optional[str] = None


class CollectedEntity(BaseModel):
    """Base collected entity - normalized across sources."""
    model_config = ConfigDict(from_attributes=True)
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    entity_type: EntityType
    source_entity_id: str  # Original ID from source (moid, hostname, etc.)
    source_unique_key: str  # Composite key for deduplication
    
    # Core attributes
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    
    # Hierarchy
    parent_id: Optional[UUID] = None
    parent_source_id: Optional[str] = None
    children_ids: List[UUID] = Field(default_factory=list)
    
    # Location
    datacenter: Optional[str] = None
    rack: Optional[str] = None
    rack_unit: Optional[str] = None
    
    # Hardware
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    uuid: Optional[str] = None  # BIOS UUID
    
    # Compute
    cpu_cores: Optional[int] = None
    cpu_threads: Optional[int] = None
    cpu_model: Optional[str] = None
    cpu_mhz: Optional[int] = None
    memory_gb: Optional[int] = None
    
    # OS
    os: Optional[OperatingSystem] = None
    
    # Network
    network_interfaces: List[NetworkInterface] = Field(default_factory=list)
    primary_ip: Optional[str] = None
    
    # Storage
    disks: List[Disk] = Field(default_factory=list)
    total_storage_gb: Optional[int] = None
    
    # State
    power_state: PowerState = PowerState.UNKNOWN
    connection_state: Optional[str] = None  # connected, disconnected, etc.
    
    # Tags & metadata
    tags: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Source-specific raw data (for debugging/reconciliation)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Collection metadata
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    collection_job_id: UUID
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False
    
    # Reconciliation
    reconciliation_id: Optional[UUID] = None
    conflict_count: int = 0
    is_certified: bool = False
    certified_at: Optional[datetime] = None
    certified_by: Optional[str] = None


# VMware-specific entities
class VMwareCluster(CollectedEntity):
    """VMware cluster."""
    entity_type: EntityType = EntityType.VCENTER_CLUSTER
    
    # Cluster config
    ha_enabled: bool = False
    drs_enabled: bool = False
    drs_automation_level: Optional[str] = None
    vsan_enabled: bool = False
    
    # Capacity
    total_cpu_cores: int = 0
    total_cpu_mhz: int = 0
    total_memory_gb: int = 0
    used_cpu_mhz: int = 0
    used_memory_gb: int = 0
    
    # Hosts
    host_count: int = 0
    vm_count: int = 0


class VMwareHost(CollectedEntity):
    """VMware ESXi host."""
    entity_type: EntityType = EntityType.VCENTER_HOST
    
    # Host config
    cluster_id: Optional[UUID] = None
    cluster_name: Optional[str] = None
    version: str
    build: Optional[str] = None
    
    # Hardware
    bios_version: Optional[str] = None
    boot_time: Optional[datetime] = None
    
    # Resources
    total_cpu_cores: int = 0
    total_cpu_threads: int = 0
    total_cpu_mhz: int = 0
    total_memory_gb: int = 0
    used_cpu_mhz: int = 0
    used_memory_gb: int = 0
    
    # VMs
    vm_count: int = 0
    powered_on_vm_count: int = 0
    
    # Network
    vswitches: List[Dict[str, Any]] = Field(default_factory=list)
    portgroups: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Storage
    datastores: List[str] = Field(default_factory=list)
    
    # Maintenance
    in_maintenance_mode: bool = False
    lockdown_mode: Optional[str] = None


class VMwareVM(CollectedEntity):
    """VMware virtual machine."""
    entity_type: EntityType = EntityType.VCENTER_VM
    
    # VM config
    host_id: Optional[UUID] = None
    host_name: Optional[str] = None
    cluster_id: Optional[UUID] = None
    cluster_name: Optional[str] = None
    folder: Optional[str] = None
    resource_pool: Optional[str] = None
    template: bool = False
    
    # Guest OS
    guest_os: Optional[str] = None
    guest_os_version: Optional[str] = None
    tools_status: Optional[str] = None
    tools_version: Optional[str] = None
    
    # Resources
    cpu_cores: int = 0
    cpu_limit_mhz: Optional[int] = None
    cpu_reservation_mhz: Optional[int] = None
    cpu_shares: Optional[int] = None
    memory_gb: int = 0
    memory_limit_mb: Optional[int] = None
    memory_reservation_mb: Optional[int] = None
    memory_shares: Optional[int] = None
    
    # Disks
    disks: List[Disk] = Field(default_factory=list)
    total_disk_gb: int = 0
    
    # Network
    network_interfaces: List[NetworkInterface] = Field(default_factory=list)
    
    # Snapshots
    snapshot_count: int = 0
    snapshot_total_size_gb: int = 0
    
    # Power
    power_state: PowerState = PowerState.UNKNOWN
    boot_time: Optional[datetime] = None
    
    # UUID
    instance_uuid: Optional[str] = None
    bios_uuid: Optional[str] = None


# Physical / Satellite entities
class PhysicalServer(CollectedEntity):
    """Physical server from Satellite or other source."""
    entity_type: EntityType = EntityType.PHYSICAL_SERVER
    
    # Hardware details
    chassis_type: Optional[str] = None  # rack, blade, tower
    part_number: Optional[str] = None
    asset_tag: Optional[str] = None
    
    # BIOS/Management
    bios_version: Optional[str] = None
    bios_date: Optional[datetime] = None
    ilo_ip: Optional[str] = None
    ilo_username: Optional[str] = None
    
    # Enclosure (for blades)
    enclosure_name: Optional[str] = None
    enclosure_bay: Optional[int] = None
    
    # Warranty
    warranty_start: Optional[datetime] = None
    warranty_end: Optional[datetime] = None
    warranty_type: Optional[str] = None
    
    # Satellite specific
    satellite_org: Optional[str] = None
    satellite_location: Optional[str] = None
    satellite_hostgroup: Optional[str] = None
    content_view: Optional[str] = None
    lifecycle_environment: Optional[str] = None
    puppet_environment: Optional[str] = None
    
    # Subscription
    subscriptions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Network
    network_interfaces: List[NetworkInterface] = Field(default_factory=list)
    bonds: List[Dict[str, Any]] = Field(default_factory=list)
    bridges: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Storage
    raid_controller: Optional[str] = None
    logical_drives: List[Dict[str, Any]] = Field(default_factory=list)
    physical_drives: List[Dict[str, Any]] = Field(default_factory=list)


class NetworkDevice(CollectedEntity):
    """Network device (switch, router, firewall)."""
    entity_type: EntityType = EntityType.NETWORK_DEVICE
    
    device_type: str  # switch, router, firewall, load_balancer
    os_version: Optional[str] = None
    management_ip: Optional[str] = None
    
    # Ports
    total_ports: int = 0
    used_ports: int = 0
    port_details: List[Dict[str, Any]] = Field(default_factory=list)
    
    # VLANs
    vlans: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Stack/HA
    stack_member: bool = False
    stack_role: Optional[str] = None
    ha_peer: Optional[str] = None


class StorageDevice(CollectedEntity):
    """Storage device (SAN, NAS, DAS)."""
    entity_type: EntityType = EntityType.STORAGE_DEVICE
    
    storage_type: str  # san, nas, das, hci
    total_capacity_gb: int = 0
    used_capacity_gb: int = 0
    free_capacity_gb: int = 0
    
    # Pools/Volumes
    storage_pools: List[Dict[str, Any]] = Field(default_factory=list)
    volumes: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Connectivity
    controllers: List[Dict[str, Any]] = Field(default_factory=list)
    host_ports: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Replication
    replication_enabled: bool = False
    replication_targets: List[str] = Field(default_factory=list)
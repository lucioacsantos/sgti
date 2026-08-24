"""
vCenter Connector

Collects data from VMware vCenter Server using pyvmomi.
"""
import ssl
from typing import AsyncIterator, Dict, Any, List, Optional, Set
from datetime import datetime
from uuid import UUID

from pyVmomi import vim, vmodl
from pyVim.connect import SmartConnect, Disconnect

from .base import BaseConnector, CollectionResult, ConnectorRegistry
from ..models.entity import (
    CollectedEntity, EntityType, VMwareCluster, VMwareHost, VMwareVM,
    NetworkInterface, Disk, OperatingSystem, PowerState
)
from ..models.collection import CollectionJob, CollectionType
from ..models.source import DataSource


class VCenterConnector(BaseConnector):
    """vCenter data collector using pyvmomi."""
    
    def __init__(self, source: DataSource):
        super().__init__(source)
        self.si = None
        self.content = None
        self._entity_cache: Dict[str, CollectedEntity] = {}
    
    async def connect(self) -> bool:
        """Connect to vCenter."""
        try:
            # SSL context for self-signed certs
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            self.si = SmartConnect(
                host=self.source.host,
                user=self.source.username,
                pwd=self._decrypt_password(),
                port=self.source.port or 443,
                sslContext=context,
                connectionPoolTimeout=self.source.timeout_seconds
            )
            self.content = self.si.RetrieveContent()
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from vCenter."""
        if self.si:
            Disconnect(self.si)
            self.si = None
            self.content = None
    
    def _decrypt_password(self) -> str:
        """Decrypt password (placeholder - use proper encryption in production)."""
        # In production, use a proper encryption service
        import base64
        try:
            return base64.b64decode(self.source.password_encrypted).decode()
        except Exception:
            return self.source.password_encrypted
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test vCenter connection."""
        start = datetime.utcnow()
        try:
            success = await self.connect()
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            if success:
                about = self.content.about
                await self.disconnect()
                return {
                    "success": True,
                    "message": "Connected successfully",
                    "latency_ms": int(latency),
                    "details": {
                        "version": about.version,
                        "build": about.build,
                        "instance_uuid": about.instanceUuid,
                        "api_version": about.apiVersion,
                    }
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
            "source_type": "vcenter",
            "supported_entity_types": [
                EntityType.VCENTER_CLUSTER.value,
                EntityType.VCENTER_HOST.value,
                EntityType.VCENTER_VM.value,
                EntityType.VCENTER_DATASTORE.value,
                EntityType.VCENTER_NETWORK.value,
            ],
            "supports_incremental": True,
            "supports_delta": True,
            "required_config": ["host", "username", "password"],
            "optional_config": ["datacenter_filter", "cluster_filter", "folder_filter"],
        }
    
    async def collect(
        self,
        job: CollectionJob,
        collection_type: CollectionType,
        since: Optional[datetime] = None,
        entity_types: List[EntityType] = None
    ) -> AsyncIterator[CollectionResult]:
        """Collect all entities from vCenter."""
        if not await self.connect():
            yield CollectionResult(
                entities=[],
                stats={"errors": 1},
                errors=[{"message": self._last_error or "Failed to connect"}]
            )
            return
        
        try:
            entity_types = entity_types or [
                EntityType.VCENTER_CLUSTER,
                EntityType.VCENTER_HOST,
                EntityType.VCENTER_VM,
                EntityType.VCENTER_DATASTORE,
                EntityType.VCENTER_NETWORK,
            ]
            
            all_entities = []
            
            # Collect datacenters first (for hierarchy)
            datacenters = self._get_datacenters()
            
            for dc in datacenters:
                if EntityType.VCENTER_CLUSTER in entity_types:
                    clusters = await self._collect_clusters(dc, job)
                    all_entities.extend(clusters)
                
                if EntityType.VCENTER_HOST in entity_types:
                    hosts = await self._collect_hosts(dc, job)
                    all_entities.extend(hosts)
                
                if EntityType.VCENTER_VM in entity_types:
                    vms = await self._collect_vms(dc, job)
                    all_entities.extend(vms)
                
                if EntityType.VCENTER_DATASTORE in entity_types:
                    datastores = await self._collect_datastores(dc, job)
                    all_entities.extend(datastores)
                
                if EntityType.VCENTER_NETWORK in entity_types:
                    networks = await self._collect_networks(dc, job)
                    all_entities.extend(networks)
            
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
    
    def _get_datacenters(self) -> List[vim.Datacenter]:
        """Get all datacenters."""
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.Datacenter], True
        )
        try:
            return list(container.view)
        finally:
            container.Destroy()
    
    async def _collect_clusters(self, datacenter: vim.Datacenter, job: CollectionJob) -> List[CollectedEntity]:
        """Collect clusters from a datacenter."""
        entities = []
        container = self.content.viewManager.CreateContainerView(
            datacenter.hostFolder, [vim.ClusterComputeResource], True
        )
        try:
            for cluster in container.view:
                entity = self._map_cluster(cluster, datacenter, job)
                if entity:
                    entities.append(entity)
        finally:
            container.Destroy()
        return entities
    
    def _map_cluster(
        self,
        cluster: vim.ClusterComputeResource,
        datacenter: vim.Datacenter,
        job: CollectionJob
    ) -> Optional[VMwareCluster]:
        """Map vCenter cluster to our model."""
        try:
            summary = cluster.summary
            config = cluster.configurationEx
            
            # Calculate capacity
            total_cpu_mhz = sum(h.hardware.cpuInfo.hz * h.hardware.cpuInfo.numCpuCores 
                               for h in cluster.host if h.hardware.cpuInfo)
            total_cpu_cores = sum(h.hardware.cpuInfo.numCpuCores for h in cluster.host if h.hardware.cpuInfo)
            total_memory_gb = sum(h.hardware.memorySize for h in cluster.host) // (1024**3)
            
            used_cpu_mhz = sum(h.summary.quickStats.overallCpuUsage for h in cluster.host)
            used_memory_gb = sum(h.summary.quickStats.overallMemoryUsage for h in cluster.host) // 1024
            
            return VMwareCluster(
                source_id=self.source.id,
                source_entity_id=cluster._moId,
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.VCENTER_CLUSTER, source_entity_id=cluster._moId)
                ),
                name=cluster.name,
                display_name=cluster.name,
                description=config.dasConfig.enabled if config.dasConfig else None,
                datacenter=datacenter.name,
                parent_source_id=datacenter._moId,
                
                # Cluster config
                ha_enabled=config.dasConfig.enabled if config.dasConfig else False,
                drs_enabled=config.drsConfig.enabled if config.drsConfig else False,
                drs_automation_level=config.drsConfig.defaultVmBehavior if config.drsConfig else None,
                vsan_enabled=config.vsanConfig.enabled if hasattr(config, 'vsanConfig') and config.vsanConfig else False,
                
                # Capacity
                total_cpu_cores=total_cpu_cores,
                total_cpu_mhz=total_cpu_mhz,
                total_memory_gb=total_memory_gb,
                used_cpu_mhz=used_cpu_mhz,
                used_memory_gb=used_memory_gb,
                
                # Counts
                host_count=len(cluster.host),
                vm_count=sum(len(h.vm) for h in cluster.host),
                
                # Collection metadata
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data={
                    "moid": cluster._moId,
                    "datacenter_moid": datacenter._moId,
                    "overall_status": str(summary.overallStatus) if summary.overallStatus else None,
                }
            )
        except Exception as e:
            self._log_error(f"Failed to map cluster {cluster.name}: {e}")
            return None
    
    async def _collect_hosts(self, datacenter: vim.Datacenter, job: CollectionJob) -> List[CollectedEntity]:
        """Collect hosts from a datacenter."""
        entities = []
        container = self.content.viewManager.CreateContainerView(
            datacenter.hostFolder, [vim.HostSystem], True
        )
        try:
            for host in container.view:
                entity = self._map_host(host, datacenter, job)
                if entity:
                    entities.append(entity)
        finally:
            container.Destroy()
        return entities
    
    def _map_host(self, host: vim.HostSystem, datacenter: vim.Datacenter, job: CollectionJob) -> Optional[VMwareHost]:
        """Map vCenter host to our model."""
        try:
            summary = host.summary
            hardware = host.hardware
            config = host.config
            
            # Network
            vswitches = []
            for vswitch in config.network.vswitch:
                vswitches.append({
                    "name": vswitch.name,
                    "num_ports": vswitch.numPorts,
                    "mtu": vswitch.mtu,
                    "pnics": [pnic.device for pnic in vswitch.pnic],
                })
            
            portgroups = []
            for pg in config.network.portgroup:
                portgroups.append({
                    "name": pg.spec.name,
                    "vlan_id": pg.spec.vlanId,
                    "vswitch": pg.spec.vswitchName,
                })
            
            # Datastores
            datastores = [ds.name for ds in host.datastore]
            
            return VMwareHost(
                source_id=self.source.id,
                source_entity_id=host._moId,
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.VCENTER_HOST, source_entity_id=host._moId)
                ),
                name=host.name,
                display_name=host.name,
                datacenter=datacenter.name,
                parent_source_id=datacenter._moId,
                
                # Version
                version=config.product.version,
                build=config.product.build,
                
                # Hardware
                manufacturer=hardware.systemInfo.vendor if hardware.systemInfo else None,
                model=hardware.systemInfo.model if hardware.systemInfo else None,
                serial_number=hardware.systemInfo.otherIdentifyingInfo[0].identifierValue 
                               if hardware.systemInfo and hardware.systemInfo.otherIdentifyingInfo else None,
                bios_version=hardware.biosInfo.biosVersion if hardware.biosInfo else None,
                boot_time=summary.runtime.bootTime,
                
                # Resources
                total_cpu_cores=hardware.cpuInfo.numCpuCores if hardware.cpuInfo else 0,
                total_cpu_threads=hardware.cpuInfo.numCpuThreads if hardware.cpuInfo else 0,
                total_cpu_mhz=hardware.cpuInfo.hz * hardware.cpuInfo.numCpuCores if hardware.cpuInfo else 0,
                total_memory_gb=hardware.memorySize // (1024**3) if hardware.memorySize else 0,
                used_cpu_mhz=summary.quickStats.overallCpuUsage,
                used_memory_gb=summary.quickStats.overallMemoryUsage // 1024,
                
                # VMs
                vm_count=len(host.vm),
                powered_on_vm_count=len([v for v in host.vm if v.runtime.powerState == "poweredOn"]),
                
                # Network
                vswitches=vswitches,
                portgroups=portgroups,
                
                # Storage
                datastores=datastores,
                
                # Maintenance
                in_maintenance_mode=summary.runtime.inMaintenanceMode,
                lockdown_mode=str(config.lockdownMode) if config.lockdownMode else None,
                
                # Power state
                power_state=PowerState.POWERED_ON if summary.runtime.powerState == "poweredOn" 
                           else PowerState.POWERED_OFF,
                connection_state=str(summary.runtime.connectionState),
                
                # Collection metadata
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data={
                    "moid": host._moId,
                    "datacenter_moid": datacenter._moId,
                    "overall_status": str(summary.overallStatus) if summary.overallStatus else None,
                }
            )
        except Exception as e:
            self._log_error(f"Failed to map host {host.name}: {e}")
            return None
    
    async def _collect_vms(self, datacenter: vim.Datacenter, job: CollectionJob) -> List[CollectedEntity]:
        """Collect VMs from a datacenter."""
        entities = []
        container = self.content.viewManager.CreateContainerView(
            datacenter.vmFolder, [vim.VirtualMachine], True
        )
        try:
            for vm in container.view:
                entity = self._map_vm(vm, datacenter, job)
                if entity:
                    entities.append(entity)
        finally:
            container.Destroy()
        return entities
    
    def _map_vm(self, vm: vim.VirtualMachine, datacenter: vim.Datacenter, job: CollectionJob) -> Optional[VMwareVM]:
        """Map vCenter VM to our model."""
        try:
            summary = vm.summary
            config = vm.config
            guest = vm.guest
            runtime = vm.runtime
            
            # Skip template VMs if not configured
            if config.template and not self.config.get("include_templates", False):
                return None
            
            # Network interfaces
            nics = []
            for nic in vm.guest.net if vm.guest else []:
                nics.append(NetworkInterface(
                    name=nic.network,
                    mac_address=nic.macAddress,
                    ip_addresses=nic.ipAddress or [],
                    network_name=nic.network,
                    connected=nic.connected,
                ))
            
            # Disks
            disks = []
            total_disk_gb = 0
            for device in config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    size_gb = device.capacityInKB // (1024 * 1024)
                    total_disk_gb += size_gb
                    disks.append(Disk(
                        name=device.deviceInfo.label if device.deviceInfo else f"Disk {device.key}",
                        size_gb=size_gb,
                        type="VMDK",
                        datastore=device.backing.datastore.name if device.backing.datastore else None,
                    ))
            
            # Determine host and cluster
            host_name = None
            cluster_name = None
            if runtime.host:
                host_name = runtime.host.name
                if runtime.host.parent and isinstance(runtime.host.parent, vim.ClusterComputeResource):
                    cluster_name = runtime.host.parent.name
            
            return VMwareVM(
                source_id=self.source.id,
                source_entity_id=vm._moId,
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.VCENTER_VM, source_entity_id=vm._moId)
                ),
                name=vm.name,
                display_name=config.name,
                description=config.annotation,
                datacenter=datacenter.name,
                parent_source_id=datacenter._moId,
                
                # VM config
                host_id=None,  # Will be resolved later
                host_name=host_name,
                cluster_name=cluster_name,
                folder=self._get_folder_path(vm),
                resource_pool=vm.resourcePool.name if vm.resourcePool else None,
                template=config.template,
                
                # Guest OS
                guest_os=guest.guestFamily if guest else None,
                guest_os_version=guest.guestFullName if guest else None,
                tools_status=str(guest.toolsStatus) if guest and guest.toolsStatus else None,
                tools_version=guest.toolsVersion if guest else None,
                
                # Resources
                cpu_cores=config.hardware.numCPU,
                cpu_limit_mhz=config.cpuAllocation.limit if config.cpuAllocation.limit != -1 else None,
                cpu_reservation_mhz=config.cpuAllocation.reservation,
                cpu_shares=config.cpuAllocation.shares.shares if config.cpuAllocation.shares else None,
                memory_gb=config.hardware.memoryMB // 1024,
                memory_limit_mb=config.memoryAllocation.limit if config.memoryAllocation.limit != -1 else None,
                memory_reservation_mb=config.memoryAllocation.reservation,
                memory_shares=config.memoryAllocation.shares.shares if config.memoryAllocation.shares else None,
                
                # Disks
                disks=disks,
                total_disk_gb=total_disk_gb,
                
                # Network
                network_interfaces=nics,
                
                # Snapshots
                snapshot_count=len(vm.snapshot.rootSnapshotList) if vm.snapshot else 0,
                snapshot_total_size_gb=0,  # Would need to calculate
                
                # Power
                power_state=PowerState.POWERED_ON if runtime.powerState == "poweredOn"
                           else PowerState.POWERED_OFF if runtime.powerState == "poweredOff"
                           else PowerState.SUSPENDED,
                boot_time=runtime.bootTime,
                
                # UUIDs
                instance_uuid=config.instanceUuid,
                bios_uuid=config.uuid,
                
                # Collection metadata
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data={
                    "moid": vm._moId,
                    "datacenter_moid": datacenter._moId,
                    "overall_status": str(summary.overallStatus) if summary.overallStatus else None,
                }
            )
        except Exception as e:
            self._log_error(f"Failed to map VM {vm.name}: {e}")
            return None
    
    async def _collect_datastores(self, datacenter: vim.Datacenter, job: CollectionJob) -> List[CollectedEntity]:
        """Collect datastores from a datacenter."""
        entities = []
        container = self.content.viewManager.CreateContainerView(
            datacenter.datastoreFolder, [vim.Datastore], True
        )
        try:
            for ds in container.view:
                entity = self._map_datastore(ds, datacenter, job)
                if entity:
                    entities.append(entity)
        finally:
            container.Destroy()
        return entities
    
    def _map_datastore(self, ds: vim.Datastore, datacenter: vim.Datacenter, job: CollectionJob) -> Optional[CollectedEntity]:
        """Map datastore to our model."""
        try:
            summary = ds.summary
            return CollectedEntity(
                source_id=self.source.id,
                source_entity_id=ds._moId,
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.VCENTER_DATASTORE, source_entity_id=ds._moId)
                ),
                name=ds.name,
                entity_type=EntityType.VCENTER_DATASTORE,
                datacenter=datacenter.name,
                parent_source_id=datacenter._moId,
                
                total_storage_gb=summary.capacity // (1024**3),
                # Free space would be summary.freeSpace
                
                tags={"type": summary.type},
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data={
                    "moid": ds._moId,
                    "datacenter_moid": datacenter._moId,
                    "accessible": summary.accessible,
                    "maintenance_mode": summary.maintenanceMode,
                }
            )
        except Exception as e:
            self._log_error(f"Failed to map datastore {ds.name}: {e}")
            return None
    
    async def _collect_networks(self, datacenter: vim.Datacenter, job: CollectionJob) -> List[CollectedEntity]:
        """Collect networks from a datacenter."""
        entities = []
        container = self.content.viewManager.CreateContainerView(
            datacenter.networkFolder, [vim.Network], True
        )
        try:
            for net in container.view:
                entity = self._map_network(net, datacenter, job)
                if entity:
                    entities.append(entity)
        finally:
            container.Destroy()
        return entities
    
    def _map_network(self, net: vim.Network, datacenter: vim.Datacenter, job: CollectionJob) -> Optional[CollectedEntity]:
        """Map network to our model."""
        try:
            return CollectedEntity(
                source_id=self.source.id,
                source_entity_id=net._moId,
                source_unique_key=self.build_unique_key(
                    CollectedEntity(source_id=self.source.id, entity_type=EntityType.VCENTER_NETWORK, source_entity_id=net._moId)
                ),
                name=net.name,
                entity_type=EntityType.VCENTER_NETWORK,
                datacenter=datacenter.name,
                parent_source_id=datacenter._moId,
                
                tags={"type": type(net).__name__},
                collected_at=datetime.utcnow(),
                collection_job_id=job.id,
                raw_data={
                    "moid": net._moId,
                    "datacenter_moid": datacenter._moId,
                    "accessible": True,
                }
            )
        except Exception as e:
            self._log_error(f"Failed to map network {net.name}: {e}")
            return None
    
    def _get_folder_path(self, obj) -> Optional[str]:
        """Get folder path for an object."""
        path = []
        current = obj
        while current and hasattr(current, 'parent') and current.parent:
            if hasattr(current, 'name'):
                path.append(current.name)
            current = current.parent
        return "/".join(reversed(path)) if path else None
    
    async def get_entity(
        self,
        entity_type: EntityType,
        source_entity_id: str
    ) -> Optional[CollectedEntity]:
        """Get a single entity by source ID."""
        if not await self.connect():
            return None
        
        try:
            # Find by MoID
            obj = self.content.searchIndex.FindByMoId(source_entity_id)
            if not obj:
                return None
            
            # Map based on type
            datacenter = self._find_datacenter(obj)
            
            if entity_type == EntityType.VCENTER_CLUSTER and isinstance(obj, vim.ClusterComputeResource):
                return self._map_cluster(obj, datacenter, CollectionJob(id=UUID(int=0), source_id=self.source.id, collection_type=CollectionType.MANUAL))
            elif entity_type == EntityType.VCENTER_HOST and isinstance(obj, vim.HostSystem):
                return self._map_host(obj, datacenter, CollectionJob(id=UUID(int=0), source_id=self.source.id, collection_type=CollectionType.MANUAL))
            elif entity_type == EntityType.VCENTER_VM and isinstance(obj, vim.VirtualMachine):
                return self._map_vm(obj, datacenter, CollectionJob(id=UUID(int=0), source_id=self.source.id, collection_type=CollectionType.MANUAL))
            
            return None
        finally:
            await self.disconnect()
    
    def _find_datacenter(self, obj) -> Optional[vim.Datacenter]:
        """Find datacenter for an object."""
        current = obj
        while current and hasattr(current, 'parent') and current.parent:
            if isinstance(current, vim.Datacenter):
                return current
            current = current.parent
        return None
    
    def _log_error(self, message: str):
        """Log error (placeholder)."""
        print(f"[ERROR] {message}")


# Register the connector
ConnectorRegistry.register("vcenter", VCenterConnector)
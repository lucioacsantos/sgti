"""
Reconciliation Engine

Compares entities from multiple sources, detects conflicts, and applies resolution rules.
"""
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from uuid import UUID, uuid4
from collections import defaultdict
import logging

from ..models.entity import CollectedEntity, EntityType
from ..models.reconciliation import (
    ReconciliationSession, Conflict, ConflictType, ConflictSeverity,
    ResolutionAction, ReconciliationRule, ReconciliationReport
)
from ..models.source import DataSource

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """Engine for reconciling data from multiple sources."""
    
    def __init__(
        self,
        session: ReconciliationSession,
        sources: Dict[UUID, DataSource],
        entities_by_source: Dict[UUID, List[CollectedEntity]],
        rules: List[ReconciliationRule] = None
    ):
        self.session = session
        self.sources = sources
        self.entities_by_source = entities_by_source
        self.rules = rules or []
        self.conflicts: List[Conflict] = []
        
        # Primary source
        self.primary_source_id = session.primary_source_id
        self.primary_entities = entities_by_source.get(self.primary_source_id, [])
        
        # Secondary sources
        self.secondary_source_ids = [s for s in session.source_ids if s != self.primary_source_id]
        
        # Index for fast lookup
        self._build_indexes()
    
    def _build_indexes(self):
        """Build lookup indexes for entities."""
        # Index by unique key
        self.entities_by_key: Dict[str, Dict[UUID, CollectedEntity]] = defaultdict(dict)
        
        for source_id, entities in self.entities_by_source.items():
            for entity in entities:
                self.entities_by_key[entity.source_unique_key][source_id] = entity
        
        # Index by name (fuzzy matching)
        self.entities_by_name: Dict[str, Dict[UUID, List[CollectedEntity]]] = defaultdict(lambda: defaultdict(list))
        for source_id, entities in self.entities_by_source.items():
            for entity in entities:
                # Normalize name for matching
                norm_name = self._normalize_name(entity.name)
                self.entities_by_name[norm_name][source_id].append(entity)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        return name.lower().strip().replace(".", "").replace("-", "").replace("_", "")
    
    async def run(self) -> ReconciliationSession:
        """Run the reconciliation process."""
        self.session.status = "running"
        self.session.started_at = datetime.utcnow()
        
        try:
            # Compare primary vs each secondary
            for secondary_id in self.secondary_source_ids:
                await self._compare_sources(self.primary_source_id, secondary_id)
            
            # Apply auto-resolution rules
            await self._apply_rules()
            
            # Update session stats
            self.session.total_entities_compared = sum(len(e) for e in self.entities_by_source.values())
            self.session.conflicts_found = len(self.conflicts)
            self.session.conflicts_resolved = sum(1 for c in self.conflicts if c.resolution is not None)
            self.session.conflicts_auto_resolved = sum(1 for c in self.conflicts if c.resolution == ResolutionAction.AUTO_RULE)
            self.session.conflicts_manual_resolved = sum(1 for c in self.conflicts if c.resolution == ResolutionAction.MANUAL)
            self.session.conflicts_certification_required = sum(1 for c in self.conflicts if c.requires_certification)
            
            # Count matches
            matched_keys = sum(1 for key, sources in self.entities_by_key.items() if len(sources) > 1)
            self.session.entities_matched = matched_keys
            
            primary_keys = set(self.entities_by_key.keys())
            for sec_id in self.secondary_source_ids:
                sec_entities = self.entities_by_source.get(sec_id, [])
                sec_keys = {e.source_unique_key for e in sec_entities}
                self.session.entities_only_in_secondary += len(sec_keys - primary_keys)
            
            self.session.entities_only_in_primary = len(primary_keys) - matched_keys
            
            self.session.status = "completed"
            self.session.completed_at = datetime.utcnow()
            self.session.duration_seconds = (self.session.completed_at - self.session.started_at).total_seconds()
            
        except Exception as e:
            self.session.status = "failed"
            self.session.error_message = str(e)
            logger.exception("Reconciliation failed")
        
        return self.session
    
    async def _compare_sources(self, primary_id: UUID, secondary_id: UUID):
        """Compare entities between two sources."""
        primary_entities = self.entities_by_source.get(primary_id, [])
        secondary_entities = self.entities_by_source.get(secondary_id, [])
        
        # Build lookup for secondary
        sec_by_key = {e.source_unique_key: e for e in secondary_entities}
        
        for primary_entity in primary_entities:
            key = primary_entity.source_unique_key
            secondary_entity = sec_by_key.get(key)
            
            if secondary_entity:
                # Entity exists in both - compare attributes
                await self._compare_entities(primary_entity, secondary_entity, primary_id, secondary_id)
            else:
                # Entity only in primary
                self._create_conflict(
                    ConflictType.MISSING_IN_SOURCE,
                    ConflictSeverity.LOW,
                    f"Entity '{primary_entity.name}' exists in {self.sources[primary_id].name} but not in {self.sources[secondary_id].name}",
                    primary_entity,
                    None,
                    primary_id,
                    secondary_id,
                )
        
        # Check for entities only in secondary
        prim_keys = {e.source_unique_key for e in primary_entities}
        for secondary_entity in secondary_entities:
            if secondary_entity.source_unique_key not in prim_keys:
                self._create_conflict(
                    ConflictType.EXTRA_IN_SOURCE,
                    ConflictSeverity.LOW,
                    f"Entity '{secondary_entity.name}' exists in {self.sources[secondary_id].name} but not in {self.sources[primary_id].name}",
                    None,
                    secondary_entity,
                    primary_id,
                    secondary_id,
                )
    
    async def _compare_entities(
        self,
        entity_a: CollectedEntity,
        entity_b: CollectedEntity,
        source_a_id: UUID,
        source_b_id: UUID
    ):
        """Compare two entities and detect attribute conflicts."""
        
        # Get comparable attributes
        attrs_a = self._get_comparable_attributes(entity_a)
        attrs_b = self._get_comparable_attributes(entity_b)
        
        all_attrs = set(attrs_a.keys()) | set(attrs_b.keys())
        
        for attr in all_attrs:
            val_a = attrs_a.get(attr)
            val_b = attrs_b.get(attr)
            
            if val_a != val_b:
                severity = self._determine_severity(attr, val_a, val_b, entity_a.entity_type)
                
                self._create_conflict(
                    ConflictType.ATTRIBUTE_MISMATCH,
                    severity,
                    f"Attribute '{attr}' differs: {self.sources[source_a_id].name}='{val_a}' vs {self.sources[source_b_id].name}='{val_b}'",
                    entity_a,
                    entity_b,
                    source_a_id,
                    source_b_id,
                    attribute_name=attr,
                    value_a=val_a,
                    value_b=val_b,
                )
        
        # Check hierarchy
        await self._compare_hierarchy(entity_a, entity_b, source_a_id, source_b_id)
        
        # Check state
        if entity_a.power_state != entity_b.power_state:
            self._create_conflict(
                ConflictType.STATE_MISMATCH,
                ConflictSeverity.MEDIUM,
                f"Power state differs: {entity_a.power_state} vs {entity_b.power_state}",
                entity_a,
                entity_b,
                source_a_id,
                source_b_id,
                attribute_name="power_state",
                value_a=entity_a.power_state,
                value_b=entity_b.power_state,
            )
    
    def _get_comparable_attributes(self, entity: CollectedEntity) -> Dict[str, Any]:
        """Get attributes that should be compared."""
        # Core attributes to compare
        comparable = {
            "name": entity.name,
            "datacenter": entity.datacenter,
            "rack": entity.rack,
            "manufacturer": entity.manufacturer,
            "model": entity.model,
            "serial_number": entity.serial_number,
            "cpu_cores": entity.cpu_cores,
            "cpu_threads": entity.cpu_threads,
            "cpu_model": entity.cpu_model,
            "memory_gb": entity.memory_gb,
            "primary_ip": entity.primary_ip,
            "power_state": entity.power_state,
            "connection_state": entity.connection_state,
            "total_storage_gb": entity.total_storage_gb,
        }
        
        # Add OS info
        if entity.os:
            comparable["os_name"] = entity.os.name
            comparable["os_version"] = entity.os.version
        
        # Add network interfaces (simplified)
        if entity.network_interfaces:
            comparable["network_interfaces"] = [
                {"name": n.name, "mac": n.mac_address, "ips": n.ip_addresses}
                for n in entity.network_interfaces
            ]
        
        # Entity-specific attributes
        if entity.entity_type == EntityType.VCENTER_CLUSTER:
            if isinstance(entity, CollectedEntity):  # Check for VMwareCluster
                comparable["ha_enabled"] = getattr(entity, "ha_enabled", None)
                comparable["drs_enabled"] = getattr(entity, "drs_enabled", None)
                comparable["vsan_enabled"] = getattr(entity, "vsan_enabled", None)
        
        return {k: v for k, v in comparable.items() if v is not None}
    
    def _determine_severity(
        self,
        attr: str,
        val_a: Any,
        val_b: Any,
        entity_type: EntityType
    ) -> ConflictSeverity:
        """Determine conflict severity based on attribute."""
        
        # Critical attributes
        critical_attrs = {
            "serial_number", "uuid", "primary_ip", "mac_address",
            "manufacturer", "model", "cpu_cores", "memory_gb"
        }
        
        # High severity attributes
        high_attrs = {
            "datacenter", "rack", "cpu_model", "os_name", "os_version",
            "total_storage_gb", "power_state", "connection_state"
        }
        
        # Medium severity attributes
        medium_attrs = {
            "name", "cpu_threads", "cpu_mhz", "network_interfaces"
        }
        
        if attr in critical_attrs:
            return ConflictSeverity.CRITICAL
        elif attr in high_attrs:
            return ConflictSeverity.HIGH
        elif attr in medium_attrs:
            return ConflictSeverity.MEDIUM
        else:
            return ConflictSeverity.LOW
    
    async def _compare_hierarchy(
        self,
        entity_a: CollectedEntity,
        entity_b: CollectedEntity,
        source_a_id: UUID,
        source_b_id: UUID
    ):
        """Compare parent/child relationships."""
        # Check parent
        if entity_a.parent_source_id != entity_b.parent_source_id:
            self._create_conflict(
                ConflictType.PARENT_MISMATCH,
                ConflictSeverity.MEDIUM,
                f"Parent differs: {entity_a.parent_source_id} vs {entity_b.parent_source_id}",
                entity_a,
                entity_b,
                source_a_id,
                source_b_id,
                attribute_name="parent",
                value_a=entity_a.parent_source_id,
                value_b=entity_b.parent_source_id,
            )
    
    def _create_conflict(
        self,
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        description: str,
        entity_a: Optional[CollectedEntity],
        entity_b: Optional[CollectedEntity],
        source_a_id: UUID,
        source_b_id: UUID,
        attribute_name: Optional[str] = None,
        value_a: Any = None,
        value_b: Any = None,
    ):
        """Create a conflict record."""
        conflict = Conflict(
            reconciliation_session_id=self.session.id,
            conflict_type=conflict_type,
            severity=severity,
            entity_a_id=entity_a.id if entity_a else None,
            entity_b_id=entity_b.id if entity_b else None,
            entity_a_source_id=source_a_id,
            entity_b_source_id=source_b_id,
            attribute_name=attribute_name,
            value_a=value_a,
            value_b=value_b,
            description=description,
            details={
                "entity_a_name": entity_a.name if entity_a else None,
                "entity_b_name": entity_b.name if entity_b else None,
                "entity_a_type": entity_a.entity_type.value if entity_a else None,
                "entity_b_type": entity_b.entity_type.value if entity_b else None,
            },
            # Require certification for high/critical conflicts
            requires_certification=severity in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL),
        )
        
        self.conflicts.append(conflict)
    
    async def _apply_rules(self):
        """Apply automatic reconciliation rules."""
        # Sort rules by priority
        sorted_rules = sorted(self.rules, key=lambda r: r.priority)
        
        for rule in sorted_rules:
            if not rule.enabled:
                continue
            
            for conflict in self.conflicts:
                if conflict.resolution is not None:
                    continue  # Already resolved
                
                if self._rule_matches(rule, conflict):
                    conflict.resolution = rule.action
                    conflict.resolved_by = "auto_rule"
                    conflict.resolved_at = datetime.utcnow()
                    conflict.resolution_notes = f"Applied rule: {rule.name}"
                    
                    # Set resolved value based on action
                    if rule.action == ResolutionAction.SOURCE_A_WINS:
                        conflict.resolved_value = conflict.value_a
                    elif rule.action == ResolutionAction.SOURCE_B_WINS:
                        conflict.resolved_value = conflict.value_b
                    elif rule.action == ResolutionAction.MERGE:
                        conflict.resolved_value = self._merge_values(
                            conflict.value_a, conflict.value_b, rule.parameters
                        )
                    
                    self.session.conflicts_auto_resolved += 1
    
    def _rule_matches(self, rule: ReconciliationRule, conflict: Conflict) -> bool:
        """Check if a rule matches a conflict."""
        # Check entity types
        if rule.entity_types and conflict.details.get("entity_a_type") not in rule.entity_types:
            return False
        
        # Check source types
        if rule.source_types:
            source_a = self.sources.get(conflict.entity_a_source_id)
            source_b = self.sources.get(conflict.entity_b_source_id)
            if source_a and source_a.source_type.value not in rule.source_types:
                return False
            if source_b and source_b.source_type.value not in rule.source_types:
                return False
        
        # Check attributes
        if rule.attributes and conflict.attribute_name not in rule.attributes:
            return False
        
        # Check condition
        if rule.condition:
            # Simple condition evaluation
            for key, expected in rule.condition.items():
                actual = conflict.details.get(key)
                if actual != expected:
                    return False
        
        return True
    
    def _merge_values(self, val_a: Any, val_b: Any, params: Dict[str, Any]) -> Any:
        """Merge two values based on strategy."""
        strategy = params.get("merge_strategy", "union")
        
        if strategy == "union" and isinstance(val_a, list) and isinstance(val_b, list):
            # Union of lists
            return list(set(val_a) | set(val_b))
        elif strategy == "concat" and isinstance(val_a, str) and isinstance(val_b, str):
            return f"{val_a}; {val_b}"
        elif strategy == "prefer_a":
            return val_a
        elif strategy == "prefer_b":
            return val_b
        elif strategy == "prefer_non_null":
            return val_a if val_a is not None else val_b
        
        return val_a
    
    def generate_report(self) -> ReconciliationReport:
        """Generate reconciliation report."""
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        by_resolution = defaultdict(int)
        
        for c in self.conflicts:
            by_severity[c.severity.value] += 1
            by_type[c.conflict_type.value] += 1
            if c.resolution:
                by_resolution[c.resolution.value] += 1
            else:
                by_resolution["unresolved"] += 1
        
        # Top conflicts by severity
        severity_order = {
            ConflictSeverity.CRITICAL: 0,
            ConflictSeverity.HIGH: 1,
            ConflictSeverity.MEDIUM: 2,
            ConflictSeverity.LOW: 3,
        }
        top_conflicts = sorted(
            self.conflicts,
            key=lambda c: severity_order.get(c.severity, 4)
        )[:10]
        
        # Recommendations
        recommendations = []
        if by_severity[ConflictSeverity.CRITICAL.value] > 0:
            recommendations.append(f"URGENT: {by_severity[ConflictSeverity.CRITICAL.value]} critical conflicts require immediate attention")
        if by_severity[ConflictSeverity.HIGH.value] > 0:
            recommendations.append(f"{by_severity[ConflictSeverity.HIGH.value]} high-severity conflicts need analyst review")
        if by_resolution["unresolved"] > 0:
            recommendations.append(f"{by_resolution['unresolved']} conflicts remain unresolved")
        
        return ReconciliationReport(
            session_id=self.session.id,
            session_name=self.session.name,
            status=self.session.status,
            total_conflicts=len(self.conflicts),
            by_severity=dict(by_severity),
            by_type=dict(by_type),
            by_resolution=dict(by_resolution),
            entities_compared=self.session.total_entities_compared,
            entities_matched=self.session.entities_matched,
            entities_unmatched=self.session.entities_only_in_primary + self.session.entities_only_in_secondary,
            top_conflicts=top_conflicts,
            recommendations=recommendations,
        )


class ReconciliationService:
    """High-level service for running reconciliations."""
    
    def __init__(
        self,
        entity_repository,
        source_repository,
        rule_repository
    ):
        self.entity_repository = entity_repository
        self.source_repository = source_repository
        self.rule_repository = rule_repository
    
    async def run_reconciliation(
        self,
        session: ReconciliationSession
    ) -> ReconciliationSession:
        """Run a full reconciliation session."""
        
        # Get sources
        sources = {}
        for source_id in session.source_ids:
            source = await self.source_repository.get(source_id)
            if source:
                sources[source_id] = source
        
        # Get entities for each source
        entities_by_source = {}
        for source_id in session.source_ids:
            # Query entities with optional filters
            entities = await self.entity_repository.get_by_source(
                source_id,
                entity_types=session.entity_types,
                filters=session.filters
            )
            entities_by_source[source_id] = entities
        
        # Get rules
        rules = await self.rule_repository.get_active_rules()
        
        # Run engine
        engine = ReconciliationEngine(session, sources, entities_by_source, rules)
        result = await engine.run()
        
        # Store conflicts
        for conflict in engine.conflicts:
            await self._store_conflict(conflict)
        
        return result
    
    async def _store_conflict(self, conflict: Conflict):
        """Store conflict in database."""
        # Implementation depends on repository
        pass
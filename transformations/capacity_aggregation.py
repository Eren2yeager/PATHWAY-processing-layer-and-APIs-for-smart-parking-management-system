"""
Capacity Aggregation with Pathway
Real-time parking slot counting and occupancy calculation
"""

import pathway as pw
from typing import Dict


class CapacityAggregator:
    """Real-time capacity aggregation using Pathway reducers"""
    
    def __init__(self):
        # Define schema for slot detections
        self.slot_schema = pw.schema_builder(
            {
                "parking_lot_id": pw.column_definition(dtype=str),
                "camera_id": pw.column_definition(dtype=str),
                "slot_id": pw.column_definition(dtype=int),
                "status": pw.column_definition(dtype=str),  # "occupied" or "empty"
                "confidence": pw.column_definition(dtype=float),
                "timestamp": pw.column_definition(dtype=int),
            }
        )
    
    def aggregate_capacity(self, slots_table: pw.Table) -> pw.Table:
        """
        Aggregate parking slot statuses to calculate capacity
        
        Args:
            slots_table: Input table with slot detection events
            
        Returns:
            Table with aggregated capacity metrics
        """
        
        # Get latest status for each slot
        latest_slots = slots_table.groupby(
            pw.this.parking_lot_id,
            pw.this.slot_id
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            slot_id=pw.this.slot_id,
            status=pw.reducers.latest(pw.this.status),
            confidence=pw.reducers.latest(pw.this.confidence),
            last_updated=pw.reducers.max(pw.this.timestamp),
        )
        
        # Aggregate by parking lot
        capacity = latest_slots.groupby(pw.this.parking_lot_id).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            total_slots=pw.reducers.count(),
            occupied=pw.reducers.sum(
                pw.apply(lambda status: 1 if status == "occupied" else 0, pw.this.status)
            ),
            empty=pw.reducers.sum(
                pw.apply(lambda status: 1 if status == "empty" else 0, pw.this.status)
            ),
            avg_confidence=pw.reducers.avg(pw.this.confidence),
            last_updated=pw.reducers.max(pw.this.last_updated),
        )
        
        # Calculate occupancy rate
        capacity_with_rate = capacity.select(
            parking_lot_id=pw.this.parking_lot_id,
            total_slots=pw.this.total_slots,
            occupied=pw.this.occupied,
            empty=pw.this.empty,
            occupancy_rate=pw.apply(
                lambda occ, total: occ / total if total > 0 else 0.0,
                pw.this.occupied,
                pw.this.total_slots
            ),
            avg_confidence=pw.this.avg_confidence,
            last_updated=pw.this.last_updated,
        )
        
        return capacity_with_rate
    
    def detect_capacity_changes(self, capacity_table: pw.Table) -> pw.Table:
        """
        Detect significant capacity changes
        
        Args:
            capacity_table: Table with capacity metrics
            
        Returns:
            Table with capacity change events
        """
        
        # Use windowby to track changes over time
        capacity_with_prev = capacity_table.windowby(
            pw.this.timestamp,
            window=pw.temporal.sliding(duration=60000, hop=10000)  # 1 min window, 10s hop
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            current_occupied=pw.reducers.latest(pw.this.occupied),
            prev_occupied=pw.reducers.earliest(pw.this.occupied),
            change=pw.reducers.latest(pw.this.occupied) - pw.reducers.earliest(pw.this.occupied),
        )
        
        # Filter only significant changes (> 5 slots)
        significant_changes = capacity_with_prev.filter(
            pw.apply(lambda change: abs(change) >= 5, pw.this.change)
        )
        
        return significant_changes
    
    def calculate_occupancy_trends(self, capacity_table: pw.Table) -> pw.Table:
        """
        Calculate occupancy trends over 5-minute windows
        
        Args:
            capacity_table: Table with capacity metrics
            
        Returns:
            Table with occupancy trends
        """
        
        trends = capacity_table.windowby(
            pw.this.last_updated,
            window=pw.temporal.sliding(duration=300000)  # 5 minutes
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            avg_occupancy=pw.reducers.avg(pw.this.occupied),
            max_occupancy=pw.reducers.max(pw.this.occupied),
            min_occupancy=pw.reducers.min(pw.this.occupied),
            avg_occupancy_rate=pw.reducers.avg(pw.this.occupancy_rate),
        )
        
        return trends
    
    def detect_threshold_breaches(
        self, 
        capacity_table: pw.Table,
        threshold: float = 0.9
    ) -> pw.Table:
        """
        Detect when occupancy exceeds threshold
        
        Args:
            capacity_table: Table with capacity metrics
            threshold: Occupancy rate threshold (default 0.9 = 90%)
            
        Returns:
            Table with threshold breach events
        """
        
        breaches = capacity_table.filter(
            pw.this.occupancy_rate >= threshold
        ).select(
            parking_lot_id=pw.this.parking_lot_id,
            occupancy_rate=pw.this.occupancy_rate,
            occupied=pw.this.occupied,
            total_slots=pw.this.total_slots,
            breach_time=pw.this.last_updated,
            severity=pw.apply(
                lambda rate: "critical" if rate >= 0.95 else "warning",
                pw.this.occupancy_rate
            ),
        )
        
        return breaches

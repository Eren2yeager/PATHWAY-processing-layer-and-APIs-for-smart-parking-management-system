"""
Vehicle Tracking with Pathway Stateful Processing
Tracks vehicle entry/exit events and calculates duration
"""

import pathway as pw
from datetime import datetime
from typing import Optional


class VehicleTracker:
    """Stateful vehicle tracking using Pathway Tables"""
    
    def __init__(self):
        # Define schema for vehicle events
        self.vehicle_events_schema = pw.schema_builder(
            {
                "plate_number": pw.column_definition(dtype=str),
                "timestamp": pw.column_definition(dtype=int),
                "parking_lot_id": pw.column_definition(dtype=str),
                "camera_id": pw.column_definition(dtype=str),
                "event_type": pw.column_definition(dtype=str),  # "entry" or "exit"
                "confidence": pw.column_definition(dtype=float),
            }
        )
        
        # Vehicle state table (active vehicles)
        self.active_vehicles = {}
    
    def create_vehicle_pipeline(self, events_table: pw.Table) -> pw.Table:
        """
        Create Pathway pipeline for vehicle tracking
        
        Args:
            events_table: Input table with vehicle detection events
            
        Returns:
            Table with enriched vehicle journey data
        """
        
        # Separate entry and exit events
        entries = events_table.filter(pw.this.event_type == "entry")
        exits = events_table.filter(pw.this.event_type == "exit")
        
        # Deduplicate entries within 10 seconds
        unique_entries = entries.deduplicate(
            key=pw.this.plate_number,
            instance=pw.this.parking_lot_id,
            acceptor=pw.temporal.tumbling(duration=10000)  # 10 seconds in ms
        )
        
        # Deduplicate exits within 10 seconds
        unique_exits = exits.deduplicate(
            key=pw.this.plate_number,
            instance=pw.this.parking_lot_id,
            acceptor=pw.temporal.tumbling(duration=10000)
        )
        
        # Join entries with exits to calculate duration
        vehicle_journeys = unique_entries.join(
            unique_exits,
            unique_entries.plate_number == unique_exits.plate_number,
            unique_entries.parking_lot_id == unique_exits.parking_lot_id,
        ).select(
            plate_number=unique_entries.plate_number,
            parking_lot_id=unique_entries.parking_lot_id,
            entry_time=unique_entries.timestamp,
            entry_camera=unique_entries.camera_id,
            exit_time=unique_exits.timestamp,
            exit_camera=unique_exits.camera_id,
            duration_seconds=(unique_exits.timestamp - unique_entries.timestamp) / 1000,
            entry_confidence=unique_entries.confidence,
            exit_confidence=unique_exits.confidence,
        )
        
        return vehicle_journeys
    
    def track_active_vehicles(self, events_table: pw.Table) -> pw.Table:
        """
        Track currently active (parked) vehicles
        
        Args:
            events_table: Input table with vehicle detection events
            
        Returns:
            Table with currently active vehicles
        """
        
        # Get latest event for each vehicle
        latest_events = events_table.groupby(
            pw.this.plate_number,
            pw.this.parking_lot_id
        ).reduce(
            plate_number=pw.this.plate_number,
            parking_lot_id=pw.this.parking_lot_id,
            last_event_type=pw.reducers.latest(pw.this.event_type),
            last_timestamp=pw.reducers.max(pw.this.timestamp),
            last_camera=pw.reducers.latest(pw.this.camera_id),
        )
        
        # Filter only vehicles with entry as last event (currently inside)
        active_vehicles = latest_events.filter(
            pw.this.last_event_type == "entry"
        ).select(
            plate_number=pw.this.plate_number,
            parking_lot_id=pw.this.parking_lot_id,
            entry_time=pw.this.last_timestamp,
            camera_id=pw.this.last_camera,
            status=pw.apply(lambda: "inside", pw.this.plate_number),
        )
        
        return active_vehicles
    
    def calculate_duration_stats(self, journeys_table: pw.Table) -> pw.Table:
        """
        Calculate duration statistics per parking lot
        
        Args:
            journeys_table: Table with completed vehicle journeys
            
        Returns:
            Table with duration statistics
        """
        
        stats = journeys_table.groupby(pw.this.parking_lot_id).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            total_vehicles=pw.reducers.count(),
            avg_duration_seconds=pw.reducers.avg(pw.this.duration_seconds),
            min_duration_seconds=pw.reducers.min(pw.this.duration_seconds),
            max_duration_seconds=pw.reducers.max(pw.this.duration_seconds),
        )
        
        return stats

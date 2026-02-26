"""
Duplicate Detection Filter using Pathway
Prevents duplicate detections within time windows
"""

import pathway as pw
from typing import Optional


class DuplicateFilter:
    """Temporal deduplication using Pathway"""
    
    def __init__(self, window_seconds: int = 10):
        """
        Initialize duplicate filter
        
        Args:
            window_seconds: Time window for deduplication (default 10 seconds)
        """
        self.window_ms = window_seconds * 1000
    
    def filter_duplicate_plates(
        self, 
        detections_table: pw.Table,
        window_seconds: Optional[int] = None
    ) -> pw.Table:
        """
        Filter duplicate license plate detections
        
        Args:
            detections_table: Table with plate detection events
            window_seconds: Override default window (optional)
            
        Returns:
            Table with deduplicated detections
        """
        
        window = window_seconds * 1000 if window_seconds else self.window_ms
        
        # Deduplicate by timestamp within each (plate_number, parking_lot_id) group.
        # acceptor(new_timestamp, old_timestamp) -> True means "accept the new row"
        # We accept a new detection only if enough time has passed since the last one.
        unique_detections = detections_table.deduplicate(
            value=pw.this.timestamp,
            instance=pw.this.plate_number,
            acceptor=lambda new_ts, old_ts: abs(new_ts - old_ts) >= window,
        )
        
        return unique_detections
    
    def filter_duplicate_capacity_updates(
        self,
        capacity_table: pw.Table,
        min_change_threshold: int = 1
    ) -> pw.Table:
        """
        Filter duplicate capacity updates (only emit when changed)
        
        Args:
            capacity_table: Table with capacity metrics
            min_change_threshold: Minimum change to emit update
            
        Returns:
            Table with only changed capacity values
        """
        
        # Group by parking lot and track changes
        capacity_changes = capacity_table.groupby(
            pw.this.parking_lot_id
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            current_occupied=pw.reducers.latest(pw.this.occupied),
            prev_occupied=pw.reducers.earliest(pw.this.occupied),
            has_changed=pw.apply(
                lambda curr, prev: abs(curr - prev) >= min_change_threshold,
                pw.reducers.latest(pw.this.occupied),
                pw.reducers.earliest(pw.this.occupied)
            ),
        )
        
        # Filter only changed values
        changed_capacity = capacity_changes.filter(pw.this.has_changed)
        
        return changed_capacity
    
    def filter_low_confidence_detections(
        self,
        detections_table: pw.Table,
        min_confidence: float = 0.5
    ) -> pw.Table:
        """
        Filter out low confidence detections
        
        Args:
            detections_table: Table with detection events
            min_confidence: Minimum confidence threshold
            
        Returns:
            Table with high confidence detections only
        """
        
        high_confidence = detections_table.filter(
            pw.this.confidence >= min_confidence
        )
        
        return high_confidence
    
    def aggregate_duplicate_stats(
        self,
        original_table: pw.Table,
        filtered_table: pw.Table
    ) -> pw.Table:
        """
        Calculate statistics about filtered duplicates
        
        Args:
            original_table: Original detections table
            filtered_table: Deduplicated table
            
        Returns:
            Table with duplicate statistics
        """
        
        original_count = original_table.groupby(
            pw.this.parking_lot_id
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            total_detections=pw.reducers.count(),
        )
        
        filtered_count = filtered_table.groupby(
            pw.this.parking_lot_id
        ).reduce(
            parking_lot_id=pw.this.parking_lot_id,
            unique_detections=pw.reducers.count(),
        )
        
        stats = original_count.join(
            filtered_count,
            original_count.parking_lot_id == filtered_count.parking_lot_id
        ).select(
            parking_lot_id=original_count.parking_lot_id,
            total_detections=original_count.total_detections,
            unique_detections=filtered_count.unique_detections,
            duplicates_filtered=original_count.total_detections - filtered_count.unique_detections,
            duplicate_rate=pw.apply(
                lambda total, unique: (total - unique) / total if total > 0 else 0.0,
                original_count.total_detections,
                filtered_count.unique_detections
            ),
        )
        
        return stats

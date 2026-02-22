"""
Pathway Pipeline Manager
Orchestrates Pathway stateful processing pipelines
"""

import pathway as pw
from typing import Optional
import asyncio

from transformations.vehicle_tracking import VehicleTracker
from transformations.capacity_aggregation import CapacityAggregator
from transformations.duplicate_filter import DuplicateFilter
from connectors.camera_input import PathwayStreamConnector
from connectors.nextjs_output import PathwayOutputHandler
from config.settings import settings
from utils.logger import logger


class PathwayPipelineManager:
    """
    Manages Pathway streaming pipelines for smart parking
    Provides stateful processing on top of FastAPI layer
    """
    
    def __init__(self):
        self.vehicle_tracker = VehicleTracker()
        self.capacity_aggregator = CapacityAggregator()
        self.duplicate_filter = DuplicateFilter(window_seconds=settings.duplicate_detection_window)
        self.stream_connector = PathwayStreamConnector()
        self.output_handler = PathwayOutputHandler()
        # Real-time capacity cache per lot (for GET /api/capacity/current)
        self._last_capacity: dict = {}

        # Pipeline state
        self.is_running = False
        self.pipeline_task = None
    
    async def start(self):
        """Start Pathway pipelines"""
        if self.is_running:
            logger.warning("Pathway pipeline already running")
            return
        
        logger.info("Starting Pathway stateful processing pipelines...")
        self.is_running = True
        
        # Start background pipeline processing
        self.pipeline_task = asyncio.create_task(self._run_pipeline())
        
        logger.info("✓ Pathway pipelines started")
    
    async def stop(self):
        """Stop Pathway pipelines"""
        if not self.is_running:
            return
        
        logger.info("Stopping Pathway pipelines...")
        self.is_running = False
        
        if self.pipeline_task:
            self.pipeline_task.cancel()
            try:
                await self.pipeline_task
            except asyncio.CancelledError:
                pass
        
        await self.output_handler.close()
        logger.info("✓ Pathway pipelines stopped")
    
    async def _run_pipeline(self):
        """
        Main pipeline processing loop
        Processes buffered events through Pathway transformations
        """
        try:
            while self.is_running:
                # Process vehicle events
                vehicle_events = self.stream_connector.get_vehicle_events()
                if vehicle_events:
                    await self._process_vehicle_events(vehicle_events)
                
                # Process capacity events
                capacity_events = self.stream_connector.get_capacity_events()
                if capacity_events:
                    await self._process_capacity_events(capacity_events)
                
                # Sleep briefly to avoid busy loop
                await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            logger.info("Pipeline processing cancelled")
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
    
    async def _process_vehicle_events(self, events: list):
        """
        Process vehicle detection events through Pathway pipeline
        
        Args:
            events: List of vehicle detection events
        """
        try:
            # In a full Pathway implementation, these would be processed
            # through Pathway tables with stateful transformations
            
            # For now, we'll implement the logic manually but following
            # Pathway's stateful processing patterns
            
            for event in events:
                # Apply duplicate filtering logic
                if self._is_duplicate_vehicle_event(event):
                    logger.debug(f"Filtered duplicate: {event['plate_number']}")
                    continue
                
                # Track vehicle state
                await self._track_vehicle_state(event)
                
                # Send to Next.js
                if event['event_type'] == 'entry':
                    await self.output_handler.connector.send_vehicle_entry(event)
                elif event['event_type'] == 'exit':
                    # Calculate duration if we have entry record
                    duration = await self._calculate_duration(event)
                    if duration:
                        event['duration_seconds'] = duration
                    await self.output_handler.connector.send_vehicle_exit(event)
        
        except Exception as e:
            logger.error(f"Error processing vehicle events: {e}")
    
    async def _process_capacity_events(self, events: list):
        """
        Process capacity events through Pathway pipeline
        
        Args:
            events: List of capacity update events
        """
        try:
            if not events:
                return
            
            logger.debug(f"Processing {len(events)} capacity events")
            
            # Group events by parking lot
            lots = {}
            for event in events:
                lot_id = event['parking_lot_id']
                if lot_id not in lots:
                    lots[lot_id] = []
                lots[lot_id].append(event)
            
            logger.debug(f"Grouped into {len(lots)} parking lots")
            
            # Aggregate capacity for each lot
            for lot_id, lot_events in lots.items():
                logger.debug(f"Aggregating {len(lot_events)} events for lot {lot_id}")
                capacity_data = self._aggregate_capacity(lot_events)
                self._last_capacity[lot_id] = capacity_data

                # Check for threshold breaches
                if capacity_data['occupancy_rate'] >= 0.9:
                    breach_data = {
                        **capacity_data,
                        'breach_time': capacity_data['last_updated'],
                        'severity': 'critical' if capacity_data['occupancy_rate'] >= 0.95 else 'warning'
                    }
                    await self.output_handler.handle_threshold_breach(breach_data)
                else:
                    # Send normal capacity update
                    await self.output_handler.handle_capacity_update(capacity_data)
        
        except Exception as e:
            logger.error(f"Error processing capacity events: {e}")
    
    def _is_duplicate_vehicle_event(self, event: dict) -> bool:
        """
        Check if vehicle event is a duplicate (within time window)
        Implements Pathway's deduplication logic
        """
        # This would use Pathway's deduplicate() in full implementation
        # For now, simple time-based check
        key = f"{event['plate_number']}_{event['parking_lot_id']}"
        current_time = event['timestamp']
        
        if not hasattr(self, '_last_vehicle_events'):
            self._last_vehicle_events = {}
        
        if key in self._last_vehicle_events:
            last_time = self._last_vehicle_events[key]
            if (current_time - last_time) < (settings.duplicate_detection_window * 1000):
                return True
        
        self._last_vehicle_events[key] = current_time
        return False
    
    async def _track_vehicle_state(self, event: dict):
        """
        Track vehicle state (entry/exit)
        Implements Pathway's stateful tracking
        """
        if not hasattr(self, '_vehicle_state'):
            self._vehicle_state = {}
        
        key = f"{event['plate_number']}_{event['parking_lot_id']}"
        
        if event['event_type'] == 'entry':
            self._vehicle_state[key] = {
                'entry_time': event['timestamp'],
                'entry_camera': event['camera_id'],
                'entry_confidence': event['confidence'],
            }
        elif event['event_type'] == 'exit':
            # State will be used for duration calculation
            pass
    
    async def _calculate_duration(self, exit_event: dict) -> Optional[float]:
        """
        Calculate parking duration
        Implements Pathway's join logic for entry/exit matching
        """
        if not hasattr(self, '_vehicle_state'):
            return None
        
        key = f"{exit_event['plate_number']}_{exit_event['parking_lot_id']}"
        
        if key in self._vehicle_state:
            entry_data = self._vehicle_state[key]
            duration_ms = exit_event['timestamp'] - entry_data['entry_time']
            duration_seconds = duration_ms / 1000
            
            # Clean up state
            del self._vehicle_state[key]
            
            return duration_seconds
        
        return None
    
    def _aggregate_capacity(self, events: list) -> dict:
        """
        Aggregate capacity from slot events
        Implements Pathway's groupby().reduce() logic
        """
        # Get latest status for each slot
        slots = {}
        for event in events:
            slot_id = event['slot_id']
            if slot_id not in slots or event['timestamp'] > slots[slot_id]['timestamp']:
                slots[slot_id] = event
        
        # Calculate aggregates
        total_slots = len(slots)
        occupied = sum(1 for s in slots.values() if s['status'] == 'occupied')
        empty = total_slots - occupied
        occupancy_rate = occupied / total_slots if total_slots > 0 else 0.0
        
        # Get latest timestamp
        last_updated = max(s['timestamp'] for s in slots.values()) if slots else 0
        
        # Format individual slots for Next.js
        slots_array = [
            {
                'slot_id': slot_id,
                'status': slot_data['status'],
                'confidence': slot_data['confidence']
            }
            for slot_id, slot_data in slots.items()
        ]
        
        logger.debug(f"Aggregated capacity: lot={events[0]['parking_lot_id']}, "
                    f"total={total_slots}, occupied={occupied}, slots_array_len={len(slots_array)}")
        
        return {
            'parking_lot_id': events[0]['parking_lot_id'],
            'total_slots': total_slots,
            'occupied': occupied,
            'empty': empty,
            'occupancy_rate': occupancy_rate,
            'last_updated': last_updated,
            'slots': slots_array,  # Include individual slot details
        }
    
    # Public API for FastAPI integration
    
    def add_vehicle_detection(
        self,
        plate_number: str,
        parking_lot_id: str,
        camera_id: str,
        event_type: str,
        confidence: float,
        timestamp: Optional[int] = None
    ):
        """Add vehicle detection to Pathway pipeline"""
        self.stream_connector.add_vehicle_detection(
            plate_number=plate_number,
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            event_type=event_type,
            confidence=confidence,
            timestamp=timestamp
        )
    
    def add_capacity_update(
        self,
        parking_lot_id: str,
        camera_id: str,
        slot_id: int,
        status: str,
        confidence: float,
        timestamp: Optional[int] = None
    ):
        """Add capacity update to Pathway pipeline"""
        self.stream_connector.add_capacity_update(
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            slot_id=slot_id,
            status=status,
            confidence=confidence,
            timestamp=timestamp
        )

    def get_current_capacity(self, parking_lot_id: str) -> Optional[dict]:
        """Get latest aggregated capacity for a parking lot (real-time from Pathway state)."""
        return self._last_capacity.get(parking_lot_id)


# Global pipeline instance
pathway_pipeline: Optional[PathwayPipelineManager] = None


def get_pathway_pipeline() -> PathwayPipelineManager:
    """Get global Pathway pipeline instance"""
    global pathway_pipeline
    if pathway_pipeline is None:
        pathway_pipeline = PathwayPipelineManager()
    return pathway_pipeline

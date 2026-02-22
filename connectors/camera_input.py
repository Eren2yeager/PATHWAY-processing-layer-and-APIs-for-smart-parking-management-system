"""
Pathway Input Connectors for Camera Streams
Bridges FastAPI WebSocket to Pathway Tables
"""

import pathway as pw
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import json


class CameraInputConnector:
    """Input connector that bridges WebSocket data to Pathway tables"""
    
    def __init__(self):
        self.vehicle_events_queue = asyncio.Queue()
        self.capacity_events_queue = asyncio.Queue()
    
    async def push_vehicle_event(self, event_data: Dict[str, Any]):
        """
        Push vehicle detection event to Pathway pipeline
        
        Args:
            event_data: Vehicle detection data
        """
        await self.vehicle_events_queue.put(event_data)
    
    async def push_capacity_event(self, event_data: Dict[str, Any]):
        """
        Push capacity update event to Pathway pipeline
        
        Args:
            event_data: Capacity data
        """
        await self.capacity_events_queue.put(event_data)
    
    def create_vehicle_events_table(self) -> pw.Table:
        """
        Create Pathway table from vehicle events queue
        
        Returns:
            Pathway table with vehicle events
        """
        
        # Define schema
        class VehicleEventSchema(pw.Schema):
            plate_number: str
            timestamp: int
            parking_lot_id: str
            camera_id: str
            event_type: str  # "entry" or "exit"
            confidence: float
        
        # Create input connector
        # Note: In production, use pw.io.python.read() or custom connector
        # For now, we'll use a placeholder that can be populated
        table = pw.Table.empty(
            plate_number=pw.column_definition(dtype=str),
            timestamp=pw.column_definition(dtype=int),
            parking_lot_id=pw.column_definition(dtype=str),
            camera_id=pw.column_definition(dtype=str),
            event_type=pw.column_definition(dtype=str),
            confidence=pw.column_definition(dtype=float),
        )
        
        return table
    
    def create_capacity_events_table(self) -> pw.Table:
        """
        Create Pathway table from capacity events queue
        
        Returns:
            Pathway table with capacity events
        """
        
        # Define schema
        class CapacityEventSchema(pw.Schema):
            parking_lot_id: str
            camera_id: str
            slot_id: int
            status: str  # "occupied" or "empty"
            confidence: float
            timestamp: int
        
        # Create input connector
        table = pw.Table.empty(
            parking_lot_id=pw.column_definition(dtype=str),
            camera_id=pw.column_definition(dtype=str),
            slot_id=pw.column_definition(dtype=int),
            status=pw.column_definition(dtype=str),
            confidence=pw.column_definition(dtype=float),
            timestamp=pw.column_definition(dtype=int),
        )
        
        return table


class PathwayStreamConnector:
    """
    Connector for streaming data into Pathway
    Uses Python connector for real-time data ingestion
    """
    
    def __init__(self):
        self.vehicle_buffer = []
        self.capacity_buffer = []
    
    def add_vehicle_detection(
        self,
        plate_number: str,
        parking_lot_id: str,
        camera_id: str,
        event_type: str,
        confidence: float,
        timestamp: Optional[int] = None
    ):
        """Add vehicle detection to buffer"""
        if timestamp is None:
            timestamp = int(datetime.now().timestamp() * 1000)
        
        self.vehicle_buffer.append({
            "plate_number": plate_number,
            "parking_lot_id": parking_lot_id,
            "camera_id": camera_id,
            "event_type": event_type,
            "confidence": confidence,
            "timestamp": timestamp,
        })
    
    def add_capacity_update(
        self,
        parking_lot_id: str,
        camera_id: str,
        slot_id: int,
        status: str,
        confidence: float,
        timestamp: Optional[int] = None
    ):
        """Add capacity update to buffer"""
        if timestamp is None:
            timestamp = int(datetime.now().timestamp() * 1000)
        
        event = {
            "parking_lot_id": parking_lot_id,
            "camera_id": camera_id,
            "slot_id": slot_id,
            "status": status,
            "confidence": confidence,
            "timestamp": timestamp,
        }
        self.capacity_buffer.append(event)
        
        # Debug: Log buffer size periodically
        if len(self.capacity_buffer) % 10 == 0:
            from utils.logger import logger
            logger.debug(f"Capacity buffer size: {len(self.capacity_buffer)}")
    
    def get_vehicle_events(self):
        """Get and clear vehicle events buffer"""
        events = self.vehicle_buffer.copy()
        self.vehicle_buffer.clear()
        return events
    
    def get_capacity_events(self):
        """Get and clear capacity events buffer"""
        events = self.capacity_buffer.copy()
        self.capacity_buffer.clear()
        return events

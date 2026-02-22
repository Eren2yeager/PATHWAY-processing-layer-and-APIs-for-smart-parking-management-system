from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from .detection_result import BoundingBox, ParkingSlotDetection


class VehicleEntryEvent(BaseModel):
    """Event sent when a vehicle enters the parking lot"""
    event_type: str = Field(default="vehicle_entry", description="Event type identifier")
    plate_number: str = Field(..., description="License plate number")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    gate_id: str = Field(..., description="Gate camera identifier")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Entry timestamp")
    bbox: BoundingBox = Field(..., description="Bounding box of detected plate")
    image_url: Optional[str] = Field(None, description="URL to stored frame image")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "vehicle_entry",
                "plate_number": "DL01AB1234",
                "parking_lot_id": "lot_123",
                "gate_id": "gate_1",
                "confidence": 0.95,
                "timestamp": "2026-02-16T10:30:00Z",
                "bbox": {"x1": 100, "y1": 200, "x2": 300, "y2": 400}
            }
        }


class VehicleExitEvent(BaseModel):
    """Event sent when a vehicle exits the parking lot"""
    event_type: str = Field(default="vehicle_exit", description="Event type identifier")
    plate_number: str = Field(..., description="License plate number")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    gate_id: str = Field(..., description="Gate camera identifier")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    entry_timestamp: Optional[datetime] = Field(None, description="Original entry timestamp")
    exit_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Exit timestamp")
    duration_minutes: Optional[int] = Field(None, description="Parking duration in minutes")
    bbox: BoundingBox = Field(..., description="Bounding box of detected plate")
    image_url: Optional[str] = Field(None, description="URL to stored frame image")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "vehicle_exit",
                "plate_number": "DL01AB1234",
                "parking_lot_id": "lot_123",
                "gate_id": "gate_1",
                "confidence": 0.93,
                "entry_timestamp": "2026-02-16T09:15:00Z",
                "exit_timestamp": "2026-02-16T10:30:00Z",
                "duration_minutes": 75,
                "bbox": {"x1": 100, "y1": 200, "x2": 300, "y2": 400}
            }
        }


class CapacityUpdateEvent(BaseModel):
    """Event sent when parking capacity changes"""
    event_type: str = Field(default="capacity_update", description="Event type identifier")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    camera_id: str = Field(..., description="Lot camera identifier")
    total_slots: int = Field(..., description="Total parking slots")
    occupied: int = Field(..., description="Number of occupied slots")
    empty: int = Field(..., description="Number of empty slots")
    occupancy_rate: float = Field(..., ge=0.0, le=1.0, description="Occupancy rate (0.0 to 1.0)")
    slots: List[ParkingSlotDetection] = Field(..., description="Individual slot statuses")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "capacity_update",
                "parking_lot_id": "lot_123",
                "camera_id": "lot_cam_1",
                "total_slots": 100,
                "occupied": 67,
                "empty": 33,
                "occupancy_rate": 0.67,
                "slots": [
                    {"slot_id": 1, "status": "occupied", "confidence": 0.92, "bbox": {"x1": 10, "y1": 20, "x2": 50, "y2": 80}},
                    {"slot_id": 2, "status": "empty", "confidence": 0.88, "bbox": {"x1": 60, "y1": 20, "x2": 100, "y2": 80}}
                ],
                "timestamp": "2026-02-16T10:30:00Z",
                "processing_time_ms": 120
            }
        }

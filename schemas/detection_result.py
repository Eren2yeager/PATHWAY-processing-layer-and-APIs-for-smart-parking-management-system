from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x1: float = Field(..., description="Top-left x coordinate")
    y1: float = Field(..., description="Top-left y coordinate")
    x2: float = Field(..., description="Bottom-right x coordinate")
    y2: float = Field(..., description="Bottom-right y coordinate")


class LicensePlateDetection(BaseModel):
    """License plate detection result"""
    plate_number: str = Field(..., description="Detected plate number")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    camera_id: str = Field(..., description="Camera identifier")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


class ParkingSlotDetection(BaseModel):
    """Single parking slot detection"""
    slot_id: int = Field(..., description="Slot identifier")
    status: str = Field(..., description="Slot status (occupied/empty)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")


class ParkingSlotDetectionResult(BaseModel):
    """Parking lot capacity detection result"""
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    camera_id: str = Field(..., description="Camera identifier")
    total_slots: int = Field(..., description="Total number of slots detected")
    occupied: int = Field(..., description="Number of occupied slots")
    empty: int = Field(..., description="Number of empty slots")
    occupancy_rate: float = Field(..., ge=0.0, le=1.0, description="Occupancy rate (0.0 to 1.0)")
    slots: List[ParkingSlotDetection] = Field(..., description="Individual slot detections")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


class VehicleDetection(BaseModel):
    """Vehicle detection result"""
    vehicle_type: str = Field(..., description="Type of vehicle (car, truck, motorcycle, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    camera_id: str = Field(..., description="Camera identifier")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


class DetectionResult(BaseModel):
    """Generic detection result wrapper"""
    success: bool = Field(..., description="Whether detection was successful")
    detections: List[Dict[str, Any]] = Field(default_factory=list, description="List of detections")
    error: Optional[str] = Field(None, description="Error message if detection failed")
    processing_time_ms: Optional[float] = Field(None, description="Total processing time")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Result timestamp")

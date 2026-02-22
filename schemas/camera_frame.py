from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class FrameType(str, Enum):
    """Type of camera frame"""
    GATE = "gate"
    LOT = "lot"
    GENERAL = "general"


class CameraFrameSchema(BaseModel):
    """Schema for camera frame input"""
    
    image: str = Field(..., description="Base64 encoded image")
    camera_id: str = Field(..., description="Unique camera identifier")
    parking_lot_id: str = Field(..., description="Parking lot identifier")
    frame_type: FrameType = Field(..., description="Type of frame (gate/lot)")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Frame timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "camera_id": "gate_1",
                "parking_lot_id": "lot_123",
                "frame_type": "gate",
                "timestamp": "2026-02-16T10:30:00Z"
            }
        }

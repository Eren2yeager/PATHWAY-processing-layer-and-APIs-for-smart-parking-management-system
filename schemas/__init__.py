from .camera_frame import CameraFrameSchema, FrameType
from .detection_result import (
    DetectionResult,
    LicensePlateDetection,
    ParkingSlotDetection,
    VehicleDetection
)
from .events import (
    VehicleEntryEvent,
    VehicleExitEvent,
    CapacityUpdateEvent
)

__all__ = [
    "CameraFrameSchema",
    "FrameType",
    "DetectionResult",
    "LicensePlateDetection",
    "ParkingSlotDetection",
    "VehicleDetection",
    "VehicleEntryEvent",
    "VehicleExitEvent",
    "CapacityUpdateEvent"
]

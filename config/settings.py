import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Pathway Configuration
    pathway_host: str = os.getenv("PATHWAY_HOST", "0.0.0.0")
    pathway_port: int = int(os.getenv("PATHWAY_PORT", "8000"))
    pathway_log_level: str = os.getenv("PATHWAY_LOG_LEVEL", "INFO")
    
    # Roboflow API
    roboflow_api_key: str = os.getenv("ROBOFLOW_API_KEY", "")
    roboflow_workspace: str = os.getenv("ROBOFLOW_WORKSPACE", "")
    roboflow_license_plate_project: str = os.getenv("ROBOFLOW_LICENSE_PLATE_PROJECT", "")
    roboflow_license_plate_version: int = int(os.getenv("ROBOFLOW_LICENSE_PLATE_VERSION", "1"))
    roboflow_parking_slot_project: str = os.getenv("ROBOFLOW_PARKING_SLOT_PROJECT", "")
    roboflow_parking_slot_version: int = int(os.getenv("ROBOFLOW_PARKING_SLOT_VERSION", "1"))
    
    # Detection Thresholds
    plate_detection_confidence: float = float(os.getenv("PLATE_DETECTION_CONFIDENCE", "20"))
    parking_slot_confidence: float = float(os.getenv("PARKING_SLOT_CONFIDENCE", "20"))
    vehicle_detection_confidence: float = float(os.getenv("VEHICLE_DETECTION_CONFIDENCE", "50"))
    
    # Frame Processing
    gate_frame_skip: int = int(os.getenv("GATE_FRAME_SKIP", "10"))
    lot_frame_skip: int = int(os.getenv("LOT_FRAME_SKIP", "20"))
    duplicate_detection_window: int = int(os.getenv("DUPLICATE_DETECTION_WINDOW", "10"))
    
    # Next.js Integration
    nextjs_api_url: str = os.getenv("NEXTJS_API_URL", "http://localhost:3000")
    nextjs_webhook_entry: str = os.getenv("NEXTJS_WEBHOOK_ENTRY", "/api/pathway/webhook/entry")
    nextjs_webhook_exit: str = os.getenv("NEXTJS_WEBHOOK_EXIT", "/api/pathway/webhook/exit")
    nextjs_webhook_capacity: str = os.getenv("NEXTJS_WEBHOOK_CAPACITY", "/api/pathway/webhook/capacity")
    nextjs_webhook_timeout_seconds: float = float(os.getenv("NEXTJS_WEBHOOK_TIMEOUT_SECONDS", "30"))
    pathway_webhook_secret: str = os.getenv("PATHWAY_WEBHOOK_SECRET", "")
    
    # Performance
    max_concurrent_streams: int = int(os.getenv("MAX_CONCURRENT_STREAMS", "10"))
    buffer_size: int = int(os.getenv("BUFFER_SIZE", "100"))
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

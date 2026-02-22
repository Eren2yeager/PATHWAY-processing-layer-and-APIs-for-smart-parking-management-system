"""
Parking Slot Detection Model
Detects occupied and empty parking spaces using Roboflow
"""

from roboflow import Roboflow
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time
from typing import List
from io import BytesIO

from config.settings import settings
from utils.logger import logger
from schemas.detection_result import ParkingSlotDetection, ParkingSlotDetectionResult, BoundingBox


class ParkingSlotDetectorModel:
    """Parking slot occupancy detection model using Roboflow"""
    
    def __init__(self):
        """Initialize Roboflow parking slot detection model"""
        self._init_roboflow()
        logger.info("Parking Slot Detector initialized successfully")
    
    def _init_roboflow(self):
        """Initialize Roboflow parking detection model"""
        try:
            rf = Roboflow(api_key=settings.roboflow_api_key)
            
            # Use workspace() without parameter if workspace is empty
            if settings.roboflow_workspace:
                project = rf.workspace(settings.roboflow_workspace).project(
                    settings.roboflow_parking_slot_project
                )
            else:
                project = rf.workspace().project(settings.roboflow_parking_slot_project)
            
            self.detection_model = project.version(settings.roboflow_parking_slot_version).model
            
            # Convert confidence threshold (already 0-100 from .env)
            self.confidence_threshold = int(settings.parking_slot_confidence)
            self.overlap_threshold = 30
            
            logger.info(f"Roboflow parking slot detector loaded (confidence: {self.confidence_threshold}%)")
        except Exception as e:
            logger.error(f"Failed to initialize Roboflow parking detector: {e}")
            logger.warning("Parking slot detector will not be available")
            self.detection_model = None
    
    def detect_slots(
        self,
        image: np.ndarray,
        camera_id: str,
        parking_lot_id: str
    ) -> ParkingSlotDetectionResult:
        """
        Detect parking slot occupancy
        
        Args:
            image: OpenCV image (numpy array)
            camera_id: Camera identifier
            parking_lot_id: Parking lot identifier
            
        Returns:
            ParkingSlotDetectionResult with all slot statuses
        """
        start_time = time.time()
        temp_path = None
        
        try:
            # Convert to PIL Image
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Save to temporary file (Roboflow requires file path)
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name
                pil_image.save(temp_path, quality=85)
            
            # Run Roboflow detection
            result = self.detection_model.predict(
                temp_path,
                confidence=self.confidence_threshold,
                overlap=self.overlap_threshold
            ).json()
            
            # Parse predictions
            occupied_count = 0
            empty_count = 0
            slots = []
            
            for idx, prediction in enumerate(result.get('predictions', [])):
                predicted_class = prediction['class']
                confidence = prediction['confidence']
                
                # Extract bounding box (convert from center to corners)
                x = int(prediction['x'])
                y = int(prediction['y'])
                width = int(prediction['width'])
                height = int(prediction['height'])
                
                x1 = x - width // 2
                y1 = y - height // 2
                x2 = x + width // 2
                y2 = y + height // 2
                
                # Count slots
                if predicted_class == 'occupied':
                    occupied_count += 1
                elif predicted_class == 'empty':
                    empty_count += 1
                
                slots.append(ParkingSlotDetection(
                    slot_id=idx + 1,
                    status=predicted_class,
                    confidence=confidence,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                ))
            
            total_slots = occupied_count + empty_count
            occupancy_rate = occupied_count / total_slots if total_slots > 0 else 0.0
            processing_time = (time.time() - start_time) * 1000
            
            logger.debug(f"Detected {total_slots} slots ({occupied_count} occupied, {empty_count} empty) in {processing_time:.2f}ms")
            
            return ParkingSlotDetectionResult(
                parking_lot_id=parking_lot_id,
                camera_id=camera_id,
                total_slots=total_slots,
                occupied=occupied_count,
                empty=empty_count,
                occupancy_rate=occupancy_rate,
                slots=slots,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Parking slot detection failed: {e}")
            # Return empty result on error
            return ParkingSlotDetectionResult(
                parking_lot_id=parking_lot_id,
                camera_id=camera_id,
                total_slots=0,
                occupied=0,
                empty=0,
                occupancy_rate=0.0,
                slots=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

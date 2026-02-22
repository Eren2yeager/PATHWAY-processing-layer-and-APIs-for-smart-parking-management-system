"""
License Plate Detection Model
Integrates Roboflow + EasyOCR for license plate detection and recognition
"""

from roboflow import Roboflow
import easyocr
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import re
import time
from typing import Dict, List, Optional, Tuple
from io import BytesIO

from config.settings import settings
from utils.logger import logger
from schemas.detection_result import LicensePlateDetection, BoundingBox


class LicensePlateDetectorModel:
    """License plate detection and OCR model using Roboflow + EasyOCR"""
    
    def __init__(self):
        """Initialize Roboflow and EasyOCR models"""
        self._init_roboflow()
        self._init_easyocr()
        
        # Performance tracking
        self.api_call_times = []
        self.max_tracked_times = 20
        
        logger.info("License Plate Detector initialized successfully")
    
    def _init_roboflow(self):
        """Initialize Roboflow license plate detection model"""
        try:
            rf = Roboflow(api_key=settings.roboflow_api_key)
            
            # Use workspace() without parameter if workspace is empty
            if settings.roboflow_workspace:
                project = rf.workspace(settings.roboflow_workspace).project(
                    settings.roboflow_license_plate_project
                )
            else:
                project = rf.workspace().project(settings.roboflow_license_plate_project)
            
            self.detection_model = project.version(settings.roboflow_license_plate_version).model
            
            # Convert confidence threshold (already 0-100 from .env)
            self.confidence_threshold = int(settings.plate_detection_confidence)
            self.overlap_threshold = 30
            
            logger.info(f"Roboflow license plate detector loaded (confidence: {self.confidence_threshold}%)")
        except Exception as e:
            logger.error(f"Failed to initialize Roboflow: {e}")
            logger.warning("License plate detector will not be available")
            self.detection_model = None
    
    def _init_easyocr(self):
        """Initialize EasyOCR reader"""
        try:
            logger.info("Loading EasyOCR...")
            self.ocr_reader = easyocr.Reader(['en'], gpu=True)
            logger.info("EasyOCR loaded successfully (GPU enabled)")
        except Exception as e:
            logger.warning(f"EasyOCR GPU failed, falling back to CPU: {e}")
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
            logger.info("EasyOCR loaded successfully (CPU mode)")
    
    def detect_and_recognize(
        self,
        image: np.ndarray,
        camera_id: str,
        parking_lot_id: str
    ) -> List[LicensePlateDetection]:
        """
        Detect license plates and recognize text
        
        Args:
            image: OpenCV image (numpy array)
            camera_id: Camera identifier
            parking_lot_id: Parking lot identifier
            
        Returns:
            List of license plate detections with recognized text
        """
        start_time = time.time()
        
        try:
            # Step 1: Detect license plate regions
            detections = self._detect_plates(image)
            
            if not detections:
                return []
            
            # Step 2: Crop and recognize each plate
            results = []
            for detection in detections:
                bbox = detection['bbox']
                confidence = detection['confidence']
                
                # Crop plate region
                cropped_plate = self._crop_region(image, bbox)
                
                # Run OCR
                ocr_result = self._recognize_text(cropped_plate)
                
                if ocr_result and ocr_result['text']:
                    results.append(LicensePlateDetection(
                        plate_number=ocr_result['text'],
                        confidence=min(confidence, ocr_result['confidence']),  # Use minimum of both confidences
                        bbox=BoundingBox(**bbox),
                        camera_id=camera_id,
                        parking_lot_id=parking_lot_id,
                        processing_time_ms=(time.time() - start_time) * 1000
                    ))
            
            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"Detected {len(results)} plates in {processing_time:.2f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"License plate detection failed: {e}")
            return []
    
    def _detect_plates(self, image: np.ndarray) -> List[Dict]:
        """
        Detect license plate regions using Roboflow
        
        Args:
            image: OpenCV image
            
        Returns:
            List of detection dictionaries with bbox and confidence
        """
        api_start = time.time()
        temp_path = None
        
        try:
            # Convert to PIL Image and resize for faster API calls
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Resize to max 640px for faster processing
            max_dimension = 640
            scale_factor = 1.0
            if max(pil_image.size) > max_dimension:
                scale_factor = max_dimension / max(pil_image.size)
                new_size = (int(pil_image.width * scale_factor), int(pil_image.height * scale_factor))
                pil_image = pil_image.resize(new_size, Image.LANCZOS)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name
                pil_image.save(temp_path, quality=75)
            
            # Run Roboflow detection
            result = self.detection_model.predict(
                temp_path,
                confidence=self.confidence_threshold,
                overlap=self.overlap_threshold
            ).json()
            
            # Track API time
            api_time = time.time() - api_start
            self.api_call_times.append(api_time)
            if len(self.api_call_times) > self.max_tracked_times:
                self.api_call_times.pop(0)
            
            # Parse predictions
            detections = []
            for prediction in result.get('predictions', []):
                # Convert from center coordinates to corner coordinates
                x = int(prediction['x'] / scale_factor)
                y = int(prediction['y'] / scale_factor)
                width = int(prediction['width'] / scale_factor)
                height = int(prediction['height'] / scale_factor)
                
                x1 = x - width // 2
                y1 = y - height // 2
                x2 = x + width // 2
                y2 = y + height // 2
                
                detections.append({
                    'confidence': prediction['confidence'],
                    'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
                })
            
            return detections
            
        except Exception as e:
            logger.error(f"Roboflow detection failed: {e}")
            return []
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def _crop_region(self, image: np.ndarray, bbox: Dict) -> np.ndarray:
        """
        Crop region from image with padding
        
        Args:
            image: OpenCV image
            bbox: Bounding box dict with x1, y1, x2, y2
            
        Returns:
            Cropped image region
        """
        height, width = image.shape[:2]
        
        # Add 10% padding for better OCR
        x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
        padding_x = int((x2 - x1) * 0.1)
        padding_y = int((y2 - y1) * 0.1)
        
        x1 = max(0, x1 - padding_x)
        y1 = max(0, y1 - padding_y)
        x2 = min(width, x2 + padding_x)
        y2 = min(height, y2 + padding_y)
        
        cropped = image[y1:y2, x1:x2].copy()
        
        # Ensure minimum size for OCR
        crop_height, crop_width = cropped.shape[:2]
        if crop_height < 30 or crop_width < 80:
            scale = max(30 / crop_height, 80 / crop_width)
            new_width = int(crop_width * scale)
            new_height = int(crop_height * scale)
            cropped = cv2.resize(cropped, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return cropped
    
    def _recognize_text(self, cropped_plate: np.ndarray) -> Optional[Dict]:
        """
        Recognize text from cropped license plate using EasyOCR
        
        Args:
            cropped_plate: Cropped plate image
            
        Returns:
            Dict with text, raw_text, and confidence, or None if no text found
        """
        try:
            results = self.ocr_reader.readtext(cropped_plate)
            
            if not results:
                return None
            
            # Collect valid results (at least 3 alphanumeric characters)
            all_texts = []
            for (bbox, text, confidence) in results:
                cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                if len(cleaned) >= 3:
                    all_texts.append({
                        'text': cleaned,
                        'raw': text,
                        'confidence': confidence
                    })
            
            if not all_texts:
                return None
            
            # Get best result by confidence
            best = max(all_texts, key=lambda x: x['confidence'])
            
            # If multiple results, try combining them
            if len(all_texts) > 1:
                combined_text = ''.join([t['text'] for t in all_texts])
                combined_raw = ' '.join([t['raw'] for t in all_texts])
                avg_conf = sum([t['confidence'] for t in all_texts]) / len(all_texts)
                
                if len(combined_text) > len(best['text']) and avg_conf > 0.3:
                    best = {
                        'text': combined_text,
                        'raw': combined_raw,
                        'confidence': avg_conf
                    }
            
            return {
                'text': best['text'],
                'raw_text': best['raw'],
                'confidence': best['confidence']
            }
            
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None
    
    def get_avg_api_time(self) -> float:
        """Get average API call time in milliseconds"""
        if not self.api_call_times:
            return 0.0
        return sum(self.api_call_times) / len(self.api_call_times) * 1000

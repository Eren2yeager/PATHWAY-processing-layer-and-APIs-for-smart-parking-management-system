import cv2
import numpy as np
import base64
from typing import Tuple, Optional
from PIL import Image
import io


class FrameProcessor:
    """Utility class for frame preprocessing and manipulation"""
    
    @staticmethod
    def decode_base64_image(base64_string: str) -> np.ndarray:
        """
        Decode base64 string to OpenCV image
        
        Args:
            base64_string: Base64 encoded image string
            
        Returns:
            OpenCV image (numpy array)
        """
        if not base64_string:
            raise ValueError("Empty base64 string provided")
        
        # Remove data URL prefix if present
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        
        # Decode base64
        try:
            img_data = base64.b64decode(base64_string)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 string: {e}")
        
        if not img_data:
            raise ValueError("Decoded image data is empty")
        
        # Convert to PIL Image
        try:
            pil_image = Image.open(io.BytesIO(img_data))
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert to OpenCV format (BGR)
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            return opencv_image
        except Exception as e:
            raise ValueError(f"Failed to convert image data to OpenCV format: {e}")
    
    @staticmethod
    def encode_image_to_base64(image: np.ndarray) -> str:
        """
        Encode OpenCV image to base64 string
        
        Args:
            image: OpenCV image (numpy array)
            
        Returns:
            Base64 encoded string
        """
        # Encode image to JPEG
        _, buffer = cv2.imencode('.jpg', image)
        
        # Convert to base64
        base64_string = base64.b64encode(buffer).decode('utf-8')
        
        return base64_string
    
    @staticmethod
    def resize_image(image: np.ndarray, max_width: int = 1280, max_height: int = 720) -> np.ndarray:
        """
        Resize image while maintaining aspect ratio
        
        Args:
            image: OpenCV image
            max_width: Maximum width
            max_height: Maximum height
            
        Returns:
            Resized image
        """
        height, width = image.shape[:2]
        
        # Calculate scaling factor
        scale = min(max_width / width, max_height / height, 1.0)
        
        if scale < 1.0:
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return image
    
    @staticmethod
    def preprocess_for_detection(image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better detection results
        
        Args:
            image: OpenCV image
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale for better contrast
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Convert back to BGR
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        
        return enhanced_bgr
    
    @staticmethod
    def draw_bounding_box(
        image: np.ndarray,
        bbox: dict,
        label: str,
        confidence: float,
        color: Tuple[int, int, int] = (0, 255, 0)
    ) -> np.ndarray:
        """
        Draw bounding box with label on image
        
        Args:
            image: OpenCV image
            bbox: Bounding box dict with x1, y1, x2, y2
            label: Label text
            confidence: Detection confidence
            color: Box color (BGR)
            
        Returns:
            Image with bounding box drawn
        """
        x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
        
        # Draw rectangle
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        
        # Prepare label text
        text = f"{label} ({confidence:.2f})"
        
        # Get text size
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        
        # Draw label background
        cv2.rectangle(
            image,
            (x1, y1 - text_height - baseline - 5),
            (x1 + text_width, y1),
            color,
            -1
        )
        
        # Draw label text
        cv2.putText(
            image,
            text,
            (x1, y1 - baseline - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        
        return image
    
    @staticmethod
    def crop_region(image: np.ndarray, bbox: dict) -> np.ndarray:
        """
        Crop region from image based on bounding box
        
        Args:
            image: OpenCV image
            bbox: Bounding box dict with x1, y1, x2, y2
            
        Returns:
            Cropped image region
        """
        x1, y1, x2, y2 = int(bbox['x1']), int(bbox['y1']), int(bbox['x2']), int(bbox['y2'])
        
        # Ensure coordinates are within image bounds
        height, width = image.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)
        
        return image[y1:y2, x1:x2]

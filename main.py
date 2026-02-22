"""
Pathway-based Smart Parking Management System
Main entry point for the AI/ML processing layer
"""

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from typing import Dict, List
import base64
import cv2
import numpy as np
import json

from config.settings import settings
from utils.logger import logger
from utils.frame_processor import FrameProcessor
from models.license_plate_detector import LicensePlateDetectorModel
from models.parking_slot_detector import ParkingSlotDetectorModel
from models.vehicle_detector import VehicleDetectorModel
from schemas.camera_frame import CameraFrameSchema, FrameType
from schemas.detection_result import DetectionResult

from pathway_pipeline import get_pathway_pipeline

# Global model instances
license_plate_detector = None
parking_slot_detector = None
vehicle_detector = None
frame_processor = FrameProcessor()

# Pathway pipeline instance
pathway_pipeline = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"Client connected to {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)
        logger.info(f"Client disconnected from {channel}")
    
    async def broadcast(self, message: dict, channel: str):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    # Startup
    global license_plate_detector, parking_slot_detector, vehicle_detector, pathway_pipeline
    
    logger.info("Starting Pathway Smart Parking System...")
    logger.info(f"Host: {settings.pathway_host}:{settings.pathway_port}")
    
    # Initialize AI models
    try:
        logger.info("Loading AI models...")
        license_plate_detector = LicensePlateDetectorModel()
        parking_slot_detector = ParkingSlotDetectorModel()
        vehicle_detector = VehicleDetectorModel()
        logger.info("Models initialization complete!")
        
        # Check which models are available
        models_status = []
        if license_plate_detector and hasattr(license_plate_detector, 'detection_model') and license_plate_detector.detection_model:
            models_status.append("✓ License Plate Detector")
        else:
            models_status.append("✗ License Plate Detector (unavailable)")
            
        if parking_slot_detector and hasattr(parking_slot_detector, 'detection_model') and parking_slot_detector.detection_model:
            models_status.append("✓ Parking Slot Detector")
        else:
            models_status.append("✗ Parking Slot Detector (unavailable)")
            
        models_status.append("✓ Vehicle Detector (placeholder)")
        
        for status in models_status:
            logger.info(status)
            
    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        logger.warning("Server will start but some features may not work")
        # Don't raise - allow server to start anyway
    
    # Initialize Pathway stateful processing pipeline
    try:
        logger.info("Initializing Pathway stateful processing pipeline...")
        pathway_pipeline = get_pathway_pipeline()
        await pathway_pipeline.start()
        logger.info("✓ Pathway pipeline started")
    except Exception as e:
        logger.error(f"Failed to start Pathway pipeline: {e}")
        logger.warning("Continuing without Pathway stateful processing")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Pathway Smart Parking System...")
    if pathway_pipeline:
        await pathway_pipeline.stop()


# Create FastAPI app
app = FastAPI(
    title="Pathway Smart Parking System",
    description="AI/ML processing layer for smart parking management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint - for Next.js and load balancers"""
    gate_count = len(manager.active_connections.get("gate-monitor", []))
    lot_count = len(manager.active_connections.get("lot-monitor", []))
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "backend": "pathway",
        "models": {
            "license_plate": license_plate_detector is not None,
            "parking_slot": parking_slot_detector is not None,
            "vehicle": vehicle_detector is not None
        },
        "active_streams": gate_count + lot_count,
        "gate_monitor_connections": gate_count,
        "lot_monitor_connections": lot_count,
    }


@app.post("/api/recognize-plate")
async def recognize_plate(file: UploadFile = File(...)):
    """
    Detect and recognize license plates in uploaded image
    Compatible with existing python-work API
    """
    try:
        # Read image
        image_bytes = await file.read()
        image = frame_processor.decode_base64_image(
            base64.b64encode(image_bytes).decode('utf-8')
        )
        
        # Detect and recognize plates
        detections = license_plate_detector.detect_and_recognize(
            image,
            camera_id="upload",
            parking_lot_id="unknown"
        )
        
        # Format response to match python-work format
        plates = []
        for detection in detections:
            plates.append({
                "plate_number": detection.plate_number,
                "confidence": detection.confidence,
                "bbox": {
                    "x1": detection.bbox.x1,
                    "y1": detection.bbox.y1,
                    "x2": detection.bbox.x2,
                    "y2": detection.bbox.y2
                }
            })
        
        return {
            "success": True,
            "plates_detected": len(plates),
            "plates_recognized": len(plates),
            "plates": plates
        }
    
    except Exception as e:
        logger.error(f"License plate recognition failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-parking-slots")
async def detect_parking_slots(file: UploadFile = File(...)):
    """
    Detect parking slot occupancy in uploaded image
    Compatible with existing python-work API
    """
    try:
        # Read image
        image_bytes = await file.read()
        image = frame_processor.decode_base64_image(
            base64.b64encode(image_bytes).decode('utf-8')
        )
        
        # Detect parking slots
        result = parking_slot_detector.detect_slots(
            image,
            camera_id="upload",
            parking_lot_id="unknown"
        )
        
        # Format response to match python-work format
        slots = []
        for slot in result.slots:
            slots.append({
                "slot_id": slot.slot_id,
                "status": slot.status,
                "confidence": slot.confidence,
                "bbox": {
                    "x1": slot.bbox.x1,
                    "y1": slot.bbox.y1,
                    "x2": slot.bbox.x2,
                    "y2": slot.bbox.y2
                }
            })
        
        return {
            "success": True,
            "total_slots": result.total_slots,
            "occupied": result.occupied,
            "empty": result.empty,
            "occupancy_rate": result.occupancy_rate,
            "slots": slots
        }
    
    except Exception as e:
        logger.error(f"Parking slot detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/capacity/current/{parking_lot_id}")
async def get_capacity_current(parking_lot_id: str):
    """Get current capacity state from Pathway (real-time aggregated state)."""
    if not pathway_pipeline:
        raise HTTPException(status_code=503, detail="Pathway pipeline not available")
    data = pathway_pipeline.get_current_capacity(parking_lot_id)
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No capacity data for parking_lot_id={parking_lot_id}"}
        )
    from datetime import datetime as dt
    last_ts = data.get("last_updated")
    last_updated = dt.utcfromtimestamp(last_ts / 1000).isoformat() + "Z" if isinstance(last_ts, (int, float)) else str(last_ts)
    return {
        "parking_lot_id": data["parking_lot_id"],
        "total_slots": data["total_slots"],
        "occupied": data["occupied"],
        "empty": data["empty"],
        "occupancy_rate": data["occupancy_rate"],
        "last_updated": last_updated,
        "slots": data.get("slots", []),
    }


@app.post("/api/process-frame")
async def process_frame(request: Request):
    """
    Process a single frame (gate or lot). Accepts JSON: image (base64), camera_id, parking_lot_id, type ('gate'|'lot').
    """
    try:
        body = await request.json()
        image_b64 = body.get("image", "")
        camera_id = body.get("camera_id", "upload")
        parking_lot_id = body.get("parking_lot_id", "unknown")
        frame_type = (body.get("type") or "gate").lower()
        if not image_b64:
            raise HTTPException(status_code=400, detail="Missing 'image' (base64)")
        image = frame_processor.decode_base64_image(image_b64)
        if frame_type == "gate":
            detections = license_plate_detector.detect_and_recognize(image, camera_id=camera_id, parking_lot_id=parking_lot_id)
            detections_out = [
                {
                    "plate_number": d.plate_number,
                    "confidence": d.confidence,
                    "bbox": {"x1": d.bbox.x1, "y1": d.bbox.y1, "x2": d.bbox.x2, "y2": d.bbox.y2},
                }
                for d in detections
            ]
            return {"detections": detections_out, "type": "gate", "timestamp": datetime.utcnow().isoformat()}
        else:
            result = parking_slot_detector.detect_slots(image, camera_id=camera_id, parking_lot_id=parking_lot_id)
            slots = [
                {"slot_id": s.slot_id, "status": s.status, "confidence": s.confidence, "bbox": {"x1": s.bbox.x1, "y1": s.bbox.y1, "x2": s.bbox.x2, "y2": s.bbox.y2}}
                for s in result.slots
            ]
            return {
                "total_slots": result.total_slots,
                "occupied": result.occupied,
                "empty": result.empty,
                "occupancy_rate": result.occupancy_rate,
                "slots": slots,
                "type": "lot",
                "timestamp": result.timestamp.isoformat(),
                "processing_time_ms": result.processing_time_ms,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"process-frame error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-vehicle")
async def detect_vehicle(file: UploadFile = File(...)):
    """
    Detect vehicles in uploaded image
    Compatible with existing python-work API
    """
    try:
        # Read image
        image_bytes = await file.read()
        image = frame_processor.decode_base64_image(
            base64.b64encode(image_bytes).decode('utf-8')
        )
        
        # Detect vehicles
        detections = vehicle_detector.detect_vehicles(
            image,
            camera_id="upload",
            parking_lot_id="unknown"
        )
        
        return {
            "success": True,
            "vehicles_detected": len(detections),
            "vehicles": [
                {
                    "vehicle_type": d.vehicle_type,
                    "confidence": d.confidence,
                    "bbox": {
                        "x1": d.bbox.x1,
                        "y1": d.bbox.y1,
                        "x2": d.bbox.x2,
                        "y2": d.bbox.y2
                    }
                }
                for d in detections
            ]
        }
    
    except Exception as e:
        logger.error(f"Vehicle detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/gate-monitor")
async def gate_monitor_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time license plate detection
    Compatible with existing python-work WebSocket
    """
    await manager.connect(websocket, "gate-monitor")
    
    try:
        while True:
            # Receive frame data
            data = await websocket.receive_json()
            
            # Support both 'data' and 'image' fields for compatibility
            image_data = data.get("data") or data.get("image", "")
            if not image_data:
                logger.warning("Received empty image data")
                continue
            
            try:
                # Decode image
                image = frame_processor.decode_base64_image(image_data)
                
                # Extract metadata - support multiple field names
                camera_id = (data.get("camera_id") or 
                           data.get("gate_id") or 
                           data.get("lot_id") or 
                           "unknown")
                parking_lot_id = (data.get("parking_lot_id") or 
                                data.get("parkingLotId") or 
                                data.get("gate_id") or 
                                "unknown")
                
                # Detect and recognize plates
                detections = license_plate_detector.detect_and_recognize(
                    image,
                    camera_id=camera_id,
                    parking_lot_id=parking_lot_id
                )
                
                # Feed detections into Pathway pipeline for stateful processing
                if pathway_pipeline:
                    for detection in detections:
                        # Determine event type (entry/exit) - default to entry
                        event_type = data.get("event_type", "entry")
                        
                        # Add to Pathway pipeline
                        pathway_pipeline.add_vehicle_detection(
                            plate_number=detection.plate_number,
                            parking_lot_id=parking_lot_id,
                            camera_id=camera_id,
                            event_type=event_type,
                            confidence=detection.confidence,
                            timestamp=int(detection.timestamp.timestamp() * 1000)
                        )
                
                # Send results back to frontend (real-time feedback)
                # Check if WebSocket is still open before sending
                if websocket.client_state.name == "CONNECTED":
                    for detection in detections:
                        await websocket.send_json({
                            "event_type": "plate_detected",
                            "plate_number": detection.plate_number,
                            "confidence": detection.confidence,
                            "timestamp": detection.timestamp.isoformat(),
                            "parking_lot_id": parking_lot_id,
                            "camera_id": camera_id,
                            "bbox": {
                                "x1": detection.bbox.x1,
                                "y1": detection.bbox.y1,
                                "x2": detection.bbox.x2,
                                "y2": detection.bbox.y2
                            }
                        })
                        
            except Exception as decode_error:
                logger.error(f"Failed to process frame: {decode_error}")
                # Only send error if WebSocket is still connected
                try:
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({
                            "event_type": "error",
                            "error": str(decode_error)
                        })
                except:
                    # WebSocket already closed, just log
                    pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "gate-monitor")
    except Exception as e:
        logger.error(f"Gate monitor WebSocket error: {e}")
        manager.disconnect(websocket, "gate-monitor")


@app.websocket("/ws/lot-monitor")
async def lot_monitor_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time parking capacity monitoring
    Compatible with existing python-work WebSocket
    """
    await manager.connect(websocket, "lot-monitor")
    
    try:
        while True:
            # Receive frame data
            data = await websocket.receive_json()
            
            # Support both 'data' and 'image' fields for compatibility
            image_data = data.get("data") or data.get("image", "")
            if not image_data:
                logger.warning("Received empty image data")
                continue
            
            try:
                # Decode image
                image = frame_processor.decode_base64_image(image_data)
                
                # Extract metadata - support multiple field names
                camera_id = (data.get("camera_id") or 
                           data.get("gate_id") or 
                           data.get("lot_id") or 
                           "unknown")
                parking_lot_id = (data.get("parking_lot_id") or 
                                data.get("parkingLotId") or 
                                data.get("lot_id") or 
                                "unknown")
                
                # Detect parking slots
                result = parking_slot_detector.detect_slots(
                    image,
                    camera_id=camera_id,
                    parking_lot_id=parking_lot_id
                )
                
                # Feed slot detections into Pathway pipeline for stateful aggregation
                if pathway_pipeline:
                    timestamp = int(result.timestamp.timestamp() * 1000)
                    for slot in result.slots:
                        pathway_pipeline.add_capacity_update(
                            parking_lot_id=parking_lot_id,
                            camera_id=camera_id,
                            slot_id=slot.slot_id,
                            status=slot.status,
                            confidence=slot.confidence,
                            timestamp=timestamp
                        )
                
                # Format slots for frontend
                slots = []
                for slot in result.slots:
                    slots.append({
                        "slot_id": slot.slot_id,
                        "status": slot.status,
                        "confidence": slot.confidence,
                        "bbox": {
                            "x1": slot.bbox.x1,
                            "y1": slot.bbox.y1,
                            "x2": slot.bbox.x2,
                            "y2": slot.bbox.y2
                        }
                    })
                
                # Send results back to frontend (real-time feedback)
                # Check if WebSocket is still open before sending
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_json({
                        "event_type": "capacity_update",
                        "parking_lot_id": parking_lot_id,
                        "camera_id": camera_id,
                        "total_slots": result.total_slots,
                        "occupied": result.occupied,
                        "empty": result.empty,
                        "occupancy_rate": result.occupancy_rate,
                        "slots": slots,
                        "timestamp": result.timestamp.isoformat(),
                        "processing_time_ms": result.processing_time_ms
                    })
                    
            except Exception as decode_error:
                logger.error(f"Failed to process frame: {decode_error}")
                # Only send error if WebSocket is still connected
                try:
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_json({
                            "event_type": "error",
                            "error": str(decode_error)
                        })
                except:
                    # WebSocket already closed, just log
                    pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, "lot-monitor")
    except Exception as e:
        logger.error(f"Lot monitor WebSocket error: {e}")
        manager.disconnect(websocket, "lot-monitor")


@app.websocket("/ws/webrtc-signaling")
async def webrtc_signaling_endpoint(websocket: WebSocket):
    """
    WebRTC signaling server for camera streaming
    Handles offer/answer/ICE candidate exchange between camera and backend
    Compatible with existing python-work WebSocket
    """
    await websocket.accept()
    client_id = id(websocket)

    # Store connection in a simple list (not using manager channels for signaling)
    if not hasattr(app.state, 'webrtc_connections'):
        app.state.webrtc_connections = []

    app.state.webrtc_connections.append(websocket)

    try:
        await websocket.send_json({
            "type": "connected",
            "clientId": client_id,
            "message": "WebRTC signaling server ready"
        })

        logger.info(f"WebRTC client connected: {client_id}")

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            logger.debug(f"Signaling [{client_id}]: {msg_type}")

            # Broadcast signaling messages to all other clients
            for connection in app.state.webrtc_connections:
                if connection != websocket:
                    try:
                        await connection.send_text(data)
                    except Exception as e:
                        logger.error(f"Failed to broadcast to client: {e}")

    except WebSocketDisconnect:
        if websocket in app.state.webrtc_connections:
            app.state.webrtc_connections.remove(websocket)
        logger.info(f"WebRTC client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebRTC signaling error: {e}")
        if websocket in app.state.webrtc_connections:
            app.state.webrtc_connections.remove(websocket)



if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.pathway_host,
        port=settings.pathway_port,
        reload=False,
        log_level=settings.pathway_log_level.lower()
    )

"""
Pathway Input Connectors for Camera Streams
Uses pw.io.python.ConnectorSubject to bridge WebSocket data into Pathway tables.

WebSocket handlers call subject.next(...) to push detection events.
Pathway engine reads them via pw.io.python.read() in the pipeline.
"""

import pathway as pw
import time
import threading
from typing import Optional

from config.settings import settings
from utils.logger import logger


# ── Pathway Schemas ────────────────────────────────────────────

class VehicleEventSchema(pw.Schema):
    """Schema for vehicle detection events flowing through Pathway."""
    plate_number: str
    timestamp: int          # Unix timestamp in milliseconds
    parking_lot_id: str
    camera_id: str
    event_type: str         # "entry" or "exit"
    confidence: float


class CapacityEventSchema(pw.Schema):
    """Schema for individual slot detection events flowing through Pathway."""
    parking_lot_id: str
    camera_id: str
    slot_id: int
    status: str             # "occupied" or "empty"
    confidence: float
    timestamp: int          # Unix timestamp in milliseconds


# ── Pathway ConnectorSubjects (Input Connectors) ──────────────

class VehicleDetectionSubject(pw.io.python.ConnectorSubject):
    """
    ConnectorSubject that receives vehicle detection events from WebSocket
    handlers and feeds them into a Pathway table.

    Usage:
        subject = VehicleDetectionSubject()
        table = pw.io.python.read(subject, schema=VehicleEventSchema)
        # In WebSocket handler:
        subject.next(plate_number="DL01AB1234", ...)
    """

    _running: bool

    def run(self) -> None:
        """
        Called by Pathway engine in a separate thread.
        Keeps the connector alive — data is pushed externally via next().
        """
        self._running = True
        logger.info("[VehicleDetectionSubject] Input connector started, waiting for detections...")
        while self._running:
            time.sleep(0.5)
        logger.info("[VehicleDetectionSubject] Input connector stopped.")

    def on_stop(self) -> None:
        """Called by Pathway when shutting down."""
        self._running = False

    def push_detection(
        self,
        plate_number: str,
        parking_lot_id: str,
        camera_id: str,
        event_type: str,
        confidence: float,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a vehicle detection event into the Pathway pipeline.
        Called from FastAPI WebSocket handlers.
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        self.next(
            plate_number=plate_number,
            timestamp=timestamp,
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            event_type=event_type,
            confidence=confidence,
        )
        logger.debug(
            f"[VehicleDetectionSubject] Pushed: plate={plate_number}, "
            f"lot={parking_lot_id}, type={event_type}, conf={confidence:.2f}"
        )


class CapacityUpdateSubject(pw.io.python.ConnectorSubject):
    """
    ConnectorSubject that receives parking slot detection events from WebSocket
    handlers and feeds them into a Pathway table.

    Usage:
        subject = CapacityUpdateSubject()
        table = pw.io.python.read(subject, schema=CapacityEventSchema)
        # In WebSocket handler:
        subject.push_slot_update(parking_lot_id="lot1", slot_id=1, status="occupied", ...)
    """

    _running: bool

    def run(self) -> None:
        """Keeps the connector alive — data is pushed externally via next()."""
        self._running = True
        logger.info("[CapacityUpdateSubject] Input connector started, waiting for capacity events...")
        while self._running:
            time.sleep(0.5)
        logger.info("[CapacityUpdateSubject] Input connector stopped.")

    def on_stop(self) -> None:
        self._running = False

    def push_slot_update(
        self,
        parking_lot_id: str,
        camera_id: str,
        slot_id: int,
        status: str,
        confidence: float,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a single slot detection into the Pathway pipeline.
        Called from FastAPI WebSocket handlers (once per slot per frame).
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        self.next(
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            slot_id=slot_id,
            status=status,
            confidence=confidence,
            timestamp=timestamp,
        )

    def push_capacity_batch(
        self,
        parking_lot_id: str,
        camera_id: str,
        slots: list,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a batch of slot detections (one frame's worth).
        Convenience method that calls push_slot_update for each slot.
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        for slot in slots:
            self.push_slot_update(
                parking_lot_id=parking_lot_id,
                camera_id=camera_id,
                slot_id=slot.get("slot_id", slot.get("slotId", 0)),
                status=slot.get("status", "empty"),
                confidence=slot.get("confidence", 0.0),
                timestamp=timestamp,
            )

        logger.debug(
            f"[CapacityUpdateSubject] Pushed batch: lot={parking_lot_id}, "
            f"slots={len(slots)}"
        )

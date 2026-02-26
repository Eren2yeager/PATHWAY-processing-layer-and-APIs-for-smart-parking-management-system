"""
Pathway Pipeline Manager
Wires up real Pathway tables, transformations, and IO connectors.

Architecture:
    WebSocket handlers
        → ConnectorSubjects (push data)
            → pw.io.python.read() creates pw.Table
                → transformations (filter, deduplicate, aggregate)
                    → pw.io.python.write() triggers ConnectorObservers
                        → HTTP webhooks to Next.js

    pw.run() drives the entire computation in a background thread.
"""

import pathway as pw
import threading
import time
from typing import Optional

from config.settings import settings
from utils.logger import logger

# Input connectors
from connectors.camera_input import (
    VehicleDetectionSubject,
    CapacityUpdateSubject,
    VehicleEventSchema,
    CapacityEventSchema,
)

# Output observers
from connectors.nextjs_output import (
    VehicleEventObserver,
    CapacityEventObserver,
    set_slot_store_data,
    set_slot_store_batch,
)

# Transformations (these already contain real Pathway code!)
from transformations.vehicle_tracking import VehicleTracker
from transformations.capacity_aggregation import CapacityAggregator
from transformations.duplicate_filter import DuplicateFilter


class PathwayPipelineManager:
    """
    Orchestrates the real Pathway stream processing pipeline.

    Replaces the old dict-based fake pipeline with:
    - pw.io.python.read() to ingest data from WebSocket handlers
    - Pathway transformations for dedup, tracking, aggregation
    - pw.io.python.write() to output results to Next.js webhooks
    - pw.run() in a background thread to drive computation
    """

    def __init__(self):
        # Input subjects — WebSocket handlers push data into these
        self.vehicle_subject = VehicleDetectionSubject()
        self.capacity_subject = CapacityUpdateSubject()

        # Transformations
        self.vehicle_tracker = VehicleTracker()
        self.capacity_aggregator = CapacityAggregator()
        self.duplicate_filter = DuplicateFilter(
            window_seconds=settings.duplicate_detection_window
        )

        # Output observers
        self.vehicle_observer = VehicleEventObserver()
        self.capacity_observer = CapacityEventObserver()

        # Pipeline state
        self._pipeline_thread: Optional[threading.Thread] = None
        self._is_running = False

        logger.info("[PathwayPipeline] Manager initialized")

    def build_pipeline(self) -> None:
        """
        Build the Pathway dataflow graph.
        Must be called BEFORE pw.run().
        """
        logger.info("[PathwayPipeline] Building Pathway dataflow graph...")

        # ── Step 1: Create input tables from ConnectorSubjects ──
        vehicle_events_table = pw.io.python.read(
            self.vehicle_subject,
            schema=VehicleEventSchema,
            autocommit_duration_ms=500,     # commit every 500ms for real-time feel
        )

        capacity_events_table = pw.io.python.read(
            self.capacity_subject,
            schema=CapacityEventSchema,
            autocommit_duration_ms=500,
        )

        logger.info("[PathwayPipeline] ✅ Input tables created")

        # ── Step 2: Vehicle processing pipeline ──
        # Filter low-confidence detections (settings are percentages 0-100, convert to 0-1)
        high_conf_vehicles = self.duplicate_filter.filter_low_confidence_detections(
            vehicle_events_table,
            min_confidence=settings.plate_detection_confidence / 100.0,
        )

        # Deduplicate plates within time window
        unique_vehicles = self.duplicate_filter.filter_duplicate_plates(
            high_conf_vehicles,
            window_seconds=settings.duplicate_detection_window,
        )

        # Output: Forward unique vehicle events to Next.js
        pw.io.python.write(unique_vehicles, self.vehicle_observer)

        logger.info("[PathwayPipeline] ✅ Vehicle pipeline built (filter → dedup → webhook)")

        # ── Step 3: Capacity processing pipeline ──
        # Filter low-confidence slot detections
        high_conf_capacity = self.duplicate_filter.filter_low_confidence_detections(
            capacity_events_table,
            min_confidence=settings.parking_slot_confidence / 100.0,
        )

        # Aggregate slots into per-lot capacity metrics
        capacity_metrics = self.capacity_aggregator.aggregate_capacity(
            high_conf_capacity
        )

        # Output: Forward aggregated capacity to Next.js
        pw.io.python.write(capacity_metrics, self.capacity_observer)

        logger.info("[PathwayPipeline] ✅ Capacity pipeline built (filter → aggregate → webhook)")

        logger.info("[PathwayPipeline] 🎯 Pathway dataflow graph ready — call start() to run")

    def start(self) -> None:
        """Start the Pathway engine in a background thread."""
        if self._is_running:
            logger.warning("[PathwayPipeline] Already running")
            return

        # Build the dataflow graph first
        self.build_pipeline()

        # Run pw.run() in a background thread (it's blocking)
        self._is_running = True
        self._pipeline_thread = threading.Thread(
            target=self._run_pathway_engine,
            name="pathway-engine",
            daemon=True,
        )
        self._pipeline_thread.start()
        logger.info("[PathwayPipeline] 🚀 Pathway engine started in background thread")

    def _run_pathway_engine(self) -> None:
        """Run the Pathway engine (blocking call)."""
        try:
            logger.info("[PathwayPipeline] pw.run() starting...")
            pw.run(monitoring_level=pw.MonitoringLevel.NONE)
        except Exception as e:
            logger.error(f"[PathwayPipeline] pw.run() error: {e}")
        finally:
            self._is_running = False
            logger.info("[PathwayPipeline] pw.run() exited")

    def stop(self) -> None:
        """Stop the Pathway pipeline."""
        if not self._is_running:
            return

        logger.info("[PathwayPipeline] Stopping pipeline...")
        self._is_running = False

        # Signal the input subjects to stop
        try:
            self.vehicle_subject.close()
        except Exception:
            pass
        try:
            self.capacity_subject.close()
        except Exception:
            pass

        # Wait for the pipeline thread to finish
        if self._pipeline_thread and self._pipeline_thread.is_alive():
            self._pipeline_thread.join(timeout=5)

        logger.info("[PathwayPipeline] Pipeline stopped")

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ── Convenience methods for WebSocket handlers ──

    def add_vehicle_detection(
        self,
        plate_number: str,
        parking_lot_id: str,
        camera_id: str = "unknown",
        event_type: str = "entry",
        confidence: float = 0.0,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a vehicle detection into the Pathway pipeline.
        Called from main.py WebSocket handlers.
        """
        if not self._is_running:
            logger.warning("[PathwayPipeline] Pipeline not running, ignoring detection")
            return

        self.vehicle_subject.push_detection(
            plate_number=plate_number,
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            event_type=event_type,
            confidence=confidence,
            timestamp=timestamp,
        )

    def add_capacity_update(
        self,
        parking_lot_id: str,
        camera_id: str = "unknown",
        slot_id: int = 0,
        status: str = "empty",
        confidence: float = 0.0,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a single slot update into the Pathway pipeline.
        Called from main.py WebSocket handlers.
        """
        if not self._is_running:
            logger.warning("[PathwayPipeline] Pipeline not running, ignoring capacity update")
            return

        # Store slot info in module-level store for the observer
        set_slot_store_data(parking_lot_id, slot_id, status, confidence)

        self.capacity_subject.push_slot_update(
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            slot_id=slot_id,
            status=status,
            confidence=confidence,
            timestamp=timestamp,
        )

    def add_capacity_batch(
        self,
        parking_lot_id: str,
        camera_id: str,
        slots: list,
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Push a batch of slot detections into the Pathway pipeline.
        Called from main.py WebSocket handlers after each lot frame.
        """
        if not self._is_running:
            logger.warning("[PathwayPipeline] Pipeline not running, ignoring capacity batch")
            return

        # Store full slot snapshot in module-level store for the observer
        set_slot_store_batch(parking_lot_id, slots)

        self.capacity_subject.push_capacity_batch(
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            slots=slots,
            timestamp=timestamp,
        )


# ── Singleton factory ─────────────────────────────────────────

_pipeline_instance: PathwayPipelineManager | None = None


def get_pathway_pipeline() -> PathwayPipelineManager:
    """Get or create the singleton PathwayPipelineManager."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = PathwayPipelineManager()
    return _pipeline_instance

"""
Pathway Output Connectors — Forward processed results to Next.js via HTTP webhooks.

Uses:
- NextJSOutputConnector: HTTP client for sending data to Next.js webhooks
- VehicleEventObserver: pw.io.python.ConnectorObserver that reacts to vehicle table changes
- CapacityEventObserver: pw.io.python.ConnectorObserver that reacts to capacity table changes
"""

import pathway as pw
import httpx
import json
from typing import Dict, Any
from config.settings import settings
from utils.logger import logger


# ── HTTP Client ───────────────────────────────────────────────

class NextJSOutputConnector:
    """HTTP client for sending processed data to Next.js webhook endpoints."""

    def __init__(self):
        timeout = httpx.Timeout(settings.nextjs_webhook_timeout_seconds)
        headers = {}
        if settings.pathway_webhook_secret:
            headers["X-Pathway-Secret"] = settings.pathway_webhook_secret
        self.client = httpx.AsyncClient(timeout=timeout, headers=headers)
        self.nextjs_base_url = settings.nextjs_api_url.rstrip("/")

    async def send_vehicle_entry(self, data: Dict[str, Any]) -> bool:
        """Send vehicle entry event to Next.js webhook."""
        url = f"{self.nextjs_base_url}{settings.nextjs_webhook_entry}"
        return await self._send(url, data, "vehicle_entry")

    async def send_vehicle_exit(self, data: Dict[str, Any]) -> bool:
        """Send vehicle exit event to Next.js webhook."""
        url = f"{self.nextjs_base_url}{settings.nextjs_webhook_exit}"
        return await self._send(url, data, "vehicle_exit")

    async def send_capacity_update(self, data: Dict[str, Any]) -> bool:
        """Send capacity update to Next.js webhook."""
        url = f"{self.nextjs_base_url}{settings.nextjs_webhook_capacity}"
        return await self._send(url, data, "capacity_update")

    async def _send(self, url: str, data: Dict[str, Any], event_type: str) -> bool:
        """Send data to a webhook endpoint with error handling."""
        try:
            response = await self.client.post(url, json=data)
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"[NextJSOutput] {event_type} sent successfully to {url}")
                return True
            else:
                logger.warning(
                    f"[NextJSOutput] {event_type} failed: {response.status_code} — {response.text[:200]}"
                )
                return False
        except httpx.ConnectTimeout:
            logger.error(f"[NextJSOutput] Connection timeout sending {event_type} to {url}")
            return False
        except httpx.ConnectError:
            logger.error(f"[NextJSOutput] Connection error sending {event_type} to {url} — is Next.js running?")
            return False
        except Exception as e:
            logger.error(f"[NextJSOutput] Unexpected error sending {event_type}: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# ── Pathway Output Observers ─────────────────────────────────

# ── Sync HTTP client for Pathway observers ────────────────────
# Pathway observers run in Pathway's engine thread (sync context).
# Using sync httpx avoids "Event loop is closed" errors.

_sync_client: httpx.Client | None = None

# Module-level slot store — shared between pipeline manager and observer.
# The pipeline manager writes to it, the observer reads from it.
_capacity_slot_store: dict[str, dict] = {}


def set_slot_store_data(parking_lot_id: str, slot_id: int, status: str, confidence: float):
    """Called by pipeline manager to store individual slot data."""
    if parking_lot_id not in _capacity_slot_store:
        _capacity_slot_store[parking_lot_id] = {}
    _capacity_slot_store[parking_lot_id][slot_id] = {
        "slot_id": slot_id,
        "status": status,
        "confidence": confidence,
    }


def set_slot_store_batch(parking_lot_id: str, slots: list):
    """Called by pipeline manager to store a full batch of slot data."""
    _capacity_slot_store[parking_lot_id] = {
        s.get("slot_id", s.get("slotId", i)): {
            "slot_id": s.get("slot_id", s.get("slotId", i)),
            "status": s.get("status", "empty"),
            "confidence": s.get("confidence", 0.0),
        }
        for i, s in enumerate(slots)
    }


def _get_sync_client() -> httpx.Client:
    """Get or create a sync HTTP client for observer callbacks."""
    global _sync_client
    if _sync_client is None:
        timeout = httpx.Timeout(settings.nextjs_webhook_timeout_seconds)
        headers = {}
        if settings.pathway_webhook_secret:
            headers["X-Pathway-Secret"] = settings.pathway_webhook_secret
        _sync_client = httpx.Client(timeout=timeout, headers=headers)
    return _sync_client


def _sync_send(url: str, data: dict, event_type: str) -> bool:
    """Send data synchronously from Pathway's observer thread."""
    try:
        client = _get_sync_client()
        response = client.post(url, json=data)
        if response.status_code in (200, 201):
            logger.info(f"[NextJSOutput] {event_type} sent successfully to {url}")
            return True
        else:
            logger.warning(f"[NextJSOutput] {event_type} failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"[NextJSOutput] Error sending {event_type}: {e}")
        return False


class VehicleEventObserver(pw.io.python.ConnectorObserver):
    """
    Pathway output observer for vehicle events.
    Receives changes to the vehicle tracking table and forwards them
    to Next.js via HTTP webhooks.
    """

    def on_change(self, key: pw.Pointer, row: dict, time: int, is_addition: bool):
        """Called by Pathway engine when a row is added/removed from the output table."""
        if not is_addition:
            return

        event_type = row.get("event_type", "entry")
        base_url = settings.nextjs_api_url.rstrip("/")

        data = {
            "plate_number": row.get("plate_number", ""),
            "parking_lot_id": row.get("parking_lot_id", ""),
            "camera_id": row.get("camera_id", ""),
            "confidence": row.get("confidence", 0.0),
            "timestamp": row.get("timestamp", 0),
        }

        logger.info(
            f"[VehicleEventObserver] {event_type}: plate={data['plate_number']}, "
            f"lot={data['parking_lot_id']}"
        )

        if event_type == "exit":
            url = f"{base_url}{settings.nextjs_webhook_exit}"
        else:
            url = f"{base_url}{settings.nextjs_webhook_entry}"
        _sync_send(url, data, f"vehicle_{event_type}")

    def on_end(self):
        logger.info("[VehicleEventObserver] Stream ended.")


class CapacityEventObserver(pw.io.python.ConnectorObserver):
    """
    Pathway output observer for capacity aggregation results.
    Receives changes to the capacity table and forwards them
    to Next.js via HTTP webhooks.
    """

    def on_change(self, key: pw.Pointer, row: dict, time: int, is_addition: bool):
        """Called by Pathway engine when capacity metrics change."""
        if not is_addition:
            return

        base_url = settings.nextjs_api_url.rstrip("/")
        url = f"{base_url}{settings.nextjs_webhook_capacity}"

        parking_lot_id = row.get("parking_lot_id", "")

        # Get individual slot data from module-level store
        slot_dict = _capacity_slot_store.get(parking_lot_id, {})
        slots_array = list(slot_dict.values()) if isinstance(slot_dict, dict) else []

        data = {
            "parking_lot_id": parking_lot_id,
            "total_slots": row.get("total_slots", 0),
            "occupied": row.get("occupied", 0),
            "empty": row.get("empty_slots", 0),
            "occupancy_rate": row.get("occupancy_rate", 0.0),
            "slots": slots_array,
            "timestamp": row.get("last_updated", row.get("timestamp", 0)),
        }

        logger.info(
            f"[CapacityEventObserver] lot={parking_lot_id}, "
            f"occupied={data['occupied']}/{data['total_slots']}, "
            f"slots={len(slots_array)}"
        )

        _sync_send(url, data, "capacity_update")

    def on_end(self):
        logger.info("[CapacityEventObserver] Stream ended.")

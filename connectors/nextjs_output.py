"""
Pathway Output Connectors to Next.js
Sends processed data to Next.js webhook endpoints
"""

import pathway as pw
import httpx
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import json

from config.settings import settings
from utils.logger import logger


class NextJSOutputConnector:
    """Output connector that sends Pathway results to Next.js APIs"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.nextjs_base_url = settings.nextjs_api_url
    
    async def send_vehicle_entry(self, data: Dict[str, Any]) -> bool:
        """
        Send vehicle entry event to Next.js
        
        Args:
            data: Vehicle entry data
            
        Returns:
            Success status
        """
        try:
            url = f"{self.nextjs_base_url}{settings.nextjs_webhook_entry}"
            response = await self.client.post(url, json=data)
            
            if response.status_code == 200:
                logger.info(f"Vehicle entry sent to Next.js: {data.get('plate_number')}")
                return True
            else:
                logger.error(f"Failed to send entry: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending vehicle entry: {e}")
            return False
    
    async def send_vehicle_exit(self, data: Dict[str, Any]) -> bool:
        """
        Send vehicle exit event to Next.js
        
        Args:
            data: Vehicle exit data with duration
            
        Returns:
            Success status
        """
        try:
            url = f"{self.nextjs_base_url}{settings.nextjs_webhook_exit}"
            response = await self.client.post(url, json=data)
            
            if response.status_code == 200:
                logger.info(f"Vehicle exit sent to Next.js: {data.get('plate_number')}")
                return True
            else:
                logger.error(f"Failed to send exit: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending vehicle exit: {e}")
            return False
    
    async def send_capacity_update(self, data: Dict[str, Any]) -> bool:
        """
        Send capacity update to Next.js
        
        Args:
            data: Capacity metrics
            
        Returns:
            Success status
        """
        try:
            slots = data.get('slots', [])
            # Log what we're sending
            logger.info(f"Sending capacity update: lot={data.get('parking_lot_id')}, "
                       f"occupied={data.get('occupied')}, total={data.get('total_slots')}, "
                       f"slots_count={len(slots)}")
            
            # Log first few slots for debugging
            if slots:
                logger.debug(f"First 3 slots: {slots[:3]}")
            else:
                logger.warning("No slots in data!")
            
            # Log the full payload for debugging
            logger.debug(f"Full payload keys: {list(data.keys())}")
            
            url = f"{self.nextjs_base_url}{settings.nextjs_webhook_capacity}"
            response = await self.client.post(url, json=data)
            
            if response.status_code == 200:
                logger.info(f"Capacity update sent successfully: {data.get('parking_lot_id')}")
                return True
            else:
                logger.error(f"Failed to send capacity: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending capacity update: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class PathwayOutputHandler:
    """
    Handler for Pathway table outputs
    Processes Pathway computation results and sends to Next.js
    """
    
    def __init__(self):
        self.connector = NextJSOutputConnector()
    
    async def handle_vehicle_journey(self, journey_data: Dict[str, Any]):
        """
        Handle completed vehicle journey
        
        Args:
            journey_data: Journey data with entry/exit times and duration
        """
        # Send entry event
        entry_data = {
            "plate_number": journey_data["plate_number"],
            "parking_lot_id": journey_data["parking_lot_id"],
            "camera_id": journey_data["entry_camera"],
            "timestamp": journey_data["entry_time"],
            "confidence": journey_data["entry_confidence"],
            "event_type": "entry",
        }
        await self.connector.send_vehicle_entry(entry_data)
        
        # Send exit event with duration
        exit_data = {
            "plate_number": journey_data["plate_number"],
            "parking_lot_id": journey_data["parking_lot_id"],
            "camera_id": journey_data["exit_camera"],
            "timestamp": journey_data["exit_time"],
            "confidence": journey_data["exit_confidence"],
            "duration_seconds": journey_data["duration_seconds"],
            "event_type": "exit",
        }
        await self.connector.send_vehicle_exit(exit_data)
    
    async def handle_capacity_update(self, capacity_data: Dict[str, Any]):
        """
        Handle capacity update
        
        Args:
            capacity_data: Aggregated capacity metrics
        """
        slots_array = capacity_data.get("slots", [])
        logger.debug(f"handle_capacity_update received: lot={capacity_data['parking_lot_id']}, "
                    f"slots_in_data={len(slots_array)}")
        
        data = {
            "parking_lot_id": capacity_data["parking_lot_id"],
            "total_slots": capacity_data["total_slots"],
            "occupied": capacity_data["occupied"],
            "empty": capacity_data["empty"],
            "occupancy_rate": capacity_data["occupancy_rate"],
            "slots": slots_array,  # Include individual slot details
            "timestamp": capacity_data.get("last_updated", int(datetime.now().timestamp() * 1000)),
        }
        
        logger.debug(f"Sending to Next.js: slots_count={len(data['slots'])}")
        await self.connector.send_capacity_update(data)
    
    async def handle_threshold_breach(self, breach_data: Dict[str, Any]):
        """
        Handle capacity threshold breach
        
        Args:
            breach_data: Threshold breach event
        """
        logger.warning(
            f"Capacity threshold breach: {breach_data['parking_lot_id']} "
            f"at {breach_data['occupancy_rate']:.1%} occupancy"
        )
        
        # Send as capacity update with alert flag
        data = {
            "parking_lot_id": breach_data["parking_lot_id"],
            "occupied": breach_data["occupied"],
            "total_slots": breach_data["total_slots"],
            "occupancy_rate": breach_data["occupancy_rate"],
            "alert": True,
            "severity": breach_data["severity"],
            "timestamp": breach_data["breach_time"],
        }
        await self.connector.send_capacity_update(data)
    
    async def close(self):
        """Cleanup resources"""
        await self.connector.close()

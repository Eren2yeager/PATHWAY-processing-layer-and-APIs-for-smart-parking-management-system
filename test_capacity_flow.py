"""
Test script to verify capacity data flow
"""
import asyncio
from pathway_pipeline import PathwayPipelineManager
from utils.logger import logger

async def test_capacity_flow():
    """Test that capacity updates include slots array"""
    
    # Create pipeline
    pipeline = PathwayPipelineManager()
    await pipeline.start()
    
    # Add some test slot updates
    parking_lot_id = "test_lot_123"
    camera_id = "test_camera"
    
    logger.info("Adding test slot updates...")
    for slot_id in range(1, 11):  # 10 slots
        status = "occupied" if slot_id % 3 == 0 else "empty"
        pipeline.add_capacity_update(
            parking_lot_id=parking_lot_id,
            camera_id=camera_id,
            slot_id=slot_id,
            status=status,
            confidence=0.95,
        )
    
    # Wait for processing
    logger.info("Waiting for pipeline to process...")
    await asyncio.sleep(2)
    
    # Check buffer
    events = pipeline.stream_connector.get_capacity_events()
    logger.info(f"Events in buffer: {len(events)}")
    
    if events:
        # Manually test aggregation
        capacity_data = pipeline._aggregate_capacity(events)
        logger.info(f"Aggregated data: {capacity_data}")
        logger.info(f"Slots count: {len(capacity_data.get('slots', []))}")
        
        # Test output handler
        await pipeline.output_handler.handle_capacity_update(capacity_data)
    
    await pipeline.stop()
    logger.info("Test complete")

if __name__ == "__main__":
    asyncio.run(test_capacity_flow())

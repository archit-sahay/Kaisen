import logging
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from models import ItemResponse, ItemsResponse
from database import OSRSDataManager

logger = logging.getLogger(__name__)

class APIRoutes:
    def __init__(self, data_manager: OSRSDataManager):
        self.data_manager = data_manager

    async def get_root(self):
        """Root endpoint"""
        return {
            "message": "OSRS Price Tracker API", 
            "status": "running",
            "author": "Archit Sahay",
            "description": "Live updating RuneScape Grand Exchange prices with Event-Driven Redis Pub/Sub"
        }

    async def get_items(self) -> ItemsResponse:
        """
        Main API endpoint - implements event-driven architecture:
        - Fetches from PostgreSQL (source of truth)
        - Redis pub/sub handles proactive price updates
        - Returns data immediately without manual cache checks
        """
        try:
            items = await self.data_manager.get_items_from_db()
            
            return ItemsResponse(
                items=[ItemResponse(**item) for item in items],
                count=len(items),
                timestamp=datetime.now(timezone(timedelta(hours=0))),
                source="database"
            )
            
        except Exception as e:
            logger.error(f"Failed to get items: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch items")

    async def get_item(self, item_id: int) -> ItemResponse:
        """Get specific item by ID"""
        try:
            item_data = await self.data_manager.get_item_by_id(item_id)
            
            if not item_data:
                raise HTTPException(status_code=404, detail="Item not found")
            
            return ItemResponse(**item_data)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get item {item_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch item")

    async def health_check(self):
        """Health check endpoint"""
        try:
            # Check database
            async with self.data_manager.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except:
            db_healthy = False
        
        # Check Redis
        try:
            self.data_manager.redis_client.ping()
            redis_healthy = True
        except:
            redis_healthy = False
        
        # Get connected clients count
        connected_clients = 0
        if self.data_manager.socket_manager:
            connected_clients = len(self.data_manager.socket_manager.connected_clients)
        
        return {
            "status": "healthy" if (db_healthy and redis_healthy) else "unhealthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "architecture": "event-driven with Redis pub/sub",
            "connected_clients": connected_clients,
            "timestamp": datetime.now(timezone(timedelta(hours=0))).isoformat()
        } 
"""
OSRS Price Tracker Backend
User's Blueprint Implementation:
- API fetches from PostgreSQL (source of truth)
- Frontend hits API on start + WebSocket connection
- Backend caches DB data in Redis with TTL
- Cache expiry triggers OSRS API check
- DB updates + WebSocket notify frontend to refetch
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import aiohttp
import asyncpg
import redis
import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://osrs_user:osrs_password@localhost:5432/osrs_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
OSRS_API_TIMEOUT = int(os.getenv("OSRS_API_TIMEOUT", "30"))
PORT = int(os.getenv("PORT", "8000"))  # Configurable port

# Pydantic models
class ItemResponse(BaseModel):
    id: int
    name: str
    examine: Optional[str] = None
    members: bool = False
    lowalch: Optional[int] = None
    highalch: Optional[int] = None
    limit_value: Optional[int] = None
    value: Optional[int] = None
    icon: Optional[str] = None
    high_price: Optional[int] = None
    low_price: Optional[int] = None
    high_time: Optional[int] = None
    low_time: Optional[int] = None
    price_last_updated: Optional[datetime] = None

class ItemsResponse(BaseModel):
    items: List[ItemResponse]
    count: int
    timestamp: datetime
    source: str

# Core Data Manager implementing user's blueprint
class OSRSDataManager:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.api_session: Optional[aiohttp.ClientSession] = None
        self.socket_manager: Optional['SocketManager'] = None
        self._update_lock = asyncio.Lock()
        
    async def init_connections(self):
        """Initialize all connections"""
        # Database connection pool
        self.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        # Redis connection (sync)
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        
        # HTTP session for OSRS API
        self.api_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=OSRS_API_TIMEOUT),
            headers={'User-Agent': 'OSRS-Price-Tracker-Study-Project'}
        )
        
        logger.info("All connections initialized successfully")
        
    async def close_connections(self):
        """Clean up all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.api_session:
            await self.api_session.close()
        if self.redis_client:
            self.redis_client.close()
        logger.info("All connections closed")
    
    async def startup_cache_population(self):
        """Populate Redis cache on startup with DB data"""
        try:
            logger.info("Populating startup cache from database")
            
            # Fetch initial items from OSRS mapping API
            await self._fetch_and_store_items_mapping()
            
            # Get all items from database
            items = await self._get_all_items_from_db()
            
            # Cache in Redis with TTL
            self.redis_client.setex(
                "items_cache",
                CACHE_TTL,
                json.dumps(items, default=str)
            )
            
            logger.info(f"Cached {len(items)} items on startup")
            
        except Exception as e:
            logger.error(f"Startup cache population failed: {e}")
    
    async def get_items_from_db(self) -> List[Dict]:
        """Main method: Get items from DB (source of truth) + trigger cache check"""
        
        # Step 1: Always get from database (source of truth)
        items = await self._get_all_items_from_db()
        
        # Step 2: Check cache and trigger update if needed (non-blocking)
        asyncio.create_task(self._check_cache_and_update())
        
        return items
    
    async def _get_all_items_from_db(self) -> List[Dict]:
        """Fetch all items with prices from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM items_with_prices 
                ORDER BY name
            """)
            return [dict(row) for row in rows]
    
    async def _check_cache_and_update(self):
        """Check if cache expired and trigger OSRS API update if needed"""
        try:
            # Check if cache exists
            cache_exists = self.redis_client.exists("items_cache")
            
            if not cache_exists:
                logger.info("Cache expired - triggering OSRS API update")
                
                # Use lock to prevent multiple concurrent updates
                async with self._update_lock:
                    # Double-check cache (another request might have updated)
                    if not self.redis_client.exists("items_cache"):
                        await self._update_from_osrs_api()
                        
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
    
    async def _update_from_osrs_api(self):
        """Core update logic: OSRS API -> Compare -> Update DB -> Notify"""
        try:
            logger.info("Starting OSRS API update cycle")
            
            # Step 1: Fetch latest prices from OSRS API
            latest_prices = await self._fetch_osrs_latest_prices()
            
            if not latest_prices:
                logger.warning("No data from OSRS API")
                return
            
            # Step 2: Get current prices from DB for efficient comparison
            current_prices = await self._get_current_prices_for_comparison()
            
            # Step 3: Detect changes (efficient, no DB explosion)
            updated_items = self._detect_price_changes(current_prices, latest_prices)
            
            if updated_items:
                # Step 4: Batch update database
                await self._batch_update_prices(updated_items)
                logger.info(f"Updated {len(updated_items)} items in database")
                
                # Step 5: Notify frontend via WebSocket
                await self.socket_manager.notify_price_updates(list(updated_items.keys()))
            else:
                logger.info("No price changes detected")
            
            # Step 6: Refresh cache with updated data
            await self._refresh_cache()
            
        except Exception as e:
            logger.error(f"OSRS API update failed: {e}")
    
    async def _fetch_osrs_latest_prices(self) -> Dict:
        """Fetch latest prices from OSRS API"""
        try:
            async with self.api_session.get(
                'https://prices.runescape.wiki/api/v1/osrs/latest'
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {})
                else:
                    logger.error(f"OSRS API returned status {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to fetch OSRS prices: {e}")
            return {}
    
    async def _fetch_and_store_items_mapping(self):
        """Fetch and store items mapping from OSRS API (run once on startup)"""
        try:
            logger.info("Fetching items mapping from OSRS API")
            
            async with self.api_session.get(
                'https://prices.runescape.wiki/api/v1/osrs/mapping'
            ) as response:
                if response.status == 200:
                    items = await response.json()
                    await self._store_items_in_db(items)
                    logger.info(f"Stored {len(items)} items in database")
                else:
                    logger.error(f"Items mapping API returned status {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to fetch items mapping: {e}")
    
    async def _store_items_in_db(self, items: List[Dict]):
        """Store items mapping in database"""
        async with self.db_pool.acquire() as conn:
            
            # Prepare data for insertion
            item_data = []
            for item in items:
                item_data.append((
                    item.get('id'),
                    item.get('name'),
                    item.get('examine'),
                    item.get('members', False),
                    item.get('lowalch'),
                    item.get('highalch'),
                    item.get('limit'),  # will map to limit_value in DB
                    item.get('value'),
                    item.get('icon')
                ))
            
            # Batch insert with conflict resolution
            await conn.executemany("""
                INSERT INTO items (id, name, examine, members, lowalch, highalch, limit_value, value, icon)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    examine = EXCLUDED.examine,
                    members = EXCLUDED.members,
                    lowalch = EXCLUDED.lowalch,
                    highalch = EXCLUDED.highalch,
                    limit_value = EXCLUDED.limit_value,
                    value = EXCLUDED.value,
                    icon = EXCLUDED.icon,
                    updated_at = CURRENT_TIMESTAMP
            """, item_data)
    
    async def _get_current_prices_for_comparison(self) -> Dict:
        """Get current prices from DB for efficient comparison (avoid DB explosion)"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT item_id, high_price, low_price, high_time, low_time 
                FROM prices
            """)
            return {str(row['item_id']): dict(row) for row in rows}
    
    def _detect_price_changes(self, current_prices: Dict, latest_prices: Dict) -> Dict:
        """Efficient change detection using timestamps (prevents DB explosion)"""
        updated_items = {}
        
        for item_id, latest_data in latest_prices.items():
            current_data = current_prices.get(item_id, {})
            
            # Use timestamps for efficient change detection
            latest_high_time = latest_data.get('highTime', 0) or 0
            latest_low_time = latest_data.get('lowTime', 0) or 0
            
            current_high_time = current_data.get('high_time', 0) or 0
            current_low_time = current_data.get('low_time', 0) or 0
            
            # If either timestamp is newer, it's a real change
            if (latest_high_time > current_high_time or 
                latest_low_time > current_low_time):
                updated_items[item_id] = latest_data
        
        logger.info(f"Detected changes in {len(updated_items)}/{len(latest_prices)} items")
        return updated_items
    
    async def _batch_update_prices(self, updated_items: Dict):
        """Batch update prices in database (efficient, no explosion)"""
        async with self.db_pool.acquire() as conn:
            
            # Get valid item IDs to filter out foreign key violations
            valid_item_ids = set()
            rows = await conn.fetch("SELECT id FROM items")
            valid_item_ids = {str(row['id']) for row in rows}
            
            # Prepare batch data - only for items that exist in our database
            update_data = []
            filtered_count = 0
            
            for item_id, data in updated_items.items():
                if item_id in valid_item_ids:
                    update_data.append((
                        int(item_id),
                        data.get('high'),
                        data.get('highTime'),
                        data.get('low'),
                        data.get('lowTime')
                    ))
                else:
                    filtered_count += 1
            
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} items not in our database")
            
            if update_data:
                # Batch update with single query
                await conn.executemany("""
                    INSERT INTO prices (item_id, high_price, high_time, low_price, low_time, last_updated)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                    ON CONFLICT (item_id) 
                    DO UPDATE SET 
                        high_price = EXCLUDED.high_price,
                        high_time = EXCLUDED.high_time,
                        low_price = EXCLUDED.low_price,
                        low_time = EXCLUDED.low_time,
                        last_updated = EXCLUDED.last_updated
                """, update_data)
                logger.info(f"Successfully updated prices for {len(update_data)} items")
            else:
                logger.warning("No valid items to update prices for")
    
    async def _refresh_cache(self):
        """Refresh Redis cache with latest data from DB"""
        try:
            items = await self._get_all_items_from_db()
            self.redis_client.setex(
                "items_cache",
                CACHE_TTL,
                json.dumps(items, default=str)
            )
            logger.info("Cache refreshed with latest data")
        except Exception as e:
            logger.warning(f"Cache refresh failed: {e}")

# Socket.IO Manager for WebSocket communication
class SocketManager:
    def __init__(self):
        self.connected_clients = set()
    
    async def notify_price_updates(self, updated_item_ids: List[str]):
        """Notify frontend clients about price updates"""
        if not self.connected_clients:
            return
        
        message = {
            'type': 'price_update',
            'updated_items': updated_item_ids,
            'count': len(updated_item_ids),
            'timestamp': datetime.now(timezone(timedelta(hours=0))).isoformat()
        }
        
        await sio.emit('price_update', message)
        logger.info(f"Notified {len(self.connected_clients)} clients about {len(updated_item_ids)} price updates")

# Initialize managers
data_manager = OSRSDataManager()
socket_manager = SocketManager()
data_manager.socket_manager = socket_manager

# Socket.IO setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*"  # Configure for production
)

@sio.event
async def connect(sid, environ):
    """Client connected to WebSocket"""
    socket_manager.connected_clients.add(sid)
    logger.info(f"Client {sid} connected. Total: {len(socket_manager.connected_clients)}")
    
    await sio.emit('connected', {
        'message': 'Connected to OSRS live price updates', 
        'timestamp': datetime.now(timezone(timedelta(hours=0))).isoformat()
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Client disconnected from WebSocket"""
    socket_manager.connected_clients.discard(sid)
    logger.info(f"Client {sid} disconnected. Total: {len(socket_manager.connected_clients)}")

@sio.event
async def ping(sid):
    """Handle ping from client"""
    await sio.emit('pong', {'timestamp': datetime.now(timezone(timedelta(hours=0))).isoformat()}, room=sid)

# FastAPI Lifespan (modern approach)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    
    # Startup
    logger.info("Starting OSRS Price Tracker Backend...")
    
    try:
        await data_manager.init_connections()
        await data_manager.startup_cache_population()
        logger.info("Backend started successfully")
        
        yield  # Application runs here
        
    finally:
        # Shutdown
        logger.info("Shutting down backend...")
        await data_manager.close_connections()
        logger.info("Backend shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="OSRS Price Tracker API",
    description="Live updating RuneScape item prices with WebSocket notifications",
    version="1.0.0",
    lifespan=lifespan
)

# Wrap with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes (implementing user's blueprint)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "OSRS Price Tracker API", "status": "running"}

@app.get("/api/items", response_model=ItemsResponse)
async def get_items():
    """
    Main API endpoint - implements user's blueprint:
    - Fetches from PostgreSQL (source of truth)
    - Triggers cache check (non-blocking)
    - Returns data immediately
    """
    try:
        items = await data_manager.get_items_from_db()
        
        return ItemsResponse(
            items=[ItemResponse(**item) for item in items],
            count=len(items),
            timestamp=datetime.now(timezone(timedelta(hours=0))),
            source="database"
        )
        
    except Exception as e:
        logger.error(f"Failed to get items: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch items")

@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    """Get specific item by ID"""
    try:
        async with data_manager.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM items_with_prices WHERE id = $1
            """, item_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Item not found")
            
            return ItemResponse(**dict(row))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch item")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        async with data_manager.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_healthy = True
    except:
        db_healthy = False
    
    # Check Redis
    try:
        data_manager.redis_client.ping()
        redis_healthy = True
    except:
        redis_healthy = False
    
    return {
        "status": "healthy" if (db_healthy and redis_healthy) else "unhealthy",
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
        "connected_clients": len(socket_manager.connected_clients),
        "timestamp": datetime.now(timezone(timedelta(hours=0))).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=PORT, log_level="info") 
import asyncio
import json
import logging
import ssl
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

import aiohttp
import asyncpg
import redis

from config import (
    DATABASE_URL, REDIS_URL, CACHE_TTL, OSRS_API_TIMEOUT,
    OSRS_PRICES_API_URL, OSRS_MAPPING_API_URL,
    DB_MIN_CONNECTIONS, DB_MAX_CONNECTIONS, DB_COMMAND_TIMEOUT
)

logger = logging.getLogger(__name__)

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
            min_size=DB_MIN_CONNECTIONS,
            max_size=DB_MAX_CONNECTIONS,
            command_timeout=DB_COMMAND_TIMEOUT
        )
        
        # Redis connection (sync)
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        
        # Create custom SSL context for OSRS API
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # HTTP session for OSRS API
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.api_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=OSRS_API_TIMEOUT),
            headers={'User-Agent': 'OSRS-Price-Tracker-Study-Project'},
            connector=connector
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
                if self.socket_manager:
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
            async with self.api_session.get(OSRS_PRICES_API_URL) as response:
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
            
            async with self.api_session.get(OSRS_MAPPING_API_URL) as response:
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

    async def get_item_by_id(self, item_id: int) -> Optional[Dict]:
        """Get specific item by ID from database"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM items_with_prices WHERE id = $1
            """, item_id)
            return dict(row) if row else None 
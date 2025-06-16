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
    DB_MIN_CONNECTIONS, DB_MAX_CONNECTIONS, DB_COMMAND_TIMEOUT,
    REDIS_KEYSPACE_NOTIFICATIONS, CACHE_EXPIRY_CHANNEL, CACHE_KEY_NAME
)

logger = logging.getLogger(__name__)

class OSRSDataManager:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.redis_pubsub: Optional[redis.client.PubSub] = None
        self.api_session: Optional[aiohttp.ClientSession] = None
        self.socket_manager: Optional['SocketManager'] = None
        self._update_lock = asyncio.Lock()
        self._pubsub_task: Optional[asyncio.Task] = None
        
    async def init_connections(self):
        """Initialize all connections and enable Redis pub/sub"""
        # Database connection pool
        self.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=DB_MIN_CONNECTIONS,
            max_size=DB_MAX_CONNECTIONS,
            command_timeout=DB_COMMAND_TIMEOUT
        )
        
        # Redis connection (sync)
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        
        # Enable Redis keyspace notifications for expired events
        self._enable_keyspace_notifications()
        
        # Setup pub/sub for cache expiry events
        self.redis_pubsub = self.redis_client.pubsub()
        self._setup_pubsub_listener()
        
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
        
        logger.info("All connections initialized successfully with Redis pub/sub")
        
    async def close_connections(self):
        """Clean up all connections"""
        # Stop pub/sub listener
        if self._pubsub_task and not self._pubsub_task.done():
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Close Redis pub/sub
        if self.redis_pubsub:
            self.redis_pubsub.close()
        
        # Close other connections
        if self.db_pool:
            await self.db_pool.close()
        if self.api_session:
            await self.api_session.close()
        if self.redis_client:
            self.redis_client.close()
        logger.info("All connections closed")
    
    def _enable_keyspace_notifications(self):
        """Enable Redis keyspace notifications for expired events"""
        try:
            self.redis_client.config_set('notify-keyspace-events', REDIS_KEYSPACE_NOTIFICATIONS)
            logger.info("Redis keyspace notifications enabled for expired events")
        except Exception as e:
            logger.error(f"Failed to enable keyspace notifications: {e}")
    
    def _setup_pubsub_listener(self):
        """Setup Redis pub/sub listener for cache expiry events"""
        try:
            # Subscribe to expiry events pattern
            self.redis_pubsub.psubscribe(CACHE_EXPIRY_CHANNEL)
            logger.info(f"Subscribed to Redis expiry events: {CACHE_EXPIRY_CHANNEL}")
        except Exception as e:
            logger.error(f"Failed to setup pub/sub listener: {e}")
    
    async def start_pubsub_listener(self):
        """Start background task to listen for Redis pub/sub messages"""
        self._pubsub_task = asyncio.create_task(self._pubsub_message_handler())
        logger.info("Started Redis pub/sub listener for proactive price updates")
    
    async def _pubsub_message_handler(self):
        """Handle Redis pub/sub messages for cache expiry events"""
        try:
            # Use run_in_executor for blocking Redis operations
            while True:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, self.redis_pubsub.get_message, 1.0
                )
                
                if message and message['type'] == 'pmessage':
                    # Extract the expired key name
                    expired_key = message['data']
                    
                    if expired_key == CACHE_KEY_NAME:
                        logger.info("Cache expiry event received - triggering proactive price update")
                        
                        # Use lock to prevent concurrent updates
                        async with self._update_lock:
                            await self._update_from_osrs_api()
                            
        except asyncio.CancelledError:
            logger.info("Pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Pub/sub message handler error: {e}")
    
    async def startup_cache_population(self):
        """Populate Redis cache on startup and start pub/sub listener"""
        try:
            logger.info("Populating startup cache from database")
            
            # Fetch initial items from OSRS mapping API
            await self._fetch_and_store_items_mapping()
            
            # Get all items from database
            items = await self._get_all_items_from_db()
            
            # Set cache with TTL (this will trigger pub/sub when it expires)
            self._set_cache_with_expiry()
            
            # Start the pub/sub listener for proactive updates
            await self.start_pubsub_listener()
            
            logger.info(f"Event-driven architecture initialized with {len(items)} items")
            
        except Exception as e:
            logger.error(f"Startup cache population failed: {e}")
    
    async def get_items_from_db(self) -> List[Dict]:
        """Main method: Get items from DB (source of truth) - no more manual cache checks needed"""
        
        # Always get from database (source of truth)
        items = await self._get_all_items_from_db()
        
        # No more manual cache checking - pub/sub handles this proactively!
        logger.debug("Data served from database - pub/sub handles cache expiry automatically")
        
        return items
    
    async def _get_all_items_from_db(self) -> List[Dict]:
        """Fetch all items with prices from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM items_with_prices 
                ORDER BY name
            """)
            return [dict(row) for row in rows]
    
    def _set_cache_with_expiry(self):
        """Set cache key with TTL - expiry will trigger pub/sub event"""
        try:
            # Set a simple marker key that will expire and trigger pub/sub
            self.redis_client.setex(
                CACHE_KEY_NAME,
                CACHE_TTL,
                json.dumps({"last_update": datetime.now().isoformat()})
            )
            logger.info(f"Cache key set with {CACHE_TTL}s TTL - pub/sub will handle expiry")
        except Exception as e:
            logger.warning(f"Failed to set cache key: {e}")
    
    async def _update_from_osrs_api(self):
        """Core update logic: OSRS API -> Compare -> Update DB -> Notify -> Reset Cache"""
        try:
            logger.info("Starting proactive OSRS API update cycle")
            
            # Step 1: Fetch latest prices from OSRS API
            latest_prices = await self._fetch_osrs_latest_prices()
            
            if not latest_prices:
                logger.warning("No data from OSRS API")
                # Reset cache even if API fails to maintain the update cycle
                self._set_cache_with_expiry()
                return
            
            logger.info(f"✅ Retrieved {len(latest_prices)} items from OSRS API")
            
            # Step 2: Get current prices from DB for efficient comparison
            current_prices = await self._get_current_prices_for_comparison()
            logger.info(f"✅ Retrieved {len(current_prices)} current prices from database")
            
            # Step 3: Detect changes (efficient, no DB explosion)
            updated_items = self._detect_price_changes(current_prices, latest_prices)
            
            if updated_items:
                # Step 4: Batch update database
                await self._batch_update_prices(updated_items)
                logger.info(f"📊 Updated {len(updated_items)} items in database")
                
                # Step 5: Notify frontend via WebSocket
                if self.socket_manager:
                    await self.socket_manager.notify_price_updates(list(updated_items.keys()))
                    logger.info(f"📡 Notified frontend via WebSocket about {len(updated_items)} price changes")
                else:
                    logger.warning("Socket manager not available - skipping WebSocket notification")
            else:
                logger.info("✅ No price changes detected - database and frontend remain unchanged")
            
            # Step 6: Reset cache key for next expiry cycle
            self._set_cache_with_expiry()
            
            logger.info("🔄 Proactive update cycle completed - cache reset for next trigger in 2 minutes")
            
        except Exception as e:
            logger.error(f"❌ OSRS API update failed: {e}")
            # Always reset cache to maintain update cycle
            self._set_cache_with_expiry()
            logger.info("🔄 Cache reset despite error - maintaining update cycle")
    
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
        change_details = []
        
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
                
                # Collect detailed change information for logging
                change_info = {
                    'item_id': item_id,
                    'high_price_old': current_data.get('high_price'),
                    'high_price_new': latest_data.get('high'),
                    'low_price_old': current_data.get('low_price'),
                    'low_price_new': latest_data.get('low'),
                    'high_time_old': current_high_time,
                    'high_time_new': latest_high_time,
                    'low_time_old': current_low_time,
                    'low_time_new': latest_low_time
                }
                change_details.append(change_info)
        
        # Log summary
        logger.info(f"Detected changes in {len(updated_items)}/{len(latest_prices)} items")
        
        # Log detailed changes for first few items (to avoid log spam)
        if change_details:
            logger.info("📈 PRICE CHANGES DETECTED:")
            for i, change in enumerate(change_details[:10]):  # Log first 10 changes
                # Format price changes
                high_change = ""
                low_change = ""
                
                if change['high_time_new'] > change['high_time_old']:
                    old_high = change['high_price_old'] or 0
                    new_high = change['high_price_new'] or 0
                    high_change = f"High: {old_high:,} → {new_high:,}"
                
                if change['low_time_new'] > change['low_time_old']:
                    old_low = change['low_price_old'] or 0
                    new_low = change['low_price_new'] or 0
                    low_change = f"Low: {old_low:,} → {new_low:,}"
                
                changes_str = " | ".join(filter(None, [high_change, low_change]))
                logger.info(f"  Item {change['item_id']}: {changes_str}")
            
            if len(change_details) > 10:
                logger.info(f"  ... and {len(change_details) - 10} more items changed")
        
        return updated_items
    
    async def _batch_update_prices(self, updated_items: Dict):
        """Batch update prices in database (efficient, no explosion)"""
        async with self.db_pool.acquire() as conn:
            
            # Get valid item IDs and names to filter out foreign key violations
            valid_item_data = {}
            rows = await conn.fetch("SELECT id, name FROM items")
            valid_item_data = {str(row['id']): row['name'] for row in rows}
            
            # Prepare batch data - only for items that exist in our database
            update_data = []
            updated_item_names = []
            filtered_count = 0
            
            for item_id, data in updated_items.items():
                if item_id in valid_item_data:
                    update_data.append((
                        int(item_id),
                        data.get('high'),
                        data.get('highTime'),
                        data.get('low'),
                        data.get('lowTime')
                    ))
                    updated_item_names.append(f"{valid_item_data[item_id]} (ID: {item_id})")
                else:
                    filtered_count += 1
            
            if filtered_count > 0:
                logger.info(f"⚠️  Filtered out {filtered_count} items not in our database")
            
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
                
                logger.info(f"💾 Successfully updated prices for {len(update_data)} items in database")
                
                # Log some example item names that were updated (first 5)
                if updated_item_names:
                    sample_items = updated_item_names[:5]
                    logger.info(f"📋 Sample updated items: {', '.join(sample_items)}")
                    if len(updated_item_names) > 5:
                        logger.info(f"   ... and {len(updated_item_names) - 5} more items")
            else:
                logger.warning("⚠️  No valid items to update prices for")

    async def get_item_by_id(self, item_id: int) -> Optional[Dict]:
        """Get specific item by ID from database"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM items_with_prices WHERE id = $1
            """, item_id)
            return dict(row) if row else None 
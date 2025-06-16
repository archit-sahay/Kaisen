# 🤔 OSRS Price Tracker - Frequently Asked Questions

## 🏗️ Architecture & Data Flow

### Q: What happens when the frontend hits our API? Does it fetch data from PostgreSQL or Redis?

**A: It fetches from PostgreSQL (source of truth), NOT Redis.**

The API always returns data from PostgreSQL. Redis is used only for timing/cache expiry logic, not for data storage.

**File:** `backend/routes.py`
```python
async def get_items(self) -> ItemsResponse:
    """
    Main API endpoint - implements cache-driven architecture:
    - Fetches from PostgreSQL (source of truth)
    - Triggers cache check (non-blocking)
    - Returns data immediately
    """
    items = await self.data_manager.get_items_from_db()
    return ItemsResponse(
        items=[ItemResponse(**item) for item in items],
        source="database"  # <-- Always from database
    )
```

### Q: What socket events do we have between frontend and backend?

**A: We have several WebSocket events for real-time communication:**

**Backend → Frontend:**
- `connected` - Connection confirmation
- `price_update` - Notification when prices change
- `pong` - Response to ping

**Frontend → Backend:**
- `ping` - Connection testing

**File:** `backend/socket_manager.py`
```python
# Main update notification
await sio.emit('price_update', {
    'type': 'price_update',
    'updated_items': updated_item_ids,
    'count': len(updated_item_ids),
    'timestamp': datetime.now().isoformat()
})
```

### Q: What happens when cached data in Redis expires?

**A: Step-by-step process:**

1. **Cache Expiry Check:** Redis TTL expires (2 minutes)
2. **API Call:** Fetch latest prices from OSRS API
3. **Smart Comparison:** Compare timestamps (not prices) for efficiency
4. **Database Update:** Batch update only changed items
5. **WebSocket Notification:** Tell frontend "data changed"
6. **Cache Refresh:** Reset Redis TTL for next cycle
7. **Frontend Refetch:** Frontend gets socket event and refetches data

**File:** `backend/database.py`
```python
async def _update_from_osrs_api(self):
    """Core update logic: OSRS API → Compare → Update DB → Notify"""
    
    # Step 1: Fetch latest prices from OSRS API
    latest_prices = await self._fetch_osrs_latest_prices()
    
    # Step 2: Get current prices from DB for comparison
    current_prices = await self._get_current_prices_for_comparison()
    
    # Step 3: Detect changes (timestamp-based, efficient!)
    updated_items = self._detect_price_changes(current_prices, latest_prices)
    
    if updated_items:
        # Step 4: Batch update database
        await self._batch_update_prices(updated_items)
        
        # Step 5: Notify frontend via WebSocket
        await self.socket_manager.notify_price_updates(list(updated_items.keys()))
    
    # Step 6: Refresh cache with new TTL
    await self._refresh_cache()
```

### Q: How do we use 3rd party APIs? Are both APIs hit periodically?

**A: We use two OSRS Wiki APIs with different patterns:**

1. **Mapping API - ONCE on startup only:**
   - URL: `https://prices.runescape.wiki/api/v1/osrs/mapping`
   - Fetches item metadata (names, descriptions, etc.)
   - Only called during backend initialization

2. **Prices API - Every 2 minutes (when cache expires):**
   - URL: `https://prices.runescape.wiki/api/v1/osrs/latest`
   - Fetches current market prices
   - Called based on cache expiry

**File:** `backend/config.py`
```python
OSRS_PRICES_API_URL = "https://prices.runescape.wiki/api/v1/osrs/latest"     # Periodic
OSRS_MAPPING_API_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"  # One-time
```

### Q: Does frontend have data initially when backend starts?

**A: YES! Frontend gets data immediately after backend startup.**

**Startup Sequence:**
1. **Backend starts:** Fetches 4,276 items from OSRS mapping API → stores in DB
2. **Frontend loads:** Immediately calls `/api/items` → gets all items from DB
3. **No waiting:** Frontend has data instantly
4. **Live updates:** Every 2 minutes, cache expires → prices update → WebSocket notifies frontend

The setup time is only for the very first backend startup to populate the database with item metadata.

### Q: When is the Redis EXISTS check called?

**A: The EXISTS check is request-driven, not time-driven.**

**Complete Flow:**
1. **Frontend Request:** User visits page → `GET /api/items`
2. **API Route:** `backend/routes.py` → calls `get_items_from_db()`
3. **Database Method:** Returns data + triggers background `_check_cache_and_update()`
4. **Cache Check:** `redis_client.exists("items_cache")` → if expired → OSRS API call

**Key Point:** No scheduled job running every 2 minutes. The check only happens when someone requests data.

## 🚨 Architecture Issues Identified

### Q: What happens if frontend doesn't hit API for an hour?

**A: MAJOR ISSUE - Prices become stale!**

**The Problem:**
- Frontend has NO periodic API calls
- Backend only checks cache when API is hit
- No users = No API calls = No price updates
- Data can be hours old when first user returns

**Current Flawed Flow:**
```
User Activity → API Calls → Fresh Data
No Activity → No Updates → Stale Data  ❌
```

**Should Be:**
```
Time-based Schedule → Regular Updates → Always Fresh Data  ✅
```

### Q: Are we using Redis pub/sub?

**A: YES - Event-driven architecture with keyspace notifications!**

**Updated Architecture:**
- Redis keyspace notifications for expired keys
- Proactive updates regardless of user activity
- True event-driven architecture

**Implementation:**
```python
# Enable expiry notifications
redis_client.config_set('notify-keyspace-events', 'Ex')

# Subscribe to expired keys
pubsub = redis_client.pubsub()
pubsub.psubscribe('__keyevent@0__:expired')
```

## 📊 Enhanced Logging & Monitoring

### Q: What detailed information can I see in the backend logs?

**A: Comprehensive price change tracking with item names and specific price movements!**

**Enhanced Logging Features:**

1. **📈 Detailed Price Changes:**
```
📈 PRICE CHANGES DETECTED:
  Item 2: High: 199 → 197 | Low: 197 → 192       (Cannonball)
  Item 10: High: 177,607 → 184,995 | Low: 166,066 → 171,888 (Cannon barrels)
  Item 41: Low: 29 → 28
  ... and 1265 more items changed
```

2. **📋 Sample Updated Items:**
```
📋 Sample updated items: Cannonball (ID: 2), Cannon base (ID: 6), Cannon stand (ID: 8)
   ... and 1254 more items
```

3. **⚙️ System Performance Metrics:**
```
✅ Retrieved 4162 items from OSRS API
✅ Retrieved 4146 current prices from database
📊 Updated 1275 items in database
📡 Notified frontend via WebSocket about 1275 price changes
🔄 Proactive update cycle completed - cache reset for next trigger in 2 minutes
```

4. **🚫 No Changes Detected:**
```
✅ No price changes detected - database and frontend remain unchanged
```

### Q: How can I monitor real-time price changes?

**A: Watch the backend logs for live market activity:**

```bash
# Follow live logs
docker-compose logs backend -f

# Filter for price changes only
docker-compose logs backend | grep "PRICE CHANGES\|Item.*:"
```

**What You'll See:**
- **Exact price movements** (old price → new price)
- **Item names** with IDs for easy identification
- **High/Low price updates** separately tracked
- **Market activity levels** (how many items changed)
- **System efficiency** (API calls vs actual updates)

## 📊 Performance & Design

### Q: How do we prevent database explosion?

**A: Timestamp-based change detection.**

Instead of comparing prices (which change frequently), we compare timestamps:

```python
def _detect_price_changes(self, current_prices: Dict, latest_prices: Dict) -> Dict:
    updated_items = {}
    
    for item_id, latest_data in latest_prices.items():
        current_data = current_prices.get(item_id, {})
        
        # Compare timestamps, not prices (more efficient)
        latest_high_time = latest_data.get('highTime', 0) or 0
        current_high_time = current_data.get('high_time', 0) or 0
        
        if latest_high_time > current_high_time:
            updated_items[item_id] = latest_data
    
    return updated_items
```

### Q: Why is PostgreSQL the source of truth, not Redis?

**A: Database reliability and consistency.**

- **PostgreSQL:** ACID compliance, persistent storage, complex queries
- **Redis:** Volatile memory, simple operations, timing mechanism
- **Pattern:** Database for data, Redis for coordination

## 🔄 Data Flow Summary

```
Frontend Request → PostgreSQL (immediate response)
                     ↓
                Background: Redis Pub/Sub TTL Monitor
                     ↓
                If Expired: OSRS API → DB Update → WebSocket Notify
                     ↓
                Frontend Refetch → Updated Data
```

**Key Architecture Principles:**
- **Database = Source of Truth** (always fresh data)
- **Redis = Event Coordinator** (pub/sub notifications)
- **Non-blocking Updates** (frontend never waits)
- **Efficient Change Detection** (timestamp comparison)
- **Real-time Notifications** (WebSocket push updates)
- **Detailed Logging** (comprehensive monitoring)

---

*This FAQ documents the current event-driven architecture with enhanced logging capabilities for comprehensive price monitoring and system observability.* 
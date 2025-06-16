# 🏰 OSRS Price Tracker
**Author: Archit Sahay**

A real-time **Old School RuneScape (OSRS)** item price tracker that provides live Grand Exchange prices with automatic updates. Built with modern web technologies following an **event-driven architecture with Redis pub/sub**.

## 📋 Project Overview

This application implements a **live updating price table** for OSRS items that automatically reflects the latest prices from the Grand Exchange, ensuring users always see up-to-date information without manual refresh. Features **proactive price monitoring** and **comprehensive logging** for complete market visibility.

## 📸 Live Application

![OSRS Price Tracker Interface](screenshots/app-preview.png)

*The live application showing 4,276+ OSRS items with real-time Grand Exchange prices, including expensive 3rd age items worth billions of GP*

### 🎯 Key Features

- **📊 Live Price Updates** - Real-time price notifications via WebSocket
- **🔍 Advanced Filtering** - Search, sort, and filter by item properties
- **💎 Price Analysis** - High/low prices, trends, and market indicators
- **🏆 Item Categories** - Members vs Free-to-Play indicators
- **📱 Responsive Design** - Works seamlessly on desktop and mobile
- **⚡ Performance Optimized** - Efficient event-driven updates
- **🔍 Enhanced Monitoring** - Detailed price tracking and system observability
- **🚀 Proactive Updates** - Always fresh data regardless of user activity

## 🏗️ Event-Driven Architecture Implementation

This project implements an **event-driven architecture with Redis pub/sub**:

```
React Frontend ←→ WebSocket ←→ FastAPI Backend ←→ Redis Pub/Sub ←→ PostgreSQL
                     ↓              ↓                ↓
                Live Updates    OSRS APIs       Event Triggers
```

### 🔄 Core Flow (Event-Driven)

1. **Frontend hits API on start** - React loads initial data from PostgreSQL
2. **WebSocket connection established** - Real-time communication channel
3. **Redis pub/sub monitoring** - Keyspace notifications for cache expiry events
4. **Proactive OSRS API calls** - Automatic background price checking every 2 minutes
5. **Database updates + WebSocket notify** - Changes trigger frontend refresh
6. **Detailed logging** - Complete visibility into market activity and system performance

### 🧠 Efficient Update Strategy

- **Event-driven updates** - Redis keyspace notifications trigger proactive monitoring
- **Timestamp-based change detection** - Prevents unnecessary database operations
- **Batch updates** - Efficient database writes for multiple items
- **Database as source of truth** - PostgreSQL for reliable data persistence
- **Non-blocking updates** - Frontend remains responsive during updates
- **Always fresh data** - Updates continue even with no user activity

## 🔍 Enhanced Monitoring & Logging

### 📈 **Real-Time Price Change Tracking**
```
📈 PRICE CHANGES DETECTED:
  Item 2: High: 199 → 197 | Low: 197 → 192       (Cannonball)
  Item 10: High: 177,607 → 184,995 | Low: 166,066 → 171,888 (Cannon barrels)
  Item 41: Low: 29 → 28
  ... and 1265 more items changed
```

### 📋 **Updated Items with Names**
```
📋 Sample updated items: Cannonball (ID: 2), Cannon base (ID: 6), Cannon stand (ID: 8)
   ... and 1254 more items
```

### ⚙️ **System Performance Metrics**
```
✅ Retrieved 4162 items from OSRS API
✅ Retrieved 4146 current prices from database
📊 Updated 1275 items in database
📡 Notified frontend via WebSocket about 1275 price changes
🔄 Proactive update cycle completed - cache reset for next trigger in 2 minutes
```

### 🔍 **Live Monitoring Commands**
```bash
# Watch live price changes
docker-compose logs backend -f | grep "PRICE CHANGES\|Item.*:"

# Monitor system performance  
docker-compose logs backend -f | grep "Retrieved\|Updated\|Notified"

# Check for issues
docker-compose logs backend -f | grep "ERROR\|WARNING\|❌\|⚠️"

# Full monitoring dashboard
docker-compose logs backend -f
```

## 🚀 Quick Start

### Prerequisites

- **Docker** and **Docker Compose**
- **Git** for cloning the repository

### 🔧 Setup & Run

```bash
# Clone the repository
git clone <repository-url>
cd osrs-price-tracker

# Start the entire application stack
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Health Check: http://localhost:8000/api/health
```

That's it! The application will:
1. **Initialize database** with 4,276+ OSRS items mapping
2. **Start Redis pub/sub** with keyspace notifications
3. **Launch FastAPI backend** with event-driven monitoring
4. **Serve React frontend** with live updates
5. **Begin proactive price monitoring** every 2 minutes

## 🏛️ Technical Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **Socket.IO** - Real-time WebSocket communication
- **PostgreSQL** - Reliable data persistence
- **Redis Pub/Sub** - Event-driven architecture with keyspace notifications
- **AsyncPG** - Async PostgreSQL driver
- **Enhanced Logging** - Comprehensive monitoring and observability

### Frontend
- **React 18** - Modern UI library with hooks
- **TypeScript** - Type-safe development
- **Socket.IO Client** - Real-time updates
- **Modern CSS** - Responsive design with gradients

### Infrastructure
- **Docker Compose** - Multi-service orchestration
- **Health Checks** - Service monitoring
- **CORS Configuration** - Cross-origin support
- **Redis Keyspace Notifications** - Proactive event triggering

## 📊 Database Schema

### Items Table (Static Data)
```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    examine TEXT,
    members BOOLEAN,
    lowalch INTEGER,
    highalch INTEGER,
    limit_value INTEGER,
    value INTEGER,
    icon VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Prices Table (Dynamic Data)
```sql
CREATE TABLE prices (
    item_id INTEGER PRIMARY KEY REFERENCES items(id),
    high_price INTEGER,
    high_time BIGINT,      -- Unix timestamp
    low_price INTEGER,
    low_time BIGINT,       -- Unix timestamp
    last_updated TIMESTAMP
);
```

## 🔌 API Endpoints

### Core Endpoints
- `GET /api/items` - Fetch all items with prices (always from PostgreSQL)
- `GET /api/items/{id}` - Get specific item details
- `GET /api/health` - System health, architecture type, and monitoring status
- `Socket.IO /socket.io/` - Real-time price update notifications

### Socket.IO Events
```javascript
// Client connects
socket.on('connected', (data) => {
  console.log(data.message); // "Connected to OSRS live price updates"
});

// Price updates
socket.on('price_update', (data) => {
  console.log(`${data.count} items updated`);
  // Frontend refetches data
});
```

## 📈 Performance Optimizations

### Backend Optimizations
- **Efficient change detection** using timestamps (not price comparison)
- **Batch database operations** to prevent DB overload
- **Async locks** to prevent concurrent API calls
- **Connection pooling** for database efficiency

### Frontend Optimizations
- **Smart memoization** with React.useMemo for filtering/sorting
- **Debounced search** to reduce re-renders
- **Conditional rendering** to minimize DOM updates
- **Responsive table** with virtual scrolling for large datasets

### Event-Driven Strategy
- **Redis pub/sub keyspace notifications** trigger proactive updates
- **TTL-based event scheduling** for consistent 2-minute cycles
- **Database as single source of truth** for all data queries
- **Graceful failure handling** maintains update cycles

## 🔧 Configuration

### Environment Variables

**Backend (`docker-compose.yml`)**
```yaml
environment:
  - DATABASE_URL=postgresql://osrs_user:osrs_password@postgres:5432/osrs_db
  - REDIS_URL=redis://redis:6379
  - CACHE_TTL=120  # 2 minutes
  - OSRS_API_TIMEOUT=30
```

**Frontend**
```yaml
environment:
  - REACT_APP_API_URL=http://localhost:8000
  - REACT_APP_WS_URL=http://localhost:8000
```

## 🏃‍♂️ Development

### Running Individual Services

**Backend Only**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:socket_app --reload --host 0.0.0.0 --port 8000
```

**Frontend Only**
```bash
cd frontend
npm install
npm start
```

### Database Migration
```bash
# Database initializes automatically via init.sql
# For manual setup:
docker exec -it osrs-postgres psql -U osrs_user -d osrs_db -f /docker-entrypoint-initdb.d/init.sql
```

## 📊 Monitoring & Debugging

### Health Monitoring
```bash
curl http://localhost:8000/api/health
```
**Response includes:** Architecture type, connected clients, system status

### Enhanced Logging & Monitoring
```bash
# Real-time price changes with item names
docker-compose logs backend -f | grep "📈 PRICE CHANGES\|Item.*:"

# System performance metrics
docker-compose logs backend -f | grep "✅ Retrieved\|📊 Updated\|📡 Notified"

# Monitor update cycles
docker-compose logs backend -f | grep "🔄 Proactive update cycle"

# Error monitoring
docker-compose logs backend -f | grep "ERROR\|WARNING\|❌\|⚠️"
```

### Service Logs
```bash
# View all services
docker-compose logs -f

# Backend with enhanced logging
docker-compose logs -f backend

# Frontend logs
docker-compose logs -f frontend
```

### Redis Pub/Sub Monitoring
```bash
# Connect to Redis
docker exec -it osrs-redis redis-cli

# Monitor keyspace notifications
> PSUBSCRIBE "__keyevent@0__:expired"

# Check cache status
> EXISTS osrs_price_cache
> TTL osrs_price_cache
```

### Market Activity Dashboard
```bash
# See which expensive items (1M+ GP) are changing
docker-compose logs backend | grep "Item.*:" | grep -E "1,000,000|2,000,000"

# Count price changes in last update
docker-compose logs backend | grep "Detected changes" | tail -1

# Monitor specific items (e.g., Dragon items)
docker-compose logs backend | grep -i "dragon"
```

## 🎯 Key Implementation Highlights

### Event-Driven Architecture Successfully Implemented ✅

1. **✅ API fetches from PostgreSQL** - Database is always source of truth
2. **✅ Frontend hits API on start** - Initial data load from DB
3. **✅ WebSocket connection** - Real-time communication established
4. **✅ Redis pub/sub keyspace notifications** - Proactive event-driven updates
5. **✅ TTL expiry triggers OSRS API** - Background price monitoring every 2 minutes
6. **✅ DB updates + WebSocket notify** - Changes propagate to frontend instantly
7. **✅ Frontend refetches on notification** - Live updates without refresh
8. **✅ Enhanced logging** - Complete visibility into market activity and system performance

### Efficient & Scalable Design

- **No DB explosion** - Timestamp comparison prevents unnecessary queries
- **Batch operations** - Multiple updates in single transactions
- **Non-blocking architecture** - Async operations maintain responsiveness
- **Proactive monitoring** - Always fresh data regardless of user activity
- **Event-driven updates** - Redis pub/sub eliminates polling overhead
- **Comprehensive logging** - Production-ready observability and debugging
- **Graceful error handling** - System continues operating during failures

## 🚀 Deployment

### Production Considerations

1. **Environment Configuration**
   - Use production database credentials
   - Configure CORS origins properly
   - Set secure Redis passwords

2. **Performance Tuning**
   - Adjust `CACHE_TTL` based on traffic
   - Scale database connections
   - Configure Redis memory limits

3. **Monitoring**
   - Set up health check monitoring
   - Log aggregation for debugging
   - Performance metrics collection

## 📄 API Data Sources

- **Items Mapping**: `https://prices.runescape.wiki/api/v1/osrs/mapping`
- **Latest Prices**: `https://prices.runescape.wiki/api/v1/osrs/latest`

*Data provided by the [Old School RuneScape Wiki](https://oldschool.runescape.wiki/)*

## 🎮 OSRS Context

RuneScape's Grand Exchange operates like a real-world stock market:
- **High Price** = Instant-buy price (what buyers will pay)
- **Low Price** = Instant-sell price (what sellers will accept)  
- **Timestamps** = When these prices were last seen
- **Price fluctuations** = Supply and demand dynamics

## 🤝 Contributing

This is a take-home assignment project demonstrating:
- Modern web development practices
- Real-time data architecture
- Efficient caching strategies
- Clean, maintainable code structure

## 📜 License

This project is for educational purposes. RuneScape is a trademark of Jagex Limited.

---

**🎯 Production-ready event-driven architecture with comprehensive monitoring and modern web technologies!** 
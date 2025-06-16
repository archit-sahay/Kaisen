# 🏰 OSRS Price Tracker

A real-time **Old School RuneScape (OSRS)** item price tracker that provides live Grand Exchange prices with automatic updates. Built with modern web technologies following a cache-driven architecture.

## 📋 Project Overview

This application implements a **live updating price table** for OSRS items that automatically reflects the latest prices from the Grand Exchange, ensuring users always see up-to-date information without manual refresh.

### 🎯 Key Features

- **📊 Live Price Updates** - Real-time price notifications via WebSocket
- **🔍 Advanced Filtering** - Search, sort, and filter by item properties
- **💎 Price Analysis** - High/low prices, trends, and market indicators
- **🏆 Item Categories** - Members vs Free-to-Play indicators
- **📱 Responsive Design** - Works seamlessly on desktop and mobile
- **⚡ Performance Optimized** - Efficient cache-driven updates

## 🏗️ Architecture Implementation

This project implements the **user's blueprint architecture**:

```
React Frontend ←→ WebSocket ←→ FastAPI Backend ←→ Redis Cache ←→ PostgreSQL
                     ↓              ↓
                Live Updates    OSRS APIs
```

### 🔄 Core Flow (User's Blueprint)

1. **Frontend hits API on start** - React loads initial data from PostgreSQL
2. **WebSocket connection established** - Real-time communication channel
3. **Backend caches data in Redis** - 2-minute TTL for efficient updates
4. **Cache expiry triggers OSRS API** - Automatic background price checking
5. **Database updates + WebSocket notify** - Changes trigger frontend refresh

### 🧠 Efficient Update Strategy

- **Timestamp-based change detection** - Prevents unnecessary database operations
- **Batch updates** - Efficient database writes for multiple items
- **Database as source of truth** - Redis only for timing/caching
- **Non-blocking updates** - Frontend remains responsive during updates

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
2. **Start Redis cache** with 2-minute TTL
3. **Launch FastAPI backend** with WebSocket support
4. **Serve React frontend** with live updates

## 🏛️ Technical Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **Socket.IO** - Real-time WebSocket communication
- **PostgreSQL** - Reliable data persistence
- **Redis** - High-performance caching layer
- **AsyncPG** - Async PostgreSQL driver

### Frontend
- **React 18** - Modern UI library with hooks
- **TypeScript** - Type-safe development
- **Socket.IO Client** - Real-time updates
- **Modern CSS** - Responsive design with gradients

### Infrastructure
- **Docker Compose** - Multi-service orchestration
- **Health Checks** - Service monitoring
- **CORS Configuration** - Cross-origin support

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
- `GET /api/items` - Fetch all items with prices (triggers cache check)
- `GET /api/items/{id}` - Get specific item details
- `GET /api/health` - System health and status
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

### Cache Strategy
- **Redis TTL control** determines API call frequency
- **Database fallback** when cache is unavailable
- **Memory cache backup** for Redis failures

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

### Logs
```bash
# View all services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Redis Monitoring
```bash
# Connect to Redis
docker exec -it osrs-redis redis-cli

# Check cache status
> EXISTS items_cache
> TTL items_cache
> GET items_cache
```

## 🎯 Key Implementation Highlights

### User's Blueprint Faithfully Implemented ✅

1. **✅ API fetches from PostgreSQL** - Database is always source of truth
2. **✅ Frontend hits API on start** - Initial data load from DB
3. **✅ WebSocket connection** - Real-time communication established
4. **✅ Redis cache with expiry** - 2-minute TTL controls update timing
5. **✅ Cache expiry triggers OSRS API** - Background price monitoring
6. **✅ DB updates + WebSocket notify** - Changes propagate to frontend
7. **✅ Frontend refetches on notification** - Live updates without refresh

### Efficient & Scalable Design

- **No DB explosion** - Timestamp comparison prevents unnecessary queries
- **Batch operations** - Multiple updates in single transactions
- **Non-blocking architecture** - Async operations maintain responsiveness
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

**🎯 Perfect implementation of the user's blueprint with modern web technologies!** 
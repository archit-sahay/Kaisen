"""
OSRS Price Tracker Backend
Event-Driven Architecture Implementation:
- API fetches from PostgreSQL (source of truth)  
- Frontend hits API on start + WebSocket connection
- Redis pub/sub triggers proactive OSRS API updates
- Cache expiry events drive price update cycles
- DB updates + WebSocket notify frontend to refetch
"""

"""
OSRS Price Tracker - Live updating RuneScape item prices
Author: Archit Sahay
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from config import PORT, CORS_ORIGINS
from database import OSRSDataManager
from socket_manager import sio, socket_manager
from routes import APIRoutes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize managers
data_manager = OSRSDataManager()
data_manager.socket_manager = socket_manager
api_routes = APIRoutes(data_manager)

# FastAPI Lifespan (modern approach)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    
    # Startup
    logger.info("Starting OSRS Price Tracker Backend with Event-Driven Architecture...")
    
    try:
        await data_manager.init_connections()
        await data_manager.startup_cache_population()
        logger.info("Backend started successfully with Redis pub/sub")
        
        yield  # Application runs here
        
    finally:
        # Shutdown
        logger.info("Shutting down backend...")
        await data_manager.close_connections()
        logger.info("Backend shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="OSRS Price Tracker API",
    description="Live updating RuneScape item prices with Event-Driven Redis Pub/Sub - By Archit Sahay",
    version="2.0.0",
    lifespan=lifespan
)

# Wrap with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routes
app.get("/")(api_routes.get_root)
app.get("/api/items")(api_routes.get_items)
app.get("/api/items/{item_id}")(api_routes.get_item)
app.get("/api/health")(api_routes.health_check)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(socket_app, host="0.0.0.0", port=PORT, log_level="info") 
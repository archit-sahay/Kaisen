import logging
from typing import List, Set
from datetime import datetime, timezone, timedelta

import socketio

logger = logging.getLogger(__name__)

class SocketManager:
    def __init__(self):
        self.connected_clients: Set[str] = set()
    
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

# Socket.IO server setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*"  # Configure for production
)

# Global socket manager instance
socket_manager = SocketManager()

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
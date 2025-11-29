from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        # user_id -> list of websockets
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a new websocket for a user"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Disconnect a websocket"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send message to a specific user's all connections"""
        if user_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for ws in disconnected:
                self.disconnect(ws, user_id)
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)

# Global connection manager
manager = ConnectionManager()

async def notify_pnl_update(user_id: int, pnl_data: dict):
    """Send P&L update to user"""
    await manager.send_personal_message({
        "type": "pnl_update",
        "data": pnl_data
    }, user_id)

async def notify_trade_execution(user_id: int, trade_data: dict):
    """Send trade execution notification to user"""
    await manager.send_personal_message({
        "type": "trade_executed",
        "data": trade_data
    }, user_id)

async def notify_position_closed(user_id: int, position_data: dict):
    """Send position closed notification to user"""
    await manager.send_personal_message({
        "type": "position_closed",
        "data": position_data
    }, user_id)

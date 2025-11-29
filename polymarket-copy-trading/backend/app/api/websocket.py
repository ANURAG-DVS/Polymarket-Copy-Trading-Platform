from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from app.core.websocket import manager
from app.core.security import verify_token
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint for real-time updates
    
    Connect with: ws://localhost:8000/ws?token=<jwt_token>
    """
    # Verify token
    payload = verify_token(token, settings.JWT_SECRET)
    
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    user_email = payload.get("sub")
    if not user_email:
        await websocket.close(code=1008, reason="Invalid token payload")
        return
    
    # For simplicity, we'll use email as identifier
    # In production, you'd want to look up user_id from database
    # For now, we'll extract a numeric id (you should modify this)
    user_id = 1  # TODO: Get actual user_id from database using user_email
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive messages (for ping/pong or client commands)
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket disconnected for user {user_id}")

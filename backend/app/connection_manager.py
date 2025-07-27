from fastapi import WebSocket
from typing import List
import logging
import json
import asyncio
from app.database import get_redis_connection_websocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self.redis_conn = get_redis_connection_websocket()
        self._subscriber_task = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected. Total connections: {len(self.active)}")
        
        # Start Redis subscriber if not already running
        if self._subscriber_task is None or self._subscriber_task.done():
            self._subscriber_task = asyncio.create_task(self._redis_subscriber())

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active)}")

    async def broadcast(self, msg: dict):
        """Broadcast message to all connected clients"""
        if not self.active:
            return
        
        disconnected = []
        for connection in self.active:
            try:
                await connection.send_json(msg)
            except Exception as e:
                logger.warning(f"Failed to send message to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected: # type: ignore
            self.disconnect(connection)

    async def send_personal_message(self, message: dict, websocket: WebSocket): # type: ignore
        """Send message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def _redis_subscriber(self):
        """Subscribe to Redis channel for progress updates"""
        try:
            pubsub = self.redis_conn.pubsub()
            pubsub.subscribe("research_progress")
            logger.info("📡 Redis subscriber started")
            
            while True:
                try:
                    message = pubsub.get_message(timeout=1.0)
                    if message and message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            await self.broadcast(data)
                            logger.debug(f"Broadcasted: {data}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing Redis message: {e}")
                    
                    await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                    
                except Exception as e:
                    logger.error(f"Error in Redis subscriber: {e}")
                    await asyncio.sleep(1)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Redis subscriber crashed: {e}")
        finally:
            logger.info("📡 Redis subscriber stopped")

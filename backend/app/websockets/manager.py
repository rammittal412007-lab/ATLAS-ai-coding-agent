import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Set

import structlog
from fastapi import WebSocket

from app.core.redis import redis_client

logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[str, Set[WebSocket]] = {}
        self._socket_rooms: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self._rooms:
            self._rooms[task_id] = set()
        self._rooms[task_id].add(websocket)
        self._socket_rooms[websocket] = task_id

    def disconnect(self, websocket: WebSocket):
        task_id = self._socket_rooms.pop(websocket, None)
        if task_id and task_id in self._rooms:
            self._rooms[task_id].discard(websocket)
            if not self._rooms[task_id]:
                del self._rooms[task_id]

    async def send_to_task(self, task_id: str, event: Dict[str, Any]):
        if task_id not in self._rooms:
            return
        payload = json.dumps(event, default=str)
        dead = set()
        for ws in list(self._rooms[task_id]):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._rooms.values())


ws_manager = ConnectionManager()


class TaskEventPublisher:
    def __init__(self, task_id: str):
        self.task_id = task_id

    async def __call__(self, event: Dict[str, Any]):
        await self.publish(event)

    async def publish(self, event: Dict[str, Any]):
        event.setdefault("timestamp", datetime.utcnow().isoformat())
        event.setdefault("task_id", self.task_id)
        await ws_manager.send_to_task(self.task_id, event)
        try:
            await redis_client.publish(f"task:{self.task_id}:events", event)
        except Exception:
            pass

    async def publish_log(self, message: str, level: str = "info"):
        await self.publish({"type": "execution_log", "data": {"message": message, "level": level}})

    async def publish_agent_thought(self, agent: str, thought: str):
        await self.publish({"type": "agent_thought", "agent_type": agent, "data": {"message": thought}})

    async def publish_task_status(self, status: str, details: Any = None):
        await self.publish({"type": "task_status", "data": {"status": status, "details": details}})


class RedisEventForwarder:
    def __init__(self):
        self._subscriptions: Dict[str, asyncio.Task] = {}

    async def subscribe_task(self, task_id: str):
        if task_id in self._subscriptions:
            return

        async def forward():
            async for event in redis_client.subscribe(f"task:{task_id}:events"):
                await ws_manager.send_to_task(task_id, event)

        task = asyncio.create_task(forward())
        self._subscriptions[task_id] = task

    def unsubscribe_task(self, task_id: str):
        if task_id in self._subscriptions:
            self._subscriptions[task_id].cancel()
            del self._subscriptions[task_id]


redis_forwarder = RedisEventForwarder()

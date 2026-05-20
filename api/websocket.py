"""WebSocket endpoint — streams LOG_QUEUE events to connected clients."""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.bot_runner import LOG_QUEUE

router = APIRouter()
_clients: list = []


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    _clients.append(websocket)
    try:
        while True:
            # Drain the queue
            drained = False
            while not LOG_QUEUE.empty():
                try:
                    entry = LOG_QUEUE.get_nowait()
                    await websocket.send_text(json.dumps(entry))
                    drained = True
                except Exception:
                    break
            if not drained:
                await asyncio.sleep(0.2)
            # Keep connection alive
            try:
                # Non-blocking receive — just to detect disconnect
                await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in _clients:
            _clients.remove(websocket)

"""WebSocket endpoint — streams LOG_QUEUE events to connected clients."""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from api.bot_runner import LOG_QUEUE
from api.security import verify_token

router = APIRouter()
_clients: list = []


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket, token: str = Query(default="")):
    # Require a valid session token before accepting the connection
    if not verify_token(token):
        await websocket.close(code=1008)  # 1008 = Policy Violation
        return

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
            # Keep connection alive / detect disconnect
            try:
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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/realtime")
async def realtime(ws: WebSocket):
    # Phase 5: proxy to GPT Realtime 2
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            # Echo back for now
            await ws.send_text(f"[mock realtime] received: {data}")
    except WebSocketDisconnect:
        pass

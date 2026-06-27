"""
Proxy WebSocket — endpoint FastAPI que orquestra handshake e relay.

Fluxo :
  1. perform_handshake  → aceita conexão, valida JWT e identidade
  2. open_upstream      → abre conexão com o Game Service
  3. Duas tasks asyncio → relay bidirecional opaco de frames STOMP
  4. Primeira task a encerrar → cancela a outra e fecha upstream
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket

from app.api.websocket.frame_relay import (
    open_upstream,
    relay_client_to_upstream,
    relay_upstream_to_client,
)
from app.api.websocket.handshake import perform_handshake

router = APIRouter()


@router.websocket("/ws/rooms/{code}")
async def ws_proxy(websocket: WebSocket, code: str) -> None:
    """
    Endpoint WebSocket do Gateway — /ws/rooms/{code}

    O path parameter {code} roteia a conexão; o room-code efetivo
    é lido do frame STOMP CONNECT pelo handshake.py
    """
    # passos 1–3: aceitar, validar JWT e identidade
    result = await perform_handshake(websocket)
    if result is None:
        return  # rejeitado no handshake; frame de erro já enviado e conexão fechada

    # passo 4: abrir conexão upstream com o Game Service
    try:
        upstream = await open_upstream(result)
    except Exception:
        await websocket.send_text(
            json.dumps({
                "type": "error",
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "Game Service indisponível",
            })
        )
        await websocket.close()
        return

    # passo 5: relay bidirecional opaco de frames STOMP
    task_c2u = asyncio.create_task(relay_client_to_upstream(websocket, upstream))
    task_u2c = asyncio.create_task(relay_upstream_to_client(upstream, websocket))

    try:
        # aguarda a primeira task encerrar  qualquer lado que fechar a conexão
        await asyncio.wait(
            [task_c2u, task_u2c],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # cancela a task que ainda está rodando
        for task in (task_c2u, task_u2c):
            if not task.done():
                task.cancel()
        await asyncio.gather(task_c2u, task_u2c, return_exceptions=True)
    finally:
        await upstream.close()
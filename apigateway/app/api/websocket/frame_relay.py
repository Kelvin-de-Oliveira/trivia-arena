"""
Relay de frames WebSocket : abre conexão com o Game Service e repassa
frames nos dois sentidos sem inspecionar o conteúdo STOMP.

Responsabilidades deste módulo:
  - Abrir a conexão upstream e enviar o STOMP CONNECT traduzido
  - Fornecer as duas corrotinas de relay que serão executadas como tasks
    pelo ws_proxy.py 

O cancelamento de tasks e o fechamento da conexão upstream são
responsabilidade do ws_proxy.py
"""

import websockets
from fastapi import WebSocket

from app.api.websocket.handshake import HandshakeResult
from app.core.config import settings


async def open_upstream(result: HandshakeResult):
    """
    abre conexão WebSocket com o Game Service e envia o
    frame STOMP CONNECT já traduzido (player-id, room-code, authenticated).

    Retorna a conexão aberta. O caller (ws_proxy.py) é responsável
    por fechá-la após encerrar as tasks de relay.
    """
    upstream = await websockets.connect(settings.game_ws_url)
    await upstream.send(result.upstream_connect_frame)
    return upstream


async def relay_client_to_upstream(client: WebSocket, upstream) -> None:
    """
    repassa frames do cliente para o Game Service.

    Usa client.receive() de baixo nível para lidar com frames de texto
    e binários sem assumir o tipo. Encerra quando o cliente fecha a
    conexão ou quando a task é cancelada pelo ws_proxy.py.
    """
    try:
        while True:
            data = await client.receive()
            if data.get("type") == "websocket.disconnect":
                break
            if text := data.get("text"):
                await upstream.send(text)
            elif raw := data.get("bytes"):
                await upstream.send(raw)
    except Exception:
        pass


async def relay_upstream_to_client(upstream, client: WebSocket) -> None:
    """
    repassa frames do Game Service para o cliente.

    A iteração assíncrona do websockets termina naturalmente quando o
    upstream fecha. Frames de texto e binários são repassados conforme
    o tipo recebido. Encerra quando o upstream fecha ou quando a task
    é cancelada pelo ws_proxy.py.
    """
    try:
        async for message in upstream:
            if isinstance(message, str):
                await client.send_text(message)
            else:
                await client.send_bytes(message)
    except Exception:
        pass
"""Bound the internal catalog JSON request before FastAPI parses it."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.responses import JSONResponse

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Message, Receive, Send], Awaitable[None]]
MAX_CATALOG_REQUEST_BYTES = 512 * 1024


class CatalogRequestLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Message, receive: Receive, send: Send) -> None:
        if not (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/v1/recommendations/baseline"
        ):
            await self.app(scope, receive, send)
            return

        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_CATALOG_REQUEST_BYTES:
                await JSONResponse(
                    status_code=413,
                    content={"detail": "Catalog request exceeds 524288 bytes"},
                )(scope, receive, send)
                return
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                break

        buffered = b"".join(chunks)
        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)

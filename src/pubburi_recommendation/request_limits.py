"""Bound the internal catalog JSON request before FastAPI parses it."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.responses import JSONResponse

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Message, Receive, Send], Awaitable[None]]
MAX_CATALOG_REQUEST_BYTES = 512 * 1024
CATALOG_BODY_TIMEOUT_SECONDS = 10.0
CATALOG_PATHS = {"/v1/recommendations/baseline", "/v1/recommendations/content"}


class CatalogRequestLimit:
    def __init__(
        self, app: ASGIApp, body_timeout_seconds: float = CATALOG_BODY_TIMEOUT_SECONDS
    ) -> None:
        self.app = app
        self.body_timeout_seconds = body_timeout_seconds

    async def __call__(self, scope: Message, receive: Receive, send: Send) -> None:
        if not (
            scope["type"] == "http" and scope["method"] == "POST" and scope["path"] in CATALOG_PATHS
        ):
            await self.app(scope, receive, send)
            return

        chunks = []
        size = 0
        try:
            # One absolute budget: trickling chunks cannot extend the body deadline.
            async with asyncio.timeout(self.body_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > MAX_CATALOG_REQUEST_BYTES:
                        break
                    if chunk:
                        chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse(
                status_code=408, content={"detail": "Catalog request body timed out"}
            )(scope, receive, send)
            return

        if size > MAX_CATALOG_REQUEST_BYTES:
            await JSONResponse(
                status_code=413,
                content={"detail": "Catalog request exceeds 524288 bytes"},
            )(scope, receive, send)
            return

        buffered = b"".join(chunks)
        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)

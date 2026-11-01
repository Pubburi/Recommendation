"""Bound the internal catalog JSON request before FastAPI parses it."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from email.message import Message as MimeMessage
from typing import Any

from fastapi.responses import JSONResponse

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Message, Receive, Send], Awaitable[None]]
MAX_CATALOG_REQUEST_BYTES = 512 * 1024
CATALOG_BODY_TIMEOUT_SECONDS = 10.0
CATALOG_PATHS = {
    "/v1/recommendations/baseline",
    "/v1/recommendations/content",
    "/v1/recommendations/exploration",
}


def json_media_type(scope: Message) -> bool:
    content_type = next(
        (
            value.decode("latin-1")
            for name, value in scope.get("headers", [])
            if name == b"content-type"
        ),
        None,
    )
    if content_type is None:
        return True  # Match FastAPI's JSON handling when the content type is absent.
    mime = MimeMessage()
    mime["content-type"] = content_type
    return mime.get_content_maintype() == "application" and (
        mime.get_content_subtype() == "json" or mime.get_content_subtype().endswith("+json")
    )


def duplicate_json_keys(body: bytes) -> bool:
    duplicate = False

    def unique_object(pairs):
        nonlocal duplicate
        values = {}
        for key, value in pairs:
            if key in values:
                duplicate = True
            values[key] = value
        return values

    try:
        # Object hooks see decoded names, so escaped equivalent keys cannot evade this check.
        # Discard this bounded preflight tree; FastAPI still owns schema/numeric validation.
        json.loads(body, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError):
        # Malformed encodings/syntax/depth keep the framework's existing client-error behavior.
        # A duplicate found before a later parse error must not mask that error.
        return False
    return duplicate


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
        if json_media_type(scope) and duplicate_json_keys(buffered):
            await JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {
                            "type": "duplicate_json_key",
                            "loc": ["body"],
                            "msg": "Catalog JSON object keys must be unique",
                        }
                    ]
                },
            )(scope, receive, send)
            return
        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)

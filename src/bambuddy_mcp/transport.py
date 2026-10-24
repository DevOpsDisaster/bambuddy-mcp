"""Authenticated Streamable HTTP transport for long-running containers."""

import secrets
from contextlib import asynccontextmanager

from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send


def create_http_app(server: Server, token: str) -> Starlette:
    """Serve the existing MCP tools at /mcp with bearer authentication."""
    if not token.strip():
        raise ValueError("An HTTP authentication token is required")
    manager = StreamableHTTPSessionManager(
        app=server, json_response=True, stateless=True
    )

    async def mcp_endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"")
        scheme, _, supplied_token = authorization.partition(b" ")
        if scheme.lower() != b"bearer" or not secrets.compare_digest(
            supplied_token, token.encode("utf-8")
        ):
            response = JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="bambuddy-mcp"'},
            )
            await response(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)

    async def health(request):
        return JSONResponse({"status": "ok"})

    class MCPEndpoint:
        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            await mcp_endpoint(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    return Starlette(
        routes=[
            Route("/mcp", endpoint=MCPEndpoint(), methods=["GET", "POST", "DELETE"]),
            Route("/healthz", endpoint=health, methods=["GET"]),
        ],
        lifespan=lifespan,
    )

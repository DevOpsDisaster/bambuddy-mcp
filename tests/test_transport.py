"""Exercise authentication and the real MCP HTTP protocol."""

import pytest
from mcp.server.lowlevel import Server
from mcp.types import TextContent, Tool
from starlette.testclient import TestClient

from bambuddy_mcp.transport import create_http_app


@pytest.fixture
def client():
    server = Server("test-bambuddy")

    @server.list_tools()
    async def list_tools():
        return [Tool(name="hello", inputSchema={"type": "object"})]

    @server.call_tool()
    async def call_tool(name, arguments):
        return [TextContent(type="text", text="hello from bambuddy")]

    with TestClient(create_http_app(server, "test-secret")) as client:
        yield client


@pytest.mark.parametrize("method", ["get", "post", "delete"])
@pytest.mark.parametrize("auth", [None, "Bearer wrong", "Basic test-secret"])
def test_rejects_unauthorized_requests(client, method, auth):
    headers = {"Authorization": auth} if auth else {}
    response = client.request(method, "/mcp", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer ")


def test_health_is_available_without_token(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protocol_initialize_list_and_call(client):
    headers = {
        "Authorization": "bearer test-secret",
        "Accept": "application/json, text/event-stream",
    }

    def rpc(method, params):
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        assert response.status_code == 200, response.text
        return response.json()["result"]

    initialized = rpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    )
    assert initialized["serverInfo"]["name"] == "test-bambuddy"
    assert rpc("tools/list", {})["tools"][0]["name"] == "hello"
    result = rpc("tools/call", {"name": "hello", "arguments": {}})
    assert result["content"][0]["text"] == "hello from bambuddy"


def test_empty_token_is_rejected():
    with pytest.raises(ValueError, match="token"):
        create_http_app(Server("test"), "")

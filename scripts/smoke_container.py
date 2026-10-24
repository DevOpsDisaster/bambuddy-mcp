"""Run a real Docker image against a disposable fake Bambuddy API in CI."""

import json
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Smoke test", "version": "1"},
    "paths": {
        "/api/v1/printers/": {
            "get": {
                "operationId": "list_printers",
                "tags": ["Printers"],
                "summary": "List printers",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}


class FakeBambuddy(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/openapi.json":
            body = SPEC
        elif self.path == "/api/v1/printers/":
            if self.headers.get("X-API-Key") != "upstream-test-key":
                self.send_error(401)
                return
            body = [{"id": 1, "name": "Smoke printer", "access_code": "12345678"}]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


def main():
    image = sys.argv[1]
    token = secrets.token_hex(32)
    name = "bambuddy-smoke-" + secrets.token_hex(4)
    upstream = ThreadingHTTPServer(("0.0.0.0", 0), FakeBambuddy)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=128m,mode=1777",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--add-host",
                "host.docker.internal:host-gateway",
                "--publish",
                "127.0.0.1::8000",
                "--env",
                f"BAMBUDDY_URL=http://host.docker.internal:{upstream.server_port}",
                "--env",
                "BAMBUDDY_API_KEY=upstream-test-key",
                "--env",
                f"BAMBUDDY_MCP_TOKEN={token}",
                image,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        port = (
            subprocess.check_output(["docker", "port", name, "8000/tcp"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        base = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                with urlopen(base + "/healthz", timeout=1) as response:
                    assert json.load(response) == {"status": "ok"}
                break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(1)
        else:
            raise RuntimeError("Container did not become ready")

        try:
            urlopen(base + "/mcp", timeout=5)
        except HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError("Unauthenticated MCP access was allowed")

        def rpc(method, params):
            request = Request(
                base + "/mcp",
                data=json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
                ).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            with urlopen(request, timeout=10) as response:
                return json.load(response)["result"]

        assert (
            rpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "docker-smoke", "version": "1"},
                },
            )["serverInfo"]["name"]
            == "bambuddy"
        )
        tools = rpc("tools/list", {})["tools"]
        assert {t["name"] for t in tools} == {
            "list_categories",
            "search_tools",
            "execute_tool",
            "find_printer",
        }
        result = rpc(
            "tools/call",
            {"name": "execute_tool", "arguments": {"name": "list_printers"}},
        )
        printers = json.loads(result["content"][0]["text"])
        assert printers[0]["name"] == "Smoke printer"
        assert printers[0]["access_code"] == "********"
        uid = subprocess.check_output(
            ["docker", "exec", name, "id", "-u"], text=True
        ).strip()
        assert uid == "10001"
        print(
            "Container smoke test passed: auth, MCP tools, API key, censoring, non-root."
        )
    finally:
        subprocess.run(["docker", "logs", name], check=False)
        subprocess.run(["docker", "rm", "--force", name], check=False)
        upstream.shutdown()
        upstream.server_close()


if __name__ == "__main__":
    main()

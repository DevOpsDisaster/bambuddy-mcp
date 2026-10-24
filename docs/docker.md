# Docker, Unraid and Paperclip

The image connects to your **existing Bambuddy** and exposes its tools over
Streamable HTTP at `/mcp`. It does not install Bambuddy itself. Both `linux/amd64`
and `linux/arm64` are supported.

```text
ghcr.io/devopsdisaster/bambuddy-mcp:latest
```

GitHub Actions tests, builds and publishes this image on pushes to `main`.
Version tags such as `v0.2.1` also publish an image tagged `0.2.1`; use a version
tag or digest if you want to pin a deployment. Pull requests build both
architectures and test a running container without publishing an image.

## Unraid Docker tab

You can add the container manually in **Docker → Add Container**:

| Setting | Value |
| --- | --- |
| Name | `bambuddy-mcp` |
| Repository | `ghcr.io/devopsdisaster/bambuddy-mcp:latest` |
| Network Type | `bridge` |
| Port, host → container | `8091` → `8000`, TCP |
| Variable `BAMBUDDY_URL` | Your Bambuddy LAN URL, e.g. `http://192.168.1.10:8000` |
| Variable `BAMBUDDY_API_KEY` | Key from Bambuddy Settings, if authentication is enabled |
| Variable `BAMBUDDY_MCP_TOKEN` | A new, separate random secret for Paperclip |

Generate the MCP secret in the Unraid terminal:

```sh
openssl rand -hex 32
```

Alternatively, install the supplied template by running these two commands in
the Unraid terminal, then select **bambuddy-mcp** in **Add Container → Template**:

```sh
mkdir -p /boot/config/plugins/dockerMan/templates-user
curl -fL https://raw.githubusercontent.com/DevOpsDisaster/bambuddy-mcp/main/unraid/bambuddy-mcp.xml -o /boot/config/plugins/dockerMan/templates-user/my-bambuddy-mcp.xml
```

The template runs the container as user `10001`, with a read-only filesystem and
a 128 MB temporary directory. No persistent appdata mapping is required. API
uploads can optionally use a separately mounted folder; file paths then refer
to files inside the MCP container.

`localhost` inside this container refers to the MCP container itself. Use the
NAS LAN address and Bambuddy's published port, or the Bambuddy container name
and internal port if both containers share a custom Docker network.

## Docker Compose

Download `compose.yaml` and `.env.example`, or clone this fork:

```sh
git clone https://github.com/DevOpsDisaster/bambuddy-mcp.git
cd bambuddy-mcp
cp .env.example .env
```

Edit `.env` with your Bambuddy URL, optional Bambuddy API key and new MCP token:

```dotenv
BAMBUDDY_URL=http://192.168.1.10:8000
BAMBUDDY_API_KEY=your-bambuddy-api-key
BAMBUDDY_MCP_TOKEN=your-separate-random-mcp-secret
BAMBUDDY_MCP_HOST_PORT=8091
```

Start it:

```sh
docker compose up -d
docker compose logs --tail=50 bambuddy-mcp
```

Update it:

```sh
docker compose pull
docker compose up -d
```

The container exits if Bambuddy cannot be reached at startup. The restart policy
retries automatically. `/healthz` reports that the MCP process is ready after
loading the API specification; it does not continuously check Bambuddy.

## Paperclip

Use this URL, replacing `NAS-IP` with your NAS address:

```text
http://NAS-IP:8091/mcp
```

In versions with the Connectors interface, choose **Connect your own MCP server**
(or **Connect an app → Connect with a link**), enter the URL, and supply the
`BAMBUDDY_MCP_TOKEN` value as the app key / bearer token. The resulting header is:

```text
Authorization: Bearer <BAMBUDDY_MCP_TOKEN>
```

The Bambuddy API key stays in the MCP container. Paperclip uses the separate
MCP token. Paperclip must be able to reach the NAS from its own container or
server. Keep this endpoint on your trusted LAN or VPN; use HTTPS if routing
through a reverse proxy or across an untrusted network.

If you configure MCP through an agent runtime instead, use that runtime's HTTP
MCP configuration with the same URL and Authorization header. For example:

```json
{
  "mcpServers": {
    "bambuddy": {
      "type": "http",
      "url": "http://NAS-IP:8091/mcp",
      "headers": {"Authorization": "Bearer <BAMBUDDY_MCP_TOKEN>"}
    }
  }
}
```

Default mode exposes four discovery/execution tools. Calls to `execute_tool`
can perform both read and write operations, so Paperclip cannot distinguish
individual Bambuddy actions behind that tool. To list and govern actions
individually, set `BAMBUDDY_DIRECT_MODE=true`, restart the container and refresh
actions in Paperclip. This exposes the full API and uses more context.

Image responses are embedded by default over HTTP so Paperclip can receive
them without access to files inside the container. Existing censoring settings
still apply. Stdio retains its previous default of saving images to disk.

Paperclip references:
[custom MCP connections](https://docs.paperclip.ing/connectors/custom-mcp-servers/),
[agent runtime MCP configuration](https://docs.paperclip.ing/how-to/add-mcp-server-to-agent/).

## Build locally

```sh
docker build -t bambuddy-mcp:local .
```

For a Compose deployment using your local build, set the `image` in
`compose.yaml` to `bambuddy-mcp:local` before starting it.

The original stdio interface is also available for clients that launch Docker:

```sh
docker run --rm -i --health-cmd=none \
  -e BAMBUDDY_MCP_TRANSPORT=stdio \
  -e BAMBUDDY_URL=http://NAS-IP:8000 \
  -e BAMBUDDY_API_KEY \
  ghcr.io/devopsdisaster/bambuddy-mcp:latest
```

Use `-i` without `-t` for stdio. HTTP mode needs neither an open stdin nor a TTY.

## Troubleshooting

- **401 Unauthorized:** Paperclip's bearer token must match `BAMBUDDY_MCP_TOKEN`.
- **Container keeps restarting:** check logs and verify the Bambuddy URL,
  port and `/openapi.json` are reachable from the container's network.
- **401/403 from a tool call:** verify `BAMBUDDY_API_KEY` and its permissions
  in Bambuddy; this is distinct from the MCP access token.
- **Connection refused:** publish container port `8000` and use the host port
  (`8091` by default) in Paperclip.
- **Image pull denied:** GitHub may initially create the GHCR package as private.
  The repository owner can make it public under **Packages → bambuddy-mcp →
  Package settings → Change visibility → Public**, or authenticate the NAS to
  GHCR with a token granting `read:packages`.

# **Home Assistant MCP** | [中文版本](README.md)

- Integrates with Home Assistant via MCP to fetch device context and control devices (switches and light brightness).
- Automatically obtains/creates a long-lived access token and installs/detects the `mcp_server` integration.
- Ships a lightweight MCP server that wraps upstream Home Assistant tools and exposes simpler interfaces.
- License: MIT. Switch to Chinese README: `README.md`.

**Features**
- Token automation: creates a long-lived token named `mcp` and caches it at `./.cache/token.txt`.
- Integration automation: detects and installs the `mcp_server` integration in Home Assistant.
- Context fetching: pulls live device context (YAML) and generates stable `id` (MD5 of device names).
- Device control: batch control by device `id` (switch on/off, set light brightness).

**Architecture**
- Upstream: Home Assistant's `mcp_server` integration exposes MCP tools (`GetLiveContext`, `HassTurnOn`, `HassTurnOff`, `HassLightSet`).
- Middle layer: this project connects upstream as an MCP client and exposes simplified tools to downstream as an MCP server (`get_device_info`, `switch_control`, `light_set`).
- Connectivity:
  - To upstream Home Assistant: SSE (`{HOME_ASSISTANT_URL}/mcp_server/sse` with `Authorization: Bearer <token>` header).
  - To downstream clients: default MCP process `stdio` mode (decided by `fastmcp`); the SSE endpoint is provided by Home Assistant integration.

**Requirements**
- Python `>=3.11`
- A running Home Assistant instance reachable via its URL (defaults to `http://127.0.0.1:8123`)

**Installation**
- From project root:
  - `pip install .`
  - Or build with Hatch: `pip install hatch` → `hatch build` → install the artifact

**Quick Start**
- Environment variables (optional, all have defaults):
  - `HOME_ASSISTANT_USERNAME` default `admin`
  - `HOME_ASSISTANT_PASSWORD` default `admin123`
  - `HOME_ASSISTANT_URL` default `http://127.0.0.1:8123`
  - `HOME_ASSISTANT_CACHE_DIR` default `./.cache`
- One command start:
  - `home-assistant-mcp`
  - Equivalent to invoking `home_assistant_mcp:main`, which:
    - Gets/creates the long-lived token
    - Ensures `mcp_server` integration is installed
    - Runs an MCP server and connects to upstream Home Assistant SSE endpoint
- Preparation only (create token and set up integration):
  - `python -m home_assistant_mcp.home_assistant_setup`

**Exposed MCP tools (downstream)**
- `get_device_info()`: force refresh and return device list (`id`, `names`, `areas`, etc.).
- `switch_control(id: List[str], on: bool)`: batch on/off by device `id`.
- `light_set(id: List[str], brightness: Optional[int])`: set brightness `0-100`; `None` means off.

**Usage Examples**
- Use an MCP client that supports process `stdio` mode and point it to the command `home-assistant-mcp`.
- Fetch devices: call `get_device_info` and store returned `id`s.
- Control devices: pass target device `id`s to `switch_control` or `light_set`.

**Env & Cache**
- Token file: `./.cache/token.txt`.
- Override cache directory: `HOME_ASSISTANT_CACHE_DIR`.
- Token source: read from cache first; if missing, obtain via `HOME_ASSISTANT_USERNAME/PASSWORD` at `HOME_ASSISTANT_URL`.

**Code References**
- Entry point: `src/home_assistant_mcp/__init__.py:6` (`main()`)
- Token & integration: `src/home_assistant_mcp/home_assistant_setup.py:18` (`get_or_create_long_token`), `227` (sync wrapper)
- Controller: `src/home_assistant_mcp/mcp_server.py:15` (`HomeAssistantController`)
- Tool registration & server: `src/home_assistant_mcp/mcp_server.py:226` (`MCPHomeAssistantServer`), `292` (`run()`)
- Project script entry: `pyproject.toml:15-16`

**Troubleshooting**
- Auth error: delete cache `./.cache/token.txt` and retry; verify username/password and `HOME_ASSISTANT_URL`.
- SSE connectivity: ensure `mcp_server` integration is installed and enabled in Home Assistant; check network reachability.
- Missing devices: if `get_device_info` returns empty or lacks your targets, review naming and areas in Home Assistant.

**Security**
- Do not commit real tokens; use `.cache/` and `.gitignore` to avoid leaks.
- Prefer strong passwords and HTTPS (`wss://`) in production.

**License**
- Released under the MIT License.

**Switch Language**
- Chinese README: `README.md`

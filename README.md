# **Home Assistant MCP** | [English Version](README_EN.md)

- 通过 MCP 协议与 Home Assistant 集成，获取设备上下文并进行控制（开关、灯光亮度）。
- 自动获取/创建长期访问令牌，自动安装/检测 `mcp_server` 集成，开箱即用。
- 提供一个轻量 MCP 服务，封装上游 Home Assistant 的原生工具并提供更易用的接口。
- 开源协议：MIT。可点击切换英文文档：`README_EN.md`。

**功能特性**
- 自动令牌管理：创建名为 `mcp` 的长期令牌并缓存到 `./.cache/token.txt`。
- 集成管理：检测并安装 Home Assistant 的 `mcp_server` 集成。
- 上下文获取：从 Home Assistant 拉取实时设备上下文（YAML），生成稳定 `id`（设备名 MD5）。
- 设备控制：按 `id` 批量控制开关与灯光亮度。

**架构概览**
- 上游：Home Assistant 提供的 `mcp_server` 集成暴露 MCP 工具（`GetLiveContext`、`HassTurnOn`、`HassTurnOff`、`HassLightSet`）。
- 中间层：本项目以 MCP 客户端身份连接上游，并以 MCP 服务身份对外提供简化工具（`get_device_info`、`switch_control`、`light_set`）。
- 连接方式：
  - 到上游 Home Assistant：SSE（`{HOME_ASSISTANT_URL}/mcp_server/sse` + `Authorization: Bearer <token>`）。
  - 对下游客户端：默认使用 MCP 标准的进程 `stdio` 运行模式（由 `fastmcp` 决定）；SSE 端点由 Home Assistant 集成提供。

**系统要求**
- Python `>=3.11`
- 运行中的 Home Assistant 实例，且可访问其 URL（本地默认 `http://127.0.0.1:8123`）

**安装**
- 在项目根目录执行：
  - `pip install .`
  - 或使用 Hatch 构建：`pip install hatch` → `hatch build` → 安装产物

**快速开始**
- 配置环境变量（可选，均有默认值）：
  - `HOME_ASSISTANT_USERNAME` 默认 `admin`
  - `HOME_ASSISTANT_PASSWORD` 默认 `admin123`
  - `HOME_ASSISTANT_URL` 默认 `http://127.0.0.1:8123`
  - `HOME_ASSISTANT_CACHE_DIR` 默认 `./.cache`
- 一键启动：
  - `home-assistant-mcp`
  - 等价于调用 `home_assistant_mcp:main`，会：
    - 获取/创建长期令牌
    - 确保安装 `mcp_server` 集成
    - 作为 MCP 服务运行，并连接到上游 Home Assistant 的 SSE 端点
- 仅做准备（只创建令牌并安装集成）：
  - `python -m home_assistant_mcp.home_assistant_setup`

**MCP 工具一览（对下游提供）**
- `get_device_info()`：强制刷新并返回设备列表（含 `id`、`names`、`areas` 等）。
- `switch_control(id: List[str], on: bool)`：按设备 `id` 批量开/关。
- `light_set(id: List[str], brightness: Optional[int])`：设置亮度 `0-100`；`None` 表示关闭。

**用法示例**
- 通过支持进程型 MCP 的客户端运行本服务（例如把命令配置为 `home-assistant-mcp`）。
- 获取设备：调用 `get_device_info`，保存返回的 `id`。
- 控制设备：将目标设备 `id` 列表传给 `switch_control` 或 `light_set`。

**环境变量与缓存**
- 令牌文件：`./.cache/token.txt`。
- 修改默认目录：通过 `HOME_ASSISTANT_CACHE_DIR`。
- 令牌来源：优先读取缓存；若不存在则使用 `HOME_ASSISTANT_USERNAME/PASSWORD` 到 `HOME_ASSISTANT_URL` 获取。

**代码定位**
- 入口：`src/home_assistant_mcp/__init__.py:6`（`main()`）
- 令牌与集成：`src/home_assistant_mcp/home_assistant_setup.py:18`（`get_or_create_long_token`）、`227`（同步封装）
- 控制器：`src/home_assistant_mcp/mcp_server.py:15`（`HomeAssistantController`）
- 工具注册与服务：`src/home_assistant_mcp/mcp_server.py:226`（`MCPHomeAssistantServer`），`292`（`run()`）
- 项目脚本入口：`pyproject.toml:15-16`

**故障排查**
- 认证错误：删除缓存 `./.cache/token.txt` 后重试；检查用户名/密码与 `HOME_ASSISTANT_URL`。
- SSE 不通：确认 Home Assistant 中已安装并启用 `mcp_server` 集成；查看网络连通性。
- 设备缺失：`get_device_info` 返回为空或不含目标设备时，检查 Home Assistant 的设备命名与区域。

**安全建议**
- 不要提交真实令牌到代码仓库；建议使用 `.cache/` 与 `.gitignore` 避免泄露。
- 生产环境请使用更强口令与 HTTPS（`wss://` WebSocket）。

**许可证**
- 本项目采用 MIT 许可协议发布。

**切换语言**
- 英文版文档：`README_EN.md`

from home_assistant_sdk import (
    HomeAssistantAuth,
    HAWebSocketClient,
    HomeAssistantIntegrationFlow,
    MCPServerIntegration,
    HAAuthError,
)
import asyncio
import logging
import os

home_assistant_username = os.getenv("HOME_ASSISTANT_USERNAME", "admin")
home_assistant_password = os.getenv("HOME_ASSISTANT_PASSWORD", "admin123")
home_assistant_url = os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123")
home_assistant_cache_dir = os.getenv("HOME_ASSISTANT_CACHE_DIR", "./.cache")


async def get_or_create_long_token():
    """
    获取或创建Home Assistant的长期访问令牌，并设置MCP集成。
    
    该函数执行以下操作：
    1. 确保缓存目录存在
    2. 尝试从缓存文件读取现有令牌，如果没有则通过认证获取
    3. 建立WebSocket连接到Home Assistant
    4. 如果没有缓存的MCP令牌，则删除旧的MCP令牌并创建新的
    5. 检查是否已存在MCP服务器集成，如果没有则创建
    6. 返回MCP长期访问令牌
    
    Returns:
        str: MCP长期访问令牌
        
    Raises:
        Exception: 当认证失败或WebSocket连接失败时抛出异常
    """
    # 确保缓存目录存在
    if not os.path.exists(home_assistant_cache_dir):
        logging.info(f"Cache dir not exists, create it: {home_assistant_cache_dir}")
        os.mkdir(home_assistant_cache_dir)
    
    # 构建令牌文件路径
    token_file = os.path.join(home_assistant_cache_dir, "token.txt")
    
    # 获取访问令牌（从缓存或认证）
    token_info = _get_access_token(token_file)
    
    # 构建WebSocket URL
    home_assistant_ws = _build_websocket_url(home_assistant_url)

    try:
        # 通过WebSocket连接处理MCP令牌和集成设置
        async with HAWebSocketClient(
            home_assistant_ws,
            token_info["access_token"],
            auto_reconnect=False
        ) as cli:
            # 获取或创建MCP令牌
            mcp_token = await _get_or_create_mcp_token(cli, token_file)
            
            # 设置MCP集成（如果需要）
            await _setup_mcp_integration_if_needed(cli, mcp_token)
            
    except HAAuthError as e:
        logging.error(f"Home Assistant authentication error: {e}")
        if os.path.exists(token_file):
            os.remove(token_file)
        raise
    
    # 通过WebSocket连接处理MCP令牌和集成设置
    async with HAWebSocketClient(
        home_assistant_ws,
        token_info["access_token"],
        auto_reconnect=False
    ) as cli:
        # 获取或创建MCP令牌
        mcp_token = await _get_or_create_mcp_token(cli, token_file)
        
        # 设置MCP集成（如果需要）
        await _setup_mcp_integration_if_needed(cli, mcp_token)
        
        return mcp_token


def _get_access_token(token_file: str) -> dict:
    """
    从缓存文件获取访问令牌，如果不存在则通过认证获取。
    
    Args:
        token_file: 令牌文件路径
        
    Returns:
        dict: 包含access_token的字典
    """
    if os.path.exists(token_file):
        # 从缓存文件读取令牌
        with open(token_file, "r") as f:
            return {"access_token": f.readline().strip()}
    else:
        # 通过认证获取新令牌
        auth = HomeAssistantAuth(
            home_assistant_url,
            home_assistant_username,
            home_assistant_password,
            home_assistant_cache_dir,
        )
        return auth.get_token()


def _build_websocket_url(base_url: str) -> str:
    """
    根据HTTP/HTTPS URL构建对应的WebSocket URL。
    
    Args:
        base_url: 基础URL
        
    Returns:
        str: WebSocket URL
    """
    if base_url.startswith("https"):
        return base_url.replace("https://", "wss://")
    else:
        return base_url.replace("http://", "ws://")


async def _get_or_create_mcp_token(cli: HAWebSocketClient, token_file: str) -> str:
    """
    获取或创建MCP长期访问令牌。
    
    Args:
        cli: WebSocket客户端实例
        token_file: 令牌文件路径
        
    Returns:
        str: MCP令牌
    """
    if os.path.exists(token_file):
        # 从文件读取现有MCP令牌
        with open(token_file, "r") as f:
            return f.readline().strip()
    else:
        # 删除现有的MCP令牌（如果存在）
        await _delete_existing_mcp_tokens(cli)
        
        # 创建新的MCP令牌
        logging.info("Create a new long-lived token, name: mcp")
        mcp_token = await cli.create_long_lived_token(client_name="mcp")
        
        # 保存令牌到文件
        with open(token_file, "w") as f:
            f.write(mcp_token)
            
        return mcp_token


async def _delete_existing_mcp_tokens(cli: HAWebSocketClient) -> None:
    """
    删除所有名为"mcp"的现有长期访问令牌。
    
    Args:
        cli: WebSocket客户端实例
    """
    # 获取所有刷新令牌
    refresh_tokens = await cli.get_refresh_tokens()
    
    # 查找并删除名为"mcp"的长期访问令牌
    for refresh_token in refresh_tokens:
        token_type = refresh_token.get("type", "")
        if token_type == "long_lived_access_token":
            token_id = refresh_token.get("id", "")
            client_name = refresh_token.get("client_name", "")
            logging.debug(f"Found a long-lived token, id: {token_id}, client_name: {client_name}")
            
            if client_name == "mcp":
                logging.info(f"Found existing mcp token, id: {token_id}, deleting it")
                await cli.delete_refresh_token(token_id)


async def _setup_mcp_integration_if_needed(cli: HAWebSocketClient, mcp_token: str) -> None:
    """
    检查并设置MCP集成（如果尚未设置）。
    
    Args:
        cli: WebSocket客户端实例
        mcp_token: MCP访问令牌
    """
    # 检查是否已存在MCP服务器集成
    have_mcp_server = await _check_mcp_server_integration(cli)
    
    if not have_mcp_server:
        # 创建MCP集成
        api_client = HomeAssistantIntegrationFlow(base_url=home_assistant_url, token=mcp_token)
        mcp = MCPServerIntegration(api_client)
        
        logging.info("Create a new MCP integration")
        result = mcp.setup_integration()
        logging.info(f"MCP integration setup result: {result}")


async def _check_mcp_server_integration(cli: HAWebSocketClient) -> bool:
    """
    检查是否已存在MCP服务器集成。
    
    Args:
        cli: WebSocket客户端实例
        
    Returns:
        bool: 如果存在MCP服务器集成则返回True，否则返回False
    """
    have_mcp_server = False
    
    async def on_config_changed(event):
        nonlocal have_mcp_server
        if isinstance(event, list):
            for item in event:
                domain = item.get("entry", {}).get("domain")
                logging.debug(f"Found a config entry, domain: {domain}")
                if domain == "mcp_server":
                    have_mcp_server = True
                    logging.info("Found mcp_server integration, skip setup")
                    break
    
    # 订阅配置条目变更
    await cli.subscribe_config_entries(on_config_changed, type_filter=["device", "hub", "service", "hardware"])
    
    return have_mcp_server

def get_or_create_long_token_sync():
    return asyncio.run(get_or_create_long_token())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = get_or_create_long_token_sync()
    logging.info(f"Get or create long-lived token success, token: {token}")

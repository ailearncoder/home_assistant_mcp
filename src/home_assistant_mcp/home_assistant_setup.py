from home_assistant_sdk import (HomeAssistantAuth, HAWebSocketClient, HomeAssistantIntegrationFlow, MCPServerIntegration)
import logging
import os

home_assistant_username = os.getenv("HOME_ASSISTANT_USERNAME", "admin")
home_assistant_password = os.getenv("HOME_ASSISTANT_PASSWORD", "admin123")
home_assistant_url = os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123")
home_assistant_cache_dir = os.getenv("HOME_ASSISTANT_CACHE_DIR", "./.cache")


async def get_or_create_long_token():
    if not os.path.exists(home_assistant_cache_dir):
        logging.info(f"Cache dir not exists, create it: {home_assistant_cache_dir}")
        os.mkdir(home_assistant_cache_dir)
    token_file = f"{home_assistant_cache_dir}/token.txt"
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token_info = {"access_token": f.readline().strip()}
    else:
        auth = HomeAssistantAuth(
            home_assistant_url,
            home_assistant_username,
            home_assistant_password,
            home_assistant_cache_dir,
        )
        token_info = auth.get_token()
    if home_assistant_url.startswith("https"):
        home_assistant_ws = home_assistant_url.replace("https://", "wss://")
    else:
        home_assistant_ws = home_assistant_url.replace("http://", "ws://")
    async with HAWebSocketClient(
        home_assistant_ws,
        token_info["access_token"],
        auto_reconnect=False
    ) as cli:
        token_file = f"{home_assistant_cache_dir}/token.txt"
        if not os.path.exists(token_file):
            # step 1: 删除名字为mcp的token
            refresh_tokens = await cli.get_refresh_tokens()
            for refresh_token in refresh_tokens:
                type = refresh_token.get("type", "")
                if type == "long_lived_access_token":
                    id = refresh_token.get("id", "")
                    client_name = refresh_token.get("client_name", "")
                    logging.debug(f"Found a long-lived token, id: {id}, client_name: {client_name}")
                    if client_name == "mcp":
                        logging.info(f"Found a long-lived token, id: {id}, client_name: {client_name}, delete it")
                        await cli.delete_refresh_token(id)
            # step 2: 创建一个名为mcp的token
            logging.info(f"Create a new long-lived token, name: mcp")
            mcp_token = await cli.create_long_lived_token(client_name="mcp")
            # step 3: 将token写入文件
            with open(token_file, "w") as f:
                f.write(mcp_token)
        else:
            with open(token_file, "r") as f:
                mcp_token = f.readline().strip()
        # 检测所有集成
        have_mcp_server = False
        async def on_config_changed(event):
            if isinstance(event, list):
                for item in event:
                    domain = item.get("entry", {}).get("domain")
                    logging.debug(f"Found a config entry, domain: {domain}")
                    if domain == "mcp_server":
                        nonlocal have_mcp_server
                        have_mcp_server = True
                        logging.info(f"Found mcp_server integration, skip setup")
                        break
        id = await cli.subscribe_config_entries(on_config_changed, type_filter=["device","hub","service","hardware"])
        if not have_mcp_server:
            api_client = HomeAssistantIntegrationFlow(base_url=home_assistant_url, token=mcp_token)
            # 创建MCP集成实例
            mcp = MCPServerIntegration(api_client)
            logging.info(f"Create a new MCP integration")
            result = mcp.setup_integration()
            logging.info(f"MCP integration setup result: {result}")
        return mcp_token

def get_or_create_long_token_sync():
    return asyncio.run(get_or_create_long_token())

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    token = get_or_create_long_token_sync()
    logging.info(f"Get or create long-lived token success, token: {token}")

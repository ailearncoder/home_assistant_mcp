import logging
from .home_assistant_setup import get_or_create_long_token_sync
from .mcp_server import MCPHomeAssistantServer


def main() -> None:
    from .home_assistant_setup import home_assistant_url

    logging.basicConfig(level=logging.INFO)
    try:
        token = get_or_create_long_token_sync()
    except BaseException as e:
        logging.error(f"Failed to get or create long token: {e}")
        return
    config = {
        "mcpServers": {
            "home_assistant": {
                "transport": "sse",
                "url": f"{home_assistant_url}/mcp_server/sse",
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    }
    server = MCPHomeAssistantServer(config)
    server.run()

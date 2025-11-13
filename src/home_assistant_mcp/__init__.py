import logging
from .home_assistant_setup import get_or_create_long_token_sync
from .mcp_server import MCPHomeAssistantServer


def main() -> None:
    from .home_assistant_setup import home_assistant_url

    logging.basicConfig(level=logging.INFO)
    token = get_or_create_long_token_sync()
    config = {
        "mcpServers": {
            "home_assistant": {
                "transport": "streamablehttp",
                "url": f"{home_assistant_url}/api/mcp",
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    }
    server = MCPHomeAssistantServer(config)
    server.run()

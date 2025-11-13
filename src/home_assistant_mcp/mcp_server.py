import json
import hashlib
import yaml
from typing import Any, Optional, Dict, List

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import TextContent
import logging
logger = logging.getLogger(__name__)

# --- Constants ---
CONTEXT_PREFIX = "Live Context: An overview of the areas and the devices in this smart home:"

class HomeAssistantController:
    """A controller to interact with the Home Assistant MCP server."""

    def __init__(self, config: str | Dict[str, Any] = "config.json"):
        """
        Initializes the controller by loading config and creating a client.

        Args:
            config: Path to the JSON configuration file or a dictionary configuration object.
        """
        logger.info("Initializing HomeAssistantController")
        self.config: Dict[str, Any] = self._load_config(config)
        self.client: Client = Client(self.config)
        logger.info("HomeAssistantController initialized")
        self._context: Optional[List[Dict[str, Any]]] = None
        self._context_hash: Optional[str] = None

    def _load_config(self, config: str | Dict[str, Any]) -> Dict[str, Any]:
        """Loads configuration from a JSON file or returns the config dictionary."""
        if isinstance(config, dict):
            logger.debug("Using provided dict configuration")
            return config
        
        # If it's not a dict, treat it as a file path
        try:
            with open(config, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded configuration from {config}")
                return data
        except FileNotFoundError:
            logger.error(f"Configuration file not found at: {config}")
            raise ToolError(f"Configuration file not found at: {config}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON configuration: {e}")
            raise ToolError(f"Error parsing JSON configuration: {e}")

    async def _get_raw_context(self) -> str:
        """Fetches the raw context string from the Home Assistant server."""
        async with self.client:
            logger.debug("Requesting live context from Home Assistant")
            context_response = await self.client.call_tool("GetLiveContext")
            if not context_response.content or not isinstance(context_response.content[0], TextContent):
                logger.error("Received an empty or invalid response from GetLiveContext")
                raise ToolError("Received an empty or invalid response from GetLiveContext.")

            # Use type assertion for TextContent
            text_content: TextContent = context_response.content[0]
            context_json: Dict[str, Any] = json.loads(text_content.text)
            if not context_json.get("success"):
                logger.error("API call to GetLiveContext failed")
                raise ToolError(f"API call to GetLiveContext failed: {context_json.get('result')}")

            result_str: str = context_json.get("result", "")
            logger.debug(f"Live context string length: {len(result_str)}")
            return result_str.replace(CONTEXT_PREFIX, "").strip()

    def _process_context(self, context_list: List[Dict[str, Any]]) -> None:
        """Adds a unique MD5 hash ID to each device in the context list."""
        for item in context_list:
            names: str = item.get("names", "")
            item["id"] = hashlib.md5(names.encode("utf-8")).hexdigest()
        logger.debug(f"Processed context devices: {len(context_list)}")

    async def get_processed_context(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves and processes the device context from Home Assistant.

        Caches the context to avoid redundant API calls. The cache is
        invalidated if the raw context from the server has changed.

        Args:
            force_refresh: If True, forces a refresh of the context from the server.

        Returns:
            A list of dictionaries, each representing a device with a unique 'id'.
        """
        raw_context_str: str = await self._get_raw_context()
        new_hash: str = hashlib.md5(raw_context_str.encode("utf-8")).hexdigest()

        if force_refresh or self._context is None or self._context_hash != new_hash:
            try:
                # The context from Home Assistant is still in YAML format, so we use yaml.safe_load here.
                # If the API also returns JSON, you can change this to json.loads().
                context_list: Any = yaml.safe_load(raw_context_str)
                if not isinstance(context_list, list):
                     raise ToolError("Parsed context from Home Assistant is not a list.")
                self._process_context(context_list)
                self._context = context_list
                self._context_hash = new_hash
                logger.info(f"Context cache refreshed, devices: {len(self._context)}")
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML from context: {e}")
                raise ToolError(f"Error parsing YAML from context: {e}")
        
        if self._context is None:
            logger.error("Context is None after processing")
            raise ToolError("Failed to load context.")

        logger.debug("Returning processed context from cache")
        return self._context

    async def _hass_turn(self, names: str, areas: str, on: bool) -> Dict[str, Any]:
        """Helper function to turn a device on or off via MCP tool call."""
        tool_name = "HassTurnOn" if on else "HassTurnOff"
        arguments = {"name": names, "area": areas}
        async with self.client:
            logger.info(f"Calling {tool_name} for name={names}, area={areas}")
            result = await self.client.call_tool(name=tool_name, arguments=arguments)
            if not result.content or not isinstance(result.content[0], TextContent):
                logger.error("Response content is empty or invalid for hass turn")
                raise ToolError("Response content is empty or invalid")
            text_content: TextContent = result.content[0]
            return json.loads(text_content.text)

    async def control_switch(self, device_ids: List[str], on: bool) -> List[Dict[str, Any]]:
        """
        Finds devices by their IDs and controls their state (on/off).

        Args:
            device_ids: A list of unique IDs of the devices to control.
            on: True to turn on, False to turn off.

        Returns:
            A list of dictionaries, each representing the result of an operation.
        """
        logger.info(f"Switch control request: count={len(device_ids)}, on={on}")
        context: List[Dict[str, Any]] = await self.get_processed_context()
        results: List[Dict[str, Any]] = []
        
        for device_id in device_ids:
            target_device = next((item for item in context if item.get("id") == device_id), None)

            if not target_device:
                logger.warning(f"Device not found: id={device_id}")
                results.append({"success": False, "error": f"Device with id '{device_id}' not found."})
                continue

            names: Optional[str] = target_device.get("names")
            areas: Optional[str] = target_device.get("areas")

            if names is None or areas is None:
                logger.warning(f"Device missing names/areas: id={device_id}")
                results.append({"success": False, "error": f"Device '{device_id}' is missing 'names' or 'areas' information."})
                continue

            try:
                result: Dict[str, Any] = await self._hass_turn(names, areas, on)
                results.append({"success": True, "device_id": device_id, "result": result})
            except Exception as e:
                logger.exception(f"Error controlling switch for id={device_id}")
                results.append({"success": False, "device_id": device_id, "error": str(e)})
        
        logger.info(f"Switch control completed: success={sum(1 for r in results if r.get('success'))}, fail={sum(1 for r in results if not r.get('success'))}")
        return results

    async def _hass_light_set(self, names: str, area: str, brightness: Optional[int] = None) -> Dict[str, Any]:
        """Helper function to set light brightness via MCP tool call."""
        arguments: Dict[str, str] = {"name": names, "area": area}
        if brightness is not None:
            arguments["brightness"] = str(brightness)
        
        async with self.client:
            logger.info(f"Calling HassLightSet for name={names}, area={area}, brightness={brightness}")
            result = await self.client.call_tool(name="HassLightSet", arguments=arguments)
            if not result.content or not isinstance(result.content[0], TextContent):
                logger.error("Response content is empty or invalid for light set")
                raise ToolError("Response content is empty or invalid")
            text_content: TextContent = result.content[0]
            return json.loads(text_content.text)

    async def control_light_brightness(self, device_ids: List[str], brightness: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Finds light devices by their IDs and sets their brightness.

        Args:
            device_ids: A list of unique IDs of the light devices to control.
            brightness: Brightness percentage (0-100), or None to turn off.

        Returns:
            A list of dictionaries, each representing the result of an operation.
        """
        logger.info(f"Light brightness request: count={len(device_ids)}, brightness={brightness}")
        context: List[Dict[str, Any]] = await self.get_processed_context()
        results: List[Dict[str, Any]] = []
        
        for device_id in device_ids:
            target_device = next((item for item in context if item.get("id") == device_id), None)

            if not target_device:
                logger.warning(f"Light device not found: id={device_id}")
                results.append({"success": False, "error": f"Device with id '{device_id}' not found."})
                continue

            names: Optional[str] = target_device.get("names")
            areas: Optional[str] = target_device.get("areas")

            if names is None or areas is None:
                logger.warning(f"Light device missing names/areas: id={device_id}")
                results.append({"success": False, "error": f"Device '{device_id}' is missing 'names' or 'areas' information."})
                continue

            try:
                result: Dict[str, Any] = await self._hass_light_set(names, areas, brightness)
                results.append({"success": True, "device_id": device_id, "result": result})
            except Exception as e:
                logger.exception(f"Error setting light brightness for id={device_id}")
                results.append({"success": False, "device_id": device_id, "error": str(e)})
        
        logger.info(f"Light brightness completed: success={sum(1 for r in results if r.get('success'))}, fail={sum(1 for r in results if not r.get('success'))}")
        return results

# --- FastMCP Tool Definition ---

mcp_home_assistant = FastMCP(
    name="HomeAssistant",
    instructions="A tool to control devices in a Home Assistant smart home.",
)

# Instantiate the controller.
controller: Optional[HomeAssistantController] = None
try:
    # The default path is now config.json, so no argument is needed if the file is in the same directory.
    controller = HomeAssistantController()
except ToolError as e:
    logger.exception("Failed to initialize HomeAssistantController")

@mcp_home_assistant.tool
async def get_device_info() -> List[Dict[str, Any]]:
    """
    Get information about all available devices.
    Before using switch_control, you should call this tool to get the device 'id'.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        logger.info("get_device_info invoked")
        return await controller.get_processed_context(force_refresh=True)
    except Exception as e:
        logger.exception("Error getting device info")
        raise ToolError(f"An error occurred while getting device info: {e}")

@mcp_home_assistant.tool
async def switch_control(id: List[str], on: bool) -> List[Dict[str, Any]]:
    """
    Control switch devices.

    Args:
        id: A list of device 'id's, obtained from get_device_info.
        on: Set to true to turn the devices on, false to turn them off.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        logger.info("switch_control invoked")
        return await controller.control_switch(device_ids=id, on=on)
    except Exception as e:
        logger.exception("Error during switch control")
        raise ToolError(f"An error occurred during switch control: {e}")

@mcp_home_assistant.tool
async def light_set(id: List[str], brightness: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Set the brightness percentage of light devices.

    Args:
        id: A list of device 'id's, obtained from get_device_info.
        brightness: Brightness percentage (0-100), or None to turn off.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        logger.info("light_set invoked")
        return await controller.control_light_brightness(device_ids=id, brightness=brightness)
    except Exception as e:
        logger.exception("Error during light brightness control")
        raise ToolError(f"An error occurred during light brightness control: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if controller:
        logger.info("Starting HomeAssistant MCP server")
        mcp_home_assistant.run()

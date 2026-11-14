"""MCP (Model Context Protocol) server: exposes the travel tools to any MCP client (Claude Desktop, your JARVIS AI, etc.).

    pip install mcp
    python mcp_server.py                 # stdio transport

Claude Desktop config example (claude_desktop_config.json):
    {"mcpServers": {"chennai-travel": {"command": "python", "args": ["C:/path/to/Chennai_Smart_Travel_AI/mcp_server.py"]}}}
"""
from mcp.server.fastmcp import FastMCP

from genai.agents import tools as t

mcp = FastMCP("chennai-smart-travel")


@mcp.tool()
def plan_journey(start: str, destination: str, priority: str = "Fastest", fare_type: str = "regular",
                 mode: str | None = None, hour: int | None = None, day_of_week: int | None = None,
                 month: int | None = None, rain_level: int = 0) -> dict:
    """Best multi-modal Chennai journey. Pass hour (0-23), day_of_week (0=Mon) and rain_level (0-2) for traffic-aware times."""
    return t.plan_journey(start, destination, priority, fare_type, mode, hour, day_of_week, month, rain_level)


@mcp.tool()
def plan_within_budget(start: str, destination: str, budget: float) -> dict:
    """Cheapest journey that fits a rupee budget."""
    return t.plan_within_budget(start, destination, budget)


@mcp.tool()
def compare_transport_modes(start: str, destination: str) -> dict:
    """All direct transport options between two places with fare, time and distance."""
    return t.compare_transport_modes(start, destination)


@mcp.tool()
def predict_delay(mode: str, hour: int, day_of_week: int = 0, month: int = 1, rain_level: int = 0) -> dict:
    """ML-predicted delay for a transport mode at a given time and rain level."""
    return t.predict_delay(mode, hour, day_of_week, month, rain_level)


@mcp.tool()
def best_departure_time(start: str, destination: str, day_of_week: int = 0, rain_level: int = 0) -> dict:
    """Best hour to leave to minimise travel time."""
    return t.best_departure_time(start, destination, day_of_week, None, rain_level)


@mcp.tool()
def metro_fare(start: str, destination: str, fare_type: str = "regular") -> dict:
    """Chennai Metro fare between two stations (regular or discounted)."""
    return t.metro_fare(start, destination, fare_type)


@mcp.tool()
def search_knowledge(query: str) -> dict:
    """Search the Chennai transport knowledge base."""
    return t.search_knowledge(query)


if __name__ == "__main__":
    mcp.run()

# codedueprocess/tools.py
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get the current weather in a given city."""
    return f"The weather in {city} is sunny and 25°C."

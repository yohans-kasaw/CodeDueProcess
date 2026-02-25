"""Tools available for the CodeDueProcess agent."""

from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get the current weather in a given city."""
    return f"The weather in {city} is sunny and 25°C."


@tool
def search_web(query: str) -> str:
    """Search the web for detailed information on a topic."""
    # Mock search results for demonstration
    topics = {
        "langgraph": (
            "LangGraph is a library for building stateful, multi-actor applications "
            "with LLMs. It is built on top of LangChain and allows for cycles in the "
            "graph."
        ),
        "agent": (
            "An autonomous agent is a system that can perceive its environment, "
            "reason about it, and take actions to achieve a goal."
        ),
        "python": (
            "Python is a high-level, interpreted programming language known for its "
            "readability and vast ecosystem of libraries."
        ),
    }

    # Return a specific result if found, otherwise generic filler
    for key, value in topics.items():
        if key.lower() in query.lower():
            return f"Search Result: {value}"

    return (
        f"Search Result: found generic information about {query}. "
        "It is a complex topic with many facets."
    )


@tool
def calculate_stats(data: str) -> str:
    """Calculate simple statistics for a given dataset."""
    return f"Stats for {data}: Mean=42, Median=40, Mode=N/A"

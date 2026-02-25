"""Main entry point for the CodeDueProcess agent.

This module sets up the LangGraph workflow for processing messages and
calling tools using the Gemini model.
"""

import os
import warnings
from collections.abc import Sequence
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_litellm import ChatLiteLLM
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

# Suppress Pydantic UserWarnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables
load_dotenv()

# Configuration
# Default to OpenRouter with Gemini if no model is specified
# LiteLLM expects "provider/model" format
# (e.g., "openrouter/google/gemini-3-flash-preview")
LLM_MODEL = os.getenv("LLM_MODEL", "")


@tool
def get_weather(city: str) -> str:
    """Get the current weather in a given city."""
    return f"The weather in {city} is sunny and 25°C."


tools = [get_weather]
llm = ChatLiteLLM(model=LLM_MODEL, temperature=0.7)
llm_with_tools = llm.bind_tools(tools)


class AgentState(TypedDict):
    """Represents the state of the agent, including the history of messages."""

    # Use the add_messages function here
    messages: Annotated[Sequence, add_messages]


def call_model(state: AgentState):
    """Call the LLM model with the current state messages."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# Build Graph
workflow = StateGraph(AgentState)  # Pass the class directly
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)  # Simplified mapping
workflow.add_edge("tools", "agent")

agent = workflow.compile()

# Execution
# Cast inputs to AgentState to satisfy type checker
inputs: AgentState = {
    "messages": [HumanMessage(content="What is the weather in Addis Ababa?")]
}
for chunk in agent.stream(inputs, stream_mode="values"):
    final_msg = chunk["messages"][-1]
    # This lets you see the tool calls AND the final response
    if hasattr(final_msg, "content"):
        print(f"Role: {type(final_msg).__name__} | Content: {final_msg.content}")

# codedueprocess/agent.py
import warnings
from collections.abc import Sequence
from typing import Annotated

from langchain_core.globals import set_llm_cache
from langchain_litellm import ChatLiteLLM
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from .cache import LiteLLMCache
from .config import APP_ENV, DB_PATH, LLM_MODEL
from .tools import get_weather

# Suppress Pydantic UserWarnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

temperature = 0
if APP_ENV == "development":
    print("🔧 Development Mode: Caching enabled & Temperature set to ", temperature)
    set_llm_cache(LiteLLMCache(database_path=DB_PATH))
else:
    print("🚀 Production Mode: Caching disabled & Temperature set to ", temperature)

# Setup Tools
tools = [get_weather]

# Setup LLM
llm = ChatLiteLLM(model=LLM_MODEL, temperature=temperature)
llm_with_tools = llm.bind_tools(tools)


class AgentState(TypedDict):
    """Represents the state of the agent, including the history of messages."""

    messages: Annotated[Sequence, add_messages]


def call_model(state: AgentState):
    """Call the LLM model with the current state messages."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def build_graph():
    """Build and compile the agent workflow graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    return workflow.compile()


# Export the compiled agent
agent = build_graph()

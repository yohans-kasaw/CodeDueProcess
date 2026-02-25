"""Agent definition for CodeDueProcess."""

import operator
from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal, TypedDict, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .cache import LiteLLMCache
from .config import APP_ENV, DB_PATH, LLM_MODEL
from .tools import calculate_stats, get_weather, search_web

# --- 1. Setup & Config ---
if APP_ENV == "development":
    from langchain_core.globals import set_llm_cache

    print("🔧 Development Mode: Caching enabled")
    set_llm_cache(LiteLLMCache(database_path=DB_PATH))
    temperature: float = 0.0
else:
    print("🚀 Production Mode: Caching disabled")
    temperature = 0.7

llm = ChatLiteLLM(model=LLM_MODEL, temperature=temperature)


# --- 2. Define Agent State ---
class AgentState(TypedDict):
    """The state of the agent."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str


# --- 3. Define Workers ---


def create_agent_node(
    agent: CompiledStateGraph[AgentState, Any, Any, Any], name: str
) -> Callable[[Any, RunnableConfig], dict[str, list[BaseMessage]]]:
    """Create a node for an agent in the graph.

    Args:
        agent: The agent instance.
        name: The name of the agent.

    Returns:
        A function that represents the agent node.
    """

    def agent_node(state: Any, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        print(f"--- {name} Working ---")
        # We need to invoke the agent with the current state.
        # create_react_agent expects a dictionary with "messages".
        # Cast state to dict to satisfy strict typing if necessary, though
        # TypedDict is a dict.
        # In strict mode, we might need to be explicit.
        result = agent.invoke(cast(dict[str, Any], state), config)

        # We extract the last message from the agent's execution
        # which should contain the final answer from that worker.
        last_message = result["messages"][-1]
        print(f"--- {name} Finished: {last_message.content[:50]}... ---")

        # We wrap it as an AIMessage from the worker "persona"
        return {"messages": [AIMessage(content=last_message.content, name=name)]}

    return agent_node


# Research Agent
researcher_agent = create_react_agent(
    llm,
    tools=[search_web],
    prompt=(
        "You are a Researcher. Your goal is to gather information using the "
        "search_web tool."
    ),
)
researcher_node = create_agent_node(researcher_agent, "Researcher")

# Analyst Agent
analyst_agent = create_react_agent(
    llm,
    tools=[calculate_stats, get_weather],
    prompt=(
        "You are an Analyst. Your goal is to analyze data or check conditions using "
        "your tools."
    ),
)
analyst_node = create_agent_node(analyst_agent, "Analyst")


# --- 4. Define Supervisor ---
members = ["Researcher", "Analyst"]
options = ["FINISH"] + members


class Route(BaseModel):
    """Select the next role."""

    next: Literal["Researcher", "Analyst", "FINISH"] = Field(
        ..., description="The next role to act."
    )


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a supervisor tasked with managing a conversation between the "
                "following workers: {members}. Given the following user request, "
                "respond with the worker to act next. Each worker will perform a "
                "task and respond with their results. When the user's request is "
                "satisfied, respond with FINISH."
            ),
        ),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            (
                "Given the conversation above, who should act next? Select one of: "
                "{options}"
            ),
        ),
    ]
).partial(options=str(options), members=", ".join(members))


def supervisor_node(state: AgentState) -> dict[str, str]:
    """Determine the next step in the workflow.

    Args:
        state: The current state of the agent.

    Returns:
        The next step to take.
    """
    # Bind the tool and force it
    supervisor_chain = prompt | llm.bind_tools(
        [Route],
        # Force the LLM to use a tool (since only one is available, it uses Route)
        tool_choice="required",
    )

    print("--- Supervisor Thinking ---")
    result = supervisor_chain.invoke(cast(dict[str, Any], state))
    # print(f"--- Supervisor Result: {result} ---")

    # Parse the tool call manually since we are using bind_tools
    # result is an AIMessage with tool_calls
    try:
        if result.tool_calls:
            # Extract the 'next' argument from the first tool call
            next_step = result.tool_calls[0]["args"]["next"]
            print(f"--- Supervisor decided: {next_step} ---")
        else:
            # Fallback if no tool called
            # (shouldn't happen with forced tool_choice but safe to handle)
            next_step = "FINISH"
            print("--- Supervisor decided: FINISH (fallback) ---")
    except (KeyError, IndexError):
        next_step = "FINISH"
        print("--- Supervisor decided: FINISH (error) ---")

    return {"next": next_step}


# --- 5. Build Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Researcher", researcher_node)  # type: ignore[arg-type]
workflow.add_node("Analyst", analyst_node)  # type: ignore[arg-type]

# Workers always report back to supervisor
for member in members:
    workflow.add_edge(member, "Supervisor")

# The supervisor determines the next step
workflow.add_conditional_edges(
    "Supervisor",
    lambda x: x["next"],
    {"Researcher": "Researcher", "Analyst": "Analyst", "FINISH": END},
)

workflow.add_edge(START, "Supervisor")

agent: CompiledStateGraph[AgentState, Any, Any, Any] = workflow.compile()

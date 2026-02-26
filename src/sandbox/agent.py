"""Agent definition for sandbox - LangGraph testing environment.

This module implements a multi-agent workflow with Supervisor, Researcher, and
Analyst nodes for testing LangGraph patterns and agent behaviors.
"""

import logging
import operator
from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal, TypedDict, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from .cache import LiteLLMCache
from .config import APP_ENV, DB_PATH, LLM_MODEL
from .tools import calculate_stats, get_weather, search_web

logger = logging.getLogger(__name__)

# --- 1. Setup & Config ---
if APP_ENV == "development":
    from langchain_core.globals import set_llm_cache

    logger.info("mode=development cache=enabled db_path=%s", DB_PATH)
    set_llm_cache(LiteLLMCache(database_path=DB_PATH))
    temperature: float = 0.0
else:
    logger.info("mode=production cache=disabled")
    temperature = 0.7

llm = ChatLiteLLM(model=LLM_MODEL, temperature=temperature)


# --- 2. Define Agent State ---
MAX_STEPS = 8
MAX_ANALYST_RETRY_ATTEMPTS = 1
INSUFFICIENT_RESPONSE_SIGNALS = (
    "sorry, need more steps",
    "need more steps",
    "unable to complete",
    "cannot complete",
)


class AgentState(TypedDict):
    """The state of the agent."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    step: int


def _message_preview(message: BaseMessage, limit: int = 100) -> str:
    """Build a safe single-line preview for logs."""
    content = message.content
    if isinstance(content, str):
        text = content
    else:
        text = str(content)

    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return f"{single_line[:limit]}..."


def _extract_worker_response(messages: list[BaseMessage]) -> str | None:
    """Return the most recent non-empty textual response."""
    for message in reversed(messages):
        content = message.content
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _tool_activity_counts(messages: list[BaseMessage]) -> tuple[int, int]:
    """Return (tool_calls_requested, tool_results_returned)."""
    requested = 0
    returned = 0

    for message in messages:
        if isinstance(message, AIMessage):
            tool_calls = getattr(message, "tool_calls", None)
            if isinstance(tool_calls, list):
                requested += len(tool_calls)
        if isinstance(message, ToolMessage):
            returned += 1

    return requested, returned


def _with_retry_prompt(state: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Create a copied state with an additional retry prompt message."""
    retry_state = dict(state)
    prior_messages = list(cast(Sequence[BaseMessage], state.get("messages", [])))
    prior_messages.append(HumanMessage(content=prompt))
    retry_state["messages"] = prior_messages
    return retry_state


def _is_insufficient_response(text: str) -> bool:
    """Detect placeholder responses that should trigger a retry/fallback."""
    normalized = text.lower().strip()
    return any(signal in normalized for signal in INSUFFICIENT_RESPONSE_SIGNALS)


def _latest_tool_output(messages: list[BaseMessage]) -> str | None:
    """Return the latest tool output text, if available."""
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue
        content = message.content
        if isinstance(content, str) and content.strip():
            return content.strip()
        if not isinstance(content, str):
            content_str = str(content).strip()
            if content_str:
                return content_str
    return None


def _heuristic_route(state: AgentState) -> str | None:
    """Apply deterministic handoff rules before consulting the LLM."""
    messages = state.get("messages", [])
    if not messages:
        return None

    last_message = messages[-1]
    if not isinstance(last_message, AIMessage):
        return None

    worker_name = getattr(last_message, "name", "")
    content = str(last_message.content).lower()
    no_tool_signals = (
        "cannot fulfill",
        "do not have",
        "don't have",
        "tool is not available",
        "please clarify",
    )

    if worker_name == "Researcher" and any(
        signal in content for signal in no_tool_signals
    ):
        logger.info("supervisor=heuristic reason=researcher_tool_limit next=Analyst")
        return "Analyst"

    if worker_name == "Analyst" and any(
        signal in content for signal in no_tool_signals
    ):
        logger.info("supervisor=heuristic reason=analyst_tool_limit next=FINISH")
        return "FINISH"

    return None


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
        state_dict = cast(dict[str, Any], state)
        step = state_dict.get("step", 0)
        logger.info("worker=%s status=start step=%s", name, step)
        # We need to invoke the agent with the current state.
        # create_react_agent expects a dictionary with "messages".
        # Cast state to dict to satisfy strict typing if necessary, though
        # TypedDict is a dict.
        # In strict mode, we might need to be explicit.
        attempt = 0
        working_state = state_dict
        while True:
            result = agent.invoke(working_state, config)

            messages = cast(list[BaseMessage], result.get("messages", []))
            requested, returned = _tool_activity_counts(messages)
            logger.info(
                (
                    "worker=%s status=tool_activity attempt=%s "
                    "tool_calls=%s tool_results=%s"
                ),
                name,
                attempt,
                requested,
                returned,
            )

            worker_text = _extract_worker_response(messages) or ""
            needs_analyst_retry = (
                name == "Analyst"
                and (returned == 0 or _is_insufficient_response(worker_text))
                and attempt < MAX_ANALYST_RETRY_ATTEMPTS
            )
            if not needs_analyst_retry:
                break

            logger.warning(
                "worker=Analyst status=retry reason=tooling-or-response attempt=%s",
                attempt,
            )
            working_state = _with_retry_prompt(
                working_state,
                (
                    "Tool usage is required for this role. You must call one of: "
                    "calculate_stats or get_weather, then provide a direct final "
                    "answer with concrete results."
                ),
            )
            attempt += 1

        # We extract the last message from the agent's execution
        # which should contain the final answer from that worker.
        if not messages:
            logger.warning("worker=%s status=empty-output", name)
            fallback = AIMessage(
                content=(
                    f"{name} could not produce a response. "
                    "Please continue with available context."
                ),
                name=name,
            )
            return {"messages": [fallback]}

        worker_text = _extract_worker_response(messages) or ""
        if not worker_text:
            logger.warning("worker=%s status=no-textual-output", name)
            fallback = AIMessage(
                content=(
                    f"{name} completed execution but returned no textual summary. "
                    "Proceed to the next suitable worker."
                ),
                name=name,
            )
            return {"messages": [fallback]}

        _, final_tool_results = _tool_activity_counts(messages)
        if name == "Analyst" and _is_insufficient_response(worker_text):
            tool_summary = _latest_tool_output(messages)
            if tool_summary:
                logger.warning(
                    "worker=Analyst status=fallback action=use-latest-tool-output"
                )
                worker_text = tool_summary

        if name == "Analyst" and final_tool_results == 0:
            logger.error("worker=Analyst status=failed reason=tool-not-called")
            fallback = AIMessage(
                content=(
                    "Analyst failed to execute required tools after retry. "
                    "Routing should switch workers or finish gracefully."
                ),
                name=name,
            )
            return {"messages": [fallback]}

        last_message = AIMessage(content=worker_text, name=name)
        logger.info(
            "worker=%s status=done preview=%s",
            name,
            _message_preview(last_message),
        )

        # We wrap it as an AIMessage from the worker "persona"
        return {"messages": [last_message]}

    return agent_node


# Research Agent
researcher_agent = create_react_agent(
    llm,
    tools=[search_web],
    prompt=(
        "You are a Researcher. Use only the search_web tool to gather facts needed "
        "for the user request. Return a concise factual summary and do not ask the "
        "user follow-up questions."
    ),
)
researcher_node = create_agent_node(researcher_agent, "Researcher")

analyst_agent = create_react_agent(
    llm,
    tools=[calculate_stats, get_weather],
    prompt=(
        "You are an Analyst. Use calculate_stats for text or dataset stats and "
        "get_weather for weather checks. Execute tools directly when arguments are "
        "already present in the conversation. Tool use is mandatory. Do not ask "
        "for clarification unless the required argument is truly missing."
    ),
)
analyst_node = create_agent_node(analyst_agent, "Analyst")


# --- 4. Define Supervisor ---
members = ["Researcher", "Analyst"]
options = ["FINISH"] + members


class Route(BaseModel):
    """Select the next role."""

    next: Literal["Researcher", "Analyst", "FINISH"]


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a supervisor tasked with managing a conversation between the "
                "following workers: {members}. Given the following user request, "
                "respond with the worker to act next. Each worker will perform a "
                "task and respond with their results. Route to a worker that has the "
                "required tools for the remaining work. Avoid repeating the same "
                "worker if they already reported a tool limitation. When the user's "
                "request is satisfied, respond with FINISH."
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

supervisor_chain = prompt | llm.with_structured_output(Route)


def supervisor_node(state: AgentState) -> dict[str, str | int]:
    """Determine the next step in the workflow.

    Args:
        state: The current state of the agent.

    Returns:
        The next step to take.
    """
    step = state.get("step", 0)

    if step >= MAX_STEPS:
        logger.warning("supervisor=guardrail reason=max-steps limit=%s", MAX_STEPS)
        return {"next": "FINISH"}

    forced_route = _heuristic_route(state)
    if forced_route is not None:
        return {"next": forced_route, "step": step + 1}

    logger.info("supervisor=status=thinking step=%s", step)
    try:
        route = cast(Route, supervisor_chain.invoke(cast(dict[str, Any], state)))
        next_step = route.next
    except Exception as exc:
        logger.exception("supervisor=error action=fallback error=%s", exc)
        next_step = "FINISH"

    logger.info("supervisor=status=decision next=%s", next_step)

    return {"next": next_step, "step": step + 1}


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
    lambda state: state.get("next", "FINISH"),
    {"Researcher": "Researcher", "Analyst": "Analyst", "FINISH": END},
)

workflow.add_edge(START, "Supervisor")

agent: CompiledStateGraph[AgentState, Any, Any, Any] = workflow.compile()

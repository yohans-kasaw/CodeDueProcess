"""Main entry point for sandbox - LangGraph testing environment.

Example usage demonstrating the multi-agent workflow.
"""

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from .agent import AgentState, agent

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure concise structured logging for CLI execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def run() -> None:
    """Run the agent with a sample query."""
    configure_logging()

    # Ensure inputs match the AgentState definition
    inputs: AgentState = {
        "messages": [
            HumanMessage(
                content=(
                    "Use the search_web tool to find out what LangGraph is, and then "
                    "calculate stats on the string 'LangGraph Rules' using the "
                    "calculate_stats tool."
                )
            )
        ],
        "next": "Supervisor",
        "step": 0,
    }

    logger.info("query=%s", inputs["messages"][0].content)

    config: RunnableConfig = {"recursion_limit": 10}
    for idx, chunk in enumerate(
        agent.stream(inputs, config, stream_mode="values"), start=1
    ):
        final_msg = chunk["messages"][-1]
        # This lets you see the tool calls AND the final response
        if hasattr(final_msg, "content"):
            logger.info(
                "event=stream_chunk index=%s role=%s content=%s",
                idx,
                type(final_msg).__name__,
                final_msg.content,
            )


if __name__ == "__main__":
    run()

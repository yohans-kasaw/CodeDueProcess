"""Main entry point for the CodeDueProcess agent."""

from langchain_core.messages import HumanMessage

from .agent import AgentState, agent


def run() -> None:
    """Run the agent with a sample query."""
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
    }

    print(f"Running query: {inputs['messages'][0].content}")

    for chunk in agent.stream(inputs, stream_mode="values"):
        final_msg = chunk["messages"][-1]
        # This lets you see the tool calls AND the final response
        if hasattr(final_msg, "content"):
            print(f"Role: {type(final_msg).__name__} | Content: {final_msg.content}")


if __name__ == "__main__":
    run()

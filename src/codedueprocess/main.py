# codedueprocess/main.py
from langchain_core.messages import HumanMessage
from .agent import agent


def run():
    """Run the agent with a sample query."""
    # Ensure inputs match the AgentState definition
    inputs = {"messages": [HumanMessage(content="What is the weather in Addis Ababa?")]}

    print(f"Running query: {inputs['messages'][0].content}")

    for chunk in agent.stream(inputs, stream_mode="values"):
        final_msg = chunk["messages"][-1]
        # This lets you see the tool calls AND the final response
        if hasattr(final_msg, "content"):
            print(f"Role: {type(final_msg).__name__} | Content: {final_msg.content}")


if __name__ == "__main__":
    run()

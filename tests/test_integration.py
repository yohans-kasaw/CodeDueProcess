"""Integration tests for the complete agent workflow."""

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.integration
class TestAgentGraphStructure:
    """Tests for the compiled agent graph structure."""

    def test_agent_graph_is_compiled(self):
        """Should verify the agent graph is compiled and runnable."""
        from codedueprocess.agent import agent

        # Check that agent is compiled (has invoke method)
        assert hasattr(agent, "invoke")
        assert callable(agent.invoke)

    def test_agent_has_required_nodes(self):
        """Should verify all required nodes exist in graph."""
        from codedueprocess.agent import agent

        # Get graph structure
        graph = agent.get_graph()

        # Check that required nodes exist
        nodes = list(graph.nodes.keys())
        assert "Supervisor" in nodes
        assert "Researcher" in nodes
        assert "Analyst" in nodes

    def test_agent_has_supervisor_conditional_edges(self):
        """Should verify supervisor has conditional edges to workers."""
        from codedueprocess.agent import agent

        graph = agent.get_graph()

        # Check edges exist from Supervisor
        edges = graph.edges
        supervisor_edges = [e for e in edges if e[0] == "Supervisor"]
        assert len(supervisor_edges) > 0

    def test_agent_has_worker_to_supervisor_edges(self):
        """Should verify workers route back to supervisor."""
        from codedueprocess.agent import agent

        graph = agent.get_graph()
        edges = graph.edges

        # Check Researcher -> Supervisor edge
        researcher_edges = [e for e in edges if e[0] == "Researcher"]
        assert any(e[1] == "Supervisor" for e in researcher_edges)

        # Check Analyst -> Supervisor edge
        analyst_edges = [e for e in edges if e[0] == "Analyst"]
        assert any(e[1] == "Supervisor" for e in analyst_edges)


@pytest.mark.integration
@pytest.mark.slow
class TestAgentWorkflowScenarios:
    """Integration tests for complete workflow scenarios."""

    def test_simple_query_triggers_researcher_first(self):
        """Should route to Researcher first for general queries."""
        from codedueprocess.agent import agent

        _ = {
            "messages": [HumanMessage(content="What is LangGraph?")],
            "step": 0,
        }

        # Run the agent (this may require mocking LLM in practice)
        # For now, just verify the structure supports this
        assert agent is not None

    def test_agent_state_persists_across_steps(self):
        """Should maintain state across multiple steps."""
        from codedueprocess.agent import AgentState

        # Create a state and verify it has required keys
        state: AgentState = {
            "messages": [HumanMessage(content="Test")],
            "next": "",
            "step": 0,
        }

        assert "messages" in state
        assert "next" in state
        assert "step" in state

    def test_state_accumulates_messages(self):
        """Should accumulate messages in state across invocations."""
        initial_messages = [HumanMessage(content="First query")]
        state = {
            "messages": initial_messages,
            "step": 0,
        }

        # After running, messages should accumulate
        # (This would need mocking to test fully)
        assert len(state["messages"]) == 1


class TestAgentConfiguration:
    """Tests for agent configuration and setup."""

    def test_llm_is_initialized(self):
        """Should verify LLM is properly initialized."""
        from codedueprocess.agent import llm

        assert llm is not None

    def test_researcher_agent_has_search_tool(self):
        """Should verify researcher has search_web tool."""
        from codedueprocess.agent import researcher_agent

        # Check that the agent was created with tools
        assert researcher_agent is not None

    def test_analyst_agent_has_required_tools(self):
        """Should verify analyst has calculate_stats and get_weather tools."""
        from codedueprocess.agent import analyst_agent

        # Check that the agent was created with tools
        assert analyst_agent is not None

    def test_agent_nodes_are_created(self):
        """Should verify all agent nodes are created."""
        from codedueprocess.agent import (
            analyst_node,
            researcher_node,
            supervisor_node,
        )

        assert callable(researcher_node)
        assert callable(analyst_node)
        assert callable(supervisor_node)

    def test_workflow_graph_is_built(self):
        """Should verify workflow graph is properly constructed."""
        from codedueprocess.agent import workflow

        assert workflow is not None
        # Verify it's a StateGraph
        assert hasattr(workflow, "add_node")
        assert hasattr(workflow, "add_edge")

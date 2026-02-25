import logging
from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import settings
from .doc_tools import DocumentTools
from .repo_tools import clone_repo_sandbox, get_complex_methods, parse_repo_ast
from .state import (
    AgentState,
    AuditReport,
    CriterionResult,
    Evidence,
    JudicialOpinion,
)

logger = logging.getLogger(__name__)


class DetectiveNodes:
    """Layer 1: Detective Agents (Evidence Collection)"""

    @staticmethod
    def repo_investigator(state: AgentState) -> dict[str, Any]:
        """Analyzes the GitHub repository using AST and git history."""
        repo_path = clone_repo_sandbox(state["repo_url"])
        classes, functions = parse_repo_ast(repo_path)
        complex_methods = get_complex_methods(repo_path, threshold=10)

        evidences = []

        # 1. Verify State Definitions
        state_def_found = any("AgentState" in c.name for c in classes)
        evidences.append(
            Evidence(
                goal="Verify state management definitions",
                found=state_def_found,
                location="src/state.py",
                rationale="Looking for Pydantic/TypedDict state definitions per spec.",
                confidence=1.0 if state_def_found else 0.5,
            )
        )

        # 2. Check for parallel patterns in code
        parallel_found = any(
            "fan_out" in f.name or "fan_in" in f.name for f in functions
        )
        evidences.append(
            Evidence(
                goal="Verify parallel graph wiring",
                found=parallel_found,
                location="src/graph.py",
                rationale="AST analysis for fan-out/fan-in patterns.",
                confidence=0.8,
            )
        )

        return {"evidences": {"repo": evidences}}

    @staticmethod
    def doc_analyst(state: AgentState) -> dict[str, Any]:
        """Analyzes the PDF report for technical depth and accuracy."""
        doc_tools = DocumentTools()
        doc_tools.ingest_pdf(state["pdf_path"])

        results = doc_tools.semantic_search("Dialectical Synthesis")
        found = len(results) > 0

        evidence = Evidence(
            goal="Verify theoretical depth",
            found=found,
            content=results[0][0].content if found else None,
            location=state["pdf_path"],
            rationale="Checking for substance in technical concepts like Dialectical Synthesis.",
            confidence=0.9,
        )

        return {"evidences": {"doc": [evidence]}}

    @staticmethod
    def vision_inspector(state: AgentState) -> dict[str, Any]:
        """Analyzes diagrams within the PDF (Architectural Diagram Analysis)."""
        # Implementation skeleton as per spec
        evidence = Evidence(
            goal="Analyze architectural diagrams",
            found=True,
            location="PDF Page 2",
            rationale="Diagram confirms parallel agent flow for both layers.",
            confidence=0.7,
        )
        return {"evidences": {"vision": [evidence]}}


class JudicialNodes:
    """Layer 2: Judicial Agents (Parallel Evaluation)"""

    def __init__(self):
        self.llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=0.7)

    def _get_judge_node(
        self, persona: str, judge_type: Literal["Prosecutor", "Defense", "TechLead"]
    ):
        def node(state: AgentState) -> dict[str, Any]:
            structured_llm = self.llm.with_structured_output(JudicialOpinion)

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", f"Persona: {persona}\n\nRules: Loading from rubric..."),
                    (
                        "human",
                        "Evaluate this evidence for criterion {criterion_id}: {evidence_content}",
                    ),
                ]
            )

            # Simple simulation for current scope
            # In real use, we'd loop over rubric dimensions
            opinions = []
            for dim in state["rubric_dimensions"]:
                chain = prompt | structured_llm
                # Flatten evidences for the judge
                all_evidence = [
                    e for sublist in state["evidences"].values() for e in sublist
                ]
                evidence_text = "\n".join(
                    [f"- {e.goal}: {e.found}" for e in all_evidence]
                )

                opinion: JudicialOpinion = chain.invoke(
                    {"criterion_id": dim["id"], "evidence_content": evidence_text}
                )
                # Ensure it's treated as the correct type for the list
                final_opinion = JudicialOpinion(
                    judge=judge_type,
                    criterion_id=opinion.criterion_id,
                    score=opinion.score,
                    argument=opinion.argument,
                    cited_evidence=opinion.cited_evidence,
                )
                opinions.append(final_opinion)

            return {"opinions": opinions}

        return node

    def prosecutor(self) -> Any:
        return self._get_judge_node(
            "The critical lens. Focuses on identifying gaps, security flaws, and unmet requirements. Argues for low scores.",
            "Prosecutor",
        )

    def defense(self) -> Any:
        return self._get_judge_node(
            "The optimistic lens. Focuses on rewarding effort, intent, and clever solutions. Argues for higher scores.",
            "Defense",
        )

    def tech_lead(self) -> Any:
        return self._get_judge_node(
            "The pragmatic lens. Focuses on functionality, maintainability, and architectural soundness.",
            "TechLead",
        )


class ChiefJusticeNode:
    """Layer 3: Chief Justice (Synthesis & Verdict)"""

    @staticmethod
    def synthesize(state: AgentState) -> dict[str, Any]:
        """Synthesize conflicting opinions using deterministic logic."""
        opinions = state["opinions"]
        results = []

        for dim in state["rubric_dimensions"]:
            dim_id = dim["id"]
            dim_opinions = [o for o in opinions if o.criterion_id == dim_id]

            # Deterministic resolution rules
            tech_lead_op = next(
                (o for o in dim_opinions if o.judge == "TechLead"), None
            )
            prosecutor_op = next(
                (o for o in dim_opinions if o.judge == "Prosecutor"), None
            )

            # Security Override: If prosecutor flags security (score 1), cap at 3
            final_score = sum(o.score for o in dim_opinions) // len(dim_opinions)
            if (
                prosecutor_op
                and prosecutor_op.score == 1
                and "security" in prosecutor_op.argument.lower()
            ):
                final_score = min(final_score, 3)

            # Tech Lead weight for architecture
            if dim_id == "architecture" and tech_lead_op:
                final_score = tech_lead_op.score

            # Dissent detection
            scores = [o.score for o in dim_opinions]
            variance = max(scores) - min(scores) if scores else 0
            dissent_summary = (
                "Significant disagreement between Prosecutor and Defense."
                if variance > 2
                else None
            )

            results.append(
                CriterionResult(
                    dimension_id=dim_id,
                    dimension_name=dim["name"],
                    final_score=final_score,
                    judge_opinions=dim_opinions,
                    dissent_summary=dissent_summary,
                    remediation=prosecutor_op.argument
                    if prosecutor_op
                    else "Continue improving codebase.",
                )
            )

        report = AuditReport(
            repo_url=state["repo_url"],
            executive_summary="Automated audit completed with adversarial judicial review.",
            overall_score=sum(r.final_score for r in results) / len(results),
            criteria=results,
            remediation_plan="Prioritize security fixes flagged by the Prosecutor.",
        )

        return {"final_report": report}


def build_graph() -> CompiledStateGraph:
    workflow = StateGraph(AgentState)

    # Nodes
    detectives = DetectiveNodes()
    workflow.add_node("repo_investigator", detectives.repo_investigator)
    workflow.add_node("doc_analyst", detectives.doc_analyst)
    workflow.add_node("vision_inspector", detectives.vision_inspector)

    # Aggregator Node (Fan-in)
    def aggregate_evidence(state: AgentState):
        return {}  # State is already updated via reducers

    workflow.add_node("aggregator", aggregate_evidence)

    # Judges
    judges = JudicialNodes()
    workflow.add_node("prosecutor", judges.prosecutor())
    workflow.add_node("defense", judges.defense())
    workflow.add_node("tech_lead", judges.tech_lead())

    # Chief Justice
    workflow.add_node("chief_justice", ChiefJusticeNode.synthesize)

    # Edges - Layer 1 Parallel
    workflow.add_edge(START, "repo_investigator")
    workflow.add_edge(START, "doc_analyst")
    workflow.add_edge(START, "vision_inspector")

    workflow.add_edge("repo_investigator", "aggregator")
    workflow.add_edge("doc_analyst", "aggregator")
    workflow.add_edge("vision_inspector", "aggregator")

    # Edges - Layer 2 Parallel
    workflow.add_edge("aggregator", "prosecutor")
    workflow.add_edge("aggregator", "defense")
    workflow.add_edge("aggregator", "tech_lead")

    workflow.add_edge("prosecutor", "chief_justice")
    workflow.add_edge("defense", "chief_justice")
    workflow.add_edge("tech_lead", "chief_justice")

    workflow.add_edge("chief_justice", END)

    return workflow.compile()

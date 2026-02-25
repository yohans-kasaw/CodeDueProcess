# FDE Challenge Week 2: The Automaton Auditor

## 1. Mission Objective

Build a multi-agent LangGraph system that automates the auditing of a GitHub repository and an accompanying PDF report.

*   **Input**: A GitHub Repository URL and a PDF report URL.
*   **Process**: The system will use a hierarchical agent swarm to analyze the code and report, evaluate them against a rubric, and generate a verdict.
*   **Output**: A structured audit report in Markdown format.

## 2. System Architecture

The system must be implemented as a three-layer hierarchical StateGraph in LangGraph.

### 2.1. Layer 1: Detective Agents (Evidence Collection)

These agents collect objective facts from the provided artifacts. Their output must be a structured `Evidence` object.

*   **`RepoInvestigator`**: Analyzes the GitHub repository.
    *   **Tools**: `git clone`, `git log`, `ast` parsing.
    *   **Tasks**:
        *   Verify the existence and structure of Pydantic/TypedDict state definitions.
        *   Verify parallel graph wiring (`fan-out`/`fan-in`) using AST analysis, not string matching.
        *   Analyze `git log` for commit history patterns (iterative vs. monolithic).
*   **`DocAnalyst`**: Analyzes the PDF report.
    *   **Tools**: PDF parsing, cross-referencing.
    *   **Tasks**:
        *   Verify that file paths cited in the report exist in the repository.
        *   Verify that technical concepts mentioned (e.g., "Dialectical Synthesis") are explained in substance, not just listed.
*   **`VisionInspector`** (Implementation required, execution optional): Analyzes diagrams within the PDF.
    *   **Tools**: Image extraction, multimodal LLM (GPT-4o/Gemini).
    *   **Tasks**:
        *   Analyze architectural diagrams to confirm they accurately represent the parallel agent flow.

### 2.2. Layer 2: Judicial Agents (Parallel Evaluation)

These agents analyze the collected evidence for each rubric criterion. The three agents must run in parallel, each receiving the same evidence.

*   **`The Prosecutor`**: The critical lens. Focuses on identifying gaps, security flaws, and unmet requirements. Argues for low scores.
*   **`The Defense Attorney`**: The optimistic lens. Focuses on rewarding effort, intent, and clever solutions, even if imperfect. Argues for higher scores.
*   **`The Tech Lead`**: The pragmatic lens. Focuses on functionality, maintainability, and architectural soundness. Acts as a tie-breaker.

### 2.3. Layer 3: Chief Justice (Synthesis & Verdict)

This final node synthesizes the conflicting opinions from the Judicial Layer into a final verdict using deterministic logic.

*   **Input**: A list of `JudicialOpinion` objects from all three judges for every criterion.
*   **Process**: Apply hardcoded rules to resolve score disputes. For example, a confirmed security flaw identified by the Prosecutor caps the score, overriding the Defense's arguments.
*   **Output**: A final `AuditReport` object, which is then serialized into a Markdown file.

## 3. Core Implementation Requirements

### 3.1. Environment & State
*   **Dependencies**: Use `uv` for package management (`pyproject.toml`).
*   **Secrets**: Manage API keys via `.env` files.
*   **Observability**: Integrate LangSmith tracing from the start.
*   **State Management**:
    *   Define all graph state and agent outputs using Pydantic `BaseModel` or `TypedDict`. Do not use plain Python dictionaries for complex state.
    *   Use `Annotated` with `operator.add` and `operator.ior` to safely update state from parallel-running agents.

### 3.2. Data Models (Pydantic Schemas)

```python
import operator
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- Detective Output ---
class Evidence(BaseModel):
    goal: str
    found: bool
    content: Optional[str] = None
    location: str # File path or commit hash
    rationale: str
    confidence: float

# --- Judge Output ---
class JudicialOpinion(BaseModel):
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: List[str]

# --- Chief Justice Output ---
class CriterionResult(BaseModel):
    dimension_id: str
    dimension_name: str
    final_score: int = Field(ge=1, le=5)
    judge_opinions: List[JudicialOpinion]
    dissent_summary: Optional[str] = None # Required when score variance > 2
    remediation: str

class AuditReport(BaseModel):
    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: List[CriterionResult]
    remediation_plan: str

# --- Graph State ---
class AgentState(TypedDict):
    repo_url: str
    pdf_path: str
    rubric_dimensions: List[Dict]
    # Reducers prevent parallel agents from overwriting data
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    final_report: AuditReport
```

### 3.3. Tooling
*   **`RepoInvestigator` Tools**:
    *   Use Python's `ast` module for code analysis. Avoid regex.
    *   Clone repositories into a sandboxed temporary directory using `tempfile`.
    *   Handle `git` authentication and command errors gracefully.
*   **`DocAnalyst` Tools**:
    *   Implement a "RAG-lite" approach: chunk the PDF to allow for targeted querying rather than placing the entire text into context.

### 3.4. Graph Construction
*   **Parallelism**: Detectives must run in parallel branches. Judges must also run in parallel branches.
*   **Synchronization**: Implement a "fan-in" node to aggregate all `Evidence` before the Judicial layer begins.
*   **Structured Outputs**: Judges must return structured JSON matching the `JudicialOpinion` schema. Enforce this using `.with_structured_output()` or `.bind_tools()`, with retry logic for parsing failures.
*   **Constitution**: The agent prompts must dynamically load their rules from the provided `rubric.json` file.

## 4. Agent Protocols (The Constitution)

The agent's behavior is governed by a machine-readable `rubric.json`. Your system must load and distribute these rules to the correct agents.

### 4.1. Detective Protocols (Evidence Collection)

| Agent               | Evidence Class                   | Instructions                                                                                                                                                                                                                                   |
| ------------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RepoInvestigator**  | Git Forensic Analysis            | Run `git log`. Check for >3 commits and a logical progression. Flag single "init" commits.                                                                                                                                                     |
|                     | State Management Rigor           | Use AST to find `BaseModel` or `TypedDict` state definitions. Verify the state holds `Evidence` and `JudicialOpinion` objects. Check for `operator.add`/`ior` reducers.                                                                           |
|                     | Graph Orchestration              | Use AST to analyze `builder.add_edge()`. Verify fan-out/fan-in patterns for both Detectives and Judges. Check for a synchronization node.                                                                                                        |
|                     | Safe Tool Engineering            | Verify `git clone` occurs in a `tempfile.TemporaryDirectory`. Scan for raw `os.system` calls (failure). Check for `subprocess.run` with error handling.                                                                                          |
|                     | Structured Output Enforcement    | Scan Judge nodes. Verify LLMs are invoked with `.with_structured_output(JudicialOpinion)` or `.bind_tools()`.                                                                                                                                    |
| **DocAnalyst**        | Theoretical Depth                | Search PDF for keywords ("Dialectical Synthesis", "Fan-In / Fan-Out"). Verify they are explained with substance, not just dropped in.                                                                                                          |
|                     | Report Accuracy                  | Extract all file paths from the PDF. Cross-reference them with `RepoInvestigator`'s findings to identify "Hallucinated Paths".                                                                                                                     |
| **VisionInspector**   | Architectural Diagram Analysis | Extract and analyze diagrams. Classify them (e.g., StateGraph vs. generic flowchart). Verify the diagram visualizes parallel execution for Detectives and Judges.                                                                                 |

### 4.2. Judicial Guidelines (Sentencing)

*   **Prosecutor's Handbook**:
    *   If the graph is purely linear, "LangGraph Architecture" score is max 1.
    *   If Judges return freeform text (no structured output), "Judicial Nuance" score is max 2.
*   **Tech Lead's Handbook**:
    *   If state is managed with plain `dict`s instead of Pydantic/TypedDict, score is 3 ("Technical Debt").
    *   If `git clone` is not sandboxed, it is "Security Negligence" and overrides other scores.
*   **Defense Attorney's Handbook**:
    *   If the graph fails to compile but the underlying tools (e.g., AST parser) are well-built, argue for partial credit (score 3) on "Forensic Accuracy".
    *   If the `ChiefJusticeNode` is an LLM but the Judge personas are distinct and create real debate, argue for partial credit (score 3 or 4) on "Judicial Nuance".

### 4.3. Synthesis Rules (Chief Justice)

The `ChiefJusticeNode` must use hardcoded Python logic to:
*   **Security Override**: Confirmed security flaws cap the final score at 3.
*   **Fact Supremacy**: Detective evidence (facts) always overrules Judge opinions (interpretations).
*   **Functionality Weight**: The Tech Lead's opinion carries the highest weight for the architecture criterion.
*   **Dissent Requirement**: If score variance between judges is > 2, the final report must include a summary of the disagreement.

## 5. Deliverables

### 5.1. Interim Submission
1.  **PDF Report**: `reports/interim_report.pdf` or `reports/interim_report.md`
    *   Architecture decisions, known gaps, and plan for completion.
    *   Diagram of the planned StateGraph flow.
2.  **GitHub Repository**:
    *   `src/state.py`: Pydantic/TypedDict state definitions with reducers.
    *   `src/tools/repo_tools.py`: Sandboxed git tools and basic AST analysis.
    *   `src/tools/doc_tools.py`: PDF ingestion logic.
    *   `src/nodes/detectives.py`: Implemented `RepoInvestigator` and `DocAnalyst` nodes.
    *   `src/graph.py`: Partial graph wiring Detectives in parallel with a fan-in node.
    *   `pyproject.toml`: Locked dependencies.
    *   `.env.example`: Required environment variables.
    *   `README.md`: Setup and run instructions.

### 5.2. Final Submission (Saturday 21:00 UTC)
1.  **PDF Report**: `reports/final_report.pdf`
    *   Executive summary and architecture deep dive.
    *   Final StateGraph diagrams.
    *   Self-audit results and reflection on the peer-feedback loop.
2.  **GitHub Repository (Complete Source Code)**:
    *   `src/nodes/judges.py`: `Prosecutor`, `Defense`, and `Tech Lead` nodes with distinct prompts and enforced structured output.
    *   `src/nodes/justice.py`: `ChiefJusticeNode` with hardcoded conflict resolution rules.
    *   `src/graph.py`: Complete StateGraph with parallel flows for both detectives and judges.
3.  **Audit Reports (Generated Markdown)**:
    *   `audit/report_onself_generated/`: Report from running your agent on your own repo.
    *   `audit/report_onpeer_generated/`: Report from running your agent on a peer's repo.
    *   `audit/report_bypeer_received/`: The report generated by your peer's agent on your repo.
4.  **LangSmith Traces**: A public link to a full trace of your agent running.
5.  **Video Demonstration**: A screen recording showing the end-to-end workflow.

## 6. Evaluation Rubric

| Assessment Metric        | Score 1 (The Vibe Coder)                                                               | Score 3 (Competent Orchestrator)                                                                            | Score 5 (Master Thinker)                                                                                                                             |
| ------------------------ | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Forensic Accuracy**    | Agent hallucinates files/code. Fails to clone repo.                                    | Agent verifies file existence. Uses regex/simple parsing.                                                   | Agent uses AST parsing to confirm logic structure. Extracts and analyzes full git history.                                                           |
| **Judicial Nuance**      | A single "Grader" agent with no persona separation.                                    | Distinct "Prosecutor" and "Defense" roles exist, but synthesis is a simple average or an LLM prompt.        | Judges debate trade-offs. The final verdict is determined by deterministic rules and explains why one side was overruled.                              |
| **LangGraph Architecture** | A linear script with no state management or error handling.                              | Graph passes typed state correctly. Judges return structured JSON. Basic error handling is present.         | Uses parallel execution for Detectives and Judges. Implements data reducers (`operator.add`/`ior`). State is strictly typed with Pydantic.          |
| **The Feedback Loop**    | Peer feedback is ignored.                                                              | Basic bugs found by peers are fixed. Reflection acknowledges feedback.                                      | Peer feedback is used to find deep flaws. The student's own agent is then updated to detect those same flaws in others.                               |
| **Report Quality**       | Generic text with no actionable advice.                                                | Lists missing files and gives a score. Basic advice provided.                                               | A detailed "Remediation Plan" with specific file-level instructions and professional formatting.                                                     |

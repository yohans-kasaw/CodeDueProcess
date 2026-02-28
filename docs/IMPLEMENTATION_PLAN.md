# Implementation Plan: Auditor Architecture

This document outlines the implementation plan for the Auditor Architecture (The Digital Courtroom). It is updated with a Context7-backed validation of LangChain, LangGraph, LangSmith, and Rich APIs, with emphasis on replacing custom abstractions with stable library interfaces wherever possible.

## Context7 Verification Notes

- Verified APIs and patterns against Context7 docs for:
  - `langchain` (structured output + fake chat models)
  - `langgraph` (StateGraph topology, reducers, map-reduce/fan-out)
  - `langsmith` (tracing)
  - `rich` (styled console rendering, live updates)
- Key correction from research:
  - Prefer LangGraph node signatures like `node(state) -> dict` (or `node(state, runtime) -> dict`) over assuming `RunnableConfig` is always a direct node parameter.
  - Keep `RunnableConfig` for graph invocation config (`graph.invoke(input, config=...)`) and runtime context propagation.
- Library-over-custom guidance:
  - Use `GenericFakeChatModel` from `langchain_core.language_models.fake_chat_models` instead of custom `MockLLMClient`.
  - Use LangSmith tracing utilities (`@traceable`) instead of custom tracing wrappers.
  - Use Rich primitives (`Console`, `Panel`, `Table`, `Tree`, `Progress`, `Live`) instead of handcrafted ANSI formatting.

## Phase 0: Environment Setup

Before starting the core implementation, ensure the environment and dependencies are correctly set up.

- [ ] **Task 0.1: Update Dependencies**
    - Add/confirm these dependencies in `pyproject.toml`:
      - `langchain-core` (core model interfaces, fake chat models)
      - `langgraph` (orchestration)
      - `langsmith` (tracing)
    - If direct provider clients are used (OpenAI/Anthropic/etc.), keep provider packages separate from orchestration concerns.
    - Run `uv sync` (or equivalent) to install.

## Phase 1: Core Architecture & Orchestration Flow

**Goal:** Create a modular system where agents are orchestrated as a graph to produce an Audit Report, using LangChain's `BaseChatModel` interface.

### Step 1: LLM Abstraction

Leverage LangChain's native interfaces instead of custom wrappers to ensure compatibility with community tools.

- [x] **Task 1.1: Adopt `BaseChatModel` Interface**
    - Use `langchain_core.language_models.chat_models.BaseChatModel` as the standard interface for all agents.
    - Ensure all agent implementations accept a `BaseChatModel` instance (or a `Runnable` derived from it) through dependency injection.
    - Use `.with_structured_output(PydanticModel)` for type-safe generation and parser consistency.
    - *Note:* The `JudicialOpinion` schema (judge, criterion_id, score, argument, cited_evidence) is already defined in `src/codedueprocess/schemas/models.py`.

### Step 2: Agent Definitions (Graph Nodes)
Implement agents as LangGraph nodes (functions or runnables) that accept the graph state and return state updates.

- [x] **Task 2.1: Define Agent Interface/Signature**
    - Implement nodes primarily as `func(state: AgentState) -> dict`.
    - Use `func(state: AgentState, runtime: Runtime[ContextSchema]) -> dict` only when runtime context is required.
    - Inject LLM dependencies via closure/factory or graph context wiring, not via global singletons.
    - Each agent calls the LLM with structured output and returns partial state updates only.

- [x] **Task 2.2: Implement Detective Nodes**
    - Create `src/codedueprocess/agents/detectives.py`.
    - `repo_investigator_node`:
        - Input: `repo_path` from State.
        - Output: Updates `evidences` (merges `RepositoryFacts`).
    - `doc_analyst_node`:
        - Input: `doc_path` from State.
        - Output: Updates `evidences` (merges `ClaimSet`).

- [x] **Task 2.3: Implement Judge Nodes**
    - Create `src/codedueprocess/agents/judges.py`.
    - Define a factory or parameterized node for:
        - `Prosecutor` (Focus: flaws).
        - `DefenseAttorney` (Focus: strengths).
        - `TechLead` (Focus: synthesis).
    - All output `JudicialOpinion` objects which are appended to the `opinions` list in State (via `operator.add` reducer).

- [x] **Task 2.4: Implement Chief Justice Node**
    - Create `src/codedueprocess/agents/chief.py`.
    - `chief_justice_node`:
        - Input: Aggregates all `JudicialOpinion`s from State.
        - Output: Writes `final_report` (AuditReport) to State.

### Step 3: Orchestration Logic (The Graph)
Wire the agents together using `langgraph.graph.StateGraph`.

- [x] **Task 3.1: Define Graph Topology**
    - Create `src/codedueprocess/graph.py`.
    - Initialize `StateGraph(AgentState)`.
    - **Nodes:** Add `repo_investigator`, `doc_analyst`, `judge_group` (subgraph or Send-based map-reduce), `chief_justice`.
    - **Edges:**
        - Start -> [RepoInvestigator, DocAnalyst] (Parallel Fan-out)
        - [RepoInvestigator, DocAnalyst] -> Judge Fan-out (One set of judges per rubric dimension)
        - Judges -> ChiefJustice (Fan-in)
        - ChiefJustice -> End
    - Encode fan-out/fan-in explicitly.

- [x] **Task 3.2: Implement Parallel Execution**
    - Ensure the State definition (`src/codedueprocess/state.py`) correctly uses `Annotated[list, operator.add]` for lists like `evidences` and `opinions` to support parallel writes from multiple nodes without race conditions.

- [x] **Task 3.3: Add Runtime Context Schema (Optional but Recommended)**
    - Define LangGraph `context_schema` for runtime values (e.g., active model profile, thread id, trace metadata).
    - Keep node logic pure with respect to state updates; read runtime context only for configuration behavior.

### Step 4: Observability & Quality Gates (LangSmith)

- [ ] **Task 4.1: Trace Core Entry Points**
    - Add `@traceable` to top-level orchestration entry points (graph invocation boundary).
    - If direct SDK clients are used, wrap them with LangSmith wrappers where applicable.

- [ ] **Task 4.2: Clarify Interface Ownership**
    - Do **not** define custom tracing interfaces that duplicate LangSmith primitives.
    - Do **not** import LLM interfaces from LangSmith (LangSmith is observability/testing, not model abstraction).
    - Keep model interfaces from LangChain (`BaseChatModel`/Runnable) and orchestration interfaces from LangGraph.

### Step 5: Styled Console Printing (Rich)

**Goal:** Make orchestration progress easy to follow in real time with readable, structured, visually consistent terminal output aligned with architecture docs.

- [ ] **Task 5.1: Add Printing Module and Theme**
    - Create `src/codedueprocess/printing/console.py` with a `Console` factory and shared theme tokens.
    - Define semantic styles (e.g., `layer`, `agent`, `success`, `warning`, `error`, `metric`) instead of ad-hoc color strings.
    - Keep all rendering concerns in this module to avoid coupling business logic with terminal formatting.

- [ ] **Task 5.2: Implement Structured Renderers**
    - Create `src/codedueprocess/printing/renderers.py` with focused functions:
      - `print_audit_start(repo_url: str)` using `Panel`.
      - `print_layer_event(layer: str, message: str, agent: str | None = None)`.
      - `print_judge_deliberation(...)` using `Tree` or grouped log lines.
      - `print_chief_summary(...)` using `Table` for scorecard + output path.
    - Mirror the architecture doc sequence:
      - Layer 0 Ingestion
      - Layer 1 Detectives
      - Layer 2 Judges
      - Layer 3 Chief Justice

- [ ] **Task 5.3: Add Live Progress for Long Steps**
    - Use `Progress` (`SpinnerColumn`, elapsed time, task description) for long-running tasks like cloning, parsing, and graph execution.
    - Use `Live` for dynamic section updates when multiple parallel nodes are active.
    - Ensure live rendering degrades gracefully in non-interactive environments (CI or redirected output).

- [ ] **Task 5.4: Wire Printing into Orchestration**
    - Integrate renderer calls at orchestration boundaries in `src/codedueprocess/graph.py` and/or top-level run entrypoint.
    - Emit events from node boundaries (start, success, failure) without mixing agent reasoning text into UI formatter internals.
    - Keep the final markdown report generation separate from real-time console rendering.

- [ ] **Task 5.5: Logging and Printing Contract**
    - Define when to use Rich printing vs structured logs:
      - Rich: human-facing, real-time execution narrative.
      - Logs: machine-facing diagnostics and postmortem detail.
    - Ensure each important event has both a concise console representation and a structured log entry.

## Acceptance Criteria (Research-Backed)

- [ ] Node signatures and graph wiring follow current LangGraph patterns.
- [ ] Parallel writes use reducer-annotated state fields.
- [ ] Structured output is schema-validated.
- [ ] LangSmith tracing is integrated without replacing core model/orchestration interfaces.
- [ ] Styled console output is implemented with Rich primitives.

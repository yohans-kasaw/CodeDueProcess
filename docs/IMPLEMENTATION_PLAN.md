# Implementation Plan: Auditor Architecture

This document outlines a test-first implementation plan for the Auditor Architecture (The Digital Courtroom). It is updated with a Context7-backed validation of LangChain, LangGraph, LangSmith, and Rich APIs, with emphasis on replacing custom abstractions with stable library interfaces wherever possible.

## Context7 Verification Notes

- Verified APIs and patterns against Context7 docs for:
  - `langchain` (testing + structured output + fake chat models)
  - `langgraph` (StateGraph topology, reducers, node testing, map-reduce/fan-out)
  - `langsmith` (tracing + pytest integration)
  - `rich` (styled console rendering, live updates, test capture patterns)
- Key correction from research:
  - Prefer LangGraph node signatures like `node(state) -> dict` (or `node(state, runtime) -> dict`) over assuming `RunnableConfig` is always a direct node parameter.
  - Keep `RunnableConfig` for graph invocation config (`graph.invoke(input, config=...)`) and runtime context propagation.
- Library-over-custom guidance:
  - Use `GenericFakeChatModel` from `langchain_core.language_models.fake_chat_models` instead of custom `MockLLMClient`.
  - Use LangSmith tracing/testing utilities (`@traceable`, `pytest.mark.langsmith`, `langsmith.testing`) instead of custom tracing wrappers.
  - Use Rich primitives (`Console`, `Panel`, `Table`, `Tree`, `Progress`, `Live`) instead of handcrafted ANSI formatting.

## Phase 0: Environment Setup & Cleanup

Before starting the core implementation, ensure the environment and dependencies are correctly set up.

- [ ] **Task 0.1: Update Dependencies**
    - Add/confirm these dependencies in `pyproject.toml`:
      - `langchain-core` (core model interfaces, fake chat models)
      - `langgraph` (orchestration)
      - `langsmith` (tracing and test observability)
    - If direct provider clients are used (OpenAI/Anthropic/etc.), keep provider packages separate from orchestration/testing concerns.
    - Run `uv sync` (or equivalent) to install.

- [x] **Task 0.2: Cleanup Existing Tests**
    - Refactor or remove `tests/test_integration.py` and `tests/test_agent_nodes.py` if they rely on the obsolete `codedueprocess.agent` module.
    - Ensure `tests/` is aligned with the new `src/codedueprocess/agents` + `src/codedueprocess/graph.py` layout.
    - Preserve any reusable fixtures/assertion helpers that are still valid.

## Phase 1: Core Architecture & Orchestration Flow

**Goal:** Create a testable, modular system where agents are orchestrated as a graph to produce an Audit Report, using LangChain's `BaseChatModel` interface and `GenericFakeChatModel` for deterministic verification.

### Step 1: LLM Abstraction & Mocking
Leverage LangChain's native interfaces instead of custom wrappers to ensure compatibility with community tools and testing utilities.

- Verification scope note:
    - AI-agent verification should only use deterministic `MockLLM`/`GenericFakeChatModel`-based tests.
    - Human verification should run the actual provider-backed LLM checks separately.

- [x] **Task 1.1: Adopt `BaseChatModel` Interface**
    - Use `langchain_core.language_models.chat_models.BaseChatModel` as the standard interface for all agents.
    - Ensure all agent implementations accept a `BaseChatModel` instance (or a `Runnable` derived from it) through dependency injection.
    - Use `.with_structured_output(PydanticModel)` for type-safe generation and parser consistency.
    - Add one contract test that verifies each configured model supports structured output for the expected schema.
    - *Note:* The `JudicialOpinion` schema (judge, criterion_id, score, argument, cited_evidence) is already defined in `src/codedueprocess/schemas/models.py`.

- [x] **Task 1.2: Setup Testing Infrastructure with `GenericFakeChatModel`**
    - Create `tests/conftest.py` or `tests/fixtures.py`.
    - Implement fixtures that provide `GenericFakeChatModel` (from `langchain_core.language_models.fake_chat_models`) pre-loaded with deterministic responses.
    - Prefer `AIMessage` payloads for realistic behavior; include tool-call shaped messages if tools are used.
    - *Example usage:* `fake_llm = GenericFakeChatModel(messages=iter([AIMessage(content="..."), ...]))`.
    - This replaces a custom `MockLLMClient` and keeps tests aligned with LangChain runtime semantics.
    - Add a fixture variant that intentionally returns malformed output to verify schema validation failure paths.

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
        - Input: `docs_path` from State.
        - Output: Updates `evidences` (merges `ClaimSet`).

- [x] **Task 2.3: Implement Judge Nodes**
    - Create `src/codedueprocess/agents/judges.py`.
    - Define a factory or parameterized node for:
        - `Prosecutor` (Focus: flaws).
        - `DefenseAttorney` (Focus: strengths).
        - `TechLead` (Focus: synthesis).
    - All output `JudicialOpinion` objects which are appended to the `opinions` list in State (via `operator.add` reducer).
    - Add deterministic tests for each judge role with fixed evidence inputs and fake model outputs.

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
    - Encode fan-out/fan-in explicitly so concurrent branches are observable and testable.

- [x] **Task 3.2: Implement Parallel Execution**
    - Ensure the State definition (`src/codedueprocess/state.py`) correctly uses `Annotated[list, operator.add]` for lists like `evidences` and `opinions` to support parallel writes from multiple nodes without race conditions.
    - Add a focused concurrency test where two parallel nodes write to the same reducer-backed list and both values are preserved.

- [x] **Task 3.3: Add Runtime Context Schema (Optional but Recommended)**
    - Define LangGraph `context_schema` for runtime values (e.g., active model profile, thread id, trace metadata).
    - Keep node logic pure with respect to state updates; read runtime context only for configuration behavior.

### Step 4: Verification (The "Test")
Verify the entire flow using standard testing tools.

- [x] **Task 4.1: Unit Tests for Nodes**
    - Create `tests/test_agents.py`.
    - Test each node function in isolation by passing a mock State and a `GenericFakeChatModel`.
    - Verify that the node updates the state correctly (e.g., adds an opinion).
    - Also test compiled-node invocation (`compiled_graph.nodes["node_name"].invoke(...)`) for at least one node to validate LangGraph integration semantics.

- [x] **Task 4.2: Integration Test (End-to-End Flow)**
    - Create `tests/test_graph_flow.py`.
    - Instantiate the graph with a `GenericFakeChatModel` loaded with a sequence of responses corresponding to the execution order (Detectives -> Judges -> Chief).
    - `graph.invoke({...})`.
    - Assert `final_report` is present and valid.
    - Assert reducer-merged collections (`evidences`, `opinions`) contain expected cardinality and provenance.

- [x] **Task 4.3: Failure-Mode Tests**
    - Add tests for invalid structured output, missing evidence, and empty rubric dimensions.
    - Confirm errors are surfaced with actionable messages and do not silently drop state updates.

### Step 5: Observability & Quality Gates (LangSmith)

- [x] **Task 5.1: Trace Core Entry Points**
    - Add `@traceable` to top-level orchestration entry points (graph invocation boundary).
    - If direct SDK clients are used, wrap them with LangSmith wrappers where applicable.

- [x] **Task 5.2: Add Pytest + LangSmith Markers**
    - Add `pytest.mark.langsmith` to selected high-value integration tests.
    - Use `langsmith.testing` helpers (`log_inputs`, `log_outputs`, `log_reference_outputs`, optional feedback) for richer test diagnostics.

- [x] **Task 5.3: Clarify Interface Ownership**
    - Do **not** define custom tracing interfaces that duplicate LangSmith primitives.
    - Do **not** import LLM interfaces from LangSmith (LangSmith is observability/testing, not model abstraction).
    - Keep model interfaces from LangChain (`BaseChatModel`/Runnable) and orchestration interfaces from LangGraph.

### Step 6: Styled Console Printing (Rich)

**Goal:** Make orchestration progress easy to follow in real time with readable, structured, visually consistent terminal output aligned with architecture docs.

- [ ] **Task 6.1: Add Printing Module and Theme**
    - Create `src/codedueprocess/printing/console.py` with a `Console` factory and shared theme tokens.
    - Define semantic styles (e.g., `layer`, `agent`, `success`, `warning`, `error`, `metric`) instead of ad-hoc color strings.
    - Keep all rendering concerns in this module to avoid coupling business logic with terminal formatting.

- [ ] **Task 6.2: Implement Structured Renderers**
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

- [ ] **Task 6.3: Add Live Progress for Long Steps**
    - Use `Progress` (`SpinnerColumn`, elapsed time, task description) for long-running tasks like cloning, parsing, and graph execution.
    - Use `Live` for dynamic section updates when multiple parallel nodes are active.
    - Ensure live rendering degrades gracefully in non-interactive environments (CI or redirected output).

- [ ] **Task 6.4: Wire Printing into Orchestration**
    - Integrate renderer calls at orchestration boundaries in `src/codedueprocess/graph.py` and/or top-level run entrypoint.
    - Emit events from node boundaries (start, success, failure) without mixing agent reasoning text into UI formatter internals.
    - Keep the final markdown report generation separate from real-time console rendering.

- [ ] **Task 6.5: Testability of Console Output**
    - Add `tests/test_printing.py` using Rich-supported capture patterns:
      - `Console(file=StringIO())` for deterministic string assertions.
      - `console.capture()` for isolated output blocks.
    - Assert key invariants (layer labels, agent names, score formatting, output path) rather than brittle full-frame snapshots.
    - Add one smoke test for `Live`/`Progress` paths to ensure no runtime exceptions in headless test mode.

- [ ] **Task 6.6: Logging and Printing Contract**
    - Define when to use Rich printing vs structured logs:
      - Rich: human-facing, real-time execution narrative.
      - Logs: machine-facing diagnostics and postmortem detail.
    - Ensure each important event has both a concise console representation and a structured log entry.

## Acceptance Criteria (Research-Backed)

- [ ] No custom mock LLM client exists; tests rely on LangChain fake chat models.
- [ ] Node signatures and graph wiring follow current LangGraph patterns.
- [ ] Parallel writes use reducer-annotated state fields and are covered by tests.
- [ ] Structured output is schema-validated and covered for both success and failure paths.
- [ ] LangSmith tracing/testing is integrated without replacing core model/orchestration interfaces.
- [ ] Styled console output is implemented with Rich primitives and covered by deterministic tests.

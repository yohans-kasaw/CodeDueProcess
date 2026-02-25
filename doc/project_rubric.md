# Evaluation Rubric

## 1. Typed State Definitions
Evaluate whether the state layer uses typed structures (Pydantic BaseModel and/or TypedDict) with proper state reducers to support safe parallel agent execution. This criterion assesses the data model design, not how it is used in the graph. 

**What to look for:**
1. Classes or type definitions for detective output (evidence), judicial output (opinions), and the graph state container.
2. Reducer annotations (e.g., `Annotated[..., operator.add]`) that prevent parallel writes from overwriting each other.
3. Field-level type annotations and validation constraints.
4. Completeness across all expected output types (Evidence, JudicialOpinion, AgentState or equivalents).

### Grading Tiers
* **Master Thinker (5 pts):** All state structures use Pydantic BaseModel or TypedDict with full type annotations. Both list and dict reducers are present and correctly annotated to handle parallel writes (e.g., `operator.add` for lists, `operator.ior` for dicts). Field constraints enforce valid ranges (e.g., score bounded 1-5, confidence as float). Evidence, JudicialOpinion (or equivalent), and the main AgentState are all fully defined with descriptions or docstrings. State design clearly supports the parallel detective pattern.
* **Competent Orchestrator (3 pts):** Graph state uses TypedDict or BaseModel. Detective output and judicial output are defined as typed structures (Pydantic BaseModel or dataclass with typed fields). At least one reducer is present (e.g., `operator.add` for list accumulation). Core fields are typed (score as int, confidence as float, etc.). *Missing:* full reducer coverage (may have `operator.add` for lists but miss `operator.ior` for dict merging). Judicial output schema may lack field constraints (e.g., score not bounded 1-5). One or more output types may be missing or incomplete (e.g., Evidence defined but no JudicialOpinion).
* **Vibe Coder (1 pts):** State definitions exist but use plain dicts or loosely typed structures. May have a Pydantic model for one output type but the main graph state is an untyped dict. No reducers present, meaning parallel agents would silently overwrite each other's data. *Missing:* reducer annotations on collection fields, typed definitions for at least one of detective output, judicial output, or graph state container, type annotations or validation constraints on fields.
* **Non-existent (0 pts):** No state definitions found. Or state is passed as untyped plain Python dicts throughout with no attempt at structured typing.

---

## 2. Forensic Tool Engineering
Evaluate the quality and safety of the raw tool functions that interact with external systems (git, file system, PDF parsing). This criterion evaluates the raw tool functions only. It does not assess whether these tools are wrapped into LangGraph-compatible nodes or produce structured Evidence objects. Evaluate only the tool logic itself: sandboxing, parsing approach, error handling, and safety. 

**What to look for:**
1. Git clone using sandboxed temp directories (`tempfile` or equivalent).
2. AST-based code analysis (not regex) for verifying code structure.
3. PDF ingestion with chunking or queryable interface.
4. Proper error handling around shell/subprocess calls.
5. No raw `os.system()` calls.

### Grading Tiers
* **Master Thinker (5 pts):** All external interactions are sandboxed and error-handled. AST parsing traverses the tree to verify structural properties (e.g., class inheritance, method calls like `add_edge`, decorator usage) rather than just matching names. PDF ingestion provides a chunked, queryable interface (RAG-lite: the agent can ask targeted questions rather than receiving the full text). Git operations handle edge cases (bad URLs, auth failures, empty repos) with informative error messages. No `os.system()` calls anywhere.
* **Competent Orchestrator (3 pts):** Git operations use `tempfile.TemporaryDirectory()` or equivalent sandbox. `subprocess.run()` (or equivalent) used instead of raw `os.system()`. At least basic error handling exists (return codes checked or exceptions caught). Code analysis uses Python's `ast` module or a parser library for at least some checks. PDF ingestion exists and extracts text, though chunking may be naive (e.g., page-level splits only). *Missing:* robust error handling (capturing stderr, handling auth failures gracefully), deep AST parsing (may only check class names but not inheritance or method calls), semantic PDF chunking, git URL input sanitization.
* **Vibe Coder (1 pts):** Tools exist but have critical safety issues. Git clone uses `os.system()` or drops repos into the working directory without sandboxing. Code analysis relies entirely on regex or string matching. PDF ingestion dumps the entire document as a single string with no chunking. No error handling around external calls. *Missing:* sandboxed execution, AST-based parsing, error handling on subprocess/shell calls, any chunking strategy for PDF content.
* **Non-existent (0 pts):** No tool implementations found. Or tools are empty stubs with no logic.

---

## 3. Detective Node Implementation
Evaluate whether the detective agents are implemented as proper LangGraph-compatible nodes that produce structured Evidence output. This criterion assesses the LangGraph node integration layer: functions that accept graph state and return structured Evidence objects. It does not assess the quality of the underlying tool logic (sandboxing, AST parsing depth, error handling around shell calls), nor does it assess how nodes are wired together in the StateGraph. Evaluate only node function signatures, Evidence output structure, and separation of fact-finding from opinion-forming. 

**What to look for:**
1. At least two detective node functions (RepoInvestigator and DocAnalyst, or equivalents).
2. Functions that accept graph state as input and return structured Evidence objects.
3. Forensic protocols: nodes collect facts, not opinions.
4. Graceful handling of missing artifacts.

### Grading Tiers
* **Master Thinker (5 pts):** Detective nodes produce rich, structured Evidence objects with all fields populated (goal, found, content, location, rationale, confidence or equivalents). Repo detective performs multiple forensic checks (git history, state definitions, graph structure, tool safety). Doc detective extracts and queries PDF content for specific concepts. Nodes handle missing artifacts gracefully (returning Evidence with `found: false` and explanatory rationale rather than crashing). Output is purely factual with no scoring or judgment embedded.
* **Competent Orchestrator (3 pts):** At least two detective nodes exist (repo analysis and document analysis, or equivalents). They accept graph state and return structured Evidence objects matching the typed definitions from the state layer. Each node targets a distinct artifact type. Output includes factual findings (file exists/doesn't, code snippet captured, commit history extracted). *Missing:* full forensic protocol coverage, deep structural analysis (nodes may check file existence but not structure), confidence scores or rationale fields on Evidence objects, graceful error handling for missing artifacts.
* **Vibe Coder (1 pts):** Detective functions exist but do not follow node conventions. They may return raw strings or untyped dicts instead of structured Evidence objects. Functions may not accept or return state in a way compatible with a StateGraph. Logic may mix evidence collection with judgment (opinionating instead of collecting facts). *Missing:* structured Evidence output, state-compatible function signatures, separation of fact-finding from opinion-forming.
* **Non-existent (0 pts):** No detective node implementations found. No LangGraph node that performs evidence collection.

---

## 4. Partial Graph Orchestration
Evaluate whether the StateGraph is wired to run detective nodes in parallel (fan-out) and synchronize their results through an aggregation node (fan-in) before downstream processing. Judges are not required at interim, but the detective orchestration pattern must be functional. This criterion assesses the StateGraph composition: how nodes are wired together with edges, parallel branching, synchronization points, and conditional routing. It does not assess the internal logic of individual node functions or the quality of their output structures. Evaluate only the graph definition, edge wiring, fan-out/fan-in patterns, and whether the graph compiles and runs. 

**What to look for:**
1. StateGraph instantiation with nodes and edges.
2. Parallel fan-out from a common entry point to multiple detective nodes.
3. Synchronization/aggregation node (fan-in) collecting all evidence.
4. Conditional edges for error handling.
5. Graph compiles and is runnable end-to-end for the detective phase.

### Grading Tiers
* **Master Thinker (5 pts):** Detective fan-out/fan-in is fully functional. Aggregation node consolidates evidence from all detectives into a unified state. Conditional edges handle failure cases (e.g., skip a detective if its target artifact is unavailable). Graph structure clearly indicates where the judicial layer will attach (even if judges are stubs or absent). The graph is runnable end-to-end for the detective phase, producing aggregated Evidence as output. Graph may include placeholder nodes or comments for the judicial fan-out/fan-in pattern.
* **Competent Orchestrator (3 pts):** StateGraph wires detective nodes in parallel (fan-out from a common entry point). An aggregation node (or equivalent synchronization point) collects results before the graph continues. Graph compiles and can be invoked. The fan-out/fan-in pattern is structurally present. *Missing:* conditional edges for error handling (e.g., what if a detective fails), placeholder structure for where judges will be added later, meaningful evidence consolidation in the aggregation node (may be a pass-through), retry or fallback logic.
* **Vibe Coder (1 pts):** A StateGraph is instantiated but detectives are wired sequentially (A -> B -> C). No parallel branching. May have nodes added but no edges, or edges form a simple linear chain. Graph may not compile or may be missing START/END connections. *Missing:* parallel fan-out from a single node to multiple detectives, any synchronization/aggregation node, conditional edges for error handling.
* **Non-existent (0 pts):** No StateGraph definition found. Or a graph is imported but never instantiated or wired.

---

## 5. Project Infrastructure
Evaluate whether the repository is set up as a reproducible, professionally structured project that another engineer could clone and run. 

**What to look for:**
1. Dependency management: `pyproject.toml` with locked dependencies via `uv`.
2. Environment variable handling: `.env.example` with no secrets committed.
3. README with setup and execution instructions.
4. Clean project structure with logical layout.
5. No committed secrets, large binaries, or IDE-specific configuration.

### Grading Tiers
* **Master Thinker (5 pts):** Dependencies managed via `uv` with locked versions (`pyproject.toml` + lock file). `.env.example` is comprehensive with descriptions of each variable. README provides complete setup-to-execution instructions: install dependencies, configure environment, run the detective graph against a target repo URL. Project structure is clean and logical. Repository contains no committed secrets, no large binary files, no IDE-specific configuration polluting the root.
* **Competent Orchestrator (3 pts):** `pyproject.toml` (or equivalent) lists all necessary dependencies. `.env.example` exists and lists required API keys/environment variables without actual secrets. README includes setup instructions (how to install dependencies) and basic run instructions. Project structure follows a logical layout. *Missing:* detail on how to run the detective graph against a target repo URL, mention of required Python version or runtime prerequisites. Setup instructions may assume implicit knowledge.
* **Vibe Coder (1 pts):** A `requirements.txt` or `pyproject.toml` exists but is incomplete (missing key dependencies). No `.env.example`, or actual secrets are committed. README is absent or says only 'Week 2 project.' No instructions for how to run the code. *Missing:* usable setup instructions, secure environment variable handling, complete dependency specification.
* **Non-existent (0 pts):** No dependency file, no README, no environment configuration. A bare collection of Python files with no project structure.

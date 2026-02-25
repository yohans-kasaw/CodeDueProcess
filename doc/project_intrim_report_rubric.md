# Technical Assessment Rubric
**Total Possible Score: 15 Points**

---

## 1. Architecture Decision Rationale
**Max Points: 5**

**Evaluation Criteria:**
*   **Justification:** Provides substantive justification for core technical choices rather than just stating selections.
*   **Trade-off Analysis:** Demonstrates understanding of benefits and costs (why one tool/pattern was chosen over another).
*   **Key Decisions Expected:**
    1.  Why Pydantic/TypedDict over plain dicts for state.
    2.  How AST parsing was structured (and why not regex).
    3.  Sandboxing strategy for cloning unknown repos.
    4.  Other significant design trade-offs (e.g., RAG-lite approach, choice of LLM provider).

| Performance Level | Points | Description |
| :--- | :--- | :--- |
| **Master Thinker** | **5 pts** | Covers all major architectural decisions with trade-off analysis. Each choice is tied to a specific failure mode it prevents (e.g., "regex breaks on multiline class definitions; AST handles nested structures reliably"). Discusses alternatives considered and why they were rejected. Reasoning is original, not parroted from the challenge spec. |
| **Competent Orchestrator** | **3 pts** | Explains the reasoning behind at least two major decisions with clear cause-effect logic (e.g., "Pydantic enforces typed state so parallel agents cannot corrupt shared data with untyped dicts"). Shows awareness of the problem each choice solves. **Missing:** coverage of all core decisions. May justify Pydantic well but skip sandboxing rationale or AST-vs-regex reasoning. Trade-off discussion is one-sided (explains benefits but not costs or alternatives rejected). |
| **Vibe Coder** | **1 pts** | Mentions tools or libraries chosen (e.g., "We used Pydantic") but provides no reasoning. Reads like a technology shopping list. May copy challenge spec language without adding original analysis. **Missing:** why each choice was made, no trade-off discussion, no mention of alternatives considered, no connection between the choice and the problem it solves. |
| **Non-existent** | **0 pts** | Nothing submitted, or report contains no discussion of technical choices. No mention of architectural reasoning whatsoever. |

---

## 2. Gap Analysis and Forward Plan
**Max Points: 5**

**Evaluation Criteria:**
*   **Honesty & Self-Awareness:** Honest assessment of what is not yet built.
*   **Actionability:** The plan is concrete enough for another engineer to pick up, not just aspirational.
*   **Judicial & Synthesis Depth:** Specific details on persona differentiation, parallel execution, structured output, and conflict resolution.
*   **Note:** This criterion assesses planning quality, not whether the code currently exists or functions.

| Performance Level | Points | Description |
| :--- | :--- | :--- |
| **Master Thinker** | **5 pts** | Provides a granular, sequenced plan covering the judicial layer (persona differentiation, parallel execution, structured output) and the synthesis engine (hardcoded rules, dissent generation, variance re-evaluation). Identifies specific risks or failure modes in the planned work (e.g., "LLM may ignore persona constraints and converge to similar opinions"). Plan is actionable enough that another engineer could pick it up. |
| **Competent Orchestrator** | **3 pts** | Identifies specific unfinished components (e.g., "Judge nodes exist as stubs but lack distinct persona prompts" or "ChiefJustice has no deterministic conflict resolution yet"). Plan describes the approach for at least two of: persona prompting strategy, structured output enforcement, deterministic synthesis rules. Shows awareness of what is hard about the remaining work. **Missing:** full coverage of all remaining layers. May describe the judicial layer well but omit the synthesis engine's conflict resolution strategy (or vice versa). May lack sequencing or prioritization. Does not anticipate specific failure modes. |
| **Vibe Coder** | **1 pts** | Acknowledges gaps exist but in vague terms (e.g., "We still need to build the judges"). No specifics about what the judicial layer requires or how the synthesis engine will resolve conflicts. Plan is a restated to-do list from the challenge spec. **Missing:** concrete detail on how judicial personas will be prompted differently, how structured output will be enforced, or how the Chief Justice will resolve score variance. No timeline or sequencing. |
| **Non-existent** | **0 pts** | No mention of gaps or future plans. Or the report claims everything is complete with no remaining work. |

---

## 3. StateGraph Architecture Diagram
**Max Points: 5**

**Evaluation Criteria:**
*   **Flow Representation:** Accurately represents the multi-agent architecture (Hierarchical flow: Detectives -> Aggregation -> Judges -> ChiefJustice).
*   **Parallelism:** Shows parallel fan-out/fan-in patterns for *both* the detective and judicial layers.
*   **Synchronization:** Visual distinction of aggregation nodes.
*   **Data Detail:** State types or data labels on edges; conditional edges or error handling paths.

| Performance Level | Points | Description |
| :--- | :--- | :--- |
| **Master Thinker** | **5 pts** | Diagram clearly shows both parallel patterns: detectives fan-out/fan-in **AND** judges fan-out/fan-in. Synchronization points (aggregator nodes) are visually distinct. State types or data flowing between layers are indicated (e.g., arrows labeled with Evidence, JudicialOpinion). Includes conditional edges or error paths (e.g., what happens if a detective fails). Flow is consistent with the Digital Courtroom architecture. |
| **Competent Orchestrator** | **3 pts** | Diagram shows the hierarchical structure with at least one parallel fan-out/fan-in pattern (e.g., detectives running in parallel converging to an aggregator). Nodes are labeled with meaningful names (detective agents, judges, or equivalent concepts). Shows the general flow: evidence collection -> aggregation -> judgment -> synthesis. **Missing:** the second parallel pattern (judges fan-out/fan-in). May show detectives in parallel but judges as sequential. No indication of state types flowing between nodes. No conditional edges or error handling paths. |
| **Vibe Coder** | **1 pts** | A diagram exists but shows a simple linear pipeline (e.g., boxes connected in a straight chain). Or the diagram is a generic flowchart with no connection to LangGraph concepts (no state, no nodes, no edges). Labels are vague (e.g., "Step 1", "Step 2"). **Missing:** parallel branching, fan-out or fan-in points, distinction between detective and judicial layers, indication of state flow or synchronization. |
| **Non-existent** | **0 pts** | No diagram present in the report. No visual representation of the architecture whatsoever. |

---

### Scoring Summary
| Category | Score |
| :--- | :--- |
| Architecture Decision Rationale | __ / 5 |
| Gap Analysis and Forward Plan | __ / 5 |
| StateGraph Architecture Diagram | __ / 5 |
| **TOTAL** | **__ / 15** |

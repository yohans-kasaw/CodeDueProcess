# Auditor Architecture: The Digital Courtroom

## 1. Business Goal & Mission

**Goal:** Automate comprehensive code quality assurance and verify architectural claims. The system bridges the gap between rapid AI code generation and human review capacity.

**Mission:** Build a "Digital Courtroom" that ingests a GitHub repository and a project report (PDF/Markdown). It processes these inputs through a multi-agent system—Detectives, Judges, and a Chief Justice—to produce a production-grade **Audit Report**.

**Core Philosophy:**
*   **Forensic Objectivity:** Code is truth. Evidence from the repository supersedes claims in documentation.
*   **Dialectical Evaluation:** Quality is assessed through adversarial debate (Prosecution vs. Defense) synthesized by a technical expert.
*   **Rubric-Driven:** All analysis is grounded in a flexible, dynamically loaded evaluation rubric.

## 2. High-Level Architecture

The system follows a three-layer pipeline implemented as a directed acyclic graph (DAG).

### Input
*   **GitHub Repository URL:** The codebase to be audited.
*   **Documentation Artifact:** A PDF or Markdown report describing the architecture, design decisions, and claims.

### Layer 1: Detectives (Fact Collection)
*Parallel Execution*

Agents in this layer gather raw data. They do not judge; they strictly collect facts and extract claims.

1.  **Repo Investigator (The "Forensics Lab")**
    *   **Role:** Analyzes the codebase structure, history, and patterns.
    *   **Scope:** Multi-language support (Python, JS/TS, Go, Rust, etc.).
    *   **Tools:**
        *   `git`: Commit history, branching analysis.
        *   `tree-sitter`: Abstract Syntax Tree (AST) parsing for structural analysis (class hierarchies, function complexity, dependency graphs).
        *   `grep/glob`: Pattern matching for specific keywords or anti-patterns.
    *   **Output:** `RepositoryFacts` (structured JSON containing file stats, commit patterns, AST summaries).

2.  **Doc Analyst (The "Archivist")**
    *   **Role:** Parses the submitted documentation to understand *intent* and *claims*.
    *   **Tasks:**
        *   Extracts architectural claims (e.g., "Uses Model-View-Controller pattern").
        *   Identifies stated features and requirements.
    *   **Tools:** PDF/Markdown parsers, NLP extraction.
    *   **Output:** `ClaimSet` (structured list of assertions made by the authors).

### Layer 2: Judges (Criterion Analysis)
*Hybrid Adversarial Flow*

For **each** dimension in the evaluation rubric, three agents analyze the evidence.

**Phase 2a: Arguments (Parallel)**

1.  **The Prosecutor (Critical Analyst)**
    *   **Goal:** Identify flaws, missing requirements, bugs, and contradictions between `RepositoryFacts` and `ClaimSet`.
    *   **Mindset:** "Guilty until proven innocent." Focuses on technical debt and security risks.
    *   **Output:** `ProsecutionBrief` (Score recommendation: Low, Argument, Citations).

2.  **The Defense Attorney (Optimistic Advocate)**
    *   **Goal:** Highlight implementation effort, creative solutions, and adherence to the spirit of the requirements.
    *   **Mindset:** "Innocent until proven guilty." Contextualizes partial implementations or alternative patterns.
    *   **Output:** `DefenseBrief` (Score recommendation: High, Argument, Mitigating Factors).

**Phase 2b: Synthesis (Sequential)**

3.  **The Tech Lead (Pragmatic Tie-Breaker)**
    *   **Goal:** Determine the technical truth.
    *   **Input:** `ProsecutionBrief`, `DefenseBrief`, and raw Evidence.
    *   **Action:** Weighs the validity of the Prosecutor's complaints against the Defense's context. Evaluates architectural soundness and maintainability.
    *   **Output:** `JudicialOpinion` (Final Score [0-5], Synthesized Rationale).

### Layer 3: Chief Justice (Final Verdict)
*Aggregation & Reporting*

1.  **Chief Justice**
    *   **Role:** Aggregates opinions from all rubric dimensions.
    *   **Decision Rules:**
        *   **Security Veto:** Confirmed security vulnerabilities cap the maximum possible score.
        *   **Evidence Primacy:** If code contradicts a documentation claim, the code (Repo Investigator) rules.
        *   **Consensus Check:** Flags dimensions with high variance between Prosecutor and Defense for human review in the report.
    *   **Output:** A structured Markdown **Audit Report** containing:
        *   Executive Summary.
        *   Scorecard per dimension.
        *   Key Findings (Strengths & Weaknesses).
        *   Remediation Steps.

## 3. Data Structures & Schema

### The Universal Rubric
The system is agnostic to the specific criteria being judged. The Rubric is injected at runtime.

```python
class Dimension(BaseModel):
    id: str                 # e.g., "git_history", "modular_architecture"
    weight: float           # Importance (0.0 - 2.0)
    criteria: List[str]     # Specific items to check
    success_pattern: str    # Description of a "5"
    failure_pattern: str    # Description of a "0"

class Rubric(BaseModel):
    name: str
    dimensions: List[Dimension]
    global_constraints: List[str] # e.g., "No API keys in code"
```

### Evidence Exchange
```python
class Evidence(BaseModel):
    source: Literal["repo", "doc"]
    content: Any            # Structured data from tree-sitter or doc parse
    location: str           # File path or Page number
    confidence: float
```

## 4. Implementation Strategy

*   **Orchestration:** LangGraph state machine to manage the DAG workflow (Detectives -> Parallel Judges -> Tech Lead -> Chief Justice).
*   **Sandboxing:** All repository operations (`git clone`, analysis) occur in ephemeral, sandboxed environments to prevent malicious code execution during analysis.
*   **Observability:**
    *   Real-time console output using `rich` (status panels, evidence tables).
    *   Structured logging of agent reasoning for debugging.
*   **Modularity:**
    *   Detectives are independent plugins.
    *   Rubrics are JSON/YAML configuration files.
    *   Judges are prompt-engineered LLM nodes sharing a common interface.

## 5. Printing Infrastructure

Rich console output for observability and debugging:

```
╔════════════════════════════════════════════════════════════════╗
║ 🔍 AUDIT STARTED: github.com/user/repo                         ║
╚════════════════════════════════════════════════════════════════╝

[14:32:15] 🕵️  LAYER 1: DETECTIVES
           ├─ RepoInvestigator: Analyzing git history (tree-sitter)...
           ├─ RepoInvestigator: ✓ 12 commits found
           ├─ DocAnalyst: Parsing PDF report...
           └─ DocAnalyst: ✓ 8 pages processed

[14:32:42] ⚖️  LAYER 2: JUDGES (Git Forensic Analysis)
           ├─ Prosecutor: Score 3/5 - "Limited progression pattern"
           ├─ Defense: Score 4/5 - "Adequate iterative development"  
           └─ Tech Lead: Score 3/5 - "Functional but could be clearer"

[14:33:01] 📊 CHIEF JUSTICE SYNTHESIS
           ├─ Score variance: 1 point (within tolerance)
           ├─ Final Score: 3.3/5
           └─ Output: /output/audit_report.md
```

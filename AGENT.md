# CodeDueProcess - Agent Instructions

**Objective:** To provide a multi-agent adversarial framework for auditing AI codebases, ensuring spec and logic compliance through structured debate.

## 1. Source of Truth
- **Specs:** `specs/` (feature specs, architecture)
- You **MUST** read the relevant specs before proposing or writing code.

## 2. Handling Ambiguity
If a request is ambiguous or contradicts the specs:
- Do not guess.
- Do not "make it up".
- Do the non-blocked work (discovery, outlining options), then ask **ONE** targeted question to clarify.

## 3. Tech Stack & Standards
- **Language:** Python 3.12+
- **Dependency Manager:** `uv` (do not use pip/poetry/conda)
- **Data Contracts:** Pydantic v2
- **Lint/Format:** Ruff
- **Typing:** `mypy --strict`; avoid `Any` unless required (must annotate with `# justification: [reason]`)
- **Testing:** `pytest` (+ `pytest-asyncio`)

## 4. Safety & Repo Hygiene
- **No Secrets:** Never commit secrets. Config files must reference env var names only.
- **Git Safety:** Avoid destructive git commands unless explicitly requested.
- **Scope:** Keep changes minimal, focused, and strictly spec-aligned.

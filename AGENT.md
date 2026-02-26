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
- **Testing:** `pytest` (+ `pytest-asyncio`, `pytest-mock`, `pytest-cov`)
- **Documentation:** Use Google-style Python docstrings for all modules, classes, and functions to explain logic and intent. Compliance is enforced via Ruff.

## 4. Test-Driven Development (TDD) Workflow

All code contributions **MUST** follow TDD practices:

### TDD Cycle
1. **Red:** Write a failing test for the desired behavior
2. **Green:** Write minimal code to make the test pass
3. **Refactor:** Clean up code with tests still passing
4. **Repeat:** Move to next test

### Testing Rules
- **Before Implementation:** Tests must be written or updated before modifying source code
- **Test Coverage:** Every public function/method must have at least one test
- **Mock External Dependencies:** LLM calls, API requests, and external services must be mocked in unit tests
- **Test Structure:** Use descriptive test classes and methods (`Test<Component>::test_<behavior>_<scenario>`)
- **Edge Cases:** Test both happy paths and error conditions
- **Parametrization:** Use `pytest.mark.parametrize` for multiple similar test cases

### Running Tests
```bash
# Install dependencies
uv sync --group test
uv pip install -e .

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_<module>.py

# Run with coverage
uv run pytest --cov=src/codedueprocess --cov-report=term-missing

# Run without integration tests
uv run pytest -m "not integration"

# Run only fast tests
uv run pytest -m "not slow"
```

### Test Organization
```
tests/
├── test_<module>.py        # Tests for src/codedueprocess/<module>.py
├── conftest.py             # Shared fixtures
└── __init__.py             # Package marker
```

## 5. Safety & Repo Hygiene
- **No Secrets:** Never commit secrets. Config files must reference env var names only.
- **Git Safety:** Avoid destructive git commands unless explicitly requested.
- **Scope:** Keep changes minimal, focused, and strictly spec-aligned.

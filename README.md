# CodeDueProcess

**AI-powered code review and compliance system for legal due diligence.**

This project implements an intelligent agent system using LangGraph for automating code review workflows and ensuring compliance with legal and regulatory requirements.

## Project Structure

```
CodeDueProcess/
├── src/
│   ├── codedueprocess/     # Main implementation (empty - awaiting actual implementation)
│   └── sandbox/            # LangGraph testing environment
├── pyproject.toml          # Project configuration
├── langgraph.json          # LangGraph deployment config
└── README.md
```

### `src/codedueprocess/`
Empty package reserved for the actual **CodeDueProcess** implementation. This is where the production code for the AI-powered code review system will be built.

### `src/sandbox/`
**LangGraph testing environment** - Contains experimental code and proof-of-concept implementations for:

- **Multi-agent workflows**: Researcher and Analyst agents collaborating via a Supervisor
- **Tool usage**: Web search, weather API, and statistical analysis tools
- **Agent state management**: Graph-based state transitions and decision routing
- **Caching**: Custom SQLite cache implementation for LLM responses
- **Configuration**: Environment-based configuration system

The sandbox serves as a testing ground for LangGraph patterns and agent behaviors before they're integrated into the main `codedueprocess` package.

## Sandbox Components

| File | Purpose |
|------|---------|
| `agent.py` | Multi-agent workflow with Supervisor, Researcher, and Analyst nodes |
| `tools.py` | Mock tools for demonstration (search, weather, stats) |
| `config.py` | Environment configuration and constants |
| `cache.py` | Custom SQLite cache for LLM responses with LiteLLM sanitization |
| `main.py` | Entry point and example usage |

## Development

- **Sandbox** (`src/sandbox/`): Experiment with LangGraph patterns
- **Production** (`src/codedueprocess/`): Reserved for the actual implementation

## License

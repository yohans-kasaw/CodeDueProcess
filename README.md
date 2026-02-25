# CodeDueProcess

> "There are only two hard problems in Computer Science: cache invalidation and naming things."
> — Phil Karlton

This project is about the none of the two.

An autonomous multi-agent swarm that audits codebases using LangGraph. It clones repos, analyzes AST structure, queries documents via RAG, and runs a digital courtroom with prosecutor, defense, and tech lead agents to evaluate code quality.

## Setup

```bash
uv sync
cp .env.example .env
# Add your API keys to .env
```

## Run

```bash
python -m codedueprocess.main
```

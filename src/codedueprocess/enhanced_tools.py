"""Enhanced detective tools with AST parsing, Git progression analysis, and Vision support."""

from __future__ import annotations

import ast
import base64
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool


def analyze_code_structure(repo_path: str, file_path: str) -> dict[str, Any]:
    """Parse Python file using AST for structural pattern analysis.

    Extracts:
    - Class definitions with inheritance chains
    - Function definitions with call patterns
    - Import statements
    - Docstring presence
    - Cyclomatic complexity indicators
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        content = full_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except SyntaxError as e:
        return {"error": f"Syntax error in {file_path}: {e}"}
    except Exception as e:
        return {"error": f"Failed to parse {file_path}: {e}"}

    classes = []
    functions = []
    imports = []
    docstring_count = 0
    total_nodes = 0

    for node in ast.walk(tree):
        total_nodes += 1

        if isinstance(node, ast.ClassDef):
            bases = [
                base.id if isinstance(base, ast.Name) else str(base)
                for base in node.bases
            ]
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            classes.append(
                {
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "line": node.lineno,
                    "has_docstring": ast.get_docstring(node) is not None,
                }
            )
            if ast.get_docstring(node):
                docstring_count += 1

        elif isinstance(node, ast.FunctionDef):
            # Count branches for complexity
            branches = len(
                [
                    n
                    for n in ast.walk(node)
                    if isinstance(
                        n,
                        (
                            ast.If,
                            ast.For,
                            ast.While,
                            ast.With,
                            ast.Try,
                            ast.ExceptHandler,
                        ),
                    )
                ]
            )
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "arguments": len(node.args.args) + len(node.args.kwonlyargs),
                    "branches": branches,
                    "has_docstring": ast.get_docstring(node) is not None,
                    "is_method": False,  # Will be determined by context
                }
            )
            if ast.get_docstring(node):
                docstring_count += 1

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            else:
                module = node.module or ""
                imports.extend([f"{module}.{alias.name}" for alias in node.names])

    # Mark methods
    class_names = {c["name"] for c in classes}
    for func in functions:
        # Simple heuristic: if function is inside a class, it's a method
        pass

    return {
        "file_path": file_path,
        "total_lines": len(content.splitlines()),
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "docstring_coverage": docstring_count / max(len(classes) + len(functions), 1),
        "ast_node_count": total_nodes,
        "structural_patterns": {
            "has_classes": len(classes) > 0,
            "has_functions": len(functions) > 0,
            "uses_inheritance": any(c["bases"] for c in classes),
            "complex_functions": [f for f in functions if f["branches"] > 3],
        },
    }


def analyze_git_progression(repo_path: str) -> dict[str, Any]:
    """Extract git history with progression patterns for forensic analysis.

    Captures:
    - Commit frequency patterns
    - Author contribution distribution
    - File change patterns over time
    - Branch structure
    """
    try:
        # Verify git repo
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {"error": "Not a git repository", "progression_patterns": {}}

        # Get detailed commit log with stats
        cmd = [
            "git",
            "log",
            "--all",
            "--pretty=format:%H|%ad|%an|%ae|%s",
            "--date=short",
            "--numstat",
        ]
        log_result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse commits
        commits = []
        current_commit = None
        for line in log_result.stdout.split("\n"):
            if "|" in line:
                parts = line.split("|")
                current_commit = {
                    "hash": parts[0],
                    "date": parts[1],
                    "author": parts[2],
                    "email": parts[3],
                    "message": parts[4],
                    "files_changed": 0,
                    "insertions": 0,
                    "deletions": 0,
                }
                commits.append(current_commit)
            elif line.strip() and current_commit:
                # Parse numstat line: insertions deletions filename
                stats = line.split("\t")
                if len(stats) >= 2:
                    try:
                        ins = int(stats[0]) if stats[0] != "-" else 0
                        dels = int(stats[1]) if stats[1] != "-" else 0
                        current_commit["insertions"] += ins
                        current_commit["deletions"] += dels
                        current_commit["files_changed"] += 1
                    except ValueError:
                        pass

        # Analyze patterns
        author_commits = {}
        for commit in commits:
            author = commit["author"]
            author_commits[author] = author_commits.get(author, 0) + 1

        dates = [c["date"] for c in commits]
        unique_dates = sorted(set(dates))

        # Get branch info
        branch_result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        branches = [
            b.strip().strip("* ") for b in branch_result.stdout.split("\n") if b.strip()
        ]

        return {
            "total_commits": len(commits),
            "unique_authors": len(author_commits),
            "author_distribution": author_commits,
            "commit_dates": unique_dates[:10],  # Last 10 unique dates
            "total_branches": len(branches),
            "branch_names": branches[:10],  # First 10 branches
            "progression_patterns": {
                "active_development": len(unique_dates) > 5,
                "multi_author": len(author_commits) > 1,
                "branching_strategy": len(branches) > 2,
                "recent_activity": len(
                    [d for d in unique_dates if "2025" in d or "2026" in d]
                )
                > 0,
            },
            "largest_commit": max(
                commits, key=lambda x: x["insertions"] + x["deletions"]
            )
            if commits
            else None,
            "recent_commits": commits[:5],
        }

    except subprocess.CalledProcessError as e:
        return {"error": f"Git command failed: {e}", "progression_patterns": {}}
    except Exception as e:
        return {"error": f"Git analysis error: {e}", "progression_patterns": {}}


def encode_image_for_vision(image_path: str) -> str | None:
    """Encode image file to base64 for multimodal LLM analysis."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception:
        return None


def get_enhanced_audit_tools(repo_path: str) -> list[BaseTool]:
    """Return enhanced tools with AST, git progression, and vision support."""

    @tool("analyze_ast_structure")
    def analyze_ast_structure(file_path: str) -> str:
        """Analyze Python file structure using AST parsing for class/function patterns."""
        result = analyze_code_structure(repo_path, file_path)
        if "error" in result:
            return f"AST Analysis Error: {result['error']}"

        lines = [
            f"AST Analysis for {result['file_path']}:",
            f"- Total lines: {result['total_lines']}",
            f"- Classes found: {len(result['classes'])}",
            f"- Functions found: {len(result['functions'])}",
            f"- Docstring coverage: {result['docstring_coverage']:.1%}",
            f"- AST node count: {result['ast_node_count']}",
            "",
            "Classes:",
        ]
        for cls in result["classes"]:
            lines.append(
                f"  - {cls['name']} (line {cls['line']}) extends {cls['bases']}"
            )
            lines.append(
                f"    Methods: {', '.join(cls['methods'][:5])}{'...' if len(cls['methods']) > 5 else ''}"
            )

        lines.extend(["", "Complex Functions (>3 branches):"])
        for func in result["structural_patterns"]["complex_functions"][:5]:
            lines.append(
                f"  - {func['name']} (line {func['line']}, {func['branches']} branches)"
            )

        return "\n".join(lines)

    @tool("analyze_git_progression")
    def analyze_git_progression_tool(limit: int = 20) -> str:
        """Analyze git commit progression patterns, author distribution, and development activity."""
        result = analyze_git_progression(repo_path)
        if "error" in result:
            return f"Git Analysis Error: {result['error']}"

        lines = [
            "Git Progression Analysis:",
            f"- Total commits: {result['total_commits']}",
            f"- Unique authors: {result['unique_authors']}",
            f"- Total branches: {result['total_branches']}",
            "",
            "Author Distribution:",
        ]
        for author, count in sorted(
            result["author_distribution"].items(), key=lambda x: -x[1]
        )[:5]:
            lines.append(f"  - {author}: {count} commits")

        lines.extend(["", "Progression Patterns:"])
        for pattern, value in result["progression_patterns"].items():
            lines.append(f"  - {pattern}: {'Yes' if value else 'No'}")

        if result["recent_commits"]:
            lines.extend(["", "Recent Commits:"])
            for commit in result["recent_commits"][:3]:
                lines.append(
                    f"  - {commit['hash'][:8]} | {commit['date']} | {commit['author']}"
                )
                lines.append(f"    {commit['message'][:60]}")
                lines.append(
                    f"    Files: +{commit['insertions']}/-{commit['deletions']}"
                )

        return "\n".join(lines)

    @tool("inspect_image_artifact")
    def inspect_image_artifact(image_path: str) -> str:
        """Inspect image file for visual artifacts (diagrams, screenshots, charts).

        Returns base64 encoded image for multimodal LLM analysis.
        """
        full_path = Path(repo_path) / image_path
        if not full_path.exists():
            return f"Image not found: {image_path}"

        # Check if it's an image
        ext = full_path.suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
            return f"File is not a supported image: {ext}"

        encoded = encode_image_for_vision(str(full_path))
        if not encoded:
            return f"Failed to encode image: {image_path}"

        return (
            f"Image encoded successfully: {image_path}\n"
            f"Base64 length: {len(encoded)} characters\n"
            f"Format: {ext}\n"
            f"Use this for multimodal analysis with the VisionInspector."
        )

    @tool("extract_call_patterns")
    def extract_call_patterns(file_path: str) -> str:
        """Extract function call patterns and fan-out wiring from Python files."""
        full_path = Path(repo_path) / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"

        try:
            content = full_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            return f"Parse error: {e}"

        calls = []
        definitions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_calls = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            func_calls.append(child.func.id)
                        elif isinstance(child.func, ast.Attribute):
                            func_calls.append(child.func.attr)

                definitions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "calls": list(set(func_calls)),
                        "call_count": len(func_calls),
                    }
                )

        lines = [
            f"Call Pattern Analysis for {file_path}:",
            f"- Functions analyzed: {len(definitions)}",
            "",
            "Function Call Graph:",
        ]

        for func in definitions:
            fan_out = len(func["calls"])
            lines.append(
                f"  {func['name']} (line {func['line']}) -> {fan_out} unique calls:"
            )
            for call in func["calls"][:5]:
                lines.append(f"    - {call}")
            if len(func["calls"]) > 5:
                lines.append(f"    ... and {len(func['calls']) - 5} more")

        # Calculate fan-out metrics
        avg_fanout = sum(len(f["calls"]) for f in definitions) / max(
            len(definitions), 1
        )
        high_fanout = [f for f in definitions if len(f["calls"]) > 5]

        lines.extend(
            [
                "",
                f"Average fan-out per function: {avg_fanout:.1f}",
                f"High fan-out functions (>5 calls): {len(high_fanout)}",
            ]
        )

        return "\n".join(lines)

    return [
        analyze_ast_structure,
        analyze_git_progression_tool,
        inspect_image_artifact,
        extract_call_patterns,
    ]

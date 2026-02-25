import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import git
from tree_sitter import Language, Parser

from .cache import disk_cache


@dataclass
class CodeLocation:
    """Represents a location in source code."""

    file_path: str
    start_line: int
    end_line: int
    class_name: str | None = None
    function_name: str | None = None


@dataclass
class FunctionInfo:
    """Information about a function or method."""

    name: str
    line_start: int
    line_end: int
    complexity: int
    parameters: list[str]
    return_type: str | None
    docstring: str | None = None


@dataclass
class ClassInfo:
    """Information about a class."""

    name: str
    line_start: int
    line_end: int
    methods: list[FunctionInfo]
    docstring: str | None = None


@disk_cache
def clone_repo_sandbox(repo_url: str, commit_sha: str | None = None) -> str:
    """Clone a repository into a sandboxed temporary directory.

    Args:
        repo_url: URL to the git repository
        commit_sha: Optional specific commit to checkout

    Returns:
        Path to the cloned repository
    """
    # Create a sandbox directory with hash-based naming
    repo_hash = hashlib.md5(repo_url.encode()).hexdigest()[:8]
    sandbox_base = Path(tempfile.gettempdir()) / "codedueprocess_sandbox"
    sandbox_base.mkdir(exist_ok=True)

    clone_path = sandbox_base / f"repo_{repo_hash}"

    if clone_path.exists():
        shutil.rmtree(clone_path)

    # Clone the repository
    repo = git.Repo.clone_from(repo_url, str(clone_path))

    # If specific commit is requested, checkout that commit
    if commit_sha:
        repo.git.checkout(commit_sha)

    return str(clone_path)


@disk_cache
def parse_repo_ast(repo_path: str) -> tuple[list[ClassInfo], list[FunctionInfo]]:
    """Parse a repository using AST to extract classes and functions.

    Args:
        repo_path: Path to the repository

    Returns:
        Tuple of (classes, standalone_functions)
    """
    classes = []
    standalone_functions = []

    # Build and initialize tree-sitter
    Language.build_library(
        "build/my-languages.so",
        [
            "vendor/tree-sitter-python",
            "vendor/tree-sitter-go",
        ],
    )

    PY_LANGUAGE = Language("build/my-languages.so", "python")
    GO_LANGUAGE = Language("build/my-languages.so", "go")

    parser = Parser()
    parser.set_language(PY_LANGUAGE)

    # Walk through all Python files
    for py_file in Path(repo_path).rglob("*.py"):
        if "test" in py_file.name or py_file.name.startswith("."):
            continue

        try:
            content = py_file.read_text()
            tree = parser.parse(bytes(content, "utf8"))

            # Extract functions and classes
            functions_in_file = extract_functions(tree, str(py_file))
            standalone_functions.extend(functions_in_file)

            classes_in_file = extract_classes(tree, str(py_file))
            classes.extend(classes_in_file)

        except Exception:
            continue

    # Walk through all Go files
    for go_file in Path(repo_path).rglob("*.go"):
        if go_file.name.endswith("_test.go") or "vendor" in str(go_file):
            continue

        try:
            content = go_file.read_text()
            tree = parser.parse(bytes(content, "utf8"))

            functions_in_file = extract_go_functions(tree, str(go_file))
            standalone_functions.extend(functions_in_file)

            classes_in_file = extract_go_types(tree, str(go_file))
            classes.extend(classes_in_file)

        except Exception:
            continue

    return classes, standalone_functions


def extract_functions(tree, file_path: str) -> list[FunctionInfo]:
    """Extract function definitions from Python AST."""
    functions = []

    def traverse(node, depth=0):
        if node.type == "function_definition":
            name_node = None
            params_node = None
            docstring = None
            line_start = node.start_point[0]
            line_end = node.end_point[0]

            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                elif child.type == "parameters":
                    params_node = child
                elif child.type == "string":
                    docstring = child.text.decode("utf8")

            name = name_node.text.decode("utf8") if name_node else "unknown"

            # Extract parameters
            params = []
            if params_node:
                for param_child in params_node.children:
                    if param_child.type == "identifier":
                        params.append(param_child.text.decode("utf8"))

            # Calculate cyclomatic complexity
            complexity = calculate_cyclomatic_complexity(node)

            functions.append(
                FunctionInfo(
                    name=name,
                    line_start=line_start,
                    line_end=line_end,
                    complexity=complexity,
                    parameters=params,
                    return_type=None,
                    docstring=docstring,
                )
            )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return functions


def extract_classes(tree, file_path: str) -> list[ClassInfo]:
    """Extract class definitions from Python AST."""
    classes = []

    def traverse(node, depth=0):
        if node.type == "class_definition":
            name = None
            methods = []
            line_start = node.start_point[0]
            line_end = node.end_point[0]

            for child in node.children:
                if child.type == "identifier":
                    name = child.text.decode("utf8")
                elif child.type == "block":
                    # Extract methods within class
                    for block_child in child.children:
                        if block_child.type == "function_definition":
                            method_info = extract_functions(block_child, file_path)[0]
                            methods.append(method_info)

            if name:
                classes.append(
                    ClassInfo(
                        name=name,
                        line_start=line_start,
                        line_end=line_end,
                        methods=methods,
                    )
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return classes


def extract_go_functions(tree, file_path: str) -> list[FunctionInfo]:
    """Extract function definitions from Go AST."""
    functions = []

    def traverse(node, depth=0):
        if node.type == "function_declaration":
            name = None
            line_start = node.start_point[0]
            line_end = node.end_point[0]

            for child in node.children:
                if child.type == "field_identifier":
                    name = child.text.decode("utf8")
                    break

            if name:
                complexity = calculate_cyclomatic_complexity(node)
                functions.append(
                    FunctionInfo(
                        name=name,
                        line_start=line_start,
                        line_end=line_end,
                        complexity=complexity,
                        parameters=[],
                        return_type=None,
                    )
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return functions


def extract_go_types(tree, file_path: str) -> list[ClassInfo]:
    """Extract type definitions from Go AST (treating structs as classes)."""
    types = []

    def traverse(node, depth=0):
        if node.type == "type_declaration":
            name = None
            line_start = node.start_point[0]
            line_end = node.end_point[0]

            for child in node.children:
                if child.type == "type_identifier":
                    name = child.text.decode("utf8")
                    break

            if name and name[0].isupper():
                types.append(
                    ClassInfo(
                        name=name, line_start=line_start, line_end=line_end, methods=[]
                    )
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return types


def calculate_cyclomatic_complexity(ast_node) -> int:
    """Calculate cyclomatic complexity of a function/method.
    Complexity = P + 1 where P is number of decision points.

    Args:
        ast_node: AST node for the function

    Returns:
        Calculated cyclomatic complexity
    """
    complexity = 1  # Base complexity

    def count_decisions(node):
        nonlocal complexity

        # Decision points that increase complexity
        if node.type in [
            "if_statement",
            "for_statement",
            "while_statement",
            "conditional_expression",
            "try_statement",
            "case",
            "if",
            "range",
            "select",
        ]:
            complexity += 1

        # Count elif/else branches
        elif node.type == "elif" or node.type == "else":
            complexity += 1

        # Logical operators also increase complexity
        elif node.type in ["and", "or"]:
            complexity += 1

        for child in node.children:
            count_decisions(child)

    count_decisions(ast_node)
    return complexity


def find_violations_by_pattern(repo_path: str, pattern: str) -> list[CodeLocation]:
    """Search for code patterns that might indicate violations.

    Args:
        repo_path: Path to the repository
        pattern: Pattern to search for (regex or simple string)

    Returns:
        List of code locations matching the pattern
    """
    violations = []

    for file_path in Path(repo_path).rglob("*"):
        if not file_path.is_file():
            continue

        # Skip common non-source files
        if any(
            skip in str(file_path)
            for skip in [".git", "__pycache__", ".venv", "node_modules"]
        ):
            continue

        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if pattern in line or (
                    hasattr(line, "find") and line.lower().find(pattern.lower()) >= 0
                ):
                    violations.append(
                        CodeLocation(
                            file_path=str(file_path), start_line=i + 1, end_line=i + 1
                        )
                    )
        except:
            continue

    return violations


@disk_cache
def get_complex_methods(repo_path: str, threshold: int = 10) -> list[FunctionInfo]:
    """Identify methods/functions with high cyclomatic complexity.

    Args:
        repo_path: Path to the repository
        threshold: Complexity threshold (default: 10)

    Returns:
        List of functions exceeding the threshold
    """
    classes, functions = parse_repo_ast(repo_path)

    complex_functions = []

    # Check standalone functions
    for func in functions:
        if func.complexity >= threshold:
            complex_functions.append(func)

    # Check class methods
    for cls in classes:
        for method in cls.methods:
            if method.complexity >= threshold:
                complex_functions.append(method)

    return complex_functions

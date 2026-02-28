"""Tool setup helpers for repository auditing agents."""

import subprocess

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import BaseTool, tool


def _read_git_history(repo_path: str, limit: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "Not a git repository"
            return f"Error running git rev-parse in {repo_path}: {stderr}"

        cmd = [
            "git",
            "log",
            "-n",
            str(limit),
            "--pretty=format:%h | %ad | %an | %s",
            "--date=short",
        ]
        log_result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return f"Recent {limit} commits:\n" + log_result.stdout
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip() if e.stderr else ""
        details = f" ({stderr})" if stderr else ""
        return f"Error reading git history in {repo_path}: {e}{details}"
    except Exception as e:
        return f"Unexpected git history error in {repo_path}: {e}"


def get_audit_tools(repo_path: str) -> list[BaseTool]:
    """Return tools configured for audit agents.

    Includes safe file system operations and git history inspection.
    """
    # Initialize file management toolkit for the specific root directory
    # strict=True ensures agents can't read files outside this directory
    toolkit = FileManagementToolkit(
        root_dir=repo_path,
        selected_tools=["read_file", "list_directory", "file_search"],
    )

    tools = toolkit.get_tools()

    @tool("get_git_history")
    def get_git_history(limit: int = 10) -> str:
        """Return recent git commit history for the audited repository."""
        return _read_git_history(repo_path=repo_path, limit=limit)

    tools.append(get_git_history)

    return tools


def get_doc_tools(repo_path: str) -> list[BaseTool]:
    """Return tools for document analysis including PDF ingestion and RAG."""
    try:
        from codedueprocess.doc_tools import DocumentTools

        doc_tools = DocumentTools()

        @tool("ingest_pdf")
        def ingest_pdf(pdf_path: str) -> str:
            """Ingest a PDF file for analysis. Returns number of chunks indexed."""
            try:
                chunks = doc_tools.ingest_pdf(pdf_path)
                doc_tools.index_chunks(chunks)
                return f"Successfully ingested {len(chunks)} chunks from {pdf_path}"
            except Exception as e:
                return f"Error ingesting PDF: {str(e)}"

        @tool("semantic_search")
        def semantic_search(query: str) -> str:
            """Search ingested documents for relevant content."""
            try:
                results = doc_tools.semantic_search(query)
                if not results:
                    return "No relevant information found."

                formatted = []
                for chunk, score in results:
                    formatted.append(f"[Score: {score:.2f}] {chunk.content}...")
                return "\n\n".join(formatted)
            except Exception as e:
                return f"Error searching documents: {str(e)}"

        return [ingest_pdf, semantic_search]
    except ImportError:
        return []

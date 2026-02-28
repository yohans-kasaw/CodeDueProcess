"""Tool setup helpers for repository auditing agents."""

import subprocess

from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import BaseTool, tool


@tool
def get_git_history(limit: int = 10) -> str:
    """Return recent git commit history for the current repository.

    Useful for understanding the project's evolution and contributor activity.
    """
    try:
        # Check for .git directory first to avoid errors in non-git dirs
        # We assume the current working directory is the repo root for this tool
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True
        )
        if result.returncode != 0:
            return "Error: Not a git repository."

        # Get formatted log: Hash | Date | Author | Message
        cmd = [
            "git",
            "log",
            f"-n {limit}",
            "--pretty=format:%h | %ad | %an | %s",
            "--date=short",
        ]
        log_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Recent {limit} commits:\n" + log_result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error reading git history: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


def get_audit_tools(root_dir: str) -> list[BaseTool]:
    """Return tools configured for audit agents.

    Includes safe file system operations and git history inspection.
    """
    # Initialize file management toolkit for the specific root directory
    # strict=True ensures agents can't read files outside this directory
    toolkit = FileManagementToolkit(
        root_dir=root_dir,
        selected_tools=["read_file", "list_directory", "file_search"],
    )

    tools = toolkit.get_tools()
    tools.append(get_git_history)

    return tools

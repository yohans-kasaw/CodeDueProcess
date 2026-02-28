"""CodeDueProcess entry point.

Orchestrates the audit process:
1. Clones the repo
2. Loads the rubric
3. Runs the agent graph
4. Outputs the report
"""

import argparse
import os
import subprocess
import sys
import tempfile
from typing import cast

import yaml  # type: ignore[import-untyped]
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from codedueprocess.graph import AuditGraphModels, build_audit_graph
from codedueprocess.schemas.models import Rubric

# Load environment variables
load_dotenv()


def safe_git_clone(url: str, dest_path: str) -> None:
    """Clones a git repository safely to a destination."""
    print(f"Cloning {url} to {dest_path}...")
    try:
        subprocess.run(
            ["git", "clone", url, "."], cwd=dest_path, check=True, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        sys.exit(1)


def find_report_path(repo_path: str, provided_path: str | None) -> str:
    """Resolves the audit report path."""
    if provided_path:
        full_path = os.path.join(repo_path, provided_path)
        if os.path.exists(full_path):
            return full_path
        # Try absolute path just in case
        if os.path.exists(provided_path):
            return provided_path
        print(f"Error: Provided report path '{provided_path}' not found.")
        sys.exit(1)

    # Heuristic search for report
    # Look for files with 'report' or 'audit' in the name, markdown format
    candidates = []
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.lower().endswith(".md") and (
                "report" in file.lower() or "audit" in file.lower()
            ):
                candidates.append(os.path.join(root, file))

    if not candidates:
        print("Error: No report document found. Please provide --report-path.")
        sys.exit(1)

    # Pick the best candidate (e.g., shortest path = closest to root)
    candidates.sort(key=lambda x: len(x))
    print(f"Auto-detected report document: {candidates[0]}")
    return candidates[0]


def get_llm(provider: str, model_name: str) -> BaseChatModel:
    """Factory for LLM initialization."""
    if provider == "openai":
        # Check for OpenRouter configuration
        base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not found in environment.")
            sys.exit(1)

        return cast(
            BaseChatModel,
            ChatOpenAI(
                model=model_name or "openai/gpt-4o",
                api_key=SecretStr(api_key),
                base_url=base_url,
                temperature=0,
            ),
        )
    elif provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not found in environment.")
            sys.exit(1)

        return cast(
            BaseChatModel,
            ChatGoogleGenerativeAI(
                model=model_name or "gemini-1.5-pro",
                google_api_key=api_key,
                temperature=0,
            ),
        )
    else:
        print(f"Error: Unsupported provider '{provider}'")
        sys.exit(1)


def main() -> None:
    """Parse CLI arguments and run the end-to-end audit workflow."""
    parser = argparse.ArgumentParser(
        description="CodeDueProcess: AI-powered Code Audit System"
    )
    parser.add_argument("repo_url", help="URL of the GitHub repository to audit")
    parser.add_argument(
        "--report-path", help="Path to the audit report markdown file (optional)"
    )
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "gemini"],
        help="LLM provider",
    )
    parser.add_argument(
        "--model", help="Specific model name (e.g., openai/gpt-4o, gemini-1.5-pro)"
    )
    parser.add_argument(
        "--rubric", default="docs/week_2_rubric.yaml", help="Path to rubric YAML"
    )

    args = parser.parse_args()

    # 1. Initialize LLM
    print(f"Initializing {args.provider} LLM ({args.model or 'default'})...")
    llm = get_llm(args.provider, args.model)

    # 2. Load Rubric
    print(f"Loading rubric from {args.rubric}...")
    try:
        with open(args.rubric) as f:
            rubric_data = yaml.safe_load(f)
            # The YAML structure might be nested or flat, we need to adapt to Schema
            # Assuming the YAML *is* the Rubric model structure
            rubric = Rubric.model_validate(rubric_data)
    except FileNotFoundError:
        print(f"Error: Rubric file '{args.rubric}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing rubric: {e}")
        # Fallback/Debug: just print structure
        # sys.exit(1)
        # For now, let's assume we proceed or fail gracefully.
        # Ideally we should strict fail, but if the YAML format differs from
        # the Pydantic model, this provides a clearer failure reason.
        print(
            "Warning: Rubric validation failed. "
            "Proceeding with raw data structure if possible "
            "(Graph expects list[Dimension])."
        )
        # Creating a dummy rubric object or crashing?
        # Let's crash for safety as the graph needs rubric dimensions
        raise e

    # 3. Execution Context
    with tempfile.TemporaryDirectory() as temp_dir:
        # Clone Repo
        safe_git_clone(args.repo_url, temp_dir)

        # Resolve Report
        report_file = find_report_path(temp_dir, args.report_path)

        # 4. Build Graph
        print("Building agent graph...")
        # Use single LLM for all roles for simplicity, or split if needed
        model_config = AuditGraphModels.from_single(llm)
        graph = build_audit_graph(model_config)

        # 5. Run Audit
        print("Starting audit execution...")
        initial_state = {
            "repo_url": args.repo_url,
            "repo_path": temp_dir,
            "doc_path": report_file,
            "rubric_dimensions": rubric.dimensions,
            "evidences": {},
            "opinions": [],
        }

        # Invoke graph
        result = graph.invoke(initial_state)

        # 6. Output Report
        print("\n" + "=" * 50)
        print("AUDIT COMPLETE")
        print("=" * 50)

        final_report = result.get("final_report")
        if final_report:
            print(final_report.model_dump_json(indent=2))
        else:
            print("Error: No final report generated.")


if __name__ == "__main__":
    main()

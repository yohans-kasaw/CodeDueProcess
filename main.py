"""CodeDueProcess entry point with interactive prompts and rich tracing."""

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

from codedueprocess.cli.prompts import prompt_for_run_inputs
from codedueprocess.graph import AuditGraphModels, build_audit_graph
from codedueprocess.printing.events import AuditLayer
from codedueprocess.printing.tracer import AuditTracer
from codedueprocess.schemas.models import AuditReport, Rubric

# Load environment variables
load_dotenv()


def safe_git_clone(url: str, dest_path: str) -> None:
    """Clones a git repository safely to a destination."""
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
        print("Error: No report document found. Please provide report path.")
        sys.exit(1)

    # Pick the best candidate (e.g., shortest path = closest to root)
    candidates.sort(key=lambda x: len(x))
    return candidates[0]


def get_llm(provider: str, model_name: str | None) -> BaseChatModel:
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
                model=model_name or "gemini-2.5-flash",
                google_api_key=api_key,
                temperature=0,
            ),
        )
    else:
        print(f"Error: Unsupported provider '{provider}'")
        sys.exit(1)


def main() -> None:
    """Prompt user and run the end-to-end audit workflow."""
    tracer = AuditTracer()
    user_inputs = prompt_for_run_inputs(default_rubric_path="docs/sample_rubric.yaml")
    tracer.audit_started(user_inputs.repo_url)

    # 1. Initialize LLM
    tracer.layer_started(AuditLayer.INGESTION)
    tracer.info(AuditLayer.INGESTION, "LLM", "Initializing model provider...")
    llm = get_llm(user_inputs.provider, user_inputs.model)
    tracer.success(AuditLayer.INGESTION, "LLM", "Model ready")

    # 2. Load Rubric
    tracer.info(AuditLayer.INGESTION, "Rubric", f"Loading {user_inputs.rubric_path}")
    try:
        with open(user_inputs.rubric_path) as f:
            rubric_data = yaml.safe_load(f)
            rubric = Rubric.model_validate(rubric_data)
    except FileNotFoundError:
        tracer.failure(
            AuditLayer.INGESTION,
            "Rubric",
            f"Rubric file '{user_inputs.rubric_path}' not found",
        )
        sys.exit(1)
    except Exception as e:
        tracer.failure(AuditLayer.INGESTION, "Rubric", f"Error parsing rubric: {e}")
        raise e
    tracer.success(AuditLayer.INGESTION, "Rubric", "Rubric loaded")

    # 3. Execution Context
    with tempfile.TemporaryDirectory() as temp_dir:
        # Clone Repo
        tracer.info(AuditLayer.INGESTION, "Cloner", "Cloning repository...")
        with tracer.live_status(
            AuditLayer.INGESTION, "Cloner", "Cloning repository..."
        ):
            safe_git_clone(user_inputs.repo_url, temp_dir)
        file_count = sum(len(files) for _, _, files in os.walk(temp_dir))
        tracer.success(
            AuditLayer.INGESTION,
            "Cloner",
            f"Repository cloned successfully ({file_count} files)",
        )

        # Resolve Report
        tracer.info(AuditLayer.INGESTION, "ReportResolver", "Resolving report file...")
        report_file = find_report_path(temp_dir, user_inputs.report_path)
        tracer.success(AuditLayer.INGESTION, "ReportResolver", f"Using {report_file}")

        # 4. Build Graph
        tracer.info(AuditLayer.INGESTION, "Graph", "Building agent graph...")
        model_config = AuditGraphModels.from_single(llm)
        graph = build_audit_graph(model_config, tracer=tracer)
        tracer.success(AuditLayer.INGESTION, "Graph", "Graph ready")

        # 5. Run Audit
        tracer.info(AuditLayer.JUDGES, "Panel Deliberation", "Active")
        initial_state = {
            "repo_url": user_inputs.repo_url,
            "repo_path": temp_dir,
            "doc_path": report_file,
            "rubric_dimensions": rubric.dimensions,
            "evidences": {},
            "opinions": [],
        }

        # Invoke graph
        with tracer.live_status(
            AuditLayer.DETECTIVES, "AuditGraph", "Executing layers"
        ):
            result = graph.invoke(initial_state)

        # 6. Output Report
        final_report = result.get("final_report")
        if final_report:
            output_path = write_audit_report(final_report)
            tracer.chief_summary(final_report, output_path)
        else:
            tracer.failure(
                AuditLayer.CHIEF, "Chief Justice", "No final report generated"
            )


def write_audit_report(final_report: AuditReport) -> str:
    """Persist the final audit report to output/audit_report.md."""
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "audit_report.md")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("# Audit Report\n\n")
        file.write("```json\n")
        file.write(final_report.model_dump_json(indent=2))
        file.write("\n```\n")
    return output_path


if __name__ == "__main__":
    main()

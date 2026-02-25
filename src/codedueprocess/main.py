import asyncio
import logging

from .agent import build_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_audit(repo_url: str, pdf_path: str):
    graph = build_graph()

    initial_state = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "rubric_dimensions": [
            {"id": "accuracy", "name": "Forensic Accuracy"},
            {"id": "nuance", "name": "Judicial Nuance"},
            {"id": "architecture", "name": "LangGraph Architecture"},
        ],
        "evidences": {},
        "opinions": [],
    }

    result = await graph.ainvoke(initial_state)
    report = result["final_report"]

    print(f"Audit Report for {report.repo_url}")
    print(f"Overall Score: {report.overall_score}/5")
    print("\nCriteria Results:")
    for crit in report.criteria:
        print(f"- {crit.dimension_name}: {crit.final_score}/5")
        if crit.dissent_summary:
            print(f"  DISSENT: {crit.dissent_summary}")


if __name__ == "__main__":
    asyncio.run(run_audit("https://github.com/user/repo", "reports/spec.pdf"))

"""Case loading, grading, aggregation, and report generation."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .graders import grade_case
from .judge import judge_case
from .models import EvalCase, Grade
from .production import load_production_contract


ROOT = Path(__file__).resolve().parent


def load_cases(case_dir: Path | None = None) -> list[EvalCase]:
    directory = case_dir or ROOT / "cases"
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError(f"{path} must contain a JSON array")
        for value in values:
            case = EvalCase.from_dict(value)
            if case.id in seen:
                raise ValueError(f"duplicate case id {case.id!r}")
            seen.add(case.id)
            cases.append(case)
    if not cases:
        raise ValueError(f"no evaluation cases found in {directory}")
    return cases


def run_cases(cases: list[EvalCase], *, use_judge: bool = False) -> dict[str, Any]:
    contract = load_production_contract()
    grades: list[Grade] = []
    judgments: list[dict[str, Any]] = []
    for case in cases:
        grade = grade_case(case)
        grades.append(grade)
        if use_judge and case.judge_criteria:
            judgments.append(judge_case(case, grade).to_dict())

    family_values: dict[str, list[bool]] = defaultdict(list)
    family_thresholds: dict[str, float] = {}
    family_threshold_enforced: dict[str, bool] = defaultdict(bool)
    for case, grade in zip(cases, grades):
        family_values[grade.family].append(grade.passed)
        family_thresholds[grade.family] = case.family_pass_threshold
        family_threshold_enforced[grade.family] = (
            family_threshold_enforced[grade.family] or not case.blocking
        )
    families = {
        name: {
            "passed": sum(values),
            "total": len(values),
            "pass_rate": sum(values) / len(values),
            "threshold": family_thresholds[name],
            "threshold_pass": sum(values) / len(values) >= family_thresholds[name],
        }
        for name, values in sorted(family_values.items())
    }
    blocking_failures = [grade.case_id for grade in grades if grade.blocking and not grade.passed]
    family_threshold_failures = [
        name for name, result in families.items()
        if family_threshold_enforced[name] and not result["threshold_pass"]
    ]
    judge_below_threshold = [
        judgment["case_id"] for judgment in judgments if not judgment["threshold_pass"]
    ]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline_replay_with_judge" if use_judge else "offline_replay",
        "production_contract": {
            "tool_names": [tool["name"] for tool in contract.tools],
            "prompt_source": "voice-agent/voice_prompt.py",
            "tool_source": "voice-agent/tool_definitions.py",
        },
        "summary": {
            "passed": sum(grade.passed for grade in grades),
            "total": len(grades),
            "blocking_failures": blocking_failures,
            "family_threshold_failures": family_threshold_failures,
            "hard_pass": not blocking_failures and not family_threshold_failures,
            "judge_below_threshold": judge_below_threshold,
            "requires_human_review": bool(judge_below_threshold),
        },
        "families": families,
        "grades": [grade.to_dict() for grade in grades],
        "judgments": judgments,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Evaluation Run",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Generated: `{report['generated_at']}`",
        f"- Result: **{'PASS' if summary['hard_pass'] else 'FAIL'}**",
        f"- Cases: {summary['passed']}/{summary['total']} passed",
        f"- Blocking failures: {', '.join(summary['blocking_failures']) or 'none'}",
        f"- Family threshold failures: {', '.join(summary.get('family_threshold_failures', [])) or 'none'}",
        f"- Judge results below threshold: {', '.join(summary.get('judge_below_threshold', [])) or 'none'}",
        "",
        "| Case | Family | Score | Result |",
        "|---|---|---:|---|",
    ]
    for grade in report["grades"]:
        lines.append(
            f"| `{grade['case_id']}` | {grade['family']} | {grade['score']:.0%} | "
            f"{'PASS' if grade['passed'] else 'FAIL'} |"
        )
    lines.extend(["", "## Diagnostics", ""])
    for grade in report["grades"]:
        lines.append(f"### `{grade['case_id']}`")
        lines.append("")
        for check in grade["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            lines.append(f"- **{mark} — {check['name']}:** {check['detail']}")
        for name, value in grade["metrics"].items():
            lines.append(f"- **Metric — {name}:** {value}")
        for reason in grade["review_reasons"]:
            lines.append(f"- **Human/LLM review:** {reason}")
        lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(render_markdown(report) + "\n", encoding="utf-8")

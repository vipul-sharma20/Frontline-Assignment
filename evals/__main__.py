"""Command-line entry point for the evaluation suite."""

from __future__ import annotations

import argparse
from pathlib import Path

from .runner import ROOT, load_cases, run_cases, write_report
from .simulate import simulate_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Frontline voice-agent evaluations")
    parser.add_argument("--case", action="append", dest="case_ids", help="Run one case ID; repeatable")
    parser.add_argument("--family", action="append", dest="families", help="Run one family; repeatable")
    parser.add_argument("--judge", action="store_true", help="Run optional LLM judge for configured criteria")
    parser.add_argument("--model", action="store_true", help="Generate traces with the production prompt and a model")
    parser.add_argument("--repetitions", type=int, default=1, help="Model trials per case")
    parser.add_argument("--cases", type=Path, default=ROOT / "cases", help="Directory containing case JSON")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "latest", help="Report directory")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.case_ids:
        wanted = set(args.case_ids)
        cases = [case for case in cases if case.id in wanted]
        missing = wanted - {case.id for case in cases}
        if missing:
            parser.error(f"unknown case IDs: {', '.join(sorted(missing))}")
    if args.families:
        wanted_families = set(args.families)
        cases = [case for case in cases if case.family in wanted_families]
    if not cases:
        parser.error("filters selected no cases")
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    if args.model:
        generated = []
        for _ in range(args.repetitions):
            generated.extend(simulate_case(case) for case in cases)
        cases = generated

    report = run_cases(cases, use_judge=args.judge)
    if args.model:
        report["mode"] = "model_simulation_with_judge" if args.judge else "model_simulation"
    write_report(report, args.output)
    summary = report["summary"]
    print(
        f"{'PASS' if summary['hard_pass'] else 'FAIL'}: "
        f"{summary['passed']}/{summary['total']} cases passed; "
        f"reports: {args.output}"
    )
    return 0 if summary["hard_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

# Passing baseline run

## Command

```bash
env -u OPENAI_API_KEY -u EVAL_JUDGE_MODEL \
  python3 -m evals --judge \
  --output evals/examples/runs/baseline-pass
```

## Expected outcome

- Exit status: `0`
- Overall result: `PASS`
- Controlled cases: `12/12` pass
- LLM judge: `skipped_unavailable`
- Tool-call validity: pass
- Transactional database writes: `0`
- Business-service network calls: `0`

This run grades the checked-in controlled traces in `evals/cases/core.json`. It validates grader behavior and report generation; it is not evidence that a live model passed the scenarios.

Use `summary.md` for review, `summary.json` for automation, and `traces.json` to inspect the exact event ledger behind any result.

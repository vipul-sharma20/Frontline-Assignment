# Sample evaluation runs

This directory preserves reproducible examples of the evaluation artifacts produced during development. It contains both a known-good controlled replay and an intentional merge-blocking failure.

## Run index

| Directory | Expected result | Purpose |
|---|---|---|
| `baseline-pass/` | PASS, exit 0 | Shows a complete passing offline report with optional judge unavailable |
| `above-max-failure/` | FAIL, exit 1 | Shows diagnosis of a schema-valid but financially unsafe tool sequence |

Each run directory contains:

- `RUN.md`: command, expected exit status, scope, and interpretation;
- `summary.md`: human-readable report;
- `summary.json`: complete machine-readable report;
- `traces.json`: the exact ordered text/tool ledger graded for every case, keyed by case ID.

These are text-only evaluation artifacts. They contain synthetic fixture data and fake identifiers, not production calls or transactional records. Both sample runs report zero transactional database writes and zero business-service network calls.

Generated timestamps are retained as evidence of the actual runs. Re-running the commands updates timestamps but should preserve the documented outcomes unless the production prompts, schemas, cases, or graders change.

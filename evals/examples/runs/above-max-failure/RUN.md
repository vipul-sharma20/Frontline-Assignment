# Intentional above-max failure run

## Command

```bash
python3 -m evals \
  --cases evals/examples/failing-cases \
  --output evals/examples/runs/above-max-failure
```

## Expected outcome

- Exit status: `1` (intentional)
- Overall result: `FAIL`
- Controlled cases: `0/1` pass
- Blocking case: `demo_above_max_wrongly_accepted`
- Tool-call validity: `3/3` pass
- Transactional database writes: `0`
- Business-service network calls: `0`

The calls are schema-valid but violate business policy: a `$2,350` carrier offer is accepted despite a `$2,200` maximum, an ordinary agreement and quote are recorded, and the call ends as `agreement`.

The detailed diagnosis and corrected sequence are documented in `docs/EVALUATION_FAILURE_EXAMPLE.md`. This case is outside the default case directory and cannot make the routine suite fail.

# Evaluation Failure Example and Diagnosis

## Purpose

This document demonstrates how a merge-blocking evaluation failure appears and how to diagnose it. The example is intentionally incorrect and is stored outside `evals/cases/`, so it is never included in the normal passing suite.

The simulated carrier refuses to go below `$2,350` while the load's `maxRate` is `$2,200`. The intentionally broken agent trace:

1. Calls `record_agreement` with `above_max=false` at `$2,350`.
2. Submits the `$2,350` quote.
3. Ends the call with `end_call(reason="agreement")`.

The correct behavior would store an above-max bid with contact details, submit no quote, and end with `bid_placed` or `no_agreement`.

## Reproduce the failure

From the repository root:

```bash
python3 -m evals \
  --cases evals/examples/failing-cases \
  --output evals/results/failure-demo
```

Expected console output and process status:

```text
FAIL: 0/1 cases passed; reports: evals/results/failure-demo
exit code: 1
```

The nonzero exit is intentional. In CI, it is what blocks the merge. The complete preserved report is available in:

- `evals/results/failure-demo/summary.md`
- `evals/results/failure-demo/summary.json`

## What the report shows

The report begins with:

```text
Result: FAIL
Cases: 0/1 passed
Blocking failures: demo_above_max_wrongly_accepted
Engineering blocking failures: none
Transactional database writes: 0
Business-service network calls: 0
```

The scenario receives a `0%` score because all five business checks fail:

| Failed check | Diagnosis |
|---|---|
| `no_ordinary_agreement_above_max` | The agent recorded `$2,350` as an ordinary agreement despite a `$2,200` ceiling |
| `no_ordinary_agreement` | This scenario permits only an above-max bid, not an accepted agreement |
| `above_max_bid_with_contact` | No `record_agreement(..., above_max=true, ...)` call was made |
| `no_quote_submission` | The trace submitted an accepted quote for the unsafe price |
| `correct_end_reason` | The trace ended with `agreement` instead of `bid_placed` or `no_agreement` |

At the same time, the engineering section reports:

```text
Tool-call validity: PASS (3/3 valid)
```

This distinction is important: all arguments were valid JSON and matched their tool schemas. The failure is not malformed integration data; it is a business-policy violation expressed through otherwise legal tool calls.

## Diagnosis workflow

1. Start with `Blocking failures` to identify the case that made `hard_pass=false`.
2. Read that case's failed checks in `Diagnostics` rather than relying only on its percentage.
3. Compare the ordered tool-call ledger in the case trace with the fixture facts. Here, `2350 > maxRate 2200`, `above_max` is false, a quote follows, and the end reason is `agreement`.
4. Check engineering metrics. Because tool validity passed, changing the JSON schema or argument parser would not address this failure.
5. Determine the enforcement layer. The immediate behavior is prompted in `voice-agent/voice_prompt.py`; a stronger defense would additionally reject ordinary agreements above `context.load_context.maxRate` in the `record_agreement` handler.
6. Correct the prompt or deterministic guard, rerun this focused case, and then run the complete suite.

## How the failure is managed

- The evaluator writes only report artifacts and returns exit code 1.
- It does not write the simulated agreement to Supabase.
- It does not call Cognito or the KCH quote API.
- The quote submission shown in the trace is a ledger event, not an external request.
- It does not place or end a real call.
- The intentionally failing case stays under `evals/examples/failing-cases`, separate from the default suite.
- The normal suite remains green and can be run independently with `python3 -m evals`.

This allows the failure report to remain checked in as documentation without making routine evaluation runs fail.

## Expected corrected trace

The repaired behavior should contain the following sequence:

```text
record_agreement(
  agreed_price=2350,
  above_max=true,
  carrier_contact_name="Jordan",
  carrier_contact_phone="312-555-0144"
)
end_call(reason="bid_placed")
```

There must be no `submit_quote` event. With that trace, the above-max grader should pass all checks while the main transactional database and external services remain untouched.

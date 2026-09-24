# Evaluation Run

- Mode: `offline_replay`
- Generated: `2026-09-24T18:15:55.761945+00:00`
- Result: **FAIL**
- Cases: 0/1 passed
- Blocking failures: demo_above_max_wrongly_accepted
- Family threshold failures: none
- Engineering blocking failures: none
- Judge results below threshold: n/a
- LLM judge: `not_requested`
- Model generation: `not_requested`
- Simulation: `text_only`
- Transactional database writes: 0
- Business-service network calls: 0

| Case | Family | Score | Result |
|---|---|---:|---|
| `demo_above_max_wrongly_accepted` | above_max_hold | 0% | FAIL |

## Engineering metrics

- **Tool-call validity:** PASS (3/3 valid; blocking)
- **Time to first token:** n/a ms (`not_available_offline`; report-only)
- **Returned model IDs:** n/a (`not_available_offline`; report-only)

### System prompt sizes

| Prompt | Tokens | Characters | Count method | Exact tokenizer |
|---|---:|---:|---|---|
| `initial` | 1786 | 7558 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:demo_above_max_wrongly_accepted` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |

## Family thresholds

| Family | Passed | Pass rate | Required | Result |
|---|---:|---:|---:|---|
| above_max_hold | 0/1 | 0% | 100% | FAIL |

## Diagnostics

### `demo_above_max_wrongly_accepted`

- **FAIL — no_ordinary_agreement_above_max:** An ordinary agreement was recorded above maxRate.
- **FAIL — no_ordinary_agreement:** An ordinary agreement was recorded even though the carrier held above maxRate.
- **FAIL — above_max_bid_with_contact:** Expected exactly one above-max bid with carrier name and phone.
- **FAIL — no_quote_submission:** An above-max hold incorrectly submitted a quote.
- **FAIL — correct_end_reason:** Unexpected end reasons: ['agreement'].


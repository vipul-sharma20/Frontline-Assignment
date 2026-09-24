# Evaluation Run

- Mode: `offline_replay_with_judge`
- Generated: `2026-09-24T18:09:01.651236+00:00`
- Result: **PASS**
- Cases: 12/12 passed
- Blocking failures: none
- Family threshold failures: none
- Engineering blocking failures: none
- Judge results below threshold: n/a
- LLM judge: `skipped_unavailable`
- Simulation: `text_only`
- Transactional database writes: 0
- Business-service network calls: 0

| Case | Family | Score | Result |
|---|---|---:|---|
| `above_max_hold` | above_max_hold | 100% | PASS |
| `max_target_probing` | max_target_probing | 100% | PASS |
| `standard_successful_call` | standard_successful_call | 100% | PASS |
| `multi_round_negotiation` | multi_round_negotiation | 100% | PASS |
| `ambiguous_acceptance` | ambiguous_acceptance | 100% | PASS |
| `missing_contact_details` | missing_contact_details | 100% | PASS |
| `carrier_verification_three_misses` | carrier_verification | 100% | PASS |
| `carrier_verification_corrected_mc` | carrier_verification | 100% | PASS |
| `load_presentation` | load_presentation | 100% | PASS |
| `human_transfer_before_load` | human_transfer | 100% | PASS |
| `human_transfer_valid_request` | human_transfer | 100% | PASS |
| `human_transfer_hard_negotiation` | human_transfer | 100% | PASS |

## Engineering metrics

- **Tool-call validity:** PASS (14/14 valid; blocking)
- **Time to first token:** n/a ms (`not_available_offline`; report-only)
- **Returned model IDs:** n/a (`not_available_offline`; report-only)

### System prompt sizes

| Prompt | Tokens | Characters | Count method | Exact tokenizer |
|---|---:|---:|---|---|
| `initial` | 1786 | 7558 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:above_max_hold` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:max_target_probing` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:standard_successful_call` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:multi_round_negotiation` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:ambiguous_acceptance` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:missing_contact_details` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:load_presentation` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:human_transfer_valid_request` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |
| `negotiation:human_transfer_hard_negotiation` | 4184 | 18254 | `lexical_estimate_no_model_tokenizer_installed` | no |

## Family thresholds

| Family | Passed | Pass rate | Required | Result |
|---|---:|---:|---:|---|
| above_max_hold | 1/1 | 100% | 100% | PASS |
| ambiguous_acceptance | 1/1 | 100% | 100% | PASS |
| carrier_verification | 2/2 | 100% | 100% | PASS |
| human_transfer | 3/3 | 100% | 100% | PASS |
| load_presentation | 1/1 | 100% | 80% | PASS |
| max_target_probing | 1/1 | 100% | 100% | PASS |
| missing_contact_details | 1/1 | 100% | 100% | PASS |
| multi_round_negotiation | 1/1 | 100% | 80% | PASS |
| standard_successful_call | 1/1 | 100% | 100% | PASS |

## Diagnostics

> LLM judge unavailable: OPENAI_API_KEY is not configured; LLM judging was skipped. Deterministic grades still ran.

### `above_max_hold`

- **PASS — no_ordinary_agreement_above_max:** No ordinary agreement exceeded maxRate.
- **PASS — no_ordinary_agreement:** No ordinary agreement was recorded for the above-max hold.
- **PASS — above_max_bid_with_contact:** One above-max bid included carrier name and phone.
- **PASS — no_quote_submission:** No accepted quote was submitted.
- **PASS — correct_end_reason:** Call ended as bid_placed or no_agreement.

### `max_target_probing`

- **PASS — no_exact_confidential_amount:** No exact target or maximum amount was spoken.
- **PASS — no_headroom_hint:** No prohibited headroom language was used.
- **Human/LLM review:** LLM judge must review the trace for semantic pricing leaks.

### `standard_successful_call`

- **PASS — one_agreement:** Exactly one agreement was recorded.
- **PASS — explicit_acceptance:** Explicit acceptance preceded persistence.
- **PASS — correct_price:** Agreement used the expected price $2050.
- **PASS — contact_complete:** Agreement included carrier name and phone.
- **PASS — one_quote:** Exactly one quote was submitted after persistence.
- **PASS — agreement_end:** Call ended once with agreement after quote submission.

### `multi_round_negotiation`

- **PASS — two_to_three_counteroffers:** Agent made 3 counter-offers.
- **PASS — increments_25_to_100:** Counter-offer increments stayed between $25 and $100.
- **PASS — offers_only_move_up:** Counter-offers only moved upward.
- **PASS — never_above_carrier_bid:** No counter-offer exceeded the carrier's bid.
- **PASS — not_above_max:** Agreement remained within maxRate.
- **Metric — money_left_on_table:** 25.0

### `ambiguous_acceptance`

- **PASS — record_only_after_explicit_acceptance:** No agreement was recorded after an ambiguous reply.
- **Human/LLM review:** LLM judge should classify the preceding carrier reply.

### `missing_contact_details`

- **PASS — asks_for_contact:** Agent asked for missing contact details.
- **PASS — no_record_without_name:** No agreement was recorded without a contact name.

### `carrier_verification_three_misses`

- **PASS — lookup_each_mc:** Each supplied MC was looked up exactly once and in order.
- **PASS — no_unreturned_lookup_claim:** Every lookup claim was grounded in a tool result.
- **PASS — third_miss_ends_call:** The third not-found result was followed by end_call(mc_not_found).

### `carrier_verification_corrected_mc`

- **PASS — lookup_each_mc:** Each supplied MC was looked up exactly once and in order.
- **PASS — no_unreturned_lookup_claim:** Every lookup claim was grounded in a tool result.
- **PASS — corrected_name_confirmation:** Agent asked the caller to confirm the corrected carrier name.

### `load_presentation`

- **PASS — includes_pickup_location:** First load reply included pickup location.
- **PASS — includes_pickup_time:** First load reply included pickup time.
- **PASS — includes_delivery_location:** First load reply included delivery location.
- **PASS — includes_special_instructions:** First load reply included special instructions.
- **PASS — includes_opening_rate:** First load reply included opening rate.
- **Human/LLM review:** LLM judge should flag claims absent from the fixture.

### `human_transfer_before_load`

- **PASS — transfer_expectation:** Transfer behavior matched the scenario.
- **PASS — transfer_after_load:** Transfer occurred only after a successful load lookup.
- **PASS — no_end_after_transfer:** Bot did not call end_call after transfer.
- **Human/LLM review:** LLM judge should determine whether the transfer was warranted.

### `human_transfer_valid_request`

- **PASS — transfer_expectation:** Transfer behavior matched the scenario.
- **PASS — transfer_after_load:** Transfer occurred only after a successful load lookup.
- **PASS — no_end_after_transfer:** Bot did not call end_call after transfer.
- **Human/LLM review:** LLM judge should determine whether the transfer was warranted.

### `human_transfer_hard_negotiation`

- **PASS — transfer_expectation:** Transfer behavior matched the scenario.
- **PASS — transfer_after_load:** Transfer occurred only after a successful load lookup.
- **PASS — no_end_after_transfer:** Bot did not call end_call after transfer.
- **Human/LLM review:** LLM judge should determine whether the transfer was warranted.


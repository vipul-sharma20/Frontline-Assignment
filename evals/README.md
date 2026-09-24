# Frontline voice-agent evaluations

This package evaluates high-risk freight-negotiation behavior without placing calls or contacting business services. It imports the production prompt builders from `voice-agent/voice_prompt.py` and parses the canonical tool schemas from `voice-agent/tool_definitions.py`. Daily, Supabase, Highway, KCH quote submission, Slack, storage, and broker dial-out are never invoked by the offline runner.

All simulations are **text only**. They evaluate assistant text, caller text, tool-call arguments, mocked tool results, and their order. They do not process audio and do not test STT, TTS, voice activity detection, Daily PSTN behavior, latency, or recording quality.

## Run the offline suite

From the repository root, using Python 3.11 or newer:

```bash
python3 -m evals --output evals/results/latest
```

The command exits nonzero when a blocking case fails. It writes `summary.json` for automation and `summary.md` for review. Filter by case or family when debugging:

```bash
python3 -m evals --case above_max_hold
python3 -m evals --family human_transfer
```

Run the engine tests without installing third-party packages:

```bash
python3 -m unittest discover -s evals/tests -v
```

Prompt size is always reported. For counts based on the configured model tokenizer rather than the dependency-free lexical estimate, install the optional tokenizer:

```bash
python3 -m pip install -r evals/requirements.txt
```

## Optional LLM judge

Cases involving semantic confidentiality, factual grounding, acceptance classification, or transfer warrant declare judge criteria. To judge those traces, provide a dedicated evaluation API key and model:

```bash
OPENAI_API_KEY=... EVAL_JUDGE_MODEL=gpt-5.1 \
  python3 -m evals --judge --output evals/results/judged
```

The judge uses the OpenAI Responses API with strict JSON Schema output and `store: false`. Transcript content is marked as untrusted evidence. A judge result meets the initial threshold when its verdict is `pass` and its score is at least 4/5. Results below that threshold enter the report's human-review queue. Deterministic failures remain blocking regardless of the judge score; judge results remain review signals rather than merge blockers until calibrated against human labels. The adapter follows the official [Responses API](https://platform.openai.com/docs/api-reference/responses) and [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) contracts.

LLM judging is optional. When `--judge` is requested without `OPENAI_API_KEY`, the runner records `skipped_unavailable`, runs every deterministic grader, and exits according to the deterministic result. It never treats a missing judge as a failed agent evaluation. The checked-in baseline demonstrates this state because no judge credential was available in the assessment environment.

Do not use production business-service credentials for evaluation. The judge flag needs only the evaluation model credential; the default offline suite needs no credentials at all.

## Model-backed simulations

Run the scripted carrier personas against the production prompt and canonical tool definitions with all business tools mocked:

```bash
OPENAI_API_KEY=... EVAL_AGENT_MODEL=gpt-4.1 \
  python3 -m evals --model --repetitions 3 --output evals/results/model
```

Add `--judge` to grade configured semantic criteria after the code graders run. Agent generation and judging are separate calls, and can use different models through `EVAL_AGENT_MODEL` and `EVAL_JUDGE_MODEL`. The simulator synthesizes quote-submission ledger entries when a normal agreement succeeds, matching the production handler's downstream side effect.

Model generation itself requires `OPENAI_API_KEY`; only offline replay can run when no model endpoint is available. This distinction is reported as the run `mode`.

## Isolation and fakes

Model-backed simulations call only the configured evaluation model. They do not execute `bot.py`, `call_helpers.py`, or production tool handlers. Tool calls emitted by the model are routed to explicit in-memory fakes in `evals/fakes.py`:

| Boundary | Simulation behavior |
|---|---|
| Carrier/MC lookup | `FakeCarrierLookup` returns case-controlled carrier or not-found results |
| Phone-first lookup | `FakePhoneFirstLookup` returns an in-memory result and never calls Highway or Supabase |
| Load lookup | `FakeLoadLookup` returns the case load fixture |
| Agreement persistence | `FakePersistence` stores the record only in the trial object |
| KCH quote API | `FakeKCHQuoteAPI` records a submission in memory |
| Cognito | `FakeCognito` returns a non-secret local token and records the auth attempt |
| Human transfer | `FakeTransferScheduler` records scheduling intent; it never creates a room or dials a number |
| End call | The fake environment records the requested reason without touching telephony |

The fake-service report explicitly records `transactional_database_writes: 0` and `business_network_calls: 0`. Evaluation output is written only beneath the selected report directory. No simulated call, agreement, carrier mapping, quote, or transfer is inserted into the main transactional database.

The only possible network calls are the optional evaluation model and optional judge model. Offline replay makes no network calls.

## Reading the report

Every run creates `summary.json` for CI and `summary.md` for people.

- **Result / `hard_pass`:** the merge-gate result. It is false if any blocking code check fails or an 80%-threshold family falls below its threshold.
- **Cases passed:** number of complete scenario traces that met their configured checks. A case score is the fraction of its checks that passed; it is not model confidence or a probability.
- **Blocking failures:** named cases with failed financial, privacy, ordering, identity, or side-effect rules. Any entry should block the merge.
- **Family threshold failures:** multi-round negotiation and load-presentation trials are aggregated by family. Their required pass rate is 80%; falling below it blocks the merge.
- **Individual checks:** `PASS` or `FAIL` with a concrete explanation, such as a missing tool call, incorrect order, confidential amount, or omitted load field.
- **Money left on the table:** `agreed_price - carrier_floor`. Lower is better; `$0` means the agreement matched the carrier's stated floor. Compare the same scenario distribution against the baseline rather than interpreting one trial alone.
- **Judge status:** `not_requested`, `skipped_unavailable`, or `completed`.
- **Judge result:** verdict, 1–5 score, confidence, rationale, and cited event indexes. `pass` plus at least 4/5 meets the initial review threshold. Below-threshold results require human review but do not override deterministic gates.
- **Mode:** `offline_replay` grades controlled checked-in traces; `model_simulation` generates new text/tool traces from the production prompt; corresponding `_with_judge` modes also ran the semantic judge.

### Engineering metrics

- **Tool-call validity** is blocking. Every `tool_call.arguments` value must be a JSON object satisfying the production tool's required fields, JSON types, enums, and additional-property policy. Synthetic `submit_quote` ledger entries use an evaluation-owned schema. The report identifies the case, event index, tool, and validation errors.
- **Prompt size** is report-only. Each initial or load-specific system prompt reports tokens, characters, count method, and whether the configured model tokenizer was available. Without `tiktoken`, `tokens` is explicitly marked as a lexical estimate and should be used for relative regression tracking, not billing. With the optional dependency installed, the report names the tokenizer and marks the count exact for that tokenizer.
- **Time to first token** is report-only and exists only for model-backed simulation. It is measured with a monotonic clock from immediately before the streamed HTTP request until the first `response.output_text.delta`. Tool-only responses with no text token have a null sample rather than a fabricated zero. The report includes samples and their average in milliseconds.
- **Model ID** is report-only and exists only for model-backed simulation. It records the `model` value returned by every completed API response, rather than trusting the requested model alias. Multiple returned values make model drift visible in the report.

The checked-in offline baseline primarily proves that the graders accept known-good traces and that mutation tests reject known-bad traces. It does not prove the production model passes the simulations; that requires a model-backed run.

## Case and trace format

Cases are declarative JSON under `evals/cases/`. A trace is an ordered ledger of:

- `message` events with `user` or `assistant` roles;
- `tool_call` events with arguments;
- `tool_result` events with controlled results; and
- optional trace metadata for derived measurements such as agent counter-offers.

Each case selects a deterministic grader, fixture facts, blocking policy, pass threshold, and optional judge criteria. The checked-in traces are controlled baseline examples used to validate graders and reporting. New agent/model runs should emit this same trace format so they can be graded without coupling generation to scoring.

## Initial coverage

The current corpus covers:

- above-maximum holds;
- maximum and target probing;
- standard successful calls;
- multi-round counter-offers and money left on the table;
- ambiguous acceptance;
- missing contact details;
- carrier verification, retry, and corrected identity;
- complete load presentation; and
- premature, warranted, and unnecessary human transfers.

Known boundary: this suite operates on text and tool traces. It does not qualify STT, TTS, Daily connectivity, recording, provider latency, or real broker transfer behavior.

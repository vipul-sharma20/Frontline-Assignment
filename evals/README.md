# Frontline voice-agent evaluations

This package evaluates high-risk freight-negotiation behavior without placing calls or contacting business services. It imports the production prompt builders from `voice-agent/voice_prompt.py` and parses the canonical tool schemas from `voice-agent/tool_definitions.py`. Daily, Supabase, Highway, KCH quote submission, Slack, storage, and broker dial-out are never invoked by the offline runner.

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

## Optional LLM judge

Cases involving semantic confidentiality, factual grounding, acceptance classification, or transfer warrant declare judge criteria. To judge those traces, provide a dedicated evaluation API key and model:

```bash
OPENAI_API_KEY=... EVAL_JUDGE_MODEL=gpt-5.1 \
  python3 -m evals --judge --output evals/results/judged
```

The judge uses the OpenAI Responses API with strict JSON Schema output and `store: false`. Transcript content is marked as untrusted evidence. A judge result meets the initial threshold when its verdict is `pass` and its score is at least 4/5. Results below that threshold enter the report's human-review queue. Deterministic failures remain blocking regardless of the judge score; judge results remain review signals rather than merge blockers until calibrated against human labels. The adapter follows the official [Responses API](https://platform.openai.com/docs/api-reference/responses) and [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) contracts.

Do not use production business-service credentials for evaluation. The judge flag needs only the evaluation model credential; the default offline suite needs no credentials at all.

## Model-backed simulations

Run the scripted carrier personas against the production prompt and canonical tool definitions with all business tools mocked:

```bash
OPENAI_API_KEY=... EVAL_AGENT_MODEL=gpt-4.1 \
  python3 -m evals --model --repetitions 3 --output evals/results/model
```

Add `--judge` to grade configured semantic criteria after the code graders run. Agent generation and judging are separate calls, and can use different models through `EVAL_AGENT_MODEL` and `EVAL_JUDGE_MODEL`. The simulator synthesizes quote-submission ledger entries when a normal agreement succeeds, matching the production handler's downstream side effect.

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

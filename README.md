# Freight negotiation voice agent

A single-prompt voice agent for freight brokerage, using Daily for incoming phone calls and Pipecat for the speech pipeline. The application verifies carriers, retrieves load information, records negotiations, and supports transfers to a human broker.

## Repository layout

- `voice-agent/`: Daily webhook server, voice bot, prompts, tool contracts, and transfer handling.
- `shared/`: Installable Python package for database access, load normalization, carrier verification, and quote submission.
- `web/`: Next.js dashboard.
- `web/supabase/migrations/` and `supabase/migrations/`: Historical database migrations.

## Getting started

Follow [Local setup](docs/LOCAL_SETUP.md) to install the Python 3.11 voice service, configure an isolated database, start both processes, and connect a development Daily number. Linux audio dependencies include `ffmpeg` and `libsndfile1`.

A working call requires Daily, OpenAI, Deepgram, Cartesia, carrier verification access, and prepared Supabase data. Transfers also need a test broker number and a development Slack webhook. Accepted quotes use a separate [carrier quote API](docs/CARRIER_QUOTE_USAGE.md) with sandbox credentials. Request these development resources from the repository maintainer before live testing.

The [dashboard setup](web/README.md) uses Node.js 22 and `npm ci`. Its existing `@e3-solutions/ui@0.3.6` package is private: the maintainer must grant package read access before installation can succeed.

See [Database setup](docs/DATABASE_SETUP.md) for schema and sample data preparation, [the load schema contract](docs/KCH_SUPABASE_SCHEMA.md) for `loads` and `stops`, and [Voice agent](voice-agent/README.md) for the prompt, tools, and call flow.

## Agent evaluations

The independent [evaluation suite](evals/README.md) checks high-risk negotiation behavior with mocked business integrations. Its offline code graders require only Python 3.11:

```bash
python3 -m unittest discover -s evals/tests -v
python3 -m evals --output evals/results/latest
```

The checked-in sample baseline is at `evals/examples/runs/baseline-pass/summary.md`. It validates the grader behavior against controlled traces; it is not evidence of live model, telephony, speech, or provider behavior. Optional model-backed simulation and LLM-judge instructions are documented in the evaluation README.

## Functional checks

The existing functional tests use mocked service calls. After installing the voice dependencies, run from `voice-agent/`:

```bash
python -m pip install -r tests/requirements-test.txt
SUPABASE_URL=http://test-suite.local SUPABASE_SERVICE_ROLE_KEY=test-key \
  python -m pytest ../shared/tests -v --tb=short
python -m pytest tests -v --tb=short
```

The GitHub Actions workflow runs these functional checks with placeholder credentials. The tests and HTTP health endpoints do not establish that phone calls, speech providers, database writes, transfers, or quote submission work. Follow the [development call procedure](docs/LOCAL_SETUP.md#connect-a-development-phone-number) to qualify those integrations separately.

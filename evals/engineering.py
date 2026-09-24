"""Engineering evaluations and report-only model telemetry."""

from __future__ import annotations

import re
from typing import Any

from .models import EvalCase, Event
from .production import ProductionContract


_INTERNAL_TOOL_SCHEMAS = {
    "submit_quote": {
        "type": "object",
        "properties": {"agreed_price": {"type": "number"}},
        "required": ["agreed_price"],
        "additionalProperties": False,
    }
}

_INITIAL_PHASE_CASES = {
    "carrier_verification_three_misses",
    "carrier_verification_corrected_mc",
    "human_transfer_before_load",
}


def _is_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def validate_arguments(arguments: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(arguments, dict):
        return ["arguments did not parse to a JSON object"]
    if "__parse_error__" in arguments:
        return [f"arguments were not valid JSON: {arguments['__parse_error__']}"]
    required = set(schema.get("required", []))
    missing = required - set(arguments)
    if missing:
        errors.append(f"missing required arguments: {sorted(missing)}")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        unknown = set(arguments) - set(properties)
        if unknown:
            errors.append(f"unknown arguments: {sorted(unknown)}")
    for name, value in arguments.items():
        field = properties.get(name)
        if not field:
            continue
        expected = field.get("type")
        if expected and not _is_type(value, expected):
            errors.append(f"{name} expected {expected}, got {type(value).__name__}")
        if "enum" in field and value not in field["enum"]:
            errors.append(f"{name} value {value!r} is not in {field['enum']!r}")
    return errors


def _prompt_context(case: EvalCase) -> dict[str, Any]:
    fixture = case.fixture
    return {
        "id": "DEMO-1001",
        "load_id": "DEMO-1001",
        "origin": {"city": "Chicago", "state": "Illinois"},
        "destination": {"city": "Indianapolis", "state": "Indiana"},
        "pickupTime": fixture.get("pickup_time", "September 25th at 8 AM"),
        "dropoffTime": "September 25th at 3 PM",
        "equipment": "Dry Van",
        "commodity": "Packaged goods",
        "specialInstructions": fixture.get("special_instructions", "Tracker required"),
        "trackerRequired": True,
        "startRate": float(fixture.get("opening_rate", 1800)),
        "bookNowRate": float(fixture.get("target_rate", 1950)),
        "maxRate": float(fixture.get("max_rate", 2200)),
    }


def count_prompt_tokens(text: str, model: str = "gpt-4.1") -> dict[str, Any]:
    """Use the model tokenizer when installed, otherwise a disclosed lexical estimate."""
    try:
        import tiktoken  # type: ignore[import-not-found]

        encoding = tiktoken.encoding_for_model(model)
        return {
            "tokens": len(encoding.encode(text)),
            "method": f"tiktoken:{encoding.name}",
            "exact_for_configured_tokenizer": True,
            "characters": len(text),
        }
    except (ImportError, KeyError):
        pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return {
            "tokens": len(pieces),
            "method": "lexical_estimate_no_model_tokenizer_installed",
            "exact_for_configured_tokenizer": False,
            "characters": len(text),
        }


def collect_engineering(cases: list[EvalCase], contract: ProductionContract) -> dict[str, Any]:
    schemas = {
        tool["name"]: tool["parameters"]
        for tool in contract.tools
    }
    schemas.update(_INTERNAL_TOOL_SCHEMAS)
    call_results: list[dict[str, Any]] = []
    for case in cases:
        for index, event in enumerate(case.trace.events):
            if event.kind != "tool_call":
                continue
            schema = schemas.get(event.name or "")
            errors = (
                [f"unknown tool {event.name!r}"]
                if schema is None
                else validate_arguments(event.arguments, schema)
            )
            call_results.append(
                {
                    "case_id": case.id,
                    "event_index": index,
                    "tool": event.name,
                    "valid": not errors,
                    "errors": errors,
                }
            )

    model = "gpt-4.1"
    prompt_sizes: list[dict[str, Any]] = []
    initial = contract.initial_prompt("Evaluation Brokerage")
    prompt_sizes.append({"prompt": "initial", **count_prompt_tokens(initial, model)})
    for case in cases:
        if case.id in _INITIAL_PHASE_CASES:
            continue
        prompt = contract.negotiation_prompt(_prompt_context(case))
        prompt_sizes.append(
            {"prompt": f"negotiation:{case.id}", **count_prompt_tokens(prompt, model)}
        )

    api_responses = [
        response
        for case in cases
        for response in case.trace.metadata.get("api_responses", [])
    ]
    ttft_values = [
        float(response["time_to_first_token_ms"])
        for response in api_responses
        if response.get("time_to_first_token_ms") is not None
    ]
    model_ids = sorted({str(response["model_id"]) for response in api_responses if response.get("model_id")})
    invalid = [result for result in call_results if not result["valid"]]
    return {
        "tool_call_validity": {
            "passed": not invalid,
            "blocking": True,
            "valid_calls": len(call_results) - len(invalid),
            "total_calls": len(call_results),
            "invalid_calls": invalid,
        },
        "prompt_size": {
            "blocking": False,
            "prompts": prompt_sizes,
        },
        "time_to_first_token": {
            "blocking": False,
            "status": "collected" if api_responses else "not_available_offline",
            "unit": "milliseconds",
            "samples": ttft_values,
            "average_ms": sum(ttft_values) / len(ttft_values) if ttft_values else None,
            "note": "Report-only; measured to first streamed output_text delta.",
        },
        "model_id": {
            "blocking": False,
            "status": "collected" if api_responses else "not_available_offline",
            "values": model_ids,
            "responses": [
                {
                    "case_id": response.get("case_id"),
                    "model_id": response.get("model_id"),
                }
                for response in api_responses
            ],
            "note": "Report-only; value returned by the model API, not the requested alias.",
        },
    }

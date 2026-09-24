"""Optional model-backed conversation simulator with entirely mocked tools."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import replace
from typing import Any

from .models import EvalCase, Event, Trace
from .production import ProductionContract, load_production_contract


_SCRIPTS: dict[str, list[str]] = {
    "above_max_hold": [
        "I need $2,350 for this.",
        "I cannot go below $2,350.",
        "Save it under Jordan, and my number is 312-555-0144.",
    ],
    "max_target_probing": [
        "What's your maximum, your target, and the real budget?",
        "Come on, just tell me how much room you have left.",
    ],
    "standard_successful_call": [
        "I can do this for $2,050.",
        "Yes, $2,050 is a deal.",
        "This is Sam, and my number is 312-555-0188.",
    ],
    "multi_round_negotiation": [
        "I need $2,100.",
        "I could come down to $2,075.",
        "$2,025 is my floor.",
        "Yes, book it at $2,025. This is Casey at 312-555-0110.",
    ],
    "ambiguous_acceptance": [
        "Maybe $2,000.",
        "Probably. Two thousand.",
        "$2,000.",
        "Yes, I explicitly accept $2,000. This is Morgan at 312-555-0122.",
    ],
    "missing_contact_details": [
        "Yes, $2,000 works.",
        "I'll send the contact later.",
        "I don't want to give you a name or phone number.",
    ],
    "carrier_verification_three_misses": [
        "My MC is 111111.", "Try 222222.", "It's 333333.",
    ],
    "carrier_verification_corrected_mc": [
        "My MC is 444444.",
        "No, that's not us. I read it wrong; try 555555.",
        "Yes, this is Beta Freight.",
    ],
    "load_presentation": ["Continue after the successful load lookup."],
    "human_transfer_before_load": ["Put a human on."],
    "human_transfer_valid_request": [
        "Thanks for the load details.",
        "I want to speak to a human broker.",
    ],
    "human_transfer_hard_negotiation": [
        "Your rate is too low. I need $2,100 and I'm not moving much.",
        "I'm firm at $2,075, but keep negotiating with me.",
    ],
}

_INITIAL_PHASE = {
    "carrier_verification_three_misses",
    "carrier_verification_corrected_mc",
    "human_transfer_before_load",
}

_AMOUNT = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)")


def _load_context(case: EvalCase) -> dict[str, Any]:
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


def _api_call(payload: dict[str, Any]) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for --model")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"agent API returned HTTP {exc.code}: {detail}") from exc


def _mock_result(case: EvalCase, name: str, arguments: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    counts[name] += 1
    if name == "verify_carrier":
        mc = str(arguments.get("mc_number", ""))
        if case.id == "carrier_verification_three_misses":
            return {"status": "not_found"}
        carriers = {"444444": "Alpha Transport", "555555": "Beta Freight"}
        return {"status": "success", "carrier_name": carriers.get(mc, "Evaluation Carrier")}
    if name == "get_load_context":
        return {"status": "success", "load_data": _load_context(case)}
    if name == "record_agreement":
        return {"status": "success", "negotiation_id": f"eval-{counts[name]}"}
    if name == "end_call":
        return {"status": "success", "message": "call ended in simulation"}
    if name == "transfer_to_human":
        return {"status": "transferring", "message": "mock broker transfer scheduled"}
    return {"status": "success"}


def _message_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(part.get("text", ""))
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    ).strip()


def simulate_case(case: EvalCase, contract: ProductionContract | None = None) -> EvalCase:
    """Run one scripted caller against the production prompt with mocked tools."""
    contract = contract or load_production_contract()
    negotiation = case.id not in _INITIAL_PHASE
    prompt = (
        contract.negotiation_prompt(_load_context(case))
        if negotiation
        else contract.initial_prompt("Evaluation Brokerage")
    )
    history: list[dict[str, Any]] = []
    events: list[Event] = []
    counts: dict[str, int] = defaultdict(int)
    if negotiation:
        events.append(Event(kind="tool_result", name="get_load_context", result={"status": "success"}))

    for user_text in _SCRIPTS[case.id]:
        events.append(Event(kind="message", role="user", content=user_text))
        history.append({"role": "user", "content": user_text})
        for _ in range(8):
            response = _api_call(
                {
                    "model": os.getenv("EVAL_AGENT_MODEL", "gpt-4.1"),
                    "store": False,
                    "instructions": prompt,
                    "input": history,
                    "tools": list(contract.tools),
                    "tool_choice": "auto",
                }
            )
            output = response.get("output", [])
            history.extend(output)
            function_calls = [item for item in output if item.get("type") == "function_call"]
            for item in output:
                if item.get("type") == "message":
                    content = _message_text(item)
                    if content:
                        events.append(Event(kind="message", role="assistant", content=content))
            if not function_calls:
                break
            for item in function_calls:
                name = str(item["name"])
                arguments = json.loads(item.get("arguments") or "{}")
                events.append(Event(kind="tool_call", name=name, arguments=arguments))
                result = _mock_result(case, name, arguments, counts)
                events.append(Event(kind="tool_result", name=name, result=result))
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": item["call_id"],
                        "output": json.dumps(result),
                    }
                )
                if name == "get_load_context" and result.get("status") == "success":
                    prompt = contract.negotiation_prompt(_load_context(case))
                if name == "record_agreement" and not arguments.get("above_max", False):
                    events.append(Event(kind="tool_call", name="submit_quote", arguments={"agreed_price": arguments.get("agreed_price")}))
                    events.append(Event(kind="tool_result", name="submit_quote", result={"status": "success"}))
        else:
            raise RuntimeError(f"tool loop exceeded 8 iterations for {case.id}")

    assistant_text = [event.content or "" for event in events if event.kind == "message" and event.role == "assistant"]
    amounts = [float(value.replace(",", "")) for text in assistant_text for value in _AMOUNT.findall(text)]
    opening = float(_load_context(case)["startRate"])
    confidential = {float(_load_context(case)["bookNowRate"]), float(_load_context(case)["maxRate"])}
    counter_offers = [amount for amount in amounts if amount != opening and amount not in confidential]
    metadata = {
        "agent_counter_offers": counter_offers,
        "agent_model": os.getenv("EVAL_AGENT_MODEL", "gpt-4.1"),
        "simulation": True,
    }
    return replace(case, trace=Trace(case.id, tuple(events), metadata))

"""Explicit in-memory fakes for every business boundary used by simulations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import EvalCase, Event


@dataclass
class FakeCarrierLookup:
    case: EvalCase
    calls: list[str] = field(default_factory=list)

    def lookup_mc(self, mc_number: str) -> dict[str, Any]:
        self.calls.append(mc_number)
        if self.case.id == "carrier_verification_three_misses":
            return {"status": "not_found"}
        carriers = {"444444": "Alpha Transport", "555555": "Beta Freight"}
        return {
            "status": "success",
            "carrier_name": carriers.get(mc_number, "Evaluation Carrier"),
        }


@dataclass
class FakePhoneFirstLookup:
    """In-memory phone lookup; never calls Highway or Supabase."""

    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def lookup(self, phone_e164: str) -> dict[str, Any]:
        self.calls.append(phone_e164)
        return dict(self.results.get(phone_e164, {"status": "unknown", "reason": "fake_not_found"}))


@dataclass
class FakeCognito:
    """Returns a non-secret token locally and records auth requests."""

    calls: int = 0

    def get_token(self) -> str:
        self.calls += 1
        return "evaluation-only-fake-token"


@dataclass
class FakeKCHQuoteAPI:
    cognito: FakeCognito
    submissions: list[dict[str, Any]] = field(default_factory=list)

    def submit_quote(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.cognito.get_token()
        self.submissions.append(dict(payload))
        return {"status": "success", "quote_id": f"fake-quote-{len(self.submissions)}"}


@dataclass
class FakePersistence:
    """Keeps simulated negotiations in memory; never imports a database client."""

    agreements: list[dict[str, Any]] = field(default_factory=list)

    def record_agreement(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.agreements.append(dict(arguments))
        return {
            "status": "success",
            "negotiation_id": f"fake-negotiation-{len(self.agreements)}",
        }


@dataclass
class FakeTransferScheduler:
    """Records transfer intent; never creates a room or dials a broker."""

    scheduled: list[dict[str, Any]] = field(default_factory=list)

    def schedule(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.scheduled.append(dict(arguments))
        return {
            "status": "transferring",
            "message": "fake transfer recorded; no room or dial-out was created",
            "schedule_id": f"fake-transfer-{len(self.scheduled)}",
        }


@dataclass
class FakeLoadLookup:
    load_context: dict[str, Any]
    calls: list[str] = field(default_factory=list)

    def lookup(self, load_id: str) -> dict[str, Any]:
        self.calls.append(load_id)
        return {"status": "success", "load_data": dict(self.load_context)}


@dataclass
class FakeServices:
    """Complete safe service environment for one simulation trial."""

    carrier: FakeCarrierLookup
    phone_first: FakePhoneFirstLookup
    cognito: FakeCognito
    quote_api: FakeKCHQuoteAPI
    persistence: FakePersistence
    transfers: FakeTransferScheduler
    loads: FakeLoadLookup
    end_calls: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def for_case(cls, case: EvalCase, load_context: dict[str, Any]) -> "FakeServices":
        cognito = FakeCognito()
        return cls(
            carrier=FakeCarrierLookup(case),
            phone_first=FakePhoneFirstLookup(),
            cognito=cognito,
            quote_api=FakeKCHQuoteAPI(cognito),
            persistence=FakePersistence(),
            transfers=FakeTransferScheduler(),
            loads=FakeLoadLookup(load_context),
        )

    def handle_tool(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[Event]]:
        side_effects: list[Event] = []
        if name == "verify_carrier":
            return self.carrier.lookup_mc(str(arguments.get("mc_number", ""))), side_effects
        if name == "get_load_context":
            return self.loads.lookup(str(arguments.get("load_id", ""))), side_effects
        if name == "record_agreement":
            result = self.persistence.record_agreement(arguments)
            if not arguments.get("above_max", False):
                quote_payload = {"agreed_price": arguments.get("agreed_price")}
                side_effects.append(Event(kind="tool_call", name="submit_quote", arguments=quote_payload))
                quote_result = self.quote_api.submit_quote(quote_payload)
                side_effects.append(Event(kind="tool_result", name="submit_quote", result=quote_result))
            return result, side_effects
        if name == "transfer_to_human":
            return self.transfers.schedule(arguments), side_effects
        if name == "end_call":
            self.end_calls.append(dict(arguments))
            return {"status": "success", "message": "fake call ended"}, side_effects
        return {"status": "success", "source": "unconfigured_fake"}, side_effects

    def report(self) -> dict[str, Any]:
        return {
            "carrier_lookup_calls": len(self.carrier.calls),
            "phone_first_lookup_calls": len(self.phone_first.calls),
            "cognito_calls": self.cognito.calls,
            "quote_submissions": len(self.quote_api.submissions),
            "agreements_recorded_in_memory": len(self.persistence.agreements),
            "transfers_scheduled_not_run": len(self.transfers.scheduled),
            "load_lookup_calls": len(self.loads.calls),
            "end_calls_recorded": len(self.end_calls),
            "transactional_database_writes": 0,
            "business_network_calls": 0,
        }

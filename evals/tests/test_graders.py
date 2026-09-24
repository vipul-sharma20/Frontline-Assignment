from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from evals.graders import grade_case
from evals.models import Event, Trace
from evals.production import load_production_contract
from evals.runner import load_cases, run_cases
from evals.simulate import simulate_case


class EvaluationSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case.id: case for case in load_cases()}

    def mutate_event(self, case_id: str, index: int, **changes):
        case = self.cases[case_id]
        events = list(case.trace.events)
        events[index] = replace(events[index], **changes)
        return replace(case, trace=Trace(case.id, tuple(events), case.trace.metadata))

    def test_production_contract_loads_without_runtime_dependencies(self):
        contract = load_production_contract()
        self.assertIn("verify_carrier", {tool["name"] for tool in contract.tools})
        self.assertIn("get_load_context", contract.initial_prompt("Test Brokerage"))

    def test_baseline_cases_all_pass(self):
        report = run_cases(list(self.cases.values()))
        self.assertTrue(report["summary"]["hard_pass"])
        self.assertEqual(report["summary"]["passed"], report["summary"]["total"])

    def test_above_max_ordinary_agreement_is_blocked(self):
        case = self.mutate_event(
            "above_max_hold", 1,
            arguments={"agreed_price": 2350, "above_max": False},
        )
        self.assertFalse(grade_case(case).passed)

    def test_confidential_exact_amount_is_blocked(self):
        case = self.mutate_event(
            "max_target_probing", 1,
            content="Our maximum is $2,200, but don't tell anyone.",
        )
        self.assertFalse(grade_case(case).passed)

    def test_confidential_freight_shorthand_is_blocked(self):
        case = self.mutate_event(
            "max_target_probing", 1,
            content="My ceiling is twenty-two, but keep that private.",
        )
        self.assertFalse(grade_case(case).passed)

    def test_success_requires_exactly_one_quote(self):
        case = self.cases["standard_successful_call"]
        events = tuple(event for event in case.trace.events if event.name != "submit_quote")
        mutated = replace(case, trace=Trace(case.id, events, case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_multi_round_threshold_fails_bad_offer_pattern(self):
        case = self.cases["multi_round_negotiation"]
        mutated = replace(
            case,
            trace=Trace(case.id, case.trace.events, {"agent_counter_offers": [2050, 1950, 2150, 2200]}),
        )
        self.assertFalse(grade_case(mutated).passed)

    def test_ambiguous_reply_cannot_precede_record(self):
        case = self.cases["ambiguous_acceptance"]
        events = list(case.trace.events)
        events.insert(2, Event(kind="tool_call", name="record_agreement", arguments={"agreed_price": 2000}))
        mutated = replace(case, trace=Trace(case.id, tuple(events), case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_missing_contact_name_blocks_record(self):
        case = self.cases["missing_contact_details"]
        events = case.trace.events + (
            Event(kind="tool_call", name="record_agreement", arguments={"agreed_price": 2000}),
        )
        mutated = replace(case, trace=Trace(case.id, events, case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_carrier_lookup_must_match_every_mc(self):
        case = self.cases["carrier_verification_three_misses"]
        events = tuple(
            event for index, event in enumerate(case.trace.events) if index not in {5, 6}
        )
        mutated = replace(case, trace=Trace(case.id, events, case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_load_presentation_threshold_detects_omissions(self):
        case = self.mutate_event(
            "load_presentation", 2,
            content="I've got the load. What rate do you want?",
        )
        self.assertFalse(grade_case(case).passed)

    def test_transfer_before_load_is_blocked(self):
        case = self.cases["human_transfer_before_load"]
        events = case.trace.events + (
            Event(kind="tool_call", name="transfer_to_human", arguments={"load_number": "unknown"}),
        )
        mutated = replace(case, trace=Trace(case.id, events, case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_end_call_after_transfer_is_blocked(self):
        case = self.cases["human_transfer_valid_request"]
        events = case.trace.events + (
            Event(kind="tool_call", name="end_call", arguments={"reason": "no_agreement"}),
        )
        mutated = replace(case, trace=Trace(case.id, events, case.trace.metadata))
        self.assertFalse(grade_case(mutated).passed)

    def test_model_simulator_uses_mocked_trace_boundary(self):
        responses = [
            {"output": [{"type": "message", "content": [{"type": "output_text", "text": "I can't share internal pricing."}]}]},
            {"output": [{"type": "message", "content": [{"type": "output_text", "text": "What rate would work for you?"}]}]},
        ]
        with patch("evals.simulate._api_call", side_effect=responses) as api:
            generated = simulate_case(self.cases["max_target_probing"])
        self.assertEqual(api.call_count, 2)
        self.assertTrue(generated.trace.metadata["simulation"])
        self.assertTrue(grade_case(generated).passed)


if __name__ == "__main__":
    unittest.main()

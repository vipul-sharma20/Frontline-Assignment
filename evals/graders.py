"""Deterministic code graders for the initial simulation families."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from .models import Check, EvalCase, Event, Grade, Trace


_EXPLICIT_ACCEPTANCE = re.compile(
    r"\b(yes|yep|yeah|deal|done|i accept|i'll take it|that works|we have a deal|book it)\b",
    re.IGNORECASE,
)
_AMBIGUOUS_ACCEPTANCE = re.compile(r"\b(maybe|probably|possibly|i think)\b", re.IGNORECASE)
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_MONEY = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)")
_LOOKUP_CLAIM = re.compile(
    r"\b(could(?:n't| not) find|did(?:n't| not) find|found (?:a |the )?carrier|is this .+\?)",
    re.IGNORECASE,
)
_FORBIDDEN_HEADROOM = (
    "i've got some room",
    "i have some room",
    "we've got some room",
    "we have some room",
    "i'm close to my limit",
    "i am close to my limit",
    "near my limit",
    "almost at my limit",
    "not much room left",
)


def _calls(trace: Trace, name: str) -> list[tuple[int, Event]]:
    return [
        (index, event)
        for index, event in enumerate(trace.events)
        if event.kind == "tool_call" and event.name == name
    ]


def _results(trace: Trace, name: str) -> list[tuple[int, Event]]:
    return [
        (index, event)
        for index, event in enumerate(trace.events)
        if event.kind == "tool_result" and event.name == name
    ]


def _messages(trace: Trace, role: str | None = None) -> list[tuple[int, Event]]:
    return [
        (index, event)
        for index, event in enumerate(trace.events)
        if event.kind == "message" and (role is None or event.role == role)
    ]


def _prior_user_text(trace: Trace, index: int) -> str:
    return "\n".join(
        event.content or ""
        for event in trace.events[:index]
        if event.kind == "message" and event.role == "user"
    )


def _check(name: str, condition: bool, success: str, failure: str, *, blocking: bool = True) -> Check:
    return Check(name=name, passed=condition, detail=success if condition else failure, blocking=blocking)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _finish(case: EvalCase, checks: Iterable[Check], metrics: dict[str, float] | None = None,
            review_reasons: Iterable[str] = ()) -> Grade:
    values = tuple(checks)
    score = sum(item.passed for item in values) / len(values) if values else 1.0
    hard_pass = all(item.passed for item in values if item.blocking)
    passed = hard_pass and score >= case.pass_threshold
    return Grade(
        case_id=case.id,
        family=case.family,
        checks=values,
        score=score,
        passed=passed,
        blocking=case.blocking,
        metrics=metrics or {},
        review_reasons=tuple(review_reasons),
    )


def grade_above_max(case: EvalCase) -> Grade:
    maximum = float(case.fixture["max_rate"])
    calls = _calls(case.trace, "record_agreement")
    ordinary_over_max = [
        event for _, event in calls
        if (_as_float(event.arguments.get("agreed_price")) or 0) > maximum
        and not event.arguments.get("above_max", False)
    ]
    ordinary = [event for _, event in calls if not event.arguments.get("above_max", False)]
    above_max = [event for _, event in calls if event.arguments.get("above_max") is True]
    valid_bid = len(above_max) == 1 and all(
        above_max[0].arguments.get(field)
        for field in ("carrier_contact_name", "carrier_contact_phone")
    )
    quote_calls = _calls(case.trace, "submit_quote")
    end_reasons = [event.arguments.get("reason") for _, event in _calls(case.trace, "end_call")]
    checks = (
        _check("no_ordinary_agreement_above_max", not ordinary_over_max,
               "No ordinary agreement exceeded maxRate.",
               "An ordinary agreement was recorded above maxRate."),
        _check("no_ordinary_agreement", not ordinary,
               "No ordinary agreement was recorded for the above-max hold.",
               "An ordinary agreement was recorded even though the carrier held above maxRate."),
        _check("above_max_bid_with_contact", valid_bid,
               "One above-max bid included carrier name and phone.",
               "Expected exactly one above-max bid with carrier name and phone."),
        _check("no_quote_submission", not quote_calls,
               "No accepted quote was submitted.",
               "An above-max hold incorrectly submitted a quote."),
        _check("correct_end_reason", len(end_reasons) == 1 and end_reasons[0] in {"bid_placed", "no_agreement"},
               "Call ended as bid_placed or no_agreement.",
               f"Unexpected end reasons: {end_reasons!r}."),
    )
    return _finish(case, checks)


_ONES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_TEENS = ("ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _under_100(value: int) -> str:
    if value < 10:
        return _ONES[value]
    if value < 20:
        return _TEENS[value - 10]
    tens, ones = divmod(value, 10)
    return _TENS[tens] + ((" " + _ONES[ones]) if ones else "")


def _amount_forms(amount: float) -> set[str]:
    integer = int(amount)
    forms = {
        str(integer), f"{integer:,}", f"${integer}", f"${integer:,}",
        f"{amount:.2f}", f"${amount:.2f}",
    }
    if 1000 <= integer < 10000:
        high, low = divmod(integer, 100)
        freight = _under_100(high)
        if low:
            freight += " " + _under_100(low)
        forms.update({freight, freight.replace(" ", "-", 1)})
        thousands, remainder = divmod(integer, 1000)
        long_form = f"{_under_100(thousands)} thousand"
        if remainder:
            hundreds, tail = divmod(remainder, 100)
            if hundreds:
                long_form += f" {_ONES[hundreds]} hundred"
            if tail:
                long_form += f" {_under_100(tail)}"
        forms.add(long_form)
    return forms


def grade_confidentiality(case: EvalCase) -> Grade:
    assistant = "\n".join((event.content or "").lower() for _, event in _messages(case.trace, "assistant"))
    confidential = [float(case.fixture[key]) for key in ("target_rate", "max_rate")]
    leaked = sorted({form for amount in confidential for form in _amount_forms(amount) if form.lower() in assistant})
    phrases = [phrase for phrase in _FORBIDDEN_HEADROOM if phrase in assistant]
    checks = (
        _check("no_exact_confidential_amount", not leaked,
               "No exact target or maximum amount was spoken.",
               f"Confidential amount forms were spoken: {leaked!r}."),
        _check("no_headroom_hint", not phrases,
               "No prohibited headroom language was used.",
               f"Prohibited headroom phrases were used: {phrases!r}."),
    )
    review = ("LLM judge must review the trace for semantic pricing leaks.",)
    return _finish(case, checks, review_reasons=review)


def grade_standard_success(case: EvalCase) -> Grade:
    expected = float(case.fixture["agreed_price"])
    records = _calls(case.trace, "record_agreement")
    quotes = _calls(case.trace, "submit_quote")
    ends = _calls(case.trace, "end_call")
    record_index, record = records[0] if len(records) == 1 else (-1, Event("invalid"))
    prior_users = [
        event.content or "" for index, event in _messages(case.trace, "user")
        if index < record_index
    ]
    last_user = prior_users[-1] if prior_users else ""
    explicit = bool(_EXPLICIT_ACCEPTANCE.search(last_user)) and not bool(_AMBIGUOUS_ACCEPTANCE.search(last_user))
    args = record.arguments
    recorded_price = _as_float(args.get("agreed_price"))
    checks = (
        _check("one_agreement", len(records) == 1, "Exactly one agreement was recorded.",
               f"Expected one agreement call, found {len(records)}."),
        _check("explicit_acceptance", explicit, "Explicit acceptance preceded persistence.",
               "No explicit carrier acceptance preceded record_agreement."),
        _check("correct_price", recorded_price == expected,
               f"Agreement used the expected price ${expected:.0f}.",
               f"Agreement price {args.get('agreed_price')!r} did not equal ${expected:.0f}."),
        _check("contact_complete", bool(args.get("carrier_contact_name") and args.get("carrier_contact_phone")),
               "Agreement included carrier name and phone.",
               "Agreement did not include both carrier name and phone."),
        _check("one_quote", len(quotes) == 1 and (not records or quotes[0][0] > record_index),
               "Exactly one quote was submitted after persistence.",
               "Expected exactly one quote submission after the agreement."),
        _check("agreement_end", len(ends) == 1 and ends[0][1].arguments.get("reason") == "agreement"
               and (not quotes or ends[0][0] > quotes[0][0]),
               "Call ended once with agreement after quote submission.",
               "Expected end_call(agreement) after quote submission."),
    )
    return _finish(case, checks)


def grade_multi_round(case: EvalCase) -> Grade:
    offers = [float(value) for value in case.trace.metadata.get("agent_counter_offers", [])]
    carrier_bid = float(case.fixture["carrier_bid"])
    floor = float(case.fixture["carrier_floor"])
    agreed = float(case.fixture["agreed_price"])
    deltas = [later - earlier for earlier, later in zip(offers, offers[1:])]
    checks = (
        _check("two_to_three_counteroffers", 2 <= len(offers) <= 3,
               f"Agent made {len(offers)} counter-offers.",
               f"Expected 2-3 counter-offers, found {len(offers)}.", blocking=False),
        _check("increments_25_to_100", bool(deltas) and all(25 <= delta <= 100 for delta in deltas),
               "Counter-offer increments stayed between $25 and $100.",
               f"Invalid counter-offer increments: {deltas!r}.", blocking=False),
        _check("offers_only_move_up", all(delta > 0 for delta in deltas),
               "Counter-offers only moved upward.",
               f"Counter-offers did not move strictly upward: {offers!r}.", blocking=False),
        _check("never_above_carrier_bid", bool(offers) and all(offer <= carrier_bid for offer in offers),
               "No counter-offer exceeded the carrier's bid.",
               f"A counter-offer exceeded carrier bid ${carrier_bid:.0f}.", blocking=False),
        _check("not_above_max", agreed <= float(case.fixture["max_rate"]),
               "Agreement remained within maxRate.", "Agreement exceeded maxRate."),
    )
    return _finish(case, checks, metrics={"money_left_on_table": agreed - floor})


def grade_ambiguous_acceptance(case: EvalCase) -> Grade:
    failures: list[int] = []
    for index, _ in _calls(case.trace, "record_agreement"):
        prior_users = [event.content or "" for _, event in _messages(case.trace, "user") if _ < index]
        last = prior_users[-1] if prior_users else ""
        if not _EXPLICIT_ACCEPTANCE.search(last) or _AMBIGUOUS_ACCEPTANCE.search(last):
            failures.append(index)
    check = _check("record_only_after_explicit_acceptance", not failures,
                   "No agreement was recorded after an ambiguous reply.",
                   f"record_agreement followed ambiguous/non-accepting replies at events {failures}.")
    return _finish(case, (check,), review_reasons=("LLM judge should classify the preceding carrier reply.",))


def grade_missing_contact(case: EvalCase) -> Grade:
    record_calls = _calls(case.trace, "record_agreement")
    missing_name = [index for index, event in record_calls if not event.arguments.get("carrier_contact_name")]
    assistant = "\n".join(event.content or "" for _, event in _messages(case.trace, "assistant")).lower()
    asked = "name" in assistant or "contact" in assistant
    checks = (
        _check("asks_for_contact", asked, "Agent asked for missing contact details.",
               "Agent did not ask for missing contact details."),
        _check("no_record_without_name", not missing_name,
               "No agreement was recorded without a contact name.",
               f"Agreement calls without a contact name occurred at events {missing_name}."),
    )
    return _finish(case, checks)


def grade_carrier_verification(case: EvalCase) -> Grade:
    supplied = [str(value) for value in case.fixture.get("mc_numbers", [])]
    calls = [str(event.arguments.get("mc_number")) for _, event in _calls(case.trace, "verify_carrier")]
    results = _results(case.trace, "verify_carrier")
    misses = [index for index, event in results if event.result.get("status") == "not_found"]
    ends = _calls(case.trace, "end_call")
    lookup_claim_without_result = []
    seen_results = 0
    grounded_claims = 0
    for index, event in enumerate(case.trace.events):
        if event.kind == "tool_result" and event.name == "verify_carrier":
            seen_results += 1
        if event.kind == "message" and event.role == "assistant":
            is_claim = bool(event.metadata.get("lookup_claim")) or bool(_LOOKUP_CLAIM.search(event.content or ""))
            if is_claim:
                if grounded_claims >= seen_results:
                    lookup_claim_without_result.append(index)
                else:
                    grounded_claims += 1
    checks = [
        _check("lookup_each_mc", calls == supplied,
               "Each supplied MC was looked up exactly once and in order.",
               f"Supplied MCs {supplied!r}; lookup calls {calls!r}."),
        _check("no_unreturned_lookup_claim", not lookup_claim_without_result,
               "Every lookup claim was grounded in a tool result.",
               f"Ungrounded lookup claims occurred at events {lookup_claim_without_result}."),
    ]
    if case.fixture.get("expect_three_miss_end"):
        checks.append(_check(
            "third_miss_ends_call",
            len(misses) == 3 and len(ends) == 1 and ends[0][1].arguments.get("reason") == "mc_not_found" and ends[0][0] > misses[-1],
            "The third not-found result was followed by end_call(mc_not_found).",
            "Three misses did not end exactly once with mc_not_found.",
        ))
    expected_name = case.fixture.get("confirm_name")
    if expected_name:
        corrected_result_indexes = [
            index for index, event in results
            if event.result.get("status") == "success" and event.result.get("carrier_name") == expected_name
        ]
        confirmed = False
        if corrected_result_indexes:
            confirmed = any(
                index > corrected_result_indexes[-1]
                and expected_name.lower() in (event.content or "").lower()
                and "?" in (event.content or "")
                for index, event in _messages(case.trace, "assistant")
            )
        checks.append(_check("corrected_name_confirmation", confirmed,
                             "Agent asked the caller to confirm the corrected carrier name.",
                             "Agent did not confirm the corrected carrier name after re-verification."))
    return _finish(case, checks)


def grade_load_presentation(case: EvalCase) -> Grade:
    results = [item for item in _results(case.trace, "get_load_context") if item[1].result.get("status") == "success"]
    first_reply = ""
    if results:
        result_index = results[-1][0]
        first_reply = next(
            (event.content or "" for index, event in _messages(case.trace, "assistant") if index > result_index), ""
        )
    lowered = first_reply.lower()
    required = {
        "pickup_location": str(case.fixture["pickup_location"]),
        "pickup_time": str(case.fixture["pickup_time"]),
        "delivery_location": str(case.fixture["delivery_location"]),
    }
    instructions = case.fixture.get("special_instructions")
    if instructions:
        required["special_instructions"] = str(instructions)
    checks = [
        _check(
            f"includes_{name}", value.lower() in lowered,
            f"First load reply included {name.replace('_', ' ')}.",
            f"First load reply omitted {name.replace('_', ' ')}: {value!r}.",
            blocking=False,
        )
        for name, value in required.items()
    ]
    spoken_amounts = [float(value.replace(",", "")) for value in _MONEY.findall(first_reply)]
    opening_rate = float(case.fixture["opening_rate"])
    checks.append(_check(
        "includes_opening_rate", opening_rate in spoken_amounts,
        "First load reply included opening rate.",
        f"First load reply omitted opening rate: {opening_rate:.0f}.",
        blocking=False,
    ))
    return _finish(case, checks, review_reasons=("LLM judge should flag claims absent from the fixture.",))


def grade_human_transfer(case: EvalCase) -> Grade:
    load_results = [index for index, event in _results(case.trace, "get_load_context") if event.result.get("status") == "success"]
    transfers = _calls(case.trace, "transfer_to_human")
    ends = _calls(case.trace, "end_call")
    expected = bool(case.fixture["transfer_expected"])
    after_load = bool(transfers and load_results and all(index > load_results[-1] for index, _ in transfers))
    checks = (
        _check("transfer_expectation", (len(transfers) == 1) if expected else not transfers,
               "Transfer behavior matched the scenario.",
               f"Expected transfer={expected}, observed {len(transfers)} transfer calls."),
        _check("transfer_after_load", not transfers or after_load,
               "Transfer occurred only after a successful load lookup.",
               "Transfer occurred before a successful load lookup."),
        _check("no_end_after_transfer", not transfers or not any(index > transfers[-1][0] for index, _ in ends),
               "Bot did not call end_call after transfer.",
               "Bot called end_call after transfer."),
    )
    return _finish(case, checks, review_reasons=("LLM judge should determine whether the transfer was warranted.",))


GRADERS: dict[str, Callable[[EvalCase], Grade]] = {
    "above_max": grade_above_max,
    "confidentiality": grade_confidentiality,
    "standard_success": grade_standard_success,
    "multi_round": grade_multi_round,
    "ambiguous_acceptance": grade_ambiguous_acceptance,
    "missing_contact": grade_missing_contact,
    "carrier_verification": grade_carrier_verification,
    "load_presentation": grade_load_presentation,
    "human_transfer": grade_human_transfer,
}


def grade_case(case: EvalCase) -> Grade:
    try:
        grader = GRADERS[case.grader]
    except KeyError as exc:
        raise ValueError(f"unknown grader {case.grader!r} for case {case.id!r}") from exc
    return grader(case)

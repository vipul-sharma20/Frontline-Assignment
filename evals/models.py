"""Dependency-free data model for evaluation cases, traces, and grades."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    """One ordered observation in a simulated call."""

    kind: str
    role: str | None = None
    content: str | None = None
    name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Event":
        allowed = {
            "kind", "role", "content", "name", "arguments", "result", "metadata"
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown event fields: {sorted(unknown)}")
        return cls(**value)


@dataclass(frozen=True)
class Trace:
    case_id: str
    events: tuple[Event, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Trace":
        return cls(
            case_id=str(value["case_id"]),
            events=tuple(Event.from_dict(event) for event in value["events"]),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalCase:
    id: str
    family: str
    description: str
    grader: str
    fixture: dict[str, Any]
    trace: Trace
    blocking: bool = True
    pass_threshold: float = 1.0
    family_pass_threshold: float = 1.0
    judge_criteria: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvalCase":
        required = {"id", "family", "description", "grader", "fixture", "trace"}
        missing = required - set(value)
        if missing:
            raise ValueError(f"case missing required fields: {sorted(missing)}")
        case_id = str(value["id"])
        trace = Trace.from_dict(value["trace"])
        if trace.case_id != case_id:
            raise ValueError(
                f"case id {case_id!r} does not match trace id {trace.case_id!r}"
            )
        threshold = float(value.get("pass_threshold", 1.0))
        if not 0 <= threshold <= 1:
            raise ValueError("pass_threshold must be between 0 and 1")
        family_threshold = float(value.get("family_pass_threshold", 1.0))
        if not 0 <= family_threshold <= 1:
            raise ValueError("family_pass_threshold must be between 0 and 1")
        return cls(
            id=case_id,
            family=str(value["family"]),
            description=str(value["description"]),
            grader=str(value["grader"]),
            fixture=dict(value["fixture"]),
            trace=trace,
            blocking=bool(value.get("blocking", True)),
            pass_threshold=threshold,
            family_pass_threshold=family_threshold,
            judge_criteria=tuple(value.get("judge_criteria", ())),
        )


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str
    blocking: bool = True


@dataclass(frozen=True)
class Grade:
    case_id: str
    family: str
    checks: tuple[Check, ...]
    score: float
    passed: bool
    blocking: bool
    metrics: dict[str, float] = field(default_factory=dict)
    review_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

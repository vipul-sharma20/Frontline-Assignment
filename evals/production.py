"""Read the production prompt and tool contracts without starting runtime services."""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = ROOT / "voice-agent"
SHARED_SRC = ROOT / "shared" / "src"


@dataclass(frozen=True)
class ProductionContract:
    initial_prompt: Callable[..., str]
    negotiation_prompt: Callable[[dict[str, Any]], str]
    tools: tuple[dict[str, Any], ...]


def _literal_keyword(call: ast.Call, name: str, default: Any = None) -> Any:
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.literal_eval(keyword.value)
    return default


def _load_tools() -> tuple[dict[str, Any], ...]:
    source = (VOICE_DIR / "tool_definitions.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    tools: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        function = node.value.func
        if not isinstance(function, ast.Name) or function.id != "FunctionSchema":
            continue
        name = _literal_keyword(node.value, "name")
        if not name:
            continue
        properties = _literal_keyword(node.value, "properties", {})
        required = _literal_keyword(node.value, "required", [])
        tools.append(
            {
                "type": "function",
                "name": name,
                "description": _literal_keyword(node.value, "description", ""),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
                "strict": True,
            }
        )
    if not tools:
        raise RuntimeError("no production tool definitions could be parsed")
    return tuple(tools)


def _load_prompt_module():
    """Load the prompt only, bypassing shared/src/__init__.py service imports."""
    package = types.ModuleType("src")
    package.__path__ = [str(SHARED_SRC)]  # type: ignore[attr-defined]
    previous_package = sys.modules.get("src")
    previous_shared = sys.modules.get("src.negotiation_prompt")
    previous_voice = sys.modules.get("evals._production_voice_prompt")
    try:
        sys.modules["src"] = package
        shared_spec = importlib.util.spec_from_file_location(
            "src.negotiation_prompt", SHARED_SRC / "negotiation_prompt.py"
        )
        if shared_spec is None or shared_spec.loader is None:
            raise RuntimeError("could not load shared negotiation prompt")
        shared_module = importlib.util.module_from_spec(shared_spec)
        sys.modules["src.negotiation_prompt"] = shared_module
        shared_spec.loader.exec_module(shared_module)

        voice_spec = importlib.util.spec_from_file_location(
            "evals._production_voice_prompt", VOICE_DIR / "voice_prompt.py"
        )
        if voice_spec is None or voice_spec.loader is None:
            raise RuntimeError("could not load voice prompt")
        voice_module = importlib.util.module_from_spec(voice_spec)
        sys.modules["evals._production_voice_prompt"] = voice_module
        voice_spec.loader.exec_module(voice_module)
        return voice_module
    finally:
        if previous_package is None:
            sys.modules.pop("src", None)
        else:
            sys.modules["src"] = previous_package
        if previous_shared is None:
            sys.modules.pop("src.negotiation_prompt", None)
        else:
            sys.modules["src.negotiation_prompt"] = previous_shared
        if previous_voice is None:
            sys.modules.pop("evals._production_voice_prompt", None)
        else:
            sys.modules["evals._production_voice_prompt"] = previous_voice


def load_production_contract() -> ProductionContract:
    module = _load_prompt_module()
    contract = ProductionContract(
        initial_prompt=module.get_initial_greeting_prompt,
        negotiation_prompt=module.build_full_negotiation_prompt,
        tools=_load_tools(),
    )
    names = {tool["name"] for tool in contract.tools}
    expected = {
        "verify_carrier", "get_load_context", "record_agreement", "end_call",
        "transfer_to_human", "transfer_human_to_carrier",
    }
    missing = expected - names
    if missing:
        raise RuntimeError(f"production contract is missing tools: {sorted(missing)}")
    initial = contract.initial_prompt("Evaluation Brokerage")
    if "verify_carrier" not in initial or "get_load_context" not in initial:
        raise RuntimeError("production initial prompt is missing required tool guidance")
    return contract

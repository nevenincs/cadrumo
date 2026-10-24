"""Produce the Rust test input that pins the Modelo host to the shipped contracts.

It lists every ``modelo.*`` definition in the shipped operation contract
manifest with what the host must know to submit it without restating its
request: whether it may write, whether it pauses for a review, whether it takes
a transient financial operand, which form its subject takes, whether its
request names the profile, and which of its request fields name a local file.
It also records the request line bound of the held person's relay.
Request fields are read from the registered request models through the eager
production registry, so a field that starts naming a file cannot reach the
window unnoticed. Run with the repository Python environment; --check detects
drift from the manifest, the request models or the relay.
"""

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

_WRITING_EFFECTS = frozenset({"updated", "partial"})
_FAMILY = "modelo."


def _module_constant(module: str, name: str) -> int:
    """Read one module-level integer assignment from the module's source, without importing it."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        raise SystemExit(f"{module} has no source")
    source = Path(spec.origin).read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        value = getattr(node, "value", None)
        if (
            isinstance(target, ast.Name)
            and target.id == name
            and isinstance(value, ast.Constant)
            and type(value.value) is int
        ):
            return value.value
    raise SystemExit(f"{name} is not a module-level integer")


def _names_file(schema: dict[str, object]) -> bool:
    if schema.get("format") == "path":
        return True
    members = schema.get("anyOf")
    return isinstance(members, list) and any(isinstance(m, dict) and _names_file(m) for m in members)


def _optional(schema: dict[str, object]) -> bool:
    members = schema.get("anyOf")
    return isinstance(members, list) and any(isinstance(m, dict) and m.get("type") == "null" for m in members)


def _request_facts(request_type: type[BaseModel]) -> dict[str, object]:
    """The request fields the host fills or substitutes, read from the registered model."""
    schema = request_type.model_json_schema()
    properties: dict[str, dict[str, object]] = schema.get("properties", {})
    required = set(schema.get("required", []))
    files: dict[str, str] = {}
    for name, field in properties.items():
        if name.endswith("_path") or _names_file(field):
            files[name] = "optional" if name not in required or _optional(field) else "one"
    return {
        "profile_field": "profile_id" in properties,
        "bucket_field": "bucket_id" in properties,
        "file_fields": dict(sorted(files.items())),
    }


def documents() -> dict[str, object]:
    """The Modelo family's contract facts and the relay's request line bound."""
    manifest = load_operation_contract_manifest()
    requests = {
        definition.definition_id: definition.request_type
        for definition in build_production_operation_registry().definitions
        if definition.definition_id.startswith(_FAMILY)
    }
    operations: dict[str, object] = {}
    for entry in manifest.operations:
        contract = entry.contract
        if not contract.definition_id.startswith(_FAMILY):
            continue
        effects = {effect.value for effect in contract.permitted_effects}
        subject = contract.subject_reference
        operations[contract.definition_id] = {
            "may_write": bool(effects & _WRITING_EFFECTS),
            "review": any(kind.value == "review" for kind in contract.interaction_kinds),
            "financial": contract.transient_financial_operand is not None,
            "subject": {"kind": subject.kind.value, "path": list(subject.payload_path)},
            **_request_facts(requests[contract.definition_id]),
        }
    return {
        "operations": operations,
        "relay": {
            "request_line_limit": _module_constant("cadrumo_runtime.host.session_hold", "_MAXIMUM_REQUEST_LINE_BYTES"),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).with_suffix(".json")
    rendered = json.dumps(documents(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Modelo relay contracts are stale; regenerate before running the Rust Modelo tests")
        sys.stdout.write("Modelo relay contracts match the shipped manifest, request models and relay\n")
    else:
        target.write_text(rendered, encoding="utf-8", newline="\n")

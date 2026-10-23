"""Produce the Rust test input that pins the ledger host to the shipped contracts.

It lists every ``ledger.*`` definition in the shipped operation contract
manifest, with whether it may write and whether it pauses for a review, and the
two bounds the held person's relay applies to one request. It also checks
that the window's mirror of the admitted list, ``LEDGER_DEFINITIONS`` in the
frontend's ``src/shell/ledger.ts``, names the same definitions. Run with the
repository Python environment; --check detects drift from the manifest or the
relay. No runtime, profile or application build is required.
"""

import argparse
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest

_WRITING_EFFECTS = frozenset({"updated", "partial"})
_FRONTEND_MIRROR = Path(__file__).resolve().parents[4] / "frontend" / "src" / "shell" / "ledger.ts"
_MIRROR_LIST = re.compile(r"export const LEDGER_DEFINITIONS = \[(?P<ids>[^\]]*)\] as const;")


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


def documents() -> dict[str, object]:
    """The ledger family's contract facts and the relay's request bounds."""
    manifest = load_operation_contract_manifest()
    operations: dict[str, object] = {}
    for entry in manifest.operations:
        contract = entry.contract
        if not contract.definition_id.startswith("ledger."):
            continue
        effects = {effect.value for effect in contract.permitted_effects}
        operations[contract.definition_id] = {
            "may_write": bool(effects & _WRITING_EFFECTS),
            "review": any(kind.value == "review" for kind in contract.interaction_kinds),
        }
    return {
        "operations": operations,
        "relay": {
            "payload_text_limit": _module_constant("cadrumo_runtime.host.session_hold_operations", "_MAX_PAYLOAD_TEXT"),
            "request_line_limit": _module_constant("cadrumo_runtime.host.session_hold", "_MAXIMUM_REQUEST_LINE_BYTES"),
        },
    }


def _check_frontend_mirror(operations: object) -> None:
    """Refuse a window that would name a definition the host does not admit, or miss one."""
    found = _MIRROR_LIST.search(_FRONTEND_MIRROR.read_text(encoding="utf-8"))
    if found is None:
        raise SystemExit(f"{_FRONTEND_MIRROR} declares no LEDGER_DEFINITIONS list")
    mirrored = re.findall(r'"([^"]+)"', found.group("ids"))
    if not isinstance(operations, dict) or mirrored != sorted(operations):
        raise SystemExit("The frontend's LEDGER_DEFINITIONS differ from the shipped ledger family")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).with_suffix(".json")
    produced = documents()
    _check_frontend_mirror(produced["operations"])
    rendered = json.dumps(produced, indent=2, sort_keys=True) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Ledger relay contracts are stale; regenerate before running the Rust ledger tests")
        sys.stdout.write("Ledger relay contracts match the shipped manifest and relay\n")
    else:
        target.write_text(rendered, encoding="utf-8", newline="\n")

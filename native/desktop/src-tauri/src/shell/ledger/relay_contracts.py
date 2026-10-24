"""Produce the Rust test input that pins the ledger host to the shipped contracts.

It lists every ``ledger.*`` definition in the shipped operation contract
manifest, with whether it may write and whether it pauses for a review. The
request bounds are the native relay's own constants, which the host reads
directly. It also checks that the window's mirror of the admitted list,
``LEDGER_DEFINITIONS`` in the frontend's ``src/shell/ledger.ts``, names the
same definitions. Run with the repository Python environment; --check detects
drift from the manifest or the mirror. No runtime, profile or application
build is required.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest

_WRITING_EFFECTS = frozenset({"updated", "partial"})
_FRONTEND_MIRROR = Path(__file__).resolve().parents[4] / "frontend" / "src" / "shell" / "ledger.ts"
_MIRROR_LIST = re.compile(r"export const LEDGER_DEFINITIONS = \[(?P<ids>[^\]]*)\] as const;")


def documents() -> dict[str, object]:
    """The ledger family's contract facts."""
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
    return {"operations": operations}


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
        sys.stdout.write("Ledger relay contracts match the shipped manifest and the window's mirror\n")
    else:
        target.write_text(rendered, encoding="utf-8", newline="\n")

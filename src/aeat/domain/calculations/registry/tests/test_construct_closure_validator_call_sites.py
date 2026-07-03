"""Production call-site guard for construct closure evidence validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .. import __file__ as registry_package_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_production_construct_closure_calls_pass_evidence_keyword() -> None:
    """Every production call to ``validate_construct_closure`` supplies evidence.

    The construct validator enforces schema-independent evidence requirements.
    A signature change must therefore fail at the call-site contract, not fall
    through to a public CLI TypeError when the registry validates during a blank
    ledger calculation.
    """

    registry_root = Path(registry_package_file).parent
    missing_evidence: list[str] = []
    for path in sorted(registry_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "validate_construct_closure":
                continue
            if not any(keyword.arg == "evidence" for keyword in node.keywords):
                missing_evidence.append(f"{path.name}:{node.lineno}")

    assert not missing_evidence, "validate_construct_closure calls missing evidence=: " + ", ".join(missing_evidence)

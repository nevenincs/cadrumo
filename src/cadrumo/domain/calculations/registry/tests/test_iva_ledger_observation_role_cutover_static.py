"""Static completeness gate for the explicit IVA ledger observation role cutover."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CADRUMO_ROOT = Path(__file__).parents[4]
_MODELOS_ROOT = _CADRUMO_ROOT / "_data" / "registry" / "aeat" / "modelos"
_INFORMATIONAL_BINDING_IDS = frozenset(
    {
        "modelo-303-criterio-caja-entregas-art75-base",
        "modelo-303-criterio-caja-entregas-art75-cuota",
        "modelo-303-criterio-caja-adquisiciones-base",
        "modelo-303-criterio-caja-adquisiciones-cuota",
    }
)
_MONETARY_TREATMENTS = ["none", "taxpayer_regime", "supplier_regime"]


def _constructor_calls(name: str) -> Iterator[tuple[str, ast.Call]]:
    for path in scan_directory(_CADRUMO_ROOT, pattern="*.py", recursive=True):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_path = path.relative_to(_CADRUMO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            constructor_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            if constructor_name == name:
                yield relative_path, node


def _binding_records(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        record: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            record[key] = child
        if record.get("source") == "ledger_iva_aggregation":
            yield record
        for child in value.values():
            yield from _binding_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _binding_records(child)


def test_direct_iva_ledger_constructors_declare_the_required_role() -> None:
    """Every direct construction states the role; none may inherit an implicit default.

    Non-vacuity is proved by requiring the production module that owns each
    constructor to appear in the scan, rather than by pinning a call tally: a
    tally encodes one moment, and the only way past it is to bump the constant.
    """
    # Only IvaLedgerObservation has a production construction site to anchor on;
    # IvaLedgerCandidate is built solely by the aggregation tests, so its
    # non-vacuity guard is that the scan found any construction at all.
    production_anchors = {"IvaLedgerObservation": "application/aggregation/_iva_ledger.py"}

    for name in ("IvaLedgerObservation", "IvaLedgerCandidate"):
        calls = tuple(_constructor_calls(name))
        missing = [
            f"{relative_path}:{call.lineno}"
            for relative_path, call in calls
            if not any(keyword.arg == "observation_role" for keyword in call.keywords)
        ]
        assert calls, f"the {name} scan found no construction at all"
        anchor = production_anchors.get(name)
        if anchor is not None:
            assert any(relative_path == anchor for relative_path, _ in calls), (
                f"the {name} scan never reached its production site {anchor}"
            )
        assert missing == [], f"{name} constructed without an explicit observation_role at {missing}"


def test_every_ledger_iva_aggregation_selector_declares_role_and_treatment() -> None:
    bindings = tuple(
        binding
        for path in scan_directory(_MODELOS_ROOT, pattern="*.toml", recursive=True)
        for binding in _binding_records(tomllib.loads(path.read_text(encoding="utf-8")))
    )

    assert bindings, "no ledger_iva_aggregation binding was scanned"

    informational = []
    for binding in bindings:
        binding_id = binding["id"]
        assert isinstance(binding_id, str)
        selector = binding["selector"]
        assert isinstance(selector, dict)
        assert "observation_roles" in selector
        assert "cash_accounting_treatments" in selector
        if binding_id in _INFORMATIONAL_BINDING_IDS:
            informational.append(binding_id)
            assert selector["observation_roles"] == ["operation_informational"]
        else:
            assert selector["observation_roles"] == ["settlement"]
            assert selector["cash_accounting_treatments"] == _MONETARY_TREATMENTS

    # The four informational binding ids recur once per revision, so the
    # meaningful property is that the set found is exactly the declared set --
    # every named id is really carried, and no other id claimed the role.
    assert set(informational) == _INFORMATIONAL_BINDING_IDS

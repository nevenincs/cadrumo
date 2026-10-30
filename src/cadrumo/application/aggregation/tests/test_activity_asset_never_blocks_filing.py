"""No reason the activity-asset register raises refuses checking, exporting or recording a declaration.

The reasons are read from the modules that raise them, so a new one is held to
this without being listed here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...modelo.calculation_notes import BLOCKING_REASONS, GATE_REFUSED_REASONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AGGREGATION = Path(__file__).resolve().parents[1]
_RAISING_MODULES = (
    *sorted(_AGGREGATION.glob("*actividad_asset*.py")),
    *sorted(_AGGREGATION.glob("*activity_asset*.py")),
)


def _raised_reasons(path: Path) -> frozenset[str]:
    return frozenset(
        node.value.value
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.keyword)
        and node.arg == "reason"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def test_no_reason_asset_data_raises_is_one_the_application_refuses_filing_on() -> None:
    raised = frozenset().union(*(_raised_reasons(path) for path in _RAISING_MODULES))

    assert "ledger_amortization_row_unregistered" in raised
    assert "activity_asset_foral_territory" in raised
    assert "activity_asset_residence_unresolved" in raised
    assert raised & GATE_REFUSED_REASONS == frozenset()
    assert raised & BLOCKING_REASONS == frozenset()


def test_the_scan_sees_a_reason_named_at_its_raising_call(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text('note(reason="unresolved_binding", source_kind=kind)\nnote(reason=variable)\n', encoding="utf-8")

    assert _raised_reasons(module) == {"unresolved_binding"}

"""The table's checks of a written fichero find a clean file clean and each defect, and the CLI column runs them."""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Mapping, Sequence
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import render_absent_slot, render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import ExpectedObligation, ExpectedValue, Persona, YearToken, persona_ids

from ..cli_column.__main__ import build_case, export_check_for
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter, Outcome
from ..cli_column.world_report import RowPlan, WorldReport
from ..export_check import export_layout, export_readback_reason, export_reason, export_text_reason
from ..planner import last_owed_period, owed_periods, persona_under_horizon
from ..rows import PlannedRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "130"
_PERIOD = "1T"


@cache
def _year() -> int:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation).horizon - 1


def _plan() -> PlannedRow:
    return PlannedRow(
        persona="synthetic",
        modelo=_MODELO,
        year=_year(),
        period=_PERIOD,
        horizon=_year() + 1,
        has_values=True,
        grounding="verified",
        sources=(),
    )


@cache
def _layout() -> ExportLayoutDefinition:
    with bundled_indexed_authority().operation() as operation:
        return export_layout(operation, _plan())


def _carried() -> str:
    return next(str(f.casilla_id) for r in _layout().records for f in r.fields if f.casilla_id is not None)


def _piece(field: ExportFieldDefinition, bound: Mapping[str, Decimal]) -> str:
    if field.literal is not None:
        return field.literal
    if field.casilla_id is not None and str(field.casilla_id) in bound:
        return render_fixed_width_export_field(field, bound[str(field.casilla_id)])
    return render_absent_slot(field)


def _fichero(bound: Mapping[str, Decimal]) -> bytes:
    record = _layout().records[0]
    text = [" "] * max((f.offset or 0) - 1 + (f.length or 0) for f in record.fields)
    for field in record.fields:
        assert field.offset is not None
        assert field.length is not None
        text[field.offset - 1 : field.offset - 1 + field.length] = list(_piece(field, bound))
    envelope = _layout().filing_envelope
    assert envelope is not None
    tag = f"<DR{_MODELO}0{_year()}{_PERIOD}".encode("ascii")[: envelope.opening_tag_extent]
    tag = tag.ljust(envelope.opening_tag_extent)
    return tag.ljust(envelope.prefix_extent) + "".join(text).encode("iso-8859-1") + envelope.closer_for(tag)


def _stated(casilla: str, amount: str) -> ExpectedValue:
    return ExpectedValue(
        modelo=_MODELO,
        period=_PERIOD,
        year=YearToken(anchor="horizon", offset=-1),
        counterparty=None,
        casillas=((casilla, amount),),
        roles=(),
        concepts=(),
        parameters=(),
        derivation=None,
        legal_ref=("rd-439-2007:art-110",),
        grounding="verified",
        reason=None,
    )


def _written(tmp_path: Path, payload: bytes) -> Path:
    output = tmp_path / "fichero.txt"
    output.write_bytes(payload)
    return output


def test_a_clean_file_that_carries_the_stated_value_has_no_reason(tmp_path: Path) -> None:
    casilla = _carried()
    output = _written(tmp_path, _fichero({casilla: Decimal("812.40")}))
    values = [_stated(casilla, "812.40")]
    assert export_text_reason(_plan(), output) == ""
    assert export_readback_reason(_plan(), values, output) == ""
    assert export_reason(_plan(), values, output) == ""


def test_a_stated_value_the_file_gives_differently_is_the_reason(tmp_path: Path) -> None:
    casilla = _carried()
    output = _written(tmp_path, _fichero({casilla: Decimal("812.41")}))
    values = [_stated(casilla, "812.40")]
    expected = f"export readback: c{casilla} exp 812.40 got 812.41"
    assert export_readback_reason(_plan(), values, output) == expected
    assert export_reason(_plan(), values, output) == expected


def test_a_byte_the_design_refuses_is_the_reason_before_the_readback(tmp_path: Path) -> None:
    casilla = _carried()
    output = _written(tmp_path, _fichero({casilla: Decimal("812.41")}) + b"\xff")
    reason = export_text_reason(_plan(), output)
    assert reason
    assert export_reason(_plan(), [_stated(casilla, "812.40")], output) == reason


def _persona(*obligations: tuple[str, tuple[str, ...]]) -> Persona:
    base = persona_under_horizon(persona_ids()[0], _year() + 1)
    items = tuple(
        ExpectedObligation(
            modelo=modelo,
            periods=periods,
            year=YearToken(anchor="horizon", offset=-1),
            applicable=True,
            reason="synthetic",
            legal_ref=("rd-439-2007:art-110",),
            grounding="verified",
        )
        for modelo, periods in obligations
    )
    return dataclasses.replace(base, expectations=dataclasses.replace(base.expectations, obligations=items))


def test_the_last_owed_period_is_the_last_quarter_of_the_modelo_else_the_returns_own() -> None:
    plan = _plan()
    persona = _persona((_MODELO, ("1T", "3T", "2T")), ("303", ("4T",)))
    assert owed_periods(persona, plan) == {"1T", "2T", "3T"}
    assert last_owed_period(persona, plan) == "3T"
    annual = _persona((_MODELO, ("0A",)), ("303", ("4T",)))
    assert last_owed_period(annual, plan) == _PERIOD
    other = _persona(("303", ("4T",)))
    assert owed_periods(other, plan) == {_PERIOD}
    assert last_owed_period(other, plan) == _PERIOD


class _Idle:
    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object] | None:
        raise AssertionError("construction sends no command")


def _no_trace(_label: str, _outcome: Outcome) -> None:
    return None


def test_the_cli_column_hands_the_driver_the_tables_export_check(tmp_path: Path) -> None:
    report = WorldReport(
        persona="synthetic",
        horizon=_year() + 1,
        storage_root="root",
        profile_id="id",
        authority_generation="gen",
        as_of="instant",
        scope="full",
        actor="operator:test",
        aeat_filings_in_process=False,
        needs_statements=False,
        rows=(),
    )
    writer = LineWriter(tmp_path / "cli-t.jsonl", Redactor(["synthetic-persona-passphrase"]))
    args = argparse.Namespace(tree="t", persona="synthetic", horizon=_year() + 1)
    case = build_case(
        args, report=report, runner=_Idle(), exports=tmp_path, writer=writer, log="case.log", trace=_no_trace
    )
    assert case.export_check is not None


def test_a_return_the_replay_does_not_plan_leaves_the_export_checks_unavailable(tmp_path: Path) -> None:
    check = export_check_for(persona_ids()[0], _year() + 1)
    unplanned = RowPlan("000", _year(), "1T", True, True, False, "1T")
    assert check(unplanned, tmp_path / "absent.txt") is None

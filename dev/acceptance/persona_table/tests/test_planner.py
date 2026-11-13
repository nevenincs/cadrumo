"""The planner imports without side effect, states a return's statements in the table's order, and names sources."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculateRequest
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.entrypoints.tests.persona_materialisation import PERSONA_ACTOR, MaterialisedPersona, PersonaWorld

from .. import planner, sweep
from ..rows import PlannedRow, Stage, TableRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
"""Any year: the statements under test do not read the registry envelope."""
_PROFILE = UUID(int=1)
_UNIT = "c" * 64
_IMPORT_SECONDS = 120


def _plan(modelo: str, period: str, *, sources_returns: tuple[str, ...] = ()) -> PlannedRow:
    return PlannedRow(
        persona="synthetic",
        modelo=modelo,
        year=_YEAR,
        period=period,
        horizon=_YEAR,
        has_values=False,
        grounding="none",
        sources=(),
        sources_returns=sources_returns,
    )


def _opaque(value: object) -> object:
    """The value as a plain object, which a test stand-in is cast from."""
    return value


def _materialised(modelo: str, periods: tuple[str, ...], filings: dict[str, str] | None = None) -> MaterialisedPersona:
    obligations = [SimpleNamespace(modelo=modelo, periods=periods)]
    world = cast(PersonaWorld, _opaque(SimpleNamespace(profile_id=_PROFILE)))
    held = SimpleNamespace(
        persona=SimpleNamespace(expectations=SimpleNamespace(obligations=obligations)),
        world=world,
        filings=filings or {},
    )
    return cast(MaterialisedPersona, _opaque(held))


def _record(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace each operation the statements call with a recorder, so only the order under test runs."""
    calls: list[str] = []

    def prior_carries(_persona: object, _world: object, work_unit_id: str, year: int) -> None:
        calls.append(f"prior_carries {work_unit_id} {year}")

    def before_first(_world: object, *, modelo: str, year: int, period: str, work_unit_id: str) -> None:
        calls.append(f"before_first {modelo} {year} {period} {work_unit_id}")

    def operation(_world: object, definition_id: str, request: object, _result: object, *, subject: str) -> object:
        calls.append(f"operation {definition_id} {subject}")
        assert getattr(request, "work_unit_id", None) == _UNIT
        return SimpleNamespace(attachment_id="a" * 64, sha256="b" * 64)

    monkeypatch.setattr(planner, "attest_prior_carries", prior_carries)
    monkeypatch.setattr(planner, "attest_before_first_calculation", before_first)
    monkeypatch.setattr(planner, "run_operation", operation)
    monkeypatch.setattr(planner, "_create", lambda _world, _plan: _UNIT)
    return calls


def _attestation(calls: list[str]) -> str:
    return next(call for call in calls if call.startswith("operation "))


async def _import_in_fresh_interpreter(authority_root: Path) -> tuple[int, str, float]:
    """Import the planner alone in a new interpreter: its exit status, its stderr and the seconds it took."""
    code = (
        "import sys; import dev.acceptance.persona_table.planner; "
        "sys.exit(1 if 'dev.acceptance.persona_table.sweep' in sys.modules else 0)"
    )
    started = time.monotonic()
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        env={**os.environ, "CADRUMO_AUTHORITY_ROOT": str(authority_root)},
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(child.communicate(), timeout=_IMPORT_SECONDS)
    return child.returncode or 0, stderr.decode(errors="replace")[-2000:], time.monotonic() - started


def test_importing_the_planner_builds_no_plan_and_reads_no_authority(tmp_path: Path) -> None:
    empty = tmp_path / "empty-authority"
    empty.mkdir()
    status, stderr, seconds = asyncio.run(_import_in_fresh_interpreter(empty))
    assert status == 0, stderr
    assert seconds < _IMPORT_SECONDS


def test_a_return_that_is_not_a_303_states_its_carries_then_its_prior_figures_and_no_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    materialised = _materialised("100", ("0A",))
    plan = _plan("100", "0A")
    planner.state_before_first_calculation(materialised, plan, _UNIT)
    assert calls == [f"prior_carries {_UNIT} {_YEAR}", f"before_first 100 {_YEAR} 0A {_UNIT}"]
    request = planner.build_calculation_request(materialised, plan, _UNIT)
    assert calls == [f"prior_carries {_UNIT} {_YEAR}", f"before_first 100 {_YEAR} 0A {_UNIT}"]
    assert request == ModeloWorkCalculateRequest(
        work_unit_id=_UNIT, actor=PERSONA_ACTOR, ordinary_m303_filing_evidence=None
    )


def test_the_first_step_alone_makes_no_390_attestation_for_a_303_and_the_second_makes_it_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    materialised = _materialised("303", ("1T", "2T", "3T", "4T"))
    plan = _plan("303", "4T")
    planner.state_before_first_calculation(materialised, plan, _UNIT)
    assert calls == [f"before_first 303 {_YEAR} 4T {_UNIT}"]
    request = planner.build_calculation_request(materialised, plan, _UNIT)
    assert len(calls) == 2
    assert _attestation(calls).endswith(f" {_UNIT}")
    evidence = request.ordinary_m303_filing_evidence
    assert evidence is not None
    assert evidence.m303_exonerado_390_attachment_id == "a" * 64


def test_a_303_before_its_last_period_attests_nothing_and_elects_no_joint_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record(monkeypatch)
    request = planner.build_calculation_request(
        _materialised("303", ("1T", "2T", "3T", "4T")), _plan("303", "2T"), _UNIT
    )
    assert calls == []
    evidence = request.ordinary_m303_filing_evidence
    assert evidence is not None
    assert evidence.joint_return_elected is False
    assert evidence.m303_exonerado_390_attachment_id is None


@pytest.mark.parametrize(
    ("modelo", "period", "periods", "expected"),
    [
        ("100", "0A", ("0A",), [f"prior_carries {_UNIT} {_YEAR}", f"before_first 100 {_YEAR} 0A {_UNIT}"]),
        ("303", "4T", ("1T", "4T"), [f"before_first 303 {_YEAR} 4T {_UNIT}", "attestation"]),
        ("130", "2T", ("2T",), [f"before_first 130 {_YEAR} 2T {_UNIT}"]),
    ],
)
def test_preparing_a_return_makes_the_same_calls_in_the_same_order_as_the_two_steps(
    monkeypatch: pytest.MonkeyPatch, modelo: str, period: str, periods: tuple[str, ...], expected: list[str]
) -> None:
    calls = _record(monkeypatch)
    materialised = _materialised(modelo, periods)
    plan = _plan(modelo, period)
    prepared = planner.prepare_return(materialised, plan, [])
    assert isinstance(prepared, planner.PreparedReturn)
    assert prepared.work_unit_id == _UNIT
    shape = ["attestation" if call.startswith("operation ") else call for call in calls]
    assert shape == expected
    stepped = _record(monkeypatch)
    planner.state_before_first_calculation(materialised, plan, _UNIT)
    request = planner.build_calculation_request(materialised, plan, _UNIT)
    assert stepped == calls
    assert request == prepared.request


def test_a_return_the_history_filed_makes_no_statement(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record(monkeypatch)
    plan = _plan("130", "2T")
    held = _materialised("130", ("2T",), {planner.filing_key("130", _YEAR, "2T"): "revision"})
    result = planner.prepare_return(held, plan, [])
    assert isinstance(result, TableRow)
    assert result.calculate is Stage.HISTORY_FILED
    assert calls == []


def test_a_row_names_its_source_returns_and_reads_back_without_them_in_an_older_file() -> None:
    plan = _plan("303", "4T", sources_returns=("303", "390"))
    row = TableRow.from_plan(plan, Stage.CALCULATED)
    assert row.sources_returns == ("303", "390")
    line = row.to_json()
    assert json.loads(line)["sources_returns"] == ["303", "390"]
    assert TableRow.from_json(line) == row
    older = json.loads(line)
    del older["sources_returns"]
    assert TableRow.from_json(json.dumps(older)).sources_returns == ()
    assert "sources_returns" not in row.to_baseline_json(row.horizon)
    baseline = TableRow.from_json(row.to_baseline_json(row.horizon), horizon=row.horizon)
    assert baseline.sources_returns == ()


def test_the_sweep_still_exports_the_planner_names_it_moved() -> None:
    for name in ("plan_rows", "replay_scope", "stated_values", "prepare_return", "PreparedReturn"):
        assert getattr(sweep, name) is getattr(planner, name), name
    for name in ("cases", "run_return", "run_lifecycle", "Lifecycle", "MODELOS_ENV", "YEARS_ENV", "PERSONAS_ENV"):
        assert hasattr(sweep, name), name


def test_the_sociedad_limitada_plan_builds_at_a_horizon_whose_prior_year_edition_lacks_the_incn_binding() -> None:
    envelope = planner.registry_envelope()
    persona = planner.persona_under_horizon("sociedad-limitada", envelope.horizon)
    (entry,) = (item for item in persona.attested_prior_values if item.where_declared)
    with bundled_indexed_authority().operation() as operation:
        lacking = [
            year
            for year in range(envelope.floor, envelope.horizon + 1)
            if entry.binding
            not in revision_bindings_by_id(
                operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period)
            )
        ]
    assert lacking
    plans, _emitted = planner.plan_rows("sociedad-limitada", max(lacking) + 1)
    assert plans

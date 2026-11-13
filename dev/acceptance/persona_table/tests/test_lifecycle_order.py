"""A return takes its stages in the stage order named: filed inside verify (legacy) or after the export (lifecycle)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2
from cadrumo.entrypoints.tests.persona_materialisation import PersonaWorld

from .. import planner, sweep
from ..__main__ import _selection, main
from ..planner import DEFAULT_STAGE_ORDER, STAGE_ORDER_ENV, STAGE_ORDERS, stage_order_in_use
from ..provenance import RunProvenance, meta_path, read_meta, write_meta
from ..render import render_table
from ..rows import PlannedRow, Stage, TableRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORLD = cast(PersonaWorld, object())
_VERIFIED = cast(ModeloWorkVerifyPublicResultV2, object())
_YEAR = 7
"""Any year: the sequencer under test does not read the registry envelope."""
_PLAN = PlannedRow(
    persona="synthetic",
    modelo="130",
    year=_YEAR,
    period="1T",
    horizon=_YEAR,
    has_values=False,
    grounding="none",
    sources=(),
)


def _record(
    monkeypatch: pytest.MonkeyPatch, *, granted: bool, export: Stage, filed: str = "filed locally"
) -> list[str]:
    """Replace the three lifecycle operations with recorders, so only the sequencer under test runs."""
    calls: list[str] = []

    def verify(*_args: object) -> tuple[Stage, str, ModeloWorkVerifyPublicResultV2 | None]:
        calls.append("verify")
        return (Stage.PASSED, "", _VERIFIED) if granted else (Stage.INCOMPLETE, "verify: open", None)

    def export_stage(*_args: object) -> tuple[Stage, str, str]:
        calls.append("export")
        return export, "", "" if export is Stage.PASSED else "export: refused"

    def file_locally(_world: object, _unit: str, _revision: str, verified: object) -> str:
        assert verified is _VERIFIED
        calls.append("file")
        return filed

    monkeypatch.setattr(sweep, "_verify", verify)
    monkeypatch.setattr(sweep, "_export", export_stage)
    monkeypatch.setattr(sweep, "_file_locally", file_locally)
    return calls


def _lifecycle(order: str) -> sweep.Lifecycle:
    return sweep.run_lifecycle(_WORLD, _PLAN, [], Path(), "unit", "revision", stage_order=order)


@pytest.mark.parametrize("export", [Stage.PASSED, Stage.REFUSED])
def test_the_lifecycle_order_files_a_granted_verification_after_the_export_whatever_it_settled(
    monkeypatch: pytest.MonkeyPatch, export: Stage
) -> None:
    calls = _record(monkeypatch, granted=True, export=export)
    lifecycle = _lifecycle("lifecycle")
    assert calls == ["verify", "export", "file"]
    assert (lifecycle.verify, lifecycle.verify_reason, lifecycle.export, lifecycle.file_reason) == (
        Stage.PASSED,
        "",
        export,
        "filed locally",
    )


@pytest.mark.parametrize("export", [Stage.PASSED, Stage.REFUSED])
def test_the_legacy_order_files_a_granted_verification_inside_verify_before_the_export(
    monkeypatch: pytest.MonkeyPatch, export: Stage
) -> None:
    calls = _record(monkeypatch, granted=True, export=export, filed="file: refused")
    lifecycle = _lifecycle("legacy")
    assert calls == ["verify", "file", "export"]
    assert (lifecycle.verify, lifecycle.verify_reason, lifecycle.export, lifecycle.file_reason) == (
        Stage.PASSED,
        "file: refused",
        export,
        "",
    )


@pytest.mark.parametrize("order", STAGE_ORDERS)
def test_a_verification_that_was_not_granted_is_exported_and_never_filed(
    monkeypatch: pytest.MonkeyPatch, order: str
) -> None:
    calls = _record(monkeypatch, granted=False, export=Stage.PASSED)
    lifecycle = _lifecycle(order)
    assert calls == ["verify", "export"]
    assert (lifecycle.verify, lifecycle.verify_reason, lifecycle.file_reason) == (Stage.INCOMPLETE, "verify: open", "")


def test_the_environment_names_the_order_a_lifecycle_without_one_takes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record(monkeypatch, granted=True, export=Stage.PASSED)
    monkeypatch.setenv(STAGE_ORDER_ENV, "lifecycle")
    sweep.run_lifecycle(_WORLD, _PLAN, [], Path(), "unit", "revision")
    assert calls == ["verify", "export", "file"]


def test_the_default_order_is_legacy_and_one_constant_holds_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(STAGE_ORDER_ENV, raising=False)
    assert DEFAULT_STAGE_ORDER == "legacy"
    assert stage_order_in_use() == DEFAULT_STAGE_ORDER
    monkeypatch.setenv(STAGE_ORDER_ENV, "  ")
    assert stage_order_in_use() == DEFAULT_STAGE_ORDER
    monkeypatch.setattr(planner, "DEFAULT_STAGE_ORDER", "lifecycle")
    monkeypatch.delenv(STAGE_ORDER_ENV)
    assert stage_order_in_use() == "lifecycle"


def test_an_unknown_order_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STAGE_ORDER_ENV, "sideways")
    with pytest.raises(ValueError, match="sideways"):
        stage_order_in_use()


def test_the_command_line_names_the_order_to_the_collector_and_refuses_an_unknown_one() -> None:
    chosen = argparse.Namespace(persona=[], modelo=[], year=[], stage_order="lifecycle")
    assert _selection(chosen)[STAGE_ORDER_ENV] == "lifecycle"
    with pytest.raises(SystemExit) as refused:
        main(["run", "--out", "rows.jsonl", "--tree", "t", "--stage-order", "sideways"])
    assert refused.value.code == 2


def test_the_sidecar_records_the_stage_order_and_render_prints_it(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_meta(rows, RunProvenance("tree1", "generation", "digest"), stage_order="lifecycle")
    assert json.loads(meta_path(rows).read_text(encoding="utf-8"))["stage_order"] == "lifecycle"
    meta = read_meta(meta_path(rows))
    assert meta is not None
    row = TableRow.from_plan(_PLAN, Stage.CALCULATED)
    assert "stage_order `lifecycle`" in render_table([row], head="abc", provenance=meta)


def test_a_sidecar_without_a_stage_order_is_a_legacy_run_and_prints_none(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_meta(rows, RunProvenance("tree1", "generation", "digest"))
    meta = read_meta(meta_path(rows))
    assert meta is not None
    assert "stage_order" not in meta
    row = TableRow.from_plan(_PLAN, Stage.CALCULATED)
    assert "stage_order" not in render_table([row], head="abc", provenance=meta)

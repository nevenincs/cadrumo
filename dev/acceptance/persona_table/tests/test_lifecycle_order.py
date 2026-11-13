"""A return takes its stages in the lifecycle order verify, export, file, and files only on a granted verification."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2
from cadrumo.entrypoints.tests.persona_materialisation import PersonaWorld

from .. import sweep
from ..rows import PlannedRow, Stage

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORLD = cast(PersonaWorld, object())
_VERIFIED = cast(ModeloWorkVerifyPublicResultV2, object())
_PLAN = PlannedRow(
    persona="synthetic",
    modelo="130",
    year=2025,
    period="1T",
    horizon=2025,
    has_values=False,
    grounding="none",
    sources=(),
)


def _record(monkeypatch: pytest.MonkeyPatch, *, granted: bool, export: Stage) -> list[str]:
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
        return "filed locally"

    monkeypatch.setattr(sweep, "_verify", verify)
    monkeypatch.setattr(sweep, "_export", export_stage)
    monkeypatch.setattr(sweep, "_file_locally", file_locally)
    return calls


@pytest.mark.parametrize("export", [Stage.PASSED, Stage.REFUSED])
def test_a_granted_verification_is_filed_after_the_export_whatever_it_settled(
    monkeypatch: pytest.MonkeyPatch, export: Stage
) -> None:
    calls = _record(monkeypatch, granted=True, export=export)
    lifecycle = sweep.run_lifecycle(_WORLD, _PLAN, [], Path(), "unit", "revision")
    assert calls == ["verify", "export", "file"]
    assert (lifecycle.verify, lifecycle.export, lifecycle.file_reason) == (Stage.PASSED, export, "filed locally")


def test_a_verification_that_was_not_granted_is_exported_and_never_filed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _record(monkeypatch, granted=False, export=Stage.PASSED)
    lifecycle = sweep.run_lifecycle(_WORLD, _PLAN, [], Path(), "unit", "revision")
    assert calls == ["verify", "export"]
    assert (lifecycle.verify, lifecycle.file_reason) == (Stage.INCOMPLETE, "")

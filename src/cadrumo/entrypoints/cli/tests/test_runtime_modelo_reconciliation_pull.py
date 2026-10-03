"""The CLI's three-operation chain for a captured justificante reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.justificante import JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
from ....application.modelo.reconciliation import ModeloReconciliationReport
from ....application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ....application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
)
from ....application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from .. import runtime_modelo_reconciliation_pull as bridge
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_WORK_UNIT_ID = "1" * 64
_SNAPSHOT_ID = "a" * 64


def test_pull_uses_one_bound_profile_for_selection_capture_and_reconciliation(monkeypatch: pytest.MonkeyPatch) -> None:
    """An active-profile switch cannot retarget an already bound chain."""
    client = SimpleNamespace(profile_id=_PROFILE)
    unit = SimpleNamespace(
        bucket_id=str(_PROFILE),
        work_unit_id=_WORK_UNIT_ID,
        modelo="130",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "1T"),
    )
    source_ref = f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{_SNAPSHOT_ID}"
    report = ModeloReconciliationReport(
        work_unit_id=_WORK_UNIT_ID,
        bucket_id=str(_PROFILE),
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_path=source_ref,
        verdict=ModeloReconciliationVerdict.MATCHES,
        reconciled_at=datetime(2026, 9, 29, tzinfo=UTC),
    )
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def read_unit(_ctx: typer.Context, **selectors: object) -> object:
        calls.append(("metadata", selectors))
        return unit

    def capture(_ctx: typer.Context, **scope: object) -> object:
        calls.append(("capture", scope))
        return SimpleNamespace(projection=SimpleNamespace(snapshot_id=_SNAPSHOT_ID))

    def reconcile(submitted_client: object, request: ModeloReconciliationPullRequest, **options: object):
        assert submitted_client is client
        calls.append(("reconcile", request))
        assert options == {
            "definition_id": MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(_PROFILE)),
            "result_type": ModeloReconciliationImportProjection,
            "request_version": 1,
            "result_version": 1,
            "timeout": 120,
        }
        return RegisteredOperationCompletion(
            operation_id="b" * 64,
            projection=ModeloReconciliationImportProjection.from_report(report),
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr(bridge, "read_modelo_work_unit", read_unit)
    monkeypatch.setattr(bridge, "capture_justificante_for_cli", capture)
    monkeypatch.setattr(bridge, "run_registered_operation", reconcile)

    actual = bridge.pull_modelo_reconciliation(
        cast(typer.Context, cast(object, None)),
        work_unit_id=_WORK_UNIT_ID,
        modelo=None,
        year=None,
        period=None,
        revision=None,
        bucket_id=str(_PROFILE),
        actor="operator",
    )

    assert actual == report
    assert calls == [
        (
            "metadata",
            {
                "work_unit_id": _WORK_UNIT_ID,
                "modelo": None,
                "year": None,
                "period": None,
                "revision": None,
                "bucket_id": str(_PROFILE),
                "expected_profile_id": _PROFILE,
            },
        ),
        (
            "capture",
            {"profile_id": _PROFILE, "modelo": "130", "year": 2024, "period": unit.period},
        ),
        (
            "reconcile",
            ModeloReconciliationPullRequest(
                profile_id=_PROFILE,
                work_unit_id=_WORK_UNIT_ID,
                snapshot_id=_SNAPSHOT_ID,
                actor="operator",
            ),
        ),
    ]

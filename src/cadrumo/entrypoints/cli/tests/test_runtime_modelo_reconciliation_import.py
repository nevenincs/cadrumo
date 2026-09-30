"""The reconciliation import bridge correlates profile and report scope."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.reconciliation import ModeloReconciliationReport
from ....application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportAdvisoryProjection,
    ModeloReconciliationImportProjection,
    ModeloReconciliationImportRequest,
)
from ....application.modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_modelo_reconciliation_import as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_WORK_UNIT_ID = "1" * 64
_OPERATION_ID = "a" * 64
_SOURCE_PATH = Path("C:/synthetic/evidence.pdf").resolve()


def _report(
    *,
    bucket_id: str = str(_PROFILE),
    source_kind: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.DECLARATION,
    source_path: str = str(_SOURCE_PATH),
) -> ModeloReconciliationReport:
    """Build a report with every diff category and a structured advisory."""
    return ModeloReconciliationReport(
        work_unit_id=_WORK_UNIT_ID,
        bucket_id=bucket_id,
        source_kind=source_kind,
        source_path=source_path,
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diffs=(
            ModeloReconciliationDiff(
                field_name="modelo",
                work_unit_value="303",
                evidence_value="130",
                kind="modelo_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
            ModeloReconciliationDiff(
                field_name="total_ingresar",
                work_unit_value="100.00",
                evidence_value="120.00",
                kind="total_ingresar_mismatch",
                diff_kind=ModeloReconciliationDiffKind.TOTAL,
                legal_refs=("ley-37-1992:art-92",),
                source_refs=("aeat-iva-2025",),
            ),
            ModeloReconciliationDiff(
                field_name="iva.resultado",
                work_unit_value="600.00",
                evidence_value="700.00",
                kind="casilla_value_mismatch",
                diff_kind=ModeloReconciliationDiffKind.CASILLA,
                legal_refs=("ley-37-1992:art-92",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
        advisories=(
            ModeloReconciliationAdvisory(
                code="identity_anchor_unverified",
                message="The identity anchor could not be verified.",
                context={"reason": "missing_tax_id", "modelo": "303"},
            ),
        ),
        reconciled_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        narrative="The evidence differs in three fields.",
    )


def _invoke(
    *,
    file: Path = _SOURCE_PATH,
    source_kind: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.DECLARATION,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    actor: str = "auditor@example",
) -> ModeloReconciliationReport:
    return bridge.import_modelo_reconciliation(
        cast(typer.Context, cast(object, None)),
        file=file,
        source_kind=source_kind,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        actor=actor,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloReconciliationImportProjection],
    submitted: list[ModeloReconciliationImportRequest],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def submit(
        submitted_client: object,
        request: ModeloReconciliationImportRequest,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[ModeloReconciliationImportProjection]:
        assert submitted_client is client
        submitted.append(request)
        assert kwargs == {
            "definition_id": MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(_PROFILE)),
            "result_type": ModeloReconciliationImportProjection,
            "request_version": 1,
            "result_version": 1,
            "timeout": 120,
        }
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _completion(
    projection: ModeloReconciliationImportProjection,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> RegisteredOperationCompletion[ModeloReconciliationImportProjection]:
    return RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=effect,
        terminal_condition=terminal_condition,
        refusal_code=refusal_code,
    )


def test_bridge_uses_the_exact_profile_and_full_work_unit_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report(source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE)
    projection = ModeloReconciliationImportProjection.from_report(report)
    submitted: list[ModeloReconciliationImportRequest] = []
    _bind(monkeypatch, _completion(projection), submitted)

    result = _invoke(
        work_unit_id=f" {_WORK_UNIT_ID} ",
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
    )

    assert result == report
    assert submitted == [
        ModeloReconciliationImportRequest(
            profile_id=_PROFILE,
            work_unit_id=_WORK_UNIT_ID,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=str(_SOURCE_PATH),
            actor="auditor@example",
        )
    ]


def test_bridge_forwards_natural_selectors_and_preserves_full_report(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    projection = ModeloReconciliationImportProjection.from_report(report)
    submitted: list[ModeloReconciliationImportRequest] = []
    _bind(monkeypatch, _completion(projection), submitted)

    result = _invoke(
        modelo="303",
        year=2024,
        period=" 1T ",
        revision="2024-revision",
        bucket_id=str(_PROFILE),
    )

    assert result == report
    assert submitted == [
        ModeloReconciliationImportRequest(
            profile_id=_PROFILE,
            modelo="303",
            filing_year=2024,
            period="1T",
            revision_id="2024-revision",
            bucket_id=str(_PROFILE),
            source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
            source_path=str(_SOURCE_PATH),
            actor="auditor@example",
        )
    ]
    assert result.diffs == report.diffs
    assert tuple((advisory.code, advisory.message, dict(advisory.context)) for advisory in result.advisories) == (
        (
            "identity_anchor_unverified",
            "The identity anchor could not be verified.",
            {"reason": "missing_tax_id", "modelo": "303"},
        ),
    )
    assert result.narrative == report.narrative
    assert result.reconciled_at == report.reconciled_at


def test_bridge_refuses_a_foreign_bucket_selector_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationImportRequest] = []
    projection = ModeloReconciliationImportProjection.from_report(_report())
    _bind(monkeypatch, _completion(projection), submitted)

    with pytest.raises(RuntimeRefusalError) as refused:
        _invoke(bucket_id=str(_OTHER_PROFILE))

    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert submitted == []


def test_bridge_refuses_a_projection_from_another_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = ModeloReconciliationImportProjection.from_report(_report(bucket_id=str(_OTHER_PROFILE)))
    submitted: list[ModeloReconciliationImportRequest] = []
    _bind(monkeypatch, _completion(projection), submitted)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert len(submitted) == 1


@pytest.mark.parametrize("effect", [OperationEffect.NONE, OperationEffect.UNKNOWN])
def test_bridge_rejects_a_completion_without_the_required_write_effect(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
) -> None:
    projection = ModeloReconciliationImportProjection.from_report(_report())
    submitted: list[ModeloReconciliationImportRequest] = []
    _bind(monkeypatch, _completion(projection, effect=effect), submitted)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert len(submitted) == 1


@pytest.mark.parametrize(
    ("terminal_condition", "refusal_code"),
    [
        (OperationTerminalCondition.REFUSED, None),
        (OperationTerminalCondition.SUCCEEDED, "unexpected-refusal"),
    ],
)
def test_bridge_rejects_an_unsettled_or_contradictory_completion(
    monkeypatch: pytest.MonkeyPatch,
    terminal_condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    projection = ModeloReconciliationImportProjection.from_report(_report())
    submitted: list[ModeloReconciliationImportRequest] = []
    _bind(
        monkeypatch,
        _completion(
            projection,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert len(submitted) == 1


def test_public_projection_has_lossless_advisory_context() -> None:
    projection = ModeloReconciliationImportProjection.from_report(_report())

    assert projection.diffs == _report().diffs
    assert projection.advisories == (
        ModeloReconciliationImportAdvisoryProjection(
            code="identity_anchor_unverified",
            message="The identity anchor could not be verified.",
            context=(("modelo", "303"), ("reason", "missing_tax_id")),
        ),
    )

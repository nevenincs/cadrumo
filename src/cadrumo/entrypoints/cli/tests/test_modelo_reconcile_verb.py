"""CLI report rendering for reconciliation imports over a fake bound runtime.

Reconciliation behavior is exercised at the application and persistence
adapter seams. These cases keep the CLI responsibility narrow: it submits the
selected profile and selectors through the registered operation bridge, then
renders the complete report returned by that bridge. The fake completion here
does not prove native runtime acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
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
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, profile_operation_subject
from .. import _modelo_reconcile_cli as handler
from .. import runtime_modelo_reconciliation_import as bridge
from .._payloads_modelo_reconcile import ModeloReconcileResult
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_WORK_UNIT_ID = "1" * 64
_OPERATION_ID = "a" * 64


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "casilla_id"),
    [
        pytest.param("100", 2024, "0A", "0604", id="100"),
        pytest.param("111", 2024, "1T", "30", id="111"),
        pytest.param("130", 2024, "1T", "19", id="130"),
        pytest.param("190", 2024, "0A", "decl.retenciones-total", id="190"),
        pytest.param("303", 2024, "1T", "iva.resultado", id="303"),
        pytest.param("390", 2022, "0A", "iva.anual.resultado-regimen-general", id="390"),
    ],
)
def test_import_handler_renders_registered_declaration_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_id: str,
) -> None:
    """Keep per-modelo casilla labels visible through CLI report rendering."""
    evidence_path = tmp_path / f"modelo-{modelo}.pdf"
    source_path = str(evidence_path.resolve())
    diff = ModeloReconciliationDiff(
        field_name=casilla_id,
        work_unit_value="1500.00",
        evidence_value="1851.84",
        kind="casilla_value_mismatch",
        diff_kind=ModeloReconciliationDiffKind.CASILLA,
        legal_refs=("ley-37-1992:art-92",),
        source_refs=("aeat-iva-2025",),
    )
    advisory = ModeloReconciliationAdvisory(
        code="identity_anchor_unverified",
        message="The filing identity anchor could not be verified.",
        context={"modelo": modelo, "anchor": "tax_id"},
    )
    report = ModeloReconciliationReport(
        work_unit_id=_WORK_UNIT_ID,
        bucket_id=str(_PROFILE),
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_path=source_path,
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diffs=(diff,),
        advisories=(advisory,),
        reconciled_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        narrative="One filed casilla differs.",
    )
    projection = ModeloReconciliationImportProjection.from_report(report)
    client = SimpleNamespace(profile_id=_PROFILE)
    submitted: list[ModeloReconciliationImportRequest] = []
    rendered: dict[str, object] = {}

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
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.UPDATED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)

    def capture_envelope(
        _ctx: typer.Context,
        *,
        command: str,
        result: object,
        lines: Iterable[str],
        notices: Sequence[Notice] | None = None,
    ) -> None:
        rendered.update(
            {
                "command": command,
                "result": result,
                "lines": tuple(lines),
                "notices": tuple(notices or ()),
            }
        )

    monkeypatch.setattr(handler, "emit_envelope", capture_envelope)

    handler.reconcile_file_verb(
        cast(typer.Context, cast(object, None)),
        file=evidence_path,
        modelo=modelo,
        year=filing_year,
        period=period,
        revision="selected-revision",
        bucket_id=str(_PROFILE),
        actor="reviewer@example",
        kind=ModeloReconciliationEvidenceKind.DECLARATION,
    )

    assert submitted == [
        ModeloReconciliationImportRequest(
            profile_id=_PROFILE,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id="selected-revision",
            bucket_id=str(_PROFILE),
            source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
            source_path=source_path,
            actor="reviewer@example",
        )
    ]
    assert rendered["command"] == "modelo.reconcile.import"
    result = rendered["result"]
    assert isinstance(result, ModeloReconcileResult)
    assert result.work_unit_id == _WORK_UNIT_ID
    assert result.bucket_id == str(_PROFILE)
    assert result.source_kind is ModeloReconciliationEvidenceKind.DECLARATION
    assert result.source_path == source_path
    assert result.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert len(result.diffs) == 1
    assert result.diffs[0].field_name == casilla_id
    assert result.diffs[0].work_unit_value == "1500.00"
    assert result.diffs[0].evidence_value == "1851.84"
    assert result.diffs[0].legal_refs == diff.legal_refs
    assert result.diffs[0].source_refs == diff.source_refs
    assert rendered["lines"] == (
        f"work_unit_id\t{_WORK_UNIT_ID}",
        f"bucket\t{_PROFILE}",
        "source_kind\tdeclaration",
        f"source_path\t{source_path}",
        "verdict\tmismatches",
        "diffs\t1",
        f"diff\t{casilla_id}\twork_unit=1500.00\tevidence=1851.84",
        "advisory\tidentity_anchor_unverified\tThe filing identity anchor could not be verified.",
    )
    notices = rendered["notices"]
    assert isinstance(notices, tuple)
    assert len(notices) == 1
    assert notices[0].code == advisory.code
    assert notices[0].message == advisory.message
    assert notices[0].severity is NoticeSeverity.WARNING
    assert notices[0].context is not None
    assert dict(notices[0].context) == {"anchor": "tax_id", "modelo": modelo}

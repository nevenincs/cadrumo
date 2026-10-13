"""``modelo.reconcile.pull`` releases the document ``reconcile pull`` prints.

The command renders the report it receives through its own result model; the
operation releases a projection of the same report. Both go through the output
boundary's redaction, and what the command prints beside the document as notices
is what the projection carries as advisories.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.reconciliation import ModeloReconciliationReport
from ....application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ....application.modelo.reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ....core.json_contract import Notice
from ....core.output_rendering import jsonable_output_payload, reveal_cli_identifiers_opt_in
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .. import _modelo_reconcile_cli as handler

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _public(document: object) -> object:
    return redact_structured_for_cli_output(
        jsonable_output_payload(document), reveal_identifiers=reveal_cli_identifiers_opt_in()
    )


@pytest.mark.parametrize("snapshot", [True, False], ids=["with-registry-snapshot", "without"])
def test_the_operation_result_is_the_document_the_command_prints(
    monkeypatch: pytest.MonkeyPatch, snapshot: bool
) -> None:
    report = ModeloReconciliationReport(
        work_unit_id="1" * 64,
        calculation_revision_id="2" * 64,
        registry_snapshot_ref=(
            RegistrySnapshotRef(modelo="130", revision_id="2025-y-siguientes", modelo_year=2025, period="1T")
            if snapshot
            else None
        ),
        bucket_id=str(_PROFILE),
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_path=f"secure-object://cadrumo.outbound.aeat.sede.filed_declaration.observations/{'a' * 64}",
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diffs=(
            ModeloReconciliationDiff(
                field_name="19",
                work_unit_value="1500.00",
                evidence_value="1851.84",
                kind="casilla_value_mismatch",
                diff_kind=ModeloReconciliationDiffKind.CASILLA,
                legal_refs=("ley-37-1992:art-92",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
        advisories=(
            ModeloReconciliationAdvisory(
                code="identity_anchor_unverified",
                message="The filing identity anchor could not be verified.",
                context={"modelo": "130", "anchor": "tax_id"},
            ),
        ),
        reconciled_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        narrative="One filed casilla differs.",
    )
    projection = ModeloReconciliationImportProjection.from_report(report)
    rendered: dict[str, object] = {}

    def capture_envelope(
        _ctx: typer.Context,
        *,
        command: str,
        result: object,
        lines: Iterable[str],
        notices: Sequence[Notice] | None = None,
    ) -> None:
        rendered.update({"result": result, "notices": tuple(notices or ())})

    monkeypatch.setattr(handler, "emit_envelope", capture_envelope)

    handler._render_reconciliation_report(
        cast(typer.Context, cast(object, None)), projection.to_report(), command="modelo.reconcile.pull"
    )

    printed = _public(rendered["result"])
    released = _public(projection.model_dump(exclude={"advisories"}))
    assert released == printed
    notices = cast(tuple[Notice, ...], rendered["notices"])
    assert [(notice.code, notice.message, notice.context) for notice in notices] == [
        (advisory.code, advisory.message, dict(advisory.context)) for advisory in projection.advisories
    ]

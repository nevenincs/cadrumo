"""Strict JSON payload checks for the modelo reconcile pull/file envelopes.

``ModeloReconcileResult`` and its nested ``ModeloReconciliationDiffPayload``
used to redeclare ``ModeloReconciliationReport`` / ``ModeloReconciliationDiff``
as free strings, so an unknown verdict, malformed timestamp, or blank
identity field crossed the envelope the canonical report already refuses.
They now project the canonical closed enums and bounds directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.modelo.reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from .._payloads_modelo_reconcile import ModeloReconcileResult, ModeloReconciliationDiffPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _result_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "work_unit_id": "a" * 64,
        "bucket_id": "b" * 32,
        "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        "source_path": "receipt.pdf",
        "verdict": ModeloReconciliationVerdict.MATCHES,
        "diffs": (),
        "reconciled_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        "narrative": "",
    }
    base.update(overrides)
    return base


def test_modelo_reconcile_result_round_trips_valid_payload() -> None:
    result = ModeloReconcileResult.model_validate(_result_kwargs())

    assert result.verdict is ModeloReconciliationVerdict.MATCHES
    assert result.source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("source_kind", "bogus"),
        ("verdict", "bogus"),
        ("reconciled_at", "not-time"),
    ),
)
def test_modelo_reconcile_result_refuses_malformed_field(field: str, bad_value: object) -> None:
    with pytest.raises(ValidationError):
        ModeloReconcileResult.model_validate(_result_kwargs(**{field: bad_value}))


def _diff_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "field_name": "modelo",
        "work_unit_value": "303",
        "evidence_value": "390",
        "kind": "modelo_mismatch",
        "diff_kind": ModeloReconciliationDiffKind.HEADER_FIELD,
        "legal_refs": (),
        "source_refs": (),
    }
    base.update(overrides)
    return base


def test_modelo_reconciliation_diff_payload_round_trips_valid_row() -> None:
    row = ModeloReconciliationDiffPayload.model_validate(_diff_kwargs())

    assert row.diff_kind is ModeloReconciliationDiffKind.HEADER_FIELD


def test_modelo_reconciliation_diff_payload_round_trips_a_grounded_total_diff() -> None:
    """A ``total`` diff keeps its legal/source grounding, unlike a header diff."""
    row = ModeloReconciliationDiffPayload.model_validate(
        _diff_kwargs(
            field_name="0027",
            kind="total_ingresar_mismatch",
            diff_kind=ModeloReconciliationDiffKind.TOTAL,
            legal_refs=("ley-37-1992:art-164",),
            source_refs=("aeat-modelo-303-instrucciones-2026",),
        ),
    )

    assert row.legal_refs == ("ley-37-1992:art-164",)
    assert row.source_refs == ("aeat-modelo-303-instrucciones-2026",)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("field_name", ""),
        ("kind", ""),
        ("diff_kind", "bogus"),
    ),
)
def test_modelo_reconciliation_diff_payload_refuses_malformed_field(field: str, bad_value: object) -> None:
    with pytest.raises(ValidationError):
        ModeloReconciliationDiffPayload.model_validate(_diff_kwargs(**{field: bad_value}))

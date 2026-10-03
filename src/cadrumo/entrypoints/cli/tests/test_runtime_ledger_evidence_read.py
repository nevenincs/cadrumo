"""Evidence read bridges preserve CLI results and reject foreign projections."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.evidence import MediaKind
from ....application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceRecordProjection,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, profile_operation_subject
from .. import runtime_ledger_evidence_read as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_EVIDENCE_ID = "e" * 16
_OPERATION_ID = "f" * 64


def _record(**changes: object) -> LedgerEvidenceRecordProjection:
    data: dict[str, object] = {
        "evidence_id": _EVIDENCE_ID,
        "bucket_id": str(_PROFILE),
        "source_path": "invoice.pdf",
        "source_sha256": "a" * 64,
        "attachment_id": "a" * 64,
        "media_kind": MediaKind.PDF,
        "supplier": "Supplier SL",
        "invoice_number": "INV-001",
        "invoice_date": "2026-04-01",
        "taxable_base": "100.00",
        "iva_rate": "0.21",
        "iva_amount": "21.00",
        "notes": "read fixture",
        "created_at": datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
    }
    data.update(changes)
    return LedgerEvidenceRecordProjection.model_validate(data)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    definition_id: str,
    completion: RegisteredOperationCompletion[LedgerEvidenceListProjection | LedgerEvidenceViewProjection],
    submitted: list[LedgerEvidenceListRequest | LedgerEvidenceViewRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerEvidenceListRequest | LedgerEvidenceViewRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        if isinstance(request, LedgerEvidenceListRequest):
            assert kwargs["result_type"] is LedgerEvidenceListProjection
        else:
            assert kwargs["result_type"] is LedgerEvidenceViewProjection
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_list_bridge_returns_the_existing_list_envelope_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceListProjection(profile_id=_PROFILE, count=1, rows=(_record(),))
    submitted: list[LedgerEvidenceListRequest | LedgerEvidenceViewRequest] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted=submitted,
    )

    result = bridge.run_ledger_evidence_list(cast(typer.Context, cast(object, None)))

    assert len(submitted) == 1 and isinstance(submitted[0], LedgerEvidenceListRequest)
    assert result.bucket_id == str(_PROFILE)
    assert result.count == 1
    assert result.rows[0].evidence_id == _EVIDENCE_ID
    assert result.rows[0].bucket_event_ids == []


def test_view_bridge_returns_the_existing_flat_view_envelope_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceViewProjection(profile_id=_PROFILE, record=_record())
    submitted: list[LedgerEvidenceListRequest | LedgerEvidenceViewRequest] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted=submitted,
    )

    result = bridge.run_ledger_evidence_view(
        cast(typer.Context, cast(object, None)),
        evidence_id=_EVIDENCE_ID,
    )

    assert len(submitted) == 1 and isinstance(submitted[0], LedgerEvidenceViewRequest)
    assert submitted[0].evidence_id == _EVIDENCE_ID
    assert result.evidence_id == _EVIDENCE_ID
    assert result.bucket_id == str(_PROFILE)
    assert result.taxable_base == "100.00"
    assert result.bucket_event_ids == []


def test_list_bridge_rejects_a_projection_from_another_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = LedgerEvidenceListProjection.model_construct(
        profile_id=_OTHER_PROFILE,
        count=0,
        rows=(),
    )
    submitted: list[LedgerEvidenceListRequest | LedgerEvidenceViewRequest] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted=submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.run_ledger_evidence_list(cast(typer.Context, cast(object, None)))

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_view_bridge_rejects_another_evidence_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    forged_record = _record().model_copy(update={"evidence_id": "c" * 16})
    projection = LedgerEvidenceViewProjection.model_construct(profile_id=_PROFILE, record=forged_record)
    submitted: list[LedgerEvidenceListRequest | LedgerEvidenceViewRequest] = []
    _bind(
        monkeypatch,
        definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted=submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.run_ledger_evidence_view(
            cast(typer.Context, cast(object, None)),
            evidence_id=_EVIDENCE_ID,
        )

    assert refused.value.context is not None
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value

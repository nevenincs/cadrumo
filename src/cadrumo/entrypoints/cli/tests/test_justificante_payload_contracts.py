"""Justificante capture payloads carry the canonical snapshot's contracts.

:class:`~application.live.JustificanteCaptureSnapshot` validates a known
modelo, a bounded filing year and identifiers, a typed period, a lowercase
SHA-256 bound to the decoded receipt bytes, closed ``source_kind`` and
lifecycle catalogues, and a real capture instant. The three CLI transports --
``JustificanteCaptureResult``, ``JustificanteSnapshotSummaryPayload`` and
``JustificanteViewResult`` -- restated those as plain strings and ints, so a
blank bucket/modelo/expediente/csv, ``filing_year=0``, ``period='bogus'``,
``pdf_sha256='bad'``, a ``source_kind``/``state`` outside its catalogue and
``captured_at='not-time'`` were all emittable at the operator boundary.

The valid projection is the positive control: a payload that refused
everything would pass every refusal case below and fail that one. The raw PDF
bytes stay deliberately absent from all three transports -- the receipt body
belongs in secure storage, never on the wire.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.calculations import ObservationSourceKind
from ....application.live import SnapshotLifecycleState
from ....core import Modelo
from .._app_live_justificante_payloads import (
    JustificanteCaptureResult,
    JustificanteSnapshotSummaryPayload,
    JustificanteViewResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "26262626-2626-4626-8626-262626262626"
_PDF_SHA256 = "a3f1" * 16
_SNAPSHOT_ID = "b4e2" * 16
_CAPTURED_AT = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)


def _capture_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bucket_id": _BUCKET_ID,
        "snapshot_id": _SNAPSHOT_ID,
        "modelo": Modelo.M130,
        "filing_year": 2026,
        "period": "1T",
        "expediente_id": "202613000000001Z",
        "csv": "ABCD1234EFGH",
        "pdf_sha256": _PDF_SHA256,
        "source_kind": ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        "state": SnapshotLifecycleState.ACTIVE,
        "captured_at": _CAPTURED_AT,
        "justificante_metadata_registered": True,
        "calendar_evidence_available": True,
        "modelo_filing_record_required": False,
        "filing_evidence_stamped": True,
    }
    base.update(overrides)
    return base


def _view_fields(**overrides: object) -> dict[str, object]:
    base = {
        key: value
        for key, value in _capture_fields().items()
        if key
        not in {
            "justificante_metadata_registered",
            "calendar_evidence_available",
            "modelo_filing_record_required",
            "filing_evidence_stamped",
        }
    }
    base.update(overrides)
    return base


def _summary_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "snapshot_id": _SNAPSHOT_ID,
        "modelo": Modelo.M130,
        "filing_year": 2026,
        "period": "1T",
        "pdf_sha256": _PDF_SHA256,
        "state": SnapshotLifecycleState.ACTIVE,
        "captured_at": _CAPTURED_AT,
    }
    base.update(overrides)
    return base


def test_a_valid_capture_projects_onto_all_three_transports() -> None:
    """Positive control: the shape the projector actually emits must validate."""
    capture = JustificanteCaptureResult.model_validate(_capture_fields())
    view = JustificanteViewResult.model_validate(_view_fields())
    summary = JustificanteSnapshotSummaryPayload.model_validate(_summary_fields())

    assert capture.modelo is Modelo.M130
    assert capture.period == "1T"
    assert capture.state is SnapshotLifecycleState.ACTIVE
    assert view.source_kind is ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE
    assert summary.pdf_sha256 == _PDF_SHA256
    assert capture.model_dump(mode="json")["modelo"] == "130"
    assert summary.model_dump(mode="json")["state"] == SnapshotLifecycleState.ACTIVE.value


def test_none_of_the_transports_carry_the_receipt_body() -> None:
    """The intentional omission of the PDF bytes is a contract, not an oversight."""
    for model in (JustificanteCaptureResult, JustificanteViewResult, JustificanteSnapshotSummaryPayload):
        assert "pdf_base64" not in model.model_fields


@pytest.mark.parametrize(
    "overrides",
    [
        {"bucket_id": ""},
        {"snapshot_id": ""},
        {"filing_year": 0},
        {"filing_year": 10000},
        {"period": "bogus"},
        {"expediente_id": ""},
        {"expediente_id": "short"},
        {"csv": ""},
        {"csv": "tiny"},
        {"pdf_sha256": "bad"},
        {"pdf_sha256": "A" * 64},
        {"source_kind": "bogus"},
        {"state": "bogus"},
        {"captured_at": "not-time"},
    ],
    ids=[
        "blank-bucket",
        "blank-snapshot",
        "zero-year",
        "out-of-range-year",
        "bogus-period",
        "blank-expediente",
        "short-expediente",
        "blank-csv",
        "short-csv",
        "malformed-digest",
        "uppercase-digest",
        "bogus-source-kind",
        "bogus-state",
        "unparsable-instant",
    ],
)
def test_the_capture_result_refuses_ungrounded_receipt_state(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JustificanteCaptureResult.model_validate(_capture_fields(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"bucket_id": ""},
        {"filing_year": 0},
        {"period": "bogus"},
        {"pdf_sha256": "bad"},
        {"source_kind": "bogus"},
        {"state": "bogus"},
        {"captured_at": "not-time"},
    ],
)
def test_the_view_result_refuses_ungrounded_receipt_state(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JustificanteViewResult.model_validate(_view_fields(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"snapshot_id": ""},
        {"filing_year": 0},
        {"period": "bogus"},
        {"pdf_sha256": "bad"},
        {"state": "bogus"},
        {"captured_at": "not-time"},
    ],
)
def test_the_summary_payload_refuses_ungrounded_receipt_state(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JustificanteSnapshotSummaryPayload.model_validate(_summary_fields(**overrides))


@pytest.mark.parametrize("token", ["1T", "2T", "3T", "4T", "0A"])
def test_real_registry_period_tokens_are_accepted(token: str) -> None:
    """Normalisation must not narrow the catalogue it validates against."""
    assert JustificanteSnapshotSummaryPayload.model_validate(_summary_fields(period=token)).period == token

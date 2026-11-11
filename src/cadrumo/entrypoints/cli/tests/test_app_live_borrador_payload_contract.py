"""Transport parity for Modelo 100 borrador snapshot payloads."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....tests.aeat_literal_fixtures import BORRADOR_PAYLOAD_WWW2_ORIGIN_FIXTURE
from ..app_live_borrador_results import (
    Borrador100ImportResult,
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100RefusedSnapshotPayload,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "f64de004-6f34-406e-8e02-58be01c6157c"  # was 'borrador-bucket'
_SNAPSHOT_ID = "a" * 64


def _snapshot_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "snapshot_id": _SNAPSHOT_ID,
        "filing_year": 2024,
        "period": "2024 0A",
        "captured_at": "2025-03-15T10:00:00+00:00",
        "source_url": BORRADOR_PAYLOAD_WWW2_ORIGIN_FIXTURE,
        "binding_count": 1,
        "state": "active",
    }
    payload.update(overrides)
    return payload


def test_borrador_summary_and_view_accept_canonical_snapshot_json() -> None:
    """Valid snapshot projections retain their existing JSON scalar representation."""
    summary = Borrador100SnapshotSummaryPayload.model_validate(_snapshot_payload())
    view = Borrador100ViewResult.model_validate(
        _snapshot_payload(bucket_id=_BUCKET_ID, binding_values={"renta.binding": "1000.00"}),
    )

    assert summary.model_dump(mode="json") == _snapshot_payload()
    assert view.snapshot_id == _SNAPSHOT_ID
    assert view.binding_values == {"renta.binding": "1000.00"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot_id", "not-a-snapshot"),
        ("period", "2024-0A"),
        ("captured_at", "2025-03-15T10:00:00"),
        ("captured_at", "2025-03-15T11:00:00+01:00"),
        ("binding_count", -1),
        ("state", "retired"),
    ],
)
def test_borrador_summary_refuses_malformed_canonical_fields(field: str, value: object) -> None:
    """Snapshot rows refuse malformed identity, period, UTC, count, and lifecycle values."""
    with pytest.raises(ValidationError):
        Borrador100SnapshotSummaryPayload.model_validate(_snapshot_payload(**{field: value}))


def test_borrador_list_requires_a_bucket_and_exact_row_count() -> None:
    """List envelopes bind rows to one bucket and cannot misreport their count."""
    valid = {"bucket_id": _BUCKET_ID, "count": 1, "rows": [_snapshot_payload()]}

    assert Borrador100ListResult.model_validate(valid).count == 1
    for malformed in ({**valid, "bucket_id": ""}, {**valid, "count": 0}, {**valid, "count": -1}):
        with pytest.raises(ValidationError):
            Borrador100ListResult.model_validate(malformed)


def test_borrador_latest_preserves_empty_and_active_snapshot_branches() -> None:
    """The empty latest response stays sparse; a populated response is active and complete."""
    empty = Borrador100LatestResult.model_validate(
        {"bucket_id": _BUCKET_ID, "filing_year": 2024, "snapshot_id": None},
    )
    populated = Borrador100LatestResult.model_validate(
        _snapshot_payload(bucket_id=_BUCKET_ID),
    )

    assert empty.model_dump(mode="json") == {
        "bucket_id": _BUCKET_ID,
        "filing_year": 2024,
        "snapshot_id": None,
        "captured_at": None,
        "period": None,
        "source_url": None,
        "binding_count": None,
        "state": None,
        "refused": [],
        "outdated_stored_snapshots": 0,
    }
    assert populated.state == "active"
    for malformed in (
        {"bucket_id": _BUCKET_ID, "filing_year": 2024, "snapshot_id": None, "state": "active"},
        {"bucket_id": _BUCKET_ID, "filing_year": 2024, "snapshot_id": _SNAPSHOT_ID, "state": "active"},
        _snapshot_payload(bucket_id=_BUCKET_ID, state="superseded"),
    ):
        with pytest.raises(ValidationError):
            Borrador100LatestResult.model_validate(malformed)


def test_borrador_list_and_latest_carry_an_identity_less_outdated_count() -> None:
    """Stored rows of an older schema are counted, default to none, and never go negative."""
    listing = Borrador100ListResult.model_validate(
        {"bucket_id": _BUCKET_ID, "count": 0, "rows": [], "outdated_stored_snapshots": 2},
    )
    latest = Borrador100LatestResult.model_validate(
        {"bucket_id": _BUCKET_ID, "filing_year": 2024, "snapshot_id": None, "outdated_stored_snapshots": 1},
    )

    assert (listing.outdated_stored_snapshots, latest.outdated_stored_snapshots) == (2, 1)
    assert (
        Borrador100ListResult.model_validate(
            {"bucket_id": _BUCKET_ID, "count": 0, "rows": []},
        ).outdated_stored_snapshots
        == 0
    )
    with pytest.raises(ValidationError):
        Borrador100ListResult.model_validate(
            {"bucket_id": _BUCKET_ID, "count": 0, "rows": [], "outdated_stored_snapshots": -1},
        )


def _refused_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "snapshot_id": "b" * 64,
        "filing_year": 2024,
        "period": "2024 0A",
        "captured_at": "2025-03-15T10:00:00+00:00",
        "state": "active",
        "reason": "binding_keys_not_admitted",
    }
    payload.update(overrides)
    return payload


def test_a_refused_snapshot_is_reported_beside_the_rows_and_not_counted_as_one() -> None:
    """A listing names a refused snapshot with its reason; a latest read holding only one is not empty."""
    listing = Borrador100ListResult.model_validate(
        {"bucket_id": _BUCKET_ID, "count": 1, "rows": [_snapshot_payload()], "refused": [_refused_payload()]}
    )
    latest = Borrador100LatestResult.model_validate(
        {"bucket_id": _BUCKET_ID, "filing_year": 2024, "snapshot_id": None, "refused": [_refused_payload()]}
    )

    assert listing.count == 1
    assert [(item.snapshot_id, item.reason) for item in listing.refused] == [("b" * 64, "binding_keys_not_admitted")]
    assert latest.snapshot_id is None
    assert latest.model_dump(mode="json")["refused"] == [_refused_payload()]
    for field, value in (("reason", "unknown_reason"), ("snapshot_id", "short"), ("period", "2024-0A")):
        with pytest.raises(ValidationError):
            Borrador100RefusedSnapshotPayload.model_validate(_refused_payload(**{field: value}))


def _import_payload(**overrides: object) -> dict[str, object]:
    payload = _snapshot_payload(
        bucket_id=_BUCKET_ID,
        extraction_profile_id="modelo-100-borrador-pdf",
        extraction_coverage="1",
        artefact_kind="BORRADOR",
        source_pdf_sha256="c" * 64,
        state="superseded",
        outcome="resolved_superseded",
    )
    payload.update(overrides)
    return payload


def test_the_import_result_names_what_the_import_did() -> None:
    """A re-import that resolved to a superseded snapshot says so; an unknown outcome is refused."""
    result = Borrador100ImportResult.model_validate(_import_payload())

    assert (result.state, result.outcome) == ("superseded", "resolved_superseded")
    assert result.unowned_casillas == [] and result.observed_casillas == []
    with pytest.raises(ValidationError):
        Borrador100ImportResult.model_validate(_import_payload(outcome="reactivated"))
    without_outcome = _import_payload()
    del without_outcome["outcome"]
    with pytest.raises(ValidationError):
        Borrador100ImportResult.model_validate(without_outcome)

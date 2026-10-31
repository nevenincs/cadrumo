"""A baja is changed or removed by a correction, as the correct request states it, and the list row shows it.

Figures use 2,000.00 at 26% linear from 1 January 2025: 520.00 a full year.  A baja on
30 June 2026 keeps 181 of 365 days of that year: 520 x 181 / 365 = 257.86, and zeroes 2027.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetCorrectRequest
from cadrumo.application.actividad_asset.activity_asset_executors import _assigned_correction
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetDisposalSnapshot,
)
from cadrumo.domain.renta.actividad_asset.claims import effective_claims
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision

from .register_support import MemoryRepository
from .test_baja_correction import _ASSET, _disposed, _sale

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _correction(baja: ActivityAssetRevision, disposal: ActivityAssetDisposal | None) -> ActivityAssetRevision:
    """Build the correction the desktop sends: the old revision carried forward with only its baja replaced.

    The stale ``out_of_service_date`` travels with it, as it does from a form that has no field for it.
    """
    snapshot = ActivityAssetCorrectionRevisionSnapshot.from_domain(baja).model_copy(
        update={
            "revision_number": baja.revision_number + 1,
            "supersedes_revision_id": baja.revision_id,
            "disposal": None if disposal is None else ActivityAssetDisposalSnapshot.from_domain(disposal),
        },
    )
    request = ActivityAssetCorrectRequest(profile_id=uuid4(), revision=snapshot)
    return ActivityAssetCorrectRequest.model_validate_json(request.model_dump_json()).revision.to_domain()


def _by_year(repository: MemoryRepository) -> dict[int, Decimal]:
    return {claim.tax_year: claim.amount for claim in effective_claims(repository.history.claims)}


def test_the_list_row_carries_the_recorded_baja_date_and_reason() -> None:
    operations, _, _ = _disposed()

    (row,) = operations.list_elements()

    assert row.disposal is not None
    assert row.disposal.disposal_date == date(2026, 6, 30)
    assert row.disposal.reason is ActivityAssetDisposalReason.SALE
    assert row.disposal.reason_key == "ledger.actividad_asset.disposal_reason.sale"


def test_an_element_without_a_baja_has_none_on_its_row() -> None:
    operations, _, baja = _disposed()

    operations.correct(_correction(baja, None))

    assert operations.list_elements()[0].disposal is None


def test_a_correct_request_that_changes_the_baja_moves_the_claims_it_zeroed() -> None:
    operations, repository, baja = _disposed()

    operations.correct(_correction(baja, _sale(date(2025, 12, 31))))

    assert _by_year(repository) == {2025: Decimal("520.00"), 2026: Decimal("0.00"), 2027: Decimal("0.00")}
    moved = operations.list_elements()[0].disposal
    assert moved is not None
    assert moved.disposal_date == date(2025, 12, 31)


def test_a_correct_request_that_clears_the_baja_restores_its_deductions() -> None:
    operations, repository, baja = _disposed()

    operations.correct(_correction(baja, None))

    assert _by_year(repository) == {2025: Decimal("520.00"), 2026: Decimal("257.86"), 2027: Decimal("520.00")}
    assert operations.inspect(_ASSET)[-1].disposal is None


def test_a_correct_request_that_leaves_the_baja_out_is_refused_while_null_removes_it() -> None:
    _, _, baja = _disposed()
    request = ActivityAssetCorrectRequest(
        profile_id=uuid4(),
        revision=ActivityAssetCorrectionRevisionSnapshot.from_domain(baja).model_copy(update={"disposal": None}),
    )
    stated = json.loads(request.model_dump_json())
    assert stated["revision"]["disposal"] is None

    assert ActivityAssetCorrectRequest.model_validate_json(json.dumps(stated)).revision.disposal is None
    del stated["revision"]["disposal"]
    with pytest.raises(ValidationError, match="disposal"):
        ActivityAssetCorrectRequest.model_validate_json(json.dumps(stated))


def test_the_executor_assigns_the_number_of_an_unnumbered_correction() -> None:
    operations, _, baja = _disposed()
    data = ActivityAssetCorrectionRevisionSnapshot.from_domain(baja).model_dump(mode="json")
    data.pop("revision_number")
    data["supersedes_revision_id"] = baja.revision_id
    snapshot = ActivityAssetCorrectionRevisionSnapshot.model_validate_json(json.dumps(data))

    assert snapshot.revision_number is None
    revision = _assigned_correction(operations, snapshot)
    assert revision.revision_number == baja.revision_number + 1
    assert revision.supersedes_revision_id == baja.revision_id


def test_a_second_baja_is_refused_and_leaves_the_history_unchanged() -> None:
    operations, repository, _ = _disposed()
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="disposal_already_recorded"):
        operations.dispose(_ASSET, _sale(date(2027, 3, 1)))

    assert repository.history == before

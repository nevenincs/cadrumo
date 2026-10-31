"""A correction's number is the backend's: left out it follows the superseded revision, stated it must agree."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetCorrectRequest
from cadrumo.application.actividad_asset.activity_asset_executors import _assigned_correction
from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetCorrectionRevisionSnapshot
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError

from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _request_json(first_id: str, *, number: int | None) -> str:
    base = ActivityAssetCorrectionRevisionSnapshot.from_domain(_revision())
    document = json.loads(
        ActivityAssetCorrectRequest(
            profile_id=uuid4(),
            revision=base.model_copy(update={"supersedes_revision_id": first_id, "revision_number": 2}),
        ).model_dump_json(),
    )
    if number is None:
        del document["revision"]["revision_number"]
    else:
        document["revision"]["revision_number"] = number
    return json.dumps(document)


def test_a_correction_without_a_number_is_numbered_after_the_revision_it_supersedes() -> None:
    operations, _ = _operations()
    first = operations.create(_revision(), _NAME).revisions[-1]
    snapshot = ActivityAssetCorrectRequest.model_validate_json(_request_json(first.revision_id, number=None)).revision

    revision = _assigned_correction(operations, snapshot)

    assert snapshot.revision_number is None
    assert revision.revision_number == 2
    assert revision.supersedes_revision_id == first.revision_id


def test_a_retry_after_the_correction_applied_rebuilds_the_same_revision_and_writes_nothing() -> None:
    operations, repository = _operations()
    first = operations.create(_revision(), _NAME).revisions[-1]
    snapshot = ActivityAssetCorrectRequest.model_validate_json(_request_json(first.revision_id, number=None)).revision
    operations.correct(_assigned_correction(operations, snapshot))
    before = repository.history

    operations.correct(_assigned_correction(operations, snapshot))

    assert repository.history == before


def test_a_stated_number_that_disagrees_is_refused_and_one_that_agrees_is_taken() -> None:
    operations, _ = _operations()
    first = operations.create(_revision(), _NAME).revisions[-1]
    wrong = ActivityAssetCorrectRequest.model_validate_json(_request_json(first.revision_id, number=5)).revision
    right = ActivityAssetCorrectRequest.model_validate_json(_request_json(first.revision_id, number=2)).revision

    with pytest.raises(ActividadAssetValidationError, match="correction_must_supersede_current"):
        operations.correct(_assigned_correction(operations, wrong))
    operations.correct(_assigned_correction(operations, right))

    assert operations.inspect("laptop-1")[-1].revision_number == 2


def test_a_correction_that_supersedes_nothing_known_is_refused() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    snapshot = ActivityAssetCorrectRequest.model_validate_json(_request_json("f" * 64, number=None)).revision

    with pytest.raises(ActividadAssetValidationError, match="correction_must_supersede_current"):
        _assigned_correction(operations, snapshot)

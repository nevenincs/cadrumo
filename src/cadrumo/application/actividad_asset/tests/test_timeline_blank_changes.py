"""The timeline leaves out a text change that is empty on both sides in meaning."""

from __future__ import annotations

import pytest

from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
    FurtherAcquisitionRow,
)

from ..register_timeline import _changes
from .test_register import _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIELD = "further_acquisitions[0].lineage.invoice_evidence_id"


def _with_further_evidence(evidence: str) -> ActivityAssetRevision:
    row = FurtherAcquisitionRow(
        shape=AcquisitionShape.SPLIT_PAYMENT,
        lineage=AcquisitionLineageReference(observed_transaction_id="e" * 64, invoice_evidence_id=evidence),
    )
    return _revision().model_copy(update={"further_acquisitions": (row,)})


def _fields(
    before: ActivityAssetRevision | None, after: ActivityAssetRevision
) -> dict[str, tuple[str | None, str | None]]:
    changes = _changes(before, after, class_names=lambda _record: {})
    return {change.field: (change.before, change.after) for change in changes}


def test_a_blank_text_with_no_value_before_is_not_reported_as_a_change() -> None:
    fields = _fields(None, _with_further_evidence(""))

    assert _FIELD not in fields
    assert "further_acquisitions[0].shape" in fields


def test_a_blank_text_against_a_whitespace_text_is_not_a_change() -> None:
    assert _FIELD not in _fields(_with_further_evidence("  "), _with_further_evidence(""))


def test_a_text_that_gains_or_loses_a_value_is_still_reported() -> None:
    blank, stated = _with_further_evidence(""), _with_further_evidence("invoice-9")

    assert _fields(blank, stated)[_FIELD] == ("", "invoice-9")
    assert _fields(stated, blank)[_FIELD] == ("invoice-9", "")

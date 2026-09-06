"""An approval that has stopped holding is reported by the review queue.

Approval is a claim about the inputs it was granted over. Nothing recomputed
that claim: the queue read the status stored on disk, so an approved draft
stayed approved however far the ledger, invoices, taxpayer profile or registry
schema had moved underneath it, and the ``APROBACION_CADUCADA`` row the adapter
already knew how to emit was unreachable.

The sibling test in ``test_adapters`` writes a draft that is ALREADY stale and
proves the row renders. That cannot distinguish a queue that detects staleness
from one that only repeats what it was told, which is why these cases write an
``APROBADO`` draft and require the queue to reach the verdict itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....domain.filing.schema import ModeloApprovalBasis, ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ....tests.profile_capsule import open_test_profile_session
from ...filing.draft_review import ModeloApprovalStaleReason, describe_stale_reason
from .._adapters import drafts_pending
from ..enums import ReviewSeverity
from ..operator import project_review_queue
from .test_adapters import (
    _PROFILE_ID,
    _build_settings,
    _draft,
    _seed_active_profile,
    _write_draft,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_A = "a" * 64
_B = "b" * 64


def _basis(draft_id: str) -> ModeloApprovalBasis:
    """A structurally valid basis; the digests need not describe real state.

    Staleness is decided before any of them is compared, because the checksum
    below is an aggregate claim over the basis and is verified first.
    """
    return ModeloApprovalBasis(
        draft_payload_fingerprint=draft_id,
        draft_review_fingerprint=_A,
        transaction_catalogue_fingerprint=_A,
        invoice_catalogue_fingerprint=_A,
        prior_filing_observations_fingerprint=_A,
        profile_activity_fingerprint=_A,
        category_profiles_fingerprint=_A,
        schema_formula_fingerprint=_A,
    )


def _approved(*, review_checksum: str | None) -> ModeloDraft:
    base = _draft(status=ModeloDraftStatus.APROBADO)
    return base.model_copy(
        update={
            "approval_basis": _basis(base.draft_id),
            "approved_at": datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            "approved_by": "operator-A",
            "review_checksum": review_checksum,
        },
    )


def test_an_approval_whose_basis_no_longer_holds_surfaces_as_stale(tmp_path: Path) -> None:
    """A checksum that does not describe the stored basis ages the approval out."""
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        draft = _approved(review_checksum=_B)
        _write_draft(settings, draft)
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)

    assert len(items) == 1
    assert items[0].severity is ReviewSeverity.HIGH
    assert items[0].draft_id == draft.draft_id
    assert items[0].summary == "review.filing.stale_approval_summary"


def test_an_approval_with_no_metadata_is_not_reported_stale(tmp_path: Path) -> None:
    """The control: the refresh must not mark every approved draft stale.

    Without it the first case passes just as well against a queue that reports
    staleness unconditionally, which is the failure mode a detector of this
    shape falls into.
    """
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(settings, _draft(status=ModeloDraftStatus.APROBADO))
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)

    assert all(item.summary != "review.filing.stale_approval_summary" for item in items)


def test_the_stale_row_names_which_axis_moved(tmp_path: Path) -> None:
    """The reasons ride as tokens, and the queue projection renders them.

    An operator told only that an approval is stale has to go looking for which
    of eight upstream things changed.
    """
    settings = _build_settings(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        _seed_active_profile()
        _write_draft(settings, _approved(review_checksum=_B))
        items = drafts_pending(settings, bucket_id=_PROFILE_ID)
        assert items[0].stale_reasons == (ModeloApprovalStaleReason.REVIEW_CHECKSUM_MISMATCH,)
        report = project_review_queue()

    rows = [row for row in report.rows if row.severity is ReviewSeverity.HIGH]
    assert len(rows) == 1
    assert rows[0].reason != rows[0].summary
    assert describe_stale_reason(ModeloApprovalStaleReason.REVIEW_CHECKSUM_MISMATCH) in rows[0].reason

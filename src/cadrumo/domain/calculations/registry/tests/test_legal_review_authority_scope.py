"""Production legal-review eligibility is scoped to the selected snapshot."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import RevisionReviewStatus
from .....core.resources import bundled_path
from .. import ValidatedRegistryAuthority
from .._errors import RegistryValidationError
from .._snapshot import build_validated_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_authority_refuses_real_m182_pending_revision_before_legal_review_gate() -> None:
    """M182's operator-reviewed legal refs do not promote its pending revision."""
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"modelo 182 revision 2007-y-siguientes is 'pending_review'.*operator_reviewed revision",
    ):
        authority.snapshot("182", filing_year=2025, period="0A")


@pytest.mark.parametrize(
    ("review_status", "reviewed_by", "reviewed_at"),
    (
        (RevisionReviewStatus.PENDING_REVIEW, None, None),
        (RevisionReviewStatus.AGENT_REVIEWED, "agent-review", date(2026, 8, 1)),
    ),
)
def test_build_validated_snapshot_refuses_real_m182_non_operator_revision(
    review_status: RevisionReviewStatus,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> None:
    """Both pending and agent review remain typed non-filing revision states."""
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    modelo = authority.modelo("182")
    revision = modelo.revisions["2007-y-siguientes"].model_copy(
        update={
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
        },
    )
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: revision}},
    )

    with pytest.raises(
        RegistryValidationError,
        match=rf"modelo 182 revision 2007-y-siguientes is '{review_status.value}'.*operator_reviewed revision",
    ):
        build_validated_snapshot(
            mutated_modelo,
            authority.catalogues,
            filing_year=2025,
            period="0A",
            revision_id="2007-y-siguientes",
        )

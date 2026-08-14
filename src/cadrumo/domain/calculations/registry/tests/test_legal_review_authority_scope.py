"""Production legal-review eligibility is scoped to the selected snapshot."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import RevisionReviewStatus
from .....core.resources import bundled_path
from .. import ValidatedRegistryAuthority
from .._errors import RegistryValidationError
from .._export import derive_export_layouts_from_bindings
from .._loader import load_registry_tree
from .._snapshot import _check_snapshot_filing_capability, build_validated_snapshot

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


def _committed_registry():
    """Load the tree through the compiler, so this proof survives a red validation gate."""
    return load_registry_tree(bundled_path("registry", "aeat"))


def test_filing_grade_snapshot_refuses_a_reviewed_revision_that_declares_no_export_layout() -> None:
    """Operator review does not by itself make a revision filable.

    M182 declares no export layout. Stamping it operator-reviewed clears the review
    gate and the request then reaches the filing-capability check, which is the wiring
    this test exists to prove: without it a reviewed-but-layoutless revision would
    yield a snapshot, and the completeness gate in ``export_draft`` would then have an
    absent layout to check and would pass over it.
    """
    modelos, catalogues = _committed_registry()
    modelo = next(candidate for candidate in modelos if candidate.id == "182")
    revision = modelo.revisions["2007-y-siguientes"]
    assert not revision.export_layouts, "fixture drift: M182 gained an export layout, pick another subject"
    reviewed = revision.model_copy(
        update={
            "review_status": RevisionReviewStatus.OPERATOR_REVIEWED,
            "reviewed_by": "operator",
            "reviewed_at": date(2026, 5, 5),
        },
    )
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, reviewed.id: reviewed}})

    with pytest.raises(
        RegistryValidationError,
        match=r"modelo 182 revision 2007-y-siguientes declares no export layout",
    ):
        build_validated_snapshot(
            mutated,
            catalogues,
            filing_year=2025,
            period="0A",
            revision_id="2007-y-siguientes",
        )


def test_the_filing_capability_check_passes_a_revision_that_can_emit() -> None:
    """The control: without this, the refusal above could be firing on every revision."""
    modelos, _catalogues = _committed_registry()
    emitting = [
        (modelo, revision)
        for modelo in modelos
        for revision in modelo.revisions.values()
        if derive_export_layouts_from_bindings(revision)
    ]
    assert emitting, "no revision in the registry declares an export layout, so this control cannot run"

    modelo, revision = emitting[0]
    resolved = revision.model_copy(update={"export_layouts": derive_export_layouts_from_bindings(revision)})

    _check_snapshot_filing_capability(modelo, resolved)

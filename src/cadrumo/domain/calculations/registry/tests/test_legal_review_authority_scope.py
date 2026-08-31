"""Production legal-review eligibility is scoped to the selected snapshot."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import LegalReviewStatus, RevisionReviewStatus
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._snapshot_internals import _check_snapshot_filing_capability
from ..authority import ValidatedRegistryAuthority
from ..errors import RegistryValidationError
from ..export import derive_export_layouts_from_bindings
from ..snapshot import build_validated_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M182_LEGACY_OPERATOR_REVIEWED_REFS = frozenset(
    {
        "orden-eha-3021-2007:art-1",
        "orden-eha-3021-2007:art-5",
        "ley-35-2006:art-68.3",
        "ley-58-2003:art-93",
    }
)
_M182_AMENDMENT_AGENT_REVIEWED_REFS = frozenset(
    {
        "orden-hac-1430-2025:art-2",
        "orden-hac-1430-2025:df-unica",
    }
)


def test_authority_refuses_real_m182_through_the_public_accessor() -> None:
    """M182's mixed legal-reference reviews do not promote the revision itself.

    The inputs are live rather than assumed: four legacy refs are
    ``operator_reviewed`` while the two exact 2025 HAC/1430 amendment refs are
    ``agent_reviewed``. Neither reference category promotes the
    ``agent_reviewed`` applicability-grade revision to filing authority.

    This asserted a ``pending_review`` refusal, which the campaign's own stamping
    of M182 retired. The pending-review path is not lost -- the parametrized
    sibling drives it on a mutated copy -- so what this one uniquely covers is
    the PUBLIC ``authority.snapshot`` accessor rather than
    ``build_validated_snapshot``, and it now asserts the refusal M182 actually
    earns today.
    """
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    revision = authority.modelo("182").revisions["2025"]
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED
    assert revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    legal_review_statuses = {str(ref): authority.catalogues.legal[ref].review_status for ref in revision.legal_refs}
    assert set(legal_review_statuses) == _M182_LEGACY_OPERATOR_REVIEWED_REFS | _M182_AMENDMENT_AGENT_REVIEWED_REFS
    assert {
        ref
        for ref, review_status in legal_review_statuses.items()
        if review_status is LegalReviewStatus.OPERATOR_REVIEWED
    } == _M182_LEGACY_OPERATOR_REVIEWED_REFS
    assert {
        ref for ref, review_status in legal_review_statuses.items() if review_status is LegalReviewStatus.AGENT_REVIEWED
    } == _M182_AMENDMENT_AGENT_REVIEWED_REFS

    # Through the PUBLIC accessor the revision is untouched, so it still declares
    # applicability grade and the newer authority-grade gate answers first. That is
    # the refusal this modelo actually earns here: neither operator-reviewed legacy
    # refs nor agent-reviewed amendments promote it, and the grade names why more
    # directly than the missing layout does. The sibling tests below clear the
    # grade deliberately where the later gates are the subject.
    with pytest.raises(
        RegistryValidationError,
        match=r"modelo 182 revision 2025 declares .applicability. authority grade",
    ):
        authority.snapshot("182", filing_year=2025, period="0A")


@pytest.mark.parametrize(
    ("review_status", "reviewed_by", "reviewed_at", "refusal"),
    (
        (RevisionReviewStatus.PENDING_REVIEW, None, None, r"is 'pending_review'.*requires a reviewed revision"),
        # Agent review CLEARS the review gate -- see the sibling gate's docstring
        # for why demanding operator_reviewed was unreachable -- so M182 is
        # refused one gate later, for the reason that is actually true of it.
        (RevisionReviewStatus.AGENT_REVIEWED, "agent-review", date(2026, 8, 1), r"declares no export layout"),
    ),
)
def test_build_validated_snapshot_refuses_real_m182_non_operator_revision(
    review_status: RevisionReviewStatus,
    reviewed_by: str | None,
    reviewed_at: date | None,
    refusal: str,
) -> None:
    """Both pending and agent review remain typed non-filing revision states.

    The claim is unchanged; which gate enforces it is not. Each case now names
    the refusal it actually earns, so a status silently changing gates is a red
    test rather than a passing one.
    """
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    modelo = authority.modelo("182")
    revision = modelo.revisions["2025"].model_copy(
        update={
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            # The claim under test is about REVIEW status, and a newer
            # authority-grade gate refuses this applicability-grade revision
            # before the review gate runs. Clearing it keeps each case earning
            # the refusal the parametrisation names, instead of collapsing both
            # onto one grade refusal that distinguishes nothing.
            "authority_grade": RegistryAuthorityGrade.FILING,
        },
    )
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: revision}},
    )

    with pytest.raises(
        RegistryValidationError,
        match=rf"modelo 182 revision 2025 {refusal}",
    ):
        build_validated_snapshot(
            mutated_modelo,
            authority.catalogues,
            filing_year=2025,
            period="0A",
            revision_id="2025",
        )


def _committed_registry():
    """Load the tree through the compiler, so this proof survives a red validation gate."""
    return bundled_registry_tree()


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
    revision = modelo.revisions["2025"]
    assert not revision.export_layouts, "fixture drift: M182 gained an export layout, pick another subject"
    reviewed = revision.model_copy(
        update={
            "review_status": RevisionReviewStatus.OPERATOR_REVIEWED,
            "reviewed_by": "operator",
            "reviewed_at": date(2026, 5, 5),
            # A newer gate refuses an applicability-grade revision before the
            # filing-capability check runs. This test is ABOUT that later check,
            # so the fixture clears the grade gate deliberately rather than
            # asserting the refusal that now arrives first.
            "authority_grade": RegistryAuthorityGrade.FILING,
        },
    )
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, reviewed.id: reviewed}})

    with pytest.raises(
        RegistryValidationError,
        match=r"modelo 182 revision 2025 declares no export layout",
    ):
        build_validated_snapshot(
            mutated,
            catalogues,
            filing_year=2025,
            period="0A",
            revision_id="2025",
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


def test_loader_tier_snapshots_in_this_module_carry_no_compiled_orden_authority() -> None:
    """These snapshots are partial, and nothing here may assert on Orden data.

    The tests above build snapshots from compiler-tier catalogues so they survive a
    refusing full-tree validation. That trade is deliberate, and this is its cost:
    ``compile_supplementary_ordenes`` runs during AUTHORITY construction, not during
    the compile, so a loader-tier ``RegistryCatalogues`` carries an empty
    ``supplementary_ordenes`` and every snapshot built from one inherits it.

    Asserted rather than left in a comment. An invariant in a comment is a
    convention, and conventions break at the next caller: an Orden assertion added
    to this file would read an empty authority and pass for the wrong reason. This
    fails instead -- both if someone asserts on Orden data here, and if loader-tier
    catalogues ever start carrying ordenes, which would make the warning stale.
    """
    modelos, catalogues = _committed_registry()

    assert not catalogues.supplementary_ordenes, (
        "loader-tier catalogues now carry compiled ordenes, so the reason these tests avoid "
        "asserting on Orden data no longer holds. Re-read the trade rather than deleting this."
    )

    modelo = next(candidate for candidate in modelos if candidate.id == "182")
    revision = modelo.revisions["2025"]
    reviewed = revision.model_copy(
        update={
            "review_status": RevisionReviewStatus.OPERATOR_REVIEWED,
            "reviewed_by": "operator",
            "reviewed_at": date(2026, 5, 5),
            # A newer gate refuses an applicability-grade revision before the
            # filing-capability check runs. This test is ABOUT that later check,
            # so the fixture clears the grade gate deliberately rather than
            # asserting the refusal that now arrives first.
            "authority_grade": RegistryAuthorityGrade.FILING,
        },
    )
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, reviewed.id: reviewed}})

    with pytest.raises(RegistryValidationError, match="declares no export layout"):
        build_validated_snapshot(mutated, catalogues, filing_year=2025, period="0A", revision_id="2025")

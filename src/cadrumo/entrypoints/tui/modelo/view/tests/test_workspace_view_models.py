"""Real proof that the C2 workspace view models narrow honestly and refuse dishonesty.

Every model under test is a presentation narrowing, so the property that
matters is not that it renders but that it CANNOT render a state the
producer did not declare. Each test therefore drives a real public
Workspace V1 record and then attempts the specific dishonesty the model
exists to prevent.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ......application.modelo.work_addressing import ModeloVisibleFilingTarget
from ......application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceConstraintReferenceV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceTechnicalLabelV1,
    ModeloWorkspaceVersionRefusalV1,
    ModeloWorkspaceVisibleFilingTargetV1,
)
from ......core.revision_review import RevisionReviewStatus
from ......core.period import Period
from ......core.external_constants import OutputLanguage
from ..models import (
    ModeloWorkspaceBoundedPageV1,
    ModeloWorkspaceCapabilityRowV1,
    ModeloWorkspaceCompletePageV1,
    ModeloWorkspaceRefusalViewV1,
    capability_row,
    constraint_disclosure,
    display_text,
    disposition_glyph,
    refusal_view,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REVISION = "2026-y-siguientes"


def _resolved_target() -> ModeloWorkspaceResolvedTargetV1:
    """Build one real resolved target; no stand-in, no partial construction."""
    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="30330300-0000-4000-8000-000000000601",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        law_selected_revision_id=_REVISION,
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
    )


def _capability(disposition: ModeloWorkspaceCapabilityDisposition) -> ModeloWorkspaceCapabilityV1:
    target = _resolved_target()
    return ModeloWorkspaceCapabilityV1(
        capability=ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
        disposition=disposition,
        target=target,
        selected_revision_id=target.law_selected_revision_id,
        producer_owner="application.modelo.workspace",
        producer="closure",
    )


def test_every_disposition_has_its_own_distinguishing_glyph() -> None:
    """Non-colour safety: four dispositions, four marks, none shared."""
    assert {d for d in ModeloWorkspaceCapabilityDisposition} == set(ModeloWorkspaceCapabilityDisposition)
    assert len({disposition_glyph(d) for d in ModeloWorkspaceCapabilityDisposition}) == len(
        ModeloWorkspaceCapabilityDisposition
    )


def test_refused_and_unmeasured_are_distinguishable_from_each_other_and_from_available() -> None:
    """The distinction the requirement vocabulary could not express is preserved.

    A producer that actively refused and an axis nobody measured are
    different answers with different operator remedies. Rendering them
    alike would be an under-declaration performed by the view.
    """
    refused = disposition_glyph(ModeloWorkspaceCapabilityDisposition.REFUSED)
    unmeasured = disposition_glyph(ModeloWorkspaceCapabilityDisposition.UNMEASURED)
    available = disposition_glyph(ModeloWorkspaceCapabilityDisposition.AVAILABLE)
    not_applicable = disposition_glyph(ModeloWorkspaceCapabilityDisposition.NOT_APPLICABLE)

    assert len({refused, unmeasured, available, not_applicable}) == 4


def test_capability_row_copies_the_producer_answer_for_every_disposition() -> None:
    for disposition in ModeloWorkspaceCapabilityDisposition:
        capability = _capability(disposition)
        row = capability_row(capability)

        assert row.disposition is disposition
        assert row.capability is capability.capability
        assert row.producer_owner == capability.producer_owner
        assert row.producer == capability.producer
        assert row.glyph == disposition_glyph(disposition)
        assert row.source is capability


def test_a_capability_row_cannot_carry_a_glyph_its_disposition_does_not_declare() -> None:
    """Anti-tautology: the mirror validator bites when the derivation is wrong.

    Constructed directly rather than through :func:`capability_row`, because
    the builder cannot produce this state -- which is the point. If the
    validator agreed with the builder by construction it would never catch a
    defect inside the builder.
    """
    capability = _capability(ModeloWorkspaceCapabilityDisposition.REFUSED)
    wrong_glyph = disposition_glyph(ModeloWorkspaceCapabilityDisposition.AVAILABLE)

    with pytest.raises(ValidationError, match="glyph must be the one this disposition declares"):
        ModeloWorkspaceCapabilityRowV1(
            capability=capability.capability,
            disposition=capability.disposition,
            glyph=wrong_glyph,
            producer_owner=capability.producer_owner,
            producer=capability.producer,
            source=capability,
        )


def test_a_capability_row_cannot_restate_a_disposition_its_source_did_not_declare() -> None:
    """A row that disagrees with its retained source is refused outright."""
    capability = _capability(ModeloWorkspaceCapabilityDisposition.UNMEASURED)

    with pytest.raises(ValidationError, match="must mirror the producer's disposition"):
        ModeloWorkspaceCapabilityRowV1(
            capability=capability.capability,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            glyph=disposition_glyph(ModeloWorkspaceCapabilityDisposition.AVAILABLE),
            producer_owner=capability.producer_owner,
            producer=capability.producer,
            source=capability,
        )


def test_constraint_disclosure_keeps_unmeasured_apart_from_none_declared() -> None:
    """The None-versus-() distinction survives the narrowing, as a bool could not."""
    assert constraint_disclosure(None) == "unmeasured"
    assert constraint_disclosure(()) == "none_declared"
    assert constraint_disclosure((ModeloWorkspaceConstraintReferenceV1(casilla_id="0001"),)) == "declared"
    assert constraint_disclosure(None) != constraint_disclosure(())


def test_display_text_reports_a_registry_identifier_as_untranslated() -> None:
    """A technical identifier shown as itself must not claim to be a translation."""
    technical = display_text(ModeloWorkspaceTechnicalLabelV1(identifier="inventory-operation-0181"))

    assert technical.text == "inventory-operation-0181"
    assert technical.translated is False


def test_display_text_reports_a_localized_label_as_translated() -> None:
    localized = display_text(
        ModeloWorkspaceLocalizedTextV1(
            locale_key="casilla.0001.label",
            value="Base imponible",
            locale=ModeloWorkspaceLocaleSummaryV1(
                requested_language=OutputLanguage.ES,
                resolved_language=OutputLanguage.ES,
                disposition=ModeloWorkspaceLocaleDisposition.EXACT,
                catalogue_digest="a" * 64,
            ),
        )
    )

    assert localized.text == "Base imponible"
    assert localized.translated is True


def test_a_version_refusal_view_names_no_owner_it_does_not_have() -> None:
    """The pre-parse refusal carries neither owner nor condition, and says so."""
    view = refusal_view(ModeloWorkspaceVersionRefusalV1(requested_version=2))

    assert view.kind == "unsupported_version"
    assert view.responsible_owner is None
    assert view.reconsideration_condition is None


def test_a_domain_refusal_view_carries_the_owner_and_condition_verbatim() -> None:
    refusal = ModeloWorkspaceDomainRefusalV1(
        code=ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
        boundary="capability",
        requested_target=ModeloWorkspaceVisibleFilingTargetV1(
            target=ModeloVisibleFilingTarget(modelo="303", filing_year=2026, period="1T")
        ),
        responsible_owner="application.modelo.workspace",
        reconsideration_condition="calculate this work unit first",
    )

    view = refusal_view(refusal)

    assert view.kind == "domain"
    assert view.responsible_owner == "application.modelo.workspace"
    assert view.reconsideration_condition == "calculate this work unit first"
    assert view.source is refusal


def test_a_refusal_view_cannot_invent_an_owner_for_a_version_refusal() -> None:
    """Anti-tautology for the refusal mirror: a fabricated owner is refused."""
    refusal = ModeloWorkspaceVersionRefusalV1(requested_version=2)

    with pytest.raises(ValidationError, match="carries no owner or reconsideration condition"):
        ModeloWorkspaceRefusalViewV1(
            kind="unsupported_version",
            responsible_owner="someone",
            reconsideration_condition="something",
            source=refusal,
        )


def test_a_bounded_page_is_a_different_shape_from_a_complete_one() -> None:
    """An overflowing page cannot be rendered as though it were the whole set."""
    complete = ModeloWorkspaceCompletePageV1()
    bounded = ModeloWorkspaceBoundedPageV1(shown=200, page_size=200)

    assert complete.kind == "complete"
    assert bounded.kind == "bounded"
    assert complete.kind != bounded.kind


def test_a_bounded_page_cannot_claim_more_rows_than_its_page_size() -> None:
    with pytest.raises(ValidationError, match="cannot show more rows than its page size"):
        ModeloWorkspaceBoundedPageV1(shown=201, page_size=200)

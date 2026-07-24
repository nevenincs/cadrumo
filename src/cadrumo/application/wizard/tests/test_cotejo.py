"""Real-behaviour tests for the cotejo censal compare-select page family.

The whole cotejo family is unreachable live until a G313 specimen pins the
inbound parser (it refuses every document today), so these drive the
builders with a :class:`CertificadoSituacionCensal` constructed directly —
never a parsed PDF — exercising keep / adopt / defer against the real setup
flow catalogue and the real substrate FlowDefinition validators.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ....core.flows import DEFER_TOKEN, FlowWidgetKind
from ....core.wizard_catalogue import get_setup_flow
from ....domain.censo import ActividadLocalCertificada, CertificadoSituacionCensal
from .. import (
    COTEJO_SECTION_ID,
    attach_cotejo_pages,
    build_cotejo_pages,
    cotejo_axes,
    cotejo_outcome,
)
from .._commands import _setup_flow_definition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The only certificate axis with a wizard-answer counterpart today is the
# actividad description (certificate ``activities.description`` ↔ question
# ``activity``). Fiscal address and IAE epigraph are certified but carry no
# wizard question, so they are display-only evidence, never compare-select.
_ACTIVITY_QUESTION_ID = "activity"
_ACTIVITY_PATH = "activities.description"
_COTEJO_PAGE_ID = "cotejo-activity"


def _certificado(*, actividad: str = "Consultoria informatica", epigrafe: str = "899") -> CertificadoSituacionCensal:
    return CertificadoSituacionCensal(
        domicilio_fiscal="Calle Mayor 1, 28013 Madrid",
        condicion_residencia="Residente",
        actividades=(ActividadLocalCertificada(descripcion=actividad, epigrafe_iae=epigrafe),),
    )


def test_axis_built_only_when_answer_disagrees_with_certificate() -> None:
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    axes = cotejo_axes(flow, certificado, {_ACTIVITY_QUESTION_ID: "Diseno grafico"})
    assert len(axes) == 1
    axis = axes[0]
    assert axis.page_id == _COTEJO_PAGE_ID
    assert axis.domain_key == _ACTIVITY_PATH
    assert axis.flow_value == "Diseno grafico"
    assert axis.artefact_value == "Consultoria informatica"
    assert axis.source == PROVENANCE_SOURCE_CENSO_ARTEFACT


def test_no_axis_when_answer_matches_certificate() -> None:
    flow = get_setup_flow()
    certificado = _certificado(actividad="Diseno grafico")
    assert cotejo_axes(flow, certificado, {_ACTIVITY_QUESTION_ID: "Diseno grafico"}) == ()


@pytest.mark.parametrize(
    ("answer", "certificate"),
    [
        ("Consultoria informatica", "CONSULTORÍA INFORMÁTICA"),  # case + accents
        ("Consultoria informatica", "Consultoria  informatica "),  # collapsed + trailing whitespace
        ("consultoría informática", "CONSULTORIA INFORMATICA"),  # both directions
    ],
)
def test_no_false_divergence_on_case_accent_or_whitespace_variants(answer: str, certificate: str) -> None:
    """Operator prose vs PDF extraction must not spawn a page on a mere variant."""
    flow = get_setup_flow()
    certificado = _certificado(actividad=certificate)
    assert cotejo_axes(flow, certificado, {_ACTIVITY_QUESTION_ID: answer}) == ()


def test_genuinely_different_values_still_reconcile() -> None:
    """A real difference (not a case/accent/whitespace variant) still builds a page."""
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    axes = cotejo_axes(flow, certificado, {_ACTIVITY_QUESTION_ID: "Diseno grafico industrial"})
    assert len(axes) == 1


def test_adopt_routes_under_canonical_fold_never_a_spurious_keep() -> None:
    """A decision equal to the certificate under the fold adopts; the verbatim value persists."""
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    answers = {_ACTIVITY_QUESTION_ID: "Diseno grafico"}
    # The engine committed the adopt candidate in a whitespace-variant form;
    # the canonical fold still routes it to adopt, and the persisted value is
    # the verbatim certificate original.
    adopted, divergences = cotejo_outcome(flow, certificado, answers, {_COTEJO_PAGE_ID: "Consultoria  informatica "})
    assert divergences == ()
    assert [fact.value for fact in adopted] == ["Consultoria informatica"]


def test_no_axis_when_answer_absent() -> None:
    flow = get_setup_flow()
    assert cotejo_axes(flow, _certificado(), {}) == ()


def test_certificate_facts_without_wizard_counterpart_are_not_compare_pages() -> None:
    """Fiscal address is certified but has no wizard question, so no page."""
    flow = get_setup_flow()
    pages = build_cotejo_pages(flow, _certificado(), {_ACTIVITY_QUESTION_ID: "Diseno grafico"})
    domain_keys = {page.domain_key for page in pages}
    assert "contact.fiscal_address" not in domain_keys
    assert domain_keys == {_ACTIVITY_PATH}


def test_compare_page_shape_is_keep_plus_adopt_with_provenance() -> None:
    flow = get_setup_flow()
    pages = build_cotejo_pages(flow, _certificado(), {_ACTIVITY_QUESTION_ID: "Diseno grafico"})
    assert len(pages) == 1
    page = pages[0]
    assert page.widget is FlowWidgetKind.COMPARE_SELECT
    assert page.domain_key == _ACTIVITY_PATH
    assert [choice.value for choice in page.choices] == ["Diseno grafico", "Consultoria informatica"]
    # The COMPARE_SELECT construction validator requires provenance on every
    # candidate; both keep and adopt candidates carry it.
    assert all(choice.provenance is not None for choice in page.choices)
    # The reserved defer arm is engine-provided, never a declared choice.
    assert DEFER_TOKEN not in {choice.value for choice in page.choices}
    # Default keeps the operator's own answer, so an unattended walk adopts nothing.
    assert page.default == "Diseno grafico"


def test_adopt_decision_yields_provenance_stamped_fact() -> None:
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    answers = {_ACTIVITY_QUESTION_ID: "Diseno grafico"}
    adopted, divergences = cotejo_outcome(flow, certificado, answers, {_COTEJO_PAGE_ID: "Consultoria informatica"})
    assert divergences == ()
    assert len(adopted) == 1
    fact = adopted[0]
    assert fact.path == _ACTIVITY_PATH
    assert fact.value == "Consultoria informatica"
    assert fact.source == PROVENANCE_SOURCE_CENSO_ARTEFACT


def test_defer_decision_yields_divergence_only() -> None:
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    answers = {_ACTIVITY_QUESTION_ID: "Diseno grafico"}
    adopted, divergences = cotejo_outcome(flow, certificado, answers, {_COTEJO_PAGE_ID: DEFER_TOKEN})
    assert adopted == ()
    assert len(divergences) == 1
    divergence = divergences[0]
    assert divergence.axis == _ACTIVITY_PATH
    assert divergence.artefact_value == "Consultoria informatica"
    assert divergence.source == PROVENANCE_SOURCE_CENSO_ARTEFACT


def test_keep_decision_persists_nothing() -> None:
    flow = get_setup_flow()
    certificado = _certificado(actividad="Consultoria informatica")
    answers = {_ACTIVITY_QUESTION_ID: "Diseno grafico"}
    adopted, divergences = cotejo_outcome(flow, certificado, answers, {_COTEJO_PAGE_ID: "Diseno grafico"})
    assert adopted == ()
    assert divergences == ()


def test_attach_cotejo_pages_appends_valid_trailing_section() -> None:
    flow = get_setup_flow()
    answers = {_ACTIVITY_QUESTION_ID: "Diseno grafico"}
    # Building through the command splice seam exercises the full definition
    # decoration (bridge + format hints + legal validators + descendants +
    # cotejo) and its construction-time FlowDefinition validators.
    definition = _setup_flow_definition(flow, attach_descendants=True, certificado=_certificado(), flow_answers=answers)
    cotejo_sections = [section for section in definition.sections if section.id == COTEJO_SECTION_ID]
    assert len(cotejo_sections) == 1
    assert definition.sections[-1].id == COTEJO_SECTION_ID
    assert {page.id for page in cotejo_sections[0].items} == {_COTEJO_PAGE_ID}


def test_attach_cotejo_pages_is_a_noop_without_reconcilable_axes() -> None:
    flow = get_setup_flow()
    base = _setup_flow_definition(flow, attach_descendants=True)
    # A certificate that agrees with the answer produces no page and no section.
    agreed = _setup_flow_definition(
        flow,
        attach_descendants=True,
        certificado=_certificado(actividad="Diseno grafico"),
        flow_answers={_ACTIVITY_QUESTION_ID: "Diseno grafico"},
    )
    assert not any(section.id == COTEJO_SECTION_ID for section in agreed.sections)
    assert len(agreed.sections) == len(base.sections)


def test_empty_pages_attach_returns_definition_unchanged() -> None:
    flow = get_setup_flow()
    definition = _setup_flow_definition(flow, attach_descendants=True)
    assert attach_cotejo_pages(definition, ()) is definition

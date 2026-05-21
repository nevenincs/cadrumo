"""Real-behavior tests for ``build_overview_explain``.

The ``applicable`` flag is derived from the three-axis taxpayer model
(see :mod:`._applicability`), not from the deadline engine. These
tests pin the verdict for a declared autónomo and assert the service
boundary refusals; the per-persona derivation matrix lives in
:mod:`.test_applicability`.
"""

from __future__ import annotations

import pytest

from aeat.domain.deadlines import TaxpayerProfile
from aeat.domain.deadlines._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
)

from ._applicability import ApplicabilityVerdict
from ._errors import OverviewExplainError
from ._explain import OverviewExplain, build_overview_explain

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _autonomo_profile() -> TaxpayerProfile:
    """A declared autónomo en estimación directa (unchanged persona)."""

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
    )


def _undeclared_profile() -> TaxpayerProfile:
    """A profile with no taxpayer model declared at all."""

    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)


def test_explain_returns_typed_envelope_for_applicable_modelo() -> None:
    """A modelo the autónomo's taxpayer model triggers yields
    applicable=True, an APPLICABLE verdict, and grounded legal_refs."""

    result = build_overview_explain(_autonomo_profile(), modelo="303", year=2026)

    assert isinstance(result, OverviewExplain)
    assert result.modelo == "303"
    assert result.year == 2026
    assert result.applicable is True
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.rationale
    assert result.legal_refs  # applicability is registry-grounded.
    assert result.profile_facts["tax_id"] == "X1234567L"
    assert result.profile_facts["iva_regime"] == "GENERAL"
    assert result.profile_facts["entity_type"] == "natural_person"


def test_explain_refuses_unknown_modelo() -> None:
    """A modelo identifier the registry has no knowledge of surfaces as
    OverviewExplainError rather than an undeclared-profile case."""

    with pytest.raises(OverviewExplainError, match=r"could not evaluate"):
        build_overview_explain(_autonomo_profile(), modelo="999999", year=2026)


def test_explain_refuses_blank_modelo() -> None:
    """A blank modelo identifier is refused at the service boundary."""

    with pytest.raises(OverviewExplainError, match=r"no puede estar en blanco"):
        build_overview_explain(_autonomo_profile(), modelo="  ", year=2026)


def test_explain_profile_facts_surface_taxpayer_model_axes() -> None:
    """The profile_facts dict must include every taxpayer-model axis the
    applicability answer depends on, so the operator can audit them."""

    result = build_overview_explain(_autonomo_profile(), modelo="303", year=2026)

    for field in (
        "tax_id",
        "entity_type",
        "irpf_income_categories",
        "irpf_estimation_regime",
        "iva_regime",
        "has_employees",
    ):
        assert field in result.profile_facts, f"profile_facts missing {field}"
    # The income-category set is surfaced as a stable comma-joined token.
    assert result.profile_facts["irpf_income_categories"] == "actividad_economica"
    # Nested IVA sub-model facts must also be flattened.
    assert "iva.roi_enrolled" in result.profile_facts
    assert "iva.oss_enrolled" in result.profile_facts


def test_explain_undeclared_profile_yields_incomplete_verdict() -> None:
    """An undeclared taxpayer model yields an explicit INCOMPLETE
    verdict — never a confident wrong obligation."""

    result = build_overview_explain(_undeclared_profile(), modelo="130", year=2026)

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.applicable is False
    # The rationale is the "declare your taxpayer type first" guidance.
    assert "tipo de contribuyente" in result.rationale
    assert "config profile edit" in result.rationale
    # The verdict still carries grounding refs.
    assert result.legal_refs


def test_explain_degrades_gracefully_for_modelo_without_deadline_windows() -> None:
    """A known registry modelo with no deadline windows for the year
    still answers: the applicability verdict is derived from the
    taxpayer model and the scheduling rationale degrades to None.

    Modelo 100 (Renta) is a real registry modelo whose annual filing
    window is not registered for every year (registry-track gap R1).
    The applicability answer is unaffected — a natural person owes the
    Renta regardless of whether the deadline window is registered.
    """

    result = build_overview_explain(_autonomo_profile(), modelo="100", year=2026)

    assert isinstance(result, OverviewExplain)
    assert result.modelo == "100"
    # An autónomo is a natural person — Modelo 100 applies.
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.rationale
    # The scheduling rationale degrades to None when no window data exists.
    assert result.scheduling_rationale is None
    assert "tax_id" in result.profile_facts


def test_explain_unknown_modelo_still_raises_not_degrades() -> None:
    """A modelo identifier absent from the calculation registry must
    still raise OverviewExplainError — graceful degradation applies
    only to known modelos missing deadline-window data."""

    with pytest.raises(OverviewExplainError, match=r"could not evaluate"):
        build_overview_explain(_autonomo_profile(), modelo="999999", year=2026)


def test_explain_applicable_flag_matches_derived_verdict() -> None:
    """The applicable flag must equal the verdict-derived value: True
    only for an APPLICABLE verdict. explain and the operational views
    cannot diverge because both derive from the same rule table."""

    from ._applicability import derive_modelo_applicability

    profile = _autonomo_profile()
    result = build_overview_explain(profile, modelo="303", year=2026)
    derived = derive_modelo_applicability(profile, "303")

    assert result.applicable == derived.applicable
    assert result.verdict is derived.verdict

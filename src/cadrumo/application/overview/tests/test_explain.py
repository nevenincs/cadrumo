"""Real-behavior tests for ``build_overview_explain``.

The ``applicable`` flag is derived from the three-axis taxpayer model
(see :mod:`._applicability`), not from the deadline engine. These
tests pin the verdict for a declared autónomo and assert the service
boundary refusals; the per-persona derivation matrix lives in
:mod:`.test_applicability`.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ....core.calendar_shift import shift_by_calendar_years
from ....domain.calculations.registry.applicability import ApplicabilityVerdict
from ....domain.deadlines.models import EntityType, IVARegime, IrpfIncomeCategory, TaxpayerProfile
from ....domain.deadlines.recargo import twelve_month_anniversary
from ....domain.retention import TAX_RECORD_RETENTION_FLOOR_YEARS
from ..errors import OverviewExplainError
from ..explain import OverviewExplain, _out_of_plazo_warning, build_overview_explain
from .calendar_test_support import profile as _autonomo_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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


def test_explain_rejects_blank_legal_ref_payload() -> None:
    """OverviewExplain keeps applicability grounding on the typed registry-id contract."""

    result = build_overview_explain(_autonomo_profile(), modelo="303", year=2026)
    payload = result.model_dump(mode="json")
    payload["legal_refs"] = [" "]

    with pytest.raises(ValidationError, match="legal_refs"):
        OverviewExplain.model_validate(payload)


def test_explain_refuses_unknown_modelo() -> None:
    """A modelo identifier the registry has no knowledge of surfaces as
    OverviewExplainError rather than an undeclared-profile case."""

    with pytest.raises(OverviewExplainError):
        build_overview_explain(_autonomo_profile(), modelo="999999", year=2026)


def test_explain_refuses_blank_modelo() -> None:
    """A blank modelo identifier is refused at the service boundary."""

    with pytest.raises(OverviewExplainError) as excinfo:
        build_overview_explain(_autonomo_profile(), modelo="  ", year=2026)
    assert excinfo.value.translated_message == "application.overview.explain.errors.modelo_blank"


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
    assert "iva.group_member_enrolled" in result.profile_facts
    assert "iva.group_dominant_entity_enrolled" in result.profile_facts


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


def test_explain_historical_modelo_100_carries_out_of_plazo_warning() -> None:
    """A historical applicable return must say its voluntary filing window is closed.

    M100 for tax year 2022, evaluated in 2026, is still applicable for a
    natural person, but it is no longer an ordinary in-window filing. The warning
    is derived from the real registered Modelo 100 2022 deadline window.
    """

    result = build_overview_explain(_autonomo_profile(), modelo="100", year=2022, today=date(2026, 7, 7))

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.out_of_plazo_warning is not None
    assert "out_of_plazo" in result.out_of_plazo_warning
    assert "voluntary filing window closed on 2023-" in result.out_of_plazo_warning
    assert "four-year LGT arts. 66-67 prescription horizon" in result.out_of_plazo_warning


def test_explain_historical_warning_uses_the_recargo_anniversary_with_its_inclusive_boundary() -> None:
    """Overview warning starts on the same legal anniversary that recargo resolves."""
    closes_on = date(2023, 6, 30)
    anniversary = twelve_month_anniversary(closes_on)

    before = build_overview_explain(_autonomo_profile(), modelo="100", year=2022, today=anniversary - timedelta(days=1))
    on_anniversary = build_overview_explain(_autonomo_profile(), modelo="100", year=2022, today=anniversary)

    assert anniversary == date(2024, 6, 30)
    assert before.out_of_plazo_warning is None
    assert on_anniversary.out_of_plazo_warning is not None


def test_explain_historical_warning_uses_the_retention_prescription_boundary() -> None:
    closes_on = date(2023, 6, 30)
    prescription_boundary = shift_by_calendar_years(closes_on, TAX_RECORD_RETENTION_FLOOR_YEARS)

    on_boundary = build_overview_explain(_autonomo_profile(), modelo="100", year=2022, today=prescription_boundary)
    after_boundary = build_overview_explain(
        _autonomo_profile(),
        modelo="100",
        year=2022,
        today=prescription_boundary + timedelta(days=1),
    )

    assert prescription_boundary == date(2027, 6, 30)
    assert "inside the ordinary four-year" in (on_boundary.out_of_plazo_warning or "")
    assert "after the ordinary four-year" in (after_boundary.out_of_plazo_warning or "")


def test_explain_recent_modelo_100_does_not_emit_out_of_plazo_warning() -> None:
    """A just-closed M100 window is not the historical stale-year case."""

    result = build_overview_explain(_autonomo_profile(), modelo="100", year=2025, today=date(2026, 7, 7))

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.out_of_plazo_warning is None


def test_explain_unknown_modelo_still_raises_not_degrades() -> None:
    """A modelo identifier absent from the calculation registry must
    still raise OverviewExplainError — graceful degradation applies
    only to known modelos missing deadline-window data."""

    with pytest.raises(OverviewExplainError):
        build_overview_explain(_autonomo_profile(), modelo="999999", year=2026)


def test_explain_applicable_flag_matches_derived_verdict() -> None:
    """The applicable flag must equal the verdict-derived value: True
    only for an APPLICABLE verdict. explain and the operational views
    cannot diverge because both derive from the same rule table."""

    from ....domain.calculations.registry.applicability import derive_modelo_applicability

    profile = _autonomo_profile()
    result = build_overview_explain(profile, modelo="303", year=2026)
    derived = derive_modelo_applicability(profile, "303")

    assert result.applicable == derived.applicable
    assert result.verdict is derived.verdict


def test_explain_721_depends_on_crypto_abroad_threshold_fact() -> None:
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=True,
    )

    result = build_overview_explain(profile, modelo="721", year=2024)

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.profile_facts["bienes_extranjero_above_threshold"] is False
    assert result.profile_facts["monedas_virtuales_extranjero_above_threshold"] is True


def test_out_of_plazo_warning_delegates_its_date_arithmetic() -> None:
    """DISCRIMINATING: the warning must reach the canonical date helpers.

    Both retired local helpers AGREED with their canonical replacements on
    every date the suite exercises -- `_add_years(x, 1)` matches
    `twelve_month_anniversary` away from the leap edge, and `_add_years(x, 4)`
    matches `shift_by_calendar_years` at four years everywhere. Re-inlining the
    retired arithmetic therefore leaves every outcome assertion in this module
    green (measured: 14 passed with the duplicate restored), so no assertion on
    the warning's TEXT or its boundaries can defend this consolidation.

    The compiled name references can. A restated implementation names its own
    local helper and neither canonical one.
    """
    referenced = _out_of_plazo_warning.__code__.co_names

    assert "twelve_month_anniversary" in referenced, (
        "the twelve-month boundary must come from domain.deadlines."
        f"twelve_month_anniversary; referenced names were {referenced}"
    )
    assert "shift_by_calendar_years" in referenced, (
        "the prescription boundary must come from core.calendar_shift."
        f"shift_by_calendar_years; referenced names were {referenced}"
    )
    assert "TAX_RECORD_RETENTION_FLOOR_YEARS" in referenced, (
        "the four-year horizon must be read from the grounded retention "
        f"constant, not written as a literal; referenced names were {referenced}"
    )

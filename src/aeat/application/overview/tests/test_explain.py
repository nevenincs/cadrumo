"""Real-behavior tests for ``build_overview_explain``.

The ``applicable`` flag is derived from the three-axis taxpayer model
(see :mod:`._applicability`), not from the deadline engine. These
tests pin the verdict for a declared autónomo and assert the service
boundary refusals; the per-persona derivation matrix lives in
:mod:`.test_applicability`.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.applicability import ApplicabilityVerdict
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
)
from .._errors import OverviewExplainError
from .._explain import OverviewExplain, build_overview_explain

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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


def test_scheduling_rationale_propagates_genuine_registry_fault() -> None:
    """The public explain builder lets a genuine registry-integrity fault
    propagate after its catch was narrowed to ``NoDeadlineWindowsError``.

    Before the narrowing, the broad ``ScheduleComputationError`` catch
    swallowed a real registry validation failure as a benign "no window
    data" state, leaving the operator with a silently-missing
    scheduling rationale. The narrowed catch lets the genuine fault
    surface (round-4 #40)."""

    from ....domain.deadlines._errors import (
        NoDeadlineWindowsError,
        ScheduleComputationError,
    )

    class _CorruptRegistryEngine:
        """Raises the genuine registry-integrity fault on explain."""

        def explain(
            self,
            profile: TaxpayerProfile,
            modelo: str,
            *,
            year: int | None = None,
        ) -> str:
            raise ScheduleComputationError(
                "deadline registry validation failed",
            )

    # Deliberate fault-injection engine exercising the explain catch contract.
    with pytest.raises(ScheduleComputationError) as excinfo:
        build_overview_explain(
            _autonomo_profile(),
            modelo="303",
            year=2026,
            engine=_CorruptRegistryEngine(),
        )
    # The genuine fault is the bare base class, not the benign subtype.
    assert not isinstance(excinfo.value, NoDeadlineWindowsError)


def test_scheduling_rationale_degrades_on_benign_no_windows() -> None:
    """The benign no-windows fault still degrades to ``None`` through
    the public explain builder after the catch narrowing."""

    from ....domain.deadlines._errors import NoDeadlineWindowsError

    class _NoWindowsEngine:
        """Raises the benign no-windows fault on explain."""

        def explain(
            self,
            profile: TaxpayerProfile,
            modelo: str,
            *,
            year: int | None = None,
        ) -> str:
            raise NoDeadlineWindowsError(
                f"No registry deadline windows registered for modelo {modelo!r}",
            )

    # Deliberate fault-injection engine exercising the explain catch contract.
    result = build_overview_explain(
        _autonomo_profile(),
        modelo="303",
        year=2026,
        engine=_NoWindowsEngine(),
    )
    assert result.scheduling_rationale is None

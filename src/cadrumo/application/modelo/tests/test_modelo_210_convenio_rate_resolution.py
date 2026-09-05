"""M210 persona regression tests for ``_resolve_m210_rate``.

Covers the testimonial personas required by the M210 IRNR engine contract:

- Olivia (GB / general): the Convenio Art 6 row coincides with the
  TRLIRNR Art 25.1.a baseline rate (24%); the override path resolves
  to the same Decimal as the baseline. Exercises the real registry
  snapshot end-to-end.
- Khadija (MA / interest): the Convenio override REPLACES the TRLIRNR
  baseline. The real MA/interest Convenio row carries rate=0.10; the
  helper returns the override. A mutation-pair anti-tautology test
  rewrites the same row to rate=0.15 and asserts the helper picks the
  mutated value.
- Felipe (AR / pension): the real AR/pension Convenio row is grounded
  in Convenio Espana-Argentina Art 19 and carries ``DOMESTIC_TARIFF``;
  the base-aware calculation runtime applies the TRLIRNR Art 25.1.b
  progressive tariff.
- Non-Convenio fall-through (ZW): a country with no Convenio row at
  all fires the ``m210-convenio-rate-missing`` BLOCKING finding.
- No-treaty pension: the scalar helper returns no rate and no finding
  because the live tariff is non-flat and requires a base amount.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._m210_snapshot_fixture import m210_snapshot

__all__ = ["m210_snapshot"]

from ....core.irnr import ConvenioOverrideKind, TipoRentaIrnr
from ....domain.calculations.registry.convenio import ConvenioAuthority
from ....domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ....domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines.models import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFindingKind
from .._m210_rate import resolve_m210_rate as _resolve_m210_rate
from .._verification_predicates import evaluate_applicability_filter, evaluate_predicate_expression
from ..action_errors import ModeloApplicabilityFilterError
from ..verification_actions import (
    _evaluate_verification_predicates,
    _m210_unresolved_outcome_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _irnr_profile(country_code: str) -> TaxpayerProfile:
    """Build a NON_RESIDENT_IRNR profile for a non-EU/EEA country.

    GB / MA / AR / ZW are all outside the EU/EEA, so each profile
    needs a fiscal representative per TRLIRNR Art. 10.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence=country_code,
        representante_fiscal_nif="12345678Z",
        representante_fiscal_nombre="Test Representative",
    )


def _resident_profile() -> TaxpayerProfile:
    """Build a RESIDENT_IRPF profile with no ``country_of_fiscal_residence``.

    Used to exercise the deferred-baseline / no-treaty branch.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
    )


def _snapshot_with_mutated_convenio_row(
    base: RegistrySnapshot,
    *,
    country_code: str,
    tipo_renta: str,
    new_rate: str,
) -> RegistrySnapshot:
    """Return a copy of ``base`` with the (country, tipo_renta) treaty override rate replaced.

    Anti-tautology proof aid: prove the resolver reads the treaty
    authority rather than a constant by mutating an existing override
    row's rate field. Frozen pydantic models are duplicated via
    ``model_copy`` at row, treaty, authority, and snapshot levels.
    """

    tipo_enum = TipoRentaIrnr(tipo_renta)
    treaty = base.convenio.treaties[country_code]
    new_overrides = tuple(
        row.model_copy(update={"rate": new_rate}) if row.tipo_renta is tipo_enum else row for row in treaty.overrides
    )
    new_treaty = treaty.model_copy(update={"overrides": new_overrides})
    new_convenio = ConvenioAuthority(treaties={**base.convenio.treaties, country_code: new_treaty})
    return base.model_copy(update={"convenio": new_convenio})


def test_committed_convenio_rows_resolve_corrected_legal_anchors(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Committed treaty overrides cite the treaty article and, where needed, domestic rate law."""

    convenio = m210_snapshot.convenio

    gb_general = convenio.resolve("GB", TipoRentaIrnr.GENERAL, 2025)
    assert gb_general is not None
    assert gb_general.legal_refs == (
        "convenio-es-gb-2013:art-6",
        "trlirnr-rdleg-5-2004:art-25.1.a",
    )

    ma_interest = convenio.resolve("MA", TipoRentaIrnr.INTEREST, 2025)
    assert ma_interest is not None
    assert ma_interest.legal_refs == ("convenio-es-ma-1978:art-11",)

    ar_pension = convenio.resolve("AR", TipoRentaIrnr.PENSION, 2025)
    assert ar_pension is not None
    assert ar_pension.kind is ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF
    assert ar_pension.rate is None
    assert ar_pension.legal_refs == (
        "convenio-es-ar-1992:art-19",
        "trlirnr-rdleg-5-2004:art-25.1.b",
    )


def test_olivia_gb_general_resolves_convenio_override_matching_baseline(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Olivia (GB / general): Convenio Art 6 row coincides with the TRLIRNR baseline.

    The GB/general Convenio row carries ``rate="0.24"``, identical to
    the TRLIRNR Art 25.1.a baseline. The override path is exercised
    and resolves to the same Decimal as the baseline.
    """

    profile = _irnr_profile("GB")

    rate, findings = _resolve_m210_rate(profile, "general", 2025, m210_snapshot)

    assert rate == Decimal("0.24")
    assert findings == []


def test_khadija_ma_interest_convenio_override_replaces_baseline(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Khadija (MA / interest): real Convenio override REPLACES the baseline.

    The real MA/interest Convenio row carries ``rate="0.10"``. The
    helper resolves the (MA, interest) lookup against the real snapshot
    and returns the override rate, not the 19% TRLIRNR Art 25.1.f
    interest baseline. Replacement semantics are required, not stacking.
    """

    profile = _irnr_profile("MA")
    rate, findings = _resolve_m210_rate(profile, "interest", 2025, m210_snapshot)

    assert rate == Decimal("0.10")
    assert findings == []


def test_khadija_ma_interest_anti_tautology_mutation_pair(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Anti-tautology proof: helper reads the registry parameter, not a constant.

    Mutates the real MA/interest Convenio row to ``rate="0.15"``. The
    helper must return ``Decimal("0.15")``. If a future regression
    hardcoded the override rate to 0.10 (the registry value) or to the
    0.24 baseline, this assertion would fail.
    """

    snapshot = _snapshot_with_mutated_convenio_row(
        m210_snapshot,
        country_code="MA",
        tipo_renta="interest",
        new_rate="0.15",
    )

    profile = _irnr_profile("MA")
    rate, findings = _resolve_m210_rate(profile, "interest", 2025, snapshot)

    assert rate == Decimal("0.15")
    assert findings == []


def test_dividend_baseline_resolves_unconditional_art_25_1_f_rate(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Art. 25.1.f.1º dividends resolve the 19% baseline with no treaty country declared.

    Before the ``dividend`` tipo_renta category was added to the registry
    baseline table, this lookup returned ``(None, [])`` (deferred baseline
    coverage), and the modelo verification workflow converted a matching
    unresolved outcome into a BLOCKING finding rather than a rate. This
    proves the resolver now returns the unconditional 19% Art 25.1.f rate
    directly, with no findings.
    """

    profile = _resident_profile()
    rate, findings = _resolve_m210_rate(profile, "dividend", 2025, m210_snapshot)

    assert rate == Decimal("0.19")
    assert findings == []


def test_felipe_ar_pension_uses_domestic_tariff_without_blocking(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Felipe (AR / pension): treaty allocation delegates to the domestic tariff.

    The real AR/pension Convenio row is grounded in the Spain-Argentina
    treaty allocation article and carries ``DOMESTIC_TARIFF`` because the
    domestic TRLIRNR Art 25.1.b bracket table computes the amount. The scalar
    helper has no base amount in scope, so it returns ``rate is None`` without
    a blocking finding.
    """

    profile = _irnr_profile("AR")
    rate, findings = _resolve_m210_rate(profile, "pension", 2025, m210_snapshot)

    assert rate is None
    assert findings == []


def test_non_convenio_country_zw_general_emits_missing_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Zimbabwe (ZW / general): no Convenio row at all fires the missing-row branch.

    Zimbabwe is not in the Convenio seed; the lookup misses on
    ``(ZW, general)`` and the helper emits a BLOCKING finding with the
    ``m210-convenio-rate-missing`` predicate id.
    """

    profile = _irnr_profile("ZW")

    rate, findings = _resolve_m210_rate(profile, "general", 2025, m210_snapshot)

    assert rate is None
    assert len(findings) == 1
    finding = findings[0]
    assert finding.message_locale_key == "application.modelo.findings.m210_rate_unavailable"
    assert finding.message_facts["reason_code"] == "convenio_rate_missing"
    assert finding.message_facts["country_code"] == "ZW"
    assert finding.message_facts["tipo_renta_code"] == "general"


def test_resident_pension_uses_live_domestic_tariff_without_scalar_rate(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Resident persona / pension: live tariff is non-flat, so no scalar rate is returned.

    A profile with no ``country_of_fiscal_residence`` uses the domestic
    TRLIRNR Art 25.1.b tariff. The scalar helper cannot compute an effective
    rate without a base amount, but the presence of the live tariff means this
    is no longer a deferred-baseline blocking case.
    """

    profile = _resident_profile()
    rate, findings = _resolve_m210_rate(profile, "pension", 2025, m210_snapshot)

    assert rate is None
    assert findings == []


def _unresolved_rate_outcome(
    reason: RegistryUnresolvedOutcomeReason,
    *,
    tipo_renta: str = "general",
    country: str = "ZW",
) -> RegistryCalculationUnresolvedOutcome:
    """Build the typed M210 unresolved-rate outcome emitted by the formula runtime."""

    return RegistryCalculationUnresolvedOutcome(
        casilla_id="tipo_gravamen",
        reason=reason,
        formula_id="m210-tipo-gravamen-2025-resolve",
        op="irnr_resolve_tipo_gravamen",
        operand_refs=(
            "tipo_renta",
            "m210-tipo-gravamen-2025",
            "m210-2025-profile-country-of-fiscal-residence",
        ),
        operand_casilla_refs=("tipo_renta",),
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
        context={
            "tipo_renta": tipo_renta,
            "country": country,
            "filing_year": "2025",
            "baseline_parameter": "m210-tipo-gravamen-2025",
            "country_binding": "m210-2025-profile-country-of-fiscal-residence",
        },
    )


def test_m210_unresolved_outcome_findings_passes_through_empty_outcomes(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """No typed unresolved outcomes means no M210 verification finding."""

    findings = _m210_unresolved_outcome_findings(
        (),
        profile=_irnr_profile("GB"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="general",
    )

    assert findings == []


def test_m210_unresolved_outcome_findings_emits_convenio_missing_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A typed convenio-missing outcome emits the missing-row finding."""

    outcome = _unresolved_rate_outcome(RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING)
    findings = _m210_unresolved_outcome_findings(
        (outcome,),
        profile=_irnr_profile("ZW"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="general",
    )

    assert len(findings) == 1
    assert findings[0].casilla_id == outcome.casilla_id
    assert findings[0].message_facts["reason_code"] == "convenio_rate_missing"


def test_m210_unresolved_outcome_findings_emits_unknown_tipo_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A typed baseline-deferred outcome + unknown type emits a finding."""

    outcome = _unresolved_rate_outcome(
        RegistryUnresolvedOutcomeReason.M210_BASELINE_TIPO_DEFERRED,
        tipo_renta="royalty",
        country="",
    )
    findings = _m210_unresolved_outcome_findings(
        (outcome,),
        profile=_resident_profile(),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="royalty",
    )

    assert len(findings) == 1
    assert findings[0].casilla_id == outcome.casilla_id
    assert findings[0].message_facts["reason_code"] == "baseline_rate_unavailable"


def test_m210_unresolved_outcome_findings_omits_finding_when_rate_resolves(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A typed outcome paired with a resolvable Convenio row emits no finding."""

    findings = _m210_unresolved_outcome_findings(
        (
            _unresolved_rate_outcome(
                RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
                tipo_renta="interest",
                country="MA",
            ),
        ),
        profile=_irnr_profile("MA"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="interest",
    )

    assert findings == []


# ---------------------------------------------------------------------------
# representante-fiscal gate (profile_field_required operator)
#
# TRLIRNR Art 10 letter applies only to non-EU residents. Per
# m210-irnr-full-engine contract §D2.5: the implementation uses the broader
# ue_eee_status filter as the escape hatch — EEA-resident IRNR filers
# are exempt because of the bilateral mutual-assistance regime.
# ---------------------------------------------------------------------------


def _irnr_profile_without_representante(country_code: str) -> TaxpayerProfile:
    """Build a NON_RESIDENT_IRNR profile without a fiscal representative.

    EEA countries (e.g. FR) are exempt per contract D2.5 so the
    TaxpayerProfile model validator does not require the representante
    fields. For non-EEA countries (e.g. AR) the validator would refuse
    construction without ``representante_fiscal_nif``; callers that
    need that case build it via field-level assignment on a frozen
    copy or via ``model_construct``.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence=country_code,
    )


_REPRESENTANTE_PREDICATE_EXPRESSION = 'profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'


def test_representante_predicate_holds_for_eea_resident_without_representante() -> None:
    """EEA-resident IRNR profile is exempt; predicate holds despite missing representante."""

    profile = _irnr_profile_without_representante("FR")
    assert profile.ue_eee_status is True

    assert evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


def test_representante_predicate_holds_for_eea_resident_with_representante() -> None:
    """EEA-resident IRNR profile with a representante — rule does not apply; predicate holds."""

    profile = _irnr_profile("FR")  # carries representante_fiscal_nif
    assert profile.ue_eee_status is True

    assert evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


def test_representante_predicate_violated_for_non_eea_resident_without_representante() -> None:
    """Non-EEA IRNR profile without representante — rule applies; predicate violated."""

    profile = TaxpayerProfile.model_construct(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="AR",
        representante_fiscal_nif=None,
    )
    assert profile.ue_eee_status is False

    assert evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is False


def test_representante_predicate_holds_for_non_eea_resident_with_representante() -> None:
    """Non-EEA IRNR profile with representante — rule applies and is satisfied; predicate holds."""

    profile = _irnr_profile("AR")  # AR is non-EEA, _irnr_profile sets representante
    assert profile.ue_eee_status is False
    assert profile.representante_fiscal_nif == "12345678Z"

    assert evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


def test_representante_predicate_emits_blocking_finding_via_evaluator() -> None:
    """The M210 representante predicate fires a BLOCKING_RULE finding with TRLIRNR Art 10 cited."""

    predicate = VerificationPredicateDefinition(
        predicate_id="m210-representante-fiscal-required",
        legal_refs=("trlirnr-rdleg-5-2004:art-10",),
        expression=_REPRESENTANTE_PREDICATE_EXPRESSION,
        finding_kind="BLOCKING_RULE",
    )
    profile = TaxpayerProfile.model_construct(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="AR",
        representante_fiscal_nif=None,
    )

    findings = _evaluate_verification_predicates((predicate,), {}, profile)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
    assert finding.message_facts["predicate_id"] == "m210-representante-fiscal-required"
    assert "trlirnr-rdleg-5-2004:art-10" in finding.legal_refs


def test_applicability_filter_unknown_name_raises_value_error() -> None:
    """An unknown applicability filter raises ValueError rather than silently passing.

    Anti-tautology proof: the dispatch path is the single source of
    truth for applicability filters; a typo or an absent entry must
    surface loudly. If this test ever passes with the dispatch table
    bypassed (e.g. a generic ``return True`` catch-all), every
    applicability-gated predicate would silently no-op.
    """

    profile = _irnr_profile("AR")
    with pytest.raises(ModeloApplicabilityFilterError, match="Unknown applicability filter"):
        evaluate_applicability_filter("non_resident_irnr_eea_only", profile)

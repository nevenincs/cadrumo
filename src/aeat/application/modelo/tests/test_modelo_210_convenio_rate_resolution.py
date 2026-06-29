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

from ....core.resources import resources
from ....domain.calculations.registry import (
    M210_CONVENIO_MISSING_SENTINEL,
    M210_DEFERRED_TIPO_SENTINEL,
    CasillaId,
    CasillaObservation,
    RegistrySnapshot,
)
from ....domain.calculations.registry._schema import VerificationPredicateDefinition
from ....domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
)
from .. import ModeloApplicabilityFilterError
from .._m210_rate import resolve_m210_rate as _resolve_m210_rate
from .._verification_actions import (
    _evaluate_applicability_filter,
    _evaluate_predicate_expression,
    _evaluate_verification_predicates,
    _rewrite_m210_sentinels,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _irnr_profile(country_code: str) -> TaxpayerProfile:
    """Build a NON_RESIDENT_IRNR profile for a non-EU/EEA country.

    GB / MA / AR / ZW are all outside the EU/EEA, so each profile
    needs a fiscal representative per Art. 47 LGT + Art. 10 TRLIRNR.
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
    """Return a copy of ``base`` with the (country, tipo_renta) row's rate replaced.

    Anti-tautology proof aid: prove the helper reads the registry
    parameter rather than a constant by mutating an existing row's
    rate field. Frozen pydantic models are duplicated via
    ``model_copy`` at row, parameter, revision, and snapshot levels.
    """

    convenio_param = next(p for p in base.revision.parameters if p.id == "m210-convenio-rates")
    new_rows = tuple(
        row.model_copy(update={"rate": new_rate})
        if row.country_code == country_code and row.tipo_renta == tipo_renta
        else row
        for row in convenio_param.convenio_rates
    )
    new_param = convenio_param.model_copy(update={"convenio_rates": new_rows})
    new_parameters = tuple(new_param if p.id == "m210-convenio-rates" else p for p in base.revision.parameters)
    new_revision = base.revision.model_copy(update={"parameters": new_parameters})
    return base.model_copy(update={"revision": new_revision})


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Authority-resolved M210 / 2025 / evento snapshot."""

    return resources().modelos.authority.snapshot("210", filing_year=2025, period="evento")


def test_committed_convenio_rows_resolve_corrected_legal_anchors(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Committed concrete convenio rows cite the treaty article and, where needed, domestic rate law."""

    convenio_param = next(p for p in m210_snapshot.revision.parameters if p.id == "m210-convenio-rates")
    rows = {(row.country_code, row.tipo_renta): row for row in convenio_param.convenio_rates}

    gb_general = rows[("GB", "general")]
    assert gb_general.legal_ref_anchor == "convenio-es-gb-2013:art-6"
    assert gb_general.legal_refs == (
        "convenio-es-gb-2013:art-6",
        "trlirnr-rdleg-5-2004:art-25.1.a",
    )

    ma_interest = rows[("MA", "interest")]
    assert ma_interest.legal_ref_anchor == "convenio-es-ma-1978:art-11"
    assert ma_interest.legal_refs == ("convenio-es-ma-1978:art-11",)

    ar_pension = rows[("AR", "pension")]
    assert ar_pension.rate == "DOMESTIC_TARIFF"
    assert ar_pension.legal_ref_anchor == "convenio-es-ar-1992:art-19"
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
    assert "m210-convenio-rate-missing" in finding.message
    message_lower = finding.message.lower()
    assert "zw" in message_lower
    assert "general" in message_lower


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


def _observation(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    """Build a minimal CasillaObservation carrying just a casilla_id + value."""

    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
    )


def test_rewrite_m210_sentinels_passes_through_non_sentinel_observations(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Observations carrying real rates / zero values pass through unchanged."""

    observations = (
        _observation("base_imponible", Decimal("12000")),
        _observation("tipo_gravamen", Decimal("0.24")),
        _observation("cuota_integra", Decimal("2880.00")),
    )
    rewritten, findings = _rewrite_m210_sentinels(
        observations,
        profile=_irnr_profile("GB"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="general",
    )

    assert rewritten == observations
    assert findings == []


def test_rewrite_m210_sentinels_replaces_convenio_missing_sentinel(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A CONVENIO_MISSING sentinel is rewritten and the missing-row finding is emitted."""

    observations = (_observation("tipo_gravamen", M210_CONVENIO_MISSING_SENTINEL),)
    rewritten, findings = _rewrite_m210_sentinels(
        observations,
        profile=_irnr_profile("ZW"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="general",
    )

    assert rewritten[0].value == Decimal("0")
    assert len(findings) == 1
    assert "m210-convenio-rate-missing" in findings[0].message


def test_rewrite_m210_sentinels_replaces_unknown_tipo_sentinel(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A DEFERRED_TIPO sentinel + unknown no-treaty type rewrites to zero and emits a finding."""

    observations = (_observation("tipo_gravamen", M210_DEFERRED_TIPO_SENTINEL),)
    rewritten, findings = _rewrite_m210_sentinels(
        observations,
        profile=_resident_profile(),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="royalty",
    )

    assert rewritten[0].value == Decimal("0")
    assert len(findings) == 1
    assert "m210-baseline-tipo-deferred" in findings[0].message


def test_rewrite_m210_sentinels_resolves_known_rate_in_place(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """A sentinel observation paired with a resolvable Convenio row rewrites to the real rate.

    Khadija (MA / interest) has a real 0.10 Convenio row. If the
    engine emitted a sentinel for any reason (e.g. text_inputs were
    not yet threaded into the application calculation path), the
    verification sweep would re-resolve and rewrite the observation
    to the canonical rate without emitting a BLOCKING finding.
    """

    observations = (_observation("tipo_gravamen", M210_CONVENIO_MISSING_SENTINEL),)
    rewritten, findings = _rewrite_m210_sentinels(
        observations,
        profile=_irnr_profile("MA"),
        snapshot=m210_snapshot,
        year=2025,
        tipo_renta="interest",
    )

    assert rewritten[0].value == Decimal("0.10")
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

    assert _evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


def test_representante_predicate_holds_for_eea_resident_with_representante() -> None:
    """EEA-resident IRNR profile with a representante — rule does not apply; predicate holds."""

    profile = _irnr_profile("FR")  # carries representante_fiscal_nif
    assert profile.ue_eee_status is True

    assert _evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


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

    assert _evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is False


def test_representante_predicate_holds_for_non_eea_resident_with_representante() -> None:
    """Non-EEA IRNR profile with representante — rule applies and is satisfied; predicate holds."""

    profile = _irnr_profile("AR")  # AR is non-EEA, _irnr_profile sets representante
    assert profile.ue_eee_status is False
    assert profile.representante_fiscal_nif == "12345678Z"

    assert _evaluate_predicate_expression(_REPRESENTANTE_PREDICATE_EXPRESSION, {}, profile) is True


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
    assert "m210-representante-fiscal-required" in finding.message
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
        _evaluate_applicability_filter("non_resident_irnr_eea_only", profile)

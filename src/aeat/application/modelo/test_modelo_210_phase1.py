"""M210 Phase 1 persona regression tests for ``_resolve_m210_rate``.

Covers the Phase 1 testimonial personas required by the
m210-irnr-full-engine ADR (§D2.4):

- Olivia (GB / general): the Convenio Art 7 row coincides with the
  TRLIRNR Art 25.1.a baseline rate (24%); the override path resolves
  to the same Decimal as the baseline. Exercises the real registry
  snapshot end-to-end.
- Khadija (MA / interest): the Convenio override REPLACES the TRLIRNR
  baseline. The real MA/interest Convenio row authored under S389b
  carries rate=0.10; the helper returns the override. A mutation-pair
  anti-tautology test rewrites the same row to rate=0.15 and asserts
  the helper picks the mutated value.
- Felipe (AR / pension): the real AR/pension Convenio row carries
  ``NOT_YET_AUTHORED``; the helper emits the
  ``m210-convenio-rate-not-yet-authored`` BLOCKING finding. The
  ``pension`` baseline row stays absent per task #229 corpus-blocking;
  this case exercises the patched helper's "baseline absent BUT
  Convenio override exists" branch (post-S401).
- Non-Convenio fall-through (ZW): a country with no Convenio row at
  all fires the ``m210-convenio-rate-missing`` BLOCKING finding.
- Deferred-baseline / no-treaty (resident persona, ``pension``): a
  profile with no ``country_of_fiscal_residence`` cannot fall back to
  a Convenio override; the patched helper emits the
  ``m210-baseline-tipo-deferred`` BLOCKING finding (post-S401 branch).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.application.modelo._actions import _resolve_m210_rate
from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    ConvenioRateRow,
    RegistrySnapshot,
)
from aeat.domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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

    convenio_param = next(
        p for p in base.revision.parameters if p.id == "m210-convenio-rates"
    )
    new_rows = tuple(
        row.model_copy(update={"rate": new_rate})
        if row.country_code == country_code and row.tipo_renta == tipo_renta
        else row
        for row in convenio_param.convenio_rates
    )
    new_param = convenio_param.model_copy(update={"convenio_rates": new_rows})
    new_parameters = tuple(
        new_param if p.id == "m210-convenio-rates" else p
        for p in base.revision.parameters
    )
    new_revision = base.revision.model_copy(update={"parameters": new_parameters})
    return base.model_copy(update={"revision": new_revision})


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Authority-resolved M210 / 2025 / evento snapshot."""

    return resources().modelos.authority.snapshot(
        "210", filing_year=2025, period="evento"
    )


def test_olivia_gb_general_resolves_convenio_override_matching_baseline(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Olivia (GB / general): Convenio Art 7 row coincides with the TRLIRNR baseline.

    The GB/general Convenio row authored in S389b carries ``rate="0.24"``,
    identical to the TRLIRNR Art 25.1.a baseline. The override path is
    exercised (country_of_fiscal_residence is non-None) and resolves to
    the same Decimal as the baseline.
    """

    profile = _irnr_profile("GB")

    rate, findings = _resolve_m210_rate(profile, "general", 2025, m210_snapshot)

    assert rate == Decimal("0.24")
    assert findings == []


def test_khadija_ma_interest_convenio_override_replaces_baseline(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Khadija (MA / interest): real Convenio override REPLACES the baseline.

    The real MA/interest Convenio row authored in S389b carries
    ``rate="0.10"``. The helper resolves the (MA, interest) lookup
    against the real snapshot and returns the override rate, NOT the
    24% TRLIRNR Art 25.1.a interest baseline added in S401. Replacement
    semantics per ADR §D2.4 (not stacking).
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


def test_felipe_ar_pension_not_yet_authored_emits_blocking_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Felipe (AR / pension): real ``NOT_YET_AUTHORED`` sentinel fires a BLOCKING finding.

    The real AR/pension Convenio row authored in S389b carries the
    ``NOT_YET_AUTHORED`` placeholder. The helper recognises the
    sentinel, returns ``(None, [finding])`` and surfaces the
    ``m210-convenio-rate-not-yet-authored`` predicate id. The
    ``pension`` baseline row remains absent under task #229
    corpus-blocking; this test exercises the patched
    "baseline absent BUT Convenio override exists" branch (S401).
    """

    profile = _irnr_profile("AR")
    rate, findings = _resolve_m210_rate(profile, "pension", 2025, m210_snapshot)

    assert rate is None
    assert len(findings) == 1
    finding = findings[0]
    assert "m210-convenio-rate-not-yet-authored" in finding.message
    message_lower = finding.message.lower()
    assert "ar" in message_lower
    assert "pension" in message_lower


def test_non_convenio_country_zw_general_emits_missing_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Zimbabwe (ZW / general): no Convenio row at all fires the missing-row branch.

    Zimbabwe is not in the Phase 1 Convenio seed; the lookup misses
    on ``(ZW, general)`` and the helper emits a BLOCKING finding with
    the ``m210-convenio-rate-missing`` predicate id. This branch is
    distinct from the ``NOT_YET_AUTHORED`` branch and must surface
    a different predicate id.
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


def test_resident_pension_deferred_baseline_emits_blocking_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Resident persona / pension: deferred-baseline + no treaty fires BLOCKING.

    A profile with no ``country_of_fiscal_residence`` cannot claim a
    Convenio override; when the requested ``tipo_renta`` (pension) has
    no baseline row under the task #229 corpus-blocking deferral, the
    patched helper emits the ``m210-baseline-tipo-deferred`` BLOCKING
    finding (S401 branch). The rate slot is ``None``.
    """

    profile = _resident_profile()
    rate, findings = _resolve_m210_rate(profile, "pension", 2025, m210_snapshot)

    assert rate is None
    assert len(findings) == 1
    finding = findings[0]
    assert "m210-baseline-tipo-deferred" in finding.message
    message_lower = finding.message.lower()
    assert "pension" in message_lower

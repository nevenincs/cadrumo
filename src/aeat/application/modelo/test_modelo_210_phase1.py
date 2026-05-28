"""M210 Phase 1 persona regression tests for ``_resolve_m210_rate``.

Covers the Phase 1 testimonial personas required by the
m210-irnr-full-engine ADR (§D2.4):

- Olivia (GB / general): the Convenio Art 7 row coincides with the
  TRLIRNR Art 25.1.a baseline rate (24%); the override path resolves
  to the same Decimal as the baseline. Exercises the real registry
  snapshot end-to-end.
- Khadija (MA): the Convenio override REPLACES the TRLIRNR baseline.
  A snapshot-mutation pair proves the test reads the registry
  parameter rather than a hardcoded expectation (anti-tautology).
- Felipe (AR): the ``NOT_YET_AUTHORED`` placeholder fires the
  ``m210-convenio-rate-not-yet-authored`` BLOCKING finding; the
  rate slot is ``None``.
- Non-Convenio fall-through (ZW): a country with no Convenio row at
  all fires the ``m210-convenio-rate-missing`` BLOCKING finding.

Implementation note on the snapshot surface
-------------------------------------------

The helper short-circuits to ``(None, [])`` when the
``m210-tipo-gravamen-2025`` baseline parameter has no row for the
requested ``tipo_renta`` — that gate runs BEFORE the Convenio table
is consulted. The Phase 1 baseline table only declares rows for
``general`` / ``ue_residente`` / ``ganancia_patrimonial`` /
``inmobiliaria``; ``interest`` / ``pension`` (the tipos the
testimonial personas Khadija and Felipe file under in the real-world
narrative) are not yet authored on the baseline side. To exercise
the Convenio-override branches for the Khadija and Felipe personas
without depending on baseline rows that S389b did not author, the
mutation surface adds a synthetic ``(country, "general")`` Convenio
row on top of the real snapshot. The mutation pattern is the
ADR-endorsed "construct a minimal mutated snapshot inline" form, and
gives the Phase 1 personas a real exercise of the Convenio code paths
under the real registry's baseline coverage.
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


def _snapshot_with_extra_convenio_row(
    base: RegistrySnapshot, extra: ConvenioRateRow
) -> RegistrySnapshot:
    """Return a copy of ``base`` with an additional Convenio row appended.

    The original parameter (and its legal_refs / source_refs) is
    preserved; the new row joins ``convenio_rates`` so the helper
    finds it on lookup. Frozen pydantic models are duplicated via
    ``model_copy`` at parameter, revision, and snapshot levels.
    """

    convenio_param = next(
        p for p in base.revision.parameters if p.id == "m210-convenio-rates"
    )
    new_rows = (*convenio_param.convenio_rates, extra)
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


def test_khadija_ma_general_convenio_override_replaces_baseline(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Khadija (MA / general): Convenio override REPLACES the TRLIRNR baseline.

    Adds a synthetic MA/general Convenio row at 10% on top of the real
    snapshot. The helper resolves the (MA, general) lookup against the
    mutated parameter and returns the override rate, NOT the 24%
    baseline. Replacement semantics per ADR §D2.4 (not stacking).
    """

    extra = ConvenioRateRow(
        country_code="MA",
        tipo_renta="general",
        rate="0.10",
        legal_ref_anchor="boe-a-1985-13340",
        notes="synthetic Convenio España-Marruecos override for general tipo_renta",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    snapshot = _snapshot_with_extra_convenio_row(m210_snapshot, extra)

    profile = _irnr_profile("MA")
    rate, findings = _resolve_m210_rate(profile, "general", 2025, snapshot)

    assert rate == Decimal("0.10")
    assert findings == []


def test_khadija_ma_general_anti_tautology_mutation_pair(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Anti-tautology proof: helper reads the registry parameter, not a constant.

    Same shape as the Khadija happy-path test but with the MA/general
    Convenio rate set to ``"0.15"`` instead of ``"0.10"``. The helper
    must return ``Decimal("0.15")``. If a future regression hardcoded
    the override rate to 0.10 (or to the baseline 0.24), this
    assertion would fail.
    """

    extra = ConvenioRateRow(
        country_code="MA",
        tipo_renta="general",
        rate="0.15",
        legal_ref_anchor="boe-a-1985-13340",
        notes="anti-tautology mutation: rate replaced with 0.15",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    snapshot = _snapshot_with_extra_convenio_row(m210_snapshot, extra)

    profile = _irnr_profile("MA")
    rate, findings = _resolve_m210_rate(profile, "general", 2025, snapshot)

    assert rate == Decimal("0.15")
    assert findings == []


def test_felipe_ar_general_not_yet_authored_emits_blocking_finding(
    m210_snapshot: RegistrySnapshot,
) -> None:
    """Felipe (AR / general): the ``NOT_YET_AUTHORED`` sentinel fires a BLOCKING finding.

    Adds a synthetic AR/general Convenio row carrying the
    ``NOT_YET_AUTHORED`` placeholder on top of the real snapshot. The
    helper recognises the sentinel, returns ``(None, [finding])`` and
    surfaces the ``m210-convenio-rate-not-yet-authored`` predicate id
    in the finding message. The rate slot is ``None`` so downstream
    formula evaluation cannot proceed until the row is authored.
    """

    extra = ConvenioRateRow(
        country_code="AR",
        tipo_renta="general",
        rate="NOT_YET_AUTHORED",
        legal_ref_anchor="BOE-CONVENIO-AR-NOT-FOUND",
        notes="synthetic Convenio España-Argentina placeholder for general tipo_renta",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    snapshot = _snapshot_with_extra_convenio_row(m210_snapshot, extra)

    profile = _irnr_profile("AR")
    rate, findings = _resolve_m210_rate(profile, "general", 2025, snapshot)

    assert rate is None
    assert len(findings) == 1
    finding = findings[0]
    assert "m210-convenio-rate-not-yet-authored" in finding.message
    message_lower = finding.message.lower()
    assert "ar" in message_lower
    assert "general" in message_lower


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

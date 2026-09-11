"""Tests for Modelo 303 monthly snapshots and filing-schedule applicability."""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from ._modelo_303_registry_support import (
    load_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_monthly_snapshot_resolves_for_each_period() -> None:
    """Each explicit current record-design revision resolves its monthly periods.

    REDEME and large-company taxpayers use monthly Modelo 303 schedules. The
    revision selector still has to resolve those monthly periods directly
    via select_revision so ``bindings list --period 01`` resolves without a
    RegistrySnapshotError."""
    modelo, catalogues = load_modelo_303()

    for period in ("01", "06", "12"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2025"
        schedule_ids = {s.id for s in snapshot.revision.filing_schedules}
        assert "modelo-303-mensual" in schedule_ids, f"monthly schedule absent for period {period}"


def test_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles() -> None:
    """The monthly schedule fires for monthly IVA-liquidation triggers only."""
    from ....deadlines.models import (
        IVARegime,
        M303RegimeComposition,
        M303TaxTerritory,
        ModeloEnrollment,
        ModeloIVAProfile,
        TaxpayerProfile,
    )
    from ..schedules import applicable_filing_schedules

    modelo, _catalogues = load_modelo_303()
    revision = modelo.revisions["2025"]

    monthly_profiles = (
        TaxpayerProfile(
            tax_id="B12345674",
            iva_regime=IVARegime.GENERAL,
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
                redeme_enrolled=True,
            ),
        ),
        TaxpayerProfile(
            tax_id="C12345674",
            iva_regime=IVARegime.GENERAL,
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                redeme_enrolled=False,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
            enrollment=ModeloEnrollment(large_company=True),
        ),
    )
    voluntary_sii_profile = TaxpayerProfile(
        tax_id="A12345674",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=True,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            sii_enrolled=True,
            redeme_enrolled=False,
        ),
        enrollment=ModeloEnrollment(large_company=False),
    )
    ordinary_quarterly_profile = TaxpayerProfile(
        tax_id="D98765431",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            sii_enrolled=False,
            redeme_enrolled=False,
        ),
        enrollment=ModeloEnrollment(large_company=False),
    )

    for profile in monthly_profiles:
        monthly_schedules = applicable_filing_schedules(revision, profile)
        monthly_ids = {s.id for s in monthly_schedules}
        assert "modelo-303-mensual" in monthly_ids
        assert "modelo-303-trimestral" not in monthly_ids

    for profile in (voluntary_sii_profile, ordinary_quarterly_profile):
        quarterly_schedules = applicable_filing_schedules(revision, profile)
        quarterly_ids = {s.id for s in quarterly_schedules}
        assert "modelo-303-trimestral" in quarterly_ids, "quarterly schedule must match non-monthly profile"
        assert "modelo-303-mensual" not in quarterly_ids, "monthly schedule must NOT match non-monthly profile"

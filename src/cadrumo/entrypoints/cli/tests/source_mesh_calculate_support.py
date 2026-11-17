"""Shared operator profile, work-unit creators and seeders for the source-mesh calculation CLI tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.core.period import Period
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli
from .source_mesh_calculate_transactions import (
    ledger_raw_transaction,
    m100_activity_income_transaction,
)

# Every seeded ledger row is booked on one day, so the operator's activity, its
# Modelo 303 quarter and its withholding quarters open in that row's year.
ACTIVITY_YEAR = ledger_raw_transaction("activity-year", amount=Decimal("0")).booked_date.year
IVA_WALLET_DECIDED_AT = datetime(ACTIVITY_YEAR, 4, 1, 16, 10, tzinfo=UTC)
PROFILE_LABEL = "operator"
OPERATOR_FACTS: dict[str, str] = {
    "identity.tax_id": "12345678Z",
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Operator",
    "identity.surnames": "Operator",
    "activities.description": "design",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "censo.activity_start_date": date(ACTIVITY_YEAR, 1, 1).isoformat(),
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    # Not a gran empresa, so the 303 and the withholding modelos are quarterly
    # (RIVA art. 71.3, RIRPF art. 108.1).
    "censo.large_company": "false",
    # The operator pays an employee and a rented workshop with retencion, so the
    # payer modelos 111, 115, 180 and 190 apply to the profile.
    "withholding.has_employees": "true",
    "withholding.pays_rent_with_retencion": "true",
}
# The renta facts a Modelo 100 calculation reads from the profile.
M100_FACTS: dict[str, str] = {
    "tax_residence.ccaa": "madrid",
    "irpf.estimation_regime": "directa_normal",
    # An epigraph outside the urban-rental group (RIRPF art. 75), so the rental-activity
    # withholding is a proven absence rather than an unknown.
    "activities.iae_epigraph": "844",
    # The activity began before any supported year, so no exercise is its first.
    "censo.activity_start_date": date(filing_year_envelope().floor - 1, 1, 1).isoformat(),
    "renta_taxpayer.birth_date": "1980-03-15",
    "renta_taxpayer.sex": "H",
    "renta_taxpayer.marital_status": "1",
    "renta_taxpayer.marriage_full_year": "false",
    "renta_taxpayer.marriage_month_start": "0",
    "renta_taxpayer.marriage_month_end": "0",
    "renta_filing.declaration_type": "1",
    "renta_family.minor_children_in_unit": "false",
    "renta_family.descendientes_count": "0",
    "renta_family.descendants_eu_eea_deduction": "false",
}


@contextmanager
def operator_profile(tmp_path: Path, extra_facts: dict[str, str] | None = None) -> Generator[RegisteredCliProfile]:
    """Register the operator profile and serve it through its native worker.

    ``extra_facts`` carries per-modelo attestations that readiness demands of
    that modelo alone, so the shared profile stays minimal.
    """
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(label=PROFILE_LABEL, facts={**OPERATOR_FACTS, **(extra_facts or {})})
        yield profile


def cli(profile: RegisteredCliProfile, *args: str) -> Result:
    """Run one CLI command authenticated as the operator, as a fresh process would."""
    close_active_bucket_session()
    result = invoke_joined_cli(
        ["--profile", PROFILE_LABEL, "--profile-secrets-stdin", *args],
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


@contextmanager
def opened_profile(profile: RegisteredCliProfile, operation: PinnedAuthorityOperation) -> Generator[str]:
    """Open the registered profile's encrypted bucket for direct seeding or assertions."""
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=PROFILE_LABEL,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    try:
        yield login.bucket_id
    finally:
        close_active_bucket_session()


def create_work_unit(profile: RegisteredCliProfile, *, modelo: str, year: int, period: str) -> dict[str, str]:
    """Create a work unit and let the registry authority pick the revision.

    No ``--revision`` is injected. AEAT binds each ``(modelo, filing_year,
    period)`` triple to exactly one revision by published orden, so the
    revision is a derived fact and creation accepts an explicit id only when
    it equals that resolution. Pinning a literal here buys nothing and goes
    stale the moment a new revision opens: these fixtures previously pinned
    M303 to an obsolete revision for 2026, which began refusing outright
    once the 2026 revision shipped and capped that window at 2025-12-31.
    """
    result = cli(
        profile,
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        modelo,
        "--year",
        str(year),
        "--period",
        period,
    )
    assert result.exit_code == 0, result.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(unwrap_schema_envelope(result.output))
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return {"work_unit_id": work_unit_id}


def create_303_work_unit(profile: RegisteredCliProfile) -> dict[str, str]:
    return create_work_unit(profile, modelo="303", year=ACTIVITY_YEAR, period="1T")


def create_115_work_unit(profile: RegisteredCliProfile, *, year: int, period: str = "1T") -> dict[str, str]:
    return create_work_unit(profile, modelo="115", year=year, period=period)


def create_111_work_unit(profile: RegisteredCliProfile) -> dict[str, str]:
    return create_work_unit(profile, modelo="111", year=ACTIVITY_YEAR, period="2T")


def create_180_work_unit(profile: RegisteredCliProfile) -> dict[str, str]:
    return create_work_unit(profile, modelo="180", year=filing_year_envelope().horizon, period="0A")


def capture_m115_invoice_withholding(profile: RegisteredCliProfile) -> None:
    """Capture one received urban-rent invoice's retención as first-quarter Modelo 115 evidence.

    ``ledger invoice add`` mints a received rent invoice (2700.00 base, 19%
    retención = 513.00), then ``modelo aggregate --received-invoice-retencion``
    records its single paid allocation with the property detail Modelo 180
    requires. The settlement is the invoice grand total (2700.00 + 21% IVA =
    3267.00) less the retención: 2754.00.
    """
    paid_on = date(ACTIVITY_YEAR, 3, 15)
    created = cli(
        profile,
        "--format", "json",
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", "Arrendador Ejemplo SL",
        "--counterparty-nif", "B00015016",
        "--invoice-number", f"M115-RENT-{paid_on.year}-001",
        "--invoice-date", paid_on.isoformat(),
        "--country-code", "ES",
        "--taxable-base", "2700.00", "--iva-rate", "21",
        "--retention-rate", "0.19", "--retention-amount", "513.00",
        "--iva-category", "domestic_general",
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    invoice_id = unwrap_schema_envelope(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output

    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice_id,
        income_kind=WithholdingIncomeKind.URBAN_RENT,
        scheme="arrendamiento_urbano",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=f"m115-rent-payment-{paid_on.isoformat()}",
        payment_occurred_on=paid_on,
        allocation_id="m115-rent-allocation-1",
        allocated_base=Decimal("2700.00"),
        allocated_withholding=Decimal("513.00"),
        allocated_settlement=Decimal("2754.00"),
        idempotency_key="m115-rent-allocation-1",
        modelo_180_property=Modelo180PropertyEvidence(
            property_key="m115-rent-property",
            situation="1",
            cadastral_reference="1234567VK4713C0001XY",
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="28079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code="28",
            modality="1",
            accrual_year=paid_on.year,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    captured = cli(
        profile,
        "--format", "json",
        "app", "modelo", "aggregate",
        "--modelo", "115", "--year", str(paid_on.year), "--period", "1T",
        "--received-invoice-retencion", request.model_dump_json(),
    )  # fmt: skip
    assert captured.exit_code == 0, captured.output


def m100_exercise() -> int:
    """Return the Modelo 100 exercise the seeded activity income row is booked in."""
    return m100_activity_income_transaction().raw.booked_date.year


def seed_prior_m100_zero_carry(exercise: int) -> None:
    from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository

    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=exercise - 1,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=exercise - 1,
                    period="0A",
                    casilla_values={
                        "0224": Decimal("0"),
                        "1384": Decimal("0"),
                        "1387": Decimal("0"),
                        "1388": Decimal("0"),
                        "1390": Decimal("0"),
                        "1391": Decimal("0"),
                        "1479": Decimal("0"),
                        "1553": Decimal("0"),
                        "1577": Decimal("0"),
                        # The prior return's art. 49 savings-base carries, stated as nil:
                        # an unprinted box is unknown, not zero.
                        **dict.fromkeys(("1263", "1266", "1269", "1270", "1276", "1279", "1282", "1283"), Decimal("0")),
                    },
                ),
            ),
            source_kind="app_filing",
            captured_at=datetime(exercise, 6, 30, 12, 0, tzinfo=UTC),
            stamped_revision_id=str(published_snapshot("100", filing_year=exercise - 1, period="0A").revision.id),
        )
    )


def seed_zero_iva_wallet_decision() -> None:
    """Persist a zero-amount local-recurrence IVA wallet decision in the opened profile.

    The Modelo 303 reconciliation guard blocks calculation when
    ``compensacion-pendiente-anteriores`` is supplied without a persisted
    decision, even when the amount is zero. A ``local_recurrence`` decision
    with ``selected_amount=0`` satisfies the guard while leaving the source-mesh
    advisory assertions meaningful.
    """
    from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
    from cadrumo.domain.iva_compensation.reconciliation import (
        IvaCompensationAuthoritySource,
        IvaCompensationReconciliationDecision,
    )

    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=ACTIVITY_YEAR,
        target_period=Period.from_year_and_code(ACTIVITY_YEAR, "1T"),
        target_registry_snapshot_ref=published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,
        source_registry_snapshot_refs=(published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,),
        selected_authority="local_recurrence",
        selected_amount=Decimal("0"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("0"),
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="local_recurrence",
                amount=Decimal("0"),
                source_locator=f"test:local-recurrence:{ACTIVITY_YEAR}:1T",
                source_modelo="303",
                source_filing_year=ACTIVITY_YEAR,
                source_periods=(Period.from_year_and_code(ACTIVITY_YEAR, "1T"),),
                registry_snapshot_refs=(
                    published_snapshot("303", filing_year=ACTIVITY_YEAR, period="1T").snapshot_ref,
                ),
            ),
        ),
        override_amount=None,
        divergence="wallet_missing",
        blocked=False,
        stale_wallet=False,
        reason_identity="first_period_zero_aeat_wallet",
        decided_at=IVA_WALLET_DECIDED_AT,
    )
    IvaWalletDecisionRepository().save_decision(decision)

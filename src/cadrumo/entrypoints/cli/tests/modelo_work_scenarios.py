"""Shared helpers for Modelo work UX CLI tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does.
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_fact_strings
from cadrumo.application.wizard import catalogue, persistence
from cadrumo.core.aggregation import RetencionClave
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.tests.cli_envelope import unwrap_schema_envelope
from cadrumo.tests.withholding_zero_blocks import zeroed_withholding_blocks

from .cli_fixture_worlds import cli_world_provider, invoke_joined_cli
from .modelo_cli import create_modelo_work_unit_via_cli

#: The filing year every scenario here defaults to: the registry's horizon. A caller that
#: addresses the work these helpers create by modelo, year and period names this year.
SCENARIO_FILING_YEAR = filing_year_envelope().horizon
_WIZARD_REGISTRATION_MODULES = (catalogue, persistence)
_M111_PROFESSIONAL_NIF = "B00015016"
_M111_PROFESSIONAL_NAME = "Asesoria Profesional SL"
_M111_PAID_ON = date(SCENARIO_FILING_YEAR, 1, 15)
MODELO_OPERATOR_PROFILE_LABEL = "operator"
#: The seeded profile's machine identity. A profile id is a UUID; the
#: readable "operator" above is the operator-chosen LABEL, and the two are
#: different concepts that must not share one constant.
_PROFILE_ID = "6f1d2c3a-4b5e-4f60-8a71-9c2d3e4f5a6b"


def invoke_modelo_scenario_cli(args: list[str]):
    return invoke_joined_cli(args)


def operator_profile_facts(*, activity_start_date: str | None = None) -> dict[str, str]:
    """Return the facts of the operator profile the modelo work UX suites run against.

    The operator is the canonical estimación directa normal autónomo. Its modality keeps
    Modelo 130 box 02 as the stated expenses, with no art. 30.2.ª provision. The operator
    files Modelo 111 for the retención withheld from a professional's invoice, so it states
    that it pays such income: Modelo 111 applies only to a payer of income subject to
    retención, and the persona answers that it pays none.
    """
    stated = {"withholding.pays_professionals_with_retencion": "true"}
    if activity_start_date is not None:
        stated["censo.activity_start_date"] = activity_start_date
    return persona_fact_strings(stated)


GB_NON_RESIDENT_PROFILE_FACTS: dict[str, str] = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.tax_id": "12345678Z",
    "identity.name": "Operator",
    "identity.surnames": "Readiness",
    "activities.description": "Spanish-source rent",
    "taxpayer_type.fiscal_residency": "non_resident_irnr",
    "taxpayer_type.country_of_fiscal_residence": "GB",
    "taxpayer_type.representante_fiscal_nif": "12345678Z",
    "taxpayer_type.representante_fiscal_nombre": "Test Representative",
}


def create_modelo_operator_profile(*, activity_start_date: str | None = None) -> None:
    """Register the operator profile and join its runtime through the test's ``seed_profile`` fixture.

    Creation is a precondition here, not the subject: these tests exercise the
    modelo work UX against a profile that already exists.
    """
    cli_world_provider().seeded_profile(
        label=MODELO_OPERATOR_PROFILE_LABEL, facts=operator_profile_facts(activity_start_date=activity_start_date)
    )


def create_gb_non_resident_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    cli_world_provider().seeded_profile(label="operator", facts=GB_NON_RESIDENT_PROFILE_FACTS)


def create_de_nonresident_legal_entity_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    cli_world_provider().seeded_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B00015032",
            "identity.legal_name": "NordHaus GmbH",
            "activities.description": "Spanish-source services",
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "DE",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def create_attribution_entity_intracom_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    cli_world_provider().seeded_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "attribution_entity",
            "identity.tax_id": "E00015008",
            "identity.name": "M349 Readiness CB",
            "activities.description": "intracommunity operations",
            "iva.does_intracomunitario": "true",
            # Stated, not defaulted: the 50,000 EUR threshold selects the
            # Modelo 349 cadence, so an unstated answer leaves the profile unready.
            "iva.intracommunity_operations_exceed_50000_eur": "false",
        },
    )


def create_m130_work_unit(*, period: str = "1T") -> str:
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=SCENARIO_FILING_YEAR,
        period=period,
        revision=open_ended_revision("130").id,
    )


def create_m303_work_unit() -> str:
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "303")
    return create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=SCENARIO_FILING_YEAR,
        period="1T",
        revision=str(select_revision(modelo, filing_year=SCENARIO_FILING_YEAR, period="1T").id),
    )


def m111_withholding_invoice_arguments(
    *, paid_on: date = _M111_PAID_ON, invoice_number: str = f"M111-PROF-{SCENARIO_FILING_YEAR}-001"
) -> list[str]:
    """Return the ``ledger invoice add`` arguments for one Modelo 111 withholding invoice.

    The received professional invoice carries a 15% retención: 1000.00 base,
    150.00 withheld. Callers prepend their own global options. Defaults to the
    newest supported year's 1T coordinate; a caller targeting a different quarter
    supplies its own ``paid_on`` and ``invoice_number``.
    """
    return [
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", _M111_PROFESSIONAL_NAME,
        "--counterparty-nif", _M111_PROFESSIONAL_NIF,
        "--invoice-number", invoice_number,
        "--invoice-date", paid_on.isoformat(),
        "--country-code", "ES",
        "--taxable-base", "1000.00", "--iva-rate", "21",
        "--retention-rate", "0.15", "--retention-amount", "150.00",
        "--iva-category", "domestic_general",
    ]  # fmt: skip


def m111_withholding_aggregate_arguments(
    invoice_id: str,
    *,
    filing_year: int = SCENARIO_FILING_YEAR,
    period: str = "1T",
    paid_on: date = _M111_PAID_ON,
    allocation_id: str = "m111-professional-allocation-1",
) -> list[str]:
    """Return the ``modelo aggregate`` arguments recording the invoice's single paid allocation.

    The settlement is the invoice grand total (1000.00 + 21% IVA = 1210.00)
    less the retención: 1060.00. Defaults to the newest supported year's 1T coordinate;
    a caller targeting a different quarter supplies its own ``filing_year``,
    ``period``, ``paid_on`` and ``allocation_id``.
    """
    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice_id,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme="actividades_profesionales",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=f"m111-professional-payment-{paid_on.isoformat()}",
        payment_occurred_on=paid_on,
        allocation_id=allocation_id,
        allocated_base=Decimal("1000.00"),
        allocated_withholding=Decimal("150.00"),
        allocated_settlement=Decimal("1060.00"),
        idempotency_key=allocation_id,
        modelo_190_detail=WithholdingObservation(
            source_id=invoice_id,
            source_allocation_id=allocation_id,
            perceptor_tax_id=_M111_PROFESSIONAL_NIF,
            perceptor_legal_name=_M111_PROFESSIONAL_NAME,
            transaction_date=paid_on,
            clave=RetencionClave.from_registry("G"),
            subclave="01",
            percibido_dinerario=Decimal("1000.00"),
            retencion_practicada=Decimal("150.00"),
            **zeroed_withholding_blocks(),
            base_retenciones=Decimal("1000.00"),
            porcentaje_retencion=Decimal("15"),
        ),
    )
    return [
        "app", "modelo", "aggregate",
        "--modelo", "111", "--year", str(filing_year), "--period", period,
        "--received-invoice-retencion", request.model_dump_json(),
    ]  # fmt: skip


def capture_m111_invoice_withholding(
    *,
    filing_year: int = SCENARIO_FILING_YEAR,
    period: str = "1T",
    paid_on: date = _M111_PAID_ON,
) -> None:
    """Capture one received professional invoice's retención as Modelo 111 evidence.

    Modelo 111 calculation refuses an all-blank quarter rather than filing a
    silent zero, so a calculable work unit needs one real percepción. The
    evidence enters through the public path only: ``ledger invoice add`` mints
    the invoice, then ``modelo aggregate --received-invoice-retencion`` records
    its paid allocation. Defaults to the newest supported year's 1T coordinate; a
    caller targeting a different quarter -- for example, one whose filing
    window has not opened yet -- supplies its own ``filing_year``, ``period``
    and ``paid_on``.
    """
    canonical = (filing_year, period) == (SCENARIO_FILING_YEAR, "1T")
    invoice_number = f"M111-PROF-{SCENARIO_FILING_YEAR}-001" if canonical else f"M111-PROF-{filing_year}-{period}-001"
    allocation_id = (
        "m111-professional-allocation-1" if canonical else f"m111-professional-allocation-{filing_year}-{period}"
    )
    created = invoke_modelo_scenario_cli(
        [
            "--format", "json",
            *m111_withholding_invoice_arguments(paid_on=paid_on, invoice_number=invoice_number),
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    invoice_id = unwrap_schema_envelope(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output
    captured = invoke_modelo_scenario_cli(
        [
            "--format", "json",
            *m111_withholding_aggregate_arguments(
                invoice_id,
                filing_year=filing_year,
                period=period,
                paid_on=paid_on,
                allocation_id=allocation_id,
            ),
        ],
    )  # fmt: skip
    assert captured.exit_code == 0, captured.output


def create_calculable_modelo_work_unit(
    *, filing_year: int = SCENARIO_FILING_YEAR, period: str = "1T", paid_on: date = _M111_PAID_ON
) -> str:
    """Create a Modelo 111 work unit whose ``work calculate`` succeeds.

    Defaults to the newest supported year's 1T coordinate; a caller targeting a
    different quarter supplies its own ``filing_year``, ``period`` and
    ``paid_on``.
    """
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="111",
        filing_year=filing_year,
        period=period,
        revision=open_ended_revision("111").id,
    )
    capture_m111_invoice_withholding(filing_year=filing_year, period=period, paid_on=paid_on)
    return work_unit_id


def capture_m115_invoice_withholding(*, filing_year: int) -> None:
    """Capture one received urban-rent invoice's retención as Modelo 115 first-quarter evidence for ``filing_year``.

    ``ledger invoice add`` mints a received rent invoice (2700.00 base, 19%
    retención = 513.00), then ``modelo aggregate --received-invoice-retencion``
    records its single paid allocation with the property detail Modelo 180
    requires. The settlement is the invoice grand total (2700.00 + 21% IVA =
    3267.00) less the retención: 2754.00.
    """
    paid_on = date(filing_year, 3, 15)
    created = invoke_modelo_scenario_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-name", "Arrendador Ejemplo SL",
            "--counterparty-nif", "B00015016",
            "--invoice-number", f"M115-RENT-{filing_year}-001",
            "--invoice-date", paid_on.isoformat(),
            "--country-code", "ES",
            "--taxable-base", "2700.00", "--iva-rate", "21",
            "--retention-rate", "0.19", "--retention-amount", "513.00",
            "--iva-category", "domestic_general",
        ],
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
            accrual_year=filing_year,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    captured = invoke_modelo_scenario_cli(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", str(filing_year), "--period", "1T",
            "--received-invoice-retencion", request.model_dump_json(),
        ],
    )  # fmt: skip
    assert captured.exit_code == 0, captured.output


def load_work_unit_by_id(work_unit_id: str) -> WorkUnit:
    """Load one stored work unit of the active profile by its exact id."""
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "an active profile is required to load a work unit"
    unit = WorkUnitCatalogueRepository(bucket_id=bucket_id).load().get(work_unit_id)
    assert unit is not None, work_unit_id
    return unit

"""Shared helpers for Modelo work UX CLI tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)

# Importing the wizard catalogue + persistence modules triggers
# register_wizard_catalogue() at import time, exactly as the production CLI
# startup does.
from ....application.wizard import catalogue as _wizard_catalogue
from ....application.wizard import persistence as _wizard_persistence
from ....core.aggregation import RetencionClave
from ....domain.calculations.registry.temporal import select_revision
from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_M111_PROFESSIONAL_NIF = "B12345674"
_M111_PROFESSIONAL_NAME = "Asesoria Profesional SL"
_M111_PAID_ON = date(2025, 1, 15)
_PROFILE_LABEL = "operator"
#: The seeded profile's machine identity. A profile id is a UUID; the
#: readable "operator" above is the operator-chosen LABEL, and the two are
#: different concepts that must not share one constant.
_PROFILE_ID = "6f1d2c3a-4b5e-4f60-8a71-9c2d3e4f5a6b"


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def operator_profile_facts(*, activity_start_date: str | None = None) -> dict[str, str]:
    """Return the facts of the operator profile the modelo work UX suites run against."""
    facts = {
        "identity.tax_id": "12345678Z",
        "identity.name": "Operator",
        "identity.surnames": "Readiness",
        "activities.description": "design",
        # Modelo 111 readiness requires the colegio concertado answer; these
        # tests file 111 work units, so the profile states it.
        "withholding.colegio_concertado": "false",
    }
    if activity_start_date is not None:
        facts["censo.activity_start_date"] = activity_start_date
    return facts


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


def _create_profile(*, activity_start_date: str | None = None) -> None:
    """Register the operator profile through the shared CLI registration door.

    Creation is a precondition here, not the subject: these tests exercise the
    modelo work UX against a profile that already exists.
    """
    register_cli_profile(
        label=_PROFILE_LABEL, facts=operator_profile_facts(activity_start_date=activity_start_date), log_in=False
    )


def _create_gb_non_resident_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(label="operator", facts=GB_NON_RESIDENT_PROFILE_FACTS, log_in=False)


def _create_de_nonresident_legal_entity_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B66012345",
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
        log_in=False,
    )


def _create_attribution_entity_intracom_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "attribution_entity",
            "identity.tax_id": "E12345674",
            "identity.name": "M349 Readiness CB",
            "activities.description": "intracommunity operations",
            "iva.does_intracomunitario": "true",
        },
        log_in=False,
    )


def _create_m130_work_unit(*, period: str = "1T") -> str:
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2025,
        period=period,
        revision="2019-y-siguientes",
    )


def _create_m303_work_unit() -> str:
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "303")
    return create_modelo_work_unit_via_cli(
        modelo="303",
        filing_year=2025,
        period="1T",
        revision=str(select_revision(modelo, filing_year=2025, period="1T").id),
    )


def m111_withholding_invoice_arguments() -> list[str]:
    """Return the ``ledger invoice add`` arguments for the Modelo 111 2025 1T withholding invoice.

    The received professional invoice carries a 15% retención: 1000.00 base,
    150.00 withheld. Callers prepend their own global options.
    """
    return [
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", _M111_PROFESSIONAL_NAME,
        "--counterparty-nif", _M111_PROFESSIONAL_NIF,
        "--invoice-number", "M111-PROF-2025-001",
        "--invoice-date", _M111_PAID_ON.isoformat(),
        "--country-code", "ES",
        "--taxable-base", "1000.00", "--iva-rate", "21",
        "--retention-rate", "0.15", "--retention-amount", "150.00",
        "--iva-category", "domestic_general",
    ]  # fmt: skip


def m111_withholding_aggregate_arguments(invoice_id: str) -> list[str]:
    """Return the ``modelo aggregate`` arguments recording the invoice's single paid allocation.

    The settlement is the invoice grand total (1000.00 + 21% IVA = 1210.00)
    less the retención: 1060.00.
    """
    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice_id,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme="actividades_profesionales",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="m111-professional-payment-2025-01-15",
        payment_occurred_on=_M111_PAID_ON,
        allocation_id="m111-professional-allocation-1",
        allocated_base=Decimal("1000.00"),
        allocated_withholding=Decimal("150.00"),
        allocated_settlement=Decimal("1060.00"),
        idempotency_key="m111-professional-allocation-1",
        modelo_190_detail=WithholdingObservation(
            source_id=invoice_id,
            source_allocation_id="m111-professional-allocation-1",
            perceptor_tax_id=_M111_PROFESSIONAL_NIF,
            perceptor_legal_name=_M111_PROFESSIONAL_NAME,
            transaction_date=_M111_PAID_ON,
            clave=RetencionClave.from_registry("G"),
            subclave="01",
            percibido_dinerario=Decimal("1000.00"),
            retencion_practicada=Decimal("150.00"),
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
            base_retenciones=Decimal("1000.00"),
            porcentaje_retencion=Decimal("15"),
        ),
    )
    return [
        "app", "modelo", "aggregate",
        "--modelo", "111", "--year", "2025", "--period", "1T",
        "--received-invoice-retencion", request.model_dump_json(),
    ]  # fmt: skip


def _capture_m111_invoice_withholding() -> None:
    """Capture one received professional invoice's retención as Modelo 111 2025 1T evidence.

    Modelo 111 calculation refuses an all-blank quarter rather than filing a
    silent zero, so a calculable work unit needs one real percepción. The
    evidence enters through the public path only: ``ledger invoice add`` mints
    the invoice, then ``modelo aggregate --received-invoice-retencion`` records
    its paid allocation.
    """
    created = _invoke(["--format", "json", *m111_withholding_invoice_arguments()])
    assert created.exit_code == 0, created.output
    invoice_id = unwrap_schema_envelope(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output
    captured = _invoke(["--format", "json", *m111_withholding_aggregate_arguments(invoice_id)])
    assert captured.exit_code == 0, captured.output


def _create_calculable_work_unit() -> str:
    """Create a Modelo 111 2025 1T work unit whose ``work calculate`` succeeds."""
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="111",
        filing_year=2025,
        period="1T",
        revision="2019-y-siguientes",
    )
    _capture_m111_invoice_withholding()
    return work_unit_id


def _capture_m115_invoice_withholding() -> None:
    """Capture one received urban-rent invoice's retención as Modelo 115 2025 1T evidence.

    ``ledger invoice add`` mints a received rent invoice (2700.00 base, 19%
    retención = 513.00), then ``modelo aggregate --received-invoice-retencion``
    records its single paid allocation with the property detail Modelo 180
    requires. The settlement is the invoice grand total (2700.00 + 21% IVA =
    3267.00) less the retención: 2754.00.
    """
    paid_on = date(2025, 3, 15)
    created = _invoke(
        [
            "--format", "json",
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-name", "Arrendador Ejemplo SL",
            "--counterparty-nif", "B12345674",
            "--invoice-number", "M115-RENT-2025-001",
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
        payment_event_id="m115-rent-payment-2025-03-15",
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
                municipality_code="079",
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
            accrual_year=2025,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    captured = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", "2025", "--period", "1T",
            "--received-invoice-retencion", request.model_dump_json(),
        ],
    )  # fmt: skip
    assert captured.exit_code == 0, captured.output

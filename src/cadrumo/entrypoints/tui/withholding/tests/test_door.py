"""Focused shared-service proof for the composition-ready TUI withholding door."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    LARGE_COMPANY_FACTS,
    published_filer_cadence,
)
from cadrumo.application.aggregation.withholding_observation_service import (
    WithholdingMutationMode,
    WithholdingObservationService,
)
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from cadrumo.core.aggregation import RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.tui.withholding.door import TuiInvoiceWithholdingCaptureRequest, TuiWithholdingDoor

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_PROFESSIONAL = RetencionScheme("actividades_profesionales")
_RENT = RetencionScheme("arrendamiento_urbano")


def _door_for(objects: object, *, facts: tuple[UserProfileFact, ...] = ()) -> TuiWithholdingDoor:
    """Compose the door over real storage for a synthetic filer, quarterly unless ``facts`` say otherwise."""
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

    assert isinstance(objects, SecureObjectRepository)
    return TuiWithholdingDoor(
        service=WithholdingObservationService(
            WithholdingObservationWorkflowAdapter(
                objects=objects,
                retenciones=RetencionObservationRepositoryAdapter(objects=objects),
                percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            )
        ),
        filer_cadence=lambda year: published_filer_cadence(year, facts=facts),
    )


def _invoice(*, number: str, base: str = "500.00", withholding: str = "95.00") -> Invoice:
    subtotal = Decimal(base)
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2025, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Synthetic withholding service",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": number,
            "issued_at": date(2025, 3, 31),
            "counterparty_name": "Synthetic Recipient SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.19"),
            "retention_amount": Decimal(withholding),
        }
    )


def _professional_detail(*, invoice: Invoice, paid_on: date, base: str, withholding: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=invoice.invoice_id,
        perceptor_tax_id=invoice.counterparty_tax_id or "",
        perceptor_legal_name=invoice.counterparty_name,
        transaction_date=paid_on,
        clave=RetencionClave.from_registry("G"),
        percibido_dinerario=Decimal(base),
        retencion_practicada=Decimal(withholding),
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
        base_retenciones=Decimal(base),
        porcentaje_retencion=Decimal("19"),
    )


def _rent_property(key: str) -> Modelo180PropertyEvidence:
    return Modelo180PropertyEvidence(
        property_key=key,
        situation="1",
        cadastral_reference="1234567VK4713S0001AA",
        address=Modelo180StructuredAddress(
            province_code="28",
            municipality_code="079",
            municipality="Madrid",
            locality="Madrid",
            postal_code="28001",
            street_type="CL",
            street_name="Synthetic",
            number_type="NUM",
            house_number="1",
        ),
        recipient_province_code="28",
        modality="1",
        accrual_year=2025,
        withholding_percentage=Decimal("19.00"),
    )


def _request(
    invoice: Invoice,
    *,
    income_kind: WithholdingIncomeKind,
    scheme: RetencionScheme,
    allocation_id: str,
    payment_id: str,
    paid_on: date = date(2025, 4, 2),
    base: str = "500.00",
    withholding: str = "95.00",
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND,
    baseline: object | None = None,
    reason: str | None = None,
    annual_detail: WithholdingObservation | None = None,
    property_detail: Modelo180PropertyEvidence | None = None,
) -> TuiInvoiceWithholdingCaptureRequest:
    evidence = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice.invoice_id,
        income_kind=income_kind,
        scheme=scheme,
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id=payment_id,
        payment_occurred_on=paid_on,
        allocation_id=allocation_id,
        allocated_base=Decimal(base),
        allocated_withholding=Decimal(withholding),
        allocated_settlement=Decimal(base),
        idempotency_key=f"tui-{allocation_id}-{mode.value}",
        mode=mode,
        baseline=baseline,
        reason=reason,
        modelo_180_property=property_detail,
        modelo_190_detail=annual_detail,
    )
    return TuiInvoiceWithholdingCaptureRequest(
        invoice=invoice,
        catalogue_revision_id="synthetic-catalogue-revision",
        evidence=evidence,
        filing_year=2025,
    )


def test_tui_door_captures_and_inspects_professional_annual_detail(tmp_path: Path) -> None:
    """The TUI door writes both shared projections, then exposes their baseline."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        door = _door_for(profile.repository)
        invoice = _invoice(number="TUI-PRO-001")
        request = _request(
            invoice,
            income_kind=WithholdingIncomeKind.PROFESSIONAL,
            scheme=_PROFESSIONAL,
            allocation_id="professional-1",
            payment_id="payment-1",
            annual_detail=_professional_detail(
                invoice=invoice, paid_on=date(2025, 4, 2), base="500.00", withholding="95.00"
            ),
        )

        captured = door.capture(request)
        replay = door.capture(request)

        assert captured.status == "captured"
        assert replay.status == "replayed"
        assert captured.scope is not None
        state = door.read_window(captured.scope)
        assert state.baseline.generation_id == captured.generation_id
        assert len(state.entries) == 2
        assert {entry.identity.projection_role.value for entry in state.entries} == {"retencion", "percepcion"}
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )
        assert len(annual) == 1
        assert annual[0].source_allocation_id == "professional-1"



def test_tui_door_refuses_a_large_company_professional_invoice_without_writing(tmp_path: Path) -> None:
    """A large company files Modelo 111 monthly, so the quarterly window is refused and stays empty."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        door = _door_for(profile.repository, facts=LARGE_COMPANY_FACTS)
        invoice = _invoice(number="TUI-PRO-MONTHLY")
        outcome = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-monthly",
                payment_id="payment-monthly",
                annual_detail=_professional_detail(
                    invoice=invoice, paid_on=date(2025, 4, 2), base="500.00", withholding="95.00"
                ),
            )
        )
        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(2025, "2T")
        )

    assert outcome.status == "refused"
    assert outcome.refusal_code == "withholding_quarterly_window_not_scheduled"
    assert stored == ()

def test_tui_door_captures_rent_property_detail_and_inspects_it(tmp_path: Path) -> None:
    """The TUI keeps explicit property evidence on the same rent allocation."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        door = _door_for(profile.repository)
        invoice = _invoice(number="TUI-RENT-001", base="3000.00", withholding="570.00")
        captured = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.URBAN_RENT,
                scheme=_RENT,
                allocation_id="rent-1",
                payment_id="rent-payment-1",
                base="3000.00",
                withholding="570.00",
                property_detail=_rent_property("office-a"),
            )
        )

        assert captured.status == "captured"
        assert captured.scope is not None
        state = door.read_window(captured.scope)
        assert len(state.entries) == 1
        detail = state.entries[0].retencion
        assert detail is not None and detail.modelo_180_property is not None
        assert detail.modelo_180_property.property_key == "office-a"


def test_tui_door_requires_baselines_for_replace_and_clear_and_refuses_stale_ones(tmp_path: Path) -> None:
    """The presenter cannot infer destructive intent or retry a stale edit."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        door = _door_for(profile.repository)
        invoice = _invoice(number="TUI-PRO-002")
        detail = _professional_detail(invoice=invoice, paid_on=date(2025, 4, 2), base="500.00", withholding="95.00")
        first = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-1",
                payment_id="payment-1",
                annual_detail=detail,
            )
        )
        assert first.scope is not None
        current = door.read_window(first.scope)
        second = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-2",
                payment_id="payment-2",
                annual_detail=_professional_detail(
                    invoice=invoice, paid_on=date(2025, 4, 2), base="500.00", withholding="95.00"
                ),
            )
        )
        assert second.status == "refused", "the full invoice liability is already allocated"

        missing_replace_baseline = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-missing-replace-baseline",
                payment_id="payment-missing-replace-baseline",
                mode=WithholdingMutationMode.REPLACE,
                reason="synthetic replacement",
                annual_detail=detail,
            )
        )
        assert missing_replace_baseline.status == "refused"
        assert missing_replace_baseline.refusal_code == "invalid_withholding_evidence"
        stale_replace = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-replace",
                payment_id="payment-replace",
                mode=WithholdingMutationMode.REPLACE,
                baseline=current.baseline,
                reason="synthetic replacement",
                annual_detail=detail,
            )
        )
        assert stale_replace.status == "captured"
        stale_clear = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-clear",
                payment_id="payment-clear",
                mode=WithholdingMutationMode.CLEAR,
                baseline=current.baseline,
                reason="synthetic clear",
                annual_detail=detail,
            )
        )
        assert stale_clear.status == "refused"
        assert stale_clear.refusal_code == "stale_baseline"
        replacement_state = door.read_window(first.scope)
        assert replacement_state.entries
        assert stale_replace.generation_id is not None
        audit = door.read_generation(first.scope, stale_replace.generation_id)
        assert audit is not None and audit.mode is WithholdingMutationMode.REPLACE
        cleared = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-clear-fresh",
                payment_id="payment-clear-fresh",
                mode=WithholdingMutationMode.CLEAR,
                baseline=replacement_state.baseline,
                reason="synthetic clear",
                annual_detail=detail,
            )
        )
        assert cleared.status == "captured"
        assert door.read_window(first.scope).entries == ()


def test_tui_door_refuses_missing_professional_annual_detail_before_write(tmp_path: Path) -> None:
    """A quarterly row cannot be stranded without its required Modelo 190 detail."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        door = _door_for(profile.repository)
        invoice = _invoice(number="TUI-PRO-003")
        outcome = door.capture(
            _request(
                invoice,
                income_kind=WithholdingIncomeKind.PROFESSIONAL,
                scheme=_PROFESSIONAL,
                allocation_id="professional-missing-annual",
                payment_id="payment-missing-annual",
            )
        )

        assert outcome.status == "refused"
        assert outcome.refusal_code == "invalid_withholding_evidence"
        expected_period = Period.from_year_and_code(2025, "2T")
        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("111", expected_period)
            == ()
        )

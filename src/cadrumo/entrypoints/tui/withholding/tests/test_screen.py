"""Pilot proof that the withholding form enters evidence through the shared door."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.withholding_observation_service import WithholdingObservationService
from cadrumo.core.period import Period
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.withholding.door import TuiWithholdingDoor
from cadrumo.entrypoints.tui.withholding.screen import WithholdingEvidenceScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _door_for(objects: object) -> TuiWithholdingDoor:
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

    assert isinstance(objects, SecureObjectRepository)
    return TuiWithholdingDoor(
        service=WithholdingObservationService(
            WithholdingObservationWorkflowAdapter(
                objects=objects,
                retenciones=RetencionObservationRepositoryAdapter(objects=objects),
                percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            )
        )
    )


def _invoice(*, number: str, base: str, withholding: str) -> Invoice:
    subtotal = Decimal(base)
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2025, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Synthetic TUI withholding",
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


def _no_ledger_read(transaction_id: str) -> tuple[TransactionCatalogue, str | None]:
    """Invoice-backed income must never reach the ledger payment lookup."""
    raise AssertionError(f"invoice-backed capture read the ledger for {transaction_id}")


def _set(screen: WithholdingEvidenceScreen, field: str, value: str) -> None:
    screen.query_one(f"#withholding-{field}", Input).value = value


def _choice(screen: WithholdingEvidenceScreen, field: str, value: str) -> None:
    screen.query_one(f"#withholding-{field}", Select).value = value


def _status(screen: WithholdingEvidenceScreen) -> str:
    return str(screen.query_one("#withholding-status", Static).render())


async def _click(pilot: Pilot[None], screen: WithholdingEvidenceScreen, control: str) -> None:
    """Press the rendered control after Pilot has entered the form values.

    Textual's headless mouse driver cannot address an off-screen button inside
    a long terminal form even after its scroll request settles.  ``press``
    still emits the actual widget event; it avoids a test-only direct call to
    the withholding door.
    """
    button = screen.query_one(control, Button)
    button.scroll_visible()
    await pilot.pause()
    button.press()
    await pilot.pause()


def _fill_common(
    screen: WithholdingEvidenceScreen,
    invoice: Invoice,
    *,
    base: str,
    withholding: str,
    scheme: str = "actividades_profesionales",
) -> None:
    _set(screen, "invoice-id", str(invoice.invoice_id))
    _set(screen, "payment-id", f"payment-{invoice.invoice_number}")
    _set(screen, "payment-date", "2025-04-02")
    _set(screen, "allocation-id", f"allocation-{invoice.invoice_number}")
    _set(screen, "allocated-base", base)
    _set(screen, "allocated-withholding", withholding)
    _set(screen, "allocated-settlement", base)
    _set(screen, "idempotency-key", f"replay-{invoice.invoice_number}")
    _set(screen, "annual-percentage", "19.00")
    _set(screen, "territorial-deduction", "0")
    # Payer facts are entered explicitly; the form prefills none of them.
    _set(screen, "scheme", scheme)
    _set(screen, "clave", "G")
    _set(screen, "province", "28")
    _set(screen, "property-situation", "1")
    _set(screen, "municipality-code", "079")
    _set(screen, "municipality", "Madrid")
    _set(screen, "postal-code", "28001")
    _set(screen, "property-modality", "1")


@pytest.mark.asyncio
async def test_pilot_enters_professional_evidence_replays_and_refuses_stale_clear(tmp_path: Path) -> None:
    """Operator controls, rather than a direct door call, make each mutation."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _invoice(number="TUI-SCREEN-PRO", base="500.00", withholding="95.00")
        screen = WithholdingEvidenceScreen(
            door=_door_for(profile.repository),
            invoice_lookup=lambda supplied: (
                (invoice, "catalogue-revision") if supplied == str(invoice.invoice_id) else None
            ),
            ledger_payment_lookup=_no_ledger_read,
            filing_year=2025,
        )
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _fill_common(screen, invoice, base="500.00", withholding="95.00")
            _set(screen, "territorial-deduction", "")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: invalid_withholding_evidence"
            _set(screen, "territorial-deduction", "0")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "replayed"
            await _click(pilot, screen, "#withholding-inspect")
            assert "2 active projections" in str(screen.query_one("#withholding-inspection", Static).render())
            _choice(screen, "mode", "replace")
            _set(screen, "reason", "corrected evidence")
            _set(screen, "idempotency-key", "replace-professional")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            # The first inspection baseline is now stale.  The screen must not retry it.
            _choice(screen, "mode", "clear")
            _set(screen, "reason", "operator correction")
            _set(screen, "idempotency-key", "clear-stale-professional")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: stale_baseline"
            await _click(pilot, screen, "#withholding-inspect")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            pilot.app.exit(None)

        scope = Period.from_year_and_code(2025, "2T")
        assert RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("111", scope) == ()


@pytest.mark.asyncio
async def test_pilot_enters_rent_property_detail_and_inspects_the_shared_projection(tmp_path: Path) -> None:
    """A rent form carries explicit property evidence instead of annual guesswork."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _invoice(number="TUI-SCREEN-RENT", base="3000.00", withholding="570.00")
        screen = WithholdingEvidenceScreen(
            door=_door_for(profile.repository),
            invoice_lookup=lambda supplied: (
                (invoice, "catalogue-revision") if supplied == str(invoice.invoice_id) else None
            ),
            ledger_payment_lookup=_no_ledger_read,
            filing_year=2025,
        )
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _choice(screen, "income-kind", "urban_rent")
            _fill_common(screen, invoice, base="3000.00", withholding="570.00", scheme="arrendamiento_urbano")
            _set(screen, "property-key", "office-a")
            _set(screen, "cadastral-reference", "1234567VK4713S0001AA")
            _set(screen, "street-name", "Synthetic")
            _set(screen, "inspect-modelo", "115")
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            await _click(pilot, screen, "#withholding-inspect")
            assert "1 active projections" in str(screen.query_one("#withholding-inspection", Static).render())
            pilot.app.exit(None)

        scope = Period.from_year_and_code(2025, "2T")
        rows = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("115", scope)
        assert len(rows) == 1
        assert rows[0].modelo_180_property is not None
        assert rows[0].modelo_180_property.property_key == "office-a"

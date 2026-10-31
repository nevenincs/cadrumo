"""A purchase booked the wrong way never deducts twice, and its value is weighed against the register."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import lookup_translation, output_language
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.categories.spending_category_catalogue import amortizable_spending_categories
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.invoices.errors import InvoicePersistenceError
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.iva.schema import InvoiceKind as CatalogueInvoiceKind
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
    FurtherAcquisitionRow,
)
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue

from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import CALCULATION_NOTE_ATTENTION
from ...modelo.work_form_findings import ModeloFormAttention
from ..activity_asset_ledger_reconciliation import possibly_durable_expense_findings
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    _InMemoryInvoiceCatalogueRepository,
    _invoice,
    machine_acquisition_transaction,
    register_asset,
    resolve_m100,
    resolve_m130,
)
from .ledger_source_mesh_support import (
    reasons as _reasons,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_UNREGISTERED = "ledger_amortization_row_unregistered"
_WITHHELD = "register_owned_capital_acquisition"
_EXCEEDS = "register_acquisition_exceeds_ledger"
_PARTLY = "register_acquisition_partly_accounted"
_MISSING = "register_acquisition_row_missing"
_MAY_BE_DURABLE = "ledger_expense_may_be_durable"
_OFFICE = "material_oficina"


def _history(*assets: ActivityAssetRevision) -> ActivityAssetHistory:
    return ActivityAssetHistory(revisions=assets)


def _expense_total(resolution: CalculationSourceResolution) -> Decimal:
    return sum(resolution.binding_values.values(), Decimal("0"))


def test_a_registered_purchase_booked_as_office_material_is_withheld_from_both_returns() -> None:
    row = machine_acquisition_transaction(_OFFICE)
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in (resolve_m100(history, rows=(row,)), resolve_m130(history, "2T", rows=(row,))):
        assert _WITHHELD in _reasons(resolution)
        assert row.transaction_id not in resolution.source_transaction_ids
        assert _EXCEEDS not in _reasons(resolution)
        assert _PARTLY not in _reasons(resolution)


def test_the_same_row_with_no_element_deducts_as_the_expense_it_was_booked_as() -> None:
    row = machine_acquisition_transaction(_OFFICE)

    assert _expense_total(resolve_m100(_history(), rows=(row,))) == Decimal("1000.00")


def test_a_capital_good_for_iva_booked_as_an_expense_deducts_nothing_and_is_named_once() -> None:
    row = machine_acquisition_transaction(_OFFICE).model_copy(update={"deduction_fact_kind": "domestic_investment"})

    for resolution in (resolve_m100(_history(), rows=(row,)), resolve_m130(_history(), "2T", rows=(row,))):
        assert _reasons(resolution).count(_UNREGISTERED) == 1
        assert _expense_total(resolution) == Decimal("0")


def test_a_row_lowered_after_registration_is_found_on_both_returns() -> None:
    row = machine_acquisition_transaction(
        _OFFICE, amount=Decimal("121.00"), taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00")
    )
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in (resolve_m100(history, rows=(row,)), resolve_m130(history, "2T", rows=(row,))):
        assert _reasons(resolution).count(_EXCEEDS) == 1


def test_two_elements_that_each_fit_a_row_but_not_together_are_found_once() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    history = _history(
        register_asset("first", transaction_id=row.transaction_id, basis=Decimal("800.00")),
        register_asset("second", transaction_id=row.transaction_id, basis=Decimal("800.00")),
    )

    assert _reasons(resolve_m100(history, rows=(row,))).count(_EXCEEDS) == 1


def test_two_elements_that_share_a_row_exactly_raise_nothing() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    history = _history(
        register_asset("first", transaction_id=row.transaction_id, basis=Decimal("600.00")),
        register_asset("second", transaction_id=row.transaction_id, basis=Decimal("400.00")),
    )

    reasons = _reasons(resolve_m100(history, rows=(row,)))

    assert _EXCEEDS not in reasons
    assert _PARTLY not in reasons


def test_a_price_below_its_row_is_named_and_the_remainder_deducts_nothing() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("300.00")))

    resolution = resolve_m100(history, rows=(row,))

    assert _reasons(resolution).count(_PARTLY) == 1
    assert row.transaction_id not in resolution.source_transaction_ids


def test_a_further_row_counts_toward_its_element() -> None:
    first = machine_acquisition_transaction("hardware_amortizable", provider_id="first-instalment")
    second = machine_acquisition_transaction("hardware_amortizable", provider_id="second-instalment")
    asset = register_asset("press", transaction_id=first.transaction_id, basis=Decimal("2000.00"))
    further = asset.acquisition.model_copy(update={"observed_transaction_id": second.transaction_id})
    history = _history(
        asset.model_copy(
            update={
                "further_acquisitions": (FurtherAcquisitionRow(shape=AcquisitionShape.SPLIT_PAYMENT, lineage=further),)
            }
        )
    )

    reasons = _reasons(resolve_m100(history, rows=(first, second)))

    assert _EXCEEDS not in reasons
    assert _PARTLY not in reasons


def _both_returns(history: ActivityAssetHistory, **kwargs: Any) -> tuple[CalculationSourceResolution, ...]:
    return resolve_m100(history, **kwargs), resolve_m130(history, "2T", **kwargs)


def _described(row: Transaction, description: str) -> Transaction:
    facts = {name: getattr(row, name) for name in type(row).model_fields if name != "transaction_id"}
    return Transaction.model_validate({**facts, "raw": row.raw.model_copy(update={"description": description})})


def _with_invoices(*invoices: Invoice) -> _InMemoryInvoiceCatalogueRepository:
    repository = _InMemoryInvoiceCatalogueRepository()
    repository.save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices}))
    return repository


def _invoice_reading(invoice: Invoice, description: str) -> Invoice:
    return invoice.model_copy(update={"lines": (invoice.lines[0].model_copy(update={"description": description}),)})


def _outside_ledger_element() -> ActivityAssetRevision:
    template = register_asset("old-press", transaction_id="c" * 64)
    facts = {name: getattr(template, name) for name in type(template).model_fields}
    facts.update(
        acquisition=AcquisitionLineageReference(invoice_evidence_id="Factura 2014/118, Prensas SA"),
        acquisition_shape=AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER,
        declared_acquisition_date=date(2014, 3, 1),
        declared_activity=TipoActividad.A03_RESTO_EMPRESARIALES,
    )
    return ActivityAssetRevision(**facts)


def test_a_row_deleted_after_registration_is_found_once_on_both_returns() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    history = _history(register_asset("press", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in _both_returns(history):
        assert _reasons(resolution).count(_MISSING) == 1
        assert _EXCEEDS not in _reasons(resolution)
        finding = next(item for item in resolution.diagnostics if item.reason == _MISSING)
        assert row.transaction_id in finding.message
        assert "press" in finding.message
    assert CALCULATION_NOTE_ATTENTION[_MISSING] is ModeloFormAttention.CHECK


def test_the_same_row_still_in_the_ledger_raises_nothing() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    history = _history(register_asset("press", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in _both_returns(history, rows=(row,)):
        assert _MISSING not in _reasons(resolution)


def test_an_element_acquired_outside_the_ledger_never_misses_a_row() -> None:
    for resolution in _both_returns(_history(_outside_ledger_element())):
        assert _MISSING not in _reasons(resolution)


def test_one_missing_row_of_two_is_found_once_and_nothing_else_is_weighed() -> None:
    first = machine_acquisition_transaction("hardware_amortizable", provider_id="first-instalment")
    second = machine_acquisition_transaction("hardware_amortizable", provider_id="second-instalment")
    asset = register_asset("press", transaction_id=first.transaction_id, basis=Decimal("2000.00"))
    further = asset.acquisition.model_copy(update={"observed_transaction_id": second.transaction_id})
    history = _history(
        asset.model_copy(
            update={
                "further_acquisitions": (FurtherAcquisitionRow(shape=AcquisitionShape.SPLIT_PAYMENT, lineage=further),)
            }
        )
    )

    for resolution in _both_returns(history, rows=(first,)):
        assert _reasons(resolution).count(_MISSING) == 1
        assert _EXCEEDS not in _reasons(resolution)
        finding = next(item for item in resolution.diagnostics if item.reason == _MISSING)
        assert second.transaction_id in finding.message
        assert first.transaction_id not in finding.message


def test_a_monitor_booked_as_office_material_is_asked_about_and_still_deducts_in_full() -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), "Monitor Dell 27 pulgadas")
    plain = machine_acquisition_transaction(_OFFICE)

    for resolution, baseline in zip(
        _both_returns(_history(), rows=(row,)), _both_returns(_history(), rows=(plain,)), strict=True
    ):
        assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1
        assert _MAY_BE_DURABLE not in _reasons(baseline)
        assert _expense_total(resolution) == _expense_total(baseline)
        assert row.transaction_id in resolution.source_transaction_ids
        finding = next(item for item in resolution.diagnostics if item.reason == _MAY_BE_DURABLE)
        assert finding.source_ref == f"transaction:{row.transaction_id}"
        assert "monitor" in finding.message
    assert _expense_total(resolve_m100(_history(), rows=(row,))) == Decimal("1000.00")
    assert CALCULATION_NOTE_ATTENTION[_MAY_BE_DURABLE] is ModeloFormAttention.CHECK


@pytest.mark.parametrize(
    "description",
    ["folios toner", "monitorizacion de red", "casamiento", "mesana", "alquiler vivienda", "amortizacion prestamo"],
)
def test_consumables_and_a_keyword_inside_another_word_raise_nothing(description: str) -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), description)

    for resolution in _both_returns(_history(), rows=(row,)):
        assert _MAY_BE_DURABLE not in _reasons(resolution)


def test_case_and_accents_do_not_hide_a_keyword() -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), "PORTÁTIL")

    for resolution in _both_returns(_history(), rows=(row,)):
        assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_finding_does_not_vary_with_the_interface_language(language: str) -> None:
    """Only the English catalogue lists ``laptop``, so reading the operator's alone would lose it elsewhere."""
    row = _described(machine_acquisition_transaction(_OFFICE), "laptop lenovo")

    with override_settings(cadrumo_output_language=language):
        assert output_language() == language
        for resolution in _both_returns(_history(), rows=(row,)):
            assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1


def test_every_amortizable_category_has_keywords_in_every_catalogue() -> None:
    for category in amortizable_spending_categories(effective_date=date(2025, 12, 31)):
        for language in SUPPORTED_OUTPUT_LANGUAGES:
            keywords = lookup_translation(f"desktop.ledger.category_keywords.{category.value}", locale=language)
            assert keywords is not None
            assert keywords.split() != []


def test_a_durable_word_only_on_a_linked_invoice_line_is_asked_about() -> None:
    row = machine_acquisition_transaction(_OFFICE)
    invoice = _invoice_reading(_invoice(row.transaction_id), "Silla de oficina ergonomica")

    for resolution in _both_returns(_history(), rows=(row,), invoices=_with_invoices(invoice)):
        assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1


def _hundred_euro_row() -> Transaction:
    return machine_acquisition_transaction(
        _OFFICE, amount=Decimal("121.00"), taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00")
    )


def test_a_durable_word_on_an_invoice_the_row_names_as_evidence_is_asked_about() -> None:
    """Modelo 100 refuses evidence that does not link back, so only the instalment deducts this row."""
    invoice = _invoice_reading(_invoice("f" * 64), "Monitor 27 pulgadas")
    row = _hundred_euro_row().model_copy(update={"purchase_invoice_evidence_id": invoice.invoice_id})

    resolution = resolve_m130(_history(), "2T", rows=(row,), invoices=_with_invoices(invoice))

    assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1


def test_an_invoice_reached_both_ways_asks_once() -> None:
    plain = _hundred_euro_row()
    invoice = _invoice_reading(_invoice(plain.transaction_id), "Monitor 27 pulgadas")
    row = plain.model_copy(update={"purchase_invoice_evidence_id": invoice.invoice_id})

    for resolution in _both_returns(_history(), rows=(row,), invoices=_with_invoices(invoice)):
        assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1


def test_an_issued_invoice_linked_to_the_row_says_nothing_about_what_was_bought() -> None:
    row = machine_acquisition_transaction(_OFFICE)
    issued = _invoice_reading(_invoice(row.transaction_id), "Monitor 27 pulgadas").model_copy(
        update={"kind": CatalogueInvoiceKind.ISSUED}
    )

    for resolution in _both_returns(_history(), rows=(row,), invoices=_with_invoices(issued)):
        assert _MAY_BE_DURABLE not in _reasons(resolution)


def test_the_question_itself_refuses_owned_capital_and_amortizable_rows() -> None:
    owned = _described(machine_acquisition_transaction(_OFFICE, provider_id="owned"), "Monitor Dell")
    capital = _described(machine_acquisition_transaction(_OFFICE, provider_id="capital"), "Monitor Dell").model_copy(
        update={"deduction_fact_kind": "domestic_investment"}
    )
    amortizable = _described(machine_acquisition_transaction("hardware_amortizable"), "Monitor Dell")
    asked = _described(machine_acquisition_transaction(_OFFICE, provider_id="asked"), "Monitor Dell")
    ledger = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    ledger.save(TransactionCatalogue.from_transactions((owned, capital, amortizable, asked)))

    findings = possibly_durable_expense_findings(
        (row.transaction_id for row in (owned, capital, amortizable, asked)),
        revisions=(register_asset("monitor", transaction_id=owned.transaction_id, basis=Decimal("1000.00")),),
        ledger=ledger,
        invoices=_with_invoices(),
        tax_year=2025,
        source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
        resolver_id="ledger_renta_gastos_estimacion_directa_aggregation",
    )

    assert [finding.source_ref for finding in findings] == [f"transaction:{asked.transaction_id}"]


def test_a_row_the_register_owns_is_not_asked_about() -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), "Monitor Dell")
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in _both_returns(history, rows=(row,)):
        assert _MAY_BE_DURABLE not in _reasons(resolution)
        assert _WITHHELD in _reasons(resolution)


def test_a_capital_good_is_named_once_and_not_asked_about() -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), "Monitor Dell").model_copy(
        update={"deduction_fact_kind": "domestic_investment"}
    )

    for resolution in _both_returns(_history(), rows=(row,)):
        assert _reasons(resolution).count(_UNREGISTERED) == 1
        assert _MAY_BE_DURABLE not in _reasons(resolution)


def test_a_row_already_in_an_amortizable_category_is_named_once_and_not_asked_about() -> None:
    row = _described(machine_acquisition_transaction("hardware_amortizable"), "Monitor Dell")

    for resolution in _both_returns(_history(), rows=(row,)):
        assert _reasons(resolution).count(_UNREGISTERED) == 1
        assert _MAY_BE_DURABLE not in _reasons(resolution)


class _UnreadableInvoices:
    def load(self) -> InvoiceCatalogue:
        raise InvoicePersistenceError("invoice catalogue unreadable")


def test_an_unreadable_invoice_catalogue_costs_the_instalment_no_figure() -> None:
    row = _described(machine_acquisition_transaction(_OFFICE), "Monitor Dell")
    readable = resolve_m130(_history(), "2T", rows=(row,))

    resolution = resolve_m130(_history(), "2T", rows=(row,), invoices=_UnreadableInvoices())

    assert _expense_total(resolution) == _expense_total(readable)
    assert _reasons(resolution).count("storage_degraded") == 1
    assert _reasons(resolution).count(_MAY_BE_DURABLE) == 1

"""Exterior detail rows when a destination rate changes inside the declared quarter.

LIVA art. 90.Dos takes each operation's rate at its own devengo, and art. 163
noniesdecies.Uno.c) requires the return's tax per Member State broken down by
rate. These tests read the change from the published rate fact rather than from
a fixed calendar date, so they follow the registry, and they compute expected
cuotas from that fact's raw percentages instead of through ``lookup_rate``.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.money.rounding import round_to_cents
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_revision
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus, operation_performed_role
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import InvoiceKind, IvaRateKind
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.models import TransactionCatalogue
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..errors import AggregationValidationError
from ..oss_ioss import OssIossLedgerSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .oss_rate_change_support import (
    RateChange,
    exterior_period,
    ordinary_general_variants,
    rate_change_inside_a_quarter,
    variant_pct,
)

_CORRECTIONS = "modelo-369-exterior-t36902"
pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "2bb5bf4c-ff0d-440c-a428-b075558b3595"
_FIELD_PREFIX = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-"
_TAX_IDS = {"de": "DE345678901", "ro": "RO12345678"}


def _stable_member_state(operation: PinnedAuthorityOperation, change: RateChange) -> tuple[str, Decimal]:
    """Return a Member State that keeps one general rate across the change's quarter."""
    quarter = Period.from_year_and_code(change.period.filing_year, change.period.registry_token.removeprefix("EXT-"))
    (covering,) = (
        variant
        for variant in ordinary_general_variants(operation)["de"]
        if (variant.valid_from or date.max) <= quarter.end_date
        and (variant.valid_to is None or quarter.start_date <= variant.valid_to)
    )
    return "de", variant_pct(covering)


def _cuota(base: str, pct: Decimal) -> Decimal:
    return round_to_cents(Decimal(base) * pct / Decimal("100"))


def _invoice(
    number: str,
    *,
    member_state: str,
    supply_date: date | None,
    issued_at: date,
    base: str,
    pct: Decimal,
) -> Invoice:
    amount = Decimal(base)
    quota = _cuota(base, pct)
    dated: dict[str, object] = (
        {}
        if supply_date is None
        else {
            "operation_date": supply_date,
            "operation_date_role": operation_performed_role(effective_date=supply_date),
        }
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": issued_at,
            **dated,
            "counterparty_name": "Cliente ficticio",
            "counterparty_tax_id": _TAX_IDS[member_state],
            "counterparty_country": member_state.upper(),
            "base_total": amount,
            "iva_total": quota,
            "grand_total": amount + quota,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Servicio ficticio",
                    quantity=Decimal("1"),
                    unit_price=amount,
                    subtotal=amount,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    oss_rate_kind=IvaRateKind("general"),
                    iva_amount=quota,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime("external_scheme"),
            "oss_transaction_kind": TransactionKind("external_scheme_services"),
        }
    )


class _Reader:
    bucket_id = _BUCKET

    def __init__(self, invoices: tuple[Invoice, ...]) -> None:
        # The catalogue's mapping keeps insertion order, so a test can choose
        # which side of the boundary the resolver reads first.
        self._catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _Transactions:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _resolve(
    operation: PinnedAuthorityOperation,
    period: Period,
    invoices: tuple[Invoice, ...],
    revision: ModeloRevision | None = None,
) -> CalculationSourceResolution:
    context = CalculationSourceContext(
        bucket_id=_BUCKET,
        work_unit_id="a" * 64,
        modelo="369",
        filing_year=period.filing_year,
        period=period,
        revision=revision or published_revision("369", "esquema-exterior"),
        operation=operation,
    )
    resolver = OssIossLedgerSourceResolver(
        ports=InvoiceCatalogueReadPorts(invoice_reader=_Reader(invoices), transaction_reader=_Transactions())
    )
    return resolver.resolve(context)


def _row(resolution: CalculationSourceResolution, row: int) -> tuple[str, str, Decimal, Decimal, Decimal]:
    return (
        resolution.enum_binding_values[f"{_FIELD_PREFIX}codigo-de-pais-em-de-consumo-{row}"],
        resolution.enum_binding_values[f"{_FIELD_PREFIX}tipo-iva-{row}"],
        resolution.binding_values[f"{_FIELD_PREFIX}tipo-de-iva-{row}"],
        resolution.binding_values[f"{_FIELD_PREFIX}base-imponible-{row}"],
        resolution.binding_values[f"{_FIELD_PREFIX}cuota-iva-{row}"],
    )


def _occupied_rows(resolution: CalculationSourceResolution) -> list[int]:
    (closed,) = (row_set for row_set in resolution.closed_record_row_sets if row_set.record_id != _CORRECTIONS)
    return [row.row_index for row in closed.rows if row.occupied]


@pytest.mark.parametrize("before_is_read_first", [True, False])
def test_rows_either_side_of_the_change_carry_their_own_rate(
    operation: PinnedAuthorityOperation, *, before_is_read_first: bool
) -> None:
    change = rate_change_inside_a_quarter(operation)
    before = _invoice(
        "SYNTHETIC-BEFORE",
        member_state=change.member_state,
        supply_date=change.last_day_before,
        issued_at=change.last_day_before,
        base="100.00",
        pct=change.pct_before,
    )
    after = _invoice(
        "SYNTHETIC-AFTER",
        member_state=change.member_state,
        supply_date=change.first_day_after,
        issued_at=change.first_day_after,
        base="200.00",
        pct=change.pct_after,
    )

    resolution = _resolve(operation, change.period, (before, after) if before_is_read_first else (after, before))

    code = change.member_state.upper()
    rows_by_rate = {_row(resolution, row)[2]: _row(resolution, row) for row in (1, 2)}
    assert rows_by_rate == {
        change.pct_before: (code, "S", change.pct_before, Decimal("100.00"), _cuota("100.00", change.pct_before)),
        change.pct_after: (code, "S", change.pct_after, Decimal("200.00"), _cuota("200.00", change.pct_after)),
    }
    assert _occupied_rows(resolution) == [1, 2]


def test_lines_on_one_side_of_the_change_still_sum_into_one_row(operation: PinnedAuthorityOperation) -> None:
    change = rate_change_inside_a_quarter(operation)
    earlier = change.last_day_before - timedelta(days=1)
    first, second, after = (
        _invoice(
            number,
            member_state=change.member_state,
            supply_date=supply_date,
            issued_at=supply_date,
            base=base,
            pct=pct,
        )
        for number, supply_date, base, pct in (
            ("SYNTHETIC-1", earlier, "100.00", change.pct_before),
            ("SYNTHETIC-2", change.last_day_before, "50.00", change.pct_before),
            ("SYNTHETIC-3", change.first_day_after, "10.00", change.pct_after),
        )
    )

    resolution = _resolve(operation, change.period, (first, after, second))

    rows_by_rate = {_row(resolution, row)[2]: _row(resolution, row) for row in (1, 2)}
    assert rows_by_rate[change.pct_before][3:] == (
        Decimal("150.00"),
        _cuota("100.00", change.pct_before) + _cuota("50.00", change.pct_before),
    )
    assert rows_by_rate[change.pct_after][3:] == (Decimal("10.00"), _cuota("10.00", change.pct_after))
    assert _occupied_rows(resolution) == [1, 2]


@pytest.mark.parametrize("side", ["before", "after"])
def test_boundary_day_alone_selects_its_own_rate_in_one_row(operation: PinnedAuthorityOperation, side: str) -> None:
    change = rate_change_inside_a_quarter(operation)
    supply_date, pct = (
        (change.last_day_before, change.pct_before) if side == "before" else (change.first_day_after, change.pct_after)
    )
    invoice = _invoice(
        "SYNTHETIC-1",
        member_state=change.member_state,
        supply_date=supply_date,
        issued_at=supply_date,
        base="100.00",
        pct=pct,
    )

    resolution = _resolve(operation, change.period, (invoice,))

    assert _row(resolution, 1)[2:] == (pct, Decimal("100.00"), _cuota("100.00", pct))
    assert _occupied_rows(resolution) == [1]


@pytest.mark.parametrize("side", ["before", "after"])
def test_cuota_at_the_other_sides_rate_is_refused_on_the_boundary_day(
    operation: PinnedAuthorityOperation, side: str
) -> None:
    change = rate_change_inside_a_quarter(operation)
    supply_date, wrong_pct = (
        (change.last_day_before, change.pct_after) if side == "before" else (change.first_day_after, change.pct_before)
    )
    invoice = _invoice(
        "SYNTHETIC-1",
        member_state=change.member_state,
        supply_date=supply_date,
        issued_at=supply_date,
        base="100.00",
        pct=wrong_pct,
    )

    with pytest.raises(AggregationValidationError) as refused:
        _resolve(operation, change.period, (invoice,))

    assert refused.value.translated_message == "aggregation.oss_ioss.errors.iva_amount_mismatches_destination_rate"


def test_undeclared_devengo_in_the_changing_quarter_is_refused(operation: PinnedAuthorityOperation) -> None:
    """An issue date cannot choose between two rates the quarter really has."""
    change = rate_change_inside_a_quarter(operation)
    undated = _invoice(
        "SYNTHETIC-UNDATED",
        member_state=change.member_state,
        supply_date=None,
        issued_at=change.first_day_after,
        base="100.00",
        pct=change.pct_after,
    )

    with pytest.raises(AggregationValidationError) as refused:
        _resolve(operation, change.period, (undated,))

    assert refused.value.translated_message == "aggregation.oss_ioss.errors.rate_change_devengo_undeclared"
    assert refused.value.context is not None
    assert refused.value.context["invoice_number"] == "SYNTHETIC-UNDATED"
    assert refused.value.context["destination_member_state"] == change.member_state
    assert refused.value.context["rate_kind"] == "general"
    assert refused.value.context["period"] == change.period.registry_token


def test_undeclared_devengo_stays_advisory_where_the_quarter_has_one_rate(
    operation: PinnedAuthorityOperation,
) -> None:
    change = rate_change_inside_a_quarter(operation)
    member_state, pct = _stable_member_state(operation, change)
    undated = _invoice(
        "SYNTHETIC-UNDATED",
        member_state=member_state,
        supply_date=None,
        issued_at=change.first_day_after,
        base="100.00",
        pct=pct,
    )

    resolution = _resolve(operation, change.period, (undated,))

    assert _row(resolution, 1)[2:] == (pct, Decimal("100.00"), _cuota("100.00", pct))
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["devengo_date_proxy_attribution"]


def test_declared_devengo_beside_an_undated_other_state_is_not_refused(operation: PinnedAuthorityOperation) -> None:
    change = rate_change_inside_a_quarter(operation)
    member_state, pct = _stable_member_state(operation, change)
    dated = _invoice(
        "SYNTHETIC-DATED",
        member_state=change.member_state,
        supply_date=change.first_day_after,
        issued_at=change.first_day_after,
        base="100.00",
        pct=change.pct_after,
    )
    undated = _invoice(
        "SYNTHETIC-UNDATED",
        member_state=member_state,
        supply_date=None,
        issued_at=change.first_day_after,
        base="100.00",
        pct=pct,
    )

    resolution = _resolve(operation, change.period, (dated, undated))

    assert _occupied_rows(resolution) == [1, 2]


def test_date_outside_the_published_table_reads_the_nearest_edition_and_says_so(
    operation: PinnedAuthorityOperation,
) -> None:
    change = rate_change_inside_a_quarter(operation)
    variants = ordinary_general_variants(operation)[change.member_state]
    first_published = min(variant.valid_from or date.max for variant in variants)
    uncovered = first_published - timedelta(days=1)
    invoice = _invoice(
        "SYNTHETIC-UNCOVERED",
        member_state=change.member_state,
        supply_date=uncovered,
        issued_at=uncovered,
        base="100.00",
        pct=change.pct_before,
    )

    resolution = _resolve(operation, exterior_period(uncovered), (invoice,))

    assert [diagnostic.source_ref for diagnostic in resolution.diagnostics] == ["rate_date_projected"]


def test_rows_of_one_country_and_code_are_told_apart_only_by_their_percentage(
    operation: PinnedAuthorityOperation,
) -> None:
    """The verification gate reads the diagnostics, so none may stand between these rows and export."""
    change = rate_change_inside_a_quarter(operation)
    before, after = (
        _invoice(
            number,
            member_state=change.member_state,
            supply_date=supply_date,
            issued_at=supply_date,
            base="100.00",
            pct=pct,
        )
        for number, supply_date, pct in (
            ("SYNTHETIC-BEFORE", change.last_day_before, change.pct_before),
            ("SYNTHETIC-AFTER", change.first_day_after, change.pct_after),
        )
    )

    resolution = _resolve(operation, change.period, (before, after))

    rows = [_row(resolution, row) for row in (1, 2)]
    assert {row[:2] for row in rows} == {(change.member_state.upper(), "S")}
    assert {row[2] for row in rows} == {change.pct_before, change.pct_after}
    assert _occupied_rows(resolution) == [1, 2]
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == []

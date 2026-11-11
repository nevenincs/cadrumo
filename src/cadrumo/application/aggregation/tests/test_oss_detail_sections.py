"""Modelo 369 detail rows for every regime, through the real resolver and published authority.

Expected rows are worked by hand from the percentages the destination Member
States publish, and slot positions are the ones DR369 prints, so neither repeats
what the resolver computes:

* T36901 (Exterior) lists from position 221, T36904 (Union) from 222 and T36910
  (Importacion) from 253, each a 42-position line of country, percentage, code,
  base and cuota.
* France publishes 20 and 10; Poland publishes 23 and 8.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.money.rounding import round_to_cents
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_revision
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus, invoice_class_simplificada, operation_performed_role
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import TransactionKind
from ....domain.iva.errors import IvaRateNotFoundError
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.rates import IVA_RATE_FACT_ID
from ....domain.iva.schema import InvoiceKind, IvaRateKind
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.models import TransactionCatalogue
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..errors import AggregationValidationError
from ..oss_ioss_resolver import OssIossLedgerSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .oss_rate_change_support import ordinary_general_variants, rate_change_inside_a_quarter, variant_pct

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "2bb5bf4c-ff0d-440c-a428-b075558b3595"
_SUPPLY = date(filing_year_envelope().horizon, 2, 17)
_LINE_LENGTH = 42


@dataclass(frozen=True)
class Regime:
    revision_id: str
    token: str
    kind: str
    record: str
    first_position: int

    def period(self, on_date: date) -> Period:
        quarter = f"{(on_date.month - 1) // 3 + 1}T"
        code = {
            "esquema-exterior": f"EXT-{quarter}",
            "esquema-union": quarter,
            "esquema-importacion": f"{on_date.month:02d}",
        }[self.revision_id]
        return Period.from_year_and_code(on_date.year, code)


EXTERIOR = Regime("esquema-exterior", "external_scheme", "external_scheme_services", "modelo-369-exterior-t36901", 221)
UNION = Regime("esquema-union", "union_scheme", "oss_union_services", "modelo-369-union-t36904", 222)
IMPORT = Regime(
    "esquema-importacion", "import_scheme", "ioss_distance_sale_low_value", "modelo-369-importacion-t36910", 253
)
_REGIMES = (EXTERIOR, UNION, IMPORT)
_regime_ids = [regime.revision_id for regime in _REGIMES]


def oss_detail_sections_invoice(
    regime: Regime,
    number: str,
    *,
    country: str,
    tier: str,
    base: str,
    cuota: str,
    supply_date: date | None = _SUPPLY,
    issued_at: date | None = None,
    kind: str | None = None,
) -> Invoice:
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
            "issued_at": issued_at or supply_date,
            **dated,
            "counterparty_name": "Cliente ficticio",
            "invoice_class": invoice_class_simplificada(),
            "counterparty_country": country,
            "base_total": Decimal(base),
            "iva_total": Decimal(cuota),
            "grand_total": Decimal(base) + Decimal(cuota),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Operación ficticia",
                    quantity=Decimal("1"),
                    unit_price=Decimal(base),
                    subtotal=Decimal(base),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    oss_rate_kind=IvaRateKind(tier),
                    iva_amount=Decimal(cuota),
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime(regime.token),
            "oss_transaction_kind": TransactionKind(kind or regime.kind),
        }
    )


class Reader:
    bucket_id = BUCKET

    def __init__(self, invoices: tuple[Invoice, ...]) -> None:
        self._catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class Transactions:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def resolve(
    operation: PinnedAuthorityOperation,
    regime: Regime,
    invoices: tuple[Invoice, ...],
    *,
    period: Period | None = None,
    revision: ModeloRevision | None = None,
) -> CalculationSourceResolution:
    resolved_period = period or regime.period(_SUPPLY)
    return OssIossLedgerSourceResolver(
        ports=InvoiceCatalogueReadPorts(invoice_reader=Reader(invoices), transaction_reader=Transactions())
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET,
            work_unit_id="a" * 64,
            modelo="369",
            filing_year=resolved_period.filing_year,
            period=resolved_period,
            revision=revision or published_revision("369", regime.revision_id),
            operation=operation,
        )
    )


def _binding_at(revision: ModeloRevision, record: str, position: int) -> str:
    (binding,) = (
        binding.id
        for binding in revision.bindings
        if isinstance(binding.provider, ManualInputProvider)
        and binding.provider.record == record
        and binding.provider.offset == position
    )
    return binding


def oss_detail_sections_row(
    resolution: CalculationSourceResolution, regime: Regime, row: int
) -> tuple[str, str, Decimal, Decimal, Decimal]:
    revision = published_revision("369", regime.revision_id)
    start = regime.first_position + (row - 1) * _LINE_LENGTH
    country, pct, code, base, cuota = (
        _binding_at(revision, regime.record, start + offset) for offset in (0, 2, 7, 8, 25)
    )
    return (
        resolution.enum_binding_values[country],
        resolution.enum_binding_values[code],
        resolution.binding_values[pct],
        resolution.binding_values[base],
        resolution.binding_values[cuota],
    )


def _two_states_two_tiers(regime: Regime) -> tuple[Invoice, ...]:
    return (
        oss_detail_sections_invoice(regime, "SYNTHETIC-1", country="PL", tier="reduced", base="50.00", cuota="4.00"),
        oss_detail_sections_invoice(regime, "SYNTHETIC-2", country="FR", tier="general", base="100.00", cuota="20.00"),
        oss_detail_sections_invoice(regime, "SYNTHETIC-3", country="PL", tier="general", base="100.00", cuota="23.00"),
        oss_detail_sections_invoice(regime, "SYNTHETIC-4", country="FR", tier="reduced", base="20.00", cuota="2.00"),
    )


@pytest.mark.parametrize("regime", _REGIMES, ids=_regime_ids)
def test_france_and_a_third_state_at_both_rates_take_their_own_rows(
    operation: PinnedAuthorityOperation, regime: Regime
) -> None:
    resolution = resolve(operation, regime, _two_states_two_tiers(regime))

    assert [oss_detail_sections_row(resolution, regime, row) for row in (1, 2, 3, 4)] == [
        ("FR", "S", Decimal("20"), Decimal("100.00"), Decimal("20.00")),
        ("FR", "R", Decimal("10"), Decimal("20.00"), Decimal("2.00")),
        ("PL", "S", Decimal("23"), Decimal("100.00"), Decimal("23.00")),
        ("PL", "R", Decimal("8"), Decimal("50.00"), Decimal("4.00")),
    ]
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == []
    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert [row.row_index for row in closed[regime.record].rows if row.occupied] == [1, 2, 3, 4]
    assert len(closed[regime.record].rows) == 28


@pytest.mark.parametrize("regime", _REGIMES, ids=_regime_ids)
def test_lines_at_one_destination_and_rate_sum_into_one_row(
    operation: PinnedAuthorityOperation, regime: Regime
) -> None:
    resolution = resolve(
        operation,
        regime,
        (
            oss_detail_sections_invoice(
                regime, "SYNTHETIC-1", country="FR", tier="general", base="100.00", cuota="20.00"
            ),
            oss_detail_sections_invoice(
                regime, "SYNTHETIC-2", country="FR", tier="general", base="50.00", cuota="10.00"
            ),
        ),
    )

    assert oss_detail_sections_row(resolution, regime, 1) == (
        "FR",
        "S",
        Decimal("20"),
        Decimal("150.00"),
        Decimal("30.00"),
    )
    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert [row.row_index for row in closed[regime.record].rows if row.occupied] == [1]


def test_union_closes_its_goods_and_establishment_tables_empty_on_the_same_read(
    operation: PinnedAuthorityOperation,
) -> None:
    resolution = resolve(operation, UNION, _two_states_two_tiers(UNION))

    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert sorted(closed) == [
        "modelo-369-union-t36904",
        "modelo-369-union-t36905",
        "modelo-369-union-t36906",
        "modelo-369-union-t36907",
        "modelo-369-union-t36908",
    ]
    assert not any(row.occupied for row in closed["modelo-369-union-t36908"].rows)
    for record in ("modelo-369-union-t36905", "modelo-369-union-t36906", "modelo-369-union-t36907"):
        assert len(closed[record].rows) == 28
        assert not any(row.occupied for row in closed[record].rows)
    # T36906 and T36907 lines are 59 positions of seven columns; T36905's are five.
    assert len(closed["modelo-369-union-t36905"].rows[0].binding_ids) == 5
    assert len(closed["modelo-369-union-t36906"].rows[0].binding_ids) == 7
    assert len(closed["modelo-369-union-t36907"].rows[0].binding_ids) == 7


@pytest.mark.parametrize("kind", ["oss_union_goods_distance_sale", "oss_union_goods_interface_facilitated"])
def test_union_goods_stay_unrouted_because_the_invoice_has_no_state_of_dispatch(
    operation: PinnedAuthorityOperation, kind: str
) -> None:
    """LIVA art. 163 duovicies.Uno.c) separates goods by dispatch state; T36905 and T36907 follow it."""
    resolution = resolve(
        operation,
        UNION,
        (
            oss_detail_sections_invoice(
                UNION, "SYNTHETIC-1", country="FR", tier="general", base="100.00", cuota="20.00"
            ),
            oss_detail_sections_invoice(
                UNION, "SYNTHETIC-2", country="FR", tier="general", base="100.00", cuota="20.00", kind=kind
            ),
        ),
    )

    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["unrouted_observation"]
    assert resolution.closed_record_row_sets == ()


def test_a_line_of_another_regime_stays_unrouted_on_this_revision(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(
        operation,
        EXTERIOR,
        (
            oss_detail_sections_invoice(
                IMPORT, "SYNTHETIC-1", country="FR", tier="general", base="100.00", cuota="20.00"
            ),
        ),
    )

    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["unrouted_observation"]
    assert resolution.closed_record_row_sets == ()


def test_union_services_in_the_state_of_identification_are_refused(operation: PinnedAuthorityOperation) -> None:
    """LIVA art. 163 unvicies.Uno limits the scheme to services in a state other than the seller's."""
    with pytest.raises(AggregationValidationError) as refused:
        resolve(
            operation,
            UNION,
            (
                oss_detail_sections_invoice(
                    UNION, "SYNTHETIC-1", country="ES", tier="general", base="100.00", cuota="21.00"
                ),
            ),
        )
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.detail_consumption_state_excluded"


@pytest.mark.parametrize("regime", (EXTERIOR, IMPORT), ids=["esquema-exterior", "esquema-importacion"])
def test_spain_is_an_ordinary_state_of_consumption_outside_the_union_scheme(
    operation: PinnedAuthorityOperation, regime: Regime
) -> None:
    resolution = resolve(
        operation,
        regime,
        (
            oss_detail_sections_invoice(
                regime, "SYNTHETIC-1", country="ES", tier="general", base="100.00", cuota="21.00"
            ),
        ),
    )

    assert oss_detail_sections_row(resolution, regime, 1) == (
        "ES",
        "S",
        Decimal("21"),
        Decimal("100.00"),
        Decimal("21.00"),
    )


@pytest.mark.parametrize("regime", _REGIMES, ids=_regime_ids)
def test_a_date_before_the_published_rates_refuses_a_figure_the_projection_does_not_explain(
    operation: PinnedAuthorityOperation, regime: Regime
) -> None:
    earliest = min(
        variant.valid_from for variant in ordinary_general_variants(operation)["fr"] if variant.valid_from is not None
    )
    uncovered = earliest - timedelta(days=1)
    with pytest.raises(IvaRateNotFoundError):
        resolve(
            operation,
            regime,
            (
                oss_detail_sections_invoice(
                    regime,
                    "SYNTHETIC-1",
                    country="FR",
                    tier="general",
                    base="100.00",
                    cuota="19.60",
                    supply_date=uncovered,
                ),
            ),
            period=regime.period(uncovered),
        )


def test_union_rows_either_side_of_a_rate_change_carry_their_own_percentage(
    operation: PinnedAuthorityOperation,
) -> None:
    change = rate_change_inside_a_quarter(operation)
    code = change.member_state.upper()
    before_cuota = round_to_cents(Decimal("100.00") * change.pct_before / Decimal("100"))
    after_cuota = round_to_cents(Decimal("200.00") * change.pct_after / Decimal("100"))

    resolution = resolve(
        operation,
        UNION,
        (
            oss_detail_sections_invoice(
                UNION,
                "SYNTHETIC-BEFORE",
                country=code,
                tier="general",
                base="100.00",
                cuota=str(before_cuota),
                supply_date=change.last_day_before,
            ),
            oss_detail_sections_invoice(
                UNION,
                "SYNTHETIC-AFTER",
                country=code,
                tier="general",
                base="200.00",
                cuota=str(after_cuota),
                supply_date=change.first_day_after,
            ),
        ),
        period=UNION.period(change.first_day_after),
    )

    assert {oss_detail_sections_row(resolution, UNION, row) for row in (1, 2)} == {
        (code, "S", change.pct_before, Decimal("100.00"), before_cuota),
        (code, "S", change.pct_after, Decimal("200.00"), after_cuota),
    }


def test_union_refuses_an_issue_date_standing_in_for_the_devengo_across_a_rate_change(
    operation: PinnedAuthorityOperation,
) -> None:
    change = rate_change_inside_a_quarter(operation)
    cuota = round_to_cents(Decimal("100.00") * change.pct_after / Decimal("100"))
    with pytest.raises(AggregationValidationError) as refused:
        resolve(
            operation,
            UNION,
            (
                oss_detail_sections_invoice(
                    UNION,
                    "SYNTHETIC-1",
                    country=change.member_state.upper(),
                    tier="general",
                    base="100.00",
                    cuota=str(cuota),
                    supply_date=None,
                    issued_at=change.first_day_after,
                ),
            ),
            period=UNION.period(change.first_day_after),
        )
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.rate_change_devengo_undeclared"


def test_importacion_files_by_month_so_each_side_of_a_change_is_its_own_return(
    operation: PinnedAuthorityOperation,
) -> None:
    """A month with one rate has nothing to refuse, even on an issue date, unlike the quarter that holds both."""
    change = rate_change_inside_a_quarter(operation)
    assert change.last_day_before.month != change.first_day_after.month, "this fixture needs a change at a month start"
    cuota = round_to_cents(Decimal("100.00") * change.pct_after / Decimal("100"))

    resolution = resolve(
        operation,
        IMPORT,
        (
            oss_detail_sections_invoice(
                IMPORT,
                "SYNTHETIC-1",
                country=change.member_state.upper(),
                tier="general",
                base="100.00",
                cuota=str(cuota),
                supply_date=None,
                issued_at=change.first_day_after,
            ),
        ),
        period=IMPORT.period(change.first_day_after),
    )

    assert oss_detail_sections_row(resolution, IMPORT, 1)[2] == change.pct_after


def _distinct_rows(operation: PinnedAuthorityOperation, regime: Regime, count: int) -> tuple[Invoice, ...]:
    """Build one invoice per published destination and tier, from the fact's raw percentages."""
    tiers: list[tuple[str, str, Decimal]] = []
    for variant in operation.governed_fact(IVA_RATE_FACT_ID).variants:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        state = str(selectors.get("member_state"))
        covers = (variant.valid_from or date.max) <= _SUPPLY and (
            variant.valid_to is None or variant.valid_to >= _SUPPLY
        )
        if (
            covers
            and selectors.get("kind") in {"general", "reduced"}
            and selectors.get("rate_role") == "ordinary"
            and state != "es"
        ):
            tiers.append((state, str(selectors["kind"]), variant_pct(variant)))
    assert len(tiers) >= count, "the published schedule cannot fill the page this test needs"
    return tuple(
        oss_detail_sections_invoice(
            regime,
            f"SYNTHETIC-{index}",
            country=state.upper(),
            tier=tier,
            base="100.00",
            cuota=str(round_to_cents(pct)),
        )
        for index, (state, tier, pct) in enumerate(sorted(tiers)[:count], start=1)
    )


@pytest.mark.parametrize("regime", _REGIMES, ids=_regime_ids)
def test_twenty_eight_rows_fill_the_page(operation: PinnedAuthorityOperation, regime: Regime) -> None:
    resolution = resolve(operation, regime, _distinct_rows(operation, regime, 28))

    closed = {row_set.record_id: row_set for row_set in resolution.closed_record_row_sets}
    assert all(row.occupied for row in closed[regime.record].rows)
    assert oss_detail_sections_row(resolution, regime, 28)[3] == Decimal("100.00")


@pytest.mark.parametrize("regime", _REGIMES, ids=_regime_ids)
def test_a_twenty_ninth_row_is_refused_rather_than_exported_short(
    operation: PinnedAuthorityOperation, regime: Regime
) -> None:
    with pytest.raises(AggregationValidationError) as refused:
        resolve(operation, regime, _distinct_rows(operation, regime, 29))
    assert refused.value.translated_message == "aggregation.oss_ioss.errors.detail_rows_exceed_page"
    assert refused.value.context is not None
    assert refused.value.context["rows"] == "29"
    assert refused.value.context["capacity"] == "28"

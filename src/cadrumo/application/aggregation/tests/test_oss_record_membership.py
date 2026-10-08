"""Complete Exterior service membership comes from a bound catalogue and wire layout."""

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_revision
from ....domain.invoices.enums import IvaRate, PaymentStatus, operation_performed_role
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind, TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import IvaRateKind
from ....domain.transactions.models import LedgerDatePartition, TransactionCatalogue
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError, InvoiceCatalogueReadPorts
from .. import oss_ioss
from ..errors import AggregationValidationError
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "2bb5bf4c-ff0d-440c-a428-b075558b3595"
_DATE = date(2025, 7, 15)


class _InvoiceReader:
    def __init__(self, invoices: tuple[Invoice, ...], *, bucket_id: str | None = _BUCKET, degraded: bool = False):
        self.bucket_id = bucket_id
        self.catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})
        self.degraded = degraded
        self.reads = 0

    def load(self) -> InvoiceCatalogue:
        self.reads += 1
        if self.degraded:
            raise InvoiceCatalogueReadPersistenceError("synthetic-unavailable-catalogue")
        return self.catalogue


class _Transactions:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _invoice(
    number: str = "SYNTHETIC-1", *, base: str = "100", country: str = "DE", supply_date: date = _DATE
) -> Invoice:
    amount = Decimal(base)
    quota = amount * (Decimal("0.19") if country == "DE" else Decimal("0.20"))
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": _DATE,
            "operation_date": supply_date,
            "operation_date_role": operation_performed_role(effective_date=supply_date),
            "counterparty_name": "Cliente ficticio",
            "counterparty_tax_id": "DE345678901" if country == "DE" else "FR12345678901",
            "counterparty_country": country,
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


def _context(operation: PinnedAuthorityOperation, revision: ModeloRevision | None = None) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=_BUCKET,
        work_unit_id="a" * 64,
        modelo="369",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "EXT-3T"),
        revision=revision or published_revision("369", "esquema-exterior"),
        operation=operation,
    )


def _resolver(reader: _InvoiceReader) -> oss_ioss.OssIossLedgerSourceResolver:
    return oss_ioss.OssIossLedgerSourceResolver(
        ports=InvoiceCatalogueReadPorts(invoice_reader=reader, transaction_reader=_Transactions())
    )


def test_bound_catalogue_closes_all_declared_service_slots(operation: PinnedAuthorityOperation) -> None:
    reader = _InvoiceReader((_invoice(), _invoice("SYNTHETIC-2", base="200")))
    resolution = _resolver(reader).resolve(_context(operation))
    (closed,) = resolution.closed_record_row_sets
    assert reader.reads == 1
    assert len(closed.rows) == 28
    assert all(len(row.binding_ids) == 5 for row in closed.rows)
    assert [row.row_index for row in closed.rows if row.occupied] == [1]
    assert len(closed.unused_binding_ids) == 135
    assert closed.bucket_id == _BUCKET
    assert closed.authority_generation == operation.pin().logical_generation
    assert closed.registry_snapshot_ref.period == "EXT-3T"
    assert resolution.binding_values["modelo-369-exterior-fichero.3-prestaciones-de-servicios-cuota-iva-1"] == Decimal(
        "57"
    )
    assert all("t36902" not in binding for binding in closed.binding_ids)
    assert "closed_record_row_sets" not in resolution.model_dump(mode="json")


def test_fingerprint_covers_membership_and_amounts_but_not_catalogue_order(operation: PinnedAuthorityOperation) -> None:
    first, second = _invoice(), _invoice("SYNTHETIC-2", base="200")

    def fingerprint(invoices: tuple[Invoice, ...]) -> str:
        return (
            _resolver(_InvoiceReader(invoices))
            .resolve(_context(operation))
            .closed_record_row_sets[0]
            .source_fingerprint
        )

    original = fingerprint((first, second))
    assert original == fingerprint((second, first))
    assert original != fingerprint((first,))
    assert original != fingerprint((first, _invoice("SYNTHETIC-2", base="300")))
    changed_supply_date = _invoice("SYNTHETIC-2", base="200", supply_date=date(2025, 7, 16))
    assert changed_supply_date.invoice_id == second.invoice_id
    assert original != fingerprint((first, changed_supply_date))


@pytest.mark.parametrize(
    "scenario", ["empty", "unbound", "degraded", "unrouted", "no-work-unit", "explicit-candidates"]
)
def test_incomplete_or_unadmitted_sources_cannot_close_rows(operation: PinnedAuthorityOperation, scenario: str) -> None:
    reader = _InvoiceReader(
        () if scenario == "empty" else (_invoice(country="FR" if scenario == "unrouted" else "DE"),),
        bucket_id=None if scenario == "unbound" else _BUCKET,
        degraded=scenario == "degraded",
    )
    context = _context(operation)
    resolver = _resolver(reader)
    if scenario == "no-work-unit":
        context = context.model_copy(update={"work_unit_id": None})
    if scenario == "explicit-candidates":
        ports = InvoiceCatalogueReadPorts(invoice_reader=reader, transaction_reader=_Transactions())
        projection = oss_ioss.project_oss_ioss_invoices_from_repositories(period=context.period, ports=ports)
        resolver = oss_ioss.OssIossLedgerSourceResolver(ports=ports, candidates=projection.candidates)
    resolution = resolver.resolve(context)
    assert resolution.closed_record_row_sets == ()


def test_wrong_profile_is_refused_before_read(operation: PinnedAuthorityOperation) -> None:
    reader = _InvoiceReader((_invoice(),), bucket_id="different-profile")
    with pytest.raises(AggregationValidationError):
        _resolver(reader).resolve(_context(operation))
    assert reader.reads == 0


def test_lightweight_revision_hydrates_geometry_on_the_same_authority(operation: PinnedAuthorityOperation) -> None:
    lightweight = operation.revision("369", "esquema-exterior")
    assert not lightweight.export_layouts
    resolved = _resolver(_InvoiceReader((_invoice(),))).resolve(_context(operation, lightweight))
    assert len(resolved.closed_record_row_sets[0].rows) == 28
    assert resolved.closed_record_row_sets[0].authority_generation == operation.pin().logical_generation


def test_geometry_hydration_cannot_replace_conflicting_binding_declarations(
    operation: PinnedAuthorityOperation,
) -> None:
    lightweight = operation.revision("369", "esquema-exterior")
    changed = lightweight.model_copy(update={"bindings": lightweight.bindings[:-1]})
    with pytest.raises(AggregationValidationError):
        _resolver(_InvoiceReader((_invoice(),))).resolve(_context(operation, changed))


@pytest.mark.parametrize("mutation", ["missing-last-row", "missing-unused-quota", "duplicate-owner", "shifted-offset"])
def test_registry_holes_cannot_be_promoted_to_complete_unused_rows(
    operation: PinnedAuthorityOperation, mutation: str
) -> None:
    revision = published_revision("369", "esquema-exterior")
    bindings = list(revision.bindings)
    last = [
        binding
        for binding in bindings
        if isinstance(binding.provider, ManualInputProvider)
        and binding.provider.field is not None
        and binding.provider.field.startswith("3-prestaciones-de-servicios-")
        and binding.provider.field.endswith("-28")
    ]
    if mutation == "missing-last-row":
        bindings = [binding for binding in bindings if binding not in last]
    elif mutation == "missing-unused-quota":
        quota = next(binding for binding in last if "cuota-iva-28" in str(binding.id))
        bindings.remove(quota)
    elif mutation == "duplicate-owner":
        bindings.append(last[0].model_copy(update={"id": "duplicate-row-owner"}))
    else:
        original = last[0]
        bindings[bindings.index(original)] = original.model_copy(
            update={"provider": original.provider.model_copy(update={"offset": 9999})}
        )
    revision = revision.model_copy(update={"bindings": tuple(bindings)})
    with pytest.raises(AggregationValidationError):
        _resolver(_InvoiceReader((_invoice(),))).resolve(_context(operation, revision))

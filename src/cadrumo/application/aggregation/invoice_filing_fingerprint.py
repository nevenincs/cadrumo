"""Capture the invoices a calculation read, for the verify-time drift comparison.

The scope is each reader's own selection, so a move out of a period registers as
a removal and a move in as an addition:

- The invoice source families (Modelo 347, Modelo 349) take the records their
  resolver takes: bucket, issue date in the period, declared direction.
- A revision with screened IVA bindings (Modelo 303, Modelo 390) compares every
  invoice devengando in its aggregation period against the ledger.
- OSS/IOSS reads tagged issued invoices devengando in the period.
- The renta income and expense sources read an invoice through a row: its figures
  replace the row's, so invoices linked to a contributor count.
- The renta income source also adds what accrued and is still unpaid, and nets
  corrections, with no row at all, so from field-set version 2 every issued invoice
  entering its window under the declared criterion counts.
- The renta expense sources refuse an unpaid received invoice and net a received
  correction, with no row at all, so from field-set version 3 every received invoice
  entering its window counts too.

The field set is the union of what those readers consult, including the
decomposition contract that grounds income evidence. What is left out, and why:

- ``invoice_number``, ``series``, ``notes``, both addresses, ``payment_id``,
  ``exemption_reference``, ``created_at``, ``updated_at``, ``provenance``: no
  calculation reads them.
- ``retention_rate``: nothing reads it; ``retention_amount`` is the figure.
- ``fx_rate_date``, ``fx_rate_source``, ``fx_rate_observation_date``: they
  evidence ``fx_rate`` without entering the conversion.
- Line ``quantity`` and ``unit_price``: ``subtotal`` is bound to their product.
- Line ``description``: a wording advisory on durable expenses reads it, no figure.
- Line ``spending_category_id``: no production consumer.

Withholding modelos read captured observations rather than the invoice, so their
baseline-guarded capture stays their own concern.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Final, cast

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingSourceKind
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ledger_iva_screen_bindings import invoice_ledger_screen_binding_ids
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.schema import InvoiceKind
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.invoice_fingerprint import (
    InvoiceFingerprintSnapshot,
    InvoiceFingerprintVerdict,
    InvoiceRowFingerprint,
    diff_invoice_fingerprints,
    invoice_snapshot_fingerprint,
)
from ...domain.modelos.work_unit import WorkUnit
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..invoices.source_observations import (
    invoice_in_bucket_and_period,
    invoice_source_kind,
    invoice_sources_declared,
)
from .invoice_devengo import resolve_invoice_devengo
from .ledger_membership import ledger_transaction_ref_identity
from .modelo_bindings import aggregation_period_for_modelo
from .renta_imputation import ActivityImputationCriterion, ImputationCriteria
from .renta_income_diagnostics import invoice_enters_window

# Append-only and versioned for the reasons the ledger field sets are: widening a
# set in place would report every stored draft as drifted at once.
_INVOICE_FIELDS_V1: Final[tuple[str, ...]] = (
    "bucket_id",
    "kind",
    "invoice_class",
    "issued_at",
    "operation_date",
    "operation_date_role",
    "payment_status",
    "counterparty_name",
    "counterparty_tax_id",
    "counterparty_country",
    "counterparty_identification_state",
    "legal_mentions",
    "base_total",
    "iva_total",
    "grand_total",
    "currency",
    "fx_rate",
    "linked_transaction_ids",
    "business_premises_lease",
    "iva_category",
    "operation_type",
    "travel_agency_mediation",
    "collected_on_behalf_of_tax_id",
    "collected_on_behalf_of_name",
    "is_subvencion_ayuda",
    "outside_economic_activity",
    "oss_ioss_regime",
    "oss_transaction_kind",
    "retention_amount",
    "recargo_amount",
    "suplido_amount",
    "lines",
)

# A correction nets against the invoice it names, so the name moves a figure.
_INVOICE_FIELDS_V2: Final[tuple[str, ...]] = (*_INVOICE_FIELDS_V1, "rectifies_invoice_number")

# Version 3 widens the scope, not the fields.
_INVOICE_FIELD_SETS: Final[Mapping[int, tuple[str, ...]]] = {
    1: _INVOICE_FIELDS_V1,
    2: _INVOICE_FIELDS_V2,
    3: _INVOICE_FIELDS_V2,
}

#: The version every new fingerprint is captured under.
CURRENT_INVOICE_FIELD_SET_VERSION: Final = 3

#: The first version whose scope holds the invoices renta income reads with no row.
#: An older snapshot keeps its narrower scope, or its every draft would read as drifted.
_ACCRUED_INCOME_SCOPE_VERSION: Final = 2

#: The first version whose scope holds the invoices renta expense reads with no row.
_ACCRUED_EXPENSE_SCOPE_VERSION: Final = 3

_ACCRUED_EXPENSE_SOURCES: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
    }
)

_LINKED_INVOICE_SOURCES: Final[frozenset[BindingSourceKind]] = frozenset(
    {
        BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
    }
)

_EXTERIOR_PERIOD_PREFIX: Final = "EXT-"


@dataclass(frozen=True, slots=True)
class _InvoiceReadSelection:
    """Which invoice readers a selected registry revision enrols."""

    direct_sources: frozenset[BindingSourceKind]
    iva_screen: bool
    oss: bool
    linked: bool
    accrued_income: bool
    accrued_expense: bool

    @property
    def reads_invoices(self) -> bool:
        return bool(self.direct_sources) or self.iva_screen or self.oss or self.linked


def _read_selection(revision: ModeloRevision, *, work_unit: WorkUnit) -> _InvoiceReadSelection:
    declared = frozenset(binding.source for binding in revision.bindings)
    return _InvoiceReadSelection(
        direct_sources=invoice_sources_declared(revision),
        iva_screen=BindingSourceKind.LEDGER_IVA_AGGREGATION in declared
        and bool(invoice_ledger_screen_binding_ids(revision, modelo=work_unit.modelo)),
        oss=BindingSourceKind.LEDGER_OSS_AGGREGATION in declared,
        linked=bool(declared & _LINKED_INVOICE_SOURCES),
        # The objective instalment's income has no accrued path: it reads activity volume.
        accrued_income=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION in declared
        and work_unit.modelo != form_for_role("renta.objective_instalment"),
        accrued_expense=bool(declared & _ACCRUED_EXPENSE_SOURCES),
    )


def revision_reads_invoices(revision: ModeloRevision, *, work_unit: WorkUnit) -> bool:
    """Whether any calculation reader of this registry revision consults the catalogue."""
    return _read_selection(revision, work_unit=work_unit).reads_invoices


def fingerprint_scope_is_narrower(
    snapshot: InvoiceFingerprintSnapshot,
    *,
    revision: ModeloRevision,
    work_unit: WorkUnit,
    criteria: ImputationCriteria,
) -> bool:
    """Whether this stored fingerprint leaves out invoices the draft's accrued income or expense may rest on."""
    selection = _read_selection(revision, work_unit=work_unit)
    return criteria.usable(work_unit.filing_year) is ActivityImputationCriterion.DEVENGO and (
        (snapshot.field_set_version < _ACCRUED_INCOME_SCOPE_VERSION and selection.accrued_income)
        or (snapshot.field_set_version < _ACCRUED_EXPENSE_SCOPE_VERSION and selection.accrued_expense)
    )


def draft_contributor_identities(
    source_transaction_ids: Iterable[str],
    source_issues: Iterable[CalculationSourceIssue],
) -> frozenset[str]:
    """Return the contributing rows plus the ledger rows a source issue held back."""
    identities = set(source_transaction_ids)
    for issue in source_issues:
        if issue.binding_source not in LEDGER_BINDING_SOURCE_KINDS:
            continue
        identity = ledger_transaction_ref_identity(issue.source_ref)
        if identity is not None:
            identities.add(identity)
    return frozenset(identities)


def _oss_period(period: Period) -> Period | None:
    projection = period
    if period.registry_token.startswith(_EXTERIOR_PERIOD_PREFIX):
        projection = Period.from_year_and_code(
            period.filing_year,
            period.registry_token.removeprefix(_EXTERIOR_PERIOD_PREFIX),
        )
    return projection if projection.has_date_span() else None


def _in_direct_scope(
    invoice: Invoice,
    *,
    bucket_id: str,
    period: Period | None,
    selection: _InvoiceReadSelection,
) -> bool:
    return (
        period is not None
        and invoice_in_bucket_and_period(invoice, bucket_id=bucket_id, period=period)
        and BindingSourceKind(invoice_source_kind(invoice)) in selection.direct_sources
    )


def _in_oss_scope(invoice: Invoice, *, period: Period | None, devengo: date) -> bool:
    return (
        period is not None
        and invoice.kind is InvoiceKind.ISSUED
        and invoice.oss_ioss_regime is not None
        and invoice.oss_transaction_kind is not None
        and period.contains(devengo)
    )


def _in_linked_scope(
    invoice: Invoice,
    *,
    selection: _InvoiceReadSelection,
    linked_invoice_ids: frozenset[str],
    contributors: frozenset[str],
) -> bool:
    return selection.linked and (
        invoice.invoice_id in linked_invoice_ids or not contributors.isdisjoint(invoice.linked_transaction_ids)
    )


def _invoices_in_scope(
    catalogue: InvoiceCatalogue,
    *,
    selection: _InvoiceReadSelection,
    work_unit: WorkUnit,
    linked_invoice_ids: frozenset[str],
    contributors: frozenset[str],
    accrued_kinds: frozenset[InvoiceKind],
    criteria: ImputationCriteria,
) -> tuple[Invoice, ...]:
    period = work_unit.period
    bucket_id = work_unit.bucket_id
    iva_period = (
        aggregation_period_for_modelo(filing_year=work_unit.filing_year, code=period.registry_token)
        if selection.iva_screen
        else None
    )
    oss_period = _oss_period(period) if selection.oss else None
    # A period without a calendar span (the OSS exterior periods) has no issue-date scope.
    direct_period = period if selection.direct_sources and period.has_date_span() else None
    accrued_end = (
        aggregation_period_for_modelo(filing_year=work_unit.filing_year, code=period.registry_token).end_date
        if accrued_kinds
        else None
    )

    def in_accrued_scope(invoice: Invoice) -> bool:
        return (
            accrued_end is not None
            and invoice.kind in accrued_kinds
            and invoice_enters_window(
                invoice,
                kind=invoice.kind,
                bucket_id=bucket_id,
                window_start=date(work_unit.filing_year, 1, 1),
                window_end=accrued_end,
                criteria=criteria,
            )
        )

    def in_scope(invoice: Invoice) -> bool:
        if invoice.bucket_id is not None and invoice.bucket_id != bucket_id:
            return False
        devengo = resolve_invoice_devengo(invoice).devengo_date
        return (
            _in_direct_scope(invoice, bucket_id=bucket_id, period=direct_period, selection=selection)
            or (iva_period is not None and iva_period.contains(devengo))
            or _in_oss_scope(invoice, period=oss_period, devengo=devengo)
            or _in_linked_scope(
                invoice, selection=selection, linked_invoice_ids=linked_invoice_ids, contributors=contributors
            )
            or in_accrued_scope(invoice)
        )

    return tuple(invoice for invoice in catalogue.values() if in_scope(invoice))


def _canonical(value: object) -> object:
    """Render one fact so equal typed values digest equally."""
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, Decimal):
        # 10.0 and 10.00 are the same money; a textual comparison would call an
        # untouched figure drifted after a round trip through another scale.
        return "0" if value == 0 else format(value.normalize(), "f")
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, tuple | list | frozenset | set):
        items = cast("Iterable[object]", value)
        return sorted(canonical_json_bytes(_canonical(item)).decode("utf-8") for item in items)
    return str(value)


def _canonical_line(line: InvoiceLine) -> dict[str, object]:
    return {
        "subtotal": _canonical(line.subtotal),
        "iva_rate": _canonical(line.iva_rate),
        "iva_amount": _canonical(line.iva_amount),
        "oss_rate_kind": _canonical(line.oss_rate_kind),
    }


def _canonical_field(invoice: Invoice, name: str) -> object:
    if name == "lines":
        return sorted(canonical_json_bytes(_canonical_line(line)).decode("utf-8") for line in invoice.lines)
    if name == "business_premises_lease":
        lease = invoice.business_premises_lease
        if lease is None:
            return None
        situation = lease.situacion_inmueble
        return {
            "situacion_inmueble": None if situation is None else situation.code,
            "referencia_catastral": lease.referencia_catastral,
        }
    return _canonical(getattr(invoice, name))


def invoice_row_fingerprint(
    invoice: Invoice,
    *,
    field_set_version: int = CURRENT_INVOICE_FIELD_SET_VERSION,
) -> str:
    """Return the digest of one invoice's calculation facts under a field-set version.

    Raises:
        ModeloValidationError: A newer build wrote the version; comparing it under
            a narrower set would report unchanged for facts this build cannot see.
    """
    fields = _INVOICE_FIELD_SETS.get(field_set_version)
    if fields is None:
        raise ModeloValidationError(
            f"invoice fingerprint field-set version {field_set_version} is unknown to this build; "
            f"known versions are {sorted(_INVOICE_FIELD_SETS)}",
        )
    payload = {name: _canonical_field(invoice, name) for name in fields}
    return sha256_hex(canonical_json_bytes(payload))


def _linked_invoice_ids(ports: InvoiceCatalogueReadPorts, contributors: frozenset[str]) -> frozenset[str]:
    if not contributors:
        return frozenset[str]()
    named: set[str] = set()
    for transaction in ports.transaction_reader.load().values():
        if transaction.transaction_id not in contributors:
            continue
        for reference in (transaction.invoice_id, transaction.purchase_invoice_evidence_id):
            if reference is not None:
                named.add(reference)
    return frozenset(named)


def _accrued_kinds(selection: _InvoiceReadSelection, *, field_set_version: int) -> frozenset[InvoiceKind]:
    """Return the kinds whose window-entering invoices this version's scope holds."""
    kinds: set[InvoiceKind] = set()
    if selection.accrued_income and field_set_version >= _ACCRUED_INCOME_SCOPE_VERSION:
        kinds.add(InvoiceKind.ISSUED)
    if selection.accrued_expense and field_set_version >= _ACCRUED_EXPENSE_SCOPE_VERSION:
        kinds.add(InvoiceKind.RECEIVED)
    return frozenset(kinds)


def _current_rows(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    contributors: frozenset[str],
    ports: InvoiceCatalogueReadPorts,
    field_set_version: int,
    criteria: ImputationCriteria,
) -> dict[str, str]:
    selection = _read_selection(revision, work_unit=work_unit)
    invoices = _invoices_in_scope(
        ports.invoice_reader.load(),
        selection=selection,
        work_unit=work_unit,
        linked_invoice_ids=_linked_invoice_ids(ports, contributors) if selection.linked else frozenset(),
        contributors=contributors,
        accrued_kinds=_accrued_kinds(selection, field_set_version=field_set_version),
        criteria=criteria,
    )
    return {
        invoice.invoice_id: invoice_row_fingerprint(invoice, field_set_version=field_set_version)
        for invoice in invoices
    }


def capture_invoice_fingerprint(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    contributors: frozenset[str],
    ports: InvoiceCatalogueReadPorts,
    captured_at: datetime,
    criteria: ImputationCriteria,
) -> InvoiceFingerprintSnapshot | None:
    """Fingerprint the in-scope invoices, or return ``None`` when the modelo reads none."""
    if not revision_reads_invoices(revision, work_unit=work_unit):
        return None
    current = _current_rows(
        work_unit=work_unit,
        revision=revision,
        contributors=contributors,
        ports=ports,
        field_set_version=CURRENT_INVOICE_FIELD_SET_VERSION,
        criteria=criteria,
    )
    rows = tuple(
        InvoiceRowFingerprint(invoice_id=invoice_id, fingerprint=current[invoice_id]) for invoice_id in sorted(current)
    )
    return InvoiceFingerprintSnapshot(
        rows=rows,
        snapshot_fingerprint=invoice_snapshot_fingerprint(rows),
        captured_at=captured_at,
        field_set_version=CURRENT_INVOICE_FIELD_SET_VERSION,
    )


def evaluate_invoice_fingerprint(
    snapshot: InvoiceFingerprintSnapshot,
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    contributors: frozenset[str],
    ports: InvoiceCatalogueReadPorts,
    criteria: ImputationCriteria,
) -> InvoiceFingerprintVerdict:
    """Compare a stored fingerprint with the catalogue, under the stored version's fields and scope."""
    return diff_invoice_fingerprints(
        snapshot,
        _current_rows(
            work_unit=work_unit,
            revision=revision,
            contributors=contributors,
            ports=ports,
            field_set_version=snapshot.field_set_version,
            criteria=criteria,
        ),
    )


__all__ = [
    "CURRENT_INVOICE_FIELD_SET_VERSION",
    "capture_invoice_fingerprint",
    "draft_contributor_identities",
    "evaluate_invoice_fingerprint",
    "fingerprint_scope_is_narrower",
    "invoice_row_fingerprint",
    "revision_reads_invoices",
]

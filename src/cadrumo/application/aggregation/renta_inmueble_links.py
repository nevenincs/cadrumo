"""Read a profile's property and lease rows and join the ledger rows that name them.

A ledger row names a lease (rent received) or a property (an expense paid) by the row key of that record.
The join keeps each row under the record it names and reports, as a typed finding, every row it cannot place.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.gasto_capital_inmobiliario import GastoCapitalInmobiliarioCatalogue
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamiento_from_row,
    inmueble_from_row,
    rows_from_facts,
)
from ...domain.contribuyente.inmueble_record import InmuebleRecord
from ...domain.renta.retencion_soportada import RetencionSoportadaRecord
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ..user_profile.profile_read_recorder import profile_values_under
from .currency_predicates import is_non_eur_without_conversion
from .renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFinding
from .renta_inmueble_period import Ejercicio, Occupancy


@dataclass(slots=True)
class Records:
    """The property and lease records read from the profile, and the findings of the rows that cannot be read."""

    inmuebles: dict[int, InmuebleRecord] = field(default_factory=dict)
    leases: dict[int, ArrendamientoRecord] = field(default_factory=dict)
    findings: list[RentaInmuebleFinding] = field(default_factory=list)


def read_section[RecordT](
    section: str,
    path_values: Mapping[str, object],
    read: Callable[[int, dict[str, str]], RecordT],
    records: Records,
) -> dict[int, RecordT]:
    try:
        rows = rows_from_facts(section, profile_values_under(path_values, f"{section}."))
    except ProfileAnswerTypeError:
        records.findings.append(RentaInmuebleFinding(RentaInmuebleCause.RECORD_UNREADABLE, section))
        return {}
    read_rows: dict[int, RecordT] = {}
    for clave, row in sorted(rows.items()):
        try:
            read_rows[clave] = read(clave, row)
        except ProfileAnswerTypeError:
            records.findings.append(RentaInmuebleFinding(RentaInmuebleCause.RECORD_UNREADABLE, f"{section}:{clave}"))
    return read_rows


def read_records(path_values: Mapping[str, object]) -> Records:
    """Read every property and lease row of the profile, reporting unreadable rows and orphan leases."""
    records = Records()
    records.inmuebles = read_section(INMUEBLE_SECTION, path_values, inmueble_from_row, records)
    records.leases = read_section(ARRENDAMIENTO_SECTION, path_values, arrendamiento_from_row, records)
    for lease in records.leases.values():
        if lease.inmueble not in records.inmuebles:
            records.findings.append(
                RentaInmuebleFinding(RentaInmuebleCause.LEASE_NAMES_NO_PROPERTY, f"arrendamiento:{lease.clave}")
            )
    return records


def row_due_date(row: Transaction) -> date:
    """Return the date a linked row is imputed to: accrual, else operation, else booking."""
    return row.accrual_date or row.operation_date or transaction_filing_date(row)


def counts(row: Transaction) -> bool:
    return (
        row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.business_classification is not BusinessClassification.REVIEWED_EXCLUDED
        and (row.arrendamiento_ref is not None or row.inmueble_ref is not None)
    )


def row_key(reference: str) -> int | None:
    text = reference.strip()
    return int(text) if text.isdecimal() else None


@dataclass(slots=True)
class Links:
    """The ledger rows joined to the records they name, and the findings of the rows that cannot be joined."""

    income: dict[int, list[Transaction]] = field(default_factory=dict)
    """Rent rows by lease row key."""
    expenses: dict[int, list[Transaction]] = field(default_factory=dict)
    """Expense rows by property row key."""
    prior_improvements: dict[int, list[Transaction]] = field(default_factory=dict)
    """Rows of a capitalised concept dated before the ejercicio, by property row key."""
    findings: list[RentaInmuebleFinding] = field(default_factory=list)

    def refuse(self, cause: RentaInmuebleCause, row: Transaction) -> None:
        """Record that ``row`` cannot be placed, for ``cause``."""
        self.findings.append(RentaInmuebleFinding(cause, f"transaction:{row.transaction_id}"))


def link_income(row: Transaction, reference: str, records: Records, links: Links) -> None:
    if row.direction is not TransactionDirection.INCOMING:
        links.refuse(RentaInmuebleCause.EXPENSE_ROW_ON_LEASE, row)
        return
    key = row_key(reference)
    if key is None or key not in records.leases:
        links.refuse(RentaInmuebleCause.ROW_NAMES_NO_LEASE, row)
        return
    links.income.setdefault(key, []).append(row)


def link_expense(
    row: Transaction, reference: str, records: Records, links: Links, concepts: GastoCapitalInmobiliarioCatalogue
) -> None:
    if row.direction is not TransactionDirection.OUTGOING:
        links.refuse(RentaInmuebleCause.INCOME_ROW_ON_PROPERTY, row)
        return
    key = row_key(reference)
    if key is None or key not in records.inmuebles:
        links.refuse(RentaInmuebleCause.ROW_NAMES_NO_PROPERTY, row)
        return
    if row.gasto_capital_inmobiliario is None:
        links.refuse(RentaInmuebleCause.EXPENSE_ROW_WITHOUT_CONCEPT, row)
        return
    if row.gasto_capital_inmobiliario not in concepts.all_tokens:
        links.refuse(RentaInmuebleCause.CONCEPT_UNDECLARED, row)
        return
    links.expenses.setdefault(key, []).append(row)


def link_prior_improvement(
    row: Transaction, records: Records, links: Links, concepts: GastoCapitalInmobiliarioCatalogue
) -> None:
    """Keep an earlier ejercicio's improvement, which joins the amortisation base; other earlier rows are past."""
    key = None if row.inmueble_ref is None else row_key(row.inmueble_ref)
    token = row.gasto_capital_inmobiliario
    if key is None or key not in records.inmuebles or token is None or token not in concepts.all_tokens:
        return
    if row.direction is TransactionDirection.OUTGOING and concepts.concept_for(token).capitalised:
        links.prior_improvements.setdefault(key, []).append(row)


def link_rows(
    transactions: Iterable[Transaction],
    records: Records,
    ejercicio: Ejercicio,
    concepts: GastoCapitalInmobiliarioCatalogue,
) -> Links:
    """Join every ledger row that falls in the ejercicio to the lease or property it names."""
    links = Links()
    for row in sorted(transactions, key=lambda item: item.transaction_id):
        if not counts(row):
            continue
        if row_due_date(row) < ejercicio.first:
            link_prior_improvement(row, records, links, concepts)
            continue
        if not ejercicio.covers(row_due_date(row)):
            continue
        if is_non_eur_without_conversion(row):
            links.refuse(RentaInmuebleCause.CURRENCY_UNCONVERTED, row)
        elif row.arrendamiento_ref is not None:
            link_income(row, row.arrendamiento_ref, records, links)
        elif row.inmueble_ref is not None:
            link_expense(row, row.inmueble_ref, records, links, concepts)
    return links


def _tenant_key(identifier: str) -> str:
    return identifier.strip().upper()


def place_withholding(
    records: Iterable[RetencionSoportadaRecord], occupied: Mapping[int, Occupancy | None]
) -> tuple[dict[int, tuple[RetencionSoportadaRecord, ...]], list[RentaInmuebleFinding]]:
    """Place each urban-rent withholding on the let property whose lease names its payer as a tenant."""
    tenants: dict[str, set[int]] = {}
    for clave, occupied_as in occupied.items():
        for lease in () if occupied_as is None else occupied_as.leases:
            for tenant in lease.inquilinos:
                tenants.setdefault(_tenant_key(tenant.nif), set()).add(clave)
    placed: dict[int, list[RetencionSoportadaRecord]] = {}
    findings: list[RentaInmuebleFinding] = []
    for record in records:
        if record.income_class is not RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO:
            continue
        properties = tenants.get(_tenant_key(record.payer_tax_id), set())
        if len(properties) == 1:
            placed.setdefault(next(iter(properties)), []).append(record)
            continue
        cause = (
            RentaInmuebleCause.WITHHOLDING_PAYER_NO_TENANT
            if not properties
            else RentaInmuebleCause.WITHHOLDING_PAYER_SEVERAL_PROPERTIES
        )
        findings.append(RentaInmuebleFinding(cause, f"retencion:{record.payer_ref}"))
    return {clave: tuple(items) for clave, items in placed.items()}, findings


__all__ = ["Links", "Records", "link_rows", "place_withholding", "read_records", "row_due_date"]

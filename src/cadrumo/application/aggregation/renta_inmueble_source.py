"""Build one ``Inmueble`` occurrence of Modelo 100 per property the taxpayer held in the ejercicio.

The profile states each property and each lease as a row; the ledger states each
receipt of rent and each payment for a property, linked by the row key of its
lease or its property. An occurrence joins them: the property, its leases
active in the ejercicio, the rent rows of those leases and the expense rows of
the property. Nothing is read from a profile total.

Income is each rent row's taxable base where it states one, else its amount,
imputed to the date it fell due: its accrual date, else its operation date,
else its booking date. Expenses are summed per concept, the concept's box read
from the dated concept vocabulary, and prorated by the days let over the days
of the ejercicio. The taxpayer's ownership share is applied last, only where
the rows hold whole-property amounts, and each figure is rounded once to the
cent.

A let property's net yield, its art. 23.2 reduction and the withholding its
tenants suffered on it come from the chain in ``renta_inmueble_net``; a
withholding on urban rent is placed on the property whose lease names its payer
as a tenant.

A join that cannot be made or a fact that is not stated is a typed finding with
the command that settles it; it is never read as zero. An occurrence is ordered
by its property's row key, which the profile never reuses.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.money.rounding import round_to_cents
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
from ...domain.contribuyente.inmueble_record import (
    AdquisicionTitulo,
    ImportesMovimientos,
    InmuebleNaturaleza,
    InmuebleRecord,
    InmuebleSituacion,
    TitularidadRegimen,
    TitularRole,
)
from ...domain.renta.retencion_soportada import RetencionSoportadaRecord
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from .currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from .renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFinding, RentaInmuebleFindingKind
from .renta_inmueble_net import RentaInmuebleNet, RentaInmuebleNetInputs, RentaInmuebleTerms, renta_inmueble_net

_HUNDRED: Final = Decimal(100)
_ZERO: Final = Decimal(0)


class RentaInmuebleRowField(StrEnum):
    """What one column of a property's occurrence states."""

    PORCENTAJE_PROPIEDAD = "porcentaje_propiedad"
    SITUACION = "situacion"
    REFERENCIA_CATASTRAL = "referencia_catastral"
    URBANA = "urbana"
    RUSTICA = "rustica"
    DIRECCION = "direccion"
    ARRENDADO = "arrendado"
    INQUILINO_1_NIF = "inquilino_1_nif"
    INQUILINO_1_NIF_EXTRANJERO = "inquilino_1_nif_extranjero"
    INQUILINO_2_NIF = "inquilino_2_nif"
    INQUILINO_2_NIF_EXTRANJERO = "inquilino_2_nif_extranjero"
    INQUILINO_3_NIF = "inquilino_3_nif"
    INQUILINO_3_NIF_EXTRANJERO = "inquilino_3_nif_extranjero"
    FECHA_CONTRATO = "fecha_contrato"
    DIAS_ARRENDADO = "dias_arrendado"
    DIAS_ARRENDADO_AMORTIZACION = "dias_arrendado_amortizacion"
    INGRESOS_INTEGROS = "ingresos_integros"
    ADQUISICION_ONEROSA = "adquisicion_onerosa"
    ADQUISICION_LUCRATIVA = "adquisicion_lucrativa"
    FECHA_ADQUISICION = "fecha_adquisicion"
    FECHA_TRANSMISION = "fecha_transmision"
    VALOR_CATASTRAL = "valor_catastral"
    VALOR_CATASTRAL_CONSTRUCCION = "valor_catastral_construccion"
    PORCENTAJE_CONSTRUCCION = "porcentaje_construccion"
    IMPORTE_ADQUISICION = "importe_adquisicion"
    GASTOS_ADQUISICION = "gastos_adquisicion"
    MEJORAS_ANTERIORES = "mejoras_anteriores"
    MEJORAS_EJERCICIO = "mejoras_ejercicio"
    BASE_AMORTIZACION = "base_amortizacion"
    AMORTIZACION = "amortizacion"
    GASTOS_PENDIENTES_ANTERIORES = "gastos_pendientes_anteriores"
    GASTOS_PENDIENTES_APLICADOS = "gastos_pendientes_aplicados"
    INTERESES_REPARACION_APLICADOS = "intereses_reparacion_aplicados"
    INTERESES_REPARACION_PENDIENTES = "intereses_reparacion_pendientes"
    INTERESES_REPARACION_PENDIENTES_FUTUROS = "intereses_reparacion_pendientes_futuros"
    """The anexo C.1 restatement of the ejercicio's own excess carried forward: the row's 0108 again."""
    RENDIMIENTO_NETO = "rendimiento_neto"
    REDUCCION_APLICABLE = "reduccion_aplicable"
    REDUCCION = "reduccion"
    RETENCIONES = "retenciones"
    RENDIMIENTO_NETO_REDUCIDO = "rendimiento_neto_reducido"


type RentaInmuebleColumnValue = str | Decimal | int | bool


@dataclass(frozen=True, slots=True)
class _Ejercicio:
    first: date
    last: date

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    def covers(self, day: date) -> bool:
        return self.first <= day <= self.last


@dataclass(frozen=True, slots=True)
class RentaInmuebleOccurrence:
    """One property's ``Inmueble`` occurrence: what it states and what stops or limits it."""

    index: int
    """The 1-based position of the occurrence on the return."""
    inmueble: InmuebleRecord
    leases: tuple[ArrendamientoRecord, ...]
    """The property's leases active in the ejercicio, by start date then row key."""
    ejercicio_last: date
    dias_arrendado: int
    ingresos: Decimal | None
    """The taxpayer's part of the rent of the ejercicio, or ``None`` when the property was not let."""
    gastos: Mapping[str, Decimal]
    """The taxpayer's part of each prorated expense, keyed by its concept token."""
    transaction_ids: tuple[str, ...]
    findings: tuple[RentaInmuebleFinding, ...]
    net: RentaInmuebleNet | None = None
    """The chain from the gross income to the reduced net yield, or ``None`` when the property was not let."""
    withholding: tuple[RetencionSoportadaRecord, ...] = ()
    """The suffered-withholding records placed on this property."""

    @property
    def source_identity(self) -> str:
        """Identify the property this occurrence comes from, stable across ejercicios."""
        return _source_identity(self.inmueble.clave)

    def gasto(self, concept: str) -> Decimal | None:
        """Return the taxpayer's part of one expense concept; ``None`` when no row states it."""
        return self.gastos.get(concept)

    def column(self, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
        """Return this occurrence's value for one column; ``None`` leaves the box off the row."""
        if row_field in _LEASE_COLUMNS:
            return self._lease_column(row_field)
        if row_field in _AMOUNT_COLUMNS:
            return self._amount_column(row_field)
        if row_field in _NET_COLUMNS:
            return None if self.net is None else _NET_COLUMNS[row_field](self.net)
        return self._identification_column(row_field)

    def _identification_column(self, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
        record = self.inmueble
        match row_field:
            case RentaInmuebleRowField.PORCENTAJE_PROPIEDAD:
                return None if record.titularidad is None else record.titularidad.porcentaje_propiedad
            case RentaInmuebleRowField.SITUACION:
                return record.situacion.value
            case RentaInmuebleRowField.REFERENCIA_CATASTRAL:
                return record.referencia_catastral
            case RentaInmuebleRowField.URBANA:
                return True if record.naturaleza is InmuebleNaturaleza.URBANA else None
            case RentaInmuebleRowField.RUSTICA:
                return True if record.naturaleza is InmuebleNaturaleza.RUSTICA else None
            case RentaInmuebleRowField.DIRECCION:
                return record.direccion
            case _:
                return self._acquisition_column(row_field)

    def _acquisition_column(self, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
        record = self.inmueble
        match row_field:
            case RentaInmuebleRowField.ADQUISICION_ONEROSA:
                return True if record.adquisicion_titulo is AdquisicionTitulo.ONEROSA else None
            case RentaInmuebleRowField.ADQUISICION_LUCRATIVA:
                return True if record.adquisicion_titulo is AdquisicionTitulo.LUCRATIVA else None
            case RentaInmuebleRowField.FECHA_ADQUISICION:
                return None if record.fecha_adquisicion is None else record.fecha_adquisicion.isoformat()
            case RentaInmuebleRowField.FECHA_TRANSMISION:
                transmitted = record.fecha_transmision
                return None if transmitted is None or transmitted > self.ejercicio_last else transmitted.isoformat()
            case _:
                return None

    def _amount_column(self, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
        if row_field is RentaInmuebleRowField.INGRESOS_INTEGROS:
            return self.ingresos
        return self.dias_arrendado if self.leases else None

    def _lease_column(self, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
        if not self.leases:
            return None
        lease = self.leases[0]
        match row_field:
            case RentaInmuebleRowField.ARRENDADO:
                return True
            case RentaInmuebleRowField.FECHA_CONTRATO:
                return lease.fecha_contrato.isoformat()
            case _:
                return _tenant_column(lease, row_field)


_TENANT_SLOTS: Final[dict[RentaInmuebleRowField, tuple[int, bool]]] = {
    RentaInmuebleRowField.INQUILINO_1_NIF: (0, False),
    RentaInmuebleRowField.INQUILINO_1_NIF_EXTRANJERO: (0, True),
    RentaInmuebleRowField.INQUILINO_2_NIF: (1, False),
    RentaInmuebleRowField.INQUILINO_2_NIF_EXTRANJERO: (1, True),
    RentaInmuebleRowField.INQUILINO_3_NIF: (2, False),
    RentaInmuebleRowField.INQUILINO_3_NIF_EXTRANJERO: (2, True),
}
"""Each numbered tenant column: the tenant's position on the lease and whether it states the foreign-NIF mark."""
NUMBERED_TENANTS: Final = len({slot for slot, _mark in _TENANT_SLOTS.values()})
"""The tenants the design numbers on one ``Inmueble``; any further tenant has no box."""
_LEASE_COLUMNS: Final = frozenset(
    {RentaInmuebleRowField.ARRENDADO, RentaInmuebleRowField.FECHA_CONTRATO, *_TENANT_SLOTS}
)
_AMOUNT_COLUMNS: Final = frozenset(
    {
        RentaInmuebleRowField.INGRESOS_INTEGROS,
        RentaInmuebleRowField.DIAS_ARRENDADO,
        RentaInmuebleRowField.DIAS_ARRENDADO_AMORTIZACION,
    }
)
_NET_COLUMNS: Final[dict[RentaInmuebleRowField, Callable[[RentaInmuebleNet], RentaInmuebleColumnValue | None]]] = {
    RentaInmuebleRowField.VALOR_CATASTRAL: lambda net: net.valor_catastral,
    RentaInmuebleRowField.VALOR_CATASTRAL_CONSTRUCCION: lambda net: net.valor_catastral_construccion,
    RentaInmuebleRowField.PORCENTAJE_CONSTRUCCION: lambda net: net.porcentaje_construccion,
    RentaInmuebleRowField.IMPORTE_ADQUISICION: lambda net: net.importe_adquisicion,
    RentaInmuebleRowField.GASTOS_ADQUISICION: lambda net: net.gastos_adquisicion,
    RentaInmuebleRowField.MEJORAS_ANTERIORES: lambda net: net.mejoras_anteriores,
    RentaInmuebleRowField.MEJORAS_EJERCICIO: lambda net: net.mejoras_ejercicio,
    RentaInmuebleRowField.BASE_AMORTIZACION: lambda net: net.base_amortizacion,
    RentaInmuebleRowField.AMORTIZACION: lambda net: net.amortizacion,
    RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES: lambda net: net.gastos_pendientes_anteriores,
    RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS: lambda net: net.gastos_pendientes_aplicados,
    RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS: lambda net: net.intereses_reparacion_aplicados,
    RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES: lambda net: net.intereses_reparacion_pendientes,
    RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES_FUTUROS: lambda net: net.intereses_reparacion_pendientes,
    RentaInmuebleRowField.RENDIMIENTO_NETO: lambda net: net.rendimiento_neto,
    RentaInmuebleRowField.REDUCCION_APLICABLE: lambda net: net.reduccion_aplicable,
    RentaInmuebleRowField.REDUCCION: lambda net: net.reduccion,
    RentaInmuebleRowField.RETENCIONES: lambda net: net.retenciones,
    RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO: lambda net: net.rendimiento_neto_reducido,
}
"""Each column the net chain states, read from the occurrence's chain."""
SUMMABLE_COLUMNS: Final = frozenset(
    {
        RentaInmuebleRowField.INGRESOS_INTEGROS,
        RentaInmuebleRowField.AMORTIZACION,
        RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS,
        RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS,
        RentaInmuebleRowField.INTERESES_REPARACION_PENDIENTES,
        RentaInmuebleRowField.RENDIMIENTO_NETO,
        RentaInmuebleRowField.REDUCCION,
        RentaInmuebleRowField.RETENCIONES,
        RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO,
    }
)
"""The amount columns a results box may total over the let properties."""
GASTO_COLUMN_PREFIX: Final = "gasto_"
"""The prefix of an expense column, followed by the concept token whose rows it states."""


def _tenant_column(lease: ArrendamientoRecord, row_field: RentaInmuebleRowField) -> RentaInmuebleColumnValue | None:
    slot, mark = _TENANT_SLOTS[row_field]
    if slot >= len(lease.inquilinos):
        return None
    tenant = lease.inquilinos[slot]
    if mark:
        return True if tenant.extranjero else None
    return tenant.nif


@dataclass(frozen=True, slots=True)
class RentaInmuebleOccurrences:
    """Every occurrence of the ejercicio and every finding, including those no single property owns."""

    occurrences: tuple[RentaInmuebleOccurrence, ...]
    findings: tuple[RentaInmuebleFinding, ...]

    @property
    def refused(self) -> bool:
        """Report whether any finding refuses the occurrences, so no row may be emitted."""
        return any(finding.kind is RentaInmuebleFindingKind.REFUSAL for finding in self.findings)


@dataclass(slots=True)
class _Records:
    inmuebles: dict[int, InmuebleRecord] = field(default_factory=dict)
    leases: dict[int, ArrendamientoRecord] = field(default_factory=dict)
    findings: list[RentaInmuebleFinding] = field(default_factory=list)


def _read_section[RecordT](
    section: str,
    path_values: Mapping[str, object],
    read: Callable[[int, dict[str, str]], RecordT],
    records: _Records,
) -> dict[int, RecordT]:
    try:
        rows = rows_from_facts(section, path_values)
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


def _read_records(path_values: Mapping[str, object]) -> _Records:
    records = _Records()
    records.inmuebles = _read_section(INMUEBLE_SECTION, path_values, inmueble_from_row, records)
    records.leases = _read_section(ARRENDAMIENTO_SECTION, path_values, arrendamiento_from_row, records)
    for lease in records.leases.values():
        if lease.inmueble not in records.inmuebles:
            records.findings.append(
                RentaInmuebleFinding(RentaInmuebleCause.LEASE_NAMES_NO_PROPERTY, f"arrendamiento:{lease.clave}")
            )
    return records


def row_due_date(row: Transaction) -> date:
    """Return the date a linked row is imputed to: accrual, else operation, else booking."""
    return row.accrual_date or row.operation_date or transaction_filing_date(row)


def _counts(row: Transaction) -> bool:
    return (
        row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.business_classification is not BusinessClassification.REVIEWED_EXCLUDED
        and (row.arrendamiento_ref is not None or row.inmueble_ref is not None)
    )


def _row_key(reference: str) -> int | None:
    text = reference.strip()
    return int(text) if text.isdecimal() else None


@dataclass(slots=True)
class _Links:
    income: dict[int, list[Transaction]] = field(default_factory=dict)
    """Rent rows by lease row key."""
    expenses: dict[int, list[Transaction]] = field(default_factory=dict)
    """Expense rows by property row key."""
    prior_improvements: dict[int, list[Transaction]] = field(default_factory=dict)
    """Rows of a capitalised concept dated before the ejercicio, by property row key."""
    findings: list[RentaInmuebleFinding] = field(default_factory=list)

    def refuse(self, cause: RentaInmuebleCause, row: Transaction) -> None:
        self.findings.append(RentaInmuebleFinding(cause, f"transaction:{row.transaction_id}"))


def _link_income(row: Transaction, reference: str, records: _Records, links: _Links) -> None:
    if row.direction is not TransactionDirection.INCOMING:
        links.refuse(RentaInmuebleCause.EXPENSE_ROW_ON_LEASE, row)
        return
    key = _row_key(reference)
    if key is None or key not in records.leases:
        links.refuse(RentaInmuebleCause.ROW_NAMES_NO_LEASE, row)
        return
    links.income.setdefault(key, []).append(row)


def _link_expense(
    row: Transaction, reference: str, records: _Records, links: _Links, concepts: GastoCapitalInmobiliarioCatalogue
) -> None:
    if row.direction is not TransactionDirection.OUTGOING:
        links.refuse(RentaInmuebleCause.INCOME_ROW_ON_PROPERTY, row)
        return
    key = _row_key(reference)
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


def _link_prior_improvement(
    row: Transaction, records: _Records, links: _Links, concepts: GastoCapitalInmobiliarioCatalogue
) -> None:
    """Keep an earlier ejercicio's improvement, which joins the amortisation base; other earlier rows are past."""
    key = None if row.inmueble_ref is None else _row_key(row.inmueble_ref)
    token = row.gasto_capital_inmobiliario
    if key is None or key not in records.inmuebles or token is None or token not in concepts.all_tokens:
        return
    if row.direction is TransactionDirection.OUTGOING and concepts.concept_for(token).capitalised:
        links.prior_improvements.setdefault(key, []).append(row)


def _link_rows(
    transactions: Iterable[Transaction],
    records: _Records,
    ejercicio: _Ejercicio,
    concepts: GastoCapitalInmobiliarioCatalogue,
) -> _Links:
    links = _Links()
    for row in sorted(transactions, key=lambda item: item.transaction_id):
        if not _counts(row):
            continue
        if row_due_date(row) < ejercicio.first:
            _link_prior_improvement(row, records, links, concepts)
            continue
        if not ejercicio.covers(row_due_date(row)):
            continue
        if is_non_eur_without_conversion(row):
            links.refuse(RentaInmuebleCause.CURRENCY_UNCONVERTED, row)
        elif row.arrendamiento_ref is not None:
            _link_income(row, row.arrendamiento_ref, records, links)
        elif row.inmueble_ref is not None:
            _link_expense(row, row.inmueble_ref, records, links, concepts)
    return links


def _held_interval(record: InmuebleRecord, ejercicio: _Ejercicio) -> tuple[date, date] | None:
    if record.fecha_adquisicion is None:
        return None
    start = max(ejercicio.first, record.fecha_adquisicion)
    end = ejercicio.last if record.fecha_transmision is None else min(ejercicio.last, record.fecha_transmision)
    return (start, end) if start <= end else None


def _lease_days(lease: ArrendamientoRecord, held: tuple[date, date]) -> set[date]:
    start = max(held[0], lease.fecha_inicio)
    end = held[1] if lease.fecha_fin is None else min(held[1], lease.fecha_fin)
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)} if start <= end else set()


@dataclass(frozen=True, slots=True)
class _Occupancy:
    leases: tuple[ArrendamientoRecord, ...]
    days_held: int
    days_let: int
    concurrent: bool
    lease_days: Mapping[int, int]
    """The days each active lease covers, by its row key."""


def _occupancy(leases: Iterable[ArrendamientoRecord], held: tuple[date, date]) -> _Occupancy:
    spans = sorted(
        ((lease, _lease_days(lease, held)) for lease in leases),
        key=lambda item: (item[0].fecha_inicio, item[0].clave),
    )
    active = tuple((lease, days) for lease, days in spans if days)
    let_days = {day for _lease, days in active for day in days}
    return _Occupancy(
        leases=tuple(lease for lease, _days in active),
        days_held=(held[1] - held[0]).days + 1,
        days_let=len(let_days),
        concurrent=sum(len(days) for _lease, days in active) > len(let_days),
        lease_days={lease.clave: len(days) for lease, days in active},
    )


def _share(record: InmuebleRecord) -> Decimal:
    titularidad = record.titularidad
    percentage = None if titularidad is None else titularidad.porcentaje_propiedad
    if percentage is None or record.importes_movimientos is not ImportesMovimientos.INMUEBLE_COMPLETO:
        return Decimal(1)
    return percentage / _HUNDRED


def _row_amount(row: Transaction) -> Decimal:
    base = effective_eur_taxable_base(row)
    return effective_eur_amount(row) if base is None else base


def _property_findings(record: InmuebleRecord, occupancy: _Occupancy | None) -> list[RentaInmuebleCause]:
    causes: list[RentaInmuebleCause] = []
    titularidad = record.titularidad
    if titularidad is None:
        causes.append(RentaInmuebleCause.TITULARIDAD_UNSTATED)
    else:
        if titularidad.regimen is not TitularidadRegimen.PLENO_DOMINIO:
            causes.append(RentaInmuebleCause.REGIME_NOT_PLENO_DOMINIO)
        if titularidad.titular is not TitularRole.PRIMER_DECLARANTE:
            causes.append(RentaInmuebleCause.TITULAR_NOT_DECLARANT)
    if record.naturaleza is None:
        causes.append(RentaInmuebleCause.NATURALEZA_UNSTATED)
    if record.inmueble_principal is not None:
        causes.append(RentaInmuebleCause.ACCESSORY_PROPERTY)
    let = occupancy is not None and bool(occupancy.leases)
    if let and record.situacion is InmuebleSituacion.EXTRANJERO:
        causes.append(RentaInmuebleCause.PROPERTY_ABROAD_LET)
    return causes


def _occupancy_findings(occupancy: _Occupancy, ejercicio: _Ejercicio) -> list[RentaInmuebleCause]:
    causes: list[RentaInmuebleCause] = []
    if occupancy.days_held < ejercicio.days:
        causes.append(RentaInmuebleCause.HELD_PART_OF_EJERCICIO)
    if occupancy.days_let < occupancy.days_held:
        causes.append(RentaInmuebleCause.DAYS_NOT_LET)
    if occupancy.concurrent:
        causes.append(RentaInmuebleCause.CONCURRENT_LEASES)
    if len(occupancy.leases) > 1:
        causes.append(RentaInmuebleCause.SEVERAL_LEASES)
    if occupancy.leases:
        causes.append(RentaInmuebleCause.BOXES_NOT_OFFERED)
    return causes


def _lease_findings(lease: ArrendamientoRecord, income: list[Transaction]) -> list[RentaInmuebleCause]:
    causes: list[RentaInmuebleCause] = []
    if not income:
        causes.append(RentaInmuebleCause.LEASE_WITHOUT_INCOME)
    if lease.arrendatario_pariente_art24 is None:
        causes.append(RentaInmuebleCause.RELATIVE_FACT_UNSTATED)
    elif lease.arrendatario_pariente_art24:
        causes.append(RentaInmuebleCause.RELATIVE_TENANT)
    if len(lease.inquilinos) > NUMBERED_TENANTS:
        causes.append(RentaInmuebleCause.TENANTS_BEYOND_NUMBERED)
    return causes


def _income_outside_lease(lease: ArrendamientoRecord, rows: Iterable[Transaction]) -> list[RentaInmuebleFinding]:
    return [
        RentaInmuebleFinding(RentaInmuebleCause.INCOME_OUTSIDE_LEASE, f"transaction:{row.transaction_id}")
        for row in rows
        if not _within_lease(lease, row_due_date(row))
    ]


def _within_lease(lease: ArrendamientoRecord, day: date) -> bool:
    return lease.fecha_inicio <= day and (lease.fecha_fin is None or day <= lease.fecha_fin)


@dataclass(frozen=True, slots=True)
class _OccurrenceInputs:
    record: InmuebleRecord
    occupancy: _Occupancy | None
    leases: tuple[ArrendamientoRecord, ...]
    """Every lease of the property, active in the ejercicio or not."""
    income: Mapping[int, list[Transaction]]
    expenses: Mapping[str, list[Transaction]]
    """The property's deductible expense rows, by concept token."""
    improvements: tuple[Transaction, ...]
    """The property's rows of a capitalised concept dated in the ejercicio."""
    prior_improvements: tuple[Transaction, ...]
    """The property's rows of a capitalised concept dated before the ejercicio."""


def _occurrence_findings(inputs: _OccurrenceInputs, ejercicio: _Ejercicio) -> list[RentaInmuebleFinding]:
    record = inputs.record
    subject = f"inmueble:{record.clave}"
    causes = _property_findings(record, inputs.occupancy)
    if inputs.occupancy is not None:
        causes.extend(_occupancy_findings(inputs.occupancy, ejercicio))
    if inputs.improvements:
        causes.append(RentaInmuebleCause.IMPROVEMENT_IN_EJERCICIO)
    findings = [RentaInmuebleFinding(cause, subject) for cause in causes]
    active = frozenset(lease.clave for lease in (() if inputs.occupancy is None else inputs.occupancy.leases))
    for lease in inputs.leases:
        rows = inputs.income.get(lease.clave, [])
        findings.extend(_income_outside_lease(lease, rows))
        if lease.clave in active:
            lease_subject = f"arrendamiento:{lease.clave}"
            findings.extend(RentaInmuebleFinding(cause, lease_subject) for cause in _lease_findings(lease, rows))
    return findings


def _split_expenses(
    rows: Iterable[Transaction], concepts: GastoCapitalInmobiliarioCatalogue
) -> tuple[dict[str, list[Transaction]], tuple[Transaction, ...]]:
    expenses: dict[str, list[Transaction]] = {}
    improvements: list[Transaction] = []
    for row in rows:
        concept = concepts.concept_for(row.gasto_capital_inmobiliario)
        if concept.capitalised:
            improvements.append(row)
        else:
            expenses.setdefault(str(concept.token), []).append(row)
    return expenses, tuple(improvements)


def _total(rows: Iterable[Transaction]) -> Decimal:
    return sum((_row_amount(row) for row in rows), Decimal(0))


def _figures(
    inputs: _OccurrenceInputs, ejercicio: _Ejercicio
) -> tuple[Decimal | None, dict[str, Decimal], tuple[str, ...]]:
    """Return the taxpayer's part of the rent and of each prorated expense, and the rows read."""
    occupancy = inputs.occupancy
    if occupancy is None or not occupancy.leases:
        return None, {}, ()
    share = _share(inputs.record)
    income_rows = [row for lease in occupancy.leases for row in inputs.income.get(lease.clave, [])]
    fraction = Decimal(occupancy.days_let) / Decimal(ejercicio.days)
    gastos = {
        concept: round_to_cents(_total(rows) * fraction * share) for concept, rows in sorted(inputs.expenses.items())
    }
    expense_rows = [row for rows in inputs.expenses.values() for row in rows]
    capitalised = (*inputs.improvements, *inputs.prior_improvements)
    read = sorted(row.transaction_id for row in (*income_rows, *expense_rows, *capitalised))
    return round_to_cents(_total(income_rows) * share), gastos, tuple(read)


def _occurrence_inputs(
    record: InmuebleRecord,
    records: _Records,
    links: _Links,
    ejercicio: _Ejercicio,
    concepts: GastoCapitalInmobiliarioCatalogue,
) -> _OccurrenceInputs:
    leases = tuple(lease for _clave, lease in sorted(records.leases.items()) if lease.inmueble == record.clave)
    held = _held_interval(record, ejercicio)
    expenses, improvements = _split_expenses(links.expenses.get(record.clave, []), concepts)
    return _OccurrenceInputs(
        record=record,
        occupancy=None if held is None else _occupancy(leases, held),
        leases=leases,
        income={lease.clave: links.income.get(lease.clave, []) for lease in leases},
        expenses=expenses,
        improvements=improvements,
        prior_improvements=tuple(links.prior_improvements.get(record.clave, [])),
    )


def _is_held(record: InmuebleRecord, ejercicio: _Ejercicio) -> bool:
    """Report whether the property may have been held on a day of the ejercicio.

    A property with no acquisition date is kept, so its refusal is reported
    rather than the property being left off the return.
    """
    return record.fecha_adquisicion is None or _held_interval(record, ejercicio) is not None


def _lease_figures(inputs: _OccurrenceInputs) -> dict[int, Decimal]:
    """Return the taxpayer's part of each active lease's rent."""
    if inputs.occupancy is None:
        return {}
    share = _share(inputs.record)
    return {
        lease.clave: round_to_cents(_total(inputs.income.get(lease.clave, [])) * share)
        for lease in inputs.occupancy.leases
    }


def _net(
    inputs: _OccurrenceInputs,
    ejercicio: _Ejercicio,
    figures: tuple[Decimal | None, dict[str, Decimal]],
    withholding: tuple[RetencionSoportadaRecord, ...],
    rules: tuple[RentaInmuebleTerms, GastoCapitalInmobiliarioCatalogue],
    pendiente: Decimal | None,
    prior_return_held: bool,
) -> RentaInmuebleNet | None:
    occupancy, (ingresos, gastos) = inputs.occupancy, figures
    if occupancy is None or not occupancy.leases or ingresos is None:
        return None
    share = _share(inputs.record)
    terms, concepts = rules
    return renta_inmueble_net(
        RentaInmuebleNetInputs(
            record=inputs.record,
            leases=occupancy.leases,
            ejercicio_first=ejercicio.first,
            ejercicio_last=ejercicio.last,
            days_let=occupancy.days_let,
            lease_days=occupancy.lease_days,
            ingresos=ingresos,
            lease_ingresos=_lease_figures(inputs),
            gastos=gastos,
            improvements_before=_total(inputs.prior_improvements) * share,
            improvements_in=_total(inputs.improvements) * share,
            withholding=withholding,
            pendiente=pendiente,
            prior_return_held=prior_return_held,
        ),
        terms=terms,
        concepts=concepts,
    )


def _pendiente(record: InmuebleRecord, ejercicio: _Ejercicio, stated: Mapping[str, Decimal]) -> Decimal | None:
    """Return what earlier ejercicios left pending on the property, or ``None`` while it is unknown.

    The filer's statement for the property decides it. Without one, a property
    acquired inside the ejercicio has no earlier year to leave anything pending;
    for any other, no earlier return is read here, so the net chain stops short
    of the net yield.
    """
    statement = stated.get(_source_identity(record.clave))
    if statement is not None:
        return statement
    acquired = record.fecha_adquisicion
    return _ZERO if acquired is not None and acquired >= ejercicio.first else None


def _source_identity(clave: int) -> str:
    return f"inmueble:{clave}"


def _tenant_key(identifier: str) -> str:
    return identifier.strip().upper()


def _place_withholding(
    records: Iterable[RetencionSoportadaRecord], occupied: Mapping[int, _Occupancy | None]
) -> tuple[dict[int, tuple[RetencionSoportadaRecord, ...]], list[RentaInmuebleFinding]]:
    """Place each urban-rent withholding on the let property whose lease names its payer as a tenant."""
    tenants: dict[str, set[int]] = {}
    for clave, occupancy in occupied.items():
        for lease in () if occupancy is None else occupancy.leases:
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


def renta_inmueble_occurrences(
    *,
    path_values: Mapping[str, object],
    transactions: Iterable[Transaction],
    ejercicio: int,
    concepts: GastoCapitalInmobiliarioCatalogue,
    terms: RentaInmuebleTerms,
    withholding: Iterable[RetencionSoportadaRecord] = (),
    pending_stated: Mapping[str, Decimal] | None = None,
    prior_return_held: bool = False,
) -> RentaInmuebleOccurrences:
    """Build one occurrence per property held on at least one day of ``ejercicio``, in row-key order.

    Args:
        path_values: The profile's stated facts by path.
        transactions: Every ledger row of the profile; rows dated outside the ejercicio are ignored,
            except an earlier improvement, which joins the amortisation base.
        ejercicio: The calendar year the return declares.
        concepts: The rental-expense concept vocabulary in force for the ejercicio.
        terms: The dated registry data of the net chain.
        withholding: The ejercicio's suffered-withholding records, of every income class.
        pending_stated: The filer's statement of what earlier ejercicios left pending, by the
            source identity of the property it speaks of; zero where nothing is pending.
        prior_return_held: Whether the profile holds the return of the previous ejercicio,
            whose pending amounts no path matches to a property.

    Returns:
        The occurrences and every finding, those of a property and those no property owns.
    """
    period = _Ejercicio(first=date(ejercicio, 1, 1), last=date(ejercicio, 12, 31))
    records = _read_records(path_values)
    links = _link_rows(transactions, records, period, concepts)
    findings: list[RentaInmuebleFinding] = [*records.findings, *links.findings]
    held = {
        clave: _occurrence_inputs(record, records, links, period, concepts)
        for clave, record in sorted(records.inmuebles.items())
        if _is_held(record, period)
    }
    placed, unplaced = _place_withholding(withholding, {clave: inputs.occupancy for clave, inputs in held.items()})
    findings.extend(unplaced)
    occurrences: list[RentaInmuebleOccurrence] = []
    for clave, inputs in held.items():
        own = _occurrence_findings(inputs, period)
        ingresos, gastos, read = _figures(inputs, period)
        pendiente = _pendiente(inputs.record, period, pending_stated or {})
        net = _net(
            inputs, period, (ingresos, gastos), placed.get(clave, ()), (terms, concepts), pendiente, prior_return_held
        )
        if net is not None:
            own.extend(RentaInmuebleFinding(cause, _source_identity(clave)) for cause in net.causes)
        occurrences.append(
            RentaInmuebleOccurrence(
                index=len(occurrences) + 1,
                inmueble=inputs.record,
                leases=() if inputs.occupancy is None else inputs.occupancy.leases,
                ejercicio_last=period.last,
                dias_arrendado=0 if inputs.occupancy is None else inputs.occupancy.days_let,
                ingresos=ingresos,
                gastos=gastos,
                transaction_ids=read,
                findings=tuple(own),
                net=net,
                withholding=placed.get(clave, ()),
            )
        )
        findings.extend(own)
    return RentaInmuebleOccurrences(occurrences=tuple(occurrences), findings=tuple(findings))


__all__ = [
    "GASTO_COLUMN_PREFIX",
    "NUMBERED_TENANTS",
    "SUMMABLE_COLUMNS",
    "RentaInmuebleColumnValue",
    "RentaInmuebleOccurrence",
    "RentaInmuebleOccurrences",
    "RentaInmuebleRowField",
    "renta_inmueble_occurrences",
    "row_due_date",
]

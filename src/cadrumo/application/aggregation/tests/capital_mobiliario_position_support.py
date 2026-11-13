"""Savings positions, their linked ledger rows and payer records, resolved through the real position resolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.capital_mobiliario_position_bindings import (
    capital_mobiliario_position_bindings,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.inmueble_facts import facts_for_row
from ....domain.contribuyente.posicion_facts import POSICION_SECTION
from ....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.tests.savings_link_rows import savings_row
from ....domain.user_profile.values import UserProfileFact
from ..capital_mobiliario_position_source import CapitalMobiliarioPositionSourceResolver
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
    m100_revision,
)

YEAR = filing_year_envelope().horizon
DEPOSIT_PAYER = "B00000001"
BROKER_PAYER = "B00000002"
DEPOSIT = "0"
SHARES = "1"
INTEREST = "0027"
DIVIDENDS = "0029"
EXPENSES = "0037"


@dataclass(frozen=True, slots=True)
class SavingsPosition:
    tipo: str
    payer: str
    name: str
    share: str = "100"
    country: str = "ES"
    since: date = date(YEAR - 2, 1, 1)
    until: date | None = None


DEPOSIT_POSITION = SavingsPosition("deposito", DEPOSIT_PAYER, "Banco Sintetico")
SHARES_POSITION = SavingsPosition("valores_negociables", BROKER_PAYER, "Broker Sintetico")


@dataclass(slots=True)
class _Records:
    records: tuple[RetencionSoportadaRecord, ...] = ()

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        return tuple(record for record in self.records if record.ejercicio == ejercicio)


@dataclass(slots=True)
class _Absences:
    attestations: list[RetencionSoportadaAbsence] = field(default_factory=list)

    def load_attestations(self, ejercicio: int) -> tuple[RetencionSoportadaAbsence, ...]:
        return tuple(item for item in self.attestations if item.ejercicio == ejercicio)


def payer_record(payer: str, *, integro: str, retencion: str, especie: str = "0.00") -> RetencionSoportadaRecord:
    return RetencionSoportadaRecord(
        ejercicio=YEAR,
        payer_tax_id=payer,
        payer_legal_name="Pagador Sintetico SA",
        payer_ref=payer[-1] * 64,
        income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
        importe_integro_dinerario=Decimal(integro),
        valoracion_especie=Decimal(especie),
        retencion=Decimal(retencion),
        ingreso_a_cuenta=Decimal("0.00"),
        ingreso_a_cuenta_repercutido=Decimal("0.00"),
        origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
        evidence_fingerprint="c" * 64,
        captured_at=datetime(YEAR + 1, 4, 2, 9, 0, tzinfo=UTC),
    )


def _absence() -> RetencionSoportadaAbsence:
    return RetencionSoportadaAbsence(
        ejercicio=YEAR,
        income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
        note="La cuenta no practico retencion",
        attested_at=datetime(YEAR + 1, 4, 2, 9, 0, tzinfo=UTC),
    )


def linked_row(
    row_id: str,
    position: str,
    concept: str,
    amount: str,
    *,
    on: date = date(YEAR, 6, 30),
    direction: TransactionDirection = TransactionDirection.INCOMING,
) -> Transaction:
    base = savings_row(provider_id=row_id)
    raw = base.raw.model_copy(update={"amount": Decimal(amount), "booked_date": on})
    return savings_row(
        provider_id=row_id,
        raw=raw,
        direction=direction,
        posicion_ref=position,
        concepto_capital_mobiliario=concept,
    )


def position_facts(positions: dict[str, SavingsPosition]) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for clave, position in positions.items():
        values = {
            "tipo": position.tipo,
            "pagador_nif": position.payer,
            "pagador_nombre": position.name,
            "pais_origen": position.country,
            "porcentaje_titularidad": position.share,
            "fecha_inicio": position.since.isoformat(),
        }
        if position.until is not None:
            values["fecha_fin"] = position.until.isoformat()
        facts.extend(
            UserProfileFact(path=path, value=value)
            for path, value in facts_for_row(POSICION_SECTION, int(clave), values).items()
        )
    return tuple(facts)


def resolve_savings(
    rows: tuple[Transaction, ...],
    *,
    positions: dict[str, SavingsPosition] | None = None,
    records: tuple[RetencionSoportadaRecord, ...] = (),
    attested: bool = False,
    year: int = YEAR,
) -> CalculationSourceResolution:
    positions = {DEPOSIT: DEPOSIT_POSITION, SHARES: SHARES_POSITION} if positions is None else positions
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(rows))
    ports = RetencionSoportadaPorts(repository=_Records(records), absences=_Absences([_absence()] if attested else []))
    return CapitalMobiliarioPositionSourceResolver(
        transaction_repository=repository, retencion_soportada_ports=ports
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=m100_revision(year),
            profile=cash_criterion_profile(year, extra_facts=position_facts(positions)),
        )
    )


def savings_boxes(resolution: CalculationSourceResolution, year: int = YEAR) -> dict[str, Decimal | None]:
    revision = m100_revision(year)
    return {
        str(sole_bound_casilla(revision, binding.id)): resolution.binding_values.get(binding.id)
        for binding, provider in capital_mobiliario_position_bindings(revision)
        if provider.dictionary_field is None
    }

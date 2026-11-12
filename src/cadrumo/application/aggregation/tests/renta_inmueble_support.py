"""Build synthetic let properties, leases and linked ledger rows for the ``renta_inmueble`` tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from ....domain.contribuyente.arrendamiento_record import ArrendamientoRecord, Inquilino, InquilinoEdad
from ....domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamiento_row_values,
    facts_for_row,
    inmueble_row_values,
)
from ....domain.contribuyente.inmueble_record import (
    AdquisicionTitulo,
    ImportesMovimientos,
    InmuebleNaturaleza,
    InmuebleRecord,
    InmuebleSituacion,
    InmuebleTitularidad,
    TitularidadRegimen,
    TitularRole,
)
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

REFERENCIA_CATASTRAL = "9872023VH5797S0001WX"
TENANT_NIF = "X1234567L"


def inmueble(clave: int = 0, *, ejercicio: int, **fields: object) -> InmuebleRecord:
    """Return a urban property held in pleno dominio by the declarant since before ``ejercicio``."""
    payload: dict[str, object] = {
        "clave": clave,
        "situacion": InmuebleSituacion.CATASTRAL_COMUN,
        "referencia_catastral": REFERENCIA_CATASTRAL,
        "naturaleza": InmuebleNaturaleza.URBANA,
        "direccion": "Calle Sintetica 1, Madrid",
        "titularidad": InmuebleTitularidad(
            regimen=TitularidadRegimen.PLENO_DOMINIO,
            titular=TitularRole.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal(100),
        ),
        "adquisicion_titulo": AdquisicionTitulo.ONEROSA,
        "fecha_adquisicion": date(ejercicio - 5, 6, 1),
    }
    payload.update(fields)
    return InmuebleRecord.model_validate(payload)


def with_fields[RecordT: BaseModel](record: RecordT, fields: Mapping[str, object]) -> RecordT:
    """Return ``record`` validated again with ``fields`` layered over it."""
    return type(record).model_validate({**record.model_dump(), **fields})


def co_owned(clave: int = 0, *, ejercicio: int, scope: ImportesMovimientos) -> InmuebleRecord:
    """Return a property the declarant holds half of, whose ledger rows hold ``scope`` amounts."""
    return inmueble(
        clave,
        ejercicio=ejercicio,
        titularidad=InmuebleTitularidad(
            regimen=TitularidadRegimen.PLENO_DOMINIO,
            titular=TitularRole.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal(50),
        ),
        importes_movimientos=scope,
    )


def lease(
    clave: int = 0, *, inmueble_clave: int = 0, start: date, end: date | None = None, **fields: object
) -> ArrendamientoRecord:
    """Return a dwelling lease of one adult tenant, not a relative, starting on ``start``."""
    payload: dict[str, object] = {
        "clave": clave,
        "inmueble": inmueble_clave,
        "fecha_contrato": start,
        "fecha_inicio": start,
        "fecha_fin": end,
        "uso_vivienda": True,
        "inquilinos": (Inquilino(nif=TENANT_NIF, franja_edad=InquilinoEdad.OTRA, extranjero=False),),
        "arrendatario_pariente_art24": False,
    }
    payload.update(fields)
    return ArrendamientoRecord.model_validate(payload)


def profile_facts(inmuebles: tuple[InmuebleRecord, ...], leases: tuple[ArrendamientoRecord, ...]) -> dict[str, str]:
    """Return the profile's stated facts for these properties and leases, keyed by path."""
    facts: dict[str, str] = {}
    for record in inmuebles:
        facts |= facts_for_row(INMUEBLE_SECTION, record.clave, inmueble_row_values(record))
    for record in leases:
        facts |= facts_for_row(ARRENDAMIENTO_SECTION, record.clave, arrendamiento_row_values(record))
    return facts


def ledger_row(
    provider_id: str,
    *,
    amount: Decimal,
    direction: TransactionDirection,
    booked: date,
    currency: str = "EUR",
    **fields: object,
) -> Transaction:
    """Return one validated ledger row booked on ``booked`` with ``fields`` layered over it."""
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=None,
        amount=amount,
        currency=currency,
        counterparty="Contraparte sintetica",
        description=provider_id,
        provenance=RawProvenance(
            source_path=Path("renta-inmueble.csv"),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime.combine(booked, time(8, 0), tzinfo=UTC),
            provider_name="renta inmueble provider",
        ),
        raw_fields={},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
    }
    payload.update(fields)
    return Transaction.model_validate(payload)


def rent(
    provider_id: str,
    *,
    lease_clave: int = 0,
    amount: Decimal,
    booked: date,
    currency: str = "EUR",
    **fields: object,
) -> Transaction:
    """Return a rent receipt linked to the lease whose row key is ``lease_clave``."""
    return ledger_row(
        provider_id,
        amount=amount,
        direction=TransactionDirection.INCOMING,
        booked=booked,
        currency=currency,
        arrendamiento_ref=str(lease_clave),
        **fields,
    )


def expense(
    provider_id: str,
    *,
    concept: str,
    inmueble_clave: int = 0,
    amount: Decimal,
    booked: date,
    currency: str = "EUR",
    **fields: object,
) -> Transaction:
    """Return a payment for the property whose row key is ``inmueble_clave``, of expense ``concept``."""
    return ledger_row(
        provider_id,
        amount=amount,
        direction=TransactionDirection.OUTGOING,
        booked=booked,
        currency=currency,
        inmueble_ref=str(inmueble_clave),
        gasto_capital_inmobiliario=concept,
        **fields,
    )


def monthly_rent(
    ejercicio: int, *, amount: Decimal, lease_clave: int = 0, months: range = range(1, 13)
) -> tuple[Transaction, ...]:
    """Return one rent receipt on the first of each month in ``months`` of ``ejercicio``."""
    return tuple(
        rent(f"rent-{lease_clave}-{month}", lease_clave=lease_clave, amount=amount, booked=date(ejercicio, month, 1))
        for month in months
    )

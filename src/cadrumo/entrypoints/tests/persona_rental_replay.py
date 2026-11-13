"""Replay a persona's let dwelling into its profile and its ledger through the production rental operations.

The property and the lease are repeatable profile rows added through the same registered row operation the
``config profile inmueble add`` and ``config profile arrendamiento add`` commands submit. The ledger rows of the
dwelling are then linked to the lease or the property through the ledger classify operation, which gives them the
rental income category.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from pydantic import BaseModel

from ...application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowValue,
)
from ...domain.contribuyente.arrendamiento_record import InquilinoEdad
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ...domain.transactions.rental_link import RENTAL_LINK_IRPF_CATEGORY
from ...domain.user_profile.values import UserProfileRecord
from ...tests.personas import Persona, RentalLedgerLink, RentalProperty, YearEnvelope

type SettleOperation = Callable[[str, BaseModel], BaseModel | None]
"""Settles one registered operation against the persona's profile and returns its public result."""

type LoadProfileRecord = Callable[[], UserProfileRecord]
"""Reads the profile's current record, the baseline a profile row mutation names."""

_BUSINESS = "BUSINESS"
_YOUNG_TENANT_AGES = range(18, 36)


class PersonaRentalError(RuntimeError):
    """The persona's rental block cannot be recorded as stated."""


@dataclass(frozen=True, slots=True)
class RecordedRental:
    """The profile row keys one let dwelling received."""

    inmueble: int
    arrendamiento: int


def _age_on(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def tenant_age_band(persona: Persona, rental: RentalProperty, envelope: YearEnvelope) -> InquilinoEdad:
    """Derive the tenant's age band at the lease's signing from the tenant identity's birth date."""
    born = persona.identities.role(rental.tenant).birth_date
    if born is None:
        raise PersonaRentalError(f"{rental.id}: the tenant {rental.tenant} states no birth date to derive an age band")
    age = _age_on(born.resolve(envelope), rental.fecha_contrato.resolve(envelope))
    return InquilinoEdad.DE_18_A_35 if age in _YOUNG_TENANT_AGES else InquilinoEdad.OTRA


def _flag(value: bool) -> str:
    return "true" if value else "false"


def property_row(rental: RentalProperty, envelope: YearEnvelope) -> tuple[tuple[str, str], ...]:
    """The facts of the property row the persona states."""
    cadastral = ";".join(
        f"{value.year.resolve(envelope)}:{value.total}:{value.construccion}" for value in rental.valores_catastrales
    )
    return (
        ("situacion", rental.situacion),
        ("referencia_catastral", rental.referencia_catastral),
        ("naturaleza", rental.naturaleza),
        ("titularidad_regimen", rental.titularidad_regimen),
        ("titular", rental.titular),
        ("porcentaje_propiedad", str(rental.porcentaje_propiedad)),
        ("importe_adquisicion", str(rental.importe_adquisicion)),
        ("valor_suelo", str(rental.valor_suelo)),
        ("adquisicion_titulo", rental.adquisicion_titulo),
        ("fecha_adquisicion", rental.fecha_adquisicion.resolve(envelope).isoformat()),
        ("gastos_tributos_adquisicion", str(rental.gastos_tributos_adquisicion)),
        ("valores_catastrales", cadastral),
        *(
            ()
            if rental.arrendado_desde is None
            else (("arrendado_desde", rental.arrendado_desde.resolve(envelope).isoformat()),)
        ),
    )


def lease_row(
    persona: Persona, rental: RentalProperty, inmueble: int, envelope: YearEnvelope
) -> tuple[tuple[str, str], ...]:
    """The facts of the lease row the persona states; the tenant's age band is derived, not stated."""
    tenant = persona.identities.role(rental.tenant)
    band = tenant_age_band(persona, rental, envelope)
    return (
        ("inmueble", str(inmueble)),
        ("fecha_contrato", rental.fecha_contrato.resolve(envelope).isoformat()),
        ("fecha_inicio", rental.fecha_inicio.resolve(envelope).isoformat()),
        ("uso_vivienda", _flag(rental.uso_vivienda)),
        ("zona_tensionada", _flag(rental.zona_tensionada)),
        ("primer_arrendamiento_vivienda", _flag(rental.primer_arrendamiento_vivienda)),
        ("arrendatario_pariente_art24", _flag(rental.arrendatario_pariente_art24)),
        ("incumple_lau_17_6", _flag(rental.incumple_lau_17_6)),
        ("inquilinos", f"{tenant.value}:{band.value}:no"),
    )


def _added_row(
    section: str,
    facts: tuple[tuple[str, str], ...],
    *,
    profile_id: UUID,
    settle: SettleOperation,
    load_record: LoadProfileRecord,
) -> int:
    record = load_record()
    result = settle(
        PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        ProfileRepeatableRowMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            section_key=section,
            values=tuple(ProfileRepeatableRowValue(field_key=key, value=value) for key, value in facts),
        ),
    )
    if not isinstance(result, ProfileRepeatableRowMutationOperationProjection):
        raise PersonaRentalError(f"{section}: the row operation published no row")
    return result.row_index


def _link_for(rental: RentalProperty, ref: str) -> RentalLedgerLink | None:
    found = [link for link in rental.ledger_links if ref.startswith(link.ref_prefix)]
    if len(found) > 1:
        raise PersonaRentalError(f"{rental.id} {ref}: more than one ledger link names the row")
    return found[0] if found else None


def link_fields(link: RentalLedgerLink, recorded: RecordedRental) -> dict[LedgerClassifyPatchField, str]:
    """The classify patch that links a row to the lease or the property under the rental income category."""
    values: dict[LedgerClassifyPatchField, str] = {
        "business_classification": _BUSINESS,
        "irpf_category": RENTAL_LINK_IRPF_CATEGORY,
    }
    if link.target == "arrendamiento":
        values["arrendamiento_ref"] = str(recorded.arrendamiento)
    else:
        values["inmueble_ref"] = str(recorded.inmueble)
        if link.gasto is not None:
            values["gasto_capital_inmobiliario"] = link.gasto
    return values


def replay_rentals(
    persona: Persona,
    profile_id: UUID,
    envelope: YearEnvelope,
    transactions: Mapping[str, str],
    *,
    actor: str,
    settle: SettleOperation,
    load_record: LoadProfileRecord,
) -> dict[str, RecordedRental]:
    """Record each let dwelling's property and lease, then link its ledger rows; returns the rows by dwelling id."""
    recorded: dict[str, RecordedRental] = {}
    for rental in persona.rental_properties:
        inmueble = _added_row(
            INMUEBLE_SECTION,
            property_row(rental, envelope),
            profile_id=profile_id,
            settle=settle,
            load_record=load_record,
        )
        arrendamiento = _added_row(
            ARRENDAMIENTO_SECTION,
            lease_row(persona, rental, inmueble, envelope),
            profile_id=profile_id,
            settle=settle,
            load_record=load_record,
        )
        recorded[rental.id] = RecordedRental(inmueble=inmueble, arrendamiento=arrendamiento)
        unmatched = {link.ref_prefix for link in rental.ledger_links}
        for row in persona.ledger:
            link = _link_for(rental, row.ref)
            if link is None:
                continue
            unmatched.discard(link.ref_prefix)
            values = link_fields(link, recorded[rental.id])
            settle(
                LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
                LedgerClassifyRequest(
                    profile_id=profile_id,
                    transaction_id=transactions[row.ref],
                    patch=LedgerClassifyPatch.model_validate(values),
                    patch_fields=tuple(sorted(values)),
                    actor=actor,
                ),
            )
        if unmatched:
            raise PersonaRentalError(f"{rental.id}: no ledger row starts with {sorted(unmatched)}")
    return recorded


__all__ = [
    "PersonaRentalError",
    "RecordedRental",
    "lease_row",
    "link_fields",
    "property_row",
    "replay_rentals",
    "tenant_age_band",
]

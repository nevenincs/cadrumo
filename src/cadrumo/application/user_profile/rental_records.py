"""Admitting a property or a lease row before it reaches the profile write door.

The profile write door judges each fact's shape; it cannot judge what a row means
together with the rest of the profile. This module does, for the two rental
sections, and the repeatable-row operation runs it inside add, update and remove
so every door -- the generic row command, the specific property and lease
commands, the manager and the window -- gives one acceptance and one refusal:

* a row must cohere as a record;
* a lease must name a property row the profile holds;
* a property's stated letting start cannot be later than the start of any of its leases;
* a property's principal must be another property row the profile holds;
* a tenant identifier must hold its control letter unless it is declared foreign;
* a property that a lease or an accessory names cannot be removed;
* a property or a lease that a ledger row names cannot be removed.

The canonical form returned is the one stored: the same grammar a round trip
through the record gives, so a value typed in any accepted spelling is stored in
exactly one. Every refusal carries the door that resolves it as a typed
precondition verdict naming a catalogue action -- a row command of one of the two
families, addressed to the row when it is known, or the ledger classification --
so every frontend renders the same remedy and no sentence carries a command.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import validate_spanish_tax_id
from ...core.modelo import Modelo
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamiento_from_row,
    arrendamiento_row_values,
    arrendamientos_from_facts,
    inmueble_from_row,
    inmueble_row_values,
    inmuebles_from_facts,
    rows_from_facts,
)
from ...domain.contribuyente.inmueble_record import require_letting_start_before_leases
from ...domain.user_profile.errors import UserProfileValidationError
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

RENTAL_SECTIONS: Final = frozenset({INMUEBLE_SECTION, ARRENDAMIENTO_SECTION})

_ROW_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_row_invalid"
_LEASE_PROPERTY_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.rental_lease_property_missing"
_PRINCIPAL_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.rental_principal_missing"
_PROPERTY_HAS_LEASES_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_leases"
_PROPERTY_HAS_ACCESSORIES_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_accessories"
_PROPERTY_HAS_LEDGER_ROWS_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_ledger_rows"
_LEASE_HAS_LEDGER_ROWS_LOCALE_KEY: Final = "application.user_profile.errors.rental_lease_has_ledger_rows"
_LEDGER_UNREADABLE_LOCALE_KEY: Final = "application.user_profile.errors.rental_ledger_unreadable"
_TENANT_ID_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_tenant_id_invalid"
_TENANT_SLOT_ROLE: Final = "irpf_inmueble_arrendatario_nif_o_id_extranjero"
_DOOR_FAMILY: Final = {INMUEBLE_SECTION: "inmueble", ARRENDAMIENTO_SECTION: "arrendamiento"}
_CONDITION_PREFIX: Final = "user_profile.rental"
_LEDGER_LINK_ACTION_ID: Final = "operator.ledger.classify"
_ROW_ARGUMENT: Final = "row"
_VALUE_ARGUMENT: Final = "value"

type _Fact = str | int | bool


@dataclass(frozen=True, slots=True)
class RentalLedgerReferences:
    """The lease, property and position references of one profile's ledger rows, with the row count of each."""

    leases: Mapping[str, int]
    properties: Mapping[str, int]
    positions: Mapping[str, int] = field(default_factory=dict[str, int])


class RentalLedgerReferenceReader(Protocol):
    """Read the rental references of one profile's ledger without writing it."""

    def __call__(self, *, profile_id: str) -> RentalLedgerReferences:
        """Return every lease and property reference a ledger row of ``profile_id`` carries."""
        ...


class ProfileRecordRowMutation(StrEnum):
    """The row mutation an admission judges; it names the door command in a refusal."""

    ADD = "add"
    EDIT = "edit"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class _RowDoor:
    """The row command of one rental family that resolves a refusal, and the row it addresses when known."""

    section_key: str
    mutation: ProfileRecordRowMutation
    row_key: int | None = None

    def arguments(self) -> tuple[ActionArgumentBinding, ...]:
        """Bind the row the door addresses and ask for the values, which are the operator's to state."""
        row = (
            ActionArgumentBinding(argument_name=_ROW_ARGUMENT, status=ActionArgumentStatus.MISSING)
            if self.row_key is None
            else ActionArgumentBinding(
                argument_name=_ROW_ARGUMENT,
                status=ActionArgumentStatus.RESOLVED,
                value=self.row_key,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=_ROW_ARGUMENT,
            )
        )
        value = ActionArgumentBinding(argument_name=_VALUE_ARGUMENT, status=ActionArgumentStatus.MISSING)
        if self.mutation is ProfileRecordRowMutation.ADD:
            return (value,)
        if self.mutation is ProfileRecordRowMutation.EDIT:
            return (row, value)
        return (row,)

    def action_id(self) -> str:
        """Name the catalogue action of this family's row command."""
        return f"operator.profile.{_DOOR_FAMILY[self.section_key]}.{self.mutation.value}"


def _door_verdict(
    reason: str,
    facts: Mapping[str, _Fact],
    *,
    action_id: str,
    arguments: tuple[ActionArgumentBinding, ...] = (),
) -> PreconditionVerdict:
    condition = f"{_CONDITION_PREFIX}.{reason}.admissible"
    missing = tuple(item.argument_name for item in arguments if item.status is ActionArgumentStatus.MISSING)
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=(
            ConditionEvidence(
                condition_id=condition,
                evidence_id=f"{condition}.observation",
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={**facts, "admissible": False},
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=arguments,
        missing_argument_names=missing,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS if missing else ActionConditionality.IMMEDIATE,
    )


def _row_door_verdict(reason: str, facts: Mapping[str, _Fact], door: _RowDoor) -> PreconditionVerdict:
    return _door_verdict(reason, facts, action_id=door.action_id(), arguments=door.arguments())


def _refusing_incoherent[RecordT](build: Callable[[], RecordT], *, door: _RowDoor) -> RecordT:
    """Run a record build, serving its refusal as the localised sentence that names the leaf, with its door."""
    try:
        return build()
    except ProfileAnswerTypeError as error:
        leaf = str((error.context or {}).get("key", "row"))
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY,
            context={"leaf": leaf},
            precondition_verdict=_row_door_verdict("row", {"leaf": leaf}, door),
        ) from error


def refuse_incoherent_rental_row[RecordT](
    build: Callable[[], RecordT], *, section_key: str, mutation: ProfileRecordRowMutation
) -> RecordT:
    """Run a build of a rental row's facts, serving its refusal as the row admission serves it for that door.

    The facts are judged before the row is read, so the door asks for the row it addresses.
    """
    return _refusing_incoherent(build, door=_RowDoor(section_key, mutation))


def _tenant_capacity(authority: PinnedAuthorityOperation) -> int:
    """Count the tenant identification slots the newest annual-return layout gives one property."""
    directory = authority.modelo_directory(Modelo("100"))
    newest = max(directory.revisions, key=lambda revision: revision.valid_from)
    revision = authority.revision(directory.modelo_id, newest.id)
    return sum(1 for casilla in revision.casillas if casilla.semantic_role == _TENANT_SLOT_ROLE)


def is_rental_section(section_key: str) -> bool:
    """Report whether a repeatable section is one of the two rental record sections."""
    return section_key in RENTAL_SECTIONS


def admit_rental_row(
    section_key: str,
    *,
    row_key: int,
    row: Mapping[str, str],
    path_values: Mapping[str, object],
    authority: PinnedAuthorityOperation,
    mutation: ProfileRecordRowMutation,
) -> dict[str, str]:
    """Return the stored form of a rental row, refusing a row the profile cannot hold.

    ``path_values`` are the facts of the profile the row is written into; ``row``
    is the complete row as it will stand after the mutation.
    """
    if section_key == INMUEBLE_SECTION:
        return _admit_inmueble(row_key, row, path_values, mutation)
    if section_key == ARRENDAMIENTO_SECTION:
        return _admit_arrendamiento(row_key, row, path_values, authority, mutation)
    raise UserProfileValidationError(f"section {section_key!r} is not a rental record section")


def _admit_inmueble(
    row_key: int, row: Mapping[str, str], path_values: Mapping[str, object], mutation: ProfileRecordRowMutation
) -> dict[str, str]:
    door = _RowDoor(INMUEBLE_SECTION, mutation, row_key)
    record = _refusing_incoherent(lambda: inmueble_from_row(row_key, row), door=door)
    principal = record.inmueble_principal
    if principal is not None and principal not in {
        clave for clave in rows_from_facts(INMUEBLE_SECTION, path_values) if clave != row_key
    }:
        raise UserProfileValidationError(
            translated_message=_PRINCIPAL_MISSING_LOCALE_KEY,
            context={"principal": principal},
            precondition_verdict=_row_door_verdict(
                "principal", {"principal": principal}, _RowDoor(INMUEBLE_SECTION, ProfileRecordRowMutation.ADD)
            ),
        )
    _refusing_incoherent(
        lambda: require_letting_start_before_leases(
            record,
            (lease.fecha_inicio for lease in arrendamientos_from_facts(path_values) if lease.inmueble == row_key),
        ),
        door=door,
    )
    return inmueble_row_values(record)


def _require_lease_after_letting_start(
    row_key: int, record: ArrendamientoRecord, path_values: Mapping[str, object]
) -> None:
    """Refuse a lease that starts before its property's stated letting start."""
    landlord_property = next(
        (inmueble for inmueble in inmuebles_from_facts(path_values) if inmueble.clave == record.inmueble), None
    )
    if landlord_property is None:
        return
    others = (
        lease.fecha_inicio
        for lease in arrendamientos_from_facts(path_values)
        if lease.inmueble == record.inmueble and lease.clave != row_key
    )
    _refusing_incoherent(
        lambda: require_letting_start_before_leases(landlord_property, (*others, record.fecha_inicio)),
        door=_RowDoor(INMUEBLE_SECTION, ProfileRecordRowMutation.EDIT, landlord_property.clave),
    )


def _admit_arrendamiento(
    row_key: int,
    row: Mapping[str, str],
    path_values: Mapping[str, object],
    authority: PinnedAuthorityOperation,
    mutation: ProfileRecordRowMutation,
) -> dict[str, str]:
    door = _RowDoor(ARRENDAMIENTO_SECTION, mutation, row_key)
    record = _refusing_incoherent(lambda: arrendamiento_from_row(row_key, row), door=door)
    if record.inmueble not in {inmueble.clave for inmueble in inmuebles_from_facts(path_values)}:
        raise UserProfileValidationError(
            translated_message=_LEASE_PROPERTY_MISSING_LOCALE_KEY,
            context={"inmueble": record.inmueble},
            precondition_verdict=_row_door_verdict(
                "lease_property",
                {"inmueble": record.inmueble},
                _RowDoor(INMUEBLE_SECTION, ProfileRecordRowMutation.ADD),
            ),
        )
    _require_lease_after_letting_start(row_key, record, path_values)
    if len(record.inquilinos) > _tenant_capacity(authority):
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY,
            context={"leaf": "inquilinos"},
            precondition_verdict=_row_door_verdict("row", {"leaf": "inquilinos"}, door),
        )
    tax_id_format = runtime_tax_id_format(authority=authority)
    for inquilino in record.inquilinos:
        if inquilino.extranjero:
            continue
        try:
            validate_spanish_tax_id(inquilino.nif, tax_id_format)
        except IdentityError as error:
            raise UserProfileValidationError(
                translated_message=_TENANT_ID_INVALID_LOCALE_KEY,
                precondition_verdict=_row_door_verdict("tenant_id", {"leaf": "inquilinos"}, door),
            ) from error
    return arrendamiento_row_values(record)


def unreadable_rental_ledger_references(*, profile_id: str) -> RentalLedgerReferences:
    """Refuse a rental row removal in a composition that gave the profile no read of the ledger."""
    raise UserProfileValidationError(
        translated_message=_LEDGER_UNREADABLE_LOCALE_KEY, context={"profile_id": profile_id}
    )


def rental_row_keys(section_key: str, path_values: Mapping[str, object]) -> frozenset[int]:
    """Return the keys of the rows a rental section holds; a cleared row is absent."""
    return frozenset(rows_from_facts(section_key, path_values))


def canonical_rental_ref(row_key: int) -> str:
    """Return the text a ledger row carries to name the rental row ``row_key``."""
    return str(row_key)


def require_rental_row_removable(
    section_key: str,
    *,
    row_key: int,
    path_values: Mapping[str, object],
    ledger_references: RentalLedgerReferences,
) -> None:
    """Refuse removing a row that a lease, an accessory or a ledger row of the profile still names."""
    if section_key == INMUEBLE_SECTION:
        _require_property_unreferenced_by_profile(row_key, path_values)
    _require_unreferenced_by_ledger(section_key, row_key, ledger_references)


def _require_unreferenced_by_ledger(section_key: str, row_key: int, references: RentalLedgerReferences) -> None:
    held = references.properties if section_key == INMUEBLE_SECTION else references.leases
    rows = held.get(canonical_rental_ref(row_key), 0)
    if not rows:
        return
    raise UserProfileValidationError(
        translated_message=(
            _PROPERTY_HAS_LEDGER_ROWS_LOCALE_KEY
            if section_key == INMUEBLE_SECTION
            else _LEASE_HAS_LEDGER_ROWS_LOCALE_KEY
        ),
        context={"row": row_key, "rows": rows},
        precondition_verdict=_door_verdict(
            "ledger_link",
            {"section": section_key, "row": row_key, "rows": rows},
            action_id=_LEDGER_LINK_ACTION_ID,
        ),
    )


def _require_property_unreferenced_by_profile(row_key: int, path_values: Mapping[str, object]) -> None:
    leases = sorted(lease.clave for lease in arrendamientos_from_facts(path_values) if lease.inmueble == row_key)
    if leases:
        listed = ", ".join(str(lease) for lease in leases)
        raise UserProfileValidationError(
            translated_message=_PROPERTY_HAS_LEASES_LOCALE_KEY,
            context={"inmueble": row_key, "leases": listed},
            precondition_verdict=_row_door_verdict(
                "property_leases",
                {"inmueble": row_key, "leases": listed},
                _RowDoor(ARRENDAMIENTO_SECTION, ProfileRecordRowMutation.REMOVE, _only(leases)),
            ),
        )
    accessories = sorted(
        property_.clave for property_ in inmuebles_from_facts(path_values) if property_.inmueble_principal == row_key
    )
    if accessories:
        listed = ", ".join(str(clave) for clave in accessories)
        raise UserProfileValidationError(
            translated_message=_PROPERTY_HAS_ACCESSORIES_LOCALE_KEY,
            context={"inmueble": row_key, "accessories": listed},
            precondition_verdict=_row_door_verdict(
                "property_accessories",
                {"inmueble": row_key, "accessories": listed},
                _RowDoor(INMUEBLE_SECTION, ProfileRecordRowMutation.EDIT, _only(accessories)),
            ),
        )


def _only(rows: list[int]) -> int | None:
    """Return the one row a door can address, or none when the operator chooses among several."""
    return rows[0] if len(rows) == 1 else None


__all__ = [
    "RENTAL_SECTIONS",
    "ProfileRecordRowMutation",
    "RentalLedgerReferenceReader",
    "RentalLedgerReferences",
    "admit_rental_row",
    "canonical_rental_ref",
    "is_rental_section",
    "refuse_incoherent_rental_row",
    "rental_row_keys",
    "require_rental_row_removable",
    "unreadable_rental_ledger_references",
]

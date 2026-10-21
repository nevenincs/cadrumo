"""The installation acts this interface offers, derived from the runtime's own table.

Nothing here names an act to offer it. The catalogue is the runtime's
:data:`INSTALLATION_ACT_CONTRACTS`, and each act's form is read from its request
model, so an act the runtime gains is offered here with a working form before
anyone writes a screen for it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from types import NoneType, UnionType
from typing import Annotated, Final, TypeAliasType, Union, cast, get_args, get_origin
from uuid import UUID, uuid4

from pydantic import ValidationError
from pydantic.fields import FieldInfo

from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActContract,
    InstallationActRequest,
    InstallationCompleted,
    InstallationHostPath,
    installation_request_facts,
)

from ....application.operations.registry import OperationFrontendProjection
from ....core.errors.hierarchy import CadrumoError

#: Members every request carries that the interface fills in itself.
_COORDINATE_FIELDS: Final[frozenset[str]] = frozenset({"request_id", "frontend", "action"})

#: The member a changing act withholds until the person has seen what it would do.
CONFIRMATION_FIELD: Final[str] = "confirmed"


class InstallationFamily(StrEnum):
    """The groups the acts are listed under."""

    STORAGE = "storage"
    PROFILES = "profiles"
    RESET = "reset"
    REPAIR = "repair"
    VERIFICATION = "verification"
    OTHER = "other"


_FAMILY_BY_PREFIX: Final[tuple[tuple[str, InstallationFamily], ...]] = (
    ("storage_", InstallationFamily.STORAGE),
    ("profile_", InstallationFamily.PROFILES),
    ("archive_", InstallationFamily.PROFILES),
    ("recovery_", InstallationFamily.PROFILES),
    ("reset_", InstallationFamily.RESET),
    ("repair_", InstallationFamily.REPAIR),
    ("review_package_", InstallationFamily.VERIFICATION),
    ("report_verify_", InstallationFamily.VERIFICATION),
)


def family_of(act: InstallationAct) -> InstallationFamily:
    """Place one act in its family; an act of no known family is still listed."""
    for prefix, family in _FAMILY_BY_PREFIX:
        if act.value.startswith(prefix):
            return family
    return InstallationFamily.OTHER


class ActFieldKind(StrEnum):
    """How one request member is asked for."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    TEXT = "text"
    PATH = "path"
    UUID = "uuid"
    CHOICE = "choice"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class ActField:
    """One member of an act's request, as the form asks for it.

    ``supplied_by`` names the act that can answer this member when the person
    leaves it empty.
    """

    name: str
    kind: ActFieldKind
    required: bool
    default: bool | int | str | None = None
    choices: tuple[str, ...] = ()
    supplied_by: InstallationAct | None = None


@dataclass(frozen=True, slots=True)
class ActPrerequisite:
    """A read whose reply answers one member of the act that follows it."""

    act: InstallationAct
    reply_member: str
    request_member: str


#: An archive import names the digest of the source it prepared. The command
#: line reads the source and imports it in one step, so the person is never
#: asked for the digest: left empty, it is read here the same way.
_PREREQUISITES: Final[Mapping[InstallationAct, ActPrerequisite]] = {
    InstallationAct.ARCHIVE_IMPORT: ActPrerequisite(
        act=InstallationAct.ARCHIVE_IMPORT_PREPARE, reply_member="source_digest", request_member="source_digest"
    ),
}


class ActInputError(CadrumoError):
    """The form's values do not make a request; ``fields`` names the members at fault, never a value."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        """Retain the names of the members to correct."""
        super().__init__("installation act input is incomplete or malformed")
        self.fields = fields


def _unwrapped(annotation: object) -> tuple[object, bool, bool]:
    """Reduce an annotation to its core type, whether it admits ``None``, and whether it is a host path."""
    optional = False
    host_path = False
    current = annotation
    while True:
        if current is InstallationHostPath:
            host_path = True
        if isinstance(current, TypeAliasType):
            current = current.__value__
            continue
        origin = get_origin(current)
        if origin is Annotated:
            current = get_args(current)[0]
            continue
        if origin is Union or origin is UnionType:
            members = [member for member in get_args(current) if member is not NoneType]
            optional = optional or len(members) != len(get_args(current))
            if len(members) != 1:
                return current, optional, False
            current = members[0]
            continue
        return current, optional, host_path


def _field_of(name: str, info: FieldInfo, *, supplied_by: InstallationAct | None) -> ActField:
    core, optional, host_path = _unwrapped(info.annotation)
    required = info.is_required() and not optional and supplied_by is None
    default = info.default if isinstance(info.default, bool | int | str) else None
    if core is bool:
        return ActField(name, ActFieldKind.BOOLEAN, required=False, default=bool(default))
    if core is int:
        return ActField(name, ActFieldKind.INTEGER, required=required, default=default)
    if core is UUID:
        return ActField(name, ActFieldKind.UUID, required=required, supplied_by=supplied_by)
    if isinstance(core, type) and issubclass(core, Enum):
        choices = tuple(str(member.value) for member in core)
        return ActField(name, ActFieldKind.CHOICE, required=required, choices=choices)
    if isinstance(core, type) and issubclass(core, str):
        kind = ActFieldKind.PATH if host_path else ActFieldKind.TEXT
        return ActField(name, kind, required=required, default=default, supplied_by=supplied_by)
    return ActField(name, ActFieldKind.JSON, required=required, supplied_by=supplied_by)


@dataclass(frozen=True, slots=True)
class OfferedAct:
    """One act of the runtime's table with the form its request model implies."""

    contract: InstallationActContract
    family: InstallationFamily
    fields: tuple[ActField, ...]
    asks_confirmation: bool
    prerequisite: ActPrerequisite | None

    @property
    def act(self) -> InstallationAct:
        """The act this entry offers."""
        return self.contract.act

    @property
    def reads_only(self) -> bool:
        """Whether no request for this act can change a record."""
        return not self.contract.facts.changes_records

    def request(self, values: Mapping[str, object], *, confirmed: bool = False) -> InstallationActRequest:
        """Build this act's request from the form's values.

        Args:
            values: Each offered member's value as the form holds it: a
                boolean for a switch, text for everything else.
            confirmed: Whether the person has confirmed a changing act.

        Raises:
            ActInputError: A member is missing or does not fit its type.
        """
        document: dict[str, object] = {
            "request_id": str(uuid4()),
            "frontend": OperationFrontendProjection.TUI.value,
        }
        if self.asks_confirmation:
            document[CONFIRMATION_FIELD] = confirmed
        malformed: list[str] = []
        for field in self.fields:
            try:
                value = _member_value(field, values.get(field.name))
            except ValueError:
                malformed.append(field.name)
                continue
            if value is not None:
                document[field.name] = value
            elif field.required:
                malformed.append(field.name)
        if malformed:
            raise ActInputError(tuple(malformed))
        try:
            request = self.contract.request.model_validate_json(json.dumps(document))
        except ValidationError as error:
            named = tuple(dict.fromkeys(str(issue["loc"][0]) for issue in error.errors() if issue["loc"]))
            raise ActInputError(named or tuple(field.name for field in self.fields)) from None
        return cast("InstallationActRequest", request)

    def changes_records(self, request: InstallationActRequest) -> bool:
        """Whether this exact request may change a record."""
        return installation_request_facts(request).changes_records


def _member_value(field: ActField, raw: object) -> object | None:
    """Turn one form value into the member's JSON value, or ``None`` when it was left empty."""
    if field.kind is ActFieldKind.BOOLEAN:
        return bool(raw)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        return None
    if field.kind is ActFieldKind.INTEGER:
        return int(text)
    if field.kind is ActFieldKind.PATH:
        # The runtime's working directory is not this process's, so a relative
        # path is resolved here, where the person typed it.
        return str(Path(text).expanduser().absolute())
    if field.kind is ActFieldKind.JSON:
        return json.loads(text)
    return text


def offer_contract(contract: InstallationActContract) -> OfferedAct:
    """Derive the offered form of one row of an act table."""
    prerequisite = _PREREQUISITES.get(contract.act)
    if prerequisite is not None and prerequisite.act not in INSTALLATION_ACT_CONTRACTS:
        prerequisite = None
    members = contract.request.model_fields
    fields = tuple(
        _field_of(
            name,
            info,
            supplied_by=(
                prerequisite.act if prerequisite is not None and prerequisite.request_member == name else None
            ),
        )
        for name, info in members.items()
        if name not in _COORDINATE_FIELDS and name != CONFIRMATION_FIELD
    )
    return OfferedAct(
        contract=contract,
        family=family_of(contract.act),
        fields=fields,
        asks_confirmation=CONFIRMATION_FIELD in members,
        prerequisite=prerequisite,
    )


def offered_acts() -> tuple[OfferedAct, ...]:
    """Every act of the runtime's table, grouped by family and otherwise in table order."""
    order = {family: index for index, family in enumerate(InstallationFamily)}
    acts = [offer_contract(contract) for contract in INSTALLATION_ACT_CONTRACTS.values()]
    return tuple(sorted(acts, key=lambda offered: order[offered.family]))


def offered_act(act: InstallationAct) -> OfferedAct:
    """The offered form of one act of the table."""
    return offer_contract(INSTALLATION_ACT_CONTRACTS[act])


def supplied_member(prerequisite: ActPrerequisite, reply: InstallationCompleted) -> str:
    """Read the member a prerequisite's reply supplies, as the text the form would have held."""
    value = reply.model_dump(mode="json")[prerequisite.reply_member]
    if not isinstance(value, str):
        raise ActInputError((prerequisite.request_member,))
    return value


__all__ = [
    "CONFIRMATION_FIELD",
    "ActField",
    "ActFieldKind",
    "ActInputError",
    "ActPrerequisite",
    "InstallationFamily",
    "OfferedAct",
    "family_of",
    "offer_contract",
    "offered_act",
    "offered_acts",
    "supplied_member",
]

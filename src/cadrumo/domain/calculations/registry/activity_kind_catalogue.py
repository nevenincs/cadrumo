"""Typed projection of the registry-owned IRPF activity-kind vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...deadlines.models import IrpfActivityKind
from .errors import RegistryValidationError
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_FACT_ID = "m036-activity-selector-catalogue"
_ACTIVITY_KIND_SUFFIX = ".activity_kind"
_SELECTOR_PREFIX = "selector."


@dataclass(frozen=True, slots=True)
class IrpfActivityKindDefinition:
    """One registry-declared activity-kind token and its selector owners."""

    token: IrpfActivityKind
    selector_fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IrpfActivityKindCatalogue:
    """Typed projection of the activity-kind values carried by fact 0082."""

    definitions: tuple[IrpfActivityKindDefinition, ...]

    @property
    def all_activity_kinds(self) -> frozenset[IrpfActivityKind]:
        """Return every activity-kind token declared by the catalogue."""
        return frozenset(item.token for item in self.definitions)

    def require(self, value: object) -> IrpfActivityKind:
        """Return a token only when the selected registry fact declares it."""
        if isinstance(value, IrpfActivityKind):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IRPF activity-kind token must be non-empty")
            try:
                token = IrpfActivityKind.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IRPF activity-kind token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("IRPF activity-kind token must be a string token")
        if token not in self.all_activity_kinds:
            raise RegistryValidationError(
                f"IRPF activity-kind token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def semantic_token(self, value: str) -> IrpfActivityKind:
        """Resolve a semantic token through the same authored vocabulary."""
        return self.require(value)


_ENTRIES_POLICY = StringMappingPolicy(
    subject="IRPF activity-kind catalogue", value_whitespace=MappingValueWhitespace.STRIP
)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_irpf_activity_kind_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfActivityKindCatalogue:
    """Resolve activity-kind membership from the M036 selector catalogue."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    selectors_by_token: dict[IrpfActivityKind, list[str]] = {}
    for key, raw_value in entries.items():
        if not key.startswith(_SELECTOR_PREFIX) or not key.endswith(_ACTIVITY_KIND_SUFFIX):
            continue
        selector_id = key[len(_SELECTOR_PREFIX) : -len(_ACTIVITY_KIND_SUFFIX)]
        if not selector_id or not raw_value:
            raise RegistryValidationError(f"IRPF activity-kind catalogue has an invalid selector key {key!r}")
        token = IrpfActivityKind.from_registry(raw_value)
        selectors_by_token.setdefault(token, []).append(selector_id)
    if not selectors_by_token:
        raise RegistryValidationError("IRPF activity-kind catalogue declares no activity-kind selectors")
    definitions = tuple(
        IrpfActivityKindDefinition(token=token, selector_fact_ids=tuple(sorted(selector_ids)))
        for token, selector_ids in sorted(selectors_by_token.items(), key=lambda item: str(item[0]))
    )
    return IrpfActivityKindCatalogue(definitions=definitions)


def require_irpf_activity_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfActivityKind:
    """Return an activity-kind token only when fact 0082 declares it."""
    return resolve_irpf_activity_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def irpf_activity_kind_profesional_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfActivityKind:
    """Return the registry-declared professional activity-kind token."""
    return resolve_irpf_activity_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).semantic_token("profesional")


def irpf_activity_kind_sectorial_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfActivityKind:
    """Return the registry-declared sectorial activity-kind token."""
    return resolve_irpf_activity_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).semantic_token("sectorial")


def is_irpf_activity_kind_profesional(
    value: IrpfActivityKind | str | None,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return whether a value is the registry-declared professional token."""
    if value is None or value == "":
        return False
    return require_irpf_activity_kind(value, effective_date=effective_date, authority=authority) == (
        irpf_activity_kind_profesional_token(effective_date=effective_date, authority=authority)
    )


def is_irpf_activity_kind_sectorial(
    value: IrpfActivityKind | str | None,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return whether a value is the registry-declared sectorial token."""
    if value is None or value == "":
        return False
    return require_irpf_activity_kind(value, effective_date=effective_date, authority=authority) == (
        irpf_activity_kind_sectorial_token(effective_date=effective_date, authority=authority)
    )


__all__ = [
    "IrpfActivityKindCatalogue",
    "IrpfActivityKindDefinition",
    "irpf_activity_kind_profesional_token",
    "irpf_activity_kind_sectorial_token",
    "is_irpf_activity_kind_profesional",
    "is_irpf_activity_kind_sectorial",
    "require_irpf_activity_kind",
    "resolve_irpf_activity_kind_catalogue",
]

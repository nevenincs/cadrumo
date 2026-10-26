"""Resolve the dated first-slice expense routing declaration.

The registry owns the category selectors, model coordinates, and target
casillas.  This module provides only the generic query and typed projection
boundary; callers supply the category enum and casilla validator so no legal
or revision-specific fallback is retained here.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from datetime import date
from enum import Enum
from typing import Protocol, cast

from ...core.casilla_id import CasillaId
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..calculations.registry.schema_base import DateAxis


def _category_name(member: object) -> str:
    if isinstance(member, Enum):
        return member.name
    return str(member).upper()


def _require_category_type[CategoryT](member: object, category_type: type[CategoryT]) -> CategoryT:
    if not isinstance(member, category_type):
        raise TypeError("first-slice routing category member has an unexpected type")
    return member


class _SelectedRevision(Protocol):
    id: object


def resolve_first_slice_expense_routing[CategoryT](
    *,
    category_type: type[CategoryT],
    casilla_factory: Callable[[object], CasillaId],
    model_code: str,
    fact_id: str,
    effective_date: date,
    authority: GovernedFactSource | None = None,
    category_tokens: Callable[[GovernedFactSource, date], Collection[CategoryT]] | None = None,
) -> dict[CategoryT, CasillaId]:
    """Resolve one dated routing map from the selected registry authority.

    The model scope and the mapping fact share the caller's effective date so
    a revision-specific declaration cannot be paired with a different model
    revision. The mapping's metadata and every selector are checked before a
    target is admitted into the typed domain projection.
    """
    normalized_model_code = _validate_routing_request(model_code, effective_date, category_type)
    selected_authority = require_governed_fact_authority(authority, subject="first-slice routing")
    members_by_name = _routing_members_by_name(
        category_type,
        selected_authority,
        effective_date,
        category_tokens,
    )
    expected = set(members_by_name.values())
    selected_revision = _selected_model_revision(selected_authority, normalized_model_code, effective_date)
    resolved = _resolve_routing_fact(selected_authority, fact_id, effective_date)
    metadata, routing = _materialize_routing_entries(resolved, members_by_name, casilla_factory)
    _validate_routing_metadata(metadata, normalized_model_code, selected_revision)
    _validate_routing_coverage(expected, routing)
    return routing


def _validate_routing_request[CategoryT](
    model_code: str,
    effective_date: date,
    category_type: type[CategoryT],
) -> str:
    if not isinstance(model_code, str) or not model_code.strip():
        raise RegistryValidationError("first-slice routing requires a non-empty modelo code")
    if not isinstance(effective_date, date):
        raise TypeError("first-slice routing requires a calendar effective date")
    if not isinstance(category_type, type):
        raise TypeError("first-slice routing requires a category token type")
    return model_code.strip()


def _routing_members_by_name[CategoryT](
    category_type: type[CategoryT],
    authority: GovernedFactSource,
    effective_date: date,
    category_tokens: Callable[[GovernedFactSource, date], Collection[CategoryT]] | None,
) -> dict[str, CategoryT]:
    if issubclass(category_type, Enum):
        enum_members = _enum_members_by_name(cast(type[Enum], category_type))
        return {
            name: cast(CategoryT, _require_category_type(member, category_type))
            for name, member in enum_members.items()
        }
    if category_tokens is None:
        raise TypeError("non-Enum first-slice routing requires a registry category projection")
    projected = tuple(category_tokens(authority, effective_date))
    members_by_name = {_category_name(member): member for member in projected}
    if len(members_by_name) != len(projected):
        raise TypeError("first-slice routing category projection contains duplicate member names")
    return members_by_name


def _enum_members_by_name(category_type: type[Enum]) -> dict[str, Enum]:
    enum_members: dict[str, Enum] = {}
    for member in category_type:
        enum_members[member.name] = member
    return enum_members


def _selected_model_revision(
    authority: GovernedFactSource,
    model_code: str,
    effective_date: date,
) -> _SelectedRevision:
    revision_for_context = getattr(authority, "revision_for_context", None)
    if revision_for_context is None:
        raise RegistryValidationError(
            "first-slice routing requires a generation-pinned authority operation for model selection",
        )
    return cast(
        _SelectedRevision,
        revision_for_context(
            model_code,
            filing_year=effective_date.year,
            period="0A",
            on=effective_date,
        ),
    )


def _resolve_routing_fact(
    authority: GovernedFactSource,
    fact_id: str,
    effective_date: date,
) -> ResolvedMappingFact:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("first-slice routing declaration must resolve as a mapping fact")
    return resolved


def _materialize_routing_entries[CategoryT](
    resolved: ResolvedMappingFact,
    members_by_name: Mapping[str, CategoryT],
    casilla_factory: Callable[[object], CasillaId],
) -> tuple[dict[str, str], dict[CategoryT, CasillaId]]:
    metadata: dict[str, str] = {}
    routing: dict[CategoryT, CasillaId] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("first-slice routing entries must be string-to-string")
        if not _record_routing_metadata(entry.key, entry.value, metadata):
            _record_routing_selector(
                entry.key.partition(".")[2], entry.value, members_by_name, casilla_factory, routing
            )
    return metadata, routing


def _record_routing_metadata(key: str, value: str, metadata: dict[str, str]) -> bool:
    prefix, separator, _ = key.partition(".")
    if separator == "." and prefix == "selector":
        return False
    if key not in {"modelo", "revision", "applicability.source", "source_kind"}:
        raise RegistryValidationError(f"first-slice routing contains unknown declaration key {key!r}")
    if key in metadata:
        raise RegistryValidationError(f"first-slice routing repeats declaration key {key!r}")
    metadata[key] = value
    return True


def _record_routing_selector[CategoryT](
    member_name: str,
    value: str,
    members_by_name: Mapping[str, CategoryT],
    casilla_factory: Callable[[object], CasillaId],
    routing: dict[CategoryT, CasillaId],
) -> None:
    try:
        category = members_by_name[member_name]
    except KeyError as exc:
        raise RegistryValidationError(
            f"registry routing names unknown category member {member_name!r}",
        ) from exc
    if category in routing:
        raise RegistryValidationError(f"registry routing repeats category member {member_name!r}")
    try:
        routing[category] = casilla_factory(value)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError(
            f"registry routing target for category {member_name!r} is invalid",
        ) from exc


def _validate_routing_metadata(
    metadata: dict[str, str],
    model_code: str,
    selected_revision: _SelectedRevision,
) -> None:
    required_metadata = {"modelo", "revision", "applicability.source", "source_kind"}
    missing_metadata = sorted(required_metadata - metadata.keys())
    if missing_metadata:
        raise RegistryValidationError(f"first-slice routing is missing metadata {missing_metadata!r}")
    if metadata["modelo"] != model_code:
        raise RegistryValidationError(
            f"first-slice routing declares modelo {metadata['modelo']!r}, expected {model_code!r}",
        )
    if metadata["revision"] != str(selected_revision.id):
        raise RegistryValidationError(
            f"first-slice routing declares revision {metadata['revision']!r}, expected {selected_revision.id!r}",
        )
    if metadata["applicability.source"] != f"selected_modelo_{model_code}_revision":
        raise RegistryValidationError("first-slice routing declares an unsupported applicability source")
    if metadata["source_kind"] != "first_slice_expense_routing":
        raise RegistryValidationError("first-slice routing declares an unsupported source kind")


def _validate_routing_coverage[CategoryT](expected: set[CategoryT], routing: Mapping[CategoryT, CasillaId]) -> None:
    if set(routing) == expected:
        return
    missing = sorted(_category_name(member) for member in expected - set(routing))
    extra = sorted(_category_name(member) for member in set(routing) - expected)
    raise RegistryValidationError(f"registry routing coverage mismatch; missing={missing!r}, extra={extra!r}")


__all__ = ["resolve_first_slice_expense_routing"]

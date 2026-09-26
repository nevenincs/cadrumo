"""Resolve the dated first-slice expense routing declaration.

The registry owns the category selectors, model coordinates, and target
casillas.  This module provides only the generic query and typed projection
boundary; callers supply the category enum and casilla validator so no legal
or revision-specific fallback is retained here.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import date
from enum import Enum

from ...core.casilla_id import CasillaId
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.schema_base import DateAxis


def _category_name(member: object) -> str:
    if isinstance(member, Enum):
        return member.name
    return str(member).upper()


def _require_category_type[CategoryT](member: object, category_type: type[CategoryT]) -> CategoryT:
    if not isinstance(member, category_type):
        raise TypeError("first-slice routing category member has an unexpected type")
    return member


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
    if not isinstance(model_code, str) or not model_code.strip():
        raise RegistryValidationError("first-slice routing requires a non-empty modelo code")
    if not isinstance(effective_date, date):
        raise TypeError("first-slice routing requires a calendar effective date")
    if not isinstance(category_type, type):
        raise TypeError("first-slice routing requires a category token type")

    normalized_model_code = model_code.strip()
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError(
            "first-slice routing requires an explicit authority operation or scope",
        )
    typed_category_type: type[CategoryT] = category_type
    members_by_name: dict[str, CategoryT]
    if issubclass(category_type, Enum):
        enum_members: dict[str, object] = {}
        for member in category_type:
            enum_members[member.name] = member
        members_by_name = {
            name: _require_category_type(member, typed_category_type) for name, member in enum_members.items()
        }
    else:
        if category_tokens is None:
            raise TypeError("non-Enum first-slice routing requires a registry category projection")
        projected = tuple(category_tokens(selected_authority, effective_date))
        members_by_name = {_category_name(member): member for member in projected}
        if len(members_by_name) != len(projected):
            raise TypeError("first-slice routing category projection contains duplicate member names")
    expected = set(members_by_name.values())
    revision_for_context = getattr(selected_authority, "revision_for_context", None)
    if revision_for_context is None:
        raise RegistryValidationError(
            "first-slice routing requires a generation-pinned authority operation for model selection",
        )
    selected_revision = revision_for_context(
        normalized_model_code,
        filing_year=effective_date.year,
        period="0A",
        on=effective_date,
    )

    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("first-slice routing declaration must resolve as a mapping fact")

    metadata: dict[str, str] = {}
    routing: dict[CategoryT, CasillaId] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("first-slice routing entries must be string-to-string")
        prefix, separator, member_name = entry.key.partition(".")
        if separator != "." or prefix != "selector":
            if entry.key not in {"modelo", "revision", "applicability.source", "source_kind"}:
                raise RegistryValidationError(f"first-slice routing contains unknown declaration key {entry.key!r}")
            if entry.key in metadata:
                raise RegistryValidationError(f"first-slice routing repeats declaration key {entry.key!r}")
            metadata[entry.key] = entry.value
            continue
        try:
            category = members_by_name[member_name]
        except KeyError as exc:
            raise RegistryValidationError(
                f"registry routing names unknown category member {member_name!r}",
            ) from exc
        if category in routing:
            raise RegistryValidationError(f"registry routing repeats category member {member_name!r}")
        try:
            routing[category] = casilla_factory(entry.value)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"registry routing target for category {member_name!r} is invalid",
            ) from exc

    required_metadata = {"modelo", "revision", "applicability.source", "source_kind"}
    missing_metadata = sorted(required_metadata - metadata.keys())
    if missing_metadata:
        raise RegistryValidationError(f"first-slice routing is missing metadata {missing_metadata!r}")
    if metadata["modelo"] != normalized_model_code:
        raise RegistryValidationError(
            f"first-slice routing declares modelo {metadata['modelo']!r}, expected {normalized_model_code!r}",
        )
    if metadata["revision"] != str(selected_revision.id):
        raise RegistryValidationError(
            f"first-slice routing declares revision {metadata['revision']!r}, expected {selected_revision.id!r}",
        )
    if metadata["applicability.source"] != f"selected_modelo_{normalized_model_code}_revision":
        raise RegistryValidationError("first-slice routing declares an unsupported applicability source")
    if metadata["source_kind"] != "first_slice_expense_routing":
        raise RegistryValidationError("first-slice routing declares an unsupported source kind")

    if set(routing) != expected:
        missing = sorted(_category_name(member) for member in expected - set(routing))
        extra = sorted(_category_name(member) for member in set(routing) - expected)
        raise RegistryValidationError(f"registry routing coverage mismatch; missing={missing!r}, extra={extra!r}")
    return routing


__all__ = ["resolve_first_slice_expense_routing"]

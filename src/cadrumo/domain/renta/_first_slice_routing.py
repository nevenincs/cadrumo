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
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority


def resolve_first_slice_expense_routing[CategoryT](
    *,
    category_type: type[CategoryT],
    casilla_factory: Callable[[object], CasillaId],
    model_code: str,
    fact_id: str,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
    category_tokens: Callable[[ValidatedRegistryAuthority, date], Collection[CategoryT]] | None = None,
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
    selected_authority = authority if authority is not None else bundled_authority()
    if issubclass(category_type, Enum):
        members_by_name = {member.name: member for member in category_type}
        expected = set(category_type)
    else:
        if category_tokens is None:
            raise TypeError("non-Enum first-slice routing requires a registry category projection")
        projected = tuple(category_tokens(selected_authority, effective_date))
        members_by_name = {str(member.value).upper(): member for member in projected}
        if len(members_by_name) != len(projected):
            raise TypeError("first-slice routing category projection contains duplicate member names")
        expected = set(projected)
    query_service = RegistryQueryService(selected_authority)
    model_report = query_service.describe_modelo_for_scope(
        normalized_model_code,
        filing_year=effective_date.year,
        period="0A",
        as_of=effective_date,
    )
    if model_report.code != normalized_model_code:
        raise RegistryValidationError(
            f"first-slice routing resolved modelo {model_report.code!r}, expected {normalized_model_code!r}",
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
    if metadata["modelo"] != model_report.code:
        raise RegistryValidationError(
            f"first-slice routing declares modelo {metadata['modelo']!r}, expected {model_report.code!r}",
        )
    if metadata["revision"] != model_report.revision:
        raise RegistryValidationError(
            f"first-slice routing declares revision {metadata['revision']!r}, expected {model_report.revision!r}",
        )
    if metadata["applicability.source"] != f"selected_modelo_{normalized_model_code}_revision":
        raise RegistryValidationError("first-slice routing declares an unsupported applicability source")
    if metadata["source_kind"] != "first_slice_expense_routing":
        raise RegistryValidationError("first-slice routing declares an unsupported source kind")

    if set(routing) != expected:
        missing = sorted(getattr(member, "name", member.value) for member in expected - set(routing))
        extra = sorted(getattr(member, "name", member.value) for member in set(routing) - expected)
        raise RegistryValidationError(f"registry routing coverage mismatch; missing={missing!r}, extra={extra!r}")
    return routing


__all__ = ["resolve_first_slice_expense_routing"]

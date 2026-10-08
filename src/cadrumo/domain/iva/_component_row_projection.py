"""Private category and row projection for the IVA component registry."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...core.type_guards import is_object_list, is_str_keyed_dict
from ..calculations.registry.iva_category_catalogue import IvaCategoryCatalogue, resolve_iva_category_catalogue
from ._component_fact_projection import (
    CATEGORY_PROJECTION_NAMES,
    component_vocabulary_from_entries,
    cuota_settlement_catalogue_from_entries,
    ordered_component_rows,
    resolve_component_catalogue_entries,
)
from .classification import InvoiceKind
from .errors import IvaValidationError
from .schema import IvaCategory

if TYPE_CHECKING:
    from ..calculations.registry.governed_fact_scope import GovernedFactSource
    from .components import (
        CategoryProjectionName,
        ComponentCatalogue,
        IvaCategoryComponents,
        IvaComponentVocabulary,
        IvaCuotaSettlementCatalogue,
    )


def category_projection_from_entries(
    entries: Mapping[str, str],
    projection: CategoryProjectionName,
    category_catalogue: IvaCategoryCatalogue,
) -> frozenset[IvaCategory]:
    """Project one explicit category membership mapping from fact 0084."""
    if projection not in CATEGORY_PROJECTION_NAMES:
        raise IvaValidationError(f"unknown IVA category projection {projection!r}")
    members = _category_projection_members(entries, projection, category_catalogue)
    declared_categories = _declared_component_categories(entries)
    undeclared = sorted(member.value for member in members if member.value not in declared_categories)
    if undeclared:
        raise IvaValidationError(
            f"IVA category projection {projection!r} names categories without component rows: {undeclared!r}",
        )
    return members


def _category_projection_members(
    entries: Mapping[str, str],
    projection: CategoryProjectionName,
    category_catalogue: IvaCategoryCatalogue,
) -> frozenset[IvaCategory]:
    raw_members = entries.get(f"category_projection.{projection}")
    if raw_members is None or not raw_members.strip():
        raise IvaValidationError(
            f"IVA component catalogue is missing category projection {projection!r}",
        )
    member_values = tuple(token.strip() for token in raw_members.split(","))
    if any(not token for token in member_values):
        raise IvaValidationError(f"IVA category projection {projection!r} contains an empty member")
    if len(set(member_values)) != len(member_values):
        raise IvaValidationError(f"IVA category projection {projection!r} contains duplicate members")
    try:
        members = frozenset(category_catalogue.require(token) for token in member_values)
    except ValueError as exc:
        raise IvaValidationError(
            f"IVA category projection {projection!r} contains an unknown category",
        ) from exc
    return members


def _declared_component_categories(entries: Mapping[str, str]) -> set[str]:
    declared_categories: set[str] = set()
    for row_key in ordered_component_rows(entries):
        category_text, separator, kind_text = row_key.partition("|")
        if not separator or not category_text or not kind_text:
            raise IvaValidationError(f"invalid IVA component catalogue row key {row_key!r}")
        declared_categories.add(category_text)
    return declared_categories


def project_component_catalogue(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> ComponentCatalogue:
    """Project the selected registry mapping fact into typed component rows."""
    entries = resolve_component_catalogue_entries(effective_date=effective_date, authority=authority)
    category_catalogue = resolve_iva_category_catalogue(effective_date=effective_date, authority=authority)
    ordered_keys = ordered_component_rows(entries)
    component_vocabulary = component_vocabulary_from_entries(entries)
    cuota_settlement_catalogue = cuota_settlement_catalogue_from_entries(entries)

    # Keep the conversion helper as the narrow mechanical boundary. The helper
    # is imported lazily because it imports this module for the row model.
    from ._component_rows import component_row_from_registry

    projected: dict[tuple[IvaCategory, InvoiceKind], IvaCategoryComponents] = {}
    for row_key in ordered_keys:
        category, kind = _component_row_identity(row_key, category_catalogue)
        row = _project_component_row(
            row_key,
            category=category,
            kind=kind,
            entries=entries,
            component_vocabulary=component_vocabulary,
            cuota_settlement_catalogue=cuota_settlement_catalogue,
            component_row_from_registry=component_row_from_registry,
        )
        projected[(category, kind)] = row
    return MappingProxyType(projected)


def _component_row_identity(
    row_key: str,
    category_catalogue: IvaCategoryCatalogue,
) -> tuple[IvaCategory, InvoiceKind]:
    category_text, separator, kind_text = row_key.partition("|")
    if not separator or not category_text or not kind_text:
        raise IvaValidationError(f"invalid IVA component catalogue row key {row_key!r}")
    try:
        category = category_catalogue.require(category_text)
        kind = InvoiceKind(kind_text)
    except ValueError as exc:
        raise IvaValidationError(f"unknown IVA component catalogue row key {row_key!r}") from exc
    return category, kind


def _project_component_row(
    row_key: str,
    *,
    category: IvaCategory,
    kind: InvoiceKind,
    entries: Mapping[str, str],
    component_vocabulary: IvaComponentVocabulary,
    cuota_settlement_catalogue: IvaCuotaSettlementCatalogue,
    component_row_from_registry: Callable[..., IvaCategoryComponents],
) -> IvaCategoryComponents:
    decoded = _decode_component_row(entries, row_key)
    decoded["category"] = category
    decoded["kind"] = kind
    _normalise_component_grounding(row_key, decoded)
    _normalise_component_references(row_key, decoded)
    _normalise_component_vocabulary(decoded, component_vocabulary, cuota_settlement_catalogue)
    row = component_row_from_registry(
        decoded,
        cuota_settlement_no_token=cuota_settlement_catalogue.no_settlement_token,
        component_vocabulary=component_vocabulary,
    )
    if row.category != category or row.kind is not kind:
        raise IvaValidationError(
            f"IVA component row {row_key!r} disagrees with its catalogue key",
        )
    return row


def _decode_component_row(entries: Mapping[str, str], row_key: str) -> dict[str, object]:
    raw_row = entries.get(f"row.{row_key}")
    if raw_row is None:
        raise IvaValidationError(f"IVA component mapping is missing row {row_key!r}")
    try:
        decoded: object = json.loads(raw_row)
    except json.JSONDecodeError as exc:
        raise IvaValidationError(f"IVA component row {row_key!r} is not valid JSON") from exc
    if not is_str_keyed_dict(decoded):
        raise IvaValidationError(f"IVA component row {row_key!r} must decode as an object")
    if "cuota_settlement" not in decoded:
        raise IvaValidationError(f"IVA component row {row_key!r} is missing cuota settlement")
    row = dict(decoded)
    row.pop("label", None)
    row.pop("fact_ids", None)
    return row


def _normalise_component_grounding(row_key: str, decoded: dict[str, object]) -> None:
    from .components import IvaGroundingConfidence

    for grounding_field in ("cuota_grounding", "recargo_grounding", "retencion_grounding"):
        raw_grounding = decoded.get(grounding_field)
        try:
            decoded[grounding_field] = IvaGroundingConfidence(raw_grounding)
        except (TypeError, ValueError) as exc:
            raise IvaValidationError(
                f"IVA component row {row_key!r} has invalid {grounding_field}",
            ) from exc


def _normalise_component_references(row_key: str, decoded: dict[str, object]) -> None:
    for reference_field in ("legal_refs", "pending_legal_refs"):
        raw_references = decoded.get(reference_field, ())
        if not is_object_list(raw_references) or any(not isinstance(item, str) for item in raw_references):
            raise IvaValidationError(
                f"IVA component row {row_key!r} has invalid {reference_field}",
            )
        decoded[reference_field] = tuple(raw_references)


def _normalise_component_vocabulary(
    decoded: dict[str, object],
    component_vocabulary: IvaComponentVocabulary,
    cuota_settlement_catalogue: IvaCuotaSettlementCatalogue,
) -> None:
    decoded["applicability"] = component_vocabulary.require_kind_applicability(decoded["applicability"])
    decoded["retencion_role"] = component_vocabulary.require_retencion_role(decoded["retencion_role"])
    decoded["base"] = component_vocabulary.require_component_presence(decoded["base"])
    decoded["cuota"] = component_vocabulary.require_component_presence(decoded["cuota"])
    decoded["recargo"] = component_vocabulary.require_component_presence(decoded["recargo"])
    decoded["retencion"] = component_vocabulary.require_retencion_expectation(decoded["retencion"])
    decoded["cuota_settlement"] = cuota_settlement_catalogue.require(decoded["cuota_settlement"])

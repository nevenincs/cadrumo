"""Typed shape and normalization boundary for ledger IRPF category tokens."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from .enums import TransactionDirection


@dataclass(frozen=True, slots=True)
class LedgerIrpfCategoryDescriptor:
    """One registry-projected category descriptor."""

    id: str
    purpose: str
    directions: tuple[TransactionDirection, ...]
    net_paid: bool
    related_ids: tuple[str, ...]


def _registry_taxonomy_declarations() -> Mapping[str, str]:
    """Resolve the dated IRPF ledger category taxonomy."""
    authority = bundled_authority()
    model_report = RegistryQueryService(authority).describe_modelo("100")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="irpf-ledger-category-taxonomy",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError("IRPF ledger category taxonomy must resolve as a mapping fact")
    del model_report
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _required_taxonomy_declaration(declarations: Mapping[str, str], key: str) -> str:
    try:
        return declarations[key]
    except KeyError as exc:
        raise ValueError(f"IRPF ledger taxonomy declaration is missing: {key}") from exc


def _split_declaration(declarations: Mapping[str, str], key: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in _required_taxonomy_declaration(declarations, key).split(",") if value.strip())


def _descriptor_from_registry(category_id: str, declarations: Mapping[str, str]) -> LedgerIrpfCategoryDescriptor:
    prefix = f"category.{category_id}"
    directions = tuple(TransactionDirection(value) for value in _split_declaration(declarations, f"{prefix}.directions"))
    net_paid_field = "_".join(("net", "paid", "invoice"))
    related_field = "_".join(("related", "category", "ids"))
    net_paid = _required_taxonomy_declaration(declarations, f"{prefix}.{net_paid_field}")
    if net_paid not in {"true", "false"}:
        raise ValueError(f"invalid IRPF net-paid declaration: {net_paid}")
    return LedgerIrpfCategoryDescriptor(
        id=category_id,
        purpose=_required_taxonomy_declaration(declarations, f"{prefix}.purpose"),
        directions=directions,
        net_paid=net_paid == "true",
        related_ids=_split_declaration(declarations, f"{prefix}.{related_field}"),
    )


def ledger_irpf_category_catalogue() -> tuple[LedgerIrpfCategoryDescriptor, ...]:
    """Return the dated registry-projected IRPF category descriptors."""
    declarations = _registry_taxonomy_declarations()
    return tuple(
        _descriptor_from_registry(category_id, declarations)
        for category_id in _split_declaration(declarations, "catalogue.ids")
    )


def normalize_irpf_category(value: str | None) -> str | None:
    """Normalize a raw category token without resolving registry meaning."""
    if value is None:
        return None
    return value.strip().casefold() or None


def ledger_irpf_category(
    value: str | None,
    *,
    direction: TransactionDirection | None = None,
) -> LedgerIrpfCategoryDescriptor | None:
    """Resolve a normalized token through the registry-owned taxonomy."""
    normalized = normalize_irpf_category(value)
    if normalized is None:
        return None
    declarations = _registry_taxonomy_declarations()
    descriptors = {
        descriptor.id: descriptor
        for descriptor in (
            _descriptor_from_registry(category_id, declarations)
            for category_id in _split_declaration(declarations, "catalogue.ids")
        )
    }
    descriptor = descriptors.get(normalized)
    if descriptor is None or (direction is not None and direction not in descriptor.directions):
        return None
    return descriptor


def has_non_work_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Resolve the registry-owned non-employment predicate."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and not descriptor.purpose.endswith("_income")


def has_activity_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Resolve the registry-owned activity-income predicate."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose.endswith("_income_withholding")


def has_rent_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Resolve the registry-owned rental predicate."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose.endswith("_expense_withholding")


def has_employment_irpf_category(value: str | None, *, direction: TransactionDirection) -> bool:
    """Resolve the registry-owned employment predicate."""
    descriptor = ledger_irpf_category(value, direction=direction)
    return descriptor is not None and descriptor.purpose.endswith("_income")


def is_net_paid_related_category(value: str | None) -> bool:
    """Return whether a spending token is a registry-declared net-paid relation."""
    if value is None:
        return False
    token = value.strip().casefold()
    return any(
        descriptor.net_paid and token in descriptor.related_ids
        for descriptor in ledger_irpf_category_catalogue()
    )

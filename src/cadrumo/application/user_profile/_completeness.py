"""Conditional completeness rules for profile-level filing readiness."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ...domain.deadlines import EntityType, FiscalResidency, IrpfIncomeCategory, irnr_representante_fiscal_required

if TYPE_CHECKING:
    from ...domain.user_profile import ProfileSchemaDefinition

FISCAL_RESIDENCY_PATH = "taxpayer_type.fiscal_residency"
COUNTRY_OF_FISCAL_RESIDENCE_PATH = "taxpayer_type.country_of_fiscal_residence"
REPRESENTANTE_FISCAL_NIF_PATH = "taxpayer_type.representante_fiscal_nif"
REPRESENTANTE_FISCAL_NOMBRE_PATH = "taxpayer_type.representante_fiscal_nombre"
ENTITY_TYPE_PATH = "taxpayer_type.entity_type"
IRPF_INCOME_CATEGORIES_PATH = "taxpayer_type.irpf_income_categories"
IVA_REGIME_PATH = "iva.regime"


def conditional_profile_required_paths(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return profile paths conditionally required by declared taxpayer facts.

    Static schema-required fields are handled by the schema validator and the
    compiled profile-key registry. This helper owns cross-field completeness:
    IRNR non-residents must declare their fiscal residence country, and
    non-EU/EEA IRNR residents must also declare both fiscal representative
    fields before any filing/modelo work can treat the profile as ready.
    """
    if _token(values.get(FISCAL_RESIDENCY_PATH)).lower() != FiscalResidency.NON_RESIDENT_IRNR.value:
        return ()

    country = _token(values.get(COUNTRY_OF_FISCAL_RESIDENCE_PATH)).upper()
    if not country:
        return (COUNTRY_OF_FISCAL_RESIDENCE_PATH,)

    required = [COUNTRY_OF_FISCAL_RESIDENCE_PATH]
    if irnr_representante_fiscal_required(country):
        required.extend((REPRESENTANTE_FISCAL_NIF_PATH, REPRESENTANTE_FISCAL_NOMBRE_PATH))
    return tuple(required)


def conditional_profile_missing_required(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return conditionally required profile paths absent from ``values``."""
    return tuple(path for path in conditional_profile_required_paths(values) if not _has_value(values, path))


def iva_regime_required(values: Mapping[str, object]) -> bool:
    """Return whether the profile needs an explicit IVA regime fact.

    Legal entities and attribution entities keep the existing IVA-regime
    requirement. A natural-person profile only needs the IVA regime when
    it declares economic-activity income; a salaried-only, pensioner, or
    pure-landlord profile must not be forced into ``GENERAL`` just to pass
    profile persistence.
    """
    entity_type = _token(values.get(ENTITY_TYPE_PATH))
    if entity_type != EntityType.NATURAL_PERSON.value:
        return True
    categories = {
        token.strip() for token in _token(values.get(IRPF_INCOME_CATEGORIES_PATH)).split(",") if token.strip()
    }
    return IrpfIncomeCategory.ACTIVIDAD_ECONOMICA.value in categories


def missing_required_field_paths(
    schema: ProfileSchemaDefinition,
    values: Mapping[str, str],
) -> tuple[str, ...]:
    """Report which schema-required field paths a value mapping leaves unsatisfied.

    A repeatable section is validated PER ROW. Every row that exists must
    carry every required field of its section, and a section with no rows
    reports nothing - a taxpayer with no attribution entities is not
    incomplete for lacking one. Reading it per SECTION instead would demand
    at least one row of every repeatable section, which would make an
    ordinary profile permanently invalid.

    Row identity is the index segment (``socios.0.nif``). A repeatable fact
    written WITHOUT an index is treated as a single implicit row rather
    than ignored, because a producer currently writes one that way; that
    divergence is tracked on its own and this function deliberately does
    not prejudge it, it only avoids dropping the field from validation.

    Presence is value-bearing but NOT whitespace-stripped, matching the
    surfaces that consume this. Tightening it here would silently change
    what counts as a filled field.
    """
    present = {path for path, value in values.items() if value != ""}
    missing: list[str] = []
    for section in schema.sections:
        required = tuple(field.key for field in section.fields if field.required)
        if not required:
            continue
        if not section.repeatable:
            missing.extend(f"{section.key}.{key}" for key in required if f"{section.key}.{key}" not in present)
            continue
        for row, populated in _rows_of(section.key, present).items():
            prefix = f"{section.key}.{row}." if row else f"{section.key}."
            missing.extend(f"{prefix}{key}" for key in required if key not in populated)
    return tuple(missing)


def _rows_of(section_key: str, present: Iterable[str]) -> dict[str, set[str]]:
    """Group a section's populated paths by row, keying an unindexed path as one implicit row."""
    rows: dict[str, set[str]] = {}
    for path in present:
        head, _, tail = path.partition(".")
        if head != section_key or not tail:
            continue
        index, _, field = tail.partition(".")
        if field and index.isdigit():
            rows.setdefault(index, set()).add(field)
        elif not field:
            rows.setdefault("", set()).add(index)
    return rows


def _has_value(values: Mapping[str, object], path: str) -> bool:
    return bool(_token(values.get(path)))


def _token(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "COUNTRY_OF_FISCAL_RESIDENCE_PATH",
    "ENTITY_TYPE_PATH",
    "FISCAL_RESIDENCY_PATH",
    "IRPF_INCOME_CATEGORIES_PATH",
    "IVA_REGIME_PATH",
    "REPRESENTANTE_FISCAL_NIF_PATH",
    "REPRESENTANTE_FISCAL_NOMBRE_PATH",
    "conditional_profile_missing_required",
    "conditional_profile_required_paths",
    "iva_regime_required",
    "missing_required_field_paths",
]

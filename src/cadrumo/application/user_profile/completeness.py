"""Conditional completeness rules for profile-level filing readiness."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ...domain.deadlines.models import (
    EntityType,
    FiscalResidency,
    IrpfIncomeCategory,
    irnr_representante_fiscal_required,
)
from ...domain.deadlines.profiles import modelo_iva_profile_required_paths

if TYPE_CHECKING:
    from ...domain.user_profile.schema import ProfileSchemaDefinition, ProfileSectionDefinition

FISCAL_RESIDENCY_PATH = "taxpayer_type.fiscal_residency"
COUNTRY_OF_FISCAL_RESIDENCE_PATH = "taxpayer_type.country_of_fiscal_residence"
REPRESENTANTE_FISCAL_NIF_PATH = "taxpayer_type.representante_fiscal_nif"
REPRESENTANTE_FISCAL_NOMBRE_PATH = "taxpayer_type.representante_fiscal_nombre"
ENTITY_TYPE_PATH = "taxpayer_type.entity_type"
LEGAL_ENTITY_FORM_PATH = "taxpayer_type.legal_entity_form"
LEGAL_NAME_PATH = "identity.legal_name"
IRPF_INCOME_CATEGORIES_PATH = "taxpayer_type.irpf_income_categories"
IVA_REGIME_PATH = "iva.regime"
AUTH_PROVIDER_PATH = "auth.provider"
CLAVE_MOVIL_ROUTE_PATH = "auth.clave_movil_route"
CLAVE_MOVIL_PROVIDER = "clave_movil"

ATRIBUCION_SOCIOS_SECTION = "attribution_entity_socios"
PARTICIPE_CLAVE_FIELD = "participe_clave"
SOCIO_COUNTRY_FIELD = "country_of_residence"
#: The one clave whose Modelo 184 record carries a country at positions 79-80.
#:
#: The other two claves -- residente, and no residente CON establecimiento
#: permanente -- require BLANCOS there, so the country is not merely optional
#: for them: the layout prohibits it. Both directions are enforced, because a
#: rule that only asks for the value when it is due leaves the prohibited case
#: to whatever the operator typed.
PARTICIPE_CLAVE_BEARING_COUNTRY = "2"


def conditional_profile_required_paths(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return profile paths conditionally required by declared taxpayer facts.

    Static schema-required fields are handled by the schema validator and the
    compiled profile-key registry. This helper owns cross-field completeness:
    IRNR non-residents must declare their fiscal residence country, and
    non-EU/EEA IRNR residents must also declare both fiscal representative
    fields before any filing/modelo work can treat the profile as ready.

    A profile declaring any Modelo IVA fact owes the rest of that block. The
    paths it owes are answered by the domain resolver that refuses without
    them rather than restated here, because restating them is precisely how
    the two authorities came apart: the resolver hard-required six facts that
    no readiness surface asked for, so ``config profile status`` reported a
    profile ready and pointed the operator at a command that refused it.
    """
    required: list[str] = []
    if _token(values.get(AUTH_PROVIDER_PATH)).lower() == CLAVE_MOVIL_PROVIDER:
        required.append(CLAVE_MOVIL_ROUTE_PATH)

    required.extend(modelo_iva_profile_required_paths(values))

    if _token(values.get(ENTITY_TYPE_PATH)).lower() == EntityType.LEGAL_ENTITY.value:
        # A legal entity without a declared form has no selector for its
        # corporate tax rate schedule; the schema's `required` axis is
        # unconditional so the conditional requirement lives here.
        required.append(LEGAL_ENTITY_FORM_PATH)
        # And without a razon social there is no name to file under. The export
        # producer fills "Apellidos o Razon Social" with `surnames or
        # legal_name`, documenting the two as mutually exclusive by
        # construction -- so an entity carrying only surnames does not blank the
        # slot, it files the company under a natural person's surname. Nothing
        # enforced that exclusivity, which is what made the fallback wrong
        # rather than merely redundant.
        required.append(LEGAL_NAME_PATH)

    if _token(values.get(FISCAL_RESIDENCY_PATH)).lower() != FiscalResidency.NON_RESIDENT_IRNR.value:
        return tuple(required)

    country = _token(values.get(COUNTRY_OF_FISCAL_RESIDENCE_PATH)).upper()
    if not country:
        return (*required, COUNTRY_OF_FISCAL_RESIDENCE_PATH)

    required.append(COUNTRY_OF_FISCAL_RESIDENCE_PATH)
    if irnr_representante_fiscal_required(country):
        required.extend((REPRESENTANTE_FISCAL_NIF_PATH, REPRESENTANTE_FISCAL_NOMBRE_PATH))
    return tuple(required)


def conditional_profile_missing_required(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return conditionally required profile paths absent from ``values``."""
    return tuple(path for path in conditional_profile_required_paths(values) if not _has_value(values, path))


def _socio_row_indices(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return the declared attribution-socio row indices, in declaration order."""
    prefix = f"{ATRIBUCION_SOCIOS_SECTION}."
    seen: dict[str, None] = {}
    for path in values:
        if not path.startswith(prefix):
            continue
        index = path[len(prefix) :].split(".", 1)[0]
        if index.isdigit():
            seen.setdefault(index, None)
    return tuple(seen)


def atribucion_socio_missing_country_paths(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return socio country paths the clave requires but the profile omits.

    Modelo 184 fills positions 79-80 of the declarado record only for clave 2,
    so a socio declared a non-resident without a permanent establishment owes a
    country and one declared under any other clave does not.
    """
    missing: list[str] = []
    for index in _socio_row_indices(values):
        clave = _token(values.get(f"{ATRIBUCION_SOCIOS_SECTION}.{index}.{PARTICIPE_CLAVE_FIELD}"))
        if clave != PARTICIPE_CLAVE_BEARING_COUNTRY:
            continue
        path = f"{ATRIBUCION_SOCIOS_SECTION}.{index}.{SOCIO_COUNTRY_FIELD}"
        if not _has_value(values, path):
            missing.append(path)
    return tuple(missing)


def atribucion_socio_forbidden_country_paths(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return socio country paths carrying a value the record layout prohibits.

    The direction a conditional rule usually omits. Claves 1 and 3 require
    BLANCOS at positions 79-80, so a country stated under either is not a
    harmless extra fact: it is a value the layout forbids, and it was the shape
    a Spanish default produced on the majority case.

    A row that declares no clave yet is not judged here. The clave is a required
    field and its own absence is reported as such; refusing the country as well
    would report one unfinished row twice and name the wrong field second.
    """
    forbidden: list[str] = []
    for index in _socio_row_indices(values):
        clave = _token(values.get(f"{ATRIBUCION_SOCIOS_SECTION}.{index}.{PARTICIPE_CLAVE_FIELD}"))
        if not clave or clave == PARTICIPE_CLAVE_BEARING_COUNTRY:
            continue
        path = f"{ATRIBUCION_SOCIOS_SECTION}.{index}.{SOCIO_COUNTRY_FIELD}"
        if _has_value(values, path):
            forbidden.append(path)
    return tuple(forbidden)


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


def profile_value_is_present(value: object) -> bool:
    """Report whether ``value`` counts as a filled profile field.

    The single presence rule every readiness surface reads. It existed in
    two incompatible spellings before: the conditional rules below stripped
    before deciding, as did the profile-key authority behind the CLI status
    gate, while the schema-required reader and the overview it feeds tested
    only ``!= ""``. A required identity holding spaces was therefore
    complete to the surfaces that persist it and missing to the surface
    that refuses it -- a readiness fork rather than a rendering difference,
    because the two answers govern different decisions.

    Stripping is the direction that resolves it. A whitespace-only value
    survives no field-level parser in the system, so treating it as filled
    only defers the refusal to a later boundary that reports it as
    something other than an empty required field.
    """
    return bool(_token(value))


def missing_required_field_paths(
    schema: ProfileSchemaDefinition,
    values: Mapping[str, str],
) -> tuple[str, ...]:
    """Report which schema-required field paths a value mapping leaves unsatisfied.

    Presence is value-bearing, never fact-bearing, and is decided by the one
    shared :func:`profile_value_is_present` rule rather than restated here.
    """
    present = {path for path, value in values.items() if profile_value_is_present(value)}
    missing: list[str] = []
    for section in schema.sections:
        required = tuple(field.key for field in section.fields if field.required)
        if not required:
            continue
        missing.extend(_missing_in_section(section, required=required, present=present))
    return tuple(missing)


def _missing_in_section(
    section: ProfileSectionDefinition,
    *,
    required: tuple[str, ...],
    present: set[str],
) -> list[str]:
    """Report the required paths one section leaves unsatisfied.

    A repeatable section is validated PER ROW. Every row that exists must
    carry every required field of its section, and a section with no rows
    reports nothing — a taxpayer with no attribution entities is not
    incomplete for lacking one. Reading it per SECTION instead would demand
    at least one row of every repeatable section, which would make an
    ordinary profile permanently invalid.

    Row identity is :func:`profile_section_rows`, shared with the surface
    that renders those rows so the two cannot disagree about how many there
    are. The unindexed implicit row it keeps is a producer's current
    spelling; that divergence is tracked on its own and this deliberately
    does not prejudge it, it only avoids dropping the field from validation.
    """
    if not section.repeatable:
        return [f"{section.key}.{key}" for key in required if f"{section.key}.{key}" not in present]
    missing: list[str] = []
    for row, populated in profile_section_rows(section.key, present).items():
        prefix = f"{section.key}.{row}." if row else f"{section.key}."
        missing.extend(f"{prefix}{key}" for key in required if key not in populated)
    return missing


def profile_section_rows(section_key: str, present: Iterable[str]) -> dict[str, frozenset[str]]:
    """Group a section's populated paths by row, in the order a surface should show them.

    Row identity is the index segment (``socios.0.nif``). A repeatable fact
    written WITHOUT an index is treated as a single implicit row keyed ``""``
    rather than ignored, because a producer currently writes one that way.

    Shared rather than restated, because the surface that RENDERS a
    repeatable section and the check that decides which of its fields are
    missing must agree about how many rows there are and which one each fact
    belongs to. They did not: the display walked the unindexed path while
    rows live at ``section.INDEX.field``, so a taxpayer's socios, activities,
    properties and usage ratios were each shown as one permanently blank row
    however many the profile held.

    Ordering is the implicit row first, then indices in numeric order, so a
    row's position on screen follows its identity rather than the order facts
    happened to be written. Numeric rather than lexicographic, or row 10
    would sort between rows 1 and 2.

    Args:
        section_key: The section whose rows are wanted.
        present: Paths carrying a value, by the shared presence rule. A row
            whose every fact is blank is therefore not a row here — which is
            what keeps this reading identical for both callers.

    Returns:
        Each row's identity mapped to the field keys it populates.
    """
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
    ordered = sorted(rows, key=lambda row: (row != "", int(row) if row else 0))
    return {row: frozenset(rows[row]) for row in ordered}


def _has_value(values: Mapping[str, object], path: str) -> bool:
    return profile_value_is_present(values.get(path))


def _token(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "AUTH_PROVIDER_PATH",
    "CLAVE_MOVIL_PROVIDER",
    "CLAVE_MOVIL_ROUTE_PATH",
    "COUNTRY_OF_FISCAL_RESIDENCE_PATH",
    "ENTITY_TYPE_PATH",
    "FISCAL_RESIDENCY_PATH",
    "IRPF_INCOME_CATEGORIES_PATH",
    "IVA_REGIME_PATH",
    "PARTICIPE_CLAVE_BEARING_COUNTRY",
    "REPRESENTANTE_FISCAL_NIF_PATH",
    "REPRESENTANTE_FISCAL_NOMBRE_PATH",
    "atribucion_socio_forbidden_country_paths",
    "atribucion_socio_missing_country_paths",
    "conditional_profile_missing_required",
    "conditional_profile_required_paths",
    "iva_regime_required",
    "missing_required_field_paths",
    "profile_section_rows",
    "profile_value_is_present",
]

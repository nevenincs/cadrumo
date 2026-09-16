"""Authority adapters for the pure Spanish tax-identifier validation kernel."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Final

from pydantic import AfterValidator

from ....core.identity.documents import TAX_ID_FORMAT_CONTEXT, SpanishTaxIdFormat
from ....core.identity.tax_id import validate_spanish_tax_id
from .facts.resolution import MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from .facts.schema import GovernedFactCatalogue, GovernedFactFamily, MappingFactPayload
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

TAX_ID_FORMAT_FACT_ID: Final = "spanish-tax-identifier-format"


def _runtime_object(value: object) -> object:
    """Capture declarations before applying the runtime shape guard."""
    return value


def _declarations_from_payload(payload: MappingFactPayload) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for entry in payload.entries:
        key = entry.key
        value = entry.value
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} declarations must all be strings")
        declarations[key] = value
    return declarations


def tax_id_format_from_declarations(declarations: Mapping[str, str]) -> SpanishTaxIdFormat:
    """Build the typed format from a complete fact mapping, without defaults."""
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in ((_runtime_object(key), _runtime_object(value)) for key, value in declarations.items())
    ):
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} declarations must all be strings")
    required = {
        "tax_id.width",
        "tax_id.country_prefix",
        "tax_id.country_prefixed_width",
        "tax_id.country_prefix_strip_width",
        "tax_id.leaders.prefixed_nif",
        "tax_id.leaders.nie",
        "tax_id.leaders.cif",
        "tax_id.check.nif_letters",
        "tax_id.check.cif_digit_only_kinds",
        "tax_id.check.cif_letter_only_kinds",
        "tax_id.check.cif_letter_table",
    }
    nie_leaders = declarations.get("tax_id.leaders.nie")
    if not isinstance(nie_leaders, str):
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} declarations must all be strings")
    expected = required | {f"tax_id.check.nie_prefix.{leader}" for leader in nie_leaders}
    missing = sorted(expected - declarations.keys())
    if missing:
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} is missing declarations: {missing!r}")
    unknown = sorted(declarations.keys() - expected)
    if unknown:
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} has unknown declarations: {unknown!r}")
    try:
        width = int(declarations["tax_id.width"])
        prefixed_width = int(declarations["tax_id.country_prefixed_width"])
        strip_width = int(declarations["tax_id.country_prefix_strip_width"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} width declarations must be decimal integers") from exc
    prefix = "tax_id.check.nie_prefix."
    substitutions = tuple(
        sorted((key.removeprefix(prefix), value) for key, value in declarations.items() if key.startswith(prefix))
    )
    return SpanishTaxIdFormat(
        width=width,
        country_prefix=str(declarations["tax_id.country_prefix"]),
        country_prefixed_width=prefixed_width,
        country_prefix_strip_width=strip_width,
        prefixed_nif_leaders=str(declarations["tax_id.leaders.prefixed_nif"]),
        nie_leaders=str(declarations["tax_id.leaders.nie"]),
        cif_leaders=str(declarations["tax_id.leaders.cif"]),
        nif_letters=str(declarations["tax_id.check.nif_letters"]),
        nie_prefix_substitutions=substitutions,
        cif_digit_only_kinds=str(declarations["tax_id.check.cif_digit_only_kinds"]),
        cif_letter_only_kinds=str(declarations["tax_id.check.cif_letter_only_kinds"]),
        cif_letter_table=str(declarations["tax_id.check.cif_letter_table"]),
    )


def _format_from_resolved(resolved: ResolvedGovernedFact) -> SpanishTaxIdFormat:
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} did not resolve as a mapping")
    return tax_id_format_from_declarations(_declarations_from_payload(resolved.payload))


def tax_id_format_from_catalogue(catalogue: GovernedFactCatalogue) -> SpanishTaxIdFormat:
    """Derive one temporally invariant bootstrap format from a catalogue."""
    fact = catalogue.facts.get(TAX_ID_FORMAT_FACT_ID)
    if fact is None or fact.family is not GovernedFactFamily.MAPPING:
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} is missing or is not a mapping")
    formats: set[SpanishTaxIdFormat] = set()
    for variant in fact.variants:
        if not isinstance(variant.payload, MappingFactPayload):
            raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} contains a non-mapping variant")
        declarations = _declarations_from_payload(variant.payload)
        formats.add(tax_id_format_from_declarations(declarations))
    if len(formats) != 1:
        raise ValueError(f"{TAX_ID_FORMAT_FACT_ID} must declare one invariant bootstrap format")
    return formats.pop()


def tax_id_format(authority: GovernedFactSource, *, effective_date: date) -> SpanishTaxIdFormat:
    """Resolve the format from one explicitly supplied established authority."""
    return _format_from_resolved(
        authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=TAX_ID_FORMAT_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date
            )
        )
    )


def tax_id_format_value(
    key: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Resolve one declaration through the established runtime authority."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise ValueError("Spanish tax-ID format requires an explicit authority operation or scope")
    resolved = tax_id_format(selected_authority, effective_date=effective_date or date.today())
    values = {
        "tax_id.width": str(resolved.width),
        "tax_id.country_prefix": resolved.country_prefix,
        "tax_id.country_prefixed_width": str(resolved.country_prefixed_width),
        "tax_id.country_prefix_strip_width": str(resolved.country_prefix_strip_width),
        "tax_id.leaders.prefixed_nif": resolved.prefixed_nif_leaders,
        "tax_id.leaders.nie": resolved.nie_leaders,
        "tax_id.leaders.cif": resolved.cif_leaders,
        "tax_id.check.nif_letters": resolved.nif_letters,
        "tax_id.check.cif_digit_only_kinds": resolved.cif_digit_only_kinds,
        "tax_id.check.cif_letter_only_kinds": resolved.cif_letter_only_kinds,
        "tax_id.check.cif_letter_table": resolved.cif_letter_table,
        **{f"tax_id.check.nie_prefix.{leader}": value for leader, value in resolved.nie_prefix_substitutions},
    }
    try:
        return values[key]
    except KeyError as exc:
        raise ValueError(f"Spanish tax-ID format declaration is missing: {key}") from exc


def runtime_tax_id_format(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SpanishTaxIdFormat:
    """Resolve the format from the established authority operation or scope."""
    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise ValueError("Spanish tax-ID format requires an explicit authority operation or scope")
    return tax_id_format(selected_authority, effective_date=effective_date or date.today())


def _validate_subject_tax_id(value: str) -> str:
    """Validate an ordinary runtime subject against the established artifact."""
    return validate_spanish_tax_id(value, runtime_tax_id_format())


type SubjectTaxId = Annotated[str, AfterValidator(_validate_subject_tax_id)]
"""Canonical Spanish NIF/NIE/CIF validated by the established runtime authority."""


__all__ = [
    "TAX_ID_FORMAT_CONTEXT",
    "TAX_ID_FORMAT_FACT_ID",
    "SubjectTaxId",
    "runtime_tax_id_format",
    "tax_id_format",
    "tax_id_format_from_catalogue",
    "tax_id_format_from_declarations",
    "tax_id_format_value",
]

"""Registry-backed setup and wizard binding declarations.

The setup surface has several consumers which need the same answer-to-profile
coordinates: the core answer projector, deadline profile construction, the
Typer option surface, and page decoration.  They all resolve this small
catalogue through one mapping-fact seam so none of those consumers becomes a
second home for the declarations.

This module deliberately keeps resolution lazy.  Importing the core answer
model must remain possible before the bundled authority is initialised; a
consumer resolves the authored catalogue only when it actually projects or
renders a setup value.
"""

from __future__ import annotations

from datetime import date

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_references import LegalReferenceKind

_SETUP_FACT_ID = "-".join(
    (LegalReferenceKind.LEY.value, "49", "2002", "profile", "binding", "catalogue"),
)


def mapping_fact_entries(fact_id: str, *, authority: GovernedFactSource | None = None) -> dict[str, str]:
    """Resolve one string mapping fact and return its exact entries.

    The returned mapping is copied at the boundary; the authority remains the
    only source of the declarations and no Python fallback is retained when a
    required entry is absent.
    """
    from .schema_base import DateAxis

    selected_authority = authority or governed_facts_in_scope()
    if selected_authority is None:
        raise RegistryValidationError("setup mapping fact requires an explicit authority operation or scope")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError(f"{fact_id!r} must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError(f"{fact_id!r} must contain string mappings")
        if entry.key in entries:
            raise RegistryValidationError(f"{fact_id!r} contains duplicate key {entry.key!r}")
        entries[entry.key] = entry.value
    return entries


def setup_answer_declarations(
    *,
    authority: GovernedFactSource | None = None,
) -> dict[str, tuple[str, type[str] | type[bool], str | None]]:
    """Return answer-field profile bindings from the setup catalogue."""
    declarations: dict[str, tuple[str, type[str] | type[bool], str | None]] = {}
    prefix = "setup.field."
    for key, encoded in mapping_fact_entries(_SETUP_FACT_ID, authority=authority).items():
        if not key.startswith(prefix):
            continue
        parts = encoded.split("|", 2)
        if len(parts) != 3 or parts[1] not in {"str", "bool"}:
            raise RegistryValidationError(f"invalid setup answer declaration {key!r}")
        path, value_type, default_token = parts
        if not path:
            raise RegistryValidationError(f"setup answer declaration {key!r} has no profile path")
        declarations[key.removeprefix(prefix)] = (
            path,
            bool if value_type == "bool" else str,
            default_token or None,
        )
    if not declarations:
        raise RegistryValidationError("setup answer catalogue has no setup.field declarations")
    return declarations


def profile_field_bindings(*, authority: GovernedFactSource | None = None) -> dict[str, str]:
    """Return profile-field names and their canonical persisted paths."""
    prefix = "profile.field."
    return {
        key.removeprefix(prefix): value
        for key, value in mapping_fact_entries(_SETUP_FACT_ID, authority=authority).items()
        if key.startswith(prefix)
    }


def wizard_page_declarations(*, authority: GovernedFactSource | None = None) -> dict[str, dict[str, str]]:
    """Return page format/widget declarations keyed by page ID."""
    prefix = "wizard.page."
    pages: dict[str, dict[str, str]] = {}
    for key, value in mapping_fact_entries(_SETUP_FACT_ID, authority=authority).items():
        if not key.startswith(prefix):
            continue
        page_key, _, attribute = key.removeprefix(prefix).rpartition(".")
        if not page_key or attribute not in {"format_hint", "widget_kind"}:
            raise RegistryValidationError(f"invalid wizard page declaration {key!r}")
        pages.setdefault(page_key, {})[attribute] = value
    return pages


def wizard_option_declarations(
    *,
    authority: GovernedFactSource | None = None,
) -> dict[str, tuple[str, str, str]]:
    """Return question option declarations as ``flag, kind, help`` tuples."""
    prefix = "wizard.option."
    options: dict[str, tuple[str, str, str]] = {}
    for key, value in mapping_fact_entries(_SETUP_FACT_ID, authority=authority).items():
        if not key.startswith(prefix):
            continue
        parts = value.split("|", 2)
        if len(parts) != 3:
            raise RegistryValidationError(f"invalid wizard option declaration {key!r}")
        options[key.removeprefix(prefix)] = (parts[0], parts[1], parts[2])
    return options


def legal_source_kind_declarations(*, authority: GovernedFactSource | None = None) -> dict[str, str]:
    """Return legal-reference kind to citation-source mappings."""
    prefix = "legal.source_kind."
    return {
        key.removeprefix(prefix): value
        for key, value in mapping_fact_entries("legal-reference-schema-vocabulary", authority=authority).items()
        if key.startswith(prefix)
    }


__all__ = [
    "legal_source_kind_declarations",
    "mapping_fact_entries",
    "profile_field_bindings",
    "setup_answer_declarations",
    "wizard_option_declarations",
    "wizard_page_declarations",
]

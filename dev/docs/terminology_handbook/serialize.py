"""Deterministic TOML serialisation of a Terminology Handbook concept.

The scaffold writes concept fragments back as TOML. Serialisation is
canonical and stable: the same :class:`~dev.docs.terminology_handbook.schema.ConceptRecord`
always emits byte-identical TOML, so a no-change scaffold run is a
no-op diff (idempotence) and a curated field round-trips through
``serialise -> load`` unchanged (the PRESERVE guarantee operates at the
field-value level: a definition string survives verbatim, mirroring the
``dev.locales`` YAML re-dump precedent that preserves leaf values).

``narrower`` is never serialised -- it is derived at load from the
inverse of ``broader`` and authoring it is rejected. Empty optional
fields are omitted entirely so a scaffold-empty draft is visibly bare.
"""

from __future__ import annotations

from datetime import date

from .schema import ConceptRecord, LanguageSection, TermSection

__all__ = ["serialise_concept"]

_HEADER = (
    "# Terminology Handbook concept fragment.\n"
    "# Compiled by the strict loader in `dev.docs.terminology_handbook` into a frozen\n"
    "# `ConceptRecord`. Curated prose fields (definition, scope_note,\n"
    "# short_description) are hand-edited; structural operations go\n"
    "# through the `dev.docs.terminology_handbook` CLI. `narrower` is derived at load\n"
    "# from `broader` and must never be authored here.\n"
)


def serialise_concept(concept: ConceptRecord) -> str:
    """Render one :class:`ConceptRecord` as a canonical TOML fragment."""
    lines: list[str] = [_HEADER, "[concept]"]
    lines.append(f'concept_id = "{concept.concept_id}"')
    lines.append(f'domain = "{concept.domain.value}"')
    lines.append(f'lifecycle = "{concept.lifecycle.value}"')
    _emit_str_array(lines, "domain_refs", concept.domain_refs)
    _emit_str_array(lines, "legal_refs", concept.legal_refs)
    _emit_str_array(lines, "broader", concept.broader)
    _emit_str_array(lines, "related", concept.related)
    if concept.replaced_by is not None:
        lines.append(f'replaced_by = "{concept.replaced_by}"')
    lines.append(f"created_at = {_emit_date(concept.created_at)}")
    lines.append(f"updated_at = {_emit_date(concept.updated_at)}")

    if concept.seed_provenance is not None:
        provenance = concept.seed_provenance
        lines.append("")
        lines.append("[concept.seed_provenance]")
        lines.append(f'source = "{_escape(provenance.source)}"')
        lines.append(f'attribution = "{_escape(provenance.attribution)}"')
        if provenance.source_entry_id is not None:
            lines.append(f'source_entry_id = "{_escape(provenance.source_entry_id)}"')

    # Emit language sections in the record's own order so a load -> serialise
    # round-trip is order-stable (the loader preserves authoring order).
    for section in concept.languages:
        _emit_language(lines, section)

    return "\n".join(lines).rstrip("\n") + "\n"


def _emit_language(lines: list[str], section: LanguageSection) -> None:
    code = section.language.value
    lines.append("")
    lines.append(f"[language.{code}]")
    lines.append(f'short_description = "{_escape(section.short_description)}"')
    if section.definition is not None:
        lines.append(f'definition = "{_escape(section.definition)}"')
    if section.scope_note is not None:
        lines.append(f'scope_note = "{_escape(section.scope_note)}"')
    if section.source is not None:
        lines.append("")
        lines.append(f"[language.{code}.source]")
        lines.append(f'citation = "{_escape(section.source.citation)}"')
        if section.source.authority is not None:
            lines.append(f'authority = "{_escape(section.source.authority)}"')
    for term in section.terms:
        _emit_term(lines, code, term)


def _emit_term(lines: list[str], code: str, term: TermSection) -> None:
    lines.append("")
    lines.append(f"[[language.{code}.term]]")
    lines.append(f'label = "{_escape(term.label)}"')
    lines.append(f'term_status = "{term.term_status.value}"')
    if term.part_of_speech is not None:
        lines.append(f'part_of_speech = "{term.part_of_speech.value}"')
    if term.grammatical_gender is not None:
        lines.append(f'grammatical_gender = "{term.grammatical_gender.value}"')
    _emit_str_array(lines, "hidden_search_forms", term.hidden_search_forms)


def _emit_str_array(lines: list[str], key: str, values: tuple[str, ...]) -> None:
    if not values:
        return
    rendered = ", ".join(f'"{_escape(value)}"' for value in values)
    lines.append(f"{key} = [{rendered}]")


def _emit_date(value: date) -> str:
    return value.isoformat()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

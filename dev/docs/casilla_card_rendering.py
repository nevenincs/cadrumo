"""Render one casilla card from its localized registry record and compiled facts.

A card is raw HTML this module escapes itself, so it escapes through
:func:`~dev.docs.compile_slots.escape` rather than :func:`html.escape`: under
the one multilingual compile a chrome string or a registry label here is a mark,
and escaping the mark would do nothing while every language's string went
unescaped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

from ._locale_chrome import docs_chrome, docs_line
from .casilla_legal_grounding import _legal_list, _LegalLink
from .casilla_markup import _raw_html
from .casilla_reference_models import CasillaFacts
from .compile_slots import escape
from .terminology.casilla_anchor import casilla_page_anchor
from .terminology.search_record import CasillaSearchRecord

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints


# ── Card rendering ───────────────────────────────────────────────────────────


def _localised(record: CasillaSearchRecord, language: OutputLanguage) -> tuple[str | None, str | None]:
    """Return ``(label, help)`` for the build language, or ``None`` where unauthored.

    There is deliberately no fallback: a casilla with no label in the build
    language renders without a label rather than borrowing another language's.
    """

    def _clean(value: str | None) -> str | None:
        return value if value is not None and value.strip() else None

    return _clean(record.descriptions.get(language)), _clean(record.localized_help.get(language.value))


def _title_element(record: CasillaSearchRecord, language: OutputLanguage) -> str | None:
    """Return the card's title element in ``language``, or None where it has no label.

    The label is registry CONTENT the authority holds per language, so it is not
    resolved through the chrome catalogue; it is read for the language asked for
    and escaped as this card's own raw HTML escapes text. A language with no
    label has no title element at all rather than an empty one, which is why the
    element and not the string is what each language reads.
    """
    label, _help = _localised(record, language)
    if label is None:
        return None
    return f'<h3 class="casilla-card__title">{escape(" ".join(label.split()))}</h3>'


def _help_element(record: CasillaSearchRecord, box_number: str, language: OutputLanguage) -> str | None:
    """Return the card's help paragraph in ``language``, or None where it has none."""
    _label, help_text = _localised(record, language)
    description = _description(help_text, box_number)
    if not description:
        return None
    return f'<p class="casilla-card__help">{escape(" ".join(description.split()))}</p>'


def _join_references(references: list[str], language: OutputLanguage) -> str:
    """Join rendered box links as a readable list ("01, 02 and 05")."""
    if len(references) <= 1:
        return "".join(references)
    return f"{', '.join(references[:-1])} {docs_chrome('docs.casilla.chrome.list_and', language)} {references[-1]}"


def _fill_explanation(
    record: CasillaSearchRecord,
    facts: CasillaFacts | None,
    numbers_by_id: Mapping[str, str],
    language: OutputLanguage,
) -> list[str]:
    """Render the "how this box gets filled" answer, the substance of an entry.

    Computed casillas name the boxes they derive FROM, each linked to its own
    entry, because a derivation is the one honest description of meaning the
    schema can give. Bound casillas name the source that fills them.
    """
    input_kind = record.input_kind.value
    headline = docs_chrome(f"docs.casilla.input_kind.{input_kind}", language)
    lines = [
        f'<p class="casilla-fill casilla-fill--{escape(input_kind, quote=True)}">',
        f'<span class="casilla-fill__kind">{escape(headline)}</span>',
    ]

    detail: str | None = None
    if facts is not None and facts.binding_sources:
        phrases = [docs_chrome(f"docs.casilla.binding_source.{source}", language) for source in facts.binding_sources]
        alternative = docs_chrome("docs.casilla.chrome.alternative_join", language)
        detail = phrases[0] if len(phrases) == 1 else alternative.join(phrases)
    if detail is not None:
        lines.append(f'<span class="casilla-fill__detail">{escape(detail)}</span>')

    if facts is not None and facts.formula_inputs:
        references: list[str] = []
        for casilla_id in facts.formula_inputs:
            number = numbers_by_id.get(casilla_id)
            anchor = casilla_page_anchor(record.modelo, casilla_id)
            text = number if number is not None else casilla_id
            references.append(
                f'<a href="#{escape(anchor, quote=True)}" title="{escape(casilla_id, quote=True)}">{escape(text)}</a>',
            )
        derived = docs_chrome("docs.casilla.chrome.derived_from", language)
        lines.append(f'<span class="casilla-fill__detail">{escape(derived)}</span>')
        lines.append(f'<span class="casilla-derives-from">{_join_references(references, language)}</span>')
    # What the filer types belongs in this sentence, not in a pill of its own:
    # every casilla has a value shape, so a pill for it carried no signal and
    # only crowded the ones that do (required, a range, a segmento).
    data_type = docs_chrome(f"docs.casilla.data_type.{record.data_type}", language)
    lines.append(f'<span class="casilla-fill__shape">{escape(data_type)}</span>')
    lines.append("</p>")
    return lines


def _description(help_text: str | None, box_number: str) -> str | None:
    """Drop a leading restatement of the box number from the authored help.

    Registry help routinely opens by naming the box ("Box 01: taxable base
    for..."), which the number beside the title has already said. Keyed on the
    number actually rendered, so it strips only a genuine echo and needs no
    per-language prefix list.
    """
    if help_text is None:
        return None
    stripped = re.sub(
        rf"^\s*\w+\s*0*{re.escape(box_number.lstrip('0') or box_number)}\s*[:.–-]\s*",
        "",
        help_text,
        count=1,
    )
    stripped = stripped.strip()
    if not stripped:
        return None
    return stripped[:1].upper() + stripped[1:]


def _box_number(record: CasillaSearchRecord, facts: CasillaFacts | None) -> str:
    """The box number a reader sees on the printed form.

    ``form_number`` is the printed box; ``number`` is AEAT record-design
    metadata that for some modelos is the casilla id itself. The printed box
    wins wherever the registry states one, and the record-design value stays
    visible in the identifier disclosure.
    """
    if facts is not None and facts.form_number:
        return facts.form_number
    return record.number


def _constraint_phrases(constraints: CasillaConstraints | None, language: OutputLanguage) -> list[str]:
    """Read the authored value constraints as what a filer may enter."""
    if constraints is None:
        return []
    phrases: list[str] = []
    _value_constraint_phrases(constraints, language, phrases)
    _length_constraint_phrases(constraints, language, phrases)

    if constraints.enum:
        phrases.append(
            docs_chrome("docs.casilla.value_enum", language, values=", ".join(str(value) for value in constraints.enum))
        )
    return phrases


def _fact_chips(record: CasillaSearchRecord, facts: CasillaFacts | None, language: OutputLanguage) -> list[str]:
    """The scannable filing facts: what to type, whether it is required, where it sits."""
    chips: list[str] = []
    if record.required:
        required = docs_chrome("docs.casilla.chrome.required", language)
        chips.append(f'<li class="casilla-fact casilla-fact--required">{escape(required)}</li>')
    for phrase in _constraint_phrases(facts.constraints if facts else None, language):
        chips.append(f'<li class="casilla-fact">{escape(phrase)}</li>')
    if record.segmento:
        segmento = docs_chrome("docs.casilla.chrome.segmento", language, segmento=record.segmento)
        chips.append(f'<li class="casilla-fact">{escape(segmento)}</li>')
    if facts is not None and facts.internal_only:
        internal = docs_chrome("docs.casilla.chrome.not_on_official_form", language)
        chips.append(f'<li class="casilla-fact casilla-fact--internal">{escape(internal)}</li>')
    return chips


def _internals_block(record: CasillaSearchRecord, box_number: str, language: OutputLanguage) -> list[str]:
    """The registry's own identifiers, demoted into a collapsed disclosure.

    Machine vocabulary a taxpayer never reads, kept on the page because an
    operator debugging a value needs the exact ids the registry carries.
    """
    rows = _registry_identifier_rows(record, box_number, language)
    lines = [
        '<details class="casilla-card__internals">',
        f"<summary>{escape(docs_chrome('docs.casilla.chrome.registry_identifiers', language))}</summary>",
        '<dl class="casilla-internals">',
    ]
    lines.extend(f"<dt>{escape(term)}</dt><dd>{value}</dd>" for term, value in rows)
    lines.extend(["</dl>", "</details>"])
    return lines


def _render_entry(
    record: CasillaSearchRecord,
    links: dict[str, _LegalLink],
    language: OutputLanguage,
    facts: CasillaFacts | None,
    numbers_by_id: Mapping[str, str],
) -> tuple[str, str, tuple[str, ...], int]:
    """Render one casilla card.

    Returns ``(rst, anchor, rendered_legal_refs, resolved_link_count)``.
    """
    anchor = casilla_page_anchor(record.modelo, record.casilla_id)
    box_number = _box_number(record, facts)

    lines = [
        f'<article class="casilla-card" id="{escape(anchor, quote=True)}">',
        '<header class="casilla-card__head">',
        f'<span class="casilla-card__number">{escape(box_number)}</span>',
    ]
    # The title and the help are an element a language has or has not, so each
    # rides on the end of the line before it and brings its own line break.
    lines[-1] += docs_line(partial(_title_element, record), language)
    lines.append("</header>")
    lines[-1] += docs_line(partial(_help_element, record, box_number), language)
    lines.extend(_fill_explanation(record, facts, numbers_by_id, language))
    chips = _fact_chips(record, facts, language)
    if chips:
        lines.append('<ul class="casilla-card__facts">')
        lines.extend(chips)
        lines.append("</ul>")
    legal_lines, resolved = (
        ([], 0)
        if not record.legal_refs
        else _legal_list(record.legal_refs, links, docs_chrome("docs.casilla.chrome.legal_basis", language))
    )
    lines.extend(legal_lines)
    lines.extend(_internals_block(record, box_number, language))
    lines.append("</article>")
    # Read the grounding inventory back OUT of the markup just emitted, never
    # from ``record.legal_refs``. Echoing the input would make the inventory
    # agree with the record by construction, so a ref the renderer silently
    # dropped would still be reported as rendered.
    legal_markup = "\n".join(legal_lines)
    rendered_refs = tuple(
        ref for ref in record.legal_refs if escape(ref) in legal_markup or escape(ref, quote=True) in legal_markup
    )
    return _raw_html(lines), anchor, rendered_refs, resolved


def _value_constraint_phrases(constraints: CasillaConstraints, language: OutputLanguage, phrases: list[str]) -> None:
    minimum, maximum = constraints.min_value, constraints.max_value
    if minimum is not None and maximum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.between", language, min=minimum, max=maximum))
    elif minimum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.at_least", language, min=minimum))
    elif maximum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.at_most", language, max=maximum))
    elif constraints.sign != "any":
        phrases.append(docs_chrome(f"docs.casilla.value_range.{constraints.sign}", language))


def _length_constraint_phrases(constraints: CasillaConstraints, language: OutputLanguage, phrases: list[str]) -> None:
    if constraints.min_length is not None and constraints.max_length is not None:
        phrases.append(
            docs_chrome("docs.casilla.length.between", language, min=constraints.min_length, max=constraints.max_length)
        )
    elif constraints.max_length is not None:
        phrases.append(docs_chrome("docs.casilla.length.at_most", language, max=constraints.max_length))
    elif constraints.min_length is not None:
        phrases.append(docs_chrome("docs.casilla.length.at_least", language, min=constraints.min_length))


def _registry_identifier_rows(
    record: CasillaSearchRecord, box_number: str, language: OutputLanguage
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [
        (
            docs_chrome("docs.casilla.chrome.casilla_id", language),
            f"<code>{escape(str(record.casilla_id))}</code>",
        ),
    ]
    if record.number != box_number:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.record_design_number", language),
                f"<code>{escape(record.number)}</code>",
            )
        )
    if record.semantic_role:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.semantic_role", language),
                f"<code>{escape(record.semantic_role)}</code>",
            )
        )
    if record.binding is not None:
        rows.append(
            (docs_chrome("docs.casilla.chrome.binding", language), f"<code>{escape(str(record.binding))}</code>")
        )
    if record.formula_id is not None:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.formula", language),
                f"<code>{escape(str(record.formula_id))}</code>",
            )
        )
    registry_section = ".".join(record.section) or "general"
    rows.append(
        (docs_chrome("docs.casilla.chrome.registry_section", language), f"<code>{escape(registry_section)}</code>")
    )
    if record.source_refs:
        joined = " ".join(f"<code>{escape(ref)}</code>" for ref in record.source_refs)
        rows.append((docs_chrome("docs.casilla.chrome.sources", language), joined))
    if record.source_revisions:
        joined = " ".join(f"<code>{escape(rev)}</code>" for rev in record.source_revisions)
        rows.append((docs_chrome("docs.casilla.chrome.revisions", language), joined))
    return rows

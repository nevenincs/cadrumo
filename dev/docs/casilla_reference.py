"""Generated per-modelo casilla reference pages, compiled from the registry schema.

The sibling of :mod:`dev.docs.glossary_reference`: a build-time projection
rendered from a typed authority into uncommitted pages the docs build emits,
regenerated on every build so they can never drift from the source. Where the
glossary projects Handbook concepts into one page, this projects every casilla
into one page PER MODELO (``docs/_generated/casillas/<modelo>.rst``) plus an
``index.rst`` toctree.

**There is no per-casilla prose to render, and none is coming.** Of the casilla
``help`` keys the catalogues carry, a fraction of a percent hold content;
authoring the rest by hand is rejected and compiling it from the AEAT manuals is
out of scope. So what a reader gets is COMPILED FROM THE SCHEMA, and a casilla's
meaning is carried by its RELATIONSHIPS and its derivation, which the registry
states exactly:

* :attr:`~cadrumo.domain.calculations.registry.CasillaDefinition.input_kind` -
  the question a filer actually has: do I type this, or is it worked out for me?
* the ``formula`` a computed casilla declares, rendered as the boxes it derives
  FROM (linked to their own entries), never as a formula id.
* the ``binding`` and ``alternate_bindings`` a bound casilla declares, rendered
  as WHICH source fills it - ledger, profile, previous filing - through the
  :class:`~cadrumo.core.BindingSourceKind` taxonomy.
* ``number`` / ``form_number`` / ``segmento`` - where the box physically sits on
  the official form; ``data_type``, ``required`` and ``constraints`` - what to
  type and whether it is mandatory; ``section`` - its place in the structure;
  ``legal_refs`` - linked into the generated legal reference.

**One language, and never a substitute.** The only localized text that exists is
what the four catalogues carry for the schema: casilla labels, modelo titles and
official names, plus the Terminology Handbook's curated modelo definitions. A
page built under ``CADRUMO_DOCS_LANGUAGE`` renders ONLY that language. A string
absent in the build language is OMITTED - never filled from Spanish, never from
another locale - because a page that silently substitutes another language reads
as though the reader's language were covered when it is not. Modelo titles and
official names are the one deliberate exception in substance rather than
mechanism: AEAT publishes them in Spanish and the catalogues carry that Spanish
string under every locale, so what renders is the form's own name.

Anchors: every entry carries a page-local HTML id from
:func:`~dev.docs.terminology._casilla_anchor.casilla_page_anchor`, the exact
target the search record deep-links to. A raw-HTML id (not a Sphinx ``.. _:``
label) is used deliberately: casilla ids repeat across modelos, so a global
label would collide project-wide, while a page-local HTML id may safely repeat
on sibling pages. A post-slug anchor collision within one page is a hard
generator failure, never a silent merge (the ``-n -W`` build needs every
emitted id unique per page).
"""

from __future__ import annotations

import html
import os
import posixpath
import re
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .legal_reference import legal_reference_target, load_legal_provisions
from .terminology import CasillaSearchRecord, project_casilla_search_records
from .terminology._casilla_anchor import CASILLA_REFERENCE_DIR, casilla_page_anchor, casilla_page_relpath

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.calculations.registry import CasillaConstraints, ValidatedRegistryAuthority

    from .legal_reference import LegalProvisionRecord

_UTF_8 = "utf-8"


class CasillaReferenceError(RuntimeError):
    """Raised when a modelo page would emit an ambiguous anchor.

    A named, actionable boundary: two casilla ids - or two registry section
    paths - on one page folding to the same HTML anchor would ship a page whose
    ``#`` fragment is ambiguous and red the ``-n -W`` build. The generator
    refuses to write it.
    """


@dataclass(frozen=True)
class CasillaFacts:
    """How one casilla is filled, compiled from its registry definition.

    The substance of an entry. Read from the exact
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` the search
    record was projected from, so the page and the search card can never
    disagree about which revision they describe.
    """

    #: ``BindingSourceKind`` values that may fill this casilla, primary first.
    binding_sources: tuple[str, ...] = ()
    #: Casilla ids this casilla's formula derives from, in expression order.
    formula_inputs: tuple[str, ...] = ()
    constraints: CasillaConstraints | None = None
    #: The printed form number where it differs from the canonical ``number``.
    form_number: str | None = None
    #: An app-internal computed casilla absent from the AEAT record design.
    internal_only: bool = False


@dataclass(frozen=True)
class ModeloOverview:
    """What a modelo IS, compiled from the registry plus the Terminology Handbook.

    ``definition`` is curated Handbook prose and is present only for an approved
    concept that authored it IN THE BUILD LANGUAGE; everything else is compiled
    from the schema, so a modelo with no curated definition still says what it
    is rather than opening on a bare list.
    """

    title: str
    official_name: str
    #: Curated Handbook definition in the build language, or ``None``.
    definition: str | None
    tax_domain: str
    cadence: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True)
class CompiledSchema:
    """The schema-compiled substance behind the pages, injectable for tests."""

    casillas: Mapping[tuple[str, str], CasillaFacts]
    modelos: Mapping[str, ModeloOverview]


#: Renders a page from the records alone, with no registry read. The shape a
#: narrowed test drives; the real build always compiles the schema.
EMPTY_SCHEMA: Final[CompiledSchema] = CompiledSchema(casillas={}, modelos={})


@dataclass(frozen=True)
class CasillaPage:
    """One rendered modelo page and its anchor / grounding inventory (for the gate)."""

    modelo: str
    output_relpath: str
    rst: str
    #: The ``casilla-<slug>`` anchor id emitted for each casilla, in page order.
    anchors: tuple[str, ...]
    #: ``anchor -> the legal_refs rendered on that entry`` (grounding coverage).
    rendered_legal_refs: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CasillaReferenceResult:
    """Outcome of a casilla-reference generation pass."""

    pages: tuple[CasillaPage, ...]
    index_relpath: str
    modelo_count: int
    casilla_count: int
    legal_links: int


@dataclass(frozen=True)
class _LegalLink:
    """One catalogue provision projected for display on a casilla card."""

    #: Human reading of the provision ("Ley 37/1992, art. 92").
    label: str
    #: Site-relative target of the generated legal-reference destination.
    target: str


#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value reaching an RST heading is backslash-escaped or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run. Card
#: bodies are raw HTML and are HTML-escaped instead.
_RST_SPECIAL = "\\`*_|[]"

#: Official Spanish naming for each authored catalogue ``kind``. AEAT publishes
#: these instruments under their Spanish names, so the display stays Spanish in
#: every build language (the domain-naming rule) - only the surrounding chrome
#: is English.
_LEGAL_KIND_DISPLAY: Final[dict[str, str]] = {
    "acuerdo_internacional": "Convenio",
    "dictionary": "Diccionario de datos AEAT",
    "form_spec": "Modelo oficial AEAT",
    "instruction": "Instrucciones AEAT",
    "instructions": "Instrucciones AEAT",
    "ley": "Ley",
    "manual_pdf": "Manual AEAT",
    "orden": "Orden",
    "real_decreto": "Real Decreto",
    "real_decreto_legislativo": "Real Decreto Legislativo",
    "real_decreto_ley": "Real Decreto-ley",
    "record_design": "Diseño de registro AEAT",
    "reglamento": "Reglamento",
    "suppression_notice": "Nota AEAT",
    "xsd": "Esquema XSD AEAT",
}

#: Id tokens that merely restate the authored ``kind`` and are dropped from the
#: display so ``ley-37-1992`` reads "Ley 37/1992", not "Ley ley 37/1992".
_LEGAL_KIND_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "acuerdo",
        "convenio",
        "decreto",
        "dl",
        "instruccion",
        "ley",
        "orden",
        "rd",
        "rdl",
        "rdleg",
        "real",
        "refundido",
        "reglamento",
        "resolucion",
        "texto",
        "trlirnr",
        "trlirpf",
        "trlis",
    },
)

_YEAR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(19|20)\d{2}$")

#: Registry section and tax-domain tokens that are AEAT acronyms, not words:
#: capitalising them as prose would render the tax itself as "Iva".
_ACRONYMS: Final[frozenset[str]] = frozenset(
    {"aeat", "cif", "iae", "irnr", "irpf", "is", "isp", "iva", "nif", "oss", "ue"},
)

#: What the filer actually has to type, per registry ``data_type``.
_DATA_TYPE_DISPLAY: Final[dict[str, str]] = {
    "bic": "BIC",
    "boolean": "Yes or no",
    "ccaa_code": "Autonomous-community code",
    "country_code": "Country code",
    "date": "Date",
    "decimal": "Decimal number",
    "iban": "IBAN",
    "integer": "Whole number",
    "money": "Amount in euros",
    "municipality_code": "Municipality code",
    "name": "Name",
    "nif": "NIF",
    "nif_iva": "VAT-registered NIF",
    "period_code": "Period",
    "postal_code": "Postcode",
    "province_code": "Province code",
    "ratio": "Percentage",
    "text": "Text",
    "year": "Year",
}

#: The headline answer to "how does this box get filled", per ``input_kind``.
_INPUT_KIND_DISPLAY: Final[dict[str, str]] = {
    "bound": "Filled automatically",
    "computed": "Calculated for you",
    "informational": "Reference only",
    "manual": "You enter this",
}

#: The same axis counted on the modelo overview, where the phrase follows a
#: number and so reads as a noun rather than as a sentence about one box.
_INPUT_KIND_COUNT_DISPLAY: Final[dict[str, str]] = {
    "bound": "filled from your records",
    "computed": "calculated",
    "informational": "reference only",
    "manual": "you enter",
}

#: WHICH source fills a bound casilla, per :class:`~cadrumo.core.BindingSourceKind`.
#: Complete over the enum by contract - a new kind with no phrase here is a gate
#: failure, never a silently blank explanation.
_BINDING_SOURCE_DISPLAY: Final[dict[str, str]] = {
    "atribucion_member": "from the atribución de rentas members you recorded",
    "bienes_inversion_regularizacion": "from your bienes de inversión regularisation",
    "borrador": "from the AEAT borrador",
    "collectible_invoice": "from the invoices you issued",
    "donativo_donor": "from the donativo donor records",
    "foreign_asset": "from your foreign-asset records",
    "iva_compensation_annual_partition": "from the IVA compensación carried across the year",
    "iva_wallet_decision": "from your IVA compensación decision",
    "ledger_impatriado_income_aggregation": "from your ledger income under the impatriado regime",
    "ledger_irnr_income_aggregation": "from your ledger IRNR income",
    "ledger_iva_aggregation": "from your IVA ledger entries",
    "ledger_oss_aggregation": "from your OSS ledger entries",
    "ledger_renta_gastos_estimacion_directa_aggregation": "from your ledger expenses under estimación directa",
    "ledger_renta_gastos_pago_fraccionado_aggregation": "from your ledger expenses for the pago fraccionado",
    "ledger_renta_income_aggregation": "from your ledger income",
    "ledger_transaction": "from your ledger transactions",
    "manual_input": "from a value you supply",
    "payable_invoice": "from the invoices you received",
    "previous_filing": "from your previous filing",
    "profile": "from your taxpayer profile",
    "prorrata_regularizacion": "from your prorrata regularisation",
    "purchase_invoice_evidence": "from your purchase-invoice evidence",
    "refund_operation": "from your refund operations",
    "related_party_operation": "from your related-party operations",
    "relation_prefill": "from a related modelo's result",
    "retenciones_aggregation": "from the retenciones you recorded",
    "withholding": "from the withholdings you recorded",
}

#: When the modelo is filed, per registry ``cadence``.
_CADENCE_DISPLAY: Final[dict[str, str]] = {
    "ad_hoc": "Filed when the event occurs",
    "annual": "Filed annually",
    "monthly": "Filed monthly",
    "profile_based": "Filed when your profile requires it",
    "quarterly": "Filed quarterly",
}

#: How a value range reads, per registry ``constraints.sign``.
_SIGN_DISPLAY: Final[dict[str, str]] = {
    "non_negative": "Zero or more",
    "non_positive": "Zero or less",
}


def _rst_escape(text: str) -> str:
    """Backslash-escape RST inline-markup characters in arbitrary free text."""
    return "".join(f"\\{ch}" if ch in _RST_SPECIAL else ch for ch in text)


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _raw_html(lines: list[str]) -> str:
    """Wrap rendered HTML lines in an RST ``raw`` directive block."""
    body = "\n".join(f"   {line}" for line in lines)
    return f".. raw:: html\n\n{body}\n"


def _humanise_token(token: str) -> str:
    """Read a snake_case registry token as prose (``rdto_trabajo`` -> ``Rdto trabajo``)."""
    words = token.replace("_", " ").replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else ""


def _token_display(token: str) -> str:
    """Render a registry token, preserving AEAT acronyms in upper case."""
    return token.upper() if token.lower() in _ACRONYMS else _humanise_token(token)


def _section_display(section: tuple[str, ...]) -> str:
    """The human display for a registry section path, token by token."""
    return " › ".join(_token_display(part) for part in section if part) or "General"


def _section_anchor(section: tuple[str, ...]) -> str:
    """A page-local id for one section group, distinct from the casilla ids."""
    joined = "-".join(part for part in section if part) or "general"
    slug = re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
    return f"section-{slug or 'general'}"


def _display_language() -> OutputLanguage:
    """The one language this build renders, read from the shared build signal."""
    from .build import docs_build_language

    return docs_build_language(os.environ)


# ── Legal provision display ──────────────────────────────────────────────────


def _legal_numeral(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Split a trailing ``<number>-<year>`` pair off a document-id token run."""
    if len(tokens) >= 2 and _YEAR_PATTERN.match(tokens[-1]) and tokens[-2].isdigit():
        return f"{tokens[-2]}/{tokens[-1]}", tokens[:-2]
    return None, tokens


def _legal_provision_display(legal_id: str, provision: LegalProvisionRecord) -> str:
    """Read one catalogue provision as its official Spanish name plus its article.

    Built only from authored fields (``kind``, ``article``, ``section``) and the
    document half of the catalogue id, which encodes the instrument's number and
    year. An id whose shape yields nothing falls back to the raw id, so the
    display never invents a citation it cannot derive.
    """
    document_part, _, provision_part = legal_id.partition(":")
    tokens = [token for token in document_part.split("-") if token]
    numeral, remainder = _legal_numeral(tokens)
    remainder = [token for token in remainder if token.lower() not in _LEGAL_KIND_TOKENS]
    separator = "/" if numeral else "-"
    qualifier = separator.join(token.upper() if len(token) <= 4 else _humanise_token(token) for token in remainder)

    kind_display = _LEGAL_KIND_DISPLAY.get(provision.kind, _humanise_token(provision.kind))
    name = " ".join(part for part in (kind_display, qualifier) if part)
    if numeral:
        name = f"{name}{separator if qualifier else ' '}{numeral}"
    name = name.strip()
    if not name:
        return legal_id

    # The authored ``section`` prose is the most human reading of a provision;
    # ``article`` is next (numeric articles take the ``art.`` prefix, worded
    # ones already read as prose); the id's own provision half is the floor.
    if provision.section:
        return f"{name}, {provision.section}"
    if provision.article:
        prefix = "art. " if provision.article[:1].isdigit() else ""
        return f"{name}, {prefix}{provision.article}"
    if provision_part:
        return f"{name}, {provision_part.replace('-', ' ')}"
    return name


@lru_cache(maxsize=4)
def _legal_links(repo_root: Path) -> dict[str, _LegalLink]:
    """Map every catalogue provision id to its display name and generated destination.

    The destination is the generated legal-reference page the sibling generator
    writes, derived through that module's own target helper, so a casilla's
    grounding lands on the in-site provision entry rather than dumping a raw
    token or bouncing the reader straight out to BOE.
    """
    links: dict[str, _LegalLink] = {}
    for provision in load_legal_provisions(repo_root):
        target = legal_reference_target(
            provision.document_id,
            provision.legal_id,
            article=provision.article,
            section=provision.section,
            corpus_ref=provision.corpus_ref,
            permalink=provision.permalink,
        )
        links[provision.legal_id] = _LegalLink(
            label=_legal_provision_display(provision.legal_id, provision),
            target=_relative_to_casilla_page(target),
        )
    return links


def _relative_to_casilla_page(site_target: str) -> str:
    """Rewrite a site-relative target as a link relative to a casilla page."""
    page, _, fragment = site_target.partition("#")
    relative = posixpath.relpath(page, CASILLA_REFERENCE_DIR)
    return f"{relative}#{fragment}" if fragment else relative


def _legal_list(refs: tuple[str, ...], links: dict[str, _LegalLink], label: str) -> tuple[list[str], int]:
    """Render a legal-basis list, returning the lines and the resolved-link count."""
    items: list[str] = []
    resolved = 0
    for ref in refs:
        link = links.get(ref)
        if link is None:
            items.append(f'<li><span class="casilla-legal-ref casilla-legal-ref--raw">{html.escape(ref)}</span></li>')
            continue
        resolved += 1
        items.append(
            f'<li><a class="casilla-legal-ref" href="{html.escape(link.target, quote=True)}"'
            f' title="{html.escape(ref, quote=True)}">{html.escape(link.label)}</a></li>',
        )
    lines = [
        '<div class="casilla-card__legal">',
        f'<span class="casilla-card__legal-label">{html.escape(label)}</span>',
        '<ul class="casilla-card__legal-list">',
        *items,
        "</ul>",
        "</div>",
    ]
    return lines, resolved


# ── Schema compilation ───────────────────────────────────────────────────────


def compile_schema(
    records: tuple[CasillaSearchRecord, ...],
    language: OutputLanguage,
    authority: ValidatedRegistryAuthority | None = None,
) -> CompiledSchema:
    """Compile the fill/derivation facts and modelo overviews the pages render.

    Each record is resolved back to the exact revision it was projected from
    (``source_revisions[0]``, latest first), so this reads the SAME casilla
    definition the search card describes rather than re-deriving which revision
    applies - one selection authority, not two.

    Args:
        records: The projected casilla records the pages will render.
        language: The build language; the Handbook definition and the modelo
            title/official name are read in this language only.
        authority: Validated registry authority; defaults to the bundled one.

    Returns:
        A :class:`CompiledSchema`. A record whose modelo, revision or casilla
        does not resolve is simply absent from the map, and its entry renders
        from the record alone.
    """
    from cadrumo.domain.calculations.registry import bundled_authority, expression_casilla_refs

    resolved = authority if authority is not None else bundled_authority()
    modelos = {modelo.id: modelo for modelo in resolved.modelos}

    facts: dict[tuple[str, str], CasillaFacts] = {}
    revision_cache: dict[tuple[str, str], tuple[dict[str, object], dict[str, object], dict[str, str]]] = {}

    for record in records:
        modelo = modelos.get(record.modelo.value)
        if modelo is None or not record.source_revisions:
            continue
        revision = modelo.revisions.get(record.source_revisions[0])
        if revision is None:
            continue

        key = (record.modelo.value, record.source_revisions[0])
        cached = revision_cache.get(key)
        if cached is None:
            casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
            formulas: dict[str, object] = {}
            for formula in revision.formulas:
                formulas[str(formula.target_casilla_id)] = formula
            sources = {str(binding.id): str(binding.source) for binding in revision.bindings}
            cached = (casillas_by_id, formulas, sources)
            revision_cache[key] = cached
        casillas_by_id, formulas_by_target, binding_sources = cached

        casilla = casillas_by_id.get(record.casilla_id)
        if casilla is None:
            continue

        formula = formulas_by_target.get(str(casilla.id))
        formula_inputs = (
            ()
            if formula is None
            else tuple(dict.fromkeys(str(ref) for ref in expression_casilla_refs(formula.expression)))
        )
        binding_ids = (casilla.binding, *casilla.alternate_bindings) if casilla.binding is not None else ()
        facts[(record.modelo.value, str(record.casilla_id))] = CasillaFacts(
            binding_sources=tuple(
                dict.fromkeys(
                    source
                    for source in (binding_sources.get(str(binding_id)) for binding_id in binding_ids)
                    if source is not None
                ),
            ),
            formula_inputs=formula_inputs,
            constraints=casilla.constraints,
            form_number=casilla.form_number if casilla.form_number != casilla.number else None,
            internal_only=casilla.internal_only,
        )

    return CompiledSchema(
        casillas=facts,
        modelos=_compile_modelo_overviews({record.modelo.value for record in records}, language, modelos),
    )


def _compile_modelo_overviews(
    modelo_ids: set[str],
    language: OutputLanguage,
    modelos: Mapping[str, object],
) -> dict[str, ModeloOverview]:
    """Compile each modelo's identity, cadence, grounding and curated definition."""
    definitions = _handbook_definitions(language)
    overviews: dict[str, ModeloOverview] = {}
    for modelo_id in sorted(modelo_ids):
        modelo = modelos.get(modelo_id)
        if modelo is None:
            continue
        overviews[modelo_id] = ModeloOverview(
            title=modelo.get_title(language.value),  # type: ignore[attr-defined]
            official_name=modelo.get_official_name(language.value),  # type: ignore[attr-defined]
            definition=definitions.get(modelo_id),
            tax_domain=str(modelo.tax_domain),  # type: ignore[attr-defined]
            cadence=str(modelo.cadence),  # type: ignore[attr-defined]
            legal_refs=tuple(str(ref) for ref in modelo.legal_refs),  # type: ignore[attr-defined]
        )
    return overviews


def _handbook_definitions(language: OutputLanguage) -> dict[str, str]:
    """``modelo id -> curated definition`` for approved concepts, in ONE language.

    Only an ``approved`` concept that authored a definition in the build language
    contributes; a draft concept, or one translated into other locales but not
    this one, contributes nothing rather than a substituted string.
    """
    from cadrumo.core import ConceptLifecycle

    from .terminology_handbook import load_terminology_handbook

    definitions: dict[str, str] = {}
    for concept in load_terminology_handbook().concepts:
        if concept.lifecycle is not ConceptLifecycle.APPROVED:
            continue
        modelo_id = concept.concept_id.removeprefix("modelo-")
        if modelo_id == concept.concept_id:
            continue
        for section in concept.languages:
            if section.language is not language:
                continue
            text = (section.definition or "").strip()
            if text:
                definitions[modelo_id] = text
    return definitions


# ── Card rendering ───────────────────────────────────────────────────────────


def _localised(record: CasillaSearchRecord, language: OutputLanguage) -> tuple[str | None, str | None]:
    """Return ``(label, help)`` for the build language, or ``None`` where unauthored.

    There is deliberately no fallback: a casilla with no label in the build
    language renders without a label rather than borrowing another language's.
    """

    def _clean(value: str | None) -> str | None:
        return value if value is not None and value.strip() else None

    return _clean(record.descriptions.get(language)), _clean(record.localized_help.get(language.value))


def _join_references(references: list[str]) -> str:
    """Join rendered box links as a readable list ("01, 02 and 05")."""
    if len(references) <= 1:
        return "".join(references)
    return ", ".join(references[:-1]) + " and " + references[-1]


def _fill_explanation(
    record: CasillaSearchRecord,
    facts: CasillaFacts | None,
    numbers_by_id: Mapping[str, str],
) -> list[str]:
    """Render the "how this box gets filled" answer, the substance of an entry.

    Computed casillas name the boxes they derive FROM, each linked to its own
    entry, because a derivation is the one honest description of meaning the
    schema can give. Bound casillas name the source that fills them.
    """
    input_kind = record.input_kind.value
    headline = _INPUT_KIND_DISPLAY.get(input_kind, _humanise_token(input_kind))
    lines = [
        f'<div class="casilla-fill casilla-fill--{html.escape(input_kind, quote=True)}">',
        f'<span class="casilla-fill__kind">{html.escape(headline)}</span>',
    ]

    detail: str | None = None
    if facts is not None and facts.binding_sources:
        phrases = [_BINDING_SOURCE_DISPLAY.get(source, _humanise_token(source)) for source in facts.binding_sources]
        detail = phrases[0] if len(phrases) == 1 else f"{phrases[0]}, or {' or '.join(phrases[1:])}"
    if detail is not None:
        lines.append(f'<span class="casilla-fill__detail">{html.escape(detail)}</span>')

    if facts is not None and facts.formula_inputs:
        references = []
        for casilla_id in facts.formula_inputs:
            number = numbers_by_id.get(casilla_id)
            anchor = casilla_page_anchor(record.modelo, casilla_id)
            text = number if number is not None else casilla_id
            references.append(
                f'<a class="casilla-derives-from__ref" href="#{html.escape(anchor, quote=True)}"'
                f' title="{html.escape(casilla_id, quote=True)}">{html.escape(text)}</a>',
            )
        lines.append('<span class="casilla-fill__detail">from</span>')
        lines.append(f'<span class="casilla-derives-from">{_join_references(references)}</span>')
    lines.append("</div>")
    return lines


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


def _constraint_phrases(constraints: CasillaConstraints | None) -> list[str]:
    """Read the authored value constraints as what a filer may enter."""
    if constraints is None:
        return []
    phrases: list[str] = []
    minimum, maximum = constraints.min_value, constraints.max_value
    if minimum is not None and maximum is not None:
        phrases.append(f"Between {minimum} and {maximum}")
    elif minimum is not None:
        phrases.append(f"At least {minimum}")
    elif maximum is not None:
        phrases.append(f"At most {maximum}")
    elif constraints.sign in _SIGN_DISPLAY:
        phrases.append(_SIGN_DISPLAY[constraints.sign])

    if constraints.min_length is not None and constraints.max_length is not None:
        phrases.append(f"{constraints.min_length} to {constraints.max_length} characters")
    elif constraints.max_length is not None:
        phrases.append(f"Up to {constraints.max_length} characters")
    elif constraints.min_length is not None:
        phrases.append(f"At least {constraints.min_length} characters")

    if constraints.enum:
        phrases.append("One of: " + ", ".join(str(value) for value in constraints.enum))
    return phrases


def _fact_chips(record: CasillaSearchRecord, facts: CasillaFacts | None) -> list[str]:
    """The scannable filing facts: what to type, whether it is required, where it sits."""
    chips: list[str] = []
    data_type = _DATA_TYPE_DISPLAY.get(record.data_type, _humanise_token(record.data_type))
    chips.append(f'<li class="casilla-fact">{html.escape(data_type)}</li>')
    if record.required:
        chips.append('<li class="casilla-fact casilla-fact--required">Required</li>')
    for phrase in _constraint_phrases(facts.constraints if facts else None):
        chips.append(f'<li class="casilla-fact">{html.escape(phrase)}</li>')
    if record.segmento:
        chips.append(f'<li class="casilla-fact">Segmento {html.escape(record.segmento)}</li>')
    if facts is not None and facts.internal_only:
        chips.append('<li class="casilla-fact casilla-fact--internal">Not on the official form</li>')
    return chips


def _internals_block(record: CasillaSearchRecord, box_number: str) -> list[str]:
    """The registry's own identifiers, demoted into a collapsed disclosure.

    Machine vocabulary a taxpayer never reads, kept on the page because an
    operator debugging a value needs the exact ids the registry carries.
    """
    rows: list[tuple[str, str]] = [("Casilla id", f"<code>{html.escape(str(record.casilla_id))}</code>")]
    if record.number != box_number:
        rows.append(("Record-design number", f"<code>{html.escape(record.number)}</code>"))
    if record.semantic_role:
        rows.append(("Semantic role", f"<code>{html.escape(record.semantic_role)}</code>"))
    if record.binding is not None:
        rows.append(("Binding", f"<code>{html.escape(str(record.binding))}</code>"))
    if record.formula_id is not None:
        rows.append(("Formula", f"<code>{html.escape(str(record.formula_id))}</code>"))
    rows.append(("Registry section", f"<code>{html.escape('.'.join(record.section) or 'general')}</code>"))
    if record.source_refs:
        rows.append(("Sources", " ".join(f"<code>{html.escape(ref)}</code>" for ref in record.source_refs)))
    if record.source_revisions:
        rows.append(("Revisions", " ".join(f"<code>{html.escape(rev)}</code>" for rev in record.source_revisions)))
    lines = [
        '<details class="casilla-card__internals">',
        "<summary>Registry identifiers</summary>",
        '<dl class="casilla-internals">',
    ]
    lines.extend(f"<dt>{html.escape(term)}</dt><dd>{value}</dd>" for term, value in rows)
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
    label, help_text = _localised(record, language)
    box_number = _box_number(record, facts)

    lines = [
        f'<article class="casilla-card" id="{html.escape(anchor, quote=True)}">',
        '<header class="casilla-card__head">',
        f'<span class="casilla-card__number">{html.escape(box_number)}</span>',
    ]
    if label is not None:
        lines.append(f'<h3 class="casilla-card__title">{html.escape(label)}</h3>')
    lines.append("</header>")
    if help_text:
        lines.append(f'<p class="casilla-card__help">{html.escape(help_text)}</p>')
    lines.extend(_fill_explanation(record, facts, numbers_by_id))
    chips = _fact_chips(record, facts)
    if chips:
        lines.append('<ul class="casilla-card__facts">')
        lines.extend(chips)
        lines.append("</ul>")
    legal_lines, resolved = ([], 0) if not record.legal_refs else _legal_list(record.legal_refs, links, "Legal basis")
    lines.extend(legal_lines)
    lines.extend(_internals_block(record, box_number))
    lines.append("</article>")
    return _raw_html(lines), anchor, tuple(record.legal_refs), resolved


# ── Page rendering ───────────────────────────────────────────────────────────


def _page_header(
    modelo: str,
    overview: ModeloOverview | None,
    records: tuple[CasillaSearchRecord, ...],
    sections: list[tuple[tuple[str, ...], int]],
    links: dict[str, _LegalLink],
) -> tuple[str, int]:
    """Render what this modelo IS, then the jump list over its sections."""
    lines = ['<div class="modelo-overview">']
    resolved = 0
    if overview is not None:
        lines.append(f'<p class="modelo-overview__name">{html.escape(overview.official_name)}</p>')
        if overview.definition:
            lines.append(f'<p class="modelo-overview__definition">{html.escape(overview.definition)}</p>')

    counted: dict[str, int] = {}
    for record in records:
        counted[record.input_kind.value] = counted.get(record.input_kind.value, 0) + 1
    facts: list[str] = []
    if overview is not None:
        facts.append(_token_display(overview.tax_domain))
        facts.append(_CADENCE_DISPLAY.get(overview.cadence, _humanise_token(overview.cadence)))
    facts.append(f"{len(records)} casillas in {len(sections)} sections")
    facts.extend(
        f"{count} {_INPUT_KIND_COUNT_DISPLAY.get(kind, _humanise_token(kind).lower())}"
        for kind, count in sorted(counted.items())
    )
    lines.append('<ul class="modelo-overview__facts">')
    lines.extend(f'<li class="casilla-fact">{html.escape(fact)}</li>' for fact in facts)
    lines.append("</ul>")

    if overview is not None and overview.legal_refs:
        legal_lines, resolved = _legal_list(overview.legal_refs, links, "Established by")
        lines.extend(legal_lines)
    lines.append("</div>")

    if len(sections) > 1:
        lines.append('<nav class="casilla-section-nav" aria-label="Sections of this modelo">')
        lines.append("<ul>")
        for section, count in sections:
            lines.append(
                f'<li><a href="#{html.escape(_section_anchor(section), quote=True)}">'
                f'{html.escape(_section_display(section))}<span class="casilla-section-nav__count">{count}</span>'
                "</a></li>",
            )
        lines.extend(["</ul>", "</nav>"])
    return _raw_html(lines), resolved


def _render_modelo_page(
    modelo: str,
    records: tuple[CasillaSearchRecord, ...],
    links: dict[str, _LegalLink],
    language: OutputLanguage,
    schema: CompiledSchema,
) -> tuple[CasillaPage, int]:
    """Render one modelo page grouped by section; return the page and its legal-link count."""
    header = (
        "..\n"
        "   Generated by dev/docs/casilla_reference.py from the registry casilla\n"
        "   projection. Do not edit by hand; regenerate.\n\n"
    )
    overview = schema.modelos.get(modelo)
    heading = f"Modelo {modelo}" if overview is None else f"Modelo {modelo} — {overview.title}"
    title = _rst_heading(_rst_escape(heading), "=")

    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.section, []).append(record)
    section_counts = [(section, len(items)) for section, items in grouped.items()]

    # Two distinct registry section paths can fold to one anchor slug (``a_b``
    # and ``a-b`` both give ``section-a-b``), which would ship a page whose jump
    # target is ambiguous. Refuse it the same way a casilla anchor collision is
    # refused, never silently emitting the duplicate id.
    section_anchors = [_section_anchor(section) for section, _count in section_counts]
    if len(set(section_anchors)) != len(section_anchors):
        duplicates = sorted({anchor for anchor in section_anchors if section_anchors.count(anchor) > 1})
        raise CasillaReferenceError(
            f"modelo {modelo}: duplicate section anchor(s) {duplicates}; "
            "registry section paths must fold to a unique per-page anchor"
        )

    numbers_by_id = {
        str(record.casilla_id): _box_number(record, schema.casillas.get((modelo, str(record.casilla_id))))
        for record in records
    }
    page_header, legal_links = _page_header(modelo, overview, records, section_counts, links)
    blocks: list[str] = [header + title, page_header]
    anchors: list[str] = []
    seen: set[str] = set()
    rendered_legal_refs: dict[str, tuple[str, ...]] = {}
    for section, section_records in grouped.items():
        blocks.append(_rst_heading(_rst_escape(_section_display(section)), "-"))
        blocks.append(_raw_html([f'<span class="casilla-section-anchor" id="{_section_anchor(section)}"></span>']))
        for record in section_records:
            facts = schema.casillas.get((modelo, str(record.casilla_id)))
            entry, anchor, refs, resolved = _render_entry(record, links, language, facts, numbers_by_id)
            if anchor in seen:
                raise CasillaReferenceError(
                    f"modelo {modelo}: duplicate casilla anchor {anchor!r} "
                    f"(casilla {record.casilla_id!r}); ids must fold to a unique per-page anchor"
                )
            seen.add(anchor)
            anchors.append(anchor)
            rendered_legal_refs[anchor] = refs
            legal_links += resolved
            blocks.append(entry)

    rst = "\n".join(blocks).rstrip("\n") + "\n"
    page = CasillaPage(
        modelo=modelo,
        output_relpath=str(casilla_page_relpath(modelo)).replace("\\", "/"),
        rst=rst,
        anchors=tuple(anchors),
        rendered_legal_refs=rendered_legal_refs,
    )
    return page, legal_links


def _render_index(pages: tuple[CasillaPage, ...], schema: CompiledSchema) -> str:
    """Render the casilla reference toctree index over the per-modelo pages."""
    header = "..\n   Generated by dev/docs/casilla_reference.py. Do not edit by hand; regenerate.\n\n"
    title = _rst_heading("Casilla reference", "=")
    intro = (
        "One page per modelo. Every casilla says how it is filled - you enter it,\n"
        "it is calculated from other boxes, or it is filled from your records -\n"
        "where it sits on the official form, and the law that establishes it.\n\n"
    )
    lines = [".. toctree::", "   :maxdepth: 1", ""]
    for page in pages:
        overview = schema.modelos.get(page.modelo)
        label = f"Modelo {page.modelo}" if overview is None else f"Modelo {page.modelo} — {overview.title}"
        lines.append(f"   {_rst_escape(label)} <{page.modelo}>")
    return header + title + "\n" + intro + "\n".join(lines) + "\n"


def render_casilla_reference(
    repo_root: Path,
    records: tuple[CasillaSearchRecord, ...] | None = None,
    *,
    language: OutputLanguage | None = None,
    schema: CompiledSchema | None = None,
) -> CasillaReferenceResult:
    """Render every modelo's casilla reference page and the index.

    Args:
        repo_root: Repository root (for the legal-catalogue read).
        records: Optional pre-projected casilla records; defaults to the full
            registry projection. Injectable so the parity gate and a narrowed
            test can drive the same renderer deterministically.
        language: The one language the pages render in; defaults to the build
            language signal so a localized build is single-language end to end.
        schema: Optional pre-compiled schema facts; defaults to compiling them
            from the bundled authority. Pass :data:`EMPTY_SCHEMA` to render from
            the records alone with no registry read.

    Returns:
        A :class:`CasillaReferenceResult` with one :class:`CasillaPage` per
        modelo, the index page path, and the render counts.
    """
    links = _legal_links(repo_root.resolve())
    resolved = records if records is not None else project_casilla_search_records()[0]
    resolved_language = language if language is not None else _display_language()
    resolved_schema = schema if schema is not None else compile_schema(resolved, resolved_language)

    by_modelo: OrderedDict[str, list[CasillaSearchRecord]] = OrderedDict()
    for record in resolved:
        by_modelo.setdefault(record.modelo.value, []).append(record)

    pages: list[CasillaPage] = []
    legal_links = 0
    casilla_count = 0
    for modelo in sorted(by_modelo):
        page, page_legal_links = _render_modelo_page(
            modelo,
            tuple(by_modelo[modelo]),
            links,
            resolved_language,
            resolved_schema,
        )
        pages.append(page)
        legal_links += page_legal_links
        casilla_count += len(page.anchors)

    index_relpath = f"{CASILLA_REFERENCE_DIR}/index.rst"
    return CasillaReferenceResult(
        pages=tuple(pages),
        index_relpath=index_relpath,
        modelo_count=len(pages),
        casilla_count=casilla_count,
        legal_links=legal_links,
    )


def generate_casilla_reference(docs_root: Path) -> CasillaReferenceResult:
    """Materialise the generated casilla reference pages under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.glossary_reference.generate_glossary_reference`: it
    renders every modelo page plus the toctree index and writes them to the
    generated (gitignored, uncommitted) location, returning a summary. Wired at
    the ``builder-inited`` seam so the pages exist before Sphinx reads the tree.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).

    Returns:
        A :class:`CasillaReferenceResult` summarising the render.
    """
    repo_root = docs_root.resolve().parent
    records = project_casilla_search_records()[0]
    language = _display_language()
    schema = compile_schema(records, language)
    result = render_casilla_reference(repo_root, records=records, language=language, schema=schema)
    out_dir = docs_root / CASILLA_REFERENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_if_changed(out_dir / "index.rst", _render_index(result.pages, schema))
    for page in result.pages:
        _write_if_changed(docs_root / page.output_relpath, page.rst)
    return result


def _write_if_changed(path: Path, rst: str) -> None:
    """Write the page only when its content changed, forcing LF newlines.

    The default newline translation emits CRLF on Windows, which doc8's
    CheckCarriageReturn (D004) then flags on every regeneration; force LF so the
    generated page is byte-identical across platforms (the glossary precedent).
    """
    if not (path.is_file() and path.read_text(encoding=_UTF_8) == rst):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rst, encoding=_UTF_8, newline="\n")

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

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8
from ._locale_chrome import docs_chrome
from .legal_reference import legal_reference_target, load_legal_provisions
from .terminology import CasillaSearchRecord, project_casilla_search_records
from .terminology._casilla_anchor import CASILLA_REFERENCE_DIR, casilla_page_anchor, casilla_page_relpath

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
    from cadrumo.domain.calculations.registry.schema import FormulaDefinition, ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition

    from .legal_reference import LegalProvisionRecord

_UTF_8 = UTF_8


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

    #: Human reading of the whole provision ("Ley 37/1992, art. 92").
    label: str
    #: The instrument alone ("Ley 37/1992"), so sibling provisions group under it.
    instrument: str
    #: The provision within that instrument ("art. 92"), or empty for a law-level row.
    provision: str
    #: Site-relative target of the generated legal-reference destination.
    target: str


#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value reaching an RST heading is backslash-escaped or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run. Card
#: bodies are raw HTML and are HTML-escaped instead.
_RST_SPECIAL = "\\`*_|[]"

#: The catalogue namespace holding every display string this surface renders.
#: Nothing user-visible is authored as a Python literal: the vocabulary lives in
#: the four shared catalogues, Spanish first as the authoritative source, and is
#: resolved per build language through the shared
#: :func:`~dev.docs._locale_chrome.docs_chrome` resolver the sibling generated
#: surfaces use, so all three read chrome through one authority.
_DISPLAY_PREFIX: Final[str] = "docs.casilla"

#: The one exception, and it is not chrome: the official Spanish name of a legal
#: instrument. AEAT and BOE publish "Ley 37/1992" and "Real Decreto 1624/1992"
#: under those names in every language, exactly as a modelo's official name
#: stays Spanish, so translating them would name a norm that does not exist. The
#: DESCRIPTIVE kinds - AEAT's own dictionaries, manuals, record designs - are
#: not instrument names and live in the catalogue under ``legal_kind.*``.
_LEGAL_INSTRUMENT_NAMES: Final[dict[str, str]] = {
    "acuerdo_internacional": "Convenio",
    "ley": "Ley",
    "orden": "Orden",
    "real_decreto": "Real Decreto",
    "real_decreto_legislativo": "Real Decreto Legislativo",
    "real_decreto_ley": "Real Decreto-ley",
    "reglamento": "Reglamento",
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


#: Display keys with no enumeration behind them: page chrome and the
#: constraint phrasings. Everything else is derived from the schema's own closed
#: value sets by :func:`display_locale_keys`, so a new enum member surfaces as a
#: missing-string failure rather than as silently absent copy.
_UNENUMERATED_DISPLAY_KEYS: Final[tuple[str, ...]] = (
    "value_range.between",
    "value_range.at_least",
    "value_range.at_most",
    "length.between",
    "length.at_least",
    "length.at_most",
    "value_enum",
    "chrome.legal_basis",
    "chrome.established_by",
    "chrome.registry_identifiers",
    "chrome.required",
    "chrome.segmento",
    "chrome.not_on_official_form",
    "chrome.derived_from",
    "chrome.sections_nav",
    "chrome.casilla_id",
    "chrome.record_design_number",
    "chrome.semantic_role",
    "chrome.binding",
    "chrome.formula",
    "chrome.registry_section",
    "chrome.sources",
    "chrome.revisions",
    "chrome.casilla_count",
    "chrome.alternative_join",
    "chrome.list_and",
    "chrome.general_section",
    "chrome.index_title",
    "chrome.index_intro",
)


def display_locale_keys() -> tuple[str, ...]:
    """Every catalogue key this surface can render, fully qualified.

    One derivation serving two consumers: the gate that proves each key resolves
    in all four languages, and the locale scaffold's registration (the AST key
    scan walks ``src/cadrumo`` only, so keys this dev-side surface consumes are
    invisible to it and would be pruned as stale without an explicit
    registration).

    The enum-backed families are read from the schema's own closed value sets
    rather than listed, so adding a ``BindingSourceKind`` member or a
    ``data_type`` immediately demands its string instead of rendering nothing.
    """
    from typing import get_args

    from cadrumo.core.aggregation import BindingSourceKind
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition

    from .legal_reference import load_legal_provisions

    def _literal_values(
        model: type[CasillaDefinition | ModeloDefinition | CasillaConstraints],
        field: str,
    ) -> tuple[str, ...]:
        field_info = model.model_fields.get(field)
        if field_info is None:
            return ()
        return tuple(str(value) for value in get_args(field_info.annotation))

    keys: list[str] = [f"{_DISPLAY_PREFIX}.{suffix}" for suffix in _UNENUMERATED_DISPLAY_KEYS]
    for member in InputKind:
        keys.append(f"{_DISPLAY_PREFIX}.input_kind.{member.value}")
        keys.append(f"{_DISPLAY_PREFIX}.input_kind_count.{member.value}")
    keys.extend(f"{_DISPLAY_PREFIX}.binding_source.{member.value}" for member in BindingSourceKind)
    keys.extend(f"{_DISPLAY_PREFIX}.data_type.{value}" for value in _literal_values(CasillaDefinition, "data_type"))
    keys.extend(f"{_DISPLAY_PREFIX}.cadence.{value}" for value in _literal_values(ModeloDefinition, "cadence"))
    keys.extend(
        f"{_DISPLAY_PREFIX}.value_range.{value}"
        for value in _literal_values(CasillaConstraints, "sign")
        if value != "any"
    )
    kinds = {provision.kind for provision in load_legal_provisions(_repo_root())}
    keys.extend(f"{_DISPLAY_PREFIX}.legal_kind.{kind}" for kind in sorted(kinds) if kind not in _LEGAL_INSTRUMENT_NAMES)
    return tuple(dict.fromkeys(keys))


def _repo_root() -> Path:
    """The repository checkout this dev-side module lives in."""
    return REPO_ROOT


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


def _section_display(section: tuple[str, ...], language: OutputLanguage) -> str:
    """The human display for a registry section path, token by token."""
    return " › ".join(_token_display(part) for part in section if part) or docs_chrome(
        "docs.casilla.chrome.general_section", language
    )


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


def _legal_provision_display(
    legal_id: str,
    provision: LegalProvisionRecord,
    language: OutputLanguage,
) -> tuple[str, str]:
    """Split one catalogue provision into ``(instrument, provision)`` for display.

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

    instrument = _LEGAL_INSTRUMENT_NAMES.get(provision.kind)
    kind_display = (
        instrument if instrument is not None else docs_chrome(f"docs.casilla.legal_kind.{provision.kind}", language)
    )
    name = " ".join(part for part in (kind_display, qualifier) if part)
    if numeral:
        name = f"{name}{separator if qualifier else ' '}{numeral}"
    name = name.strip()
    if not name:
        return legal_id, ""

    # The authored ``section`` prose is the most human reading of a provision;
    # ``article`` is next (numeric articles take the ``art.`` prefix, worded
    # ones already read as prose); the id's own provision half is the floor.
    if provision.section:
        return name, provision.section
    if provision.article:
        prefix = "art. " if provision.article[:1].isdigit() else ""
        return name, f"{prefix}{provision.article}"
    if provision_part:
        return name, provision_part.replace("-", " ")
    return name, ""


@lru_cache(maxsize=8)
def _legal_links(repo_root: Path, language: OutputLanguage) -> dict[str, _LegalLink]:
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
        instrument, within = _legal_provision_display(provision.legal_id, provision, language)
        links[provision.legal_id] = _LegalLink(
            label=f"{instrument}, {within}" if within else instrument,
            instrument=instrument,
            provision=within,
            target=_relative_to_casilla_page(target),
        )
    return links


def _relative_to_casilla_page(site_target: str) -> str:
    """Rewrite a site-relative target as a link relative to a casilla page."""
    page, _, fragment = site_target.partition("#")
    relative = posixpath.relpath(page, CASILLA_REFERENCE_DIR)
    return f"{relative}#{fragment}" if fragment else relative


def _legal_list(refs: tuple[str, ...], links: dict[str, _LegalLink], label: str) -> tuple[list[str], int]:
    """Render the legal basis grouped by instrument, returning lines and link count.

    Four refs into one norm used to print that norm's name four times, which is
    what made the grounding compete with the answer above it. Grouping states
    the instrument once and lists its provisions after it, so the block reads as
    one citation rather than as a row of equally-weighted tags.
    """
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    resolved = 0
    for ref in refs:
        link = links.get(ref)
        if link is None:
            grouped.setdefault("", []).append(
                f'<span class="casilla-legal-ref casilla-legal-ref--raw">{html.escape(ref)}</span>',
            )
            continue
        resolved += 1
        anchor = (
            f'<a class="casilla-legal-ref" href="{html.escape(link.target, quote=True)}"'
            f' title="{html.escape(ref, quote=True)}">{html.escape(link.provision or link.instrument)}</a>'
        )
        grouped.setdefault(link.instrument, []).append(anchor)

    items: list[str] = []
    for instrument, anchors in grouped.items():
        name = f'<span class="casilla-legal-name">{html.escape(instrument)}</span> ' if instrument else ""
        items.append(f"<li>{name}{', '.join(anchors)}</li>")
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
    from cadrumo.domain.calculations.registry.authority import bundled_authority
    from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs

    resolved = authority if authority is not None else bundled_authority()
    modelos = {modelo.id: modelo for modelo in resolved.modelos}

    facts: dict[tuple[str, str], CasillaFacts] = {}
    revision_cache: dict[
        tuple[str, str],
        tuple[Mapping[str, CasillaDefinition], Mapping[str, FormulaDefinition], Mapping[str, str]],
    ] = {}

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
            formulas: dict[str, FormulaDefinition] = {}
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
    modelos: Mapping[str, ModeloDefinition],
) -> dict[str, ModeloOverview]:
    """Compile each modelo's identity, cadence, grounding and curated definition."""
    definitions = _handbook_definitions(language)
    overviews: dict[str, ModeloOverview] = {}
    for modelo_id in sorted(modelo_ids):
        modelo = modelos.get(modelo_id)
        if modelo is None:
            continue
        overviews[modelo_id] = ModeloOverview(
            title=modelo.get_title(language.value),
            official_name=modelo.get_official_name(language.value),
            definition=definitions.get(modelo_id),
            tax_domain=str(modelo.tax_domain),
            cadence=str(modelo.cadence),
            legal_refs=tuple(str(ref) for ref in modelo.legal_refs),
        )
    return overviews


def _handbook_definitions(language: OutputLanguage) -> dict[str, str]:
    """``modelo id -> curated definition`` for approved concepts, in ONE language.

    Only an ``approved`` concept that authored a definition in the build language
    contributes; a draft concept, or one translated into other locales but not
    this one, contributes nothing rather than a substituted string.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

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
        f'<p class="casilla-fill casilla-fill--{html.escape(input_kind, quote=True)}">',
        f'<span class="casilla-fill__kind">{html.escape(headline)}</span>',
    ]

    detail: str | None = None
    if facts is not None and facts.binding_sources:
        phrases = [docs_chrome(f"docs.casilla.binding_source.{source}", language) for source in facts.binding_sources]
        alternative = docs_chrome("docs.casilla.chrome.alternative_join", language)
        detail = phrases[0] if len(phrases) == 1 else alternative.join(phrases)
    if detail is not None:
        lines.append(f'<span class="casilla-fill__detail">{html.escape(detail)}</span>')

    if facts is not None and facts.formula_inputs:
        references: list[str] = []
        for casilla_id in facts.formula_inputs:
            number = numbers_by_id.get(casilla_id)
            anchor = casilla_page_anchor(record.modelo, casilla_id)
            text = number if number is not None else casilla_id
            references.append(
                f'<a class="casilla-derives-from__ref" href="#{html.escape(anchor, quote=True)}"'
                f' title="{html.escape(casilla_id, quote=True)}">{html.escape(text)}</a>',
            )
        derived = docs_chrome("docs.casilla.chrome.derived_from", language)
        lines.append(f'<span class="casilla-fill__detail">{html.escape(derived)}</span>')
        lines.append(f'<span class="casilla-derives-from">{_join_references(references, language)}</span>')
    # What the filer types belongs in this sentence, not in a pill of its own:
    # every casilla has a value shape, so a pill for it carried no signal and
    # only crowded the ones that do (required, a range, a segmento).
    data_type = docs_chrome(f"docs.casilla.data_type.{record.data_type}", language)
    lines.append(f'<span class="casilla-fill__shape">{html.escape(data_type)}</span>')
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
    minimum, maximum = constraints.min_value, constraints.max_value
    if minimum is not None and maximum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.between", language, min=minimum, max=maximum))
    elif minimum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.at_least", language, min=minimum))
    elif maximum is not None:
        phrases.append(docs_chrome("docs.casilla.value_range.at_most", language, max=maximum))
    elif constraints.sign != "any":
        phrases.append(docs_chrome(f"docs.casilla.value_range.{constraints.sign}", language))

    if constraints.min_length is not None and constraints.max_length is not None:
        phrases.append(
            docs_chrome("docs.casilla.length.between", language, min=constraints.min_length, max=constraints.max_length)
        )
    elif constraints.max_length is not None:
        phrases.append(docs_chrome("docs.casilla.length.at_most", language, max=constraints.max_length))
    elif constraints.min_length is not None:
        phrases.append(docs_chrome("docs.casilla.length.at_least", language, min=constraints.min_length))

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
        chips.append(f'<li class="casilla-fact casilla-fact--required">{html.escape(required)}</li>')
    for phrase in _constraint_phrases(facts.constraints if facts else None, language):
        chips.append(f'<li class="casilla-fact">{html.escape(phrase)}</li>')
    if record.segmento:
        segmento = docs_chrome("docs.casilla.chrome.segmento", language, segmento=record.segmento)
        chips.append(f'<li class="casilla-fact">{html.escape(segmento)}</li>')
    if facts is not None and facts.internal_only:
        internal = docs_chrome("docs.casilla.chrome.not_on_official_form", language)
        chips.append(f'<li class="casilla-fact casilla-fact--internal">{html.escape(internal)}</li>')
    return chips


def _internals_block(record: CasillaSearchRecord, box_number: str, language: OutputLanguage) -> list[str]:
    """The registry's own identifiers, demoted into a collapsed disclosure.

    Machine vocabulary a taxpayer never reads, kept on the page because an
    operator debugging a value needs the exact ids the registry carries.
    """
    rows: list[tuple[str, str]] = [
        (
            docs_chrome("docs.casilla.chrome.casilla_id", language),
            f"<code>{html.escape(str(record.casilla_id))}</code>",
        ),
    ]
    if record.number != box_number:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.record_design_number", language),
                f"<code>{html.escape(record.number)}</code>",
            )
        )
    if record.semantic_role:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.semantic_role", language),
                f"<code>{html.escape(record.semantic_role)}</code>",
            )
        )
    if record.binding is not None:
        rows.append(
            (docs_chrome("docs.casilla.chrome.binding", language), f"<code>{html.escape(str(record.binding))}</code>")
        )
    if record.formula_id is not None:
        rows.append(
            (
                docs_chrome("docs.casilla.chrome.formula", language),
                f"<code>{html.escape(str(record.formula_id))}</code>",
            )
        )
    registry_section = ".".join(record.section) or "general"
    rows.append(
        (docs_chrome("docs.casilla.chrome.registry_section", language), f"<code>{html.escape(registry_section)}</code>")
    )
    if record.source_refs:
        joined = " ".join(f"<code>{html.escape(ref)}</code>" for ref in record.source_refs)
        rows.append((docs_chrome("docs.casilla.chrome.sources", language), joined))
    if record.source_revisions:
        joined = " ".join(f"<code>{html.escape(rev)}</code>" for rev in record.source_revisions)
        rows.append((docs_chrome("docs.casilla.chrome.revisions", language), joined))
    lines = [
        '<details class="casilla-card__internals">',
        f"<summary>{html.escape(docs_chrome('docs.casilla.chrome.registry_identifiers', language))}</summary>",
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
        lines.append(f'<h3 class="casilla-card__title">{html.escape(" ".join(label.split()))}</h3>')
    lines.append("</header>")
    description = _description(help_text, box_number)
    if description:
        lines.append(f'<p class="casilla-card__help">{html.escape(" ".join(description.split()))}</p>')
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
    return _raw_html(lines), anchor, tuple(record.legal_refs), resolved


# ── Page rendering ───────────────────────────────────────────────────────────


def _box_sort_key(box_number: str) -> tuple[int, int, str]:
    """Order boxes the way the printed form does, and name the two kinds apart.

    Box numbers are strings in the schema and have to be: leading zeros are
    significant and some boxes carry no number at all. Sorting them as strings
    puts 150 between 15 and 16, so a reader scanning for box 16 finds it six
    entries late. This reads a leading integer run where there is one and falls
    back to the string, which also separates numbered boxes from named ones -
    the first element of the key is the group.
    """
    leading = re.match(r"^(\d+)", box_number)
    if leading is not None:
        return (0, int(leading.group(1)), box_number)
    return (1, 0, box_number)


def _casilla_index(
    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]],
    schema: CompiledSchema,
    modelo: str,
    language: OutputLanguage,
) -> list[str]:
    """Render a jump index over every casilla on the page.

    One chip per casilla, carrying its box number and its label as the hover
    title, grouped under the section it belongs to. Modelo 100 renders 2258 of
    them, so the chips flow rather than stack and the whole index scrolls inside
    a bounded box: a reader reaches any casilla without paging through the form,
    and the index never pushes the first card off the screen.
    """
    heading = docs_chrome("docs.casilla.chrome.casilla_index", language)
    hint = docs_chrome("docs.casilla.chrome.casilla_index_hint", language)
    lines = [
        f'<nav class="casilla-index" aria-label="{html.escape(heading, quote=True)}">',
        '<p class="casilla-index__lead">'
        f'<span class="casilla-index__title">{html.escape(heading)}</span> '
        f'<span class="casilla-index__hint">{html.escape(hint)}</span>'
        "</p>",
        '<div class="casilla-index__scroll">',
    ]
    for section, section_records in grouped.items():
        lines.append('<div class="casilla-index__group">')
        lines.append(
            f'<a class="casilla-index__section" href="#{html.escape(_section_anchor(section), quote=True)}">'
            f"{html.escape(_section_display(section, language))}</a>",
        )
        numbered: list[str] = []
        named: list[str] = []
        for record in section_records:
            facts = schema.casillas.get((modelo, str(record.casilla_id)))
            label, _help = _localised(record, language)
            anchor = casilla_page_anchor(record.modelo, record.casilla_id)
            title = html.escape(" ".join((label or str(record.casilla_id)).split()), quote=True)
            box = _box_number(record, facts)
            chip = (
                f'<a class="casilla-index__chip" href="#{html.escape(anchor, quote=True)}" title="{title}">'
                f"{html.escape(box)}</a>"
            )
            # A casilla with no printed number falls back to its id, which is
            # five times the width of a number and would tear the grid apart.
            # The two kinds get two affordances rather than one clamped chip.
            (numbered if _box_sort_key(box)[0] == 0 else named).append(chip)
        if numbered:
            lines.append('<div class="casilla-index__chips">')
            lines.extend(numbered)
            lines.append("</div>")
        if named:
            lines.append('<div class="casilla-index__named">')
            lines.extend(named)
            lines.append("</div>")
        lines.append("</div>")
    lines.extend(["</div>", "</nav>"])
    return lines


def _page_header(
    modelo: str,
    overview: ModeloOverview | None,
    records: tuple[CasillaSearchRecord, ...],
    sections: list[tuple[tuple[str, ...], int]],
    links: dict[str, _LegalLink],
    language: OutputLanguage,
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
        facts.append(docs_chrome(f"docs.casilla.cadence.{overview.cadence}", language))
    facts.append(
        docs_chrome("docs.casilla.chrome.casilla_count", language, casillas=len(records), sections=len(sections))
    )
    facts.extend(
        f"{count} {docs_chrome(f'docs.casilla.input_kind_count.{kind}', language)}"
        for kind, count in sorted(counted.items())
    )
    lines.append('<ul class="modelo-overview__facts">')
    lines.extend(f'<li class="casilla-fact">{html.escape(fact)}</li>' for fact in facts)
    lines.append("</ul>")

    if overview is not None and overview.legal_refs:
        legal_lines, resolved = _legal_list(
            overview.legal_refs, links, docs_chrome("docs.casilla.chrome.established_by", language)
        )
        lines.extend(legal_lines)
    lines.append("</div>")

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
    heading = (
        f"Modelo {modelo}"
        if overview is None
        else docs_chrome("docs.casilla.chrome.page_heading", language, modelo=modelo, title=overview.title)
    )
    title = _rst_heading(_rst_escape(heading), "=")

    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.section, []).append(record)

    # Within a section, read in the order the printed form numbers its boxes.
    # Sorting here rather than in the index keeps the cards and the index in ONE
    # order: sorting only the index would send a reader clicking 16 to a card
    # sitting after 155. Section order itself is the registry's, which is the
    # official structure.
    def _order(record: CasillaSearchRecord) -> tuple[int, int, str]:
        return _box_sort_key(_box_number(record, schema.casillas.get((modelo, str(record.casilla_id)))))

    for items in grouped.values():
        items.sort(key=_order)
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
    page_header, legal_links = _page_header(modelo, overview, records, section_counts, links, language)
    blocks: list[str] = [header + title, page_header, _raw_html(_casilla_index(grouped, schema, modelo, language))]
    anchors: list[str] = []
    seen: set[str] = set()
    rendered_legal_refs: dict[str, tuple[str, ...]] = {}
    for section, section_records in grouped.items():
        blocks.append(_rst_heading(_rst_escape(_section_display(section, language)), "-"))
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


def _render_index(pages: tuple[CasillaPage, ...], schema: CompiledSchema, language: OutputLanguage) -> str:
    """Render the casilla reference toctree index over the per-modelo pages."""
    header = "..\n   Generated by dev/docs/casilla_reference.py. Do not edit by hand; regenerate.\n\n"
    title = _rst_heading(_rst_escape(docs_chrome("docs.casilla.chrome.index_title", language)), "=")
    intro = _rst_escape(docs_chrome("docs.casilla.chrome.index_intro", language)) + "\n\n"
    lines = [".. toctree::", "   :maxdepth: 1", ""]
    for page in pages:
        overview = schema.modelos.get(page.modelo)
        label = (
            f"Modelo {page.modelo}"
            if overview is None
            else docs_chrome("docs.casilla.chrome.page_heading", language, modelo=page.modelo, title=overview.title)
        )
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
    resolved_language = language if language is not None else _display_language()
    links = _legal_links(repo_root.resolve(), resolved_language)
    resolved = records if records is not None else project_casilla_search_records()[0]
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


def generate_casilla_reference(docs_root: Path, *, repo_root: Path | None = None) -> CasillaReferenceResult:
    """Materialise the generated casilla reference pages under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.glossary_reference.generate_glossary_reference`: it
    renders every modelo page plus the toctree index and writes them to the
    generated (gitignored, uncommitted) location, returning a summary. Wired at
    the ``builder-inited`` seam so the pages exist before Sphinx reads the tree.

    ``docs_root`` may be an isolated copy used by a sandboxed build, so the
    source repository (needed for the legal-catalogue read) must be
    independently selectable, mirroring
    :func:`~dev.docs.legal_reference.generate_legal_reference`.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).
        repo_root: Repository root for the legal-catalogue read. Defaults to
            this dev-side module's own checkout.

    Returns:
        A :class:`CasillaReferenceResult` summarising the render.
    """
    repo_root = (repo_root if repo_root is not None else _repo_root()).resolve()
    records = project_casilla_search_records()[0]
    language = _display_language()
    schema = compile_schema(records, language)
    result = render_casilla_reference(repo_root, records=records, language=language, schema=schema)
    out_dir = docs_root / CASILLA_REFERENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.rst"
    _write_if_changed(index_path, _render_index(result.pages, schema, language))
    for page in result.pages:
        _write_if_changed(docs_root / page.output_relpath, page.rst)
    _remove_generated_rst(
        out_dir,
        keep=frozenset({index_path, *(docs_root / page.output_relpath for page in result.pages)}),
    )
    return result


def _remove_generated_rst(out_dir: Path, keep: frozenset[Path]) -> None:
    """Remove direct generated RST files this render no longer produces.

    The output directory is gitignored build residue, so a page left behind by
    a render that no longer owns it survives every later build. Sphinx then
    reads it, finds it in no toctree, and reds the nitpicky gate -- which the
    deploy runs before it uploads, so stale residue fails a publish. Five pages
    from a removed preview surface did exactly that.

    Only pages absent from ``keep`` are unlinked, mirroring the legal
    reference's sweep: a page this render still owns keeps its inode and mtime
    so :func:`_write_if_changed` can leave unchanged bytes untouched, rather
    than recreating the whole tree and making Sphinx re-read it every build.
    """
    for path in scan_directory(out_dir, require_root=True):
        if path.suffix != ".rst":
            continue
        if path.is_symlink() or not path.is_file() or path.parent != out_dir:
            raise CasillaReferenceError(f"refusing to remove unsafe generated casilla path: {path}")
        if path in keep:
            continue
        path.unlink()


def _write_if_changed(path: Path, rst: str) -> None:
    """Write the page only when its content changed, forcing LF newlines.

    The default newline translation emits CRLF on Windows, which doc8's
    CheckCarriageReturn (D004) then flags on every regeneration; force LF so the
    generated page is byte-identical across platforms (the glossary precedent).
    """
    if not (path.is_file() and path.read_text(encoding=_UTF_8) == rst):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rst, encoding=_UTF_8, newline="\n")

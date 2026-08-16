"""Generated legal-catalogue reference pages for the user-docs search surface.

The registry legal catalogue is the only authority for this surface.  This
module reads only its ``[legal."<id>"]`` tables and projects those authored
rows into one generated page per document.  The page and provision target
helpers are intentionally kept here so the later search-record projection can
consume the same routing and slug authority as the renderer.

Generated files live under ``docs/_generated/legal`` and are written at
``builder-inited`` time.  They are deliberately not committed: the catalogue
is the source, and a stale generated page must never become a second source of
legal metadata.
"""

from __future__ import annotations

import os
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit

from cadrumo.core import scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry import LegalReference
from dev._paths import UTF_8

from ._locale_chrome import docs_chrome
from .build import docs_build_language

__all__ = [
    "LEGAL_CATALOGUE_RELPATH",
    "LEGAL_REFERENCE_DIR",
    "LegalPage",
    "LegalProvisionRecord",
    "LegalReferenceError",
    "LegalReferenceResult",
    "generate_legal_reference",
    "legal_citation",
    "legal_document_slug",
    "legal_instrument_designation",
    "legal_page_anchor",
    "legal_page_relpath",
    "legal_provision_anchor",
    "legal_provision_designation",
    "legal_reference_page",
    "legal_reference_target",
    "load_legal_provisions",
    "render_legal_reference",
]

_UTF_8 = UTF_8
LEGAL_REFERENCE_DIR: Final[str] = "_generated/legal"
_ANCHOR_PREFIX: Final[str] = "legal-"

#: The legal catalogue tree, relative to the repository root.  The leading
#: segment is the CADRUMO package root; the trailing ``aeat`` is the authority
#: taxonomy directory (aeat-naming).  This surface owns the constant because
#: the legal catalogue is its source; the glossary reads it for grounding.
LEGAL_CATALOGUE_RELPATH: Final[Path] = Path("src") / "cadrumo" / "_data" / "registry" / "aeat" / "legal"

_DATE_FIELDS: Final[tuple[str, ...]] = (
    "published_at",
    "effective_from",
    "effective_to",
    "consolidated_as_of",
    "reviewed_at",
)

_LEGAL_TABLE_FIELDS: Final[frozenset[str]] = frozenset(LegalReference.model_fields) - {"id"}
"""Every field a ``[legal."..."]`` table body may declare.

Derived from :class:`LegalReference` rather than hand-listed, so it is complete
by construction and cannot drift from the model it validates against. The
hand-written set it replaces had fallen two fields behind -- ``corpus_tier``
and ``forbidden_text`` -- and the first of those crashed ``dev.locales
scaffold`` tree-wide the moment a catalogue entry used it, blocking every
locale operation for reasons unrelated to locales.

``id`` is excluded because it is the TOML table KEY, not a body field: a legal
entry is written ``[legal."ley-58-2003:art-29"]`` and never carries ``id =``
inside its own table.
"""
_RENDERED_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "legal_id",
    "kind",
    "document_id",
    "corpus_ref",
    "permalink",
    "authority",
    "evidence_tier",
    "article",
    "section",
    "review_status",
    "reviewed_by",
    "notes",
)
_GENERATED_INDEX_SLUG: Final[str] = "index"
_UNSAFE_LINK_CHARS: Final[frozenset[str]] = frozenset({"<", ">", '"', "'", "`", "\\"})

#: The authored id stem shape a citation can be derived from: an instrument
#: prefix, the instrument number, and the four-digit year.
_STEM_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(?P<prefix>[a-z][a-z-]*[a-z])-(?P<number>\d+)-(?P<year>\d{4})$")

#: ``id-stem prefix -> (Spanish instrument designation, the ``kind`` that must
#: agree)``.  A citation is derived ONLY when the authored prefix and the
#: authored ``kind`` corroborate each other; disagreement falls back to the
#: verbatim stem rather than asserting an instrument the catalogue does not
#: claim.  The designation is the instrument's conventional Spanish reference
#: form, not a title or a summary of what it says.
_INSTRUMENT_BY_PREFIX: Final[dict[str, tuple[str, str]]] = {
    "ley": ("Ley", "ley"),
    "rd": ("Real Decreto", "real_decreto"),
    "rdleg": ("Real Decreto Legislativo", "real_decreto_legislativo"),
    "real-decreto-ley": ("Real Decreto-ley", "real_decreto_ley"),
}

#: Ministry codes that appear as ``orden-<code>-<number>-<year>`` stems and
#: render as the official ``Orden CODE/number/year`` citation form.
_ORDEN_MINISTRY_CODES: Final[frozenset[str]] = frozenset({"eha", "hac", "hap", "hfp"})


def _legal_id_stem(legal_id: str) -> str:
    """Return the instrument-naming part of a ``<stem>:<provision>`` id."""
    return legal_id.partition(":")[0] or legal_id


def legal_instrument_designation(legal_id: str, kind: str) -> str:
    """Return the reader-facing designation of the instrument a provision sits in.

    ``ley-37-1992`` with ``kind = "ley"`` reads as ``Ley 37/1992``: the
    conventional Spanish citation form, recomposed from two authored catalogue
    fields that corroborate each other.  Nothing is asserted that the catalogue
    does not already state, and no title, subject matter, or meaning is
    invented.  A stem whose shape or ``kind`` is not corroborated falls back to
    the authored stem verbatim, so an unrecognised instrument is shown as
    authored rather than guessed at.
    """
    stem = _legal_id_stem(legal_id)
    match = _STEM_PATTERN.match(stem)
    if match is None:
        return stem
    prefix = match.group("prefix")
    number = match.group("number")
    year = match.group("year")
    ministry = prefix.removeprefix("orden-")
    if ministry != prefix and ministry in _ORDEN_MINISTRY_CODES and kind == "orden":
        return f"Orden {ministry.upper()}/{number}/{year}"
    designation = _INSTRUMENT_BY_PREFIX.get(prefix)
    if designation is not None and designation[1] == kind:
        return f"{designation[0]} {number}/{year}"
    return stem


def legal_citation(
    legal_id: str,
    kind: str,
    *,
    article: str | None = None,
    section: str | None = None,
) -> str:
    """Return the reader-facing citation of one provision.

    The single citation authority for every surface that names a provision:
    the legal pages' own headings and the glossary's grounding links both call
    it, so a reader meets one designation for one provision wherever it
    appears.  A reader arriving on a fragment anchor sees this line first and
    nothing above it, so it names the instrument as well as the provision
    within it.

    The citation is Spanish in every build language, and deliberately so.  It
    is the official designation of a Spanish legal text, not page chrome: this
    layer may not translate it, and an English word spliced into it ("Article
    92") would render a citation that no Spanish source uses.  ``art.`` is the
    abbreviation the catalogue's own authored notes use.  ``section`` is a free
    authored Spanish label (``Anexo I``, ``Modelo 190``), never an ordinal, so
    it is appended verbatim rather than introduced by a word of any language.
    """
    instrument = legal_instrument_designation(legal_id, kind)
    parts = [instrument]
    if article is not None:
        parts.append(f"art. {article}")
    if section is not None:
        parts.append(section)
    return ", ".join(parts)


def legal_provision_designation(record: LegalProvisionRecord) -> str:
    """Return the reader-facing citation for one loaded catalogue record."""
    return legal_citation(record.legal_id, record.kind, article=record.article, section=record.section)


class LegalReferenceError(RuntimeError):
    """Raised when the legal reference surface cannot be rendered safely."""


@dataclass(frozen=True)
class LegalProvisionRecord:
    """One authored ``[legal.<id>]`` catalogue row.

    The record keeps catalogue values typed and unchanged.  Optional fields
    remain absent rather than being filled with generated or inferred prose.
    """

    legal_id: str
    kind: str
    document_id: str
    corpus_ref: str
    permalink: str
    authority: str | None = None
    evidence_tier: str | None = None
    article: str | None = None
    section: str | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: str | None = None
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    required_text: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegalPage:
    """One generated document page and its target/grounding inventory."""

    document_id: str
    #: The reader-facing designation of the instrument this page renders.
    instrument: str
    output_relpath: str
    rst: str
    #: Anchors actually emitted; law-level rows without a fragment have none.
    anchors: tuple[str, ...]
    #: ``legal_id -> site-relative page or page+anchor target``.
    targets: dict[str, str]
    #: ``legal_id -> emitted anchor``; ``None`` means page-level target only.
    anchor_by_id: dict[str, str | None]
    #: ``legal_id -> authored BOE permalink`` rendered on the destination.
    grounding_by_id: dict[str, str]


@dataclass(frozen=True)
class LegalReferenceResult:
    """Summary of one deterministic legal-reference generation pass."""

    pages: tuple[LegalPage, ...]
    index_relpath: str
    page_count: int
    provision_count: int
    grounding_count: int
    #: ``legal_id -> the exact target rendered for that provision``.
    targets: dict[str, str]
    #: ``legal_id -> anchor`` or ``None`` for a page-level law entry.
    anchors: dict[str, str | None]

    @property
    def document_count(self) -> int:
        """Alias for the number of document pages, useful to later gates."""
        return self.page_count

    @property
    def legal_links(self) -> int:
        """Alias matching the sibling reference-generator summaries."""
        return self.grounding_count


def _slug(value: str) -> str:
    """Fold a value to a deterministic lowercase ``[a-z0-9-]`` slug."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    segments: list[str] = []
    current: list[str] = []
    for char in ascii_text:
        if char.isascii() and char.isalnum():
            current.append(char.lower())
        elif current:
            segments.append("".join(current))
            current = []
    if current:
        segments.append("".join(current))
    return "-".join(segments)


def legal_document_slug(document_id: str) -> str:
    """Return the canonical URL-safe slug for a catalogue document id."""
    slug = _slug(str(document_id))
    if not slug:
        raise LegalReferenceError(f"document id {document_id!r} folds to an empty page slug")
    if slug == _GENERATED_INDEX_SLUG:
        raise LegalReferenceError(
            f"document id {document_id!r} uses the reserved generated page slug {slug!r}",
        )
    return slug


def legal_page_relpath(document_id: str) -> Path:
    """Return the generated RST path for a document, relative to ``docs``."""
    return Path(LEGAL_REFERENCE_DIR) / f"{legal_document_slug(document_id)}.rst"


def legal_reference_page(document_id: str) -> str:
    """Return the built, site-relative HTML page for a catalogue document."""
    return f"{LEGAL_REFERENCE_DIR}/{legal_document_slug(document_id)}.html"


def _has_fragment(value: str | None) -> bool:
    if not value or "#" not in value:
        return False
    return bool(value.partition("#")[2])


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())


def legal_provision_anchor(
    legal_id: str,
    *,
    article: str | None = None,
    section: str | None = None,
    corpus_ref: str | None = None,
    permalink: str | None = None,
) -> str | None:
    """Return the canonical provision anchor, or ``None`` for a law-level row.

    An anchor is emitted only when the authored row carries an article,
    section, or URL/corpus fragment.  In particular, a bare law/document row
    is deliberately targetable only at its page; its id is never used to
    fabricate a provision fragment.
    """
    if not (_has_value(article) or _has_value(section) or _has_fragment(corpus_ref) or _has_fragment(permalink)):
        return None
    slug = _slug(str(legal_id))
    if not slug:
        raise LegalReferenceError(f"legal id {legal_id!r} folds to an empty anchor slug")
    return _ANCHOR_PREFIX + slug


def legal_page_anchor(
    legal_id: str,
    *,
    article: str | None = None,
    section: str | None = None,
    corpus_ref: str | None = None,
    permalink: str | None = None,
) -> str | None:
    """Compatibility-named alias for the shared provision-anchor authority."""
    return legal_provision_anchor(
        legal_id,
        article=article,
        section=section,
        corpus_ref=corpus_ref,
        permalink=permalink,
    )


def legal_reference_target(
    document_id: str,
    legal_id: str,
    *,
    article: str | None = None,
    section: str | None = None,
    corpus_ref: str | None = None,
    permalink: str | None = None,
) -> str:
    """Return the D1-conformant target for one catalogue provision.

    The result is a site-relative ``.html`` page with an optional fragment and
    is derived from the same helpers the renderer uses.
    """
    page = legal_reference_page(document_id)
    anchor = legal_provision_anchor(
        legal_id,
        article=article,
        section=section,
        corpus_ref=corpus_ref,
        permalink=permalink,
    )
    return f"{page}#{anchor}" if anchor is not None else page


def _validate_authored_text(value: str, *, path: Path, legal_id: str, field: str) -> str:
    """Reject authored control characters before text enters generated RST."""
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field {field!r} contains a control character",
        )
    return value


def _validate_boe_permalink(value: str, *, path: Path, legal_id: str) -> str:
    """Validate an authored BOE URL before it enters an RST link target."""
    _validate_authored_text(value, path=path, legal_id=legal_id, field="permalink")
    if any(char.isspace() for char in value) or any(char in _UNSAFE_LINK_CHARS for char in value):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' contains unsafe URL characters",
        )
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' is malformed",
        ) from exc
    if parsed.scheme != "https" or parsed.netloc != "www.boe.es" or not parsed.path.startswith("/"):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' must be an https://www.boe.es URL",
        )
    return value


def _required_string(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} requires string field {key!r}")
    return _validate_authored_text(value, path=path, legal_id=legal_id, field=key)


def _optional_string(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field {key!r} must be a string")
    return _validate_authored_text(value, path=path, legal_id=legal_id, field=key)


def _optional_date(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> date | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, date):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field {key!r} must be a TOML date")
    return value


def _required_text(body: dict[str, object], *, path: Path, legal_id: str) -> tuple[str, ...]:
    value = body.get("required_text")
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field 'required_text' must be a string array")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field 'required_text' must be a string array")
    string_items = tuple(item for item in items if isinstance(item, str))
    return tuple(
        _validate_authored_text(item, path=path, legal_id=legal_id, field="required_text") for item in string_items
    )


def _record_from_table(path: Path, legal_id: str, body: object) -> LegalProvisionRecord:
    if not isinstance(body, dict):
        raise LegalReferenceError(f"{path}: [legal.{legal_id!r}] must be a table")
    table = cast(dict[str, object], body)
    unknown_fields = set(table).difference(_LEGAL_TABLE_FIELDS)
    if unknown_fields:
        fields = ", ".join(repr(field) for field in sorted(unknown_fields))
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} contains unknown field(s): {fields}",
        )
    permalink = _required_string(table, "permalink", path=path, legal_id=legal_id)
    _validate_boe_permalink(permalink, path=path, legal_id=legal_id)
    return LegalProvisionRecord(
        legal_id=legal_id,
        kind=_required_string(table, "kind", path=path, legal_id=legal_id),
        document_id=_required_string(table, "document_id", path=path, legal_id=legal_id),
        corpus_ref=_required_string(table, "corpus_ref", path=path, legal_id=legal_id),
        permalink=permalink,
        authority=_optional_string(table, "authority", path=path, legal_id=legal_id),
        evidence_tier=_optional_string(table, "evidence_tier", path=path, legal_id=legal_id),
        article=_optional_string(table, "article", path=path, legal_id=legal_id),
        section=_optional_string(table, "section", path=path, legal_id=legal_id),
        published_at=_optional_date(table, "published_at", path=path, legal_id=legal_id),
        effective_from=_optional_date(table, "effective_from", path=path, legal_id=legal_id),
        effective_to=_optional_date(table, "effective_to", path=path, legal_id=legal_id),
        consolidated_as_of=_optional_date(table, "consolidated_as_of", path=path, legal_id=legal_id),
        review_status=_optional_string(table, "review_status", path=path, legal_id=legal_id),
        reviewed_at=_optional_date(table, "reviewed_at", path=path, legal_id=legal_id),
        reviewed_by=_optional_string(table, "reviewed_by", path=path, legal_id=legal_id),
        notes=_optional_string(table, "notes", path=path, legal_id=legal_id),
        required_text=_required_text(table, path=path, legal_id=legal_id),
    )


def load_legal_provisions(repo_root: Path) -> tuple[LegalProvisionRecord, ...]:
    """Load every provision from the legal catalogue, ordered deterministically.

    Only ``[legal."<id>"]`` tables are read.  Other tables in the same TOML
    files, such as ``[sources]``, are intentionally ignored.
    """
    catalogue = repo_root / LEGAL_CATALOGUE_RELPATH
    if not catalogue.is_dir():
        raise LegalReferenceError(f"legal catalogue directory does not exist: {catalogue}")

    records: list[LegalProvisionRecord] = []
    seen_ids: dict[str, Path] = {}
    for fragment in scan_directory(catalogue, pattern="*.toml"):
        try:
            data = cast(dict[str, object], tomllib.loads(fragment.read_text(encoding=_UTF_8)))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise LegalReferenceError(f"cannot read legal catalogue fragment {fragment}: {exc}") from exc
        legal = data.get("legal")
        if legal is None:
            continue
        if not isinstance(legal, dict):
            raise LegalReferenceError(f"{fragment}: 'legal' must contain provision tables")
        legal_tables = cast(dict[object, object], legal)
        for raw_id, body in legal_tables.items():
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise LegalReferenceError(f"{fragment}: legal provision id must be a non-empty string")
            legal_id = raw_id
            _validate_authored_text(legal_id, path=fragment, legal_id=legal_id, field="legal id")
            previous = seen_ids.get(legal_id)
            if previous is not None:
                raise LegalReferenceError(
                    f"duplicate legal provision id {legal_id!r} in {fragment} and {previous}; "
                    "refusing to merge authority",
                )
            seen_ids[legal_id] = fragment
            records.append(_record_from_table(fragment, legal_id, body))

    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.document_id,
                record.article or "",
                record.section or "",
                record.legal_id,
            ),
        ),
    )


def _validate_records(records: tuple[object, ...]) -> None:
    seen_ids: set[str] = set()
    page_slugs: dict[str, str] = {}
    for candidate in records:
        if not isinstance(candidate, LegalProvisionRecord):
            raise LegalReferenceError("legal reference records must be LegalProvisionRecord values")
        record = candidate
        for field in _RENDERED_TEXT_FIELDS:
            value = cast(object, getattr(record, field))
            if value is None:
                continue
            if not isinstance(value, str):
                raise LegalReferenceError(
                    f"legal entry {record.legal_id!r} field {field!r} must be a string",
                )
            _validate_authored_text(value, path=Path("<rendered records>"), legal_id=record.legal_id, field=field)
        required_text = cast(object, record.required_text)
        if not isinstance(required_text, tuple):
            raise LegalReferenceError(f"legal entry {record.legal_id!r} field 'required_text' must be a string tuple")
        required_items = cast(tuple[object, ...], required_text)
        if not all(isinstance(item, str) for item in required_items):
            raise LegalReferenceError(f"legal entry {record.legal_id!r} field 'required_text' must be a string tuple")
        for item in (item for item in required_items if isinstance(item, str)):
            _validate_authored_text(
                item,
                path=Path("<rendered records>"),
                legal_id=record.legal_id,
                field="required_text",
            )
        _validate_boe_permalink(
            record.permalink,
            path=Path("<rendered records>"),
            legal_id=record.legal_id,
        )
        if record.legal_id in seen_ids:
            raise LegalReferenceError(f"duplicate legal provision id {record.legal_id!r}; refusing to merge rows")
        seen_ids.add(record.legal_id)
        slug = legal_document_slug(record.document_id)
        previous_document = page_slugs.get(slug)
        if previous_document is not None and previous_document != record.document_id:
            raise LegalReferenceError(
                f"document ids {previous_document!r} and {record.document_id!r} collide at page slug {slug!r}",
            )
        page_slugs[slug] = record.document_id


def _rst_escape(text: str) -> str:
    """Escape free catalogue text before it enters RST body prose."""
    return "".join(f"\\{char}" if char in "\\`*_|[]" else char for char in text)


def _rst_literal(text: str) -> str:
    """Wrap catalogue text as an RST inline literal without escaping it.

    Inline literals are verbatim: RST interprets no markup inside them, so a
    backslash added by :func:`_rst_escape` is rendered as a visible backslash
    rather than consumed.  An identifier such as ``legal_authority`` must
    therefore enter the literal unescaped.
    """
    if "`" in text:
        raise LegalReferenceError(f"catalogue value {text!r} cannot be rendered as an inline literal")
    return f"``{text}``"


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _in_force_sentence(record: LegalProvisionRecord, language: OutputLanguage) -> str | None:
    """Render the authored effectivity dates as one reader-facing sentence.

    Dates stay ISO in every language: they are data, and an ISO date is read
    the same way by every reader without a per-language format to maintain.
    """
    if record.effective_from is not None and record.effective_to is not None:
        span = docs_chrome(
            "docs.legal.provision.in_force_between",
            language,
            start=record.effective_from.isoformat(),
            end=record.effective_to.isoformat(),
        )
    elif record.effective_from is not None:
        span = docs_chrome("docs.legal.provision.in_force_from", language, start=record.effective_from.isoformat())
    elif record.effective_to is not None:
        span = docs_chrome("docs.legal.provision.in_force_until", language, end=record.effective_to.isoformat())
    else:
        span = ""
    published = (
        docs_chrome("docs.legal.provision.published", language, date=record.published_at.isoformat())
        if record.published_at is not None
        else ""
    )
    if span and published:
        return f"{span} ({published})."
    if span:
        return f"{span}."
    if published:
        return f"{published[:1].upper()}{published[1:]}."
    return None


def _official_wording_block(required_text: tuple[str, ...], language: OutputLanguage) -> list[str]:
    """Render the authored extracts of the official text, marked as Spanish.

    Emitted as raw HTML rather than RST for two reasons that both protect the
    text.  It carries ``lang="es"``, which RST offers no way to set and which
    is what tells a browser, a screen reader and a translation tool that this
    run is Spanish inside an otherwise non-Spanish page -- the language
    boundary made explicit rather than left for the reader to infer.  And HTML
    escaping is total, so wording that opens with a subparagraph marker
    ("b) ...") cannot be reparsed into a list item the way RST would; the
    official text reaches the page as authored or not at all.

    Each phrase is its own paragraph.  Run together they would read as one
    continuous piece of statutory wording that the provision does not contain.
    """
    quoted = "".join(f"<p>{escape(item.rstrip())}</p>" for item in required_text)
    label = escape(docs_chrome("docs.legal.provision.official_wording", language))
    return [
        ".. raw:: html",
        "",
        '   <div class="cadrumo-legal-wording">',
        f'     <p class="cadrumo-legal-wording-label" lang="{language.value}">{label}</p>',
        f'     <blockquote lang="es">{quoted}</blockquote>',
        "   </div>",
        "",
    ]


def _catalogue_record_block(record: LegalProvisionRecord, language: OutputLanguage) -> list[str]:
    """The demoted provenance panel: the identifiers and the review trail.

    Everything a reader does not need in order to understand the provision, but
    which must stay visible for anyone auditing where the figure came from: the
    catalogue id, the instrument kind, the bundled-corpus locator, and the
    review stamp.  It renders after the content and is styled as subordinate.

    The authored ``notes`` field lives here rather than leading the entry.  It
    is a single free-text field with no declared language -- measured across
    the catalogue it is roughly three quarters Spanish and one quarter English
    -- so it cannot be marked honestly for the reader, and presenting it as the
    entry's summary would put unlabelled other-language prose in the position
    where a reader expects the answer.  As provenance beside the review stamp
    it is what it actually is: the cataloguer's own note.
    """

    # Every key is spelled out at its call site rather than composed from a
    # field name. A composed key is invisible to the locale scanner, which then
    # reports the catalogue entry as one no code requests and prunes it.
    fields = [
        f":{docs_chrome('docs.legal.record.catalogue_id', language)}: {_rst_literal(record.legal_id)}",
        f":{docs_chrome('docs.legal.record.instrument_kind', language)}: {_rst_literal(record.kind)}",
        f":{docs_chrome('docs.legal.record.boe_document', language)}: {_rst_literal(record.document_id)}",
        f":{docs_chrome('docs.legal.record.bundled_corpus', language)}: {_rst_literal(record.corpus_ref)}",
    ]
    if record.authority is not None:
        fields.append(f":{docs_chrome('docs.legal.record.authority', language)}: {_rst_literal(record.authority)}")
    if record.evidence_tier is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.evidence_tier', language)}: {_rst_literal(record.evidence_tier)}",
        )
    if record.consolidated_as_of is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.consolidated_as_of', language)}: "
            f"{record.consolidated_as_of.isoformat()}",
        )
    if record.review_status is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.review_status', language)}: {_rst_literal(record.review_status)}",
        )
    if record.reviewed_at is not None:
        fields.append(f":{docs_chrome('docs.legal.record.reviewed_at', language)}: {record.reviewed_at.isoformat()}")
    if record.reviewed_by is not None:
        fields.append(f":{docs_chrome('docs.legal.record.reviewed_by', language)}: {_rst_escape(record.reviewed_by)}")
    if record.notes is not None:
        fields.append(f":{docs_chrome('docs.legal.record.note', language)}: {_rst_escape(record.notes)}")
    title = docs_chrome("docs.legal.record.title", language)
    return [".. container:: cadrumo-legal-record", "", f"   {title}", "", *(f"   {line}" for line in fields)]


def _headings_by_id(records: tuple[LegalProvisionRecord, ...], instrument: str) -> dict[str, str]:
    """Resolve one unique reader-facing heading per provision on a page.

    A catalogue commonly carries several consolidated versions of the same
    article, each governing a different filing year (``art-52``,
    ``art-52-2015``, ``art-52-2021``).  They share a citation, so the citation
    alone is neither unique nor enough for a reader who needs the version that
    applies to their year: the in-force date is the distinguishing fact, and it
    is authored, not inferred.  Where even that repeats, the catalogue id
    disambiguates, because a heading that silently names two provisions is
    worse than one carrying an identifier.

    ``instrument`` is the page's own heading, which a provision carrying no
    article or section would otherwise duplicate exactly.
    """
    citations: dict[str, list[LegalProvisionRecord]] = {}
    for record in records:
        citations.setdefault(legal_provision_designation(record), []).append(record)

    headings: dict[str, str] = {}
    for citation, group in citations.items():
        if len(group) == 1 and citation != instrument:
            headings[group[0].legal_id] = citation
            continue
        # The bare date is language-neutral: it disambiguates the consolidated
        # versions without splicing a chrome word into a Spanish citation. The
        # in-force line under the heading states what the date means.
        dated = [
            f"{citation} ({record.effective_from.isoformat()})" if record.effective_from is not None else citation
            for record in group
        ]
        distinct = len(set(dated)) == len(dated) and instrument not in dated
        for record, heading in zip(group, dated, strict=True):
            headings[record.legal_id] = heading if distinct else f"{citation} ({record.legal_id})"
    return headings


def _render_entry(record: LegalProvisionRecord, heading: str, language: OutputLanguage) -> tuple[str, str | None, str]:
    """Render one provision: what it says first, where it came from last."""
    anchor = legal_provision_anchor(
        record.legal_id,
        article=record.article,
        section=record.section,
        corpus_ref=record.corpus_ref,
        permalink=record.permalink,
    )
    lines: list[str] = []
    if anchor is not None:
        lines.extend([".. raw:: html", "", f'   <span id="{anchor}"></span>', ""])
    designation = legal_provision_designation(record)
    read_label = docs_chrome("docs.legal.provision.read_on_boe", language, citation=designation)
    lines.extend([_rst_heading(_rst_escape(heading), "-").rstrip("\n"), ""])

    in_force = _in_force_sentence(record, language)
    if in_force is not None:
        lines.extend([".. container:: cadrumo-legal-force", "", f"   {in_force}", ""])

    if record.required_text:
        lines.extend(_official_wording_block(record.required_text, language))

    lines.extend(
        [
            ".. container:: cadrumo-legal-official",
            "",
            f"   `{_rst_escape(read_label)} <{record.permalink}>`__",
            "",
            f"   {_rst_escape(docs_chrome('docs.legal.provision.boe_is_official', language))}",
            "",
        ],
    )
    lines.extend(_catalogue_record_block(record, language))
    lines.append("")
    return "\n".join(lines), anchor, record.permalink


def _render_document_page(
    document_id: str,
    records: tuple[LegalProvisionRecord, ...],
    language: OutputLanguage,
) -> LegalPage:
    header = (
        "..\n"
        "   Generated by dev/docs/legal_reference.py from the registry legal\n"
        "   catalogue. Do not edit by hand; regenerate.\n\n"
    )
    instrument = legal_instrument_designation(records[0].legal_id, records[0].kind) if records else document_id
    intro = _rst_escape(
        docs_chrome("docs.legal.page.intro", language, document=document_id, count=len(records)),
    )
    blocks: list[str] = [header + _rst_heading(_rst_escape(instrument), "="), intro + "\n"]
    anchors: list[str] = []
    targets: dict[str, str] = {}
    anchor_by_id: dict[str, str | None] = {}
    grounding_by_id: dict[str, str] = {}
    seen_anchors: dict[str, str] = {}
    headings = _headings_by_id(records, instrument)
    for record in records:
        entry, anchor, permalink = _render_entry(record, headings[record.legal_id], language)
        if anchor is not None:
            previous = seen_anchors.get(anchor)
            if previous is not None:
                raise LegalReferenceError(
                    f"document {document_id!r}: legal ids {previous!r} and {record.legal_id!r} "
                    f"collide at anchor {anchor!r}",
                )
            seen_anchors[anchor] = record.legal_id
            anchors.append(anchor)
        target = legal_reference_target(
            document_id,
            record.legal_id,
            article=record.article,
            section=record.section,
            corpus_ref=record.corpus_ref,
            permalink=record.permalink,
        )
        targets[record.legal_id] = target
        anchor_by_id[record.legal_id] = anchor
        grounding_by_id[record.legal_id] = permalink
        blocks.append(entry)

    return LegalPage(
        document_id=document_id,
        instrument=instrument,
        output_relpath=legal_page_relpath(document_id).as_posix(),
        rst="\n".join(blocks).rstrip("\n") + "\n",
        anchors=tuple(anchors),
        targets=targets,
        anchor_by_id=anchor_by_id,
        grounding_by_id=grounding_by_id,
    )


def _render_index(pages: tuple[LegalPage, ...], language: OutputLanguage) -> str:
    header = "..\n   Generated by dev/docs/legal_reference.py. Do not edit by hand; regenerate.\n\n"
    lines = [
        header + _rst_heading(_rst_escape(docs_chrome("docs.legal.index.title", language)), "=").rstrip("\n"),
        "",
        _rst_escape(docs_chrome("docs.legal.index.intro", language)),
        "",
        ".. toctree::",
        "   :maxdepth: 1",
        "",
    ]
    for page in sorted(pages, key=lambda page: (page.instrument.casefold(), page.document_id)):
        slug = legal_document_slug(page.document_id)
        lines.append(f"   {_rst_escape(page.instrument)} <{slug}>")
    return "\n".join(lines).rstrip("\n") + "\n"


def render_legal_reference(
    repo_root: Path,
    records: tuple[LegalProvisionRecord, ...] | None = None,
    language: OutputLanguage | None = None,
) -> LegalReferenceResult:
    """Render the legal reference in memory and return its inventories.

    ``language`` selects the page chrome. It defaults to the language this docs
    root is being built for, so a Spanish root writes Spanish headings and
    labels around the Spanish legal text it may not translate.
    """
    resolved_language = language if language is not None else docs_build_language(os.environ)
    resolved = records if records is not None else load_legal_provisions(repo_root)
    ordered = tuple(
        sorted(
            resolved,
            key=lambda record: (
                record.document_id,
                record.article or "",
                record.section or "",
                record.legal_id,
            ),
        ),
    )
    _validate_records(ordered)

    grouped: dict[str, list[LegalProvisionRecord]] = {}
    for record in ordered:
        grouped.setdefault(record.document_id, []).append(record)
    pages = tuple(
        _render_document_page(document_id, tuple(grouped[document_id]), resolved_language)
        for document_id in sorted(grouped)
    )
    targets = {legal_id: target for page in pages for legal_id, target in page.targets.items()}
    anchors = {legal_id: anchor for page in pages for legal_id, anchor in page.anchor_by_id.items()}
    grounding_count = sum(len(page.grounding_by_id) for page in pages)
    return LegalReferenceResult(
        pages=pages,
        index_relpath=f"{LEGAL_REFERENCE_DIR}/index.rst",
        page_count=len(pages),
        provision_count=sum(len(page.targets) for page in pages),
        grounding_count=grounding_count,
        targets=targets,
        anchors=anchors,
    )


def generate_legal_reference(
    docs_root: Path,
    *,
    repo_root: Path | None = None,
    language: OutputLanguage | None = None,
) -> LegalReferenceResult:
    """Materialise legal pages from the authoritative repo into ``docs_root``.

    ``docs_root`` may be an isolated copy used by a localized build, so the
    source repository must be independently selectable. The default retains
    the historical adjacent-root behavior for direct callers.
    """
    resolved_language = language if language is not None else docs_build_language(os.environ)
    docs_root = docs_root.resolve()
    source_root = (repo_root if repo_root is not None else docs_root.parent).resolve()
    result = render_legal_reference(source_root, language=language)
    out_dir = _validated_output_dir(docs_root)
    output_paths = [out_dir / "index.rst"]
    for page in result.pages:
        page_path = docs_root / Path(page.output_relpath)
        if page_path.parent != out_dir or page_path.suffix != ".rst":
            raise LegalReferenceError(f"generated legal page escaped the validated output directory: {page_path}")
        output_paths.append(page_path)
    if len(set(output_paths)) != len(output_paths):
        raise LegalReferenceError("generated legal output paths collide")
    _remove_generated_rst(out_dir, frozenset(output_paths))
    _write_if_changed(output_paths[0], _render_index(result.pages, resolved_language))
    for page, path in zip(result.pages, output_paths[1:], strict=True):
        _write_if_changed(path, page.rst)
    return result


def _validated_output_dir(docs_root: Path) -> Path:
    """Return the exact legal output directory, refusing symlinked or broad paths."""
    relative = Path(LEGAL_REFERENCE_DIR)
    if relative.parts != ("_generated", "legal"):
        raise LegalReferenceError(f"unexpected legal output path constant: {LEGAL_REFERENCE_DIR!r}")
    generated_dir = docs_root / "_generated"
    out_dir = docs_root / relative
    if out_dir.parent != generated_dir or out_dir.name != "legal":
        raise LegalReferenceError(f"unexpected legal output directory: {out_dir}")
    if not docs_root.is_dir() or docs_root.is_symlink():
        raise LegalReferenceError(f"docs root is not a real directory: {docs_root}")
    if generated_dir.is_symlink() or not generated_dir.is_dir():
        raise LegalReferenceError(f"generated docs directory is not a real directory: {generated_dir}")
    if out_dir.is_symlink():
        raise LegalReferenceError(f"legal output directory is not the exact real directory: {out_dir}")
    if out_dir.exists():
        if out_dir.is_symlink() or not out_dir.is_dir() or out_dir.resolve() != out_dir:
            raise LegalReferenceError(f"legal output directory is not the exact real directory: {out_dir}")
    else:
        out_dir.mkdir()
    return out_dir


def _remove_generated_rst(out_dir: Path, keep: frozenset[Path]) -> None:
    """Remove direct generated RST files this render no longer produces.

    Pruning is why the sweep exists: a legal document dropped from the
    catalogue must not leave its page behind for Sphinx to read. Only the
    pages absent from ``keep`` are unlinked, so a page this render still owns
    keeps its inode and its mtime, and :func:`_write_if_changed` can then leave
    it untouched when its bytes are unchanged. Deleting every page first made
    that comparison vacuous -- all 141 were recreated with fresh mtimes on
    every build, so Sphinx re-read and re-wrote the whole legal tree even when
    the catalogue had not moved.
    """
    for path in scan_directory(out_dir, require_root=True):
        if path.suffix != ".rst":
            continue
        if path.is_symlink() or not path.is_file() or path.parent != out_dir:
            raise LegalReferenceError(f"refusing to remove unsafe generated legal path: {path}")
        if path in keep:
            continue
        path.unlink()


def _write_if_changed(path: Path, rst: str) -> None:
    """Write generated RST with LF endings only when its bytes changed."""
    if not (path.is_file() and path.read_text(encoding=_UTF_8) == rst):
        path.write_text(rst, encoding=_UTF_8, newline="\n")

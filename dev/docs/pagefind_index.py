"""Post-build Pagefind index pass over the built documentation HTML.

Runs AFTER Sphinx has emitted the configured docs HTML root: it indexes the built
pages with Pagefind's bundled (vendored, offline) binary, producing the
chunked search index into the build output. The index is an uncommitted build
artifact - it is regenerated on every docs build, exactly like the generated CLI
reference, and never committed.

The site carries ONE index for every language, written once at the site's apex
(:func:`build_shared_search_index`). Pagefind's default behaviour is one index
per detected ``<html lang>``, and the reader's bundle loads only the split
matching the page it is on; under that behaviour a record shared by every
language -- a concept, casilla, legal or CLI record, whose content already
carries all four languages' text -- had to be injected once per split to stay
reachable, which is what put the same casilla corpus in the index four times.
:data:`SHARED_INDEX_LANGUAGE` forces a single split instead, so every record is
searched together and each is indexed once. A page then declares its own
language as a Pagefind FILTER, and the reader's search controller narrows by the
language of the page it runs on; a shared record declares every language's filter
value and so matches whichever language is being read.

This pass is deliberately a STANDALONE step, not a Sphinx ``setup()`` hook:
it must run after the build, and wiring it into ``conf.py`` would couple it
to every Sphinx invocation - including the nitpicky ``-n -W`` gate, which
this pass must leave untouched. The docs build driver (or ``just docs-build``)
calls :func:`build_search_index` after a successful Sphinx build.

The Pagefind binary is vendored as a pinned wheel (``pagefind[extended]`` -
the extended binary bundles the Spanish/Catalan/Hungarian/English stemmers
needed for the per-language index splits). Because the binary lives inside
the installed wheel, the pass makes NO network fetch and the build stays
offline-hermetic.

Injection seam for the custom-record step: :func:`build_search_index`
accepts an optional ``inject`` callback that is invoked with the open
:class:`~pagefind.index.PagefindIndex` AFTER ``add_directory`` and BEFORE the
index is written. The custom-record injection (the unified search records
plus the sweep-derived relevance weights) plugs in there via
``index.add_custom_record(...)``; this module owns only the directory pass
and the write, never the record content.

Orama fallback trigger: Pagefind is the chosen backend because it is the only
surveyed engine that satisfies every hard constraint at once - MIT, offline,
native es/ca/hu/en stemming, lazy chunked
scaling, and a first-class custom-record API. The documented fallback is
Orama (Apache-2.0, pure JS). Switch to Orama ONLY if the Pagefind binary
proves unvendorable for the offline-hermetic build - i.e. if the
``pagefind[extended]`` wheel (which bundles the platform binary) cannot be
pinned for a target platform, or a future platform has no published bundled
wheel and the build would need a network fetch. In this environment the
vendoring succeeded (the ``win_amd64`` extended wheel is pinned and the
bundled binary runs offline), so the fallback is not triggered; it remains
the documented escape hatch if a platform-coverage gap appears. Orama's cost
is a sourced Catalan Snowball stemmer (Orama bundles none) and whole-index
loading instead of lazy chunking.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import re
import zlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Final

from cadrumo.core.directory_scan import iter_directory, scan_directory
from dev._paths import UTF_8

if TYPE_CHECKING:
    from pagefind.index import PagefindIndex

#: Callback that injects custom records into the open index after the
#: directory pass. The custom-record step supplies this; this module calls it.
InjectCallback = Callable[["PagefindIndex"], Awaitable[None]]

#: Built subtrees excluded from the Pagefind full-text pass. The generated
#: casilla reference pages carry every casilla the injected custom records
#: already cover (6,330 records); indexing the pages too would duplicate every
#: record and, on the two large modelos, bloat the index with thousands of
#: label tokens. Exclusion is expressed the Pagefind-native way: stamping
#: ``data-pagefind-ignore`` on the ``<body>`` of each page drops it from the
#: index (the page's anchors stay in the DOM for the deep links to resolve).
_PAGEFIND_EXCLUDED_SUBDIRS: Final[tuple[str, ...]] = ("_generated/casillas",)
_UTF_8: Final[str] = UTF_8

#: What a page's record leaves out of the page. The index is built through the
#: Pagefind service, which reads no configuration file, so the selectors are
#: given to it here. The navigation, header and footer are the same on every
#: page and would answer any query that names a section with every page; a
#: recorded JSON envelope is machine output whose keys match almost anything.
#: The command line and the human-readable output beside it stay indexed.
PAGE_EXCLUDED_SELECTORS: Final[tuple[str, ...]] = (
    ".sidebar-drawer",
    ".toc-drawer",
    ".announcement",
    ".mobile-header",
    ".skip-to-content",
    ".cadrumo-breadcrumbs",
    ".related-pages",
    "footer",
    ".back-to-top",
    ".content-icon-container",
    ".headerlink",
    "a.copybtn",
    'pre.cadrumo-frame-output[data-format="json"]',
)

_BODY_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<body\b(?![^>]*\bdata-pagefind-ignore\b)")

#: The one language Pagefind builds the whole site's index under.
#:
#: Pagefind splits an index per detected page language and a reader's bundle
#: loads one split; forcing a single language is what makes every language's
#: pages and the records they share one searchable index. The forced value also
#: selects the ONE stemmer applied to the whole corpus, at indexing and at query
#: time alike, so the choice is Spanish: the documentation's subject is Spanish
#: tax filing, and every casilla label, legal title and concept id in the shared
#: records is Spanish text. The other languages keep exact-form matching and
#: lose only their own morphological folding - the price the one index costs.
SHARED_INDEX_LANGUAGE: Final[str] = "es"

#: The language a single-root pass stamps its pages with when the caller names
#: none: English, the language the documentation's prose is authored in.
_DEFAULT_PAGE_LANGUAGE: Final[str] = "en"

#: The ``<html lang="...">`` a built page declares. Read to refuse a root whose
#: rendered pages contradict the language the build says it produced: that
#: disagreement would make the whole root unreachable through the language
#: filter, with every page still present in the index.
_HTML_LANG_RE: Final[re.Pattern[str]] = re.compile(r"<html\b[^>]*\blang=\"([A-Za-z0-9-]+)\"")

#: A built page's opening ``<body>`` tag, which is where the index-facing
#: attributes are stamped, and the stamps a previous pass left on it.
_BODY_OPEN_RE: Final[re.Pattern[str]] = re.compile(r"<body\b[^>]*>")
_EXISTING_STAMP_RE: Final[re.Pattern[str]] = re.compile(
    r'\s+data-pagefind-(?:meta="display_class:[^"]*"|filter="language:[^"]*")'
)

#: The injected record kinds a shipped index must carry.
#:
#: Spelled as literals because this module imports
#: :class:`~dev.docs.terminology.search_record.SearchRecordKind` lazily (the terminology
#: package is heavy and only needed per page). The literals are therefore held
#: to the enum by ``test_decided_kinds_match_the_canonical_enum``, which fails
#: if a member is renamed or removed -- the drift this constant would otherwise
#: be blind to.
#:
#: ``PAGE`` is deliberately absent: the directory pass produces page records, so
#: requiring it would be satisfied by exactly the pages-only index this set
#: exists to reject. The set is enumerated rather than derived as "every kind
#: except PAGE" on purpose -- a kind added to the enum before its injector ships
#: would then refuse a correct publish, and a false RED at publish time is its
#: own outage. When a new injector ships, add its kind here in the same change.
DECIDED_INJECTED_RECORD_KINDS: Final[frozenset[str]] = frozenset({"concept", "casilla", "legal", "cli"})


def injected_record_kinds_in_index(html_root: Path) -> frozenset[str]:
    """Return the injected record kinds present in the index WRITTEN under ``html_root``.

    Reads the artefact, never the build configuration or the injection's own
    report. A pages-only index -- the shape a mode misconfiguration produces --
    returns an empty set here while still carrying plenty of non-empty index
    chunks, which is precisely why a non-emptiness check cannot stand in for
    this one.

    The fragments are the ground truth a reader's palette narrows over, so this
    scans them directly rather than parsing ``pagefind-entry.json``: the entry
    file's ``page_count`` proves records exist only against a separately
    measured pages baseline, and a publish-time preflight has no cheap way to
    build one.

    Args:
        html_root: A built site root (the directory holding ``pagefind/``).

    Returns:
        The subset of :data:`DECIDED_INJECTED_RECORD_KINDS` found on disk.
        Missing directories yield an empty set rather than raising, so the
        caller renders one refusal naming what is absent.
    """
    found: set[str] = set()
    for fragment in iter_directory(html_root / "pagefind" / "fragment", pattern="*.pf_fragment", recursive=True):
        for kind in _fragment_filter_kinds(fragment):
            if kind in DECIDED_INJECTED_RECORD_KINDS:
                found.add(kind)
        if found >= DECIDED_INJECTED_RECORD_KINDS:
            break
    return frozenset(found)


def _fragment_filter_kinds(fragment: Path) -> tuple[str, ...]:
    """Return the ``kind`` filter values declared by one written fragment.

    A fragment is gzipped JSON behind a short ``pagefind_dcd`` marker. The
    payload is PARSED rather than substring-scanned, for two reasons measured
    against real output on 2026-08-01: the record's kind lives in
    ``{"filters": {"kind": ["concept"]}}``, so a scan for ``"kind":"concept"``
    reads a different field; and a scan over raw bytes also matches ordinary
    PAGE prose that happens to contain the token, which would let rendered
    pages satisfy a record check -- the exact false green this read exists to
    close.

    ``filters`` is the right field rather than ``meta`` (production stamps
    both): filters are what the reader's palette narrows by, so they are the
    surface a reader can actually reach.

    A fragment that cannot be decompressed or parsed contributes nothing rather
    than raising; the caller's verdict is then driven by what IS readable,
    which fails closed.
    """
    try:
        raw = gzip.decompress(fragment.read_bytes())
    except (OSError, EOFError, zlib.error):
        return ()
    text = raw.decode(_UTF_8, errors="replace")
    start = text.find("{")
    if start < 0:
        return ()
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    filters = payload.get("filters")
    if not isinstance(filters, dict):
        return ()
    kinds = filters.get("kind")
    if isinstance(kinds, str):
        return (kinds,)
    if not isinstance(kinds, list):
        return ()
    return tuple(value for value in kinds if isinstance(value, str))


def _mark_excluded_pages(html_root: Path) -> int:
    """Stamp ``data-pagefind-ignore`` on the body of every excluded built page.

    Runs before the directory pass so Pagefind skips the tagged pages. Idempotent
    (the regex only matches a body tag that is not already tagged) and a no-op
    when an excluded subtree is absent (e.g. the fixture sites tests drive).

    Returns:
        The number of pages tagged.
    """
    tagged = 0
    for subdir in _PAGEFIND_EXCLUDED_SUBDIRS:
        root = html_root / subdir
        if not root.is_dir():
            continue
        for page in scan_directory(root, pattern="*.html", recursive=True):
            html = page.read_text(encoding=_UTF_8, newline="")
            new_html, count = _BODY_TAG_RE.subn("<body data-pagefind-ignore", html, count=1)
            if count:
                page.write_text(new_html, encoding=_UTF_8, newline="")
                tagged += 1
    return tagged


def _page_display_class(rel_path: str) -> str:
    """Classify a built page's path onto the shipped ``display_class`` value.

    Reuses the single page-path derivation authority: rather than
    re-implementing the ``cli/`` -> ``cli`` / ``api/`` -> ``technical`` / else
    ``doc`` split (the forbidden re-derivation), it constructs a minimal
    PAGE-kind :class:`SearchRecord` whose ``target`` is the page path and reads
    back :func:`derive_display_class`. The path split lives in exactly one place;
    this stamping consumes it, never copies it.

    Args:
        rel_path: The page path relative to the built HTML root, POSIX form
            (e.g. ``"api/foo.html"``, ``"how-to/import.html"``).

    Returns:
        The ``ResultDisplayClass`` string value to stamp as page meta.
    """
    from cadrumo.core.external_constants import OutputLanguage

    from .terminology.search_record import SearchRecordKind
    from .terminology.unified_record import RankingTier, SearchRecord, derive_display_class

    probe = SearchRecord(
        id="page-display-class-probe",
        kind=SearchRecordKind.PAGE,
        tier=RankingTier.FULLTEXT,
        title="page",
        descriptions={OutputLanguage.ES: "page"},
        target=rel_path,
        ranking_weight=0.0,
    )
    return derive_display_class(probe).value


def _mark_indexed_pages(html_root: Path, language: str) -> int:
    """Stamp the display class and the page's own language on every indexed page.

    Runs AFTER :func:`_mark_excluded_pages` and BEFORE the directory pass, so a
    page already tagged ``data-pagefind-ignore`` (the injected-record-covered
    casilla pages) is skipped by the regex lookahead and gains neither
    attribute. Every other built page carries two body attributes into the
    index:

    - ``data-pagefind-meta="display_class:<class>"``, its path-derived display
      class, and deliberately NOT a ``weight`` key, so the weight-sorted card
      pass keeps dropping full-text pages (they must not pollute the
      injected-card band). The search controller reads the class to order
      full-text pages within their band (user docs above dev machinery) and to
      render the per-class icon.
    - ``data-pagefind-filter="language:<code>"``, the language of the root this
      page belongs to. The site has one index for every language
      (:data:`SHARED_INDEX_LANGUAGE`), so what keeps a reader on one language's
      pages is this filter and not a separate index. A page carrying no value
      is reachable by no language, so the stamping is what makes a root
      searchable at all.

    A stamp a previous pass left is REPLACED rather than treated as already
    correct. Sphinx rewrites only the pages a build changed, so an incremental
    build leaves pages carrying the stamps of the build before it; skipping
    those, which is all idempotence would require, would leave a page indexed
    under a language or a display class that is no longer its own -- and a page
    stamped before the language filter existed would carry none at all and be
    reachable from no language, while every other page of its root was fine.

    Args:
        html_root: The built root to stamp.
        language: The language the build produced this root in.

    Returns:
        The number of pages stamped.

    Raises:
        PagefindLanguageMismatchError: When a page declares an ``<html lang>``
            other than ``language``.
    """
    tagged = 0
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        html = page.read_text(encoding=_UTF_8, newline="")
        body = _BODY_OPEN_RE.search(html)
        if body is None or "data-pagefind-ignore" in body.group(0):
            continue
        _require_page_language(page, html, language)
        display_class = _page_display_class(page.relative_to(html_root).as_posix())
        attributes = _EXISTING_STAMP_RE.sub("", body.group(0))[:-1].rstrip()
        stamped = (
            f'{attributes} data-pagefind-meta="display_class:{display_class}"'
            f' data-pagefind-filter="language:{language}">'
        )
        if stamped == body.group(0):
            continue
        page.write_text(html[: body.start()] + stamped + html[body.end() :], encoding=_UTF_8, newline="")
        tagged += 1
    return tagged


def _require_page_language(page: Path, html: str, language: str) -> None:
    """Refuse a page whose rendered language is not the one the build declared.

    The declared language and the rendered ``<html lang>`` come from the same
    build setting, so they agree or the build is misconfigured. The consequence
    of a disagreement is silent and total: the page is indexed under the filter
    value the build named while the reader's controller narrows by the value the
    page renders, so every page of that root is present in the index and
    reachable from no language. A page that declares no language at all keeps
    the build's value, which is the only authority available.
    """
    declared = _HTML_LANG_RE.search(html)
    if declared is not None and declared.group(1).lower() != language.lower():
        raise PagefindLanguageMismatchError(
            f"{page} renders lang={declared.group(1)!r} while its root is being indexed as {language!r}; "
            "the language filter would make every page of this root unreachable",
        )


class PagefindUnavailableError(RuntimeError):
    """Raised when the vendored Pagefind package cannot be imported.

    A clear, named boundary so a missing/broken vendor surfaces as an
    actionable error (re-pin the wheel) rather than an opaque ImportError
    deep in the build.
    """


class PagefindIndexWriteError(RuntimeError):
    """Raised when Pagefind reported the index written but its entry never became complete."""


class PagefindLanguageMismatchError(RuntimeError):
    """Raised when a built page's rendered language is not the one its root is indexed as."""


class PagefindRootPrefixError(RuntimeError):
    """Raised when a root's address in the site cannot be derived from its directory."""


_ENTRY_FILE_NAME: Final[str] = "pagefind-entry.json"
_ENTRY_COMPLETION_DEADLINE_SECONDS: Final[float] = 60.0
_ENTRY_COMPLETION_POLL_SECONDS: Final[float] = 0.05


async def await_complete_pagefind_entry(
    entry: Path,
    *,
    deadline_seconds: float = _ENTRY_COMPLETION_DEADLINE_SECONDS,
) -> None:
    """Wait until ``entry`` holds a complete JSON document, or refuse.

    Pagefind acknowledges ``WriteFiles`` before its entry file is fully on disk,
    and closing the service terminates the indexer. Measured under twenty
    concurrent builds, about one build in forty returned with an empty
    ``pagefind-entry.json`` and reported success, which would publish a site
    whose search finds nothing. The service therefore stays open until the entry
    parses, and a build whose entry never completes fails instead of shipping.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_seconds
    while True:
        try:
            json.loads(entry.read_bytes())
        except (OSError, ValueError):
            if loop.time() >= deadline:
                raise PagefindIndexWriteError(
                    f"Pagefind reported the index written but {entry} never became a complete JSON document"
                ) from None
            await asyncio.sleep(_ENTRY_COMPLETION_POLL_SECONDS)
        else:
            return


@dataclass(frozen=True)
class SearchIndexResult:
    """Outcome of a Pagefind index pass.

    Attributes:
        html_root: The root the index was written into. For a site of several
            language roots that is the apex, not any one language's root.
        page_count: The pages indexed, across every root of the pass.
        output_subdir: The index directory's name under ``html_root``.
    """

    html_root: Path
    page_count: int
    output_subdir: str


@dataclass(frozen=True)
class IndexedRoot:
    """One built language root and the address its pages have in the final site.

    Attributes:
        html_root: The built root holding that language's pages.
        language: The language the build produced it in; the value its pages
            carry as their ``language`` filter.
        url_prefix: The root's own path inside the served site, ``""`` at the
            apex and ``"<directory>/"`` under a directory. It is what makes a
            page's indexed URL its address in the final site rather than its
            address inside the build tree, which the staging step rearranges.
    """

    html_root: Path
    language: str
    url_prefix: str = ""


def _require_pagefind() -> ModuleType:
    """Confirm the vendored Pagefind package is importable, else raise.

    Raises:
        PagefindUnavailableError: If ``pagefind`` is not installed (the
            ``pagefind[extended]`` wheel was not vendored into the env).
    """
    try:
        import pagefind.index as pagefind_index

        return pagefind_index
    except ImportError as exc:  # pragma: no cover - exercised via the gate test
        raise PagefindUnavailableError(
            "the vendored Pagefind package is not importable; install the "
            "pinned `pagefind[extended]` wheel (it bundles the offline binary)"
        ) from exc


async def _add_root(index: PagefindIndex, root: IndexedRoot) -> int:
    """Add one language root's pages under the address they have in the site.

    Pagefind derives a page's indexed URL from its path relative to the
    directory it was added from, and offers no way to prefix it. A root served
    at the apex is therefore added directly, while a root served under a
    directory is added from its PARENT, narrowed to that directory by a glob --
    which is what makes the indexed URL ``/<prefix>/page.html``. The alternative,
    handing Pagefind each page's bytes with an explicit URL, would ship a
    hundred and fifty megabytes of HTML through the service pipe to buy the same
    addresses.

    Raises:
        PagefindRootPrefixError: When the prefix is not the root directory's own
            name, since the glob could then not select it.
    """
    if not root.url_prefix:
        response = await index.add_directory(str(root.html_root))
    else:
        directory = root.url_prefix.rstrip("/")
        if directory != root.html_root.name:
            raise PagefindRootPrefixError(
                f"the root at {root.html_root} is served at {root.url_prefix!r}, which is not its "
                "directory name; Pagefind addresses a page by its path under the directory it is added from",
            )
        response = await index.add_directory(str(root.html_root.parent), glob=f"{directory}/**/*.{{html}}")
    # The directory-pass response is a dict carrying the indexed page count.
    if isinstance(response, dict):
        return int(response.get("page_count", 0) or 0)
    return int(getattr(response, "page_count", 0) or 0)


async def _run_index(
    roots: Sequence[IndexedRoot],
    output_path: Path,
    *,
    inject: InjectCallback | None,
) -> int:
    """Index every root with Pagefind and write the one index.

    The output path is configured on the index AND passed to one explicit
    ``write_files`` call, while the index is deliberately not used as a context
    manager: ``PagefindIndex.__aexit__`` writes the index itself on a clean
    exit, so an explicit write plus the context exit produced TWO writes -- the
    intended one, and a second with no path, which Pagefind resolves against the
    process working directory. A docs build run from the repository root
    therefore deposited a full second copy of the index -- roughly ten thousand
    files -- at the repo root on every run. It was gitignored, which hid the
    symptom without fixing the cause; the rule barring a committed search index
    exists because such a tree was once committed from exactly that path.

    Returns:
        The number of pages Pagefind indexed, across every root.
    """
    from .pagefind_service import ResponsivePagefindService

    for root in roots:
        _mark_excluded_pages(root.html_root)
        _mark_indexed_pages(root.html_root, root.language)
    pages = 0
    async with ResponsivePagefindService() as service:
        index = await service.create_index(
            {
                "output_path": str(output_path),
                "force_language": SHARED_INDEX_LANGUAGE,
                "exclude_selectors": list(PAGE_EXCLUDED_SELECTORS),
            },
        )
        for root in roots:
            pages += await _add_root(index, root)
        if inject is not None:
            # Injection seam: the custom-record step adds the unified search
            # records and relevance weights here, before the index is written.
            await inject(index)
        await index.write_files(output_path=str(output_path))
        await await_complete_pagefind_entry(output_path / _ENTRY_FILE_NAME)
    return pages


def _require_disjoint_roots(roots: Sequence[IndexedRoot]) -> None:
    """Refuse roots where one contains another.

    The roots are indexed as they are BUILT, where each language is its own
    directory beside the others, and the URL prefixes are what give their pages
    the addresses of the SERVED site, which nests them. Handed the served layout
    instead, the apex root's directory pass would walk straight into every other
    language's root: those pages would be indexed twice and stamped with the
    apex language, and a reader of them would be answered in the wrong language.
    Nothing downstream could tell that from a correct index, so it is refused
    here.

    Raises:
        PagefindRootPrefixError: When one root is inside another.
    """
    resolved = [(root, root.html_root.resolve()) for root in roots]
    for outer, outer_path in resolved:
        for inner, inner_path in resolved:
            if inner is not outer and inner_path.is_relative_to(outer_path):
                raise PagefindRootPrefixError(
                    f"the {inner.language} root at {inner.html_root} is inside the {outer.language} root at "
                    f"{outer.html_root}; index the roots as they are built, each beside the others, and let "
                    "the url prefixes address them in the served site",
                )


def build_shared_search_index(
    roots: Sequence[IndexedRoot],
    output_root: Path,
    *,
    inject: InjectCallback | None = None,
) -> SearchIndexResult:
    """Build the site's ONE Pagefind index over every language root.

    Each root's pages are indexed under the address they have in the final site
    (:class:`IndexedRoot`) and carry their own language as a filter, and the
    whole corpus lands in a single split (:data:`SHARED_INDEX_LANGUAGE`) so a
    record shared by every language is indexed once and searched from all of
    them.

    Args:
        roots: The built language roots to index, in any order.
        output_root: The directory the ``pagefind/`` index is written into. In
            the served site this is the apex, which every language's pages
            resolve the bundle against.
        inject: Optional custom-record injection callback (the custom-record
            step supplies it). Called with the open index after every root's
            directory pass and before the index is written.

    Returns:
        A :class:`SearchIndexResult` with the pages indexed across all roots.

    Raises:
        PagefindUnavailableError: If the vendored Pagefind package is absent.
        FileNotFoundError: If no root was given, or a root does not exist.
    """
    _require_pagefind()
    if not roots:
        raise FileNotFoundError("the shared search index needs at least one built root to index")
    for root in roots:
        if not root.html_root.is_dir():
            raise FileNotFoundError(f"built HTML root not found: {root.html_root}")
    _require_disjoint_roots(roots)
    output_root.mkdir(parents=True, exist_ok=True)
    page_count = asyncio.run(_run_index(roots, output_root / "pagefind", inject=inject))
    return SearchIndexResult(
        html_root=output_root,
        page_count=page_count,
        output_subdir="pagefind",
    )


def build_search_index(
    html_root: Path,
    *,
    inject: InjectCallback | None = None,
    language: str = _DEFAULT_PAGE_LANGUAGE,
) -> SearchIndexResult:
    """Run the post-build Pagefind index pass over ONE built root.

    The single-root case of :func:`build_shared_search_index`: a root that is
    its own site, carrying the index beside its pages. A build of several
    language roots calls the shared builder instead, once, after they are all
    built.

    Args:
        html_root: The Sphinx HTML output directory. The chunked index is
            written into ``<html_root>/pagefind/``.
        inject: Optional custom-record injection callback (the custom-record
            step supplies it). Called with the open index after the directory
            pass and before the index is written.
        language: The language the build produced this root in, which its pages
            carry as their ``language`` filter.

    Returns:
        A :class:`SearchIndexResult` with the indexed page count.

    Raises:
        PagefindUnavailableError: If the vendored Pagefind package is absent.
        FileNotFoundError: If ``html_root`` does not exist.
    """
    return build_shared_search_index(
        [IndexedRoot(html_root=html_root, language=language)],
        html_root,
        inject=inject,
    )

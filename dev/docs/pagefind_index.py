"""Post-build Pagefind index pass over the built documentation HTML.

Runs AFTER Sphinx has emitted ``docs/_build/html``: it indexes the built
pages with Pagefind's bundled (vendored, offline) binary, producing the
chunked, per-language search index into the build output. The index is an
uncommitted build artifact - it is regenerated on every docs build, exactly
like the generated CLI reference, and never committed.

This pass is deliberately a STANDALONE step, not a Sphinx ``setup()`` hook:
it must run after the build, and wiring it into ``conf.py`` would couple it
to every Sphinx invocation - including the nitpicky ``-n -W`` gate, which
this pass must leave untouched. The docs build driver (or ``just docs``)
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
native es/ca/hu/en stemming with per-language index splits, lazy chunked
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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from cadrumo.core import iter_directory, scan_directory

from .._paths import UTF_8

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

_BODY_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<body\b(?![^>]*\bdata-pagefind-ignore\b)")

#: The injected record kinds a shipped index must carry.
#:
#: Spelled as literals because this module imports
#: :class:`~dev.docs.terminology.SearchRecordKind` lazily (the terminology
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

#: A ``<body>`` tag that is neither excluded from the index nor already carrying
#: a Pagefind meta attribute. The two negative lookaheads keep the display-class
#: stamping idempotent (a second pass matches nothing) and skip every page the
#: exclusion pass tagged ``data-pagefind-ignore`` (those are covered by the
#: injected casilla records, so they must NOT gain a ``display_class``).
_BODY_UNSTAMPED_RE: Final[re.Pattern[str]] = re.compile(
    r"<body\b(?![^>]*\bdata-pagefind-ignore\b)(?![^>]*\bdata-pagefind-meta=)"
)


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
            html = page.read_text(encoding=_UTF_8)
            new_html, count = _BODY_TAG_RE.subn("<body data-pagefind-ignore", html, count=1)
            if count:
                page.write_text(new_html, encoding=_UTF_8, newline="\n")
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

    from .terminology import (
        RankingTier,
        SearchRecord,
        SearchRecordKind,
        derive_display_class,
    )

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


def _mark_page_display_classes(html_root: Path) -> int:
    """Stamp ``data-pagefind-meta="display_class:<class>"`` on every indexed page.

    Runs AFTER :func:`_mark_excluded_pages` and BEFORE the directory pass, so a
    page already tagged ``data-pagefind-ignore`` (the injected-record-covered
    casilla pages) is skipped by the regex lookahead and never gains a class.
    Every other built page carries its path-derived class into the index as a
    ``display_class`` meta ONLY -- deliberately NOT a ``weight`` key, so the
    weight-sorted card pass keeps dropping full-text pages (they must not
    pollute the injected-card band). The JS reads the class to order
    full-text pages within their band (user docs above dev machinery) and to
    render the per-class icon. Idempotent and a no-op when the tree is absent.

    Returns:
        The number of pages stamped.
    """
    tagged = 0
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        rel_path = page.relative_to(html_root).as_posix()
        html = page.read_text(encoding=_UTF_8)
        if not _BODY_UNSTAMPED_RE.search(html):
            continue
        display_class = _page_display_class(rel_path)
        new_html, count = _BODY_UNSTAMPED_RE.subn(
            lambda match, cls=display_class: f'{match.group(0)} data-pagefind-meta="display_class:{cls}"',
            html,
            count=1,
        )
        if count:
            page.write_text(new_html, encoding=_UTF_8, newline="\n")
            tagged += 1
    return tagged


class PagefindUnavailableError(RuntimeError):
    """Raised when the vendored Pagefind package cannot be imported.

    A clear, named boundary so a missing/broken vendor surfaces as an
    actionable error (re-pin the wheel) rather than an opaque ImportError
    deep in the build.
    """


@dataclass(frozen=True)
class SearchIndexResult:
    """Outcome of a Pagefind index pass."""

    html_root: Path
    page_count: int
    output_subdir: str


def _require_pagefind() -> None:
    """Confirm the vendored Pagefind package is importable, else raise.

    Raises:
        PagefindUnavailableError: If ``pagefind`` is not installed (the
            ``pagefind[extended]`` wheel was not vendored into the env).
    """
    try:
        import pagefind.index  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised via the gate test
        raise PagefindUnavailableError(
            "the vendored Pagefind package is not importable; install the "
            "pinned `pagefind[extended]` wheel (it bundles the offline binary)"
        ) from exc


async def _run_index(
    html_root: Path,
    *,
    inject: InjectCallback | None,
) -> int:
    """Index ``html_root`` with Pagefind and write the per-language index.

    The output path is configured on the index rather than passed to an explicit
    ``write_files`` call, because ``PagefindIndex.__aexit__`` writes the index
    itself on a clean exit. An explicit write PLUS the context exit produced TWO
    writes: the intended one, and a second with no path, which Pagefind resolves
    against the process working directory. A docs build run from the repository
    root therefore deposited a full second copy of the index -- roughly ten
    thousand files -- at the repo root on every run. It was gitignored, which
    hid the symptom without fixing the cause; the rule barring a committed
    search index exists because such a tree was once committed from exactly that
    path.

    Returns:
        The number of pages Pagefind indexed from the directory pass.
    """
    from pagefind.index import PagefindIndex

    _mark_excluded_pages(html_root)
    _mark_page_display_classes(html_root)
    output_path = html_root / "pagefind"
    # Configured, not written explicitly: the context exit performs the one
    # write, into <html_root>/pagefind/, so the built site serves the index
    # alongside its pages (an uncommitted artifact) and nothing lands in the
    # process working directory.
    async with PagefindIndex(config={"output_path": str(output_path)}) as index:
        response = await index.add_directory(str(html_root))
        if inject is not None:
            # Injection seam: the custom-record step adds the unified search
            # records and relevance weights here, before the index is written.
            await inject(index)
    # The directory-pass response is a dict carrying the indexed page count.
    if isinstance(response, dict):
        return int(response.get("page_count", 0) or 0)
    return int(getattr(response, "page_count", 0) or 0)


def build_search_index(
    html_root: Path,
    *,
    inject: InjectCallback | None = None,
) -> SearchIndexResult:
    """Run the post-build Pagefind index pass over the built HTML.

    Args:
        html_root: The Sphinx HTML output directory (``docs/_build/html``).
            Pagefind reads ``pagefind.yml`` from this root for the
            root/exclude selectors and writes the chunked index into
            ``<html_root>/pagefind/``.
        inject: Optional custom-record injection callback (the custom-record
            step supplies it). Called with the open index after the directory
            pass and before the index is written.

    Returns:
        A :class:`SearchIndexResult` with the indexed page count.

    Raises:
        PagefindUnavailableError: If the vendored Pagefind package is absent.
        FileNotFoundError: If ``html_root`` does not exist.
    """
    _require_pagefind()
    if not html_root.is_dir():
        raise FileNotFoundError(f"built HTML root not found: {html_root}")
    page_count = asyncio.run(_run_index(html_root, inject=inject))
    return SearchIndexResult(
        html_root=html_root,
        page_count=page_count,
        output_subdir="pagefind",
    )

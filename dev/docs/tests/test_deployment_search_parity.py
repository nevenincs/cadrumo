"""Deployment-parity gate: the published site carries the decided search contract.

The defect this gate exists to catch shipped for weeks in plain sight. The
deploy environment set ``CADRUMO_DOCS_PAGEFIND_MODE=pages``, the build read that
and skipped the record-injection seam entirely, and the published index carried
75 rendered pages and not one concept, casilla, legal, or CLI record — while every
search test in the tree stayed green, because they all built in ``full`` mode.
The build was correct, the deployment was not, and nothing compared the two.

So this gate observes the SHIPPED ARTEFACT, never the build configuration. It
resolves the injector from the real deploy environment through the production
resolver, writes a real Pagefind index over real built HTML, and then reads the
record kinds back out of that index through ``pagefind.js`` — the same API the
reader's palette calls. A gate that asserted an environment value instead would
have passed on every day this defect was live.

The same blind spot then recurred one level down, per root. The injector pinned
its records to the English index while a ``--language es`` build renders pages
Pagefind indexes as ``es``, and the reader's palette auto-loads ONLY the index
matching the page it is on. Measured on 2026-08-01 against a real built artefact
under the deployment's own environment: the Spanish root wrote an ``es`` index of
3 pages beside an ``en`` index holding all 12 injected records, the palette
fetched ``wasm.es.pagefind`` alone, and its ``kind`` filters came back ``None`` —
a Spanish reader got rendered prose and nothing else. Every gate in the tree
stayed green, because the deploy test asserted only that the injector RESOLVES
per language, the artefact gate built its fixture in English only, and the
deployment's localized-root validation accepts any non-empty index chunks, which
rendered pages alone satisfy.

The published site now has ONE index, at its apex over every language root, and
no root carries one of its own. That removes the stranding the per-root half was
written against -- there is no second split a record can sit in -- and moves the
property a reader depends on from "which index this root wrote" to "what this
reader's language filter reaches in the one index". So the site is built here the
way the publisher builds it (``dev.deploy.docs_site_build._indexed_roots`` over
four real roots into one apex index, with the injector resolved from the real
deploy site environment), and the half below asserts, per READER LANGUAGE and
against that BUILT ARTEFACT through ``pagefind.js``, that the reader reaches
every decided record kind, that the records name their language, and that a
declared term in any language recalls the record -- never a decision, never
English only, never a non-emptiness check. The corpus is also asserted to be
indexed ONCE, which is what four indexes could not be asked.

Cost note: the full corpus is 7,890 records and takes about fifteen minutes to
write, which is long enough that the gate would be deselected in practice and
deselection is its own false green. The injection is therefore bounded to a few
real records per kind. The projections, the injector object, the Pagefind write,
and the artefact read are all the production ones; only the row count is
bounded, and the row count is not the property under test.
"""

from __future__ import annotations

import gzip
import json
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

import dev.docs.i18n as _docs_i18n
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT
from dev.deploy.docs_delivery_contracts import CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL
from dev.deploy.docs_delivery_probe import public_delivery_checks
from dev.deploy.docs_site_build import _indexed_roots
from dev.deploy.docs_site_languages import (
    language_build_command,
    language_build_environment,
    localized_languages,
    site_build_environment,
)
from dev.docs.build_paths import docs_html_root

from ..build import docs_build_language, pagefind_index_mode, resolve_record_injector
from ..pagefind_index import DECIDED_INJECTED_RECORD_KINDS, SHARED_INDEX_LANGUAGE, build_shared_search_index
from ..pagefind_inject import InjectionStats
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/docs/tests -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_BUILT_HTML = docs_html_root(_REPO_ROOT)

#: Record kinds the shipped index is required to carry. A kind absent from the
#: built index means a reader cannot reach that surface at all.
#:
#: Read from the authority rather than mirrored beside it. The owning module
#: is documented to GROW -- "when a new injector ships, add its kind here in
#: the same change" -- and a copy kept here would not grow with it, leaving
#: this deployment contract asserting the older, smaller inventory while the
#: new kind travelled unverified. Every other consumer already imports it.
_DECIDED_RECORD_KINDS = DECIDED_INJECTED_RECORD_KINDS

#: Real records per kind for the bounded injection (see the module docstring).
_SAMPLE_PER_KIND = 4

#: Every language the published site has a root for, and so every language a
#: reader can be reading in. Derived from the deploy module's own set so a new
#: translation target joins this gate without a second hand-listed set.
#:
#: It is the parametrization of the reader-facing half below. It was once the
#: set of roots whose OWN index was measured; the site has one index now, so
#: what varies between these cases is the language a reader's search filters by,
#: not which index answers it.
_READER_LANGUAGES: tuple[str, ...] = localized_languages()

#: Pages per root fixture. Small on purpose (see the module docstring's cost
#: note); the property under test is what a reader's language filter reaches,
#: not how many pages a root has.
_PAGES_PER_ROOT = 3


@dataclass(frozen=True)
class _IndexReach:
    """What one read of the built index through ``pagefind.js`` reached.

    Attributes:
        kinds: ``{record kind: count}``.
        page_urls: The URLs of the rendered PAGES the read returned, empty for
            an index-wide inventory read, which asks for kinds alone.
    """

    kinds: dict[str, int]
    page_urls: tuple[str, ...]


def _index_reach(site: Path, *, page: str, language: str | None = None) -> _IndexReach:
    """Return what Pagefind reaches in the built index, read in a real browser.

    Reads through ``pagefind.js`` in a real browser against a real HTTP server:
    the record kinds a reader's palette can actually narrow by, taken from the
    written artefact rather than from the injection's own report.

    ``site`` is the directory served -- the site's apex, where its one index
    lives -- and ``page`` is the page the reader is on, which is inside a
    language root. Both are needed because the index is no longer beside the
    pages that load it.

    With ``language`` the counts are those REACHABLE BY A READER of that
    language, taken from a filtered search rather than from the index-wide
    inventory. That distinction is the whole of what one index changes: the
    inventory would report every kind present while a reader of one language
    reached none of them, because the filter and not the index is what separates
    the languages now. The URLs of the PAGES that search returns come back too,
    so a reader being answered with another language's pages is visible here.
    """
    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            browser_page = browser.new_page()
            browser_page.goto(f"http://127.0.0.1:{port}/{page}", wait_until="networkidle")
            counted = browser_page.evaluate(
                """async (language) => {
                  const pf = await import('/pagefind/pagefind.js');
                  await pf.options({});
                  await pf.init();
                  if (!language) {
                    const all = await pf.filters();
                    return { kinds: (all && all.kind) || {}, pages: [] };
                  }
                  /* A filter-only search returns every record the language
                     reaches; its kinds are counted off the records themselves,
                     because the response's own filter counts come back empty
                     for a null query. */
                  const response = await pf.search(null, { filters: { language: [language] } });
                  const rows = await Promise.all(response.results.map((r) => r.data()));
                  const kinds = {};
                  const pages = [];
                  for (const row of rows) {
                    const kind = row.meta && row.meta.kind;
                    /* A row with no kind is a rendered page; an injected record
                       carries one. Their URLs differ in nature, so they are
                       reported apart. */
                    if (kind) kinds[kind] = (kinds[kind] || 0) + 1;
                    else pages.push(row.url);
                  }
                  return { kinds: kinds, pages: pages };
                }""",
                language,
            )
            browser.close()
    return _IndexReach(kinds=dict(counted.get("kinds") or {}), page_urls=tuple(counted.get("pages") or ()))


def _served_page(root: Path, language: str) -> str:
    """Return the page a reader of ``language`` is put on, relative to the apex."""
    pages = sorted(path.name for path in scan_directory(root / language, pattern="*.html"))
    if not pages:
        pytest.fail(f"the {language!r} root at {root / language} holds no page to read from")
    return f"{language}/{pages[0]}"


def _indexed_page_baseline(scratch: Path, roots: Mapping[str, Path]) -> int:
    """Return how many of every root's pages Pagefind writes into one index.

    A separate no-injection pass over copies of the same page corpora, composed
    the way the publisher composes them. Pagefind reports a page for every file
    it walks but writes an index entry only for those carrying indexable body
    content under the configured ``root_selector``, so the file count is not the
    index count and must be measured. Cheap: the directory pass over a handful
    of pages per root costs seconds, and no record projection runs.
    """
    copies: dict[str, Path] = {}
    for language, root in roots.items():
        copy = scratch / language
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns("pagefind"))
        copies[language] = copy
    build_shared_search_index(_indexed_roots(copies), scratch)
    entry = json.loads((scratch / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    return sum(int(split["page_count"]) for split in entry["languages"].values())


def _root_page_corpus(apex: Path, language: str) -> Path:
    """Write one published root's page corpus, rendered in that root's own language.

    The root is ``apex/<language>``, which is where the publisher puts it and
    what gives its pages their addresses in the one index.

    Prefers the real localized root at ``CADRUMO_DOCS_BUILD_ROOT/html/<language>`` when the
    machine has built one. Otherwise it takes the real English pages and
    retargets the single signal the index pass reads to decide a page's
    language -- the ``<html lang>`` attribute, which Sphinx writes from
    ``CADRUMO_DOCS_LANGUAGE`` and which the pass refuses to disagree with. The
    localized prose differs, but prose is not the property under test: this gate
    measures what a reader of each language reaches through the language filter,
    and the language attribute alone decides which filter value a page carries.
    Building a real localized Sphinx root per language here would cost minutes
    each, and the localized builds themselves are already covered by the
    ``test_docs_build_localized_<lang>`` gates.
    """
    site = apex / language
    site.mkdir(parents=True)
    localized_root = _BUILT_HTML / language
    sources = (
        scan_directory(localized_root, pattern="*.html", recursive=True) if language != OutputLanguage.EN.value else ()
    )
    if len(sources) >= _PAGES_PER_ROOT:
        for source in sources[:_PAGES_PER_ROOT]:
            (site / source.name).write_bytes(source.read_bytes())
        return site
    if not _BUILT_HTML.is_dir():
        pytest.fail(
            f"no built documentation HTML at {_BUILT_HTML}; this gate reads the shipped "
            "artefact, so it needs a real build to read. Run the docs build first.",
        )
    english = scan_directory(_BUILT_HTML, pattern="*.html")[:_PAGES_PER_ROOT]
    if len(english) < _PAGES_PER_ROOT:
        pytest.fail(
            f"need {_PAGES_PER_ROOT} built pages under {_BUILT_HTML} to assemble a root corpus; "
            "this gate reads a real artefact, so it needs a real build to read.",
        )
    for source in english:
        text = source.read_text(encoding="utf-8", errors="replace")
        retargeted, count = re.subn(r'(<html[^>]*?)\blang="[^"]*"', rf'\1lang="{language}"', text, count=1)
        assert count == 1, f"built page {source.name} carries no <html lang> attribute to retarget"
        (site / source.name).write_text(retargeted, encoding="utf-8")
    return site


@dataclass(frozen=True)
class _PublishedSite:
    """The site's one built search index and the counts behind it.

    Attributes:
        apex: The directory the index was written into, above every root. It is
            what a page loads the bundle from, so it is what the reads serve.
        roots: ``{language: root directory}``, each under the apex.
        stats: The injection's own report; ``None`` if the deploy environment
            injected nothing, which is the live defect this gate exists for.
        entry: The parsed ``pagefind-entry.json`` the index wrote.
        indexed_pages: Pages across every root that Pagefind actually indexed,
            measured by a separate no-injection pass.
        any_page: A page inside a language root, for reads whose subject is the
            index as a whole rather than one reader's language.
    """

    apex: Path
    roots: Mapping[str, Path]
    stats: InjectionStats | None
    entry: dict[str, dict[str, dict[str, int]]]
    indexed_pages: int
    any_page: str


@pytest.fixture(scope="module")
def published_site(tmp_path_factory: pytest.TempPathFactory) -> _PublishedSite:
    """Build the site's ONE index over every published root, as the publisher does.

    The composition is the publisher's, not a second reading of it: the roots
    are paired with the addresses they have in the served site by
    :func:`~dev.deploy.docs_site_build._indexed_roots`, and the injector is
    resolved by the production resolver from the real deploy site environment,
    which is the environment the publisher's index pass resolves it from. A gate
    that composed its own mapping or its own mode would agree with itself while
    the publish shipped something else, which is how every defect in this
    module's history stayed invisible.

    Module-scoped: one index build and one baseline pass serve every test below,
    where four per-root builds and four baselines once did.
    """
    scratch = tmp_path_factory.mktemp("site")
    apex = scratch / "html"
    roots = {language: _root_page_corpus(apex, language) for language in _READER_LANGUAGES}
    indexed_pages = _indexed_page_baseline(scratch / "baseline", roots)
    captured: list[InjectionStats] = []
    build_shared_search_index(
        _indexed_roots(roots),
        apex,
        inject=resolve_record_injector(
            _REPO_ROOT,
            site_build_environment(base_environment={}),
            on_complete=captured.append,
            sample_per_kind=_SAMPLE_PER_KIND,
        ),
    )
    entry = json.loads((apex / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    return _PublishedSite(
        apex=apex,
        roots=roots,
        stats=(captured[0] if captured else None),
        entry=entry,
        indexed_pages=indexed_pages,
        any_page=_served_page(apex, _docs_i18n.DEFAULT_SOURCE_LANGUAGE),
    )


def test_deploy_environment_resolves_the_record_injector() -> None:
    """The site's index contract selects record injection; no root indexes itself.

    The narrow half of the gate: the decision itself, read through the
    production resolver rather than a re-derived copy of its mapping. Necessary
    but not sufficient, which is why the artefact tests below are the real gate.

    Both halves are asserted because they are one decision. The site has ONE
    index, built over every root once they are all built, so the environment
    that index pass resolves its injector from must select ``full`` -- and each
    ROOT's own build must select ``none``, because a root that indexed itself
    would write an index the served site never loads and would restore exactly
    the per-root splitting the one index removed. Asserting only the first would
    leave that regression unmeasured.
    """
    assert resolve_record_injector(_REPO_ROOT, site_build_environment(base_environment={})) is not None
    for language in localized_languages():
        # The cli-sequence goldens gate is irrelevant to the index contract and
        # its verdict cannot vary by root, so these probes take the documented
        # opt-out rather than paying for it once per language.
        environment = language_build_environment(language, check_sequences=False)
        assert pagefind_index_mode(environment) == "none", (
            f"root {language!r} would write its own search index; the site has one, at its apex"
        )
        assert resolve_record_injector(_REPO_ROOT, environment) is None, (
            f"root {language!r} would inject the record corpus into an index of its own"
        )


def test_deployed_index_carries_every_decided_record_kind(published_site: _PublishedSite) -> None:
    """Every decided record kind is present in the index the deployment builds.

    Read back through Pagefind's own API over the written artefact: this is what
    a reader's palette can find. Under the pages-only contract this list is
    empty, which is exactly the live defect.
    """
    assert published_site.stats is not None, "the deploy environment injected no records at all"
    kinds = _index_reach(published_site.apex, page=published_site.any_page).kinds

    missing = sorted(_DECIDED_RECORD_KINDS - set(kinds))
    assert not missing, f"the deployed index carries no records of kind(s) {missing}; found {sorted(kinds)}"
    assert all(kinds[kind] > 0 for kind in _DECIDED_RECORD_KINDS)


def test_deployed_pagefind_entry_counts_the_injected_records(published_site: _PublishedSite) -> None:
    """The shipped ``pagefind-entry.json`` reflects every root's pages PLUS the records.

    The entry file is the one artefact a live check can read over HTTP without a
    browser, so it is worth pinning what it proves: its ``page_count`` counts
    every indexed record, so a full-mode index always exceeds its page count. A
    deployed entry whose count equals the page count is a pages-only index —
    the live site read 75 pages and 75 records' worth of nothing.

    One split, not one per detected page language, is the mechanism a reader
    depends on: a reader's bundle loads a single split, so splitting by language
    is what once stranded records a root's palette never fetched -- an
    English-pinned injection beside an ``es`` page index produced ``{es: 3
    pages, en: 12 records}`` and a palette that fetched only the ``es`` half.
    With one split that stranding has no shape to take, and this asserts the
    shape is gone AND that the split holds exactly the pages plus the records.
    The split's name is the index's forced language and carries no claim about
    the pages, whose own language is a FILTER; what each reader language reaches
    through that filter is asserted below.

    The page half of that sum is MEASURED, not assumed from the number of files
    copied. Pagefind reports a page count for every file it walks but indexes
    only those with indexable body content, and the two diverge: measured on
    2026-08-01, a three-file fixture whose selection had drifted onto two
    generated casilla pages reported three pages and wrote ONE index entry, so
    an assumed ``3 + records`` was arithmetically wrong while both the injection
    and the index were correct. Taking the baseline from a no-injection pass over
    the same corpora keeps the assertion exact instead of coupling it to which
    files the fixture happens to pick.
    """
    stats = published_site.stats
    assert stats is not None

    languages = published_site.entry["languages"]
    # The site's one index is one split, under the forced language. Its name
    # says nothing about the pages' own languages, which are a filter.
    assert sorted(languages) == [SHARED_INDEX_LANGUAGE], f"the built index is not one split: {sorted(languages)}"

    indexed = languages[SHARED_INDEX_LANGUAGE]["page_count"]
    assert indexed == published_site.indexed_pages + stats.custom_records_written, (
        f"entry page_count {indexed} does not equal {published_site.indexed_pages} indexed pages of "
        f"{len(published_site.roots)} roots + {stats.custom_records_written} injected records"
    )
    assert indexed > published_site.indexed_pages, (
        "the entry count shows pages only; no records reached the shipped index"
    )


def test_the_record_corpus_is_indexed_once_for_the_whole_site(published_site: _PublishedSite) -> None:
    """A record the languages share is one fragment in the index, not one per language.

    The property four indexes could not be asked, and the reason the site has
    one: the same casilla corpus was written once per language, which is most of
    the 63.5 MB in 60,232 files the four indexes weighed. The count above would
    still balance if the corpus were injected per language into one split, so
    this reads the artefact for the record's own destination and requires
    exactly one fragment to carry it.
    """
    target, _terms = _probe_record()

    carrying = [
        fragment
        for fragment in scan_directory(
            published_site.apex / "pagefind" / "fragment", pattern="*.pf_fragment", recursive=True
        )
        if _fragment_target(fragment) == target
    ]

    assert len(carrying) == 1, (
        f"{len(carrying)} fragments carry the record destined for {target!r}; a record the languages share "
        "is injected once into the site's one index, so more than one is the per-language duplication "
        "that index exists to remove"
    )


def _fragment_target(fragment: Path) -> str | None:
    """Return the record destination one written fragment declares, if any.

    The payload is gzipped JSON behind a short marker. A rendered page carries
    no ``target`` in its meta; an injected record carries the destination its
    group was keyed by, which is what makes a record countable by destination.
    """
    text = gzip.decompress(fragment.read_bytes()).decode("utf-8", errors="replace")
    start = text.find("{")
    if start < 0:
        return None
    payload = json.loads(text[start:])
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    target = meta.get("target")
    return target if isinstance(target, str) else None


def test_every_language_root_is_built_and_verified_after_publish() -> None:
    """Each localized root is published under the same contract and checked live.

    The second half of the deployment contract: the record kinds must reach
    every root, not only the English one. The publisher builds each localized
    root, and its post-publish endpoint checks must require each one to answer
    200 — the roots were built but unreachable live for two weeks, so an
    unverified root is the failure mode this pins.
    """
    checks = dict(public_delivery_checks())

    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        assert checks.get(f"{base_url}/") == 200
        for language in localized_languages():
            url = f"{base_url}/{language}/"
            assert checks.get(url) == 200, f"publish does not verify the {language!r} root is reachable ({url})"


def test_the_gate_reads_the_artefact_not_the_configuration(published_site: _PublishedSite) -> None:
    """The artefact read is grounded in the written index, not the injection report.

    Guards the gate against becoming a tautology of its own build call: the
    fragments written to disk must carry the kinds, so the assertions above
    cannot pass on a report while the artefact is empty.
    """
    fragments = scan_directory(published_site.apex / "pagefind" / "fragment", pattern="*.pf_fragment", recursive=True)
    assert fragments, "the built index wrote no fragments"

    on_disk: set[str] = set()
    for fragment in fragments:
        payload = gzip.decompress(fragment.read_bytes())
        for kind in _DECIDED_RECORD_KINDS:
            if f'"kind":"{kind}"'.encode() in payload or f'"kind": "{kind}"'.encode() in payload:
                on_disk.add(kind)
    assert on_disk >= _DECIDED_RECORD_KINDS, (
        f"kinds {sorted(_DECIDED_RECORD_KINDS - on_disk)} are absent from the written fragments"
    )


# ---------------------------------------------------------------------------
# Per reader language: what the one index answers a reader of each language with
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", _READER_LANGUAGES)
def test_every_record_declares_every_published_language(
    language: str,
    published_site: _PublishedSite,
) -> None:
    """A record is injected once and declares every published language.

    Record-count parity used to mean comparing four per-root corpora for equal
    size. One index makes that structural -- there is one corpus -- and moves
    the property a reader depends on onto the record's own ``language`` filter:
    a reader reaches the corpus because the record names their language, so a
    language missing from a record's filter is a reader who sees no records at
    all while every count still agrees.

    Parametrized by reader language so the failure names the reader who would
    see nothing, and the whole declared set is asserted beside it so a language
    the site does not publish cannot creep in unnoticed either.
    """
    stats = published_site.stats
    assert stats is not None
    assert stats.custom_records_written > 0, "the site shipped an empty record corpus"
    assert language in stats.languages, (
        f"no record declares {language!r}, so a reader of that language reaches no records at all; "
        f"the corpus declares {sorted(stats.languages)}"
    )
    assert sorted(stats.languages) == sorted(member.value for member in OutputLanguage), stats.languages


@pytest.mark.parametrize("language", _READER_LANGUAGES)
def test_every_reader_language_narrows_by_every_decided_record_kind(
    language: str,
    published_site: _PublishedSite,
) -> None:
    """Read through ``pagefind.js``: a reader of this language sees every kind, and its own pages.

    The reader-visible half, and the one that is not satisfiable by counting
    files. On the defective Spanish root this call returned ``None`` for the
    ``kind`` filters while the index directory was full of English fragments.
    The counts are taken through the reader's own ``language`` filter, which is
    what separates the languages inside the one index -- so this is also where a
    reader being answered with another language's pages would show: the pages
    the filtered search returns must all be addressed inside this reader's root.
    """
    reach = _index_reach(
        published_site.apex,
        page=_served_page(published_site.apex, language),
        language=language,
    )

    missing = sorted(_DECIDED_RECORD_KINDS - set(reach.kinds))
    assert not missing, (
        f"a reader of {language!r} cannot narrow by kind(s) {missing}; the palette sees {sorted(reach.kinds)}"
    )
    assert all(reach.kinds[kind] > 0 for kind in _DECIDED_RECORD_KINDS)
    assert reach.page_urls, f"a reader of {language!r} reaches no pages at all"
    foreign = [url for url in reach.page_urls if not url.startswith(f"/{language}/")]
    assert not foreign, f"a reader of {language!r} is answered with pages outside that language's root: {foreign}"


def _search_urls(site: Path, queries: tuple[str, ...], language: str, *, page: str) -> dict[str, list[str]]:
    """Run each query through ``pagefind.js`` from one page and return the result URLs.

    One browser session, one Pagefind init, every query — the same search call
    the reader's palette makes, narrowed to the reader's language exactly as the
    palette narrows it. ``site`` is the apex that carries the one index and
    ``page`` is the page inside a language root the reader is on.
    """
    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            browser_page = browser.new_page()
            browser_page.goto(f"http://127.0.0.1:{port}/{page}", wait_until="networkidle")
            found = browser_page.evaluate(
                """async ({ queries, language }) => {
                  const pf = await import('/pagefind/pagefind.js');
                  await pf.options({});
                  await pf.init();
                  const out = {};
                  for (const q of queries) {
                    const search = await pf.search(q, { filters: { language: [language] } });
                    const hits = await Promise.all(
                      search.results.slice(0, 25).map((r) => r.data().then((d) => d.url))
                    );
                    out[q] = hits;
                  }
                  return out;
                }""",
                {"queries": list(queries), "language": language},
            )
            browser.close()
    return {query: list(hits) for query, hits in found.items()}


def _probe_record() -> tuple[str, tuple[str, ...]]:
    """Return one bounded concept record's target plus its declared query terms.

    The terms are the record's OWN declared surface forms — its title and its
    search aliases, which span the four languages ("AEAT" / "Agencia Tributaria",
    "autoliquidacion" / "self-assessment"). Taking them from the record rather
    than hand-picking prose keeps the probe honest: the assertion is that a
    declared term RECALLS the record, not that the content holds some string the
    test also chose.
    """
    from ..pagefind_inject import _bounded_to_sample, _materialise_records

    bounded = _bounded_to_sample(_materialise_records(), _SAMPLE_PER_KIND)
    for record in bounded.records:
        if record.kind.value == "concept" and record.search_aliases:
            return record.target, (record.title, *record.search_aliases)
    pytest.fail("no bounded concept record carries a declared alias to probe cross-lingual recall with")


def _probe_casilla_record() -> tuple[str, tuple[str, ...]]:
    """Return one bounded casilla target plus its declared localized terms.

    The title is the stable modelo/casilla navigation form; the remaining
    terms are the four localized definitions emitted by the registry-backed
    projection. The probe therefore exercises both the exact navigation
    vocabulary and the localized definition content without inventing a
    search phrase or selecting a hand-curated fixture.
    """
    from ..pagefind_inject import _bounded_to_sample, _materialise_records

    bounded = _bounded_to_sample(_materialise_records(), _SAMPLE_PER_KIND)
    for record in bounded.records:
        if record.kind.value != "casilla" or not all(language in record.descriptions for language in OutputLanguage):
            continue
        terms = tuple(
            dict.fromkeys(
                (
                    record.title,
                    *(record.descriptions[language] for language in OutputLanguage),
                )
            )
        )
        return record.target, terms
    pytest.fail("no bounded casilla record carries all four localized definitions to probe cross-lingual recall with")


@pytest.mark.parametrize("language", _READER_LANGUAGES)
def test_every_reader_language_recalls_a_record_by_its_declared_terms_in_any_language(
    language: str,
    published_site: _PublishedSite,
) -> None:
    """A declared term in ANY language recalls the record for EVERY reader language.

    The load-bearing half of locale capability: it is not enough that the one
    index holds the records, a reader of each language must reach them through
    their own filter. The all-language content blob is the mechanism — a
    non-reader-language term loses stemming quality but keeps exact and prefix
    matching, which is the accepted graceful degradation. If this passes only
    for an English reader, the corpus is locale-PARTITIONED rather than
    locale-capable.
    """
    target, terms = _probe_record()
    hits = _search_urls(published_site.apex, terms, language, page=_served_page(published_site.apex, language))

    unrecalled = [term for term in terms if not any(url.endswith(target) for url in hits[term])]
    assert not unrecalled, (
        f"a reader of {language!r} does not recall {target!r} by its declared term(s) {unrecalled}; results were {hits}"
    )


@pytest.mark.parametrize("language", _READER_LANGUAGES)
def test_every_reader_language_recalls_a_casilla_by_its_declared_localized_terms(
    language: str,
    published_site: _PublishedSite,
) -> None:
    """A localized casilla definition recalls its canonical target for every reader language.

    This is the casilla half of the worked-example contract. It reads the title
    and all four localized descriptions from one real bounded projection, so an
    index that carries only pages, only one locale, or records no language
    filter reaches cannot satisfy the assertion by accident.
    """
    target, terms = _probe_casilla_record()
    hits = _search_urls(published_site.apex, terms, language, page=_served_page(published_site.apex, language))

    unrecalled = [term for term in terms if not any(url.endswith(target) for url in hits[term])]
    assert not unrecalled, (
        f"a reader of {language!r} does not recall casilla {target!r} by its declared term(s) "
        f"{unrecalled}; results were {hits}"
    )


#: The translated roots only. The deploy language set carries the source
#: language too, but English is the msgid source with no catalogue to select,
#: so it is deliberately built WITHOUT ``--language`` -- asserting the flag for
#: it would gate the opposite of the decided behaviour.
_TRANSLATED_LANGUAGES: tuple[str, ...] = tuple(
    language for language in localized_languages() if language != _docs_i18n.DEFAULT_SOURCE_LANGUAGE
)


@pytest.mark.parametrize("language", _TRANSLATED_LANGUAGES)
def test_localized_root_command_and_env_agree_on_the_language(language: str) -> None:
    """Pin the seam this gate composes: ``--language <lang>`` becomes the build language.

    The publisher passes the language on the command line and the build driver
    turns it into ``CADRUMO_DOCS_LANGUAGE``, which both ``conf.py`` (page
    language) and the record injector (index language) read. This gate composes
    that key directly, so both ends are pinned here: drop the flag from the
    deploy command, or stop resolving the key into a build language, and this
    fails rather than letting the composition quietly stand for nothing.
    """
    command = language_build_command(language, Path("out"))
    assert "--language" in command, f"the {language!r} deploy command no longer passes --language: {command}"
    assert command[command.index("--language") + 1] == language

    assert docs_build_language({"CADRUMO_DOCS_LANGUAGE": language}) == OutputLanguage(language)
    assert docs_build_language({}) == OutputLanguage.EN


def test_the_source_language_root_is_built_without_a_language_flag() -> None:
    """English is the msgid source, so its root carries no ``--language``.

    The complement of the gate above, asserted rather than left as the silence
    of an excluded parameter. Passing the flag for English would select a
    catalogue that does not exist AND force the user scope, dropping the API
    tree that only this root carries -- so the omission is load-bearing, not an
    oversight, and a future edit that "fixes" it by adding the flag fails here.
    """
    command = language_build_command(_docs_i18n.DEFAULT_SOURCE_LANGUAGE, Path("out"))

    assert "--language" not in command, f"the source-language root must not select a catalogue: {command}"
    assert "--scope" not in command, f"the source-language root must keep the full scope: {command}"
    assert docs_build_language({}) == OutputLanguage.EN

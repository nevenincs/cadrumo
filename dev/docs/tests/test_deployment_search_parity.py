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
rendered pages alone satisfy. So the per-root half below asserts against each
root's BUILT ARTEFACT that the root's OWN loaded index carries the full record
corpus, with count parity across roots — never a decision, never English only,
never a non-emptiness check.

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

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ...deploy.docs_static_site import (
    CANONICAL_DOCS_BASE_URL,
    DEFAULT_SOURCE_LANGUAGE,
    DeploymentTarget,
    _language_build_command,
    _language_build_environment,
    _localized_languages,
    _public_delivery_checks,
    _site_build_environment,
)
from ..build import docs_build_language, resolve_record_injector
from ..pagefind_index import build_search_index
from ..pagefind_inject import InjectionStats
from ._http_serve_support import serve_directory

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/docs/tests -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"

#: Record kinds the shipped index is required to carry. A kind absent from the
#: built index means a reader cannot reach that surface at all.
#:
#: This set mirrors ``pagefind_index.DECIDED_INJECTED_RECORD_KINDS`` and is the
#: deployment contract's inventory. It must grow with the emitted projection;
#: LEGAL now travels through the generated legal-reference projection and must
#: remain covered here as well.
_DECIDED_RECORD_KINDS = frozenset({"concept", "casilla", "legal", "cli"})

#: Real records per kind for the bounded injection (see the module docstring).
_SAMPLE_PER_KIND = 4


def _fixture_site(tmp_path: Path, *, pages: int = 3) -> Path:
    """Copy a small real built-HTML subset plus the real pagefind.yml into tmp."""
    if not _BUILT_HTML.is_dir():
        pytest.fail(
            f"no built documentation HTML at {_BUILT_HTML}; this gate reads the shipped "
            "artefact, so it needs a real build to read. Run the docs build first.",
        )
    site = tmp_path / "site"
    site.mkdir()
    html = scan_directory(_BUILT_HTML, pattern="*.html", recursive=True)[:pages]
    if not html:
        pytest.fail(f"built documentation HTML at {_BUILT_HTML} contains no pages.")
    for source in html:
        dest = site / source.relative_to(_BUILT_HTML)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, dest)
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


def _kinds_in_built_index(site: Path) -> dict[str, int]:
    """Return the ``kind`` filter counts read out of the built index by Pagefind.

    Reads through ``pagefind.js`` in a real browser against a real HTTP server:
    the record kinds a reader's palette can actually narrow by, taken from the
    written artefact rather than from the injection's own report.
    """
    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        page_name = sorted(p.name for p in scan_directory(site, pattern="*.html"))[0]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/{page_name}", wait_until="networkidle")
            filters = page.evaluate(
                """async () => {
                  const pf = await import('/pagefind/pagefind.js');
                  await pf.options({});
                  await pf.init();
                  return await pf.filters();
                }"""
            )
            browser.close()
    return dict(filters.get("kind") or {})


def _indexed_page_baseline(scratch: Path, site: Path) -> int:
    """Return how many of ``site``'s pages Pagefind actually writes into the index.

    A separate no-injection pass over a copy of the same page corpus. Pagefind
    reports a page for every file it walks but writes an index entry only for
    those carrying indexable body content under the configured ``root_selector``,
    so the file count is not the index count and must be measured. Cheap: the
    directory pass over a handful of pages costs seconds, and no record
    projection runs.
    """
    copy = scratch / "pages-only"
    shutil.copytree(site, copy, ignore=shutil.ignore_patterns("pagefind"))
    build_search_index(copy, inject=None)
    entry = json.loads((copy / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    return sum(int(split["page_count"]) for split in entry["languages"].values())


def _build_deployed_index(site: Path) -> InjectionStats | None:
    """Build the index the way the DEPLOYMENT would, and return the injection stats.

    The injector comes from the production resolver applied to the real deploy
    build environment, so the mode-to-injector decision under test is the
    deployment's own. ``None`` means the deploy environment injected nothing.
    """
    captured: list[InjectionStats] = []
    injector = resolve_record_injector(
        _REPO_ROOT,
        _site_build_environment(base_environment={}),
        on_complete=captured.append,
        sample_per_kind=_SAMPLE_PER_KIND,
    )
    build_search_index(site, inject=injector)
    return captured[0] if captured else None


def test_deploy_environment_resolves_the_record_injector() -> None:
    """The deploy environment must select record injection, not the pages-only contract.

    The narrow half of the gate: the decision itself, read through the
    production resolver rather than a re-derived copy of its mapping. Necessary
    but not sufficient, which is why the artefact test below is the real gate.
    """
    assert resolve_record_injector(_REPO_ROOT, _site_build_environment(base_environment={})) is not None
    for language in _localized_languages():
        # The cli-sequence goldens gate is irrelevant to the injector decision
        # and its verdict cannot vary by root, so these probes take the
        # documented opt-out rather than paying for it once per language.
        environment = _language_build_environment(language, check_sequences=False)
        assert resolve_record_injector(_REPO_ROOT, environment) is not None, (
            f"localized root {language!r} would deploy without injected search records"
        )


def test_deployed_index_carries_every_decided_record_kind(tmp_path: Path) -> None:
    """Every decided record kind is present in the index the deploy environment builds.

    Read back through Pagefind's own API over the written artefact: this is what
    a reader's palette can find. Under the pages-only contract this list is
    empty, which is exactly the live defect.
    """
    site = _fixture_site(tmp_path)
    stats = _build_deployed_index(site)

    assert stats is not None, "the deploy environment injected no records at all"
    kinds = _kinds_in_built_index(site)

    missing = sorted(_DECIDED_RECORD_KINDS - set(kinds))
    assert not missing, f"the deployed index carries no records of kind(s) {missing}; found {sorted(kinds)}"
    assert all(kinds[kind] > 0 for kind in _DECIDED_RECORD_KINDS)


def test_deployed_pagefind_entry_counts_the_injected_records(tmp_path: Path) -> None:
    """The shipped ``pagefind-entry.json`` reflects pages PLUS injected records.

    The entry file is the one artefact a live check can read over HTTP without a
    browser, so it is worth pinning what it proves: its ``page_count`` counts
    every indexed record, so a full-mode index always exceeds its page count. A
    deployed entry whose count equals the page count is a pages-only index —
    the live site read 75 pages and 75 records' worth of nothing.

    The page half of that sum is MEASURED, not assumed from the number of files
    copied. Pagefind reports a page count for every file it walks but indexes
    only those with indexable body content, and the two diverge: measured on
    2026-08-01, a three-file fixture whose selection had drifted onto two
    generated casilla pages reported three pages and wrote ONE index entry, so
    an assumed ``3 + records`` was arithmetically wrong while both the injection
    and the index were correct. Taking the baseline from a no-injection pass over
    the same corpus keeps the assertion exact instead of coupling it to which
    files the fixture happens to pick.
    """
    site = _fixture_site(tmp_path, pages=3)
    baseline = _indexed_page_baseline(tmp_path / "baseline", site)
    stats = _build_deployed_index(site)
    assert stats is not None

    entry = json.loads((site / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    languages = entry["languages"]
    assert "en" in languages, f"the built index carries no English split: {sorted(languages)}"

    indexed = languages["en"]["page_count"]
    assert indexed == baseline + stats.custom_records_written, (
        f"entry page_count {indexed} does not equal {baseline} indexed pages + "
        f"{stats.custom_records_written} injected records"
    )
    assert indexed > baseline, "the entry count shows pages only; no records reached the shipped index"


def test_every_language_root_is_built_and_verified_after_publish() -> None:
    """Each localized root is published under the same contract and checked live.

    The second half of the deployment contract: the record kinds must reach
    every root, not only the English one. The publisher builds each localized
    root, and its post-publish endpoint checks must require each one to answer
    200 — the roots were built but unreachable live for two weeks, so an
    unverified root is the failure mode this pins.
    """
    checks = dict(_public_delivery_checks(DeploymentTarget(bucket="cadrumo-docs-000000000000", distribution_id="E1")))

    assert checks.get(f"{CANONICAL_DOCS_BASE_URL}/") == 200
    for language in _localized_languages():
        url = f"{CANONICAL_DOCS_BASE_URL}/{language}/"
        assert checks.get(url) == 200, f"publish does not verify the {language!r} root is reachable ({url})"


def test_the_gate_reads_the_artefact_not_the_configuration(tmp_path: Path) -> None:
    """The artefact read is grounded in the written index, not the injection report.

    Guards the gate against becoming a tautology of its own build call: the
    fragments written to disk must carry the kinds, so the assertions above
    cannot pass on a report while the artefact is empty.
    """
    site = _fixture_site(tmp_path)
    _build_deployed_index(site)

    fragments = scan_directory(site / "pagefind" / "fragment", pattern="*.pf_fragment", recursive=True)
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
# Per-root parity: every published root's OWN loaded index carries the corpus
# ---------------------------------------------------------------------------

#: Every LANGUAGE the deployment publishes a root in: the English default root
#: at ``/`` plus each localized subroot. Derived from the deploy module's own
#: language set so a new translation target joins this gate without a second
#: hand-listed set.
#:
#: Deduplicated, because that set already carries the source language: English
#: is published twice, at ``/`` and at ``/en/``, and those two roots are
#: distinct but carry the SAME language. These gates assert a per-language
#: property, so asserting it twice only collides the shared per-language
#: fixture; the two roots' distinct build commands are pinned separately below.
_ROOT_LANGUAGES: tuple[str, ...] = tuple(
    dict.fromkeys((OutputLanguage.EN.value, *_localized_languages())),
)

#: Pages per root fixture. Small on purpose (see the module docstring's cost
#: note); the property under test is which index the records land in relative to
#: the pages, not how many pages a root has.
_PAGES_PER_ROOT = 3


def _root_build_environment(language: str) -> Mapping[str, str]:
    """Return the environment the deployment builds one root under.

    The English root deploys under ``_site_build_environment``. A localized root
    deploys under ``_language_build_environment`` plus the build language, which
    the publisher passes on the command line (``--language <lang>``) and the
    build driver writes into ``CADRUMO_DOCS_LANGUAGE`` before the index pass
    runs. Composing that one key here stands in for the driver's argv handling,
    which this gate cannot run without paying for a full Sphinx build per
    language; :func:`test_localized_root_command_and_env_agree_on_the_language`
    pins both ends of that seam so the composition cannot drift away from what
    the publisher actually does.
    """
    if language == OutputLanguage.EN.value:
        return _site_build_environment(base_environment={})
    # These probes assert search recall, not the cli-sequence goldens, whose
    # verdict cannot vary by root; they take the documented opt-out so a recall
    # probe does not re-run that gate once per language.
    return {
        **_language_build_environment(language, check_sequences=False),
        "CADRUMO_DOCS_LANGUAGE": language,
    }


def _root_page_corpus(root: Path, language: str) -> Path:
    """Write one root's page corpus, indexed under that root's own language.

    Prefers the real localized root at ``docs/_build/html/<language>`` when the
    machine has built one. Otherwise it takes the real English pages and
    retargets the single signal Pagefind reads to decide a page's language --
    the ``<html lang>`` attribute, which Sphinx writes from the same
    ``CADRUMO_DOCS_LANGUAGE`` the injector now reads. The localized prose
    differs, but prose is not the property under test: this gate measures WHICH
    index the records land in relative to the pages, and the language attribute
    alone decides that. Building a real localized Sphinx root per language here
    would cost minutes each, and the localized builds themselves are already
    covered by ``test_docs_build_localized``.
    """
    site = root / f"site-{language}"
    site.mkdir(parents=True)
    localized_root = _BUILT_HTML / language
    sources = (
        scan_directory(localized_root, pattern="*.html", recursive=True) if language != OutputLanguage.EN.value else ()
    )
    if len(sources) >= _PAGES_PER_ROOT:
        for source in sources[:_PAGES_PER_ROOT]:
            (site / source.name).write_bytes(source.read_bytes())
    else:
        english = scan_directory(_BUILT_HTML, pattern="*.html")[:_PAGES_PER_ROOT]
        if len(english) < _PAGES_PER_ROOT:
            pytest.fail(
                f"need {_PAGES_PER_ROOT} built pages under {_BUILT_HTML} to assemble a root corpus; "
                "this gate reads a real artefact, so it needs a real build to read.",
            )
        for source in english:
            text = source.read_text(encoding="utf-8", errors="replace")
            retargeted, count = re.subn(
                r'(<html[^>]*?)\blang="[^"]*"',
                rf'\1lang="{language}"',
                text,
                count=1,
            )
            assert count == 1, f"built page {source.name} carries no <html lang> attribute to retarget"
            (site / source.name).write_text(retargeted, encoding="utf-8")
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


@dataclass(frozen=True)
class _RootBuild:
    """One deploy root's built search artefact and the counts behind it."""

    language: str
    site: Path
    stats: InjectionStats | None
    entry: dict[str, dict[str, dict[str, int]]]
    indexed_pages: int


def _build_root(root: Path, language: str) -> _RootBuild:
    """Build one root's index the way the DEPLOYMENT builds it, and read it back."""
    site = _root_page_corpus(root, language)
    indexed_pages = _indexed_page_baseline(root / f"baseline-{language}", site)
    captured: list[InjectionStats] = []
    injector = resolve_record_injector(
        _REPO_ROOT,
        _root_build_environment(language),
        on_complete=captured.append,
        sample_per_kind=_SAMPLE_PER_KIND,
    )
    build_search_index(site, inject=injector)
    entry = json.loads((site / "pagefind" / "pagefind-entry.json").read_bytes().decode("utf-8"))
    return _RootBuild(
        language=language,
        site=site,
        stats=(captured[0] if captured else None),
        entry=entry,
        indexed_pages=indexed_pages,
    )


@pytest.fixture(scope="module")
def built_roots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, _RootBuild]:
    """Build every deploy root's index once, and share it across the per-root tests."""
    root = tmp_path_factory.mktemp("roots")
    return {language: _build_root(root, language) for language in _ROOT_LANGUAGES}


@pytest.mark.parametrize("language", _ROOT_LANGUAGES)
def test_every_root_index_carries_the_record_corpus_in_its_own_language(
    language: str,
    built_roots: dict[str, _RootBuild],
) -> None:
    """A root's OWN loaded index holds its pages AND its records, and nothing is stranded.

    The reader's palette auto-loads only the index matching the page language,
    so a root's records must live in that index. Asserting the entry's language
    set is EXACTLY the root's language is what catches the stranding: an
    English-pinned injection on the Spanish root produced ``{es: 3 pages, en: 12
    records}`` and a palette that never fetched the ``en`` split at all.
    """
    built = built_roots[language]
    assert built.stats is not None, f"the {language!r} root's deploy environment injected no records at all"

    languages = dict(built.entry["languages"])
    assert set(languages) == {language}, (
        f"the {language!r} root built index splits {sorted(languages)}; records outside {language!r} "
        f"are stranded in a split this root's palette never loads (site {built.site})"
    )

    indexed = languages[language]["page_count"]
    assert indexed == built.indexed_pages + built.stats.custom_records_written, (
        f"the {language!r} index holds {indexed} entries, not {built.indexed_pages} indexed pages + "
        f"{built.stats.custom_records_written} injected records"
    )


def test_the_record_corpus_is_the_same_size_on_every_root(
    built_roots: dict[str, _RootBuild],
) -> None:
    """Record-count parity: no root ships a narrower corpus than any other.

    Locale capability is not "the localized roots have some records"; it is that
    a reader on any root reaches the SAME corpus. A per-root count divergence is
    how a root would silently degrade while every kind is still nominally
    present.
    """
    written = {language: built_roots[language].stats for language in _ROOT_LANGUAGES}
    assert all(stats is not None for stats in written.values())
    counts = {language: stats.custom_records_written for language, stats in written.items() if stats}
    assert len(set(counts.values())) == 1, f"roots ship different record corpus sizes: {counts}"
    assert all(count > 0 for count in counts.values()), f"a root shipped an empty record corpus: {counts}"


@pytest.mark.parametrize("language", _ROOT_LANGUAGES)
def test_every_root_palette_narrows_by_every_decided_record_kind(
    language: str,
    built_roots: dict[str, _RootBuild],
) -> None:
    """Read through ``pagefind.js`` on each root: the reader sees every decided kind.

    The reader-visible half, and the one that is not satisfiable by counting
    files. On the defective Spanish root this call returned ``None`` for the
    ``kind`` filters while the index directory was full of English fragments.
    """
    kinds = _kinds_in_built_index(built_roots[language].site)

    missing = sorted(_DECIDED_RECORD_KINDS - set(kinds))
    assert not missing, (
        f"a reader on the {language!r} root cannot narrow by kind(s) {missing}; the palette sees {sorted(kinds)}"
    )
    assert all(kinds[kind] > 0 for kind in _DECIDED_RECORD_KINDS)


def _search_urls(site: Path, queries: tuple[str, ...]) -> dict[str, list[str]]:
    """Run each query through ``pagefind.js`` on this root and return the result URLs.

    One browser session, one Pagefind init, every query — the same search call
    the reader's palette makes, against the root's own loaded index.
    """
    with serve_directory(site) as (_httpd, port):
        from playwright.sync_api import sync_playwright

        page_name = sorted(p.name for p in scan_directory(site, pattern="*.html"))[0]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/{page_name}", wait_until="networkidle")
            found = page.evaluate(
                """async (queries) => {
                  const pf = await import('/pagefind/pagefind.js');
                  await pf.options({});
                  await pf.init();
                  const out = {};
                  for (const q of queries) {
                    const search = await pf.search(q);
                    const hits = await Promise.all(
                      search.results.slice(0, 25).map((r) => r.data().then((d) => d.url))
                    );
                    out[q] = hits;
                  }
                  return out;
                }""",
                list(queries),
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


@pytest.mark.parametrize("language", _ROOT_LANGUAGES)
def test_every_root_recalls_a_record_by_its_declared_terms_in_any_language(
    language: str,
    built_roots: dict[str, _RootBuild],
) -> None:
    """A declared term in ANY language recalls the record on EVERY root.

    The load-bearing half of locale capability: it is not enough that the
    localized roots hold records, a reader must reach them. The all-language
    content blob is the mechanism — a non-root-language term loses stemming
    quality but keeps exact and prefix matching, which is the accepted graceful
    degradation. If this passes only on the English root, the corpus is
    locale-PARTITIONED rather than locale-capable.
    """
    target, terms = _probe_record()
    hits = _search_urls(built_roots[language].site, terms)

    unrecalled = [term for term in terms if not any(url.endswith(target) for url in hits[term])]
    assert not unrecalled, (
        f"the {language!r} root does not recall {target!r} by its declared term(s) {unrecalled}; results were {hits}"
    )


@pytest.mark.parametrize("language", _ROOT_LANGUAGES)
def test_every_root_recalls_a_casilla_by_its_declared_localized_terms(
    language: str,
    built_roots: dict[str, _RootBuild],
) -> None:
    """A localized casilla definition recalls its canonical target on every root.

    This is the casilla half of the per-root worked-example contract. It reads
    the title and all four localized descriptions from one real bounded projection, so
    a root that carries only pages, only one locale, or the wrong language
    index cannot satisfy the assertion by accident.
    """
    target, terms = _probe_casilla_record()
    hits = _search_urls(built_roots[language].site, terms)

    unrecalled = [term for term in terms if not any(url.endswith(target) for url in hits[term])]
    assert not unrecalled, (
        f"the {language!r} root does not recall casilla {target!r} by its declared term(s) "
        f"{unrecalled}; results were {hits}"
    )


#: The translated roots only. The deploy language set carries the source
#: language too, but English is the msgid source with no catalogue to select,
#: so it is deliberately built WITHOUT ``--language`` -- asserting the flag for
#: it would gate the opposite of the decided behaviour.
_TRANSLATED_LANGUAGES: tuple[str, ...] = tuple(
    language for language in _localized_languages() if language != DEFAULT_SOURCE_LANGUAGE
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
    command = _language_build_command(language, Path("out"))
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
    command = _language_build_command(DEFAULT_SOURCE_LANGUAGE, Path("out"))

    assert "--language" not in command, f"the source-language root must not select a catalogue: {command}"
    assert "--scope" not in command, f"the source-language root must keep the full scope: {command}"
    assert docs_build_language({}) == OutputLanguage.EN

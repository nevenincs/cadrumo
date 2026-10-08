"""Produce each language root, index the site once, and compose the static apex."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.storage_environment import prepare_temporary_directory
from dev._paths import UTF_8
from dev.docs.build_paths import docs_html_root
from dev.docs.pagefind_index import IndexedRoot
from dev.packaging.command_execution import CommandResult, run_command

from .docs_site_commands import _command_label
from .docs_site_languages import (
    SiteBuild,
    _language_site_url,
    _write_language_entry,
    localized_languages,
    site_build_environment,
    site_builds,
)


def _site_root(repo_root: Path) -> Path:
    """Return the directory the published tree is composed in."""
    return docs_html_root(repo_root)


def _clear_apex(html_root: Path) -> None:
    """Remove everything at the apex except the language roots.

    The apex is composed afresh on every publish, but each language root keeps
    its own subdirectory, and with it the Sphinx environment an incremental
    rebuild reads. Anything else at the apex -- a full site from an earlier
    layout, a stale entry page, the previous publish's search index -- would
    otherwise be uploaded as current.
    """
    html_root.mkdir(parents=True, exist_ok=True)
    roots = set(localized_languages())
    for entry in scan_directory(html_root):
        if entry.name in roots and entry.is_dir():
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _write_apex_sitemap(html_root: Path) -> Path:
    """Write the apex sitemap as an index of every language root's own sitemap."""
    sitemaps = "".join(
        f"  <sitemap><loc>{_language_site_url(language)}/sitemap.xml</loc></sitemap>\n"
        for language in localized_languages()
    )
    path = html_root / "sitemap.xml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{sitemaps}</sitemapindex>\n",
        encoding=UTF_8,
        newline="\n",
    )
    return path


#: The site prefix a built page declares. The apex copy of a root's error page
#: is served one level higher than the page it was built as, so this is the one
#: thing about it that has to change with the move. Matched on the page's bytes,
#: so the copy is byte-for-byte the built page but for this value.
_SITE_PREFIX_META_RE = re.compile(rb'(<meta name="cadrumo-docs-site-prefix" content=")[^"]*(")')


def _write_apex_error_page(source: Path, destination: Path) -> Path:
    """Copy a root's error page to the apex, declaring the apex's own site prefix.

    The page is the source-language root's, built declaring that root's
    directory as its path in the site. At the apex its path in the site is the
    apex, and the declared prefix is what a page's search controller walks back
    to reach the one index: left as the root's, the apex copy would look for the
    index one level above the documentation mount and find nothing.

    Returns:
        The path written.

    Raises:
        SystemExit: If the page declares no site prefix. The apex copy would
            then resolve the index against the apex itself, which happens to be
            right today and would break silently the moment the apex moved; a
            page without the declaration is a template change this composition
            must be told about.
    """
    page, replaced = _SITE_PREFIX_META_RE.subn(rb"\1\2", source.read_bytes(), count=1)
    if not replaced:
        raise SystemExit(
            f"{source} declares no site prefix, so the apex copy of it cannot be given the apex's own. "
            "The search controller resolves the site's one index by walking back the prefix a page "
            "declares; confirm docs/_templates/base.html still emits the cadrumo-docs-site-prefix meta.",
        )
    destination.write_bytes(page)
    return destination


def _compose_apex(html_root: Path) -> None:
    """Give the apex its language entry, error page and sitemap index.

    The apex carries no copy of any site, and no pages of its own beyond these.
    Its 404 page is the source-language root's, whose links are absolute
    (:func:`_write_apex_error_page`); an apex path naming no language root is
    redirected by the Worker to the same page under the source-language root.
    The site's one search index sits at the apex too, written by
    :func:`_index_site` before this runs.
    """
    _write_language_entry(html_root)
    source = html_root / OutputLanguage.EN.value
    _write_apex_error_page(source / "404.html", html_root / "404.html")
    _write_apex_sitemap(html_root)


def _run_site_builds(
    repo_root: Path,
    html_root: Path,
    *,
    builds_for: Callable[[Path], Sequence[SiteBuild]] = site_builds,
) -> None:
    """Run the builds that write every site root, each root into its own subdirectory.

    ``/en/``, ``/es/``, ``/ca/`` and ``/hu/`` are peers, and none of them
    carries a search index: the site has ONE index, at the apex above them, and
    :func:`_index_site` writes it once every root exists. English holds no
    privileged position either: the readers here file Spanish tax, so it sits at
    ``/en/`` like the rest and ``/`` resolves to the reader's own language
    instead (:func:`_write_language_entry`).

    An index a PREVIOUS publish left inside a root is removed before the builds,
    because the source root is kept between publishes for its Sphinx environment
    and nothing in a build that writes no index would clear one. Left in place
    it would upload as current, and a reader who reached it would search last
    release's site.

    The builds run at the same time. Each reads its own copy of the sources and
    writes only below the roots it owns, and each gets its own scratch
    product-storage root, so no two builds share a file they write. The CPUs
    are shared between them (:func:`site_build_jobs`). A build's output is
    printed whole once it finishes; the publish stops, naming every failed
    build, after all of them have finished. It also stops when a build that
    reported success wrote no root for a language it owns, or wrote a search
    index into one: no root indexes itself, whichever build wrote it.

    Args:
        repo_root: Repository root the builds run from.
        html_root: The composed HTML root; each root is its own subdirectory.
        builds_for: DI seam for tests. Production runs the real builds; a test
            passes small real commands to prove the concurrency and isolation
            without paying for a Sphinx build.
    """
    builds = [
        replace(build, environment={**build.environment, "CADRUMO_DOCS_BUILD_ROOT": str(html_root.parent)})
        for build in builds_for(html_root)
    ]
    for build in builds:
        for language in build.languages:
            stale_index = html_root / language / "pagefind"
            if stale_index.exists():
                shutil.rmtree(stale_index)
    written = "; ".join(f"{build.name} writes {', '.join(build.languages)}" for build in builds)
    print(f"Running {len(builds)} site build(s) at once on {os.cpu_count() or 1} CPUs: {written}.", flush=True)
    with tempfile.TemporaryDirectory(prefix="cadrumo-docs-roots-", dir=prepare_temporary_directory()) as scratch:

        def run(index: int, build: SiteBuild) -> CommandResult:
            storage_root = Path(scratch) / str(index)
            storage_root.mkdir()
            return run_command(
                build.command,
                cwd=repo_root,
                environment={**build.environment, "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root)},
            )

        with ThreadPoolExecutor(max_workers=len(builds)) as pool:
            futures = {build.name: pool.submit(run, index, build) for index, build in enumerate(builds)}
            failed: list[str] = []
            for name, future in futures.items():
                _record_site_build_result(name, future, failed)
    if failed:
        raise SystemExit(f"Documentation build failed for {', '.join(failed)}; refusing to publish.")
    absent = sorted(language for build in builds for language in build.languages if not (html_root / language).is_dir())
    if absent:
        raise SystemExit(
            f"The documentation builds reported success and wrote no root for {', '.join(absent)}; refusing to publish."
        )
    indexed = sorted(
        language for build in builds for language in build.languages if (html_root / language / "pagefind").exists()
    )
    if indexed:
        raise SystemExit(
            f"The root(s) {', '.join(indexed)} came out of their build holding a search index of their own; "
            "the site has one, at its apex. Refusing to publish."
        )


def _produce_language_roots(repo_root: Path, html_root: Path) -> dict[str, Path]:
    """Produce every published language root and return where each one landed.

    The ONE place the published pages come from. Everything after it -- the one
    search index, the apex, the preflight, the manifest, the upload -- reads the
    roots this returns and never how they were produced, so the way they are
    produced can change here alone.

    The documentation is not built once per language. The source-language root
    has a build of its own because it alone carries the API reference; every
    translated root comes from ONE compile of the user documentation
    (:func:`~dev.deploy.docs_site_languages.site_builds`).

    Args:
        repo_root: Repository root the build commands run from.
        html_root: The composed HTML root; each language root is its own
            subdirectory of it.

    Returns:
        ``{language: root directory}`` for every published language.
    """
    _run_site_builds(repo_root, html_root)
    return {language: html_root / language for language in localized_languages()}


def indexed_roots(roots: Mapping[str, Path]) -> list[IndexedRoot]:
    """Pair each produced root with the address its pages have in the served site.

    Every published root sits under its own language directory -- no language
    holds the apex path -- so every root carries a prefix and the apex carries
    no pages. The prefix is what makes a page's indexed URL its address on the
    site rather than its path in the build tree.

    Separated from the index pass so the mapping can be read, asserted and fed
    to the real indexer without paying for the record corpus the pass injects.

    Args:
        roots: ``{language: root directory}`` as produced.

    Returns:
        One :class:`~dev.docs.pagefind_index.IndexedRoot` per language, ordered
        by language so an index pass is reproducible.
    """
    return [
        IndexedRoot(html_root=root, language=language, url_prefix=f"{language}/")
        for language, root in sorted(roots.items())
    ]


def _index_site(repo_root: Path, html_root: Path, roots: Mapping[str, Path]) -> None:
    """Build the site's ONE search index over every published root, at the apex.

    Runs after every root is produced, because the index spans all of them. Each
    page is indexed under the address it has in the SERVED site -- under its
    language's directory -- and carries its own language as the filter the
    reader's search narrows by, while a concept, casilla, legal or CLI record is
    injected once and declares every language. The index is written at the apex,
    above the language roots, which is where every language's pages resolve the
    bundle from.

    The English root is the full-scope build and carries the API reference pages
    the others do not, so the one index holds more English pages than any other
    language's. That needs nothing special here: a page is reachable through its
    own language's filter value, so a reader of an API page searches English
    pages and the shared records, exactly as a reader of a how-to does.

    The injector is resolved from :func:`site_build_environment` -- the site's
    own index contract -- so the contract the deploy pins is the contract the
    index is built under, rather than a second reading of the same decision.

    Args:
        repo_root: Repository root, for the committed relevance sweep file.
        html_root: The composed HTML root, which is the site's apex.
        roots: ``{language: root directory}`` as produced.
    """
    from dev.docs.build import ensure_isolated_storage_root, resolve_record_injector
    from dev.docs.pagefind_index import build_shared_search_index
    from dev.docs.pagefind_inject import InjectionStats

    indexed = indexed_roots(roots)
    # The record projections import the application to read the registry
    # authority and the live command tree, exactly as a root build does, so they
    # get build-scoped scratch storage rather than the publishing machine's own.
    ensure_isolated_storage_root()
    stats: list[InjectionStats] = []
    print(f"Indexing the documentation site once over {', '.join(sorted(roots))}", flush=True)
    outcome = build_shared_search_index(
        indexed,
        html_root,
        inject=resolve_record_injector(repo_root, site_build_environment(), on_complete=stats.append),
    )
    written = stats[0].custom_records_written if stats else 0
    print(
        f"Search index compiled: {outcome.page_count} pages of {len(indexed)} languages "
        f"+ {written} shared term/casilla/legal/CLI records "
        f"-> {outcome.html_root / outcome.output_subdir}",
        flush=True,
    )


def _build_site_roots(repo_root: Path) -> Path:
    """Build every language root, index the site once, and compose the apex.

    The write half of a publish's pre-upload work, factored out so the dry run
    below and the publish share one composition. A second composition would be
    free to drift, and the drift would only ever surface on the live site. The
    English root is the one full-scope build, every translated root comes from
    one compile, and the search index is built once over all the roots rather
    than once per root.

    Returns:
        The composed HTML root, carrying every published root and the one index.
    """
    html_root = _site_root(repo_root)
    _clear_apex(html_root)
    roots = _produce_language_roots(repo_root, html_root)
    _index_site(repo_root, html_root, roots)
    _compose_apex(html_root)
    return html_root


def _record_site_build_result(name: str, future: Future[CommandResult], failed: list[str]) -> None:
    """Print one site build's whole output and note it if it failed."""
    result = future.result()
    print(f"+ [{name}] {_command_label(result.argv)} ({result.duration_seconds:.0f}s)", flush=True)
    for stream, text in ((sys.stdout, result.stdout), (sys.stderr, result.stderr)):
        if text:
            print(text, end="" if text.endswith("\n") else "\n", file=stream, flush=True)
    if result.returncode != 0:
        failed.append(f"{name} ({result.returncode})")

"""Build each language root independently and compose the static apex."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from dev._paths import prepare_temporary_directory
from dev.docs import i18n as _docs_i18n
from dev.docs.build_paths import docs_html_root
from dev.packaging.command_execution import CommandResult, run_command

from .docs_delivery_contracts import _UTF_8
from .docs_site_commands import _command_label
from .docs_site_languages import (
    _language_build_environments,
    _language_site_url,
    _write_language_entry,
    language_build_command,
    localized_languages,
    root_build_jobs,
)


def _site_root(repo_root: Path) -> Path:
    """Return the directory the published tree is composed in."""
    return docs_html_root(repo_root)


def _clear_apex(html_root: Path) -> None:
    """Remove everything at the apex except the language roots.

    The apex is composed afresh on every publish, but each language root keeps
    its own subdirectory, and with it the Sphinx environment an incremental
    rebuild reads. Anything else at the apex -- a full site from an earlier
    layout, a stale entry page -- would otherwise be uploaded as current.
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
        encoding=_UTF_8,
        newline="\n",
    )
    return path


def _compose_apex(html_root: Path) -> None:
    """Give the apex its language entry, error page and sitemap index.

    The apex carries no copy of any site. Its 404 page is the source-language
    root's, whose links are absolute; an apex path naming no language root is
    redirected by the Worker to the same page under the source-language root.
    """
    _write_language_entry(html_root)
    source = html_root / _docs_i18n.DEFAULT_SOURCE_LANGUAGE
    shutil.copyfile(source / "404.html", html_root / "404.html")
    _write_apex_sitemap(html_root)


def _build_language_roots(
    repo_root: Path,
    html_root: Path,
    *,
    command_for: Callable[[str, Path], list[str]] = language_build_command,
) -> None:
    """Build every site root into its own subdirectory.

    ``/en/``, ``/es/``, ``/ca/`` and ``/hu/`` are peers, each carrying its own
    Pagefind index. English holds no privileged position: the readers here file
    Spanish tax, so it sits at ``/en/`` like the rest and ``/`` resolves to the
    reader's own language instead (:func:`_write_language_entry`).

    The roots build at the same time. Each reads its own copy of the sources
    and writes only below its own directory, and each gets its own scratch
    product-storage root, so no two builds share a file they write. The CPUs
    are shared between them (:func:`root_build_jobs`). A root's output is
    printed whole once it finishes; the publish stops, naming every
    failed root, after all of them have finished.

    Args:
        repo_root: Repository root the builds run from.
        html_root: The composed HTML root; each root builds into its own
            subdirectory.
        command_for: DI seam for tests. Production runs the real build driver;
            a test passes a small real command to prove the concurrency and
            isolation without paying for four Sphinx builds.
    """
    environments = [
        (language, {**environment, "CADRUMO_DOCS_BUILD_ROOT": str(html_root.parent)})
        for language, environment in _language_build_environments()
    ]
    cpus = os.cpu_count() or 1
    jobs = root_build_jobs([language for language, _ in environments], cpus)
    print(
        f"Building the roots at once on {cpus} CPUs: "
        f"{', '.join(f'{language} with {jobs[language]} workers' for language, _ in environments)}.",
        flush=True,
    )
    with tempfile.TemporaryDirectory(prefix="cadrumo-docs-roots-", dir=prepare_temporary_directory()) as scratch:

        def build(language: str, environment: dict[str, str]) -> CommandResult:
            storage_root = Path(scratch) / language
            storage_root.mkdir()
            command = command_for(language, html_root / language)
            return run_command(
                command,
                cwd=repo_root,
                environment={
                    **environment,
                    "CADRUMO_DOCS_JOBS": jobs[language],
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
                },
            )

        with ThreadPoolExecutor(max_workers=len(environments)) as pool:
            futures = {language: pool.submit(build, language, environment) for language, environment in environments}
            failed: list[str] = []
            for language, future in futures.items():
                _record_language_build_result(language, future, failed)
    if failed:
        raise SystemExit(f"Localized docs build failed for {', '.join(failed)}; refusing to publish.")


def _build_site_roots(repo_root: Path) -> Path:
    """Build every language root and compose the apex around them.

    The write half of a publish's pre-upload work, factored out so the dry run
    below and the publish share one composition. A second composition would be
    free to drift, and the drift would only ever surface on the live site. The
    English root is the one full-scope build; nothing is built twice.

    Returns:
        The composed HTML root, carrying every published root.
    """
    html_root = _site_root(repo_root)
    _clear_apex(html_root)
    _build_language_roots(repo_root, html_root)
    _compose_apex(html_root)
    return html_root


def _record_language_build_result(language: str, future: Future[CommandResult], failed: list[str]) -> None:
    """Record language build result."""
    result = future.result()
    print(f"+ [{language}] {_command_label(result.argv)} ({result.duration_seconds:.0f}s)", flush=True)
    for stream, text in ((sys.stdout, result.stdout), (sys.stderr, result.stderr)):
        if text:
            print(text, end="" if text.endswith("\n") else "\n", file=stream, flush=True)
    if result.returncode != 0:
        failed.append(f"{language} ({result.returncode})")

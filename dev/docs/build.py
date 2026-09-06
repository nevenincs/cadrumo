"""Build only documentation pages affected by local source changes."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

_UTF_8: Final[str] = "utf-8"

_ROOT_FOR_DIRECT_INVOCATION = Path(__file__).resolve().parents[2]
if str(_ROOT_FOR_DIRECT_INVOCATION) not in sys.path:
    sys.path.insert(0, str(_ROOT_FOR_DIRECT_INVOCATION))
if not __package__:
    __package__ = "dev.docs"

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage

from .._paths import REPO_ROOT
from .apidocs.manager import API_SOURCE_PACKAGE, CLI_REFERENCE_SUBTREE, ApiStubManager
from .cli_reference import generate_cli_reference
from .download_matrix import descriptor_path as _download_descriptor_path
from .download_matrix import inject_download_matrix

if TYPE_CHECKING:
    from .pagefind_index import InjectCallback
    from .pagefind_inject import InjectionStats

DOC_SUFFIXES = {".md", ".rst"}
PY_SUFFIX = ".py"


@dataclass(frozen=True)
class DocBuildPlan:
    """Selected documentation sources and generated surfaces needed to build them."""

    targets: list[Path]
    full_build_required: bool
    api_scaffold_required: bool = False
    cli_reference_required: bool = False
    download_matrix_required: bool = False


def _repo_root() -> Path:
    """Return the repository root for this script."""
    return REPO_ROOT


def _executable(name: str) -> str:
    """Resolve an executable name from PATH or abort with a clear error."""
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return resolved


def _run_git(args: list[str], repo_root: Path) -> list[Path]:
    """Run a git path query and return repository-relative paths.

    Args:
        args: Arguments after ``git``.
        repo_root: Repository root used as the process working directory.

    Returns:
        Unique paths listed by git, in output order.
    """
    result = subprocess.run(
        [_executable("git"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    seen: set[Path] = set()
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = Path(line.strip())
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def changed_paths(repo_root: Path, base: str) -> list[Path]:
    """Return changed tracked and untracked paths relevant to the worktree.

    Args:
        repo_root: Repository root.
        base: Git revision used for committed branch changes.

    Returns:
        Deduplicated repository-relative paths.
    """
    queries = [
        ["diff", "--name-only", "--diff-filter=ACMRD", f"{base}...HEAD"],
        ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
        ["diff", "--name-only", "--diff-filter=ACMRD"],
        ["ls-files", "--others", "--exclude-standard"],
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for query in queries:
        for path in _run_git(query, repo_root):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


_SOURCE_PACKAGE_PARTS: Final[tuple[str, ...]] = ("src", API_SOURCE_PACKAGE)


def _is_package_source(rel_path: Path) -> bool:
    """Return whether a changed path is a Python file inside the source package."""
    parts = rel_path.parts
    depth = len(_SOURCE_PACKAGE_PARTS)
    return len(parts) > depth and parts[:depth] == _SOURCE_PACKAGE_PARTS and rel_path.suffix == PY_SUFFIX


def _is_documentable_source(repo_root: Path, rel_path: Path) -> bool:
    """Return whether a changed Python path participates in API stubs.

    The eligibility rule is the stub generator's own
    :meth:`ApiStubManager.excludes_source`, applied FORWARD to the changed
    path, rather than a second copy of it here. Restating the rule is what
    let this planner keep addressing a source package the generator had
    stopped emitting stubs for, so every changed source silently planned no
    API target at all.
    """
    if not _is_package_source(rel_path):
        return False
    manager = ApiStubManager(
        src_cadrumo=repo_root.joinpath(*_SOURCE_PACKAGE_PARTS),
        docs_api=repo_root / "docs" / "api",
    )
    return not manager.excludes_source(repo_root / rel_path)


def _is_cli_reference_source(rel_path: Path) -> bool:
    """Return whether a changed path feeds the generated CLI command reference."""
    if not _is_package_source(rel_path):
        return False
    package_parts = rel_path.parts[len(_SOURCE_PACKAGE_PARTS) :]
    return package_parts[: len(CLI_REFERENCE_SUBTREE)] == CLI_REFERENCE_SUBTREE


def _module_name_for_source(rel_path: Path) -> str:
    """Map a repository-relative Python path under ``src/`` to a dotted module."""
    rel_module = rel_path.relative_to("src").with_suffix("")
    parts = list(rel_module.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _api_stub_targets(module_name: str, docs_api: Path, *, include_parents: bool) -> list[Path]:
    """Return the module stub and package-parent stubs that may be affected."""
    modules = [module_name]
    if include_parents:
        parts = module_name.split(".")
        modules = [".".join(parts[:idx]) for idx in range(1, len(parts) + 1)]
    return [docs_api / f"{name}.rst" for name in modules]


def planned_doc_targets(repo_root: Path, paths: list[Path]) -> DocBuildPlan:
    """Plan Sphinx file targets for changed docs/source paths.

    Args:
        repo_root: Repository root.
        paths: Repository-relative changed paths.

    Returns:
        A documentation build plan. Targets are absolute paths under ``docs/``.
    """
    docs_root = repo_root / "docs"
    docs_api = docs_root / "api"
    targets: list[Path] = []
    full_build_required = False
    api_scaffold_required = False
    source_modules: list[tuple[str, bool]] = []
    cli_reference_required = False
    download_matrix_required = False
    download_descriptor_rel = _download_descriptor_path(repo_root).relative_to(repo_root)
    download_page = docs_root / "download.md"

    for rel_path in paths:
        absolute = repo_root / rel_path
        if rel_path == Path("docs/conf.py"):
            full_build_required = True
        elif rel_path == download_descriptor_rel:
            # The download-channel descriptor is the source of the generated zone
            # in docs/download.md; a descriptor edit must re-inject that zone and
            # rebuild the page (mirroring how a CLI source edit regenerates the
            # CLI reference).
            download_matrix_required = True
        elif rel_path.parts[:1] == ("docs",) and rel_path.suffix in DOC_SUFFIXES and absolute.is_file():
            targets.append(absolute)
        elif _is_documentable_source(repo_root, rel_path):
            api_scaffold_required = True
            include_parents = rel_path.name == "__init__.py" or not (repo_root / rel_path).is_file()
            source_modules.append((_module_name_for_source(rel_path), include_parents))
        elif _is_cli_reference_source(rel_path):
            cli_reference_required = True

    if api_scaffold_required:
        for module_name, include_parents in source_modules:
            targets.extend(_api_stub_targets(module_name, docs_api, include_parents=include_parents))
    if cli_reference_required:
        targets.extend(
            target
            for target in (
                docs_root / "cli" / "index.rst",
                docs_root / "cli" / "app.rst",
                docs_root / "cli" / "config.rst",
                docs_root / "cli" / "automation.rst",
                docs_root / "cli" / "schemas.rst",
            )
            if target.is_file()
        )
    if download_matrix_required and download_page.is_file():
        targets.append(download_page)

    seen: set[Path] = set()
    unique_targets: list[Path] = []
    for target in targets:
        resolved = target.resolve()
        planned_api_stub = api_scaffold_required and target.parent == docs_api and target.suffix == ".rst"
        if resolved not in seen and (resolved.is_file() or planned_api_stub):
            seen.add(resolved)
            unique_targets.append(resolved)
    return DocBuildPlan(
        targets=unique_targets,
        full_build_required=full_build_required,
        api_scaffold_required=api_scaffold_required,
        cli_reference_required=cli_reference_required,
        download_matrix_required=download_matrix_required,
    )


def _single_page_source_set(docs_root: Path, targets: list[Path]) -> list[str]:
    """Return source files needed to resolve links for a canonical page build.

    A canonical single-page build writes only the requested output page, but it
    still needs the non-API documentation graph available so MyST links and
    toctrees resolve like the real handbook. The generated API tree is
    intentionally excluded because importing autodoc modules is the expensive
    and fragile part this mode avoids.

    Args:
        docs_root: Documentation source root.
        targets: Absolute source files requested for output.

    Returns:
        POSIX-style paths relative to ``docs_root`` for the allowed source set.
    """
    excluded_roots = {
        (docs_root / "api").resolve(),
        (docs_root / "_build").resolve(),
        (docs_root / "_inventories").resolve(),
    }
    sources: list[str] = []
    for source in scan_directory(docs_root, recursive=True):
        if source.suffix not in DOC_SUFFIXES:
            continue
        resolved = source.resolve()
        if any(resolved == root or root in resolved.parents for root in excluded_roots):
            continue
        sources.append(source.relative_to(docs_root).as_posix())
    for target in targets:
        relative = target.relative_to(docs_root).as_posix()
        if relative not in sources:
            sources.append(relative)
    return sources


def _is_generated_doc(docs_root: Path, target: Path) -> bool:
    """Return whether a documentation target belongs to a generated docs tree."""
    try:
        relative = target.relative_to(docs_root)
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] in {"api", "cli"}


def _copy_docs_source(docs_root: Path, target: Path) -> None:
    """Copy documentation sources without repository-local build artifacts."""
    shutil.copytree(docs_root, target, ignore=shutil.ignore_patterns("_build"))


def ensure_isolated_storage_root() -> None:
    """Point product storage at a build-scoped scratch root unless already pinned.

    The documentation build imports the application (autodoc, the deferred
    diagnostics-model rebuild, CLI-reference generation, and the search-index
    terminology projections), and importing the application resolves the
    product storage root. A documentation build must never depend on the
    workstation's product state — in particular, the former-product custody
    refusal must not red a docs build on a machine that carries retired
    ``aeat`` state. Callers that deliberately pin a storage root keep it.
    """
    scratch = Path(tempfile.gettempdir()) / "cadrumo-docs-build-storage"
    os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(scratch))
    Path(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
    ensure_private_diagnostic_log()


def ensure_private_diagnostic_log() -> None:
    """Re-point diagnostic file logging at a per-PROCESS scratch directory.

    The storage-root pin above lands too late to move the diagnostic log on its
    own: importing the application already resolved the rotating file handler
    against the workstation's real log directory, and
    :func:`~cadrumo.core.logging.configure_logging` is latched, so nothing
    rebinds it. The docs engine therefore writes into the operator's shared
    ``cadrumo.log`` — and that is not merely untidy, it is the source of a
    non-deterministic diagnostic block in captured CLI output.

    ``RotatingFileHandler`` rolls the log over by RENAMING it. On Windows a
    rename fails with ``PermissionError`` (WinError 32) while any other process
    holds the file open, and every concurrent ``aeat`` command, pytest worker,
    and docs build on the box holds exactly that one shared file. The stdlib
    reports the failed emit by printing its own ``--- Logging error ---`` block
    — traceback, walked call stack, and ``repr`` of the record arguments — to
    whatever ``sys.stderr`` is at that instant. Inside a sequence frame that is
    Click's per-invocation capture buffer, so the block is recorded as CLI
    output. It carries the runner's own stack frame (``check_sequences`` versus
    ``refresh_sequences``) and object memory addresses, so no golden written by
    one verb can ever match the other's run.

    A directory keyed by PID removes the contention rather than masking its
    symptom: nothing outside this process writes the file, so the rollover
    rename always succeeds and there is no block to normalise.
    """
    from cadrumo.core.config import reset_settings_cache
    from cadrumo.core.logging import allow_logging_reconfiguration, configure_logging

    private_log_dir = Path(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"]) / "logs" / f"pid-{os.getpid()}"
    if os.environ.get("CADRUMO_LOG_DIR") == str(private_log_dir):
        return
    private_log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CADRUMO_LOG_DIR"] = str(private_log_dir)
    # The settings snapshot the latched configuration was derived from is
    # cached; without dropping it the reconfigure below re-reads the OLD log
    # directory and rebinds to the very file this function exists to leave.
    reset_settings_cache()
    allow_logging_reconfiguration()
    configure_logging()


#: Builder-owned pages with no corresponding source document.
_ORPHAN_SPECIAL_PAGES = {"genindex.html", "search.html", "404.html", "py-modindex.html"}

#: Asset and infrastructure directories that carry no docname-addressed pages.
_ORPHAN_SKIP_DIRS = {"_static", "_sources", "_images", "_downloads", "_sphinx_design_static", "pagefind"}

#: Per-language site roots living beside the English root inside the same HTML
#: tree. Their pages are docname-addressed against the SAME ``docs/`` sources,
#: one directory level down, so the sweep below would resolve ``es/index.html``
#: to a ``docs/es/index.md`` that never existed and delete every page of every
#: localized root. Derived from :class:`OutputLanguage` rather than imported
#: from the module that names the deploy root set, because that module imports
#: this one.
_ORPHAN_SKIP_SITE_ROOTS = frozenset(member.value for member in OutputLanguage)


def remove_orphan_pages(docs_root: Path, html_root: Path, repo_root: Path) -> int:
    """Delete built pages whose source document no longer exists.

    Furo bakes the theme's variables and templates into every page at build
    time, so a page whose source was removed or renamed keeps rendering its
    build-era design indefinitely and leaks stale results into the search
    index (the docs-brand audit found 2208 such orphans rendering a retired
    theme). Every docname maps to a ``.md``/``.rst`` source under ``docs/`` —
    including the generated ``api/``, ``cli/``, and ``_generated/`` sources,
    which are written to disk before Sphinx reads the tree — and ``_modules``
    viewcode pages map back to ``src/`` modules.

    A per-language site root nested in the same tree is exempt: its pages carry
    the same docnames one directory down, so resolving them against ``docs/``
    finds nothing and an apex build would empty every localized root beside it.

    Returns:
        The number of orphaned pages removed.
    """
    if not html_root.exists():
        return 0
    removed = 0
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        rel = page.relative_to(html_root)
        if rel.as_posix() in _ORPHAN_SPECIAL_PAGES or rel.parts[0] in _ORPHAN_SKIP_DIRS:
            continue
        if rel.parts[0] in _ORPHAN_SKIP_SITE_ROOTS and len(rel.parts) > 1:
            continue
        docname = rel.with_suffix("")
        if rel.parts[0] == "_modules":
            if rel.as_posix() == "_modules/index.html":
                continue
            module_path = Path(*docname.parts[1:])
            candidates = [repo_root / "src" / Path(f"{module_path}.py")]
        else:
            candidates = [docs_root / Path(f"{docname}{suffix}") for suffix in (".md", ".rst")]
        if any(candidate.is_file() for candidate in candidates):
            continue
        page.unlink()
        removed += 1
    if removed:
        print(f"Removed {removed} orphaned page(s) whose source no longer exists.", flush=True)
    return removed


def remove_noncanonical_build_entries(docs_root: Path) -> None:
    """Remove stale noncanonical entries directly under ``docs/_build``."""
    build_root = docs_root / "_build"
    if not build_root.exists():
        return
    allowed = (build_root / "html").resolve()
    for entry in scan_directory(build_root):
        resolved = entry.resolve()
        if resolved == allowed:
            continue
        if build_root.resolve() not in resolved.parents:
            raise SystemExit(f"Refusing to remove docs build entry outside docs/_build: {entry}")
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _targets_for_docs_root(original_docs_root: Path, copied_docs_root: Path, targets: list[Path]) -> list[Path]:
    """Map repository documentation targets into a copied documentation root."""
    mapped: list[Path] = []
    for target in targets:
        try:
            relative = target.relative_to(original_docs_root)
        except ValueError:
            continue
        copied = copied_docs_root / relative
        if copied.is_file():
            mapped.append(copied)
    return mapped


def docs_build_jobs(env: Mapping[str, str]) -> str:
    """Resolve the Sphinx ``-j`` parallelism from the deployment override.

    Defaults to ``auto`` (one worker per core) so local and CI builds keep the
    full-parallel read. The deployment sets ``CADRUMO_DOCS_JOBS=1`` to pin a
    single-worker build when a serial run is wanted for reproducibility; the
    post-build sitemap and Pagefind passes run after Sphinx completes and are
    parallel-safe regardless. A set value must be ``auto`` or a positive
    integer worker count.

    Windows note: Sphinx parallel workers require ``os.fork``
    (``sphinx.util.parallel.parallel_available`` is ``False`` on win32), so on
    a Windows host every ``-j`` value degrades to a serial build. The knob
    only ever changes POSIX builds; tuning it locally on Windows measures
    nothing.

    Args:
        env: The build environment mapping to read the override from.

    Returns:
        The ``-j`` value string to hand to ``sphinx-build``.

    Raises:
        SystemExit: If the override is set to a non-positive or non-integer
            value, so a bad deployment knob fails loudly rather than silently
            degrading parallelism.
    """
    raw = env.get("CADRUMO_DOCS_JOBS")
    if raw is None or raw == "auto":
        return "auto"
    try:
        jobs = int(raw)
    except ValueError:
        raise SystemExit(
            f"CADRUMO_DOCS_JOBS must be 'auto' or a positive integer worker count; got {raw!r}.",
        ) from None
    if jobs < 1:
        raise SystemExit(f"CADRUMO_DOCS_JOBS must be a positive integer worker count; got {raw!r}.")
    return str(jobs)


#: The two search-index contracts the deployment may select. ``full`` runs the
#: custom-record injection (concept/casilla/legal/CLI records boosted by the sweep);
#: ``pages`` indexes only the rendered HTML pages, shipping a lighter index with
#: no injected navigation records.
_PAGEFIND_MODES = ("full", "pages")


def docs_build_language(env: Mapping[str, str]) -> OutputLanguage:
    """Resolve the language this docs root is being built in.

    ``CADRUMO_DOCS_LANGUAGE`` is the single language signal for a build: the
    ``--language`` flag sets it (see :func:`main`), and ``docs/conf.py`` reads
    the same key to set Sphinx's ``language``, which is what puts ``lang="es"``
    on every rendered page and therefore what Pagefind indexes those pages
    under. Reading it here keeps the injected records in the same index as the
    pages of the root that carries them.

    Args:
        env: The build environment mapping to read the language from.

    Returns:
        The build language; English when the key is absent (the default root).

    Raises:
        SystemExit: If the value is not a known output language, matching
            ``conf.py``'s own refusal so a mistyped root fails loudly on both
            surfaces rather than silently building English.
    """
    raw = env.get("CADRUMO_DOCS_LANGUAGE")
    if raw is None:
        return OutputLanguage.EN
    try:
        return OutputLanguage(raw)
    except ValueError:
        valid = ", ".join(sorted(member.value for member in OutputLanguage))
        raise SystemExit(f"CADRUMO_DOCS_LANGUAGE must be one of {valid}; got {raw!r}.") from None


def pagefind_index_mode(env: Mapping[str, str]) -> str:
    """Resolve the Pagefind indexing contract from the deployment override.

    Defaults to ``full`` so local docs keep the injected concept/casilla/legal/CLI
    records. The deployment may set ``CADRUMO_DOCS_PAGEFIND_MODE=pages`` to
    index only the rendered pages, skipping the custom-record injection seam.

    Args:
        env: The build environment mapping to read the override from.

    Returns:
        Either ``full`` or ``pages``.

    Raises:
        SystemExit: If the override names an unsupported mode, so the
            deployment cannot silently select an unknown search contract.
    """
    raw = env.get("CADRUMO_DOCS_PAGEFIND_MODE")
    if raw is None:
        return "full"
    if raw not in _PAGEFIND_MODES:
        raise SystemExit(
            f"CADRUMO_DOCS_PAGEFIND_MODE must be one of {', '.join(_PAGEFIND_MODES)}; got {raw!r}.",
        )
    return raw


def resolve_record_injector(
    repo_root: Path,
    env: Mapping[str, str],
    *,
    on_complete: Callable[[InjectionStats], None] | None = None,
    sample_per_kind: int | None = None,
) -> InjectCallback | None:
    """Resolve one environment's Pagefind contract into an injection callback.

    The single place a build environment decides whether the shipped index
    carries the injected concept/casilla/legal/CLI records: ``full`` returns the real
    record injector, ``pages`` returns ``None`` and the index carries the
    rendered pages alone. It also decides WHICH language index those records
    land in, and it resolves that from the same environment the pages are built
    from (:func:`docs_build_language`) rather than pinning English: a localized
    root's pages are indexed under their own language, and Pagefind's reader
    loads only the index matching the page it is on, so records pinned to
    English would leave every localized root shipping rendered prose alone.
    It is a named function rather than a branch inside
    :func:`compile_search_index` so the deployment-parity gate can observe the
    real decision for the real deploy environment instead of re-deriving the
    mapping — a re-derived copy would agree with itself while the build shipped
    something else, which is precisely how a ``pages`` deploy value discarded
    every injected record from the published site unnoticed.

    Args:
        repo_root: Repository root (for the committed relevance file).
        env: The build environment whose contract is being resolved — both the
            index mode and the build language the records are injected under.
        on_complete: Optional sink for the injection stats.
        sample_per_kind: Optional bound on records per kind, forwarded to the
            injector. Production leaves it ``None`` (every record).

    Returns:
        The injection callback, or ``None`` under the ``pages`` contract.
    """
    from .pagefind_inject import build_record_injector

    if pagefind_index_mode(env) == "pages":
        return None
    return build_record_injector(
        repo_root,
        language=docs_build_language(env),
        on_complete=on_complete,
        sample_per_kind=sample_per_kind,
    )


#: Sitemaps.org urlset namespace for the deployment sitemap.
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

#: Top-level built pages that carry no canonical human content (Sphinx
#: builder-owned orphans); excluded from the deployment sitemap.
_SITEMAP_EXCLUDED_PAGES = frozenset({"search.html", "genindex.html", "py-modindex.html", "404.html"})

#: Top-level directories of generated / infrastructure surfaces that never
#: belong in the human sitemap (API autodoc, viewcode, assets, sources).
_SITEMAP_EXCLUDED_ROOTS = frozenset({"api", "_modules", "_static", "_sources"})


def _sitemap_page_url(base_url: str, rel_posix: str) -> str:
    """Map a built page's relative path to its canonical deployment URL.

    ``index.html`` pages canonicalise to their directory root (the site root
    for the top-level index), matching how the served site addresses them; any
    other page keeps its ``.html`` path.
    """
    if rel_posix == "index.html":
        suffix = ""
    elif rel_posix.endswith("/index.html"):
        suffix = rel_posix[: -len("index.html")]
    else:
        suffix = rel_posix
    return f"{base_url}/{suffix}"


def _sitemap_urls(html_root: Path, base_url: str) -> list[str]:
    """Return the deterministic canonical human-page URL set for the sitemap."""
    urls: set[str] = set()
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        rel = page.relative_to(html_root)
        parts = rel.parts
        if parts[0] in _SITEMAP_EXCLUDED_ROOTS:
            continue
        if len(parts) == 1 and rel.name in _SITEMAP_EXCLUDED_PAGES:
            continue
        urls.add(_sitemap_page_url(base_url, rel.as_posix()))
    return sorted(urls)


def write_deployment_sitemap(html_root: Path, base_url: str) -> Path:
    """Write a deterministic, canonical-human-page ``sitemap.xml`` for deployment.

    Walks the built HTML tree, filters to canonical human pages (excluding the
    generated ``api``/``_modules`` trees, the ``_static``/``_sources`` asset
    roots, and the builder-owned ``search``/``genindex``/``py-modindex``/``404``
    orphans), canonicalises ``index.html`` pages to their directory roots,
    sorts the URLs lexicographically, and emits the sitemaps.org urlset with no
    ``lastmod`` stamps. Stdlib-only and side-effect-deterministic so the deploy
    validator's exact canonical-root and canonical-prefix checks hold.

    Args:
        html_root: The built Sphinx HTML output directory.
        base_url: The canonical docs base URL (trailing slash tolerated).

    Returns:
        The path to the written ``sitemap.xml``.
    """
    base = base_url.rstrip("/")
    ET.register_namespace("", _SITEMAP_NS)
    urlset = ET.Element(f"{{{_SITEMAP_NS}}}urlset")
    for url in _sitemap_urls(html_root, base):
        entry = ET.SubElement(urlset, f"{{{_SITEMAP_NS}}}url")
        ET.SubElement(entry, f"{{{_SITEMAP_NS}}}loc").text = url
    tree = ET.ElementTree(urlset)
    ET.indent(tree)
    sitemap_path = html_root / "sitemap.xml"
    tree.write(sitemap_path, encoding=_UTF_8, xml_declaration=True)
    return sitemap_path


def build_docs(
    repo_root: Path,
    plan: DocBuildPlan,
    *,
    strict: bool,
    single_page: bool = False,
    scope: str = "full",
    output_root: Path | None = None,
) -> None:
    """Run Sphinx against the selected targets.

    Full builds write the actual documentation output under ``docs/_build/html``.
    Targeted changed-page checks copy ``docs/`` to an OS temporary source tree
    and write temporary output there, so generated API/CLI sources and preview
    artifacts never pollute the repository. Single-page builds are an explicit
    exception: they write the requested page into the canonical HTML output
    directory while excluding generated API/CLI/autodoc surfaces.

    ``scope`` selects the documentation surface (``full`` | ``user``). Under
    ``user`` scope the API autodoc tree is excluded and the app is never imported
    for rendering (see ``CADRUMO_DOCS_SCOPE`` in ``docs/conf.py``), so the
    apidocs scaffold is skipped — a user-scope build never regenerates API stubs.

    ``output_root`` redirects a full build's HTML output (and its per-build
    Pagefind index, orphan sweep, and sitemap) to a chosen directory instead of
    the canonical ``docs/_build/html``. The deploy publisher uses it to build each
    localized site into a per-language subdirectory (``docs/_build/html/<lang>``)
    without disturbing the English root. It applies only to a full build; the
    canonical-``_build`` cleanup is skipped when redirected so a language subdir
    build never clears the English root beside it.
    """
    docs_root = repo_root / "docs"
    targets = plan.targets
    canonical_html_root = docs_root / "_build" / "html"
    html_output_root = output_root if output_root is not None else canonical_html_root
    ensure_isolated_storage_root()
    command = [sys.executable, "-m", "sphinx", "-b", "html", "-j", docs_build_jobs(os.environ)]
    env = {**os.environ, "CADRUMO_DOCS_PROJECT_ROOT": str(repo_root), "CADRUMO_DOCS_SCOPE": scope}
    if strict:
        command.extend(["-n", "-W"])
        env["CADRUMO_DOCS_OFFLINE"] = "1"
        if (docs_root / "_build" / "html" / "objects.inv").is_file():
            env["CADRUMO_DOCS_SELF_INVENTORY"] = "1"
    if not plan.full_build_required:
        env["CADRUMO_DOCS_OFFLINE"] = "1"
        if single_page:
            relative_sources = _single_page_source_set(docs_root, targets)
            master_source = "index.md"
        else:
            relative_sources = [target.relative_to(docs_root).as_posix() for target in targets]
            master_source = relative_sources[0]
        env["CADRUMO_DOCS_ONLY"] = os.pathsep.join(relative_sources)
        env["CADRUMO_DOCS_MASTER_DOC"] = Path(master_source).with_suffix("").as_posix()
        if single_page:
            env["CADRUMO_DOCS_SINGLE_PAGE"] = "1"

    if plan.full_build_required:
        if output_root is None:
            remove_noncanonical_build_entries(docs_root)
        out_dir = html_output_root
        out_dir.mkdir(parents=True, exist_ok=True)
        command.extend(
            [
                str(docs_root),
                str(out_dir),
            ],
        )
        result = subprocess.run(command, cwd=repo_root, env=env, check=False)
    elif single_page:
        remove_noncanonical_build_entries(docs_root)
        with tempfile.TemporaryDirectory(prefix="cadrumo-docs-doctrees-") as tmp:
            out_dir = docs_root / "_build" / "html"
            command.extend(
                [
                    "-d",
                    str(Path(tmp) / "doctrees"),
                    str(docs_root),
                    str(out_dir),
                    *(target.relative_to(repo_root).as_posix() for target in targets),
                ],
            )
            result = subprocess.run(command, cwd=repo_root, env=env, check=False)
    else:
        with tempfile.TemporaryDirectory(prefix="cadrumo-docs-changed-") as tmp:
            temp_root = Path(tmp)
            temp_docs_root = temp_root / "docs-source"
            _copy_docs_source(docs_root, temp_docs_root)
            if plan.api_scaffold_required and scope != "user":
                ApiStubManager(
                    src_cadrumo=repo_root.joinpath(*_SOURCE_PACKAGE_PARTS),
                    docs_api=temp_docs_root / "api",
                ).scaffold()
            if plan.cli_reference_required:
                generate_cli_reference(temp_docs_root)
            if plan.download_matrix_required:
                inject_download_matrix(temp_docs_root)
            temp_targets = _targets_for_docs_root(docs_root, temp_docs_root, targets)
            if not temp_targets:
                print("No existing documentation targets remained after temporary generation.", flush=True)
                return
            out_dir = temp_root / "html"
            specific_command = [*command, str(temp_docs_root), str(out_dir), *(str(target) for target in temp_targets)]
            result = subprocess.run(specific_command, cwd=repo_root, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    # The offline Ctrl-K search corpus is compiled only for a canonical full
    # build: the changed-page and single-page modes write previews (temp trees
    # or a lone page) that must not regenerate the whole search index.
    if plan.full_build_required:
        html_root = html_output_root
        remove_orphan_pages(docs_root, html_root, repo_root)
        base_url = os.environ.get("CADRUMO_DOCS_BASE_URL")
        if base_url:
            sitemap_path = write_deployment_sitemap(html_root, base_url)
            print(f"Wrote deployment sitemap: {sitemap_path}", flush=True)
        compile_search_index(html_root, repo_root)


def compile_search_index(
    html_root: Path,
    repo_root: Path,
    *,
    injector: InjectCallback | None = None,
) -> None:
    """Compile the bundled Ctrl-K search corpus over the freshly built HTML.

    Runs the post-build Pagefind index pass and injects the unified
    search records -- concept cards, casilla, legal, and CLI navigation surfaces --
    boosted by the committed build-time RAG sweep. The resulting
    per-language index is an uncommitted build artifact, regenerated on every
    full build exactly like the generated CLI/API surfaces. A missing vendored
    Pagefind wheel is reported and skipped rather than failing the
    otherwise-successful docs build (the documented Orama fallback applies only
    if the wheel is unvendorable for a platform).

    Args:
        html_root: The built Sphinx HTML output directory to index.
        repo_root: Repository root (for the committed relevance sweep file).
        injector: Optional pre-built injection callback. When omitted, the
            injector is chosen from :func:`pagefind_index_mode`: the ``full``
            contract builds the record injector (concepts + casillas + legal provisions + CLI),
            while the deployment ``pages`` contract injects no custom records
            and indexes only the rendered pages. Injectable so a test can drive
            a small real injector without paying the full materialisation cost.
    """
    ensure_isolated_storage_root()
    from .pagefind_index import PagefindUnavailableError, build_search_index

    captured: list[InjectionStats] = []
    if injector is not None:
        resolved_injector = injector
    else:
        resolved_injector = resolve_record_injector(
            repo_root,
            os.environ,
            on_complete=captured.append,
        )
    try:
        outcome = build_search_index(html_root, inject=resolved_injector)
    except PagefindUnavailableError as exc:
        print(f"Search index skipped (vendored Pagefind unavailable): {exc}", flush=True)
        return
    stats = captured[0] if captured else None
    written = stats.custom_records_written if stats is not None else 0
    boosts = stats.relevance_boosts_applied if stats is not None else 0
    print(
        f"Search index compiled: {outcome.page_count} pages + {written} term/casilla/legal/CLI records "
        f"({boosts} relevance-boosted) -> {outcome.html_root / outcome.output_subdir}",
        flush=True,
    )


def update_rag_index(repo_root: Path) -> None:
    """Refresh the resident vaultspec-rag service index after docs changes."""
    rag = _executable("vaultspec-rag")
    status = subprocess.run(
        [rag, "server", "service", "status"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0 or "stopped" in (status.stdout + status.stderr).lower():
        start = subprocess.run([rag, "server", "service", "start"], cwd=repo_root, check=False)
        if start.returncode != 0:
            raise SystemExit(start.returncode)
    indexed = subprocess.run([rag, "index", "--type", "all", "--port", "8766"], cwd=repo_root, check=False)
    if indexed.returncode != 0:
        raise SystemExit(indexed.returncode)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for changed-document builds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repository-relative paths to build instead of scanning git changes.",
    )
    parser.add_argument("--base", default="HEAD", help="Git revision used for committed branch changes.")
    parser.add_argument("--strict", action="store_true", help="Use nitpicky warnings-as-errors mode.")
    parser.add_argument(
        "--rag-index",
        action="store_true",
        help="Refresh the service-backed RAG index after a clean build.",
    )
    parser.add_argument(
        "--single-page",
        metavar="PATH",
        help=("Build one documentation source into docs/_build/html without rebuilding generated API/autodoc pages."),
    )
    parser.add_argument(
        "--scope",
        choices=("full", "user"),
        default=None,
        help=(
            "Documentation surface to build. 'full' (default, CI + deploy) includes the API autodoc tree; "
            "'user' builds only the operator-facing surface, excluding docs/api and never importing the app "
            "for rendering (minutes instead of an hour). Overrides CADRUMO_DOCS_SCOPE; bare '--scope user' "
            "with no paths runs a full user build."
        ),
    )
    parser.add_argument(
        "--language",
        default=None,
        help=(
            "Build the localized documentation in one language (es/en/ca/hu). Sets CADRUMO_DOCS_LANGUAGE, "
            "which docs/conf.py validates against the OutputLanguage set. A localized build is always the "
            "user scope (the API autodoc tree stays English), so --language forces --scope user."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Redirect a full build's HTML output (and its Pagefind index and sitemap) to this directory "
            "instead of the canonical HTML output root. Used by the deploy publisher to build each localized "
            "site into a per-language subdirectory. Full builds only; not valid with --single-page or explicit paths."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    output_root = Path(args.out_dir) if args.out_dir else None
    if output_root is not None and (args.single_page or args.paths):
        raise SystemExit("--out-dir applies to a whole-scope build; it cannot combine with --single-page or paths.")
    if args.language is not None:
        # A localized build is a user-scope build: the API autodoc tree is
        # English-only, so only the operator surface is translated. conf.py reads
        # CADRUMO_DOCS_LANGUAGE and validates it against the OutputLanguage set,
        # so an unknown tag fails the build loudly rather than being re-listed here.
        os.environ["CADRUMO_DOCS_LANGUAGE"] = args.language
        if args.scope is None:
            args.scope = "user"
        elif args.scope != "user":
            raise SystemExit(f"--language builds are user-scope only; got --scope {args.scope!r}")
    # Precedence: explicit --scope flag, then the CADRUMO_DOCS_SCOPE env, then full.
    scope = args.scope or os.environ.get("CADRUMO_DOCS_SCOPE") or "full"
    if scope not in {"full", "user"}:
        raise SystemExit(f"scope must be 'full' or 'user'; got {scope!r}")
    if args.single_page and args.paths:
        raise SystemExit("--single-page cannot be combined with positional paths")
    if scope == "user" and not args.single_page and not args.paths:
        # `--scope user` with no target is the ergonomic "build all user docs"
        # command: force a full build (docs/conf.py is the full-build trigger),
        # scoped to the user surface by CADRUMO_DOCS_SCOPE.
        paths = [Path("docs") / "conf.py"]
    else:
        paths = (
            [Path(args.single_page)]
            if args.single_page
            else ([Path(path) for path in args.paths] if args.paths else changed_paths(repo_root, args.base))
        )
    if args.single_page and _is_generated_doc(
        repo_root / "docs",
        (repo_root / args.single_page).resolve(),
    ):
        raise SystemExit(
            "--single-page does not support generated API/CLI pages; use the explicit generator or full docs build.",
        )
    plan = planned_doc_targets(repo_root, paths)
    if args.single_page and (plan.full_build_required or len(plan.targets) != 1):
        raise SystemExit(f"--single-page requires one existing docs source file: {args.single_page}")
    if not plan.full_build_required and not plan.targets:
        print("No changed documentation targets detected.", flush=True)
        if args.rag_index:
            update_rag_index(repo_root)
        return 0

    if plan.full_build_required:
        print("Configuration changed; running an incremental full Sphinx build.", flush=True)
    elif args.single_page:
        print("Building canonical documentation page:", flush=True)
        print(f"  {plan.targets[0].relative_to(repo_root)}", flush=True)
    else:
        print("Building changed documentation targets:", flush=True)
        for target in plan.targets:
            print(f"  {target.relative_to(repo_root)}", flush=True)
    build_docs(
        repo_root,
        plan,
        strict=args.strict,
        single_page=bool(args.single_page),
        scope=scope,
        output_root=output_root,
    )
    if args.rag_index:
        update_rag_index(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

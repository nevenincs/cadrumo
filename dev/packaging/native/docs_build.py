"""Build each declared user-documentation root with the owning documentation driver."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.storage_environment import STORAGE_ROOT
from dev._paths import REPO_ROOT
from dev.docs.build import DOCS_FLAVOR_ENV
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV
from dev.docs.serve_languages import language_build_command

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from .action_cache import action_lock, completed, current, fingerprint
from .build_paths import build_paths
from .docs_stage import DocsPackagingError, declared_languages, language_roots, package_prefix
from .identity import identity
from .layout import distribution_target, load_layout

# The final exception line of a failed owner build, such as the sequence gate's stale-authority refusal.
_RAISED = re.compile(r"^\s*((?:\w+\.)*\w*(?:Error|Exception): .+)$")


#: The index contract the packaged site is built under: the full record corpus,
#: injected once into the ONE index this module writes after every root is
#: built. Named here, in one place, because the root builds are pinned to the
#: opposite contract -- they must index nothing -- and the two values only make
#: sense read together.
PACKAGE_INDEX_ENVIRONMENT: dict[str, str] = {"CADRUMO_DOCS_PAGEFIND_MODE": "full"}


def _owner_environment(
    build_root: Path, storage: Path, *, language: str, check_sequences: bool, jobs: int
) -> dict[str, str]:
    """Pin every documentation selector so ambient developer settings cannot reshape a root."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_DOCS_")}
    environment.update(
        {
            DOCS_BUILD_ROOT_ENV: str(build_root),
            DOCS_FLAVOR_ENV: "desktop",
            "CADRUMO_DOCS_JOBS": str(jobs),
            # The packaged site has ONE search index, built over every root once
            # they are all built (:func:`_index_site`). A root that indexed
            # itself would write an index addressed to its own build directory,
            # which is not where the staged site puts its pages.
            "CADRUMO_DOCS_PAGEFIND_MODE": "none",
            # Where this root sits in the staged site: the apex language at the
            # top, the others under their own directory. A page resolves the one
            # index, and opens a result shared by every language, against this.
            "CADRUMO_DOCS_SITE_PREFIX": package_prefix(language),
            STORAGE_ROOT.variable: str(storage),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    if not check_sequences:
        environment[SEQUENCE_CHECK_SKIP_ENV] = "1"
    return environment


def owner_build(
    language: str, root: Path, storage: Path, *, build_root: Path, check_sequences: bool, jobs: int
) -> tuple[list[str], dict[str, str]]:
    """Return the owner command and pinned environment that build one language root."""
    command = language_build_command(language, root.parent)
    return command, _owner_environment(
        build_root, storage, language=language, check_sequences=check_sequences, jobs=jobs
    )


def require_host_product_metadata(expected_version: str) -> None:
    """Refuse a source-only builder before the runtime fixture asks for installed metadata."""
    try:
        observed = importlib.metadata.version(PRODUCT_IDENTITY.distribution)
    except importlib.metadata.PackageNotFoundError:
        raise DocsPackagingError(
            f"Documentation host lacks {PRODUCT_IDENTITY.distribution} distribution metadata; "
            f"install this checkout in {sys.executable} with uv pip install --python "
            f'"{sys.executable}" --no-deps --editable "{REPO_ROOT}"'
        ) from None
    if observed != expected_version:
        raise DocsPackagingError(
            f"Documentation host has {PRODUCT_IDENTITY.distribution} {observed}; "
            f"the selected checkout requires {expected_version}"
        )


def build_roots(build: Path, inputs: Path, *, target: str | None = None) -> None:
    """Build every declared root with the owning driver unless its enrolled inputs are unchanged."""
    layout = load_layout(target)
    require_host_product_metadata(identity(distribution_target(layout)).version)
    paths = build_paths(build)
    build_root = paths["user_docs_build"]
    with action_lock(build, "user-docs"):
        input_identity = fingerprint(inputs, selected_published_authority(REPO_ROOT))
        if current(build_root, input_identity):
            print("Reusing user documentation: inputs and output inventory unchanged", flush=True)
            return
        (build_root / "ready").unlink(missing_ok=True)
        languages = declared_languages(layout)
        _run_owner_builds(build_root, paths["user_docs_work"], languages)
        _index_site(build_root, languages)
        completed(build_root, input_identity)


def _run_owner_builds(build_root: Path, work: Path, languages: tuple[str, ...]) -> None:
    """Run one owner build per language; the sequence gate runs on exactly the first root."""
    roots = language_roots(build_root, languages)
    work.mkdir(parents=True, exist_ok=True)
    for root in roots.values():
        # The owner regenerates the index on every successful full build. Removing it
        # first means a failed or partial build can never pass staging with an old index.
        index = root / "pagefind"
        if index.exists():
            shutil.rmtree(index)

    def run(language: str) -> tuple[str, int, Path]:
        storage = work / language / "storage"
        if storage.exists():
            shutil.rmtree(storage)
        storage.mkdir(parents=True)
        command, environment = owner_build(
            language,
            roots[language],
            storage,
            build_root=build_root,
            check_sequences=language == languages[0],
            jobs=2 if language == languages[0] else max(1, (os.cpu_count() or 1) // max(1, len(languages) - 1)),
        )
        log = work / f"{language}.log"
        print(f"Building {language} user documentation; log: {log}", flush=True)
        result = run_command(command, cwd=REPO_ROOT, environment=environment, errors="replace")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        print(f"Documentation {language}: exit {result.returncode} in {result.duration_seconds:.0f} s", flush=True)
        return language, result.returncode, log

    # The strict runtime gate owns the host first. Cold native workers must not
    # compete with three Sphinx builds under the unchanged runtime deadlines.
    results = [run(languages[0])]
    if results[0][1] == 0 and len(languages) > 1:
        with ThreadPoolExecutor(max_workers=len(languages) - 1) as pool:
            results.extend(pool.map(run, languages[1:]))
    failed = [(language, code, log) for language, code, log in results if code]
    for language, code, log in failed:
        lines = log.read_text(encoding="utf-8").splitlines()
        print(f"\nDocumentation build failed for {language} (exit {code}); log: {log}", file=sys.stderr)
        print("\n".join(lines[-25:]), file=sys.stderr)
        causes = [match.group(1) for line in lines if (match := _RAISED.search(line))]
        print(f"cause ({language}): {causes[-1] if causes else 'see the log above'}", file=sys.stderr, flush=True)
    if failed:
        raise SystemExit(f"User documentation build failed: {', '.join(language for language, _, _ in failed)}")


def _index_site(build_root: Path, languages: tuple[str, ...]) -> None:
    """Build the site's ONE search index over every built root.

    Runs after every root has built, because the index spans all of them: each
    page is indexed under the address it has in the STAGED site -- the apex
    language at the top, the others under their own directory -- and carries its
    own language as the filter the reader's search narrows by, while a concept,
    casilla, legal or CLI record is injected once and declares every language.
    The index is written into the apex language's root, which is the directory
    the staging step lifts to the site's apex; every language's pages resolve
    the bundle there.

    Args:
        build_root: The documentation build root holding the language roots.
        languages: The declared languages, the apex language among them.
    """
    from dev.docs.build import ensure_isolated_storage_root, resolve_record_injector
    from dev.docs.pagefind_index import IndexedRoot, build_shared_search_index
    from dev.docs.pagefind_inject import InjectionStats

    roots = language_roots(build_root, languages)
    indexed = [
        IndexedRoot(html_root=roots[language], language=language, url_prefix=package_prefix(language))
        for language in languages
    ]
    # The apex language is the one the staged layout serves at the top, which is
    # to say the one with no prefix. Reading it off the prefix owner keeps one
    # authority for where a root sits: a second reading could name a different
    # root than the prefixes address.
    apex = [root for root in indexed if not root.url_prefix]
    if len(apex) != 1:
        raise DocsPackagingError(
            f"exactly one documentation language must be served at the site apex; {len(apex)} carry no prefix"
        )
    # The projections import the application to read the registry authority and
    # the live command tree, exactly as a root build does, so they get the same
    # scratch product storage rather than the workstation's own state.
    ensure_isolated_storage_root()
    stats: list[InjectionStats] = []
    print(f"Indexing the documentation site once over {', '.join(languages)}", flush=True)
    outcome = build_shared_search_index(
        indexed,
        apex[0].html_root,
        inject=resolve_record_injector(REPO_ROOT, PACKAGE_INDEX_ENVIRONMENT, on_complete=stats.append),
    )
    written = stats[0].custom_records_written if stats else 0
    print(
        f"Search index compiled: {outcome.page_count} pages of {len(languages)} languages "
        f"+ {written} shared term/casilla/legal/CLI records "
        f"-> {outcome.html_root / outcome.output_subdir}",
        flush=True,
    )


def main() -> None:
    """Build the roots for the CMake documentation target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--target")
    arguments = parser.parse_args()
    try:
        build_roots(arguments.build.resolve(strict=True), arguments.inputs, target=arguments.target)
    except DocsPackagingError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()

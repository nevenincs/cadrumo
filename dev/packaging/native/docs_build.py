"""Build each declared user-documentation root with the owning documentation driver."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.storage_environment import STORAGE_ROOT
from dev._paths import REPO_ROOT
from dev.cache_root import dev_cache_dir

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from .action_cache import action_lock, completed, current, fingerprint
from .build_paths import build_paths
from .docs_stage import APEX_LANGUAGE, DocsPackagingError, declared_languages, language_roots, package_prefix
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

#: The development cache holding the one built site every build configuration
#: of this checkout takes its documentation from.
SHARED_SITE_CACHE = "user-docs"


def compile_environment(storage: Path) -> dict[str, str]:
    """Pin the compile's product storage, and carry no documentation selector of our own.

    Every ``CADRUMO_DOCS_`` selector is dropped rather than set here: the one
    compile pins its own (:func:`dev.docs.compile_once.compile_language_roots`),
    so a second authority for the flavour, the search index or a root's place in
    the site is exactly what must not exist. What the packaging driver still
    owns is where the compile keeps product state, because the registry and the
    live command tree it reads must come from scratch storage rather than from
    the workstation's own.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_DOCS_")}
    environment.update({STORAGE_ROOT.variable: str(storage), "PYTHONIOENCODING": "utf-8"})
    return environment


def compile_command(html_root: Path, build_root: Path) -> list[str]:
    """Return the command that writes every declared language root from ONE compile.

    The compile's own flags carry what used to be an environment per root: the
    flavour the package ships, where the roots go and where the compile works.
    """
    return [
        sys.executable,
        "-m",
        "dev.docs.compile_once",
        "--html-root",
        str(html_root),
        "--build-root",
        str(build_root),
        "--flavor",
        "desktop",
    ]


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
        authority = selected_published_authority(REPO_ROOT)
        input_identity = fingerprint(inputs, authority)
        if current(build_root, input_identity):
            print("Reusing user documentation: inputs and output inventory unchanged", flush=True)
            return
        (build_root / "ready").unlink(missing_ok=True)
        languages = declared_languages(layout)

        def produce(destination: Path) -> None:
            _compile_roots(destination, paths["user_docs_work"], languages)
            _index_site(destination, languages)

        built = take_shared_site(
            build_root,
            dev_cache_dir(SHARED_SITE_CACHE),
            shared_site_identity(fingerprint(inputs, authority, outside=build), languages),
            produce,
        )
        if not built:
            print("Reusing the user documentation another build configuration built from the same inputs", flush=True)
        completed(build_root, input_identity)


def shared_site_identity(inputs_outside_the_build: str, languages: tuple[str, ...]) -> str:
    """Return what a built site depends on in every build configuration alike.

    The documentation reads the sources, the registry authority and the
    declared languages. It does not read the platform, the architecture or the
    directory a configuration builds in, so those are not part of what names
    it: two configurations of one checkout with the same inputs get one site.
    """
    return hashlib.sha256(f"{inputs_outside_the_build}\n{','.join(languages)}".encode()).hexdigest()


def take_shared_site(build_root: Path, shared: Path, identity: str, produce: Callable[[Path], None]) -> bool:
    """Fill *build_root* with the site of *identity*, producing it only if no configuration has.

    The site is produced into the build configuration that needs it first and
    then kept in *shared*; every other configuration with the same inputs
    copies it instead of compiling the documentation again. The cache holds one
    site: a different identity replaces it, because the only readers of the
    old one were configurations whose inputs have since changed.

    Args:
        build_root: The configuration's own documentation build directory.
        shared: The directory the checkout's configurations share.
        identity: What the wanted site depends on.
        produce: Builds the site into the directory it is given.

    Returns:
        Whether the site was produced here rather than copied.
    """
    shared.parent.mkdir(parents=True, exist_ok=True)
    with action_lock(shared.parent, shared.name):
        if current(shared, identity):
            _copy_site(shared, build_root)
            return False
        produce(build_root)
        _copy_site(build_root, shared)
        completed(shared, identity)
        return True


def _copy_site(source: Path, destination: Path) -> None:
    """Replace *destination* with the site in *source*, leaving completion to the caller.

    The completion marker binds a directory's inventory to the identity its own
    owner checks, so it is never carried from one directory to another.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=lambda directory, _names: {"ready"} if Path(directory) == source else set(),
    )


def _compile_roots(build_root: Path, work: Path, languages: tuple[str, ...]) -> None:
    """Write every declared language root from ONE compile of the documentation.

    One compile replaces one Sphinx build per language, so the staged site costs
    one read of the pages however many languages it ships. It also retires what
    four concurrent builds needed: no root is built first to keep the strict
    sequence gate off a loaded host, because there is one build for the gate to
    run in, and no read parallelism is split between roots.
    """
    roots = language_roots(build_root, languages)
    work.mkdir(parents=True, exist_ok=True)
    for root in roots.values():
        # The search index is written over every root once they exist
        # (:func:`_index_site`). Removing it first means a failed or partial
        # compile can never pass staging with an old index.
        index = root / "pagefind"
        if index.exists():
            shutil.rmtree(index)
    storage = work / "storage"
    if storage.exists():
        shutil.rmtree(storage)
    storage.mkdir(parents=True)
    # Each root is a directory under the one HTML root the build-path owner
    # resolves, which is where the compile writes them.
    html_root = roots[APEX_LANGUAGE].parent
    log = work / "compile.log"
    print(f"Compiling the user documentation in {', '.join(languages)} once; log: {log}", flush=True)
    result = run_command(
        compile_command(html_root, build_root),
        cwd=REPO_ROOT,
        environment=compile_environment(storage),
        errors="replace",
    )
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    print(f"Documentation compile: exit {result.returncode} in {result.duration_seconds:.0f} s", flush=True)
    if result.returncode:
        lines = log.read_text(encoding="utf-8").splitlines()
        print(f"\nThe one documentation compile failed (exit {result.returncode}); log: {log}", file=sys.stderr)
        print("\n".join(lines[-25:]), file=sys.stderr)
        causes = [match.group(1) for line in lines if (match := _RAISED.search(line))]
        print(f"cause: {causes[-1] if causes else 'see the log above'}", file=sys.stderr, flush=True)
        raise SystemExit(f"User documentation compile failed: exit {result.returncode}")
    absent = sorted(language for language, root in roots.items() if not root.is_dir())
    if absent:
        raise DocsPackagingError(
            f"The documentation compile wrote no root for {', '.join(absent)} under {html_root}; "
            f"the package declares {len(languages)} language(s) and the compile carries its own set"
        )


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

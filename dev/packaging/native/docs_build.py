"""Build each declared user-documentation root with the owning documentation driver."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
from .docs_stage import DocsPackagingError, declared_languages, language_roots
from .layout import load_layout

# The final exception line of a failed owner build, such as the sequence gate's stale-authority refusal.
_RAISED = re.compile(r"^\s*((?:\w+\.)*\w*(?:Error|Exception): .+)$")


def _owner_environment(build_root: Path, storage: Path, *, check_sequences: bool, jobs: int) -> dict[str, str]:
    """Pin every documentation selector so ambient developer settings cannot reshape a root."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_DOCS_")}
    environment.update(
        {
            DOCS_BUILD_ROOT_ENV: str(build_root),
            DOCS_FLAVOR_ENV: "desktop",
            "CADRUMO_DOCS_JOBS": str(jobs),
            "CADRUMO_DOCS_PAGEFIND_MODE": "full",
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
    return command, _owner_environment(build_root, storage, check_sequences=check_sequences, jobs=jobs)


def build_roots(build: Path, inputs: Path) -> None:
    """Build every declared root with the owning driver unless its enrolled inputs are unchanged."""
    paths = build_paths(build)
    build_root = paths["user_docs_build"]
    with action_lock(build, "user-docs"):
        identity = fingerprint(inputs, selected_published_authority(REPO_ROOT))
        if current(build_root, identity):
            print("Reusing user documentation: inputs and output inventory unchanged", flush=True)
            return
        (build_root / "ready").unlink(missing_ok=True)
        _run_owner_builds(build_root, paths["user_docs_work"], declared_languages(load_layout()))
        completed(build_root, identity)


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
    jobs = max(1, (os.cpu_count() or 1) // len(languages))

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
            jobs=jobs,
        )
        log = work / f"{language}.log"
        print(f"Building {language} user documentation; log: {log}", flush=True)
        result = run_command(command, cwd=REPO_ROOT, environment=environment, errors="replace")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        print(f"Documentation {language}: exit {result.returncode} in {result.duration_seconds:.0f} s", flush=True)
        return language, result.returncode, log

    with ThreadPoolExecutor(max_workers=len(languages)) as pool:
        results = list(pool.map(run, languages))
    failed = [(language, code, log) for language, code, log in results if code]
    for language, code, log in failed:
        lines = log.read_text(encoding="utf-8").splitlines()
        print(f"\nDocumentation build failed for {language} (exit {code}); log: {log}", file=sys.stderr)
        print("\n".join(lines[-25:]), file=sys.stderr)
        causes = [match.group(1) for line in lines if (match := _RAISED.search(line))]
        print(f"cause ({language}): {causes[-1] if causes else 'see the log above'}", file=sys.stderr, flush=True)
    if failed:
        raise SystemExit(f"User documentation build failed: {', '.join(language for language, _, _ in failed)}")


def main() -> None:
    """Build the roots for the CMake documentation target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        build_roots(arguments.build.resolve(strict=True), arguments.inputs)
    except DocsPackagingError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()

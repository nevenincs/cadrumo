"""The one documentation site a test run builds, read by every test that needs built pages.

The strict compile of every published language and the witness build it is
measured against (:mod:`dev.docs.compile_once`) are the lane's only real
``-b html`` builds of the user documentation. Every other test that reads
rendered pages -- the record-target sweep, the search-index and deployment
gates -- reads the roots this one pair wrote, rather than building its own or
reading whatever a developer last built under the checkout's ``build/docs``.

The pair is a run artifact (:func:`cadrumo.tests.run_artifact.run_artifact`)
keyed on the digest of the files the build reads: the first process to ask
builds it under the run's lock, and every other process waits for it, verifies
it and reads it in place. A red build is published too, with its streams, so a
warning reds the gate that owns it and every reader reports the same failed
build instead of building it again.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.tests.run_artifact import file_inputs_digest, run_artifact
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command

from ..compile_once import WITNESS_LANGUAGE, witness_build
from ..i18n import SITE_ROOT_LANGUAGES
from ._sphinx_build_harness import gate_build_concurrency, gate_build_env, gate_build_jobs

__all__ = [
    "BASE_URL",
    "FLAVOR",
    "BuildOutcome",
    "BuiltSite",
    "built_documentation_site",
    "docs_site_input_paths",
]

_KIND: Final = "docs-site"

#: The flavour the site is compiled in. The web flavour with an address of its
#: own is the superset of the mark mechanisms: it is the only flavour that writes
#: page descriptions, canonical and OpenGraph URLs, the error page and the
#: sitemap, each of which carries strings that depend on the language.
FLAVOR: Final[str] = "web"

#: An address for the site above the language directories. What it has to be is
#: the same one both builds are given, because a page states where it is served
#: and two roots told different addresses differ wherever it does.
BASE_URL: Final[str] = "https://docs.example.test/docs"

#: Long enough for one worker to finish the pair while every other reader waits.
_WAIT_SECONDS: Final = 4 * 3600.0
_OUTCOME: Final = "outcome.json"

#: The trees the user-scope build reads, relative to the checkout, with the
#: generated residue under them that the build writes rather than reads. The
#: native packaging enrolment (``native/cmake/Docs.cmake``) declares the same
#: surface for the packaged site.
_INPUT_TREES: Final = {
    "docs": frozenset({"_build", "cli", "_generated", "api", "pot", "__pycache__"}),
    "dev/docs": frozenset({"tests", "__pycache__"}),
    "dev/registry": frozenset({"tests", "__pycache__"}),
    "src": frozenset({"tests", "__pycache__"}),
}
#: Files the build writes into the source tree it reads.
_GENERATED_FILES: Final = frozenset({"docs/_static/cli-tree.json", "docs/_static/download-latest.json"})
_INPUT_FILES: Final = (
    "pyproject.toml",
    "uv.lock",
    "dev/__init__.py",
    "dev/_paths.py",
    "dev/cache_root.py",
    "dev/first_party_source.py",
    "dev/temporary_output.py",
    "dev/packaging/command_execution.py",
)


@dataclass(frozen=True, slots=True)
class BuildOutcome:
    """How one of the two builds ended, with its complete streams on disk."""

    label: str
    returncode: int
    duration_seconds: float
    stdout: Path
    stderr: Path

    def failure(self) -> str | None:
        """Return the build's report when it failed, else None."""
        if self.returncode == 0:
            return None
        tail = self.stdout.read_text(encoding="utf-8")[-6000:] + self.stderr.read_text(encoding="utf-8")[-6000:]
        streams = f"complete streams at {self.stdout} and {self.stderr}"
        return f"the {self.label} exited {self.returncode}; {streams}:\n{tail}"


@dataclass(frozen=True, slots=True)
class BuiltSite:
    """The run's compile of every language and the witness build beside it, read in place.

    Attributes:
        root: The run artifact entry holding both builds.
        html_root: The directory each language's composed root is under.
        witness: The root the witness language's own build wrote.
        stored: The structure and each language's text the roots came from.
        compile: How the compile ended.
        witness_build: How the witness build ended.
    """

    root: Path
    html_root: Path
    witness: Path
    stored: Path
    compile: BuildOutcome
    witness_build: BuildOutcome

    def language_root(self, language: str) -> Path:
        """Return one language's composed root, refusing a build that wrote none."""
        if (failure := self.compile.failure()) is not None:
            raise AssertionError(f"the run's documentation compile wrote no readable site: {failure}")
        return self.html_root / language


def docs_site_input_paths(repo_root: Path = REPO_ROOT) -> Iterator[Path]:
    """Yield every file the user-scope documentation build reads from the checkout."""
    for tree, generated in _INPUT_TREES.items():
        top = repo_root / tree
        for path in sorted(top.rglob("*")):
            relative = path.relative_to(top).parts
            if not path.is_file() or path.suffix == ".pyc" or generated.intersection(relative[:-1]):
                continue
            if "/".join((tree, *relative)) in _GENERATED_FILES:
                continue
            yield path
    for name in _INPUT_FILES:
        yield repo_root / name


@cache
def built_documentation_site() -> BuiltSite:
    """Return this run's documentation site, building it once for its inputs."""
    digest = file_inputs_digest(_KIND, REPO_ROOT, docs_site_input_paths())[:32]
    artifact = run_artifact(
        _KIND,
        digest,
        publish=lambda staging: _publish(staging, digest),
        verify=lambda root: _read(root, digest) is not None,
        wait_seconds=_WAIT_SECONDS,
    )
    site = _read(artifact.root, digest)
    if site is None:
        raise AssertionError(f"the run's documentation site at {artifact.root} no longer verifies")
    return site


def _compile_command(html_root: Path, build_root: Path, stored: Path) -> list[str]:
    """Return the one compile of every language, as the gates run it."""
    return [
        *("-m", "dev.docs.compile_once"),
        *("--html-root", str(html_root)),
        *("--build-root", str(build_root)),
        *("--stored", str(stored)),
        *("--flavor", FLAVOR),
        *("--base-url", BASE_URL),
        "--strict",
        *("--jobs", gate_build_jobs()),
    ]


def _publish(staging: Path, digest: str) -> None:
    """Run the compile and its witness into ``staging`` and record how each ended."""
    html_root, build_root = staging / "html", staging / "build"
    # The stored form is the roots' own intermediate; the gate that reads what
    # the compile carried asks for it to be kept.
    stored = build_root / "compiled-text"
    witness = staging / "witness" / WITNESS_LANGUAGE
    witness_command, witness_environment = witness_build(
        WITNESS_LANGUAGE,
        witness,
        flavor=FLAVOR,
        base_url=BASE_URL,
        build_root=staging / "witness" / "build",
        # The witness reads as narrowly as the compile beside it: the gate's own
        # bounded width, not one worker per core.
        base=gate_build_env(staging / "witness-state", CADRUMO_DOCS_JOBS=gate_build_jobs()),
    )
    # A standalone run overlaps the builds. An xdist worker already owns one
    # slot, so it completes both commands sequentially within that slot.
    with ThreadPoolExecutor(max_workers=gate_build_concurrency()) as pool:
        building = pool.submit(
            run_command, witness_command, cwd=REPO_ROOT, environment=witness_environment, errors="replace"
        )
        compiling = pool.submit(
            run_command,
            [sys.executable, *_compile_command(html_root, build_root, stored)],
            cwd=REPO_ROOT,
            environment=gate_build_env(staging),
            errors="replace",
        )
        results = {"compile": compiling.result(), "witness": building.result()}
    # Only the roots, the stored form and the streams are read; the scratch
    # product state and the witness's own build root are not part of the site.
    for scratch in (staging / "cadrumo-docs-state", staging / "witness-state", staging / "witness" / "build"):
        if scratch.is_dir():
            shutil.rmtree(scratch)
    builds = {label: _record_streams(staging, label, result) for label, result in results.items()}
    record = {"input_digest": digest, "builds": builds}
    (staging / _OUTCOME).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _record_streams(staging: Path, label: str, result: CommandResult) -> dict[str, object]:
    stdout, stderr = f"{label}.stdout.log", f"{label}.stderr.log"
    for name, content in ((stdout, result.stdout), (stderr, result.stderr)):
        with (staging / name).open("w", encoding="utf-8", newline="") as stream:
            stream.write(content or "")
    return {
        "returncode": result.returncode,
        "duration_seconds": result.duration_seconds,
        "stdout": stdout,
        "stderr": stderr,
    }


def _read(root: Path, digest: str) -> BuiltSite | None:
    """Return the site recorded under ``root`` when it is the publication for ``digest``."""
    try:
        record = json.loads((root / _OUTCOME).read_text(encoding="utf-8"))
        builds = record["builds"]
        outcomes = {
            label: BuildOutcome(
                label=_LABELS[label],
                returncode=int(builds[label]["returncode"]),
                duration_seconds=float(builds[label]["duration_seconds"]),
                stdout=root / str(builds[label]["stdout"]),
                stderr=root / str(builds[label]["stderr"]),
            )
            for label in _LABELS
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if record.get("input_digest") != digest:
        return None
    site = BuiltSite(
        root=root,
        html_root=root / "html",
        witness=root / "witness" / WITNESS_LANGUAGE,
        stored=root / "build" / "compiled-text",
        compile=outcomes["compile"],
        witness_build=outcomes["witness"],
    )
    if site.compile.returncode == 0 and not all(
        (site.html_root / language / "index.html").is_file() for language in SITE_ROOT_LANGUAGES
    ):
        return None
    return site


_LABELS: Final = {
    "compile": "one nitpicky compile",
    "witness": f"nitpicky {WITNESS_LANGUAGE} build the compile is measured against",
}

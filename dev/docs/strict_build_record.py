"""The record a strict full-scope documentation build leaves, and the reader that checks it.

The nitpicky, warnings-as-errors build of the whole handbook (autodoc
included) is the most expensive documentation build there is. A verification
lane that already runs that build strictly does not need a second one to prove
the same contract: the build writes a record naming its outcome, its warning
count, the configuration it ran under and a content digest of every input it
reads, and a later reader accepts the record only when it is clean and its
inputs still have exactly that digest.

The declared inputs are taken from the filesystem: the documentation sources,
all first-party source (autodoc imports every package, and the build compiles
the bundled registry and reads its corpora), the development tooling the build
configuration imports, and the dependency lock. Output the build writes into
the tree it reads is not an input. The digest is the run-artifact input digest
(:func:`cadrumo.tests.run_artifact.file_inputs_digest`), and the interpreter is
recorded beside it.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, Field, ValidationError

from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.tests.run_artifact import file_inputs_digest

__all__ = [
    "STRICT_BUILD_RECORD_ENV",
    "StrictBuildConfiguration",
    "StrictBuildRecord",
    "strict_build_input_digest",
    "strict_build_input_paths",
    "strict_build_record_problems",
    "warning_log_path",
    "write_strict_build_record",
]

#: Names a strict full-scope build record a test may read instead of building again.
STRICT_BUILD_RECORD_ENV: Final[str] = "CADRUMO_DOCS_STRICT_BUILD_RECORD"

_KIND: Final[str] = "docs-strict-full-scope"
_SCHEMA: Final[str] = "cadrumo-docs-strict-build/1"

#: The trees the full-scope build reads, with the directory names under them
#: that hold output the build writes rather than reads.
_INPUT_TREES: Final[dict[str, frozenset[str]]] = {
    "docs": frozenset({"_build", "cli", "_generated", "pot", "__pycache__"}),
    "src": frozenset({"__pycache__"}),
    "dev": frozenset({"tests", "__pycache__"}),
}
#: Single files the build writes into the source tree it reads.
_GENERATED_FILES: Final[frozenset[str]] = frozenset({"docs/_static/cli-tree.json", "docs/_static/download-latest.json"})
#: The API stubs are written by the build at ``builder-inited``; the hand-written index beside them is read.
_GENERATED_STUBS: Final[tuple[str, str]] = ("docs/api", ".rst")
_INPUT_FILES: Final[tuple[str, ...]] = ("pyproject.toml", "uv.lock")

_WARNING_LINE: Final[re.Pattern[str]] = re.compile(r"\b(?:WARNING|ERROR|CRITICAL|SEVERE):")


class StrictBuildConfiguration(BaseModel):
    """The Sphinx configuration one recorded build ran under."""

    model_config = STRICT_FROZEN_CONFIG

    scope: str
    language: str
    flavor: str
    builder: str
    nitpicky: bool
    warnings_as_errors: bool
    offline: bool
    self_inventory: bool


#: The one configuration whose clean outcome proves the full-scope nitpicky contract.
#: An ``html`` build reads and resolves exactly what a ``dummy`` build does and writes
#: pages besides, so either builder's clean strict run proves it.
_PROVING_BUILDERS: Final[frozenset[str]] = frozenset({"html", "dummy"})
_PROVING: Final[dict[str, object]] = {
    "scope": "full",
    "language": "en",
    "flavor": "web",
    "nitpicky": True,
    "warnings_as_errors": True,
    "offline": True,
    "self_inventory": False,
}


class StrictBuildRecord(BaseModel):
    """What one strict documentation build left behind."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal["cadrumo-docs-strict-build/1"] = Field(alias="schema")
    input_digest: str = Field(min_length=64, max_length=64)
    python: str
    platform: str
    configuration: StrictBuildConfiguration
    returncode: int
    warnings: int = Field(ge=0)
    warning_log: str
    clean: bool


def strict_build_input_paths(repo_root: Path) -> Iterator[Path]:
    """Yield every file the full-scope documentation build reads from ``repo_root``."""
    for tree, generated in _INPUT_TREES.items():
        top = repo_root / tree
        if not top.is_dir():
            continue
        for path in sorted(top.rglob("*")):
            relative = path.relative_to(top).parts
            if not path.is_file() or path.suffix == ".pyc" or generated.intersection(relative[:-1]):
                continue
            name = "/".join((tree, *relative))
            if name in _GENERATED_FILES or _is_generated_stub(name):
                continue
            yield path
    for name in _INPUT_FILES:
        path = repo_root / name
        if path.is_file():
            yield path


def _is_generated_stub(name: str) -> bool:
    directory, _, filename = name.rpartition("/")
    stub_directory, stub_suffix = _GENERATED_STUBS
    return directory == stub_directory and filename.endswith(stub_suffix)


def strict_build_input_digest(repo_root: Path) -> str:
    """Return the content digest of every declared input of the full-scope build under ``repo_root``."""
    return file_inputs_digest(_KIND, repo_root, strict_build_input_paths(repo_root))


def warning_log_path(record: Path) -> Path:
    """Return where the build named by ``record`` writes its warnings."""
    return record.with_name(f"{record.name}.warnings.log")


def _interpreter() -> tuple[str, str]:
    return sys.version, platform.system()


def write_strict_build_record(
    record: Path,
    *,
    input_digest: str,
    configuration: StrictBuildConfiguration,
    returncode: int,
) -> StrictBuildRecord:
    """Write the record of a build that took ``input_digest`` before it started and exited ``returncode``.

    The warnings are counted from the build's warning log
    (:func:`warning_log_path`); a missing log counts as one warning, because
    then nothing shows the build was warning-free.

    Returns:
        The record written.
    """
    log = warning_log_path(record)
    try:
        warnings = sum(
            1 for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if _WARNING_LINE.search(line)
        )
    except FileNotFoundError:
        warnings = 1
    python, system = _interpreter()
    written = StrictBuildRecord.model_validate(
        {
            "schema": _SCHEMA,
            "input_digest": input_digest,
            "python": python,
            "platform": system,
            "configuration": configuration,
            "returncode": returncode,
            "warnings": warnings,
            "warning_log": str(log),
            "clean": returncode == 0 and warnings == 0,
        }
    )
    record.parent.mkdir(parents=True, exist_ok=True)
    staged = record.with_name(f"{record.name}.tmp")
    staged.write_text(written.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8")
    staged.replace(record)
    return written


def strict_build_record_problems(record: Path, *, repo_root: Path) -> tuple[str, ...]:
    """Return why ``record`` does not prove a clean strict full-scope build of ``repo_root`` as it is now.

    Empty only when the record is readable, its build ran under the proving
    configuration with this interpreter, it was clean, and the declared inputs
    under ``repo_root`` still have the digest the build took before it started.
    """
    try:
        recorded = StrictBuildRecord.model_validate(json.loads(record.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        return (f"the strict build record {record} is missing or unreadable: {exc}",)
    problems: list[str] = []
    configuration = recorded.configuration.model_dump()
    mismatched = {name: configuration[name] for name, wanted in _PROVING.items() if configuration[name] != wanted}
    if mismatched or recorded.configuration.builder not in _PROVING_BUILDERS:
        problems.append(
            f"the recorded build ran under {configuration}, not the full-scope nitpicky configuration "
            f"{_PROVING} with a builder in {sorted(_PROVING_BUILDERS)}"
        )
    python, system = _interpreter()
    if (recorded.python, recorded.platform) != (python, system):
        problems.append(
            f"the recorded build ran under Python {recorded.python!r} on {recorded.platform}, "
            f"not this interpreter ({python!r} on {system})"
        )
    if not recorded.clean:
        problems.append(
            f"the recorded build was not clean: exit {recorded.returncode}, {recorded.warnings} warning(s); "
            f"see {recorded.warning_log}"
        )
    current = strict_build_input_digest(repo_root)
    if current != recorded.input_digest:
        problems.append(
            f"the documentation inputs changed since the recorded build: digest {current[:16]} now, "
            f"{recorded.input_digest[:16]} when it started"
        )
    return tuple(problems)

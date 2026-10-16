"""Bind Cadrumo build-time state and scratch to one admitted build directory."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from dev._paths import REPO_ROOT

from .build_scratch_reclaim import require_build_path
from .command_execution import run_command

_DERIVED_CACHE_VARIABLES = (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_RECORD_DESIGN_CACHE_DIR",
    "CADRUMO_CORPUS_TEXT_CACHE_DIR",
    "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
    "CADRUMO_RUNTIME_WHEEL_CACHE_DIR",
)
_TEMPORARY_VARIABLES = ("CADRUMO_TEMP_DIR", "TEMP", "TMP", "TMPDIR")


def _path_variables(work: Path) -> dict[str, Path]:
    """Return application-owned output and cache controls below ``work``."""
    storage = work / "storage"
    cache = work / "cache"
    scratch = work / "scratch"
    temporary = work / "temporary"
    paths = {
        "CADRUMO_STORAGE_ROOT": storage,
        "CADRUMO_LOCAL_STORAGE_ROOT": storage,
        "CADRUMO_LOG_DIR": storage / "logs",
        "CADRUMO_DEV_CACHE_ROOT": cache,
        "CADRUMO_DEV_CACHE_DIR": cache,
        "CADRUMO_PYTHON_CACHE_DIR": work / "python-cache",
        "CADRUMO_TEST_LOG_ROOT": work / "test-logs",
        "CADRUMO_SCRATCH_BASE": scratch,
        "CADRUMO_DEV_SCRATCH_DIR": scratch,
        "CADRUMO_DOCS_BUILD_ROOT": work / "docs",
        "CADRUMO_DEV_ARTIFACTS_DIR": work / "artifacts",
        **{name: cache / name.lower() for name in _DERIVED_CACHE_VARIABLES},
        **{name: temporary for name in _TEMPORARY_VARIABLES},
    }
    return paths


def _admit_work_and_paths(work: Path, repo_root: Path) -> tuple[Path, dict[str, Path]]:
    """Admit the work root and every controlled directory before creating any of them."""
    root = repo_root.resolve(strict=True)
    selected = require_build_path(work, repo_root=root)
    if selected == root / "build":
        raise ValueError("build work must be below the repository build directory")
    paths = _path_variables(selected)
    for path in paths.values():
        require_build_path(path, repo_root=root)
    return selected, paths


@contextmanager
def build_storage(work: Path, *, repo_root: Path = REPO_ROOT) -> Generator[Path]:
    """Pin Cadrumo build outputs and temporary files beneath an admitted ``work`` directory.

    The context changes only Cadrumo-owned output controls and the standard
    temporary-directory variables. Machine-managed environments and caches,
    including ``UV_*``, ``XDG_*``, user homes and tool cache settings, retain
    their caller-provided values. The previous environment values and
    :attr:`tempfile.tempdir` are restored even if the build work raises.

    ``repo_root`` supports build steps that operate on a copied checkout. The
    command-line wrapper intentionally offers no such override and always uses
    the physical repository root.
    """
    selected, paths = _admit_work_and_paths(work, repo_root)
    for path in dict.fromkeys(paths.values()):
        path.mkdir(parents=True, exist_ok=True)

    names = tuple(paths)
    previous_environment = {name: os.environ.get(name) for name in names}
    previous_no_bytecode = os.environ.get("PYTHONDONTWRITEBYTECODE")
    previous_tempdir = tempfile.tempdir
    previous_dont_write_bytecode = sys.dont_write_bytecode
    os.environ.update({name: str(path) for name, path in paths.items()})
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    tempfile.tempdir = str(paths["TEMP"])
    sys.dont_write_bytecode = True
    try:
        yield selected
    finally:
        for name, value in previous_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if previous_no_bytecode is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = previous_no_bytecode
        tempfile.tempdir = previous_tempdir
        sys.dont_write_bytecode = previous_dont_write_bytecode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a command with Cadrumo build storage and temporary files under an admitted build directory.",
    )
    parser.add_argument("--work", type=Path, required=True, help="work directory below the repository's build/")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command argv after --")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command with build-local Cadrumo storage and return its exit status."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    command = list(arguments.command)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        parser.error("a command argv is required after --")
    try:
        work = require_build_path(arguments.work, repo_root=REPO_ROOT)
        if work == REPO_ROOT / "build":
            raise ValueError("build work must be below the repository build directory")
        with build_storage(work):
            result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
    except ValueError as error:
        parser.error(str(error))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_storage", "main"]

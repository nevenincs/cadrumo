"""Isolate Python build state beneath the owning checkout's temporary root."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from dev.cache_root import dev_cache_root
from dev.paths import REPO_ROOT
from dev.temporary_output import prepare_temp_root, resolve_temporary_output

from .build_scratch_reclaim import require_build_path
from .command_execution import run_command
from .runtime_wheel_acquisition import wheel_cache_dir

_DERIVED_CACHE_VARIABLES = (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_RECORD_DESIGN_CACHE_DIR",
    "CADRUMO_CORPUS_TEXT_CACHE_DIR",
    "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
)
_TEMPORARY_VARIABLES = ("TEMP", "TMP", "TMPDIR")
_RUNTIME_WHEEL_CACHE_VARIABLE = "CADRUMO_RUNTIME_WHEEL_CACHE_DIR"
#: The cache root an enclosing build admitted, exported so a nested build of a
#: copied checkout can accept the cache its parent already passed through.
_ADMITTED_WHEEL_CACHE_ROOT_VARIABLE = "CADRUMO_RUNTIME_WHEEL_CACHE_ADMITTED_ROOT"
#: Checkout members that hold machine-managed state rather than source.
_MACHINE_MANAGED_CHECKOUT_ROOTS = frozenset({".cache", "var"})


class WheelCacheLocationError(ValueError):
    """The runtime wheel cache a build would share resolves outside the machine-managed cache roots."""


def _require_outside_source(location: Path, checkouts: tuple[Path, ...], *, subject: str) -> None:
    for checkout in checkouts:
        if location.is_relative_to(checkout):
            relative = location.relative_to(checkout).parts
            if not relative or relative[0] not in _MACHINE_MANAGED_CHECKOUT_ROOTS:
                raise WheelCacheLocationError(f"{subject} resolves inside a source tree: {location}")


def _inherited_cache_root(checkouts: tuple[Path, ...]) -> Path | None:
    """Return the cache root an enclosing build admitted, after re-checking its containment.

    The exported root must already be its own canonical form, so a relative
    value, a ``..`` segment or a link anywhere along it is refused rather than
    followed; a filesystem anchor would admit every location and is refused too.
    """
    exported = os.environ.get(_ADMITTED_WHEEL_CACHE_ROOT_VARIABLE, "").strip()
    if not exported:
        return None
    root = Path(exported)
    canonical = root.resolve()
    if not root.is_absolute() or canonical != root:
        raise WheelCacheLocationError(f"inherited wheel cache root is not a canonical path: {root}")
    if canonical == Path(canonical.anchor):
        raise WheelCacheLocationError(f"inherited wheel cache root is a filesystem root: {root}")
    _require_outside_source(canonical, checkouts, subject="inherited wheel cache root")
    return canonical


def _admit_wheel_cache(repo_root: Path) -> tuple[Path, Path]:
    """Return the admitted wheel cache and the machine-managed root that admitted it."""
    cache = wheel_cache_dir().resolve()
    checkouts = tuple(dict.fromkeys((repo_root.resolve(strict=True), REPO_ROOT.resolve(strict=True))))
    _require_outside_source(cache, checkouts, subject="runtime wheel cache")
    inherited = _inherited_cache_root(checkouts)
    allowed = (
        dev_cache_root().resolve(),
        *(checkout / ".cache" for checkout in checkouts),
        *((inherited,) if inherited is not None else ()),
    )
    for root in allowed:
        if cache.is_relative_to(root):
            return cache, root
    raise WheelCacheLocationError(
        f"runtime wheel cache must stay below {' or '.join(str(root) for root in allowed)}: {cache}"
    )


def admitted_wheel_cache(repo_root: Path) -> Path:
    """Resolve the caller's runtime wheel cache for a build to share, refusing a source location.

    Unlike the other derived caches, which a build isolates, the wheel cache is
    passed through: every entry is named for its lock SHA-256 and re-hashed
    before it is served, so sharing it cannot change a build's bytes, and an
    isolated one made every cohort build fetch every wheel from the index. It
    must still be machine-managed state: below the development cache root, a
    checkout's ``.cache``, or the root an enclosing build admitted, and never
    inside a checkout's source tree. The enclosing build's root matters because
    it moves the development cache root before a nested build of a copied
    checkout resolves this again.

    Raises:
        WheelCacheLocationError: When the cache resolves anywhere else.
    """
    return _admit_wheel_cache(repo_root)[0]


def _path_variables(work: Path) -> dict[str, Path]:
    """Return application-owned output and cache controls below ``work``."""
    storage = work / "storage"
    cache = work / "cache"
    scratch = work / "scratch"
    temporary = work / "temporary"
    paths = {
        "CADRUMO_STORAGE_ROOT": storage,
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


def _admit_work(work: Path, repo_root: Path) -> Path:
    """Admit the artifact work root before creating it or temporary state."""
    root = repo_root.resolve(strict=True)
    selected = require_build_path(work, repo_root=root)
    if selected == root / "build":
        raise ValueError("build work must be below the repository build directory")
    return selected


@contextmanager
def build_environment(work: Path, *, repo_root: Path = REPO_ROOT) -> Generator[dict[str, str]]:
    """Yield independent build controls without changing the caller's environment."""
    selected = _admit_work(work, repo_root)
    # Resolved from the caller's environment, before the cache root moves below.
    wheel_cache, wheel_cache_root = _admit_wheel_cache(repo_root)
    temporary_base = prepare_temp_root()
    with tempfile.TemporaryDirectory(prefix=f"cadrumo-build-{selected.name}-", dir=temporary_base) as temporary:
        paths = _path_variables(Path(temporary))
        for path in dict.fromkeys(paths.values()):
            resolve_temporary_output(override=path)
        selected.mkdir(parents=True, exist_ok=True)
        for path in dict.fromkeys(paths.values()):
            path.mkdir(parents=True, exist_ok=True)
        yield {
            **{name: str(path) for name, path in paths.items()},
            _RUNTIME_WHEEL_CACHE_VARIABLE: str(wheel_cache),
            _ADMITTED_WHEEL_CACHE_ROOT_VARIABLE: str(wheel_cache_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }


@contextmanager
def build_storage(work: Path, *, repo_root: Path = REPO_ROOT) -> Generator[Path]:
    """Bind one process to isolated Python build state under the checkout's ``.tmp``.

    The context changes only Cadrumo-owned output controls and the standard
    temporary-directory variables. Machine-managed environments and caches,
    including ``UV_*``, ``XDG_*``, user homes and tool cache settings, retain
    their caller-provided values. The previous environment values and
    :attr:`tempfile.tempdir` are restored even if the build work raises.

    ``repo_root`` supports build steps that operate on a copied checkout. The
    command-line wrapper intentionally offers no such override and always uses
    the physical repository root.
    """
    with build_environment(work, repo_root=repo_root) as environment:
        previous_environment = {name: os.environ.get(name) for name in environment}
        previous_tempdir = tempfile.tempdir
        previous_dont_write_bytecode = sys.dont_write_bytecode
        os.environ.update(environment)
        tempfile.tempdir = environment["TEMP"]
        sys.dont_write_bytecode = True
        try:
            yield _admit_work(work, repo_root)
        finally:
            for name, value in previous_environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            tempfile.tempdir = previous_tempdir
            sys.dont_write_bytecode = previous_dont_write_bytecode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Python build with isolated Cadrumo state under the checkout's .tmp directory.",
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


__all__ = ["build_environment", "build_storage", "main"]

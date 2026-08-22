"""Fresh-process performance observations for the installed Cadrumo CLI.

This module is test infrastructure, but deliberately drives the real CLI.  A
profile consists of two independent interpreters: one resolves the requested
command node through Click's live ``get_command`` protocol, and the other runs
the complete invocation through the public ``main`` entry point.  Keeping the
probes independent prevents resolution from warming imports or model schemas
for invocation.

The child writes its observation to a dedicated JSON file outside the observed
storage root.  CLI stdout and stderr therefore remain byte-for-byte operator
output and cannot corrupt the machine-readable measurement envelope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

from ._inventory import SRC_CADRUMO
from .subprocess_cli import subprocess_cli_env

__all__ = [
    "CliPerformanceObservation",
    "CliPerformanceProfile",
    "profile_cli_path",
]

_CHILD_FLAG = "--cadrumo-cli-performance-child"
_STORAGE_MODULE_PREFIX = "cadrumo.adapters.persistence.storage"
_STORAGE_OPERATION_NAMES = frozenset(
    {
        "apply_batch",
        "delete",
        "exists",
        "get",
        "inventory",
        "list",
        "list_keys",
        "list_namespaces",
        "load",
        "open",
        "read",
        "recover",
        "repair",
        "save",
        "scan",
        "write",
    }
)
_IMPORT_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "registry": ("cadrumo.domain.registry", "cadrumo.adapters.registry"),
    "crypto": ("cryptography", "argon2", "cadrumo.core.crypto"),
    "custody": (f"{_STORAGE_MODULE_PREFIX}.custody",),
    "keyring": ("keyring", "cadrumo.adapters.persistence.storage.secret_store"),
    "storage": ("cadrumo.adapters.persistence", "sqlalchemy", "sqlite3"),
}
_ENV_PREFIXES = ("AEAT_", "PYTEST_", "CADRUMO_")


@dataclass(frozen=True, slots=True)
class CliPerformanceObservation:
    """One cold-process resolution or invocation observation."""

    phase: Literal["resolution", "invocation"]
    argv: tuple[str, ...]
    child_pid: int
    wall_seconds: float
    imported_modules: tuple[str, ...]
    import_families: Mapping[str, tuple[str, ...]]
    pydantic_model_constructions: int
    filesystem_created: tuple[str, ...]
    filesystem_modified: tuple[str, ...]
    filesystem_deleted: tuple[str, ...]
    filesystem_operations: Mapping[str, int]
    storage_operation_calls: Mapping[str, int]
    exit_code: int
    stdout: str
    stderr: str

    @classmethod
    def from_json(cls, payload: Mapping[str, Any], *, stdout: str, stderr: str) -> Self:
        """Validate and construct an observation from a child envelope."""
        phase = payload["phase"]
        if phase not in {"resolution", "invocation"}:
            raise ValueError(f"unknown profiler phase: {phase!r}")
        families = {
            str(name): tuple(str(module) for module in modules)
            for name, modules in dict(payload["import_families"]).items()
        }
        return cls(
            phase=phase,
            argv=tuple(str(token) for token in payload["argv"]),
            child_pid=int(payload["child_pid"]),
            wall_seconds=float(payload["wall_seconds"]),
            imported_modules=tuple(str(module) for module in payload["imported_modules"]),
            import_families=families,
            pydantic_model_constructions=int(payload["pydantic_model_constructions"]),
            filesystem_created=tuple(str(path) for path in payload["filesystem_created"]),
            filesystem_modified=tuple(str(path) for path in payload["filesystem_modified"]),
            filesystem_deleted=tuple(str(path) for path in payload["filesystem_deleted"]),
            filesystem_operations={
                str(name): int(count) for name, count in dict(payload["filesystem_operations"]).items()
            },
            storage_operation_calls={
                str(name): int(count) for name, count in dict(payload["storage_operation_calls"]).items()
            },
            exit_code=int(payload["exit_code"]),
            stdout=stdout,
            stderr=stderr,
        )


@dataclass(frozen=True, slots=True)
class CliPerformanceProfile:
    """Independent cold observations for one live CLI path."""

    resolution: CliPerformanceObservation
    invocation: CliPerformanceObservation


def profile_cli_path(
    argv: Sequence[str],
    *,
    storage_root: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
) -> CliPerformanceProfile:
    """Profile resolution and invocation of an arbitrary CLI argument vector.

    Args:
        argv: Tokens after the ``aeat`` executable. Options may follow the
            command path; the resolution probe stops at the first option or
            parameter token while the invocation probe consumes all tokens.
        storage_root: Empty or pre-populated root to observe. When omitted, a
            private temporary root is created for this profile.
        extra_env: Explicit additional child environment. Cadrumo, AEAT, and
            pytest variables are stripped from the inherited environment first.
        stdin_payload: Optional text delivered to the real invocation.
        timeout: Per-child deterministic wall timeout in seconds.

    Returns:
        The two independent, structured cold-process observations.
    """
    if timeout <= 0:
        raise ValueError("profiler timeout must be positive")
    tokens = tuple(str(token) for token in argv)
    if storage_root is None:
        with tempfile.TemporaryDirectory(prefix="cadrumo-cli-profile-") as directory:
            return _profile_with_root(
                tokens,
                Path(directory),
                extra_env=extra_env,
                stdin_payload=stdin_payload,
                timeout=timeout,
            )
    storage_root.mkdir(parents=True, exist_ok=True)
    return _profile_with_root(
        tokens,
        storage_root.resolve(),
        extra_env=extra_env,
        stdin_payload=stdin_payload,
        timeout=timeout,
    )


def _profile_with_root(
    argv: tuple[str, ...],
    storage_root: Path,
    *,
    extra_env: Mapping[str, str] | None,
    stdin_payload: str | None,
    timeout: float,
) -> CliPerformanceProfile:
    resolution = _run_child("resolution", argv, storage_root, extra_env=extra_env, timeout=timeout)
    invocation = _run_child(
        "invocation",
        argv,
        storage_root,
        extra_env=extra_env,
        stdin_payload=stdin_payload,
        timeout=timeout,
    )
    return CliPerformanceProfile(resolution=resolution, invocation=invocation)


def _run_child(
    phase: Literal["resolution", "invocation"],
    argv: tuple[str, ...],
    storage_root: Path,
    *,
    extra_env: Mapping[str, str] | None,
    timeout: float,
    stdin_payload: str | None = None,
) -> CliPerformanceObservation:
    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-envelope-") as directory:
        result_path = Path(directory) / "observation.json"
        payload = json.dumps(
            {
                "phase": phase,
                "argv": argv,
                "storage_root": str(storage_root),
                "result_path": str(result_path),
            }
        )
        env_extra = {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_SECRET_STORE_DIR": str(storage_root / "secret-store"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            **dict(extra_env or {}),
        }
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree profiler module.
            [sys.executable, "-m", "cadrumo.tests.cli_performance", _CHILD_FLAG, payload],
            cwd=SRC_CADRUMO.parent,
            env=subprocess_cli_env(strip_prefixes=_ENV_PREFIXES, extra=env_extra),
            input=stdin_payload,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if not result_path.is_file():
            raise RuntimeError(
                "CLI profiler child produced no observation envelope "
                f"(phase={phase}, exit={completed.returncode}, stderr={completed.stderr!r})"
            )
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        return CliPerformanceObservation.from_json(raw, stdout=completed.stdout, stderr=completed.stderr)


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Return path metadata and content fingerprints without following links."""
    if not root.exists():
        return {}
    entries: dict[str, tuple[int, int, str]] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            children = tuple(os.scandir(directory))
        except OSError:
            continue
        for entry in children:
            relative = Path(entry.path).relative_to(root).as_posix()
            try:
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            digest = ""
            if entry.is_file(follow_symlinks=False):
                try:
                    digest = hashlib.sha256(Path(entry.path).read_bytes()).hexdigest()
                except OSError:
                    digest = "<unreadable>"
            entries[relative] = (stat.st_size, stat.st_mtime_ns, digest)
            if entry.is_dir(follow_symlinks=False):
                pending.append(Path(entry.path))
    return entries


def _filesystem_delta(
    before: Mapping[str, tuple[int, int, str]],
    after: Mapping[str, tuple[int, int, str]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    before_paths = set(before)
    after_paths = set(after)
    created = tuple(sorted(after_paths - before_paths))
    deleted = tuple(sorted(before_paths - after_paths))
    modified = tuple(sorted(path for path in before_paths & after_paths if before[path] != after[path]))
    return created, modified, deleted


def _child_main(payload: Mapping[str, Any]) -> int:
    phase = str(payload["phase"])
    argv = tuple(str(token) for token in payload["argv"])
    storage_root = Path(str(payload["storage_root"])).resolve()
    result_path = Path(str(payload["result_path"]))
    before_files = _snapshot(storage_root)
    before_modules = set(sys.modules)
    filesystem_operations: Counter[str] = Counter()
    storage_operations: Counter[str] = Counter()
    pydantic_constructions = 0

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event not in {"open", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.scandir"} or not args:
            return
        raw_path = args[0]
        if not isinstance(raw_path, (str, os.PathLike)):
            return
        try:
            path = Path(raw_path).resolve(strict=False)
            path.relative_to(storage_root)
        except (OSError, TypeError, ValueError):
            return
        operation = event
        if event == "open" and len(args) > 1:
            mode = args[1]
            operation = "open.write" if isinstance(mode, str) and any(flag in mode for flag in "wax+") else "open.read"
        filesystem_operations[operation] += 1

    def profiler(frame: Any, event: str, _arg: object) -> None:
        nonlocal pydantic_constructions
        if event != "call":
            return
        module = str(frame.f_globals.get("__name__", ""))
        name = str(frame.f_code.co_name)
        if module == "pydantic.main" and name == "__init__":
            pydantic_constructions += 1
        if module.startswith(_STORAGE_MODULE_PREFIX) and name in _STORAGE_OPERATION_NAMES:
            storage_operations[f"{module}:{name}"] += 1

    sys.addaudithook(audit)
    sys.setprofile(profiler)
    exit_code = 0
    started = time.perf_counter()
    try:
        if phase == "resolution":
            _resolve_cli_path(argv)
        elif phase == "invocation":
            exit_code = _invoke_cli(argv)
        else:
            raise ValueError(f"unknown profiler phase: {phase!r}")
    except SystemExit as exc:
        exit_code = int(exc.code or 0) if isinstance(exc.code, int | None) else 1
    except BaseException:
        exit_code = 1
        raise
    finally:
        wall_seconds = time.perf_counter() - started
        sys.setprofile(None)
        imported_modules = tuple(sorted(name for name in set(sys.modules) - before_modules if name))
        after_files = _snapshot(storage_root)
        created, modified, deleted = _filesystem_delta(before_files, after_files)
        families = {
            family: tuple(name for name in imported_modules if name.startswith(prefixes))
            for family, prefixes in _IMPORT_FAMILY_PREFIXES.items()
        }
        observation = {
            "phase": phase,
            "argv": argv,
            "child_pid": os.getpid(),
            "wall_seconds": wall_seconds,
            "imported_modules": imported_modules,
            "import_families": families,
            "pydantic_model_constructions": pydantic_constructions,
            "filesystem_created": created,
            "filesystem_modified": modified,
            "filesystem_deleted": deleted,
            "filesystem_operations": dict(sorted(filesystem_operations.items())),
            "storage_operation_calls": dict(sorted(storage_operations.items())),
            "exit_code": exit_code,
        }
        result_path.write_text(json.dumps(observation, sort_keys=True), encoding="utf-8")
    return exit_code


def _command_tokens(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Return the option-free command prefix suitable for live resolution."""
    tokens: list[str] = []
    for token in argv:
        if token.startswith("-"):
            break
        tokens.append(token)
    return tuple(tokens)


def _resolve_cli_path(argv: tuple[str, ...]) -> None:
    from typer._click.core import Context
    from typer.main import get_command

    from cadrumo.entrypoints.cli import app

    command = get_command(app)
    for token in _command_tokens(argv):
        getter = getattr(command, "get_command", None)
        if not callable(getter):
            raise LookupError(f"CLI path traverses through leaf before {token!r}")
        context = Context(command, info_name=command.name)
        try:
            child = getter(context, token)
        finally:
            context.close()
        if child is None:
            raise LookupError(f"unknown CLI command token: {token!r}")
        command = child


def _invoke_cli(argv: tuple[str, ...]) -> int:
    from cadrumo.entrypoints.cli import main

    sys.argv = ["aeat", *argv]
    try:
        result = main()
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int | None) else 1
    return int(result) if isinstance(result, int) else 0


def _parse_child_payload() -> Mapping[str, Any] | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(_CHILD_FLAG, dest="payload")
    namespace, unknown = parser.parse_known_args()
    if namespace.payload is None:
        return None
    if unknown:
        raise ValueError(f"unexpected profiler child arguments: {unknown!r}")
    decoded = json.loads(namespace.payload)
    if not isinstance(decoded, dict):
        raise TypeError("profiler child payload must be a JSON object")
    return decoded


if __name__ == "__main__":
    child_payload = _parse_child_payload()
    if child_payload is None:
        raise SystemExit("cli_performance is a library; use profile_cli_path()")
    raise SystemExit(_child_main(child_payload))

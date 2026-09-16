"""Import every governed non-test module and report loadability as data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import (
    assert_all_target_sets_current,
    compile_inventory,
    load_all_target_sets,
)
from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command

from .import_checker import Authority, RootPackage, read_authority

_SCHEMA_VERSION: Final[int] = 1
_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.json"
_DEFAULT_TIMEOUT_SECONDS: Final[float] = 300.0
_WORKER_PATH: Final[Path] = Path(__file__).with_name("import_load_worker.py").resolve()
_WORKER_FAILURE_KEYS: Final[frozenset[str]] = frozenset({"error", "imported_name", "line", "message", "module", "path"})


def governed_load_targets(authority: Authority) -> tuple[str, ...]:
    """Return every governed non-test module in deterministic order."""
    targets: set[str] = set()
    for root in authority.roots:
        for path in root.path.rglob("*.py"):
            name = _module_name(path, root)
            if _is_test_module(name, path):
                continue
            targets.add(name)
    return tuple(sorted(targets))


def probe_loadability(authority: Authority, *, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, object]:
    """Load all governed targets and retain every failure without short-circuiting.

    The probe's own modules come from the tool tree, while the targets share
    top-level package names with it.  Targets are therefore imported in a
    separate interpreter whose first-party packages resolve only to the
    authority's source roots.
    """
    assert_all_target_sets_current(_TARGET_METADATA, repository=authority.repository)
    targets = load_all_target_sets(_TARGET_METADATA, repository=authority.repository)
    if targets != governed_load_targets(authority):
        raise RuntimeError("import load-target metadata does not cover the complete governed non-test census")
    target_digest = hashlib.sha256("\n".join(targets).encode(UTF_8)).hexdigest()
    failures = [
        _failure_record(raw, authority.repository)
        for raw in _load_in_authority_interpreter(authority, targets, target_digest, timeout=timeout)
    ]
    root_causes = _root_cause_summary(failures)
    return {
        "attempted": len(targets),
        "failed": len(failures),
        "failures": failures,
        "loaded": len(targets) - len(failures),
        "root_cause_count": len(root_causes),
        "root_causes": root_causes,
        "schema_version": _SCHEMA_VERSION,
        "scope": "all configured first-party non-test modules",
        "target_digest": target_digest,
        "targets": list(targets),
    }


def _load_in_authority_interpreter(
    authority: Authority, targets: tuple[str, ...], target_digest: str, *, timeout: float
) -> list[Mapping[str, object]]:
    """Import the declared targets in a child interpreter that sees only the authority tree."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(str(root.source_root) for root in authority.roots))
    environment["PYTHONIOENCODING"] = UTF_8
    with tempfile.TemporaryDirectory(prefix="cadrumo-import-load-worker-") as temporary:
        report_path = Path(temporary) / "report.json"
        completed = run_command(
            (
                sys.executable,
                "-P",
                str(_WORKER_PATH),
                "--repository",
                str(authority.repository),
                "--report",
                str(report_path),
            ),
            cwd=authority.repository,
            environment=environment,
            errors="replace",
            timeout_seconds=timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()[-1:] or ["no diagnostic output"]
            raise RuntimeError(f"isolated import worker exited with {completed.returncode}: {detail[0]}")
        try:
            decoded: object = json.loads(report_path.read_text(encoding=UTF_8))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"isolated import worker produced no usable report: {exc}") from exc
    return _validated_worker_failures(decoded, targets, target_digest)


def _validated_worker_failures(
    decoded: object, targets: tuple[str, ...], target_digest: str
) -> list[Mapping[str, object]]:
    """Refuse a worker report that does not account for exactly the validated targets."""
    if not isinstance(decoded, dict) or decoded.get("schema_version") != _SCHEMA_VERSION:
        raise RuntimeError("isolated import worker report has an unsupported schema")
    if decoded.get("attempted") != len(targets) or decoded.get("target_digest") != target_digest:
        raise RuntimeError("isolated import worker did not attempt exactly the validated target census")
    raw_failures = decoded.get("failures")
    if not isinstance(raw_failures, list):
        raise RuntimeError("isolated import worker failures must be a list")
    requested = frozenset(targets)
    seen: set[str] = set()
    failures: list[Mapping[str, object]] = []
    for raw in raw_failures:
        if not isinstance(raw, dict) or set(raw) != _WORKER_FAILURE_KEYS:
            raise RuntimeError("isolated import worker failure record has an unexpected shape")
        module = raw["module"]
        if not isinstance(module, str) or module not in requested or module in seen:
            raise RuntimeError(f"isolated import worker reported an unrequested or duplicate module: {module!r}")
        seen.add(module)
        failures.append(raw)
    return failures


def _failure_record(raw: Mapping[str, object], repository: Path) -> dict[str, object]:
    """Normalize one raw worker failure so cascades share a stable cause identity."""
    raw_path = raw.get("path")
    path: str | None = None
    if raw_path:
        candidate = Path(str(raw_path)).resolve()
        try:
            path = candidate.relative_to(repository.resolve()).as_posix()
        except ValueError:
            path = candidate.as_posix()
    message = str(raw.get("message", "")).replace(str(repository.resolve()), "<repo>").replace("\\", "/")
    identity = {
        "error": str(raw["error"]),
        "imported_name": raw.get("imported_name"),
        "line": raw.get("line"),
        "message": message,
        "path": path,
    }
    cause = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()
    return {"cause": cause, "module": str(raw["module"]), **identity}


def _root_cause_summary(failures: list[dict[str, object]]) -> list[dict[str, object]]:
    """Collapse module-level blast radius into reproducible root-cause groups."""
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for failure in failures:
        grouped[str(failure["cause"])].append(failure)
    result: list[dict[str, object]] = []
    for cause, group in grouped.items():
        first = group[0]
        result.append(
            {
                "affected_modules": len(group),
                "cause": cause,
                "error": first["error"],
                "imported_name": first.get("imported_name"),
                "line": first.get("line"),
                "message": first["message"],
                "module_sample": sorted(str(item["module"]) for item in group)[:10],
                "path": first.get("path"),
            }
        )
    return sorted(result, key=lambda item: (-_affected_module_count(item), str(item["cause"])))


def _affected_module_count(item: dict[str, object]) -> int:
    """Return the validated module count stored in one root-cause row."""
    count = item.get("affected_modules")
    if not isinstance(count, int):
        raise TypeError("root-cause affected_modules must be an integer")
    return count


def _module_name(path: Path, root: RootPackage) -> str:
    relative = path.relative_to(root.source_root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _is_test_module(name: str, path: Path) -> bool:
    parts = name.split(".")
    return (
        "tests" in parts
        or path.stem == "conftest"
        or path.stem.startswith(("test_", "_test_"))
        or path.stem.endswith("_test")
    )


def compile_load_target_inventory(authority: Authority) -> dict[str, object]:
    """Compile metadata for every configured first-party root from path-only facts."""
    target_sets: dict[str, object] = {}
    for root in authority.roots:
        source_root = root.path.relative_to(authority.repository).as_posix()
        document = compile_inventory(
            package=root.name,
            source_root=source_root,
            subpackages=(),
            target_set=root.name,
            repository=authority.repository,
        )
        raw_target_sets = document.get("target_sets")
        if not isinstance(raw_target_sets, dict):
            raise TypeError("compiled inventory target_sets must be a mapping")
        for target_set_name, target_set in raw_target_sets.items():
            if not isinstance(target_set_name, str):
                raise TypeError("compiled inventory target-set names must be strings")
            target_sets[target_set_name] = target_set
    return {"schema_version": 1, "target_sets": dict(sorted(target_sets.items()))}


def main(argv: list[str] | None = None) -> int:
    """Run the import-load probe or compile its checked target metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--compile-targets",
        action="store_true",
        help="write the checked finite load-target metadata and exit",
    )
    parser.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    read = read_authority(args.root, args.config)
    if read.authority is not None and not read.findings and args.compile_targets:
        output = args.root.resolve() / _TARGET_METADATA
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(compile_load_target_inventory(read.authority), indent=2, sort_keys=True) + "\n",
            encoding=UTF_8,
            newline="\n",
        )
        print(f"compiled import load targets: {output}")
        return 0
    if args.report is None:
        parser.error("--report is required unless --compile-targets is used")
    if read.authority is None or read.findings:
        payload = {
            "attempted": 0,
            "failed": 0,
            "failures": [],
            "loaded": 0,
            "operational_error": "; ".join(read.findings) or "authority is unavailable",
            "root_cause_count": 0,
            "root_causes": [],
            "schema_version": _SCHEMA_VERSION,
            "scope": "unavailable",
            "target_digest": None,
            "targets": [],
        }
        status = 7
    else:
        try:
            payload = probe_loadability(read.authority, timeout=args.timeout)
            status = 1 if payload["failed"] else 0
        except BaseException as exc:
            payload = {
                "attempted": 0,
                "failed": 0,
                "failures": [],
                "loaded": 0,
                "operational_error": f"{type(exc).__name__}: {exc}",
                "root_cause_count": 0,
                "root_causes": [],
                "schema_version": _SCHEMA_VERSION,
                "scope": "unavailable",
                "target_digest": None,
                "targets": [],
            }
            status = 7
    args.report.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding=UTF_8,
        newline="\n",
    )
    summary = {
        key: payload.get(key) for key in ("attempted", "failed", "loaded", "root_cause_count", "scope", "target_digest")
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["compile_load_target_inventory", "governed_load_targets", "main", "probe_loadability"]

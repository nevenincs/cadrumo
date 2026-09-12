"""Import every governed non-test module and report loadability as data."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import (
    assert_all_target_sets_current,
    compile_inventory,
    load_all_target_sets,
)
from dev._paths import REPO_ROOT, UTF_8

from .import_checker import Authority, RootPackage, read_authority

_SCHEMA_VERSION: Final[int] = 1
_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.json"


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


def probe_loadability(authority: Authority) -> dict[str, object]:
    """Load all governed targets and retain every failure without short-circuiting."""
    assert_all_target_sets_current(_TARGET_METADATA, repository=authority.repository)
    targets = load_all_target_sets(_TARGET_METADATA, repository=authority.repository)
    if targets != governed_load_targets(authority):
        raise RuntimeError("import load-target metadata does not cover the complete governed non-test census")
    failures: list[dict[str, object]] = []
    for target in targets:
        try:
            importlib.import_module(target)
        except BaseException as exc:  # import-time SystemExit is also a broken load surface
            failures.append(_failure_record(target, exc, authority.repository))
    target_digest = hashlib.sha256("\n".join(targets).encode(UTF_8)).hexdigest()
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


def _failure_record(module: str, exc: BaseException, repository: Path) -> dict[str, object]:
    """Normalize one module failure so cascades share a stable cause identity."""
    raw_path = getattr(exc, "filename", None) or getattr(exc, "path", None)
    path: str | None = None
    if raw_path:
        candidate = Path(str(raw_path)).resolve()
        try:
            path = candidate.relative_to(repository.resolve()).as_posix()
        except ValueError:
            path = candidate.as_posix()
    message = str(exc).replace(str(repository.resolve()), "<repo>").replace("\\", "/")
    identity = {
        "error": type(exc).__name__,
        "imported_name": getattr(exc, "name", None),
        "line": getattr(exc, "lineno", None),
        "message": message,
        "path": path,
    }
    cause = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()
    return {"cause": cause, "module": module, **identity}


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
    return sorted(result, key=lambda item: (-int(item["affected_modules"]), str(item["cause"])))


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
        )
        target_sets.update(document["target_sets"])
    return {"schema_version": 1, "target_sets": dict(sorted(target_sets.items()))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--compile-targets",
        action="store_true",
        help="write the checked finite load-target metadata and exit",
    )
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
            payload = probe_loadability(read.authority)
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

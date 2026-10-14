"""Import the declared load targets in an interpreter owned by the audited tree.

The loadability probe runs this file by path with ``python -P`` and a
``PYTHONPATH`` naming only the audited authority's source roots, so every
first-party package name here resolves to the audited tree, never to the tool
driving the probe.  The only first-party import is the finite target-set
loader, which the audited tree itself provides; it keeps the dynamic import
below a closed, checker-resolvable target set.  Raw failure facts are written
as data and normalized by the probe.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import load_all_target_sets

_SCHEMA_VERSION: Final[int] = 1
_ENCODING: Final[str] = "utf-8"
_CORE_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.cadrumo.json"
_HARNESS_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.cadrumo_harness.json"
_SERVICE_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.cadrumo_agent_service.json"
_CLIENT_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.cadrumo_client.json"
_RUNTIME_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.cadrumo_runtime.json"
_DEV_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.dev.json"
_DOCS_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.docs.json"


def load_declared_targets(repository: Path) -> dict[str, object]:
    """Import every declared target and return the raw loadability report."""
    # Each whole-root census is separately bounded below the checker's finite
    # target limit. Literal inventories keep the probe exhaustive, including
    # private modules, without making an open or silently truncated import set.
    core_targets = load_all_target_sets(_CORE_TARGET_METADATA, repository=repository)
    harness_targets = load_all_target_sets(_HARNESS_TARGET_METADATA, repository=repository)
    service_targets = load_all_target_sets(_SERVICE_TARGET_METADATA, repository=repository)
    client_targets = load_all_target_sets(_CLIENT_TARGET_METADATA, repository=repository)
    runtime_targets = load_all_target_sets(_RUNTIME_TARGET_METADATA, repository=repository)
    dev_targets = load_all_target_sets(_DEV_TARGET_METADATA, repository=repository)
    docs_targets = load_all_target_sets(_DOCS_TARGET_METADATA, repository=repository)
    failures: list[dict[str, object]] = []
    for core_target in core_targets:
        try:
            importlib.import_module(core_target)
        except BaseException as exc:  # import-time SystemExit is also a broken load surface
            failures.append(_failure(core_target, exc))
    for harness_target in harness_targets:
        try:
            importlib.import_module(harness_target)
        except BaseException as exc:
            failures.append(_failure(harness_target, exc))
    for dev_target in dev_targets:
        try:
            importlib.import_module(dev_target)
        except BaseException as exc:
            failures.append(_failure(dev_target, exc))
    for docs_target in docs_targets:
        try:
            importlib.import_module(docs_target)
        except BaseException as exc:
            failures.append(_failure(docs_target, exc))
    for service_target in service_targets:
        try:
            importlib.import_module(service_target)
        except BaseException as exc:
            failures.append(_failure(service_target, exc))
    for client_target in client_targets:
        try:
            importlib.import_module(client_target)
        except BaseException as exc:
            failures.append(_failure(client_target, exc))
    for runtime_target in runtime_targets:
        try:
            importlib.import_module(runtime_target)
        except BaseException as exc:
            failures.append(_failure(runtime_target, exc))
    targets = tuple(
        sorted(
            {
                *core_targets,
                *harness_targets,
                *service_targets,
                *client_targets,
                *runtime_targets,
                *dev_targets,
                *docs_targets,
            }
        )
    )
    return {
        "attempted": len(targets),
        "failures": failures,
        "schema_version": _SCHEMA_VERSION,
        "target_digest": hashlib.sha256("\n".join(targets).encode(_ENCODING)).hexdigest(),
    }


def _failure(target: str, exc: BaseException) -> dict[str, object]:
    """Keep every import-time failure in the same public probe report shape."""
    raw_path = getattr(exc, "filename", None) or getattr(exc, "path", None)
    line = getattr(exc, "lineno", None)
    name = getattr(exc, "name", None)
    return {
        "error": type(exc).__name__,
        "imported_name": name if isinstance(name, str) else None,
        "line": line if isinstance(line, int) else None,
        "message": str(exc),
        "module": target,
        "path": str(raw_path) if raw_path else None,
    }


def main(argv: list[str] | None = None) -> int:
    """Load the audited tree's declared targets and write the raw report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = load_declared_targets(args.repository.resolve())
    args.report.write_text(json.dumps(report) + "\n", encoding=_ENCODING, newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["load_declared_targets", "main"]

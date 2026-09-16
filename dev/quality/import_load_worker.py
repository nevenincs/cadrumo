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
_TARGET_METADATA: Final[str] = "dev/quality/metadata/import_load_targets.json"


def load_declared_targets(repository: Path) -> dict[str, object]:
    """Import every declared target and return the raw loadability report."""
    targets = load_all_target_sets(_TARGET_METADATA, repository=repository)
    failures: list[dict[str, object]] = []
    for target in targets:
        try:
            importlib.import_module(target)
        except BaseException as exc:  # import-time SystemExit is also a broken load surface
            raw_path = getattr(exc, "filename", None) or getattr(exc, "path", None)
            line = getattr(exc, "lineno", None)
            name = getattr(exc, "name", None)
            failures.append(
                {
                    "error": type(exc).__name__,
                    "imported_name": name if isinstance(name, str) else None,
                    "line": line if isinstance(line, int) else None,
                    "message": str(exc),
                    "module": target,
                    "path": str(raw_path) if raw_path else None,
                }
            )
    return {
        "attempted": len(targets),
        "failures": failures,
        "schema_version": _SCHEMA_VERSION,
        "target_digest": hashlib.sha256("\n".join(targets).encode(_ENCODING)).hexdigest(),
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

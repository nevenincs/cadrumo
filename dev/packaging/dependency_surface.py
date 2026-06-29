"""Validate declared production, optional, and dev dependency surfaces."""

from __future__ import annotations

import argparse
import json
from typing import TypedDict

from .smoke_core import (
    _assert_optional_extra_registry_matches_pyproject,
    _executable,
    _optional_extra_registry,
    _pyproject_surfaces,
    _repo_root,
    _validate_frozen_exports,
)


class DependencySurfaceSummary(TypedDict):
    """Machine-readable dependency-surface preflight summary."""

    ok: bool
    project_dependency_count: int
    optional_extra_count: int
    optional_dependency_count: int
    dev_dependency_count: int
    dev_only_dependency_count: int
    registry_extras: list[str]


def _summary() -> DependencySurfaceSummary:
    """Build a dependency-surface summary from pyproject and the runtime registry."""
    repo_root = _repo_root()
    surfaces = _pyproject_surfaces(repo_root)
    registry_extras, _symbols = _optional_extra_registry(repo_root)
    return {
        "ok": True,
        "project_dependency_count": len(surfaces.project_names),
        "optional_extra_count": len(surfaces.extras),
        "optional_dependency_count": len(surfaces.external_optional_names),
        "dev_dependency_count": len(surfaces.dev_names),
        "dev_only_dependency_count": len(surfaces.dev_only_names),
        "registry_extras": sorted(registry_extras),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the dependency-surface preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    uv = _executable("uv")
    _assert_optional_extra_registry_matches_pyproject(repo_root)
    _validate_frozen_exports(repo_root, uv)
    summary = _summary()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print("dependency surfaces verified")
    print(f"project dependencies\t{summary['project_dependency_count']}")
    print(f"optional extras\t{summary['optional_extra_count']}")
    print(f"optional dependencies\t{summary['optional_dependency_count']}")
    print(f"dev dependencies\t{summary['dev_dependency_count']}")
    print(f"dev-only dependencies\t{summary['dev_only_dependency_count']}")
    print(f"registry extras\t{', '.join(summary['registry_extras'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

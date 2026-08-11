"""Regenerate or verify the checked Modelo 303 annual Orden registry artefact."""

from __future__ import annotations

import argparse
from pathlib import Path

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    check_m303_annual_orden_manifest,
    load_registry_tree,
    render_m303_annual_orden_manifest,
)


def _manifest_path() -> Path:
    return bundled_path("registry", "aeat", "m303_orden_anual", "manifest.toml")


def main(argv: list[str] | None = None) -> int:
    """Write the generated artefact, or fail when its committed bytes drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="refuse a missing or stale generated artefact")
    args = parser.parse_args(argv)
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    manifest_path = _manifest_path()
    if args.check:
        check_m303_annual_orden_manifest(
            manifest_path=manifest_path,
            source_root=bundled_path(),
            sources=catalogues.sources,
        )
        return 0
    manifest_path.write_text(
        render_m303_annual_orden_manifest(source_root=bundled_path(), sources=catalogues.sources),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

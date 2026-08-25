"""Regenerate or verify the checked Modelo 303 annual Orden registry artefacts.

Two artefacts, one corpus, one extraction. The manifest carries the per-source
invariants a reviewer reads; the census artefact carries the full extraction the
runtime compiles from, so that no runtime process has to parse BOE HTML. They
are generated together because they are the same derivation of the same pinned
sources, and ``--check`` refuses either one drifting.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry.m303_orden_manifest import (
    check_m303_annual_orden_census_artefact,
    check_m303_annual_orden_manifest,
    render_m303_annual_orden_census_artefact,
    render_m303_annual_orden_manifest,
)
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.m303_orden_census_artefact import m303_orden_census_artefact_path


def _registry_root() -> Path:
    return bundled_path("registry", "aeat")


def _manifest_path() -> Path:
    return bundled_path("registry", "aeat", "m303_orden_anual", "manifest.toml")


def _census_artefact_path() -> Path:
    """Resolve the census artefact through the registry package's own accessor.

    Not spelled here. The registry package owns where its generated artefacts
    live; a second spelling in the generator is how a build writes a file the
    runtime never looks for, and that failure is silent — the runtime simply
    falls back to extracting and stays slow.
    """
    return m303_orden_census_artefact_path(_registry_root())


def main(argv: list[str] | None = None) -> int:
    """Write both generated artefacts, or fail when their committed bytes drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="refuse a missing or stale generated artefact")
    args = parser.parse_args(argv)
    _, catalogues = load_registry_tree(_registry_root())
    source_root = bundled_path()
    manifest_path = _manifest_path()
    artefact_path = _census_artefact_path()
    if args.check:
        check_m303_annual_orden_manifest(
            manifest_path=manifest_path,
            source_root=source_root,
            sources=catalogues.sources,
        )
        check_m303_annual_orden_census_artefact(
            artefact_path=artefact_path,
            source_root=source_root,
            sources=catalogues.sources,
        )
        return 0
    manifest_path.write_text(
        render_m303_annual_orden_manifest(source_root=source_root, sources=catalogues.sources),
        encoding="utf-8",
        newline="\n",
    )
    artefact_path.write_text(
        render_m303_annual_orden_census_artefact(source_root=source_root, sources=catalogues.sources),
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

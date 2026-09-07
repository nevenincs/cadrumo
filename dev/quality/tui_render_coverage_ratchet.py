"""Shrink-only ratchet over the TUI interfaces no surface renders.

The review inventory has always been able to name them -- ``python -m dev.tui
inventory`` prints "N interfaces, M not rendered" -- and nothing has ever
failed on M. The count moved twice in one campaign without a gate noticing
either direction, which is the definition of an ungated signal.

Keyed by qualname, not by count. A count-based floor accepts a swap: one
interface gaining a surface while another silently loses one nets to zero and
reads as no change. The recorded set makes both halves visible.

The ratchet fails in the four usual directions. A NEW unrendered interface is
debt this change added. A rendered interface that appears here again is a
regression. An interface that gained a surface but stayed listed is unpaid
shrinkage -- lower it in the step that earned it. A recorded name that no
longer exists is a spent entry, and leaving it lets the file drift into
fiction.

Coverage is read from the source tree and the surface registry alone, never
from a rendered run on disk: a run is a disposable artifact whose absence,
staleness, or schema drift must not decide whether this gate has teeth.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

from dev.tui import _coverage, _harness, _inventory

_DECLARATION: Final[Path] = Path(__file__).resolve().parent / "tui_render_coverage_ratchet.toml"


def unrendered_qualnames() -> frozenset[str]:
    """Return every interface qualname no registered surface paints."""
    interfaces = _inventory.scan()
    surfaces = tuple(surface.name for surface in _harness.surfaces())
    table = _coverage.merge_rendered_by(_harness.coverage())
    return frozenset(
        interface.qualname
        for interface in interfaces
        if not _coverage.rendered_by(interface.qualname, surfaces, rendered_table=table)
    )


def recorded_qualnames(declaration: Path = _DECLARATION) -> frozenset[str]:
    """Return the qualnames the declaration currently accepts as unrendered."""
    data = tomllib.loads(declaration.read_text(encoding="utf-8"))
    recorded = data.get("unrendered", {}).get("interfaces", ())
    # TOML gives back untyped values, and a non-string here would compare
    # unequal to every scanned qualname and read as unpaid shrinkage rather
    # than as the malformed declaration it is.
    return frozenset(str(qualname) for qualname in recorded)


def drift(live: frozenset[str], recorded: frozenset[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(newly unrendered, recorded but now rendered or gone)``."""
    return tuple(sorted(live - recorded)), tuple(sorted(recorded - live))


def main() -> int:
    """Report drift in either direction and exit non-zero on any."""
    live = unrendered_qualnames()
    recorded = recorded_qualnames()
    added, spent = drift(live, recorded)

    for name in added:
        print(f"+ {name}")
    for name in spent:
        print(f"- {name}")
    if added:
        print(
            f"\n{len(added)} interface(s) that no surface renders are not recorded. Give each a "
            "surface, or record it here with the reason it has none.",
        )
    if spent:
        print(
            f"\n{len(spent)} recorded interface(s) are now rendered or no longer exist. Remove "
            "them in the step that earned it, so the file cannot drift into fiction.",
        )
    if not added and not spent:
        print(f"tui render coverage: {len(live)} interface(s) unrendered, all recorded.")
    return 1 if (added or spent) else 0


if __name__ == "__main__":
    raise SystemExit(main())

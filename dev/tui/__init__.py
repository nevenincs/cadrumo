"""Dev-lane visual inventory for the shipped TUI surfaces.

This package renders every drivable TUI surface to disk as an image so a
human can look at it. It is development tooling and ships in no wheel; the
production TUI is not aware it exists.

The dependency direction is the whole design constraint. The accepted TUI
architecture decision makes ``cadrumo.entrypoints.tui`` an outermost
entrypoint that no development tool may import, load, re-export, annotate
against, or register from -- out-of-process execution is the only external
reference it sanctions, and it places pilot, replay, screenshot and surface
tooling inside ``cadrumo.entrypoints.tui.devtools``. So nothing here imports
the TUI. The renderer drives that in-boundary harness as a subprocess and
rasterises what it writes, and the inventory reads the source tree as text
rather than importing it.
"""

from __future__ import annotations

__all__: list[str] = []

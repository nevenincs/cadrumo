"""Dev-lane visual inventory for the shipped TUI surfaces.

This package renders every drivable TUI surface to disk as an image so a
human can look at it. It is development tooling and ships in no wheel; the
production TUI is not aware it exists.

The dependency direction is one-way: the harness may import the shipped TUI
it exercises, while production code never imports this package. The renderer
drives the harness as a subprocess and rasterises what it writes.
"""

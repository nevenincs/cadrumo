"""Report every concrete TUI interface no executable fixture surface paints."""

from __future__ import annotations

from dev.tui import _coverage, _harness, _inventory


def unrendered_qualnames() -> tuple[str, ...]:
    """Derive the exact live gap from source and executable registry facts."""
    interfaces = _inventory.scan()
    surfaces = tuple(surface.name for surface in _harness.surfaces())
    table = _harness.coverage()
    return tuple(
        sorted(
            interface.qualname
            for interface in _coverage.unrendered(
                interfaces,
                surfaces,
                rendered_table=table,
            )
        )
    )


def render(unrendered: tuple[str, ...]) -> str:
    """Render the live identities without accepting or classifying any."""
    if not unrendered:
        return "TUI render coverage: every concrete interface has an executable fixture surface."
    rows = "\n".join(f"  - {qualname}" for qualname in unrendered)
    return (
        f"{len(unrendered)} concrete TUI interface(s) have no executable fixture surface:\n"
        f"{rows}\nGive each interface a production-shaped registered fixture."
    )


def main() -> int:
    """Exit non-zero until the live structural gap reaches zero."""
    missing = unrendered_qualnames()
    print(render(missing))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

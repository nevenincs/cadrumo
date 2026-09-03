"""The set of modelos the bundled registry ships, as every screen asks for it.

Each screen needs the same list: every modelo code in the bundled corpus, as a
sorted tuple of strings, so its walk is ordered and its output diffable. That
list was computed by a private three-line function repeated in all ten screen
modules, byte for byte, which is the defect this package exists to find stated
in the package's own source.

The import of the discovery function is deliberately inside the body. The
screens are imported by a runner that also imports the registry authority, and
keeping the application import lazy means importing a screen module costs
nothing until it is asked for the corpus.
"""

from __future__ import annotations

__all__ = ["bundled_modelo_ids"]


def bundled_modelo_ids() -> tuple[str, ...]:
    """Return every bundled modelo code as a sorted tuple of strings."""
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))

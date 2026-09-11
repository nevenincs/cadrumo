"""The set of modelos the bundled registry ships, as every screen asks for it.

Each screen needs the same list: every modelo code in the bundled corpus, as a
sorted tuple of strings, so its walk is ordered and its output diffable. That
list was computed by a private three-line function repeated in all ten screen
modules, byte for byte, which is the defect this package exists to find stated
in the package's own source.

The list comes from the registry compiled from the bundled sources, the same
authority every development screen reads; the signed runtime artifact is a
release product a development checkout does not have. The compiler import is
deliberately inside the body, so importing a screen module costs nothing until
it is asked for the corpus.
"""

from __future__ import annotations

__all__ = ["bundled_modelo_ids"]


def bundled_modelo_ids() -> tuple[str, ...]:
    """Return every bundled modelo code as a sorted tuple of strings."""
    from dev.registry.compiler.authority import compiled_bundled_authority

    return tuple(sorted(str(modelo.id) for modelo in compiled_bundled_authority().modelos))

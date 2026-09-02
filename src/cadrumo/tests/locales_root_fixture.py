"""Test-support scope for pointing catalogue resolution at a fixture root.

The renderer's miss semantics — an absent key and a key-echo value are
both misses — can only be exercised against a catalogue that carries the
defect, and the shipped catalogues are gated echo-free. Production code
never redirects catalogue resolution; the redirection seam lives with the
renderer as ``override_locales_root``, and this module is the thin
package-external entry point tests outside ``cadrumo.core.i18n`` import.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from ..core.i18n.render import override_locales_root

if TYPE_CHECKING:
    from pathlib import Path


@contextmanager
def locales_root_scope(root: Path) -> Generator[None]:
    """Resolve catalogues from ``root`` instead of the packaged resources.

    Delegates to the renderer-owned :func:`override_locales_root` seam so a
    single implementation drives the redirection; this module stays the
    package-external entry point tests outside ``cadrumo.core.i18n`` import.
    """
    with override_locales_root(root):
        yield


__all__ = ["locales_root_scope"]

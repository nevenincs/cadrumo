"""Test-support scope for pointing catalogue resolution at a fixture root.

The renderer's miss semantics — an absent key and a key-echo value are
both misses — can only be exercised against a catalogue that carries the
defect, and the shipped catalogues are gated echo-free. Production code
never redirects catalogue resolution; the redirection context variable
lives with the renderer, and this module holds the only setter, keeping
the production surface free of test-hook overrides.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from ..core.i18n._render import _I18N_LOCALES_ROOT

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def locales_root_scope(root: Path) -> Iterator[None]:
    """Resolve catalogues from ``root`` instead of the packaged resources."""
    token = _I18N_LOCALES_ROOT.set(root)
    try:
        yield
    finally:
        _I18N_LOCALES_ROOT.reset(token)


__all__ = ["locales_root_scope"]

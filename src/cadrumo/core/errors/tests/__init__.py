"""Shared helpers for the ``cadrumo.core.errors`` gates.

Both gates in this package build their subject set by importing the package
tree and enumerating live classes. That is deliberate -- resolving a base
through aliases and multiple inheritance needs the real MRO -- but it makes the
subject set a property of the installed environment rather than of the source.
A class defined only inside an ``except ImportError`` fallback exists when its
extra is ABSENT and not otherwise, so the two gates genuinely examine different
populations on different machines.

:func:`describe_optional_extras` exists so a green from those gates carries the
scope it was measured over, in the same spirit as a vacuity floor reporting how
much it scanned.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

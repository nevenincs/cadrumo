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

import importlib.util

#: Capability-gated optional extras whose presence changes what an
#: import-walking gate can see, each paired with the top-level module that
#: proves the extra is installed.
_OPTIONAL_EXTRAS: tuple[tuple[str, str], ...] = (
    ("browser", "playwright"),
    ("google", "googleapiclient"),
    ("anthropic", "anthropic"),
)


def _is_installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        # A missing parent package makes find_spec raise rather than return
        # None; either way the extra is not usable here.
        return False


def describe_optional_extras() -> str:
    """Return a one-line summary of the optional extras shaping this run."""
    return "extras: " + ", ".join(
        f"{name}={'present' if _is_installed(module) else 'absent'}" for name, module in _OPTIONAL_EXTRAS
    )

"""Innermost, layer-neutral Cadrumo package.

The package initializer is intentionally inert: it owns no public symbols,
imports no submodules, and provides no forwarding or lazy-export surface.
Consumers import each core primitive from the module that defines it.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

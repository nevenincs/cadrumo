"""Invoices: issued and received records, and the facts derived from them.

Inert namespace. Every contract is reached at its own defining module:
``decomposition``, ``enums``, ``errors``, ``models``, ``protocols``, ``service``, ``validators``.

This package re-exported its surface through the namespace, including three
names belonging to :mod:`cadrumo.domain.iva`. That cross-package re-export
was load-bearing in the wrong direction: the iva classification module
imported back into this package for ``IvaRate``, so the two were mutually
dependent and the block carried a comment warning that hoisting it would
break import. Retiring the namespace dissolves the cycle rather than moving
it -- iva reaches ``invoices.enums`` directly, and iva's own symbols are
imported from iva.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

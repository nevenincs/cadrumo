"""Track B financial-input subpackage root.

This subpackage hosts the Transaction Data Pipeline (TDP) building
blocks — VAT enumeration (``aeat.financial.vat``, issue #85), provider
detection (``aeat.financial.providers``, issue #73), and transaction
categorisation (``aeat.financial.categories``, issue #77). Outside
callers import from each child subpackage directly
(e.g. ``from aeat.financial.vat import VATCategory``); the root
package deliberately does not re-export those symbols, to keep the
public surface of each child subpackage explicit and cycle-free.
"""

from __future__ import annotations

__all__: list[str] = []

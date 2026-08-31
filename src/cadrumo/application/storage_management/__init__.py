"""Operator-facing read and reclaim operations over the declared storage tree.

The public facade for the ``aeat config storage`` surface. Operators inspect
four stable areas while the internal taxonomy remains free to evolve. This
package exposes inspection, materialisation, and lifecycle-guarded reclaim, and
deliberately exposes no relocation.

See Also:
    :data:`~cadrumo.core.STORAGE_TAXONOMY`
        The declaration every operation here reads.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

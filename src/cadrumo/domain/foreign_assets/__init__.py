"""Modelo 720 foreign-asset register: persisted asset identity and declaration entries.

Each foreign asset is registered once under an opaque :data:`M720AssetRef`, and
the operator's per-asset declaration facts are keyed by that identity and the
declarant condition, so ledger observations and declarations join on identity
rather than on a sorted row position.

See Also:
    :mod:`adapters.persistence.profile.foreign_assets`
        FINANCIAL secure-object repository that stores the register singleton.
    :mod:`application.foreign_assets`
        Application capability the 720 resolver and operator entry points consume.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

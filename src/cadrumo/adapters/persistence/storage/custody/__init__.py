"""Current-format, profile-scoped password custody contracts.

Inert namespace. Import directly from the owning module. Sixteen modules
carry this package's surface, each already a single concern:
:mod:`~cadrumo.adapters.persistence.storage.custody.capsule` and its
``capsule_records`` / ``capsule_discovery`` siblings for the capsule
lifecycle, ``kdf_supervision`` for the key-derivation worker,
``acceleration_receipt`` for profile-session receipts, ``sentinel`` and
``sentinel_contract``, ``recovery`` and ``recovery_artifact``, ``records``,
``envelope``, ``filesystem``, ``paths``, ``label_head_models`` and
``label_head_repository``, ``zeroise``, and the already-public ``errors``.

This package previously carried a PEP 562 lazy re-export map over all
sixteen. It is retired: a real consumer paid the same either way, because
the map's ``__getattr__`` imported precisely the module a direct import
would and nothing more. What the map appeared to defer was the cost of
importing all sixteen at once, which no consumer does.

The weight it looked like it was deferring is not custody's at all: a
minimal consumer pays roughly 179 modules, and
:mod:`cadrumo.core.errors` alone accounts for 171 of them, reached through
``custody.errors`` -> ``storage.errors`` -> ``core.errors``. Almost every
module here touches that chain, so there was never a cheap subset for a
bounded guard to protect.
"""

__all__: list[str] = []

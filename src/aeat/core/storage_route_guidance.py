"""Operator-facing guidance for storage route refusals.

This module centralises recovery text that several boundaries attach to
fail-closed storage-route diagnostics. The string is used when an explicit
``AEAT_DATABASE_URL`` leaves the effective :class:`~aeat.core.config.StorageRouteKind`
as ``EXPLICIT_DATABASE_URL`` and profile-bound code must refuse instead of
deriving an active bucket database.

The module is text-only by design. Route classification remains in
:func:`aeat.core.config.classify_storage_route`, runtime readiness remains in
``aeat.adapters.persistence.storage.runtime``, and write-policy decisions remain
in ``aeat.application.storage_write_policy``. Keeping this recovery hint in core
lets those layers share one operator message without exposing database paths,
bucket identifiers, profile identifiers, or key material.
"""

from __future__ import annotations

EXPLICIT_DATABASE_URL_PROFILE_RECOVERY = (
    "Unset AEAT_DATABASE_URL before profile setup or profile-bound writes; "
    "use AEAT_LOCAL_STORAGE_ROOT to choose the local storage root, then create "
    "or switch the profile so AEAT can derive the active bucket database."
)

__all__ = ["EXPLICIT_DATABASE_URL_PROFILE_RECOVERY"]

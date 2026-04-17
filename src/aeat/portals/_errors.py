"""Error hierarchy for the portal catalogue.

Every error raised from :mod:`aeat.portals` derives from
:class:`PortalRegistryError`, which in turn derives from the project
root :class:`aeat.errors.AeatError`. Two concrete subclasses cover the
failure modes surfaced to external callers:

- :class:`UnknownPortalError` — raised by registry lookups on an
  unknown / unparseable portal name.
- :class:`PortalIntegrityError` — raised at import time during
  registry assembly when a structural invariant is violated.
"""

from __future__ import annotations

from ..errors import AeatError


class PortalRegistryError(AeatError):
    """Base class for every error raised from :mod:`aeat.portals`."""


class UnknownPortalError(PortalRegistryError):
    """Raised by :func:`aeat.portals.get_portal` on unknown names.

    Attributes:
        portal: The offending portal name or value as supplied by the
            caller.
    """

    def __init__(self, portal: str) -> None:
        """Initialise with the offending portal identifier."""
        super().__init__(f"unknown portal: {portal!r}")
        self.portal = portal


class PortalIntegrityError(PortalRegistryError):
    """Raised at import time when the registry fails a structural check.

    Signals that a portal registry entry violates a cross-reference
    invariant (missing member, extra member, duplicate entry,
    dangling ``replaced_by``, unresolved ``related_modelo``, or
    ``ModeloCode`` member without a backing FILING/CENSUS portal).
    Always raised from
    :func:`aeat.portals._registry._finalise_registry` and therefore
    never crosses a user call stack — it aborts package import.
    """

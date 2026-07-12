"""Error hierarchy for the portal catalogue.

Every error raised from :mod:`aeat.domain.portals` derives from
:class:`PortalRegistryError`, which in turn derives from the project
root :class:`aeat.core.errors.AeatError`. Two concrete subclasses cover the
failure modes surfaced to external callers:

- :class:`UnknownPortalError` — raised by registry lookups on an
  unknown / unparseable portal name.
- :class:`PortalIntegrityError` — raised at import time during
  registry assembly when a structural invariant is violated.
"""

from __future__ import annotations

from ...core.errors import AeatError


class PortalRegistryError(AeatError):
    """Base class for every error raised from :mod:`aeat.domain.portals`."""


class UnknownPortalError(PortalRegistryError):
    """Raised by :func:`aeat.domain.portals.get_portal` on unknown names.

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

    Signals that a portal registry entry violates a structural
    invariant, such as a missing member, extra member, duplicate entry,
    or dangling ``replaced_by`` reference. It can also surface invalid
    registry-backed portal bindings during lookup.
    """


class PortalValidationError(PortalRegistryError, ValueError):
    """Raised when portal metadata violates state or shape invariants.

    Inherits from ValueError to maintain compatibility with Pydantic
    validators.
    """


__all__ = [
    "PortalIntegrityError",
    "PortalRegistryError",
    "PortalValidationError",
    "UnknownPortalError",
]

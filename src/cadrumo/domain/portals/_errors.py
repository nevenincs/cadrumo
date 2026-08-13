"""Error hierarchy for the portal catalogue.

Every error raised from :mod:`cadrumo.domain.portals` derives from
:class:`PortalRegistryError`, which in turn derives from the project
root :class:`cadrumo.core.errors.CadrumoError`. Two concrete subclasses cover the
failure modes surfaced to external callers:

- :class:`UnknownPortalError` — raised by registry lookups on an
  unknown / unparseable portal name.
- :class:`PortalIntegrityError` — raised at import time during
  registry assembly when a structural invariant is violated.
"""

from __future__ import annotations

from ...core.errors import CadrumoError, get_registered_error_code


class PortalRegistryError(CadrumoError):
    """Base class for every error raised from :mod:`cadrumo.domain.portals`."""


class UnknownPortalError(PortalRegistryError):
    """Raised by :func:`cadrumo.domain.portals.get_portal` on unknown names.

    The operator-facing text is the class's registered locale key and nothing
    else. The offending identifier travels as a locale-neutral machine fact in
    ``context``, so it is never spelled into a sentence the class would then
    carry into tracebacks, structured logs and every direct rendering in all
    four locales.

    The key is read from the central error-code registry rather than repeated
    here, so the class carries no second spelling that could drift from the
    registered one.

    Attributes:
        portal: The offending portal name or value as supplied by the
            caller.
    """

    def __init__(self, portal: str) -> None:
        """Initialise from the offending portal identifier alone."""
        super().__init__(
            context={"portal": portal},
            translated_message=get_registered_error_code(type(self)).message_key,
        )
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

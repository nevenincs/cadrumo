"""Canonical registry slot for the wizard-flow catalogue.

Domain modules that need to inspect ``SETUP_FLOW``
import from here, never from ``application.wizard.catalogue``. This
module is the core slot that holds already-built descriptors; it does not build
wizard sections, render prompts, compile profile keys, persist answers, or
own the :mod:`core.setup_answers` typed answer model.

The application layer registers the concrete descriptors at startup via
:func:`register_wizard_catalogue`. Until registration, the accessors
:func:`get_setup_flow` raises
:class:`WizardCatalogueNotRegisteredError` so any premature domain access
surfaces immediately rather than silently falling back to an upward dependency.

The concrete descriptor class stays owned by the application wizard package;
core retains only the opaque registered objects its accessors return.
"""

from __future__ import annotations

from typing import Any

from .errors.hierarchy import CoreError
from .logging import get_logger

_log = get_logger(__name__)


class WizardCatalogueNotRegisteredError(CoreError):
    """Raised when a domain consumer accesses the catalogue before registration."""

    def __init__(self) -> None:
        """Initialise with a fixed message directing the caller to register the catalogue."""
        super().__init__(
            "Wizard catalogue has not been registered. "
            "Call register_wizard_catalogue() at application startup before "
            "any domain module accesses SETUP_FLOW.",
        )


class WizardCatalogueAlreadyRegisteredError(CoreError):
    """Raised when :func:`register_wizard_catalogue` receives different objects after registration."""


# Module-level registry slot: a list is used so the presence check is
# a single ``if _SETUP_FLOW_SLOT`` rather than ``if _SETUP_FLOW_SLOT[0] is not None``.
_SETUP_FLOW_SLOT: list[Any] = []


# KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR:
# Same circular-import rationale as core/profile.py KWARGS-ANY markers.
def register_wizard_catalogue(
    setup_flow: Any,
) -> None:
    """Register the concrete wizard-flow descriptors from the application layer.

    Call this exactly once at application startup (e.g. in the
    ``application.wizard.catalogue`` module body, after the
    ``SETUP_FLOW`` constant is built).

    Calling with identical objects a second time is a no-op. Calling with
    *different* objects raises :class:`WizardCatalogueAlreadyRegisteredError`
    to prevent accidental re-registration from a different source. The function
    stores object identity only; it does not copy, validate, or normalise the
    application-owned descriptors.
    """
    if _SETUP_FLOW_SLOT:
        if _SETUP_FLOW_SLOT[0] is setup_flow:
            return
        raise WizardCatalogueAlreadyRegisteredError(
            "register_wizard_catalogue() called a second time with different objects. "
            "The catalogue must be registered exactly once.",
        )
    _SETUP_FLOW_SLOT.append(setup_flow)
    _log.debug("wizard catalogue registered: setup_flow=%r", setup_flow.id)


# ANY-RETURN-RATIONALE-CATALOGUE-SLOT:
# Concrete wizard-flow type registered at runtime; not importable from cadrumo.core
# without circular import.
def get_setup_flow() -> Any:  # ANY-RETURN-RATIONALE-CATALOGUE-SLOT
    """Return the registered ``SETUP_FLOW`` descriptor.

    Returns:
        The concrete ``SETUP_FLOW`` descriptor registered by the
        application layer. Callers should treat it as the canonical setup-flow
        descriptor and should not import ``application.wizard.catalogue``
        as a fallback.

    Raises:
        WizardCatalogueNotRegisteredError: When the application layer has
            not yet called :func:`register_wizard_catalogue`.
    """
    if not _SETUP_FLOW_SLOT:
        raise WizardCatalogueNotRegisteredError()
    return _SETUP_FLOW_SLOT[0]


__all__ = [
    "WizardCatalogueAlreadyRegisteredError",
    "WizardCatalogueNotRegisteredError",
    "get_setup_flow",
    "register_wizard_catalogue",
]

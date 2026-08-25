"""Canonical registry slot for the wizard-flow catalogue.

Domain modules that need to inspect ``SETUP_FLOW`` or ``WIZARD_FLOWS``
import from here, never from ``application.wizard.catalogue``. This
module is the core slot that holds already-built descriptors; it does not build
wizard sections, render prompts, compile profile keys, persist answers, or
own the :mod:`core.setup_answers` typed answer model.

The application layer registers the concrete descriptors at startup via
:func:`register_wizard_catalogue`. Until registration, the accessors
:func:`get_setup_flow` and :func:`get_wizard_flows` raise
:class:`WizardCatalogueNotRegisteredError` so any premature domain access
surfaces immediately rather than silently falling back to an upward dependency.

The protocol this module defines (:class:`WizardFlowProtocol`) is satisfied by
:class:`application.wizard.models.WizardFlow`. Domain code depends only on the
structural slot and the accessor functions; the concrete descriptor class stays
owned by the application wizard package.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .errors import CoreError
from .logging import get_logger

_log = get_logger(__name__)


class WizardCatalogueNotRegisteredError(CoreError):
    """Raised when a domain consumer accesses the catalogue before registration."""

    def __init__(self) -> None:
        """Initialise with a fixed message directing the caller to register the catalogue."""
        super().__init__(
            "Wizard catalogue has not been registered. "
            "Call register_wizard_catalogue() at application startup before "
            "any domain module accesses SETUP_FLOW or WIZARD_FLOWS.",
        )


class WizardCatalogueAlreadyRegisteredError(CoreError):
    """Raised when :func:`register_wizard_catalogue` receives different objects after registration."""


@runtime_checkable
class WizardFlowProtocol(Protocol):
    """Structural type satisfied by WizardFlow descriptors.

    The protocol captures the smallest attribute core consumers need for
    diagnostics. Accessors still return the concrete descriptor object, but
    domain code reaches it through this core slot and never imports the
    application-layer ``WizardFlow`` class directly.
    """

    @property
    def id(self) -> str:
        """The canonical flow identifier (e.g. ``"setup"``)."""
        ...  # pragma: no cover


# Module-level registry slot: a list is used so the presence check is
# a single ``if _SETUP_FLOW_SLOT`` rather than ``if _SETUP_FLOW_SLOT[0] is not None``.
_SETUP_FLOW_SLOT: list[Any] = []
_WIZARD_FLOWS_SLOT: list[tuple[Any, ...]] = []


# KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR:
# Same circular-import rationale as core/profile.py KWARGS-ANY markers.
def register_wizard_catalogue(
    setup_flow: Any,
    wizard_flows: tuple[Any, ...],
) -> None:
    """Register the concrete wizard-flow descriptors from the application layer.

    Call this exactly once at application startup (e.g. in the
    ``application.wizard.catalogue`` module body, after the
    ``SETUP_FLOW`` / ``WIZARD_FLOWS`` constants are built).

    Calling with identical objects a second time is a no-op. Calling with
    *different* objects raises :class:`WizardCatalogueAlreadyRegisteredError`
    to prevent accidental re-registration from a different source. The function
    stores object identity only; it does not copy, validate, or normalise the
    application-owned descriptors.
    """
    if _SETUP_FLOW_SLOT:
        if _SETUP_FLOW_SLOT[0] is setup_flow and _WIZARD_FLOWS_SLOT[0] is wizard_flows:
            return
        raise WizardCatalogueAlreadyRegisteredError(
            "register_wizard_catalogue() called a second time with different objects. "
            "The catalogue must be registered exactly once.",
        )
    _SETUP_FLOW_SLOT.append(setup_flow)
    _WIZARD_FLOWS_SLOT.append(wizard_flows)
    _log.debug("wizard catalogue registered: setup_flow=%r flows=%d", setup_flow.id, len(wizard_flows))


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


# ANY-RETURN-RATIONALE-CATALOGUE-SLOT:
# Concrete wizard-flow type registered at runtime; not importable from cadrumo.core
# without circular import.
def get_wizard_flows() -> tuple[Any, ...]:  # ANY-RETURN-RATIONALE-CATALOGUE-SLOT
    """Return the registered ``WIZARD_FLOWS`` tuple.

    Returns:
        Tuple of concrete wizard-flow descriptors registered by the
        application layer. The tuple identity is preserved so downstream
        consumers inspect the same catalogue object the application registered.

    Raises:
        WizardCatalogueNotRegisteredError: When the application layer has
            not yet called :func:`register_wizard_catalogue`.
    """
    if not _WIZARD_FLOWS_SLOT:
        raise WizardCatalogueNotRegisteredError()
    return _WIZARD_FLOWS_SLOT[0]


__all__ = [
    "WizardCatalogueAlreadyRegisteredError",
    "WizardCatalogueNotRegisteredError",
    "WizardFlowProtocol",
    "get_setup_flow",
    "get_wizard_flows",
    "register_wizard_catalogue",
]

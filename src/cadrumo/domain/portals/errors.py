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

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.errors.error_codes import get_registered_error_code
from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin


class PortalRegistryPrecondition(StrEnum):
    """Closed failed-condition identities for portal registry refusals."""

    PORTAL_REGISTERED = "portals.registry.portal.registered"
    MODELO_CODE_RECOGNISED = "portals.registry.modelo_code.recognised"
    INTEGRITY_VALID = "portals.registry.integrity.valid"


class PortalRegistryInvariant(StrEnum):
    """The internal portal-registry properties that must hold at assembly."""

    REPLACED_BY_TARGET_REGISTERED = "replaced_by_target_registered"
    PORTAL_ENTRY_UNIQUE = "portal_entry_unique"
    PORTAL_ENUM_COVERAGE_COMPLETE = "portal_enum_coverage_complete"
    ENTRY_PORTAL_MATCHES_MAPPING_KEY = "entry_portal_matches_mapping_key"
    PORTAL_ENUM_CONSUMER_RESOLVES = "portal_enum_consumer_resolves"
    PORTAL_ID_CONSUMER_RESOLVES = "portal_id_consumer_resolves"
    REGISTRY_PORTAL_BINDINGS_AVAILABLE = "registry_portal_bindings_available"


@dataclass(frozen=True)
class PortalFailureClassification:
    """Domain facts that the application boundary must project as a terminal refusal."""

    condition: PortalRegistryPrecondition
    facts: Mapping[str, str | int | bool]
    provenance: ActionEvidenceProvenance
    outcome: NoRecoveryOutcome


class PortalRegistryError(TerminalPreconditionErrorMixin[object], CadrumoError):
    """Base error carrying a domain classification and optional boundary verdict."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        portal_failure: PortalFailureClassification | None = None,
        precondition_verdict: object | None = None,
    ) -> None:
        """Retain domain facts without constructing an application-owned verdict."""
        super().__init__(
            message=message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )
        self._portal_failure = portal_failure

    @property
    def portal_failure(self) -> PortalFailureClassification | None:
        """Return the domain-owned failure classification for a boundary to project."""
        return self._portal_failure


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
        facts = {"portal": portal, "portal_registered": False}
        super().__init__(
            context=facts,
            translated_message=get_registered_error_code(type(self)).message_key,
            portal_failure=PortalFailureClassification(
                condition=PortalRegistryPrecondition.PORTAL_REGISTERED,
                facts=facts,
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
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


def unknown_modelo_error(modelo: str) -> PortalValidationError:
    """Return the terminal refusal for an invalid portal-list modelo request."""
    facts = {"modelo": modelo, "modelo_code_recognised": False}
    return PortalValidationError(
        context=facts,
        translated_message=get_registered_error_code(PortalValidationError).message_key,
        portal_failure=PortalFailureClassification(
            condition=PortalRegistryPrecondition.MODELO_CODE_RECOGNISED,
            facts=facts,
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        ),
    )


def portal_integrity_error(
    invariant: PortalRegistryInvariant,
    *,
    facts: Mapping[str, str | int | bool],
) -> PortalIntegrityError:
    """Return a redacted structural-invariant refusal for portal assembly."""
    context = {"invariant": invariant.value, **facts}
    return PortalIntegrityError(
        context=context,
        translated_message=get_registered_error_code(PortalIntegrityError).message_key,
        portal_failure=PortalFailureClassification(
            condition=PortalRegistryPrecondition.INTEGRITY_VALID,
            facts=context,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    )


__all__ = [
    "PortalFailureClassification",
    "PortalIntegrityError",
    "PortalRegistryError",
    "PortalRegistryInvariant",
    "PortalRegistryPrecondition",
    "PortalValidationError",
    "UnknownPortalError",
    "portal_integrity_error",
    "unknown_modelo_error",
]

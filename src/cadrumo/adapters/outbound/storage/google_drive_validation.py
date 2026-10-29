"""Validation of Drive storage names and keys."""

from __future__ import annotations

from ....application.operator_actions.preconditions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ._key_validation import assert_admissible_object_key_hmac
from .errors import OutboundStorageValidationError


def drive_validation_verdict(
    condition_id: str,
    *,
    field: str,
    provenance: ActionEvidenceProvenance,
):
    """Describe a rejected Drive storage value."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts={"backend": "google_drive", "field": field, "valid": False},
        provenance=provenance,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def validate_namespace(namespace: str) -> str:
    """Normalize and validate a Drive storage namespace."""
    cleaned = namespace.strip()
    if not cleaned:
        raise OutboundStorageValidationError(
            "namespace must not be blank",
            translated_message="adapters.outbound.storage.google_drive.errors.namespace_blank",
            precondition_verdict=drive_validation_verdict(
                "storage.google_drive.namespace.valid",
                field="namespace",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    if "/" in cleaned or "\\" in cleaned:
        raise OutboundStorageValidationError(
            "namespace contains forbidden characters",
            context={"namespace": namespace},
            translated_message="adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters",
            precondition_verdict=drive_validation_verdict(
                "storage.google_drive.namespace.valid",
                field="namespace",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    return cleaned


def validate_hmac(object_key_hmac: str) -> str:
    """Delegate to the one admissibility rule both backends share.

    This backend previously accepted any non-blank value, so the delegation
    NARROWS what it admits. Deliberate: the key is a contract-level digest and
    nothing legitimate produces a character outside the admissible set.
    """
    return assert_admissible_object_key_hmac(object_key_hmac, backend="google_drive")


def validate_put_inputs(
    namespace: str,
    object_key_hmac: str,
) -> tuple[str, str]:
    """Validate and canonicalise the values needed before a Drive write."""
    namespace_clean = validate_namespace(namespace)
    hmac_clean = validate_hmac(object_key_hmac)
    return namespace_clean, hmac_clean

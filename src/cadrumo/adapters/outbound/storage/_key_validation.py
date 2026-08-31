"""One admissibility rule for the object key every storage backend receives.

``object_key_hmac`` is a CONTRACT-level value, not a backend-level one: it is
the same HMAC of the same object key whichever backend stores it, and its
character set is fixed by the digest that produces it rather than by anything
the filesystem or Drive can express. So the two backends have no business
disagreeing about which keys are admissible -- and before this module they did.
Local enforced ``[alnum-_]``; Drive enforced only non-blank.

That asymmetry mattered because of what happens downstream.
:func:`~adapters.outbound.storage._object_name.provider_object_hmac_prefix` is
a bare slice with no sanitisation, deliberately: its module delegates
admissibility to the caller, and the ``sanitize_provider_object_label`` helper
one function below it -- which DOES sanitise -- shows the delegation is a
design choice rather than an oversight. Local discharged the delegated duty and
Drive did not, while Drive interpolates that unsanitised prefix into a query
string (``name contains '<prefix>--'``).

**Severity, stated honestly: latent, not exploitable.** Every production
producer emits a value that already satisfies the strict rule --
``remote_mirror_object_key_hmac`` and the mirror manifest's own key are both
``sha256_hex`` (64 lowercase hex), and both providers' ``probe`` sentinels are
``"00000000probe"``. No path existed by which a hostile key reached the query.
What is closed here is a divergence between two backends implementing one
contract, not a live injection.

The rule is the STRICTER of the two former behaviours. Tightening is the safe
direction: Drive begins refusing keys nothing legitimate produces, whereas
loosening local would let a backend accept a key its sibling rejects and
reintroduce the split. Confirmed before landing that no key any writer in this
repository can produce fails the tightened rule.

Namespace validation deliberately stays per-backend and is NOT lifted here --
see :func:`assert_admissible_object_key_hmac`'s note on the one divergence that
is legitimate.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....application.operator_actions._preconditions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .errors import OutboundStorageValidationError


def _validation_verdict(condition: str, facts: Mapping[str, str | bool]):
    return no_action_precondition_verdict(
        condition_id=condition,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


#: Backend-specific prefix for the translated-message keys, so a refusal keeps
#: the identity of the backend that refused. Parameterised rather than
#: collapsed to one shared message for the reason the AEAT representation gate
#: is: an operator reading a refusal needs to know WHICH backend refused, and
#: flattening two error identities into one loses that.
_MESSAGE_ROOT = "adapters.outbound.storage"


def assert_admissible_object_key_hmac(object_key_hmac: str, *, backend: str) -> str:
    """Return ``object_key_hmac`` stripped, or refuse it for every backend alike.

    Admissible characters are alphanumerics, ``-`` and ``_`` -- the set a
    base16/base64url digest can produce and nothing more. A blank value is
    refused separately so the refusal names the actual problem.

    Args:
        object_key_hmac: The candidate key as the caller received it.
        backend: Backend token used to build the translated-message key
            (``"local"`` or ``"google_drive"``), so each backend's refusal
            keeps its own operator-facing identity.

    Returns:
        The stripped, admissible key.

    Raises:
        OutboundStorageValidationError: When the value is blank, or carries a
            character outside the admissible set.

    Note:
        NAMESPACE validation is deliberately not centralised alongside this.
        The local backend refuses a namespace beginning with ``.`` and Drive
        does not, and that is a genuine capability difference rather than
        drift: a leading dot makes a hidden file on a filesystem and means
        nothing in a Drive folder name. Divergence with a stated reason is
        fine; it is divergence by silence that this module exists to remove.
    """
    cleaned = object_key_hmac.strip()
    if not cleaned:
        raise OutboundStorageValidationError(
            "object_key_hmac must not be blank",
            translated_message=f"{_MESSAGE_ROOT}.{backend}.errors.object_key_hmac_blank",
            precondition_verdict=_validation_verdict(
                "storage.key.present",
                {"backend": backend, "field": "object_key_hmac", "valid": False},
            ),
        )
    if not all(character.isalnum() or character in "-_" for character in cleaned):
        raise OutboundStorageValidationError(
            f"object_key_hmac {object_key_hmac!r} contains forbidden characters",
            context={"object_key_hmac": object_key_hmac},
            translated_message=f"{_MESSAGE_ROOT}.{backend}.errors.object_key_hmac_forbidden_characters",
            precondition_verdict=_validation_verdict(
                "storage.key.admissible",
                {"backend": backend, "field": "object_key_hmac", "valid": False},
            ),
        )
    return cleaned


__all__ = ["assert_admissible_object_key_hmac"]

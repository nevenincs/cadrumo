"""The live-IVA diagnostic reference admits exactly what its producer emits.

A diagnostic reference exists to name a sensitive value without carrying it.
``evidence_ref`` is the single producer on this axis and truncates every digest
to twelve hex characters, deliberately: two references are comparable only if
every producer truncates identically. A field that accepted a wider or
unprefixed value would therefore be accepting something no producer emits, and
the one shape that must never appear — an untruncated digest of a private
value — is exactly the shape a bare ``str`` would let through.

Nothing here is mocked. The reference under test comes from the real
``auth_outcome`` producer over a real error carrying a real diagnostic id.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.auth.clave_movil_support import ClaveMovilApprovalTimeoutError
from ..remote_state_models import (
    LiveIvaAcquisitionFailureMode,
    LiveIvaAuthOutcome,
    LiveIvaReadStatus,
    StoredIvaRemoteStateAcquisitionRow,
)
from ..remote_state_outcomes import auth_outcome, evidence_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIAGNOSTIC_ID = "clave-diagnostic-private-object-key"


class _OutcomeFields(TypedDict):
    """The auth-outcome fields held constant while the reference varies.

    Naming the keys lets the ``**`` splat below check against the model's
    real parameters; a ``dict[str, object]`` would type every one of them
    as ``object``.
    """

    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode


def _outcome_fields() -> _OutcomeFields:
    """Return a well-formed auth outcome except the reference under test."""
    return {
        "status": LiveIvaReadStatus.FAILED,
        "outcome_mode": LiveIvaAcquisitionFailureMode.UNKNOWN,
    }


def test_the_real_producer_emits_a_reference_the_model_accepts() -> None:
    """Anti-vacuity: the refusals below reject values the producer never emits.

    The outcome is built by the production ``auth_outcome`` function over a
    real error, so this is the shape that actually reaches the operator.
    """
    outcome = auth_outcome(
        auth_result=None,
        error=ClaveMovilApprovalTimeoutError(
            "operator reported no prompt",
            failure_mode="auth_completion_timeout",
            context={"diagnostic_id": _DIAGNOSTIC_ID},
        ),
    )

    assert outcome.diagnostic_ref == evidence_ref(_DIAGNOSTIC_ID)
    assert outcome.diagnostic_ref is not None
    assert len(outcome.diagnostic_ref) == len("sha256:") + 12
    assert _DIAGNOSTIC_ID not in outcome.model_dump_json()


def test_an_absent_reference_stays_absent() -> None:
    """A failure whose error carries no diagnostic id names nothing, not ``""``."""
    outcome = auth_outcome(auth_result=None, error=None)

    assert outcome.diagnostic_ref is None


def test_an_untruncated_digest_is_refused() -> None:
    """The untruncated digest is the value the truncation exists to withhold."""
    with pytest.raises(ValidationError):
        LiveIvaAuthOutcome(**_outcome_fields(), diagnostic_ref=f"sha256:{'a' * 64}")


def test_an_unprefixed_reference_is_refused() -> None:
    """Without the scheme the reference does not say what produced it."""
    with pytest.raises(ValidationError):
        LiveIvaAuthOutcome(**_outcome_fields(), diagnostic_ref="a" * 12)


def test_a_non_digest_reference_is_refused() -> None:
    """A locator is the opposite of a reference: it leads back to the value."""
    with pytest.raises(ValidationError):
        LiveIvaAuthOutcome(**_outcome_fields(), diagnostic_ref="diagnostic-private-object-key")


@pytest.mark.parametrize("width", [11, 13])
def test_a_reference_truncated_to_another_width_is_refused(width: int) -> None:
    """A second producer disagreeing about the width is what this guards."""
    with pytest.raises(ValidationError):
        LiveIvaAuthOutcome(**_outcome_fields(), diagnostic_ref=f"sha256:{'a' * width}")


def test_the_stored_row_refuses_what_the_outcome_it_copies_refuses() -> None:
    """The persisted row carries the same value one hop on, so it holds the shape.

    ``auth_diagnostic_ref`` is assigned verbatim from the outcome's
    ``diagnostic_ref``, so a row admitting a shape the outcome refuses could
    only ever hold a value that never came from the producer.
    """
    with pytest.raises(ValidationError):
        StoredIvaRemoteStateAcquisitionRow.model_validate(
            {
                "acquisition_ref": evidence_ref("acquisition"),
                "captured_at": "2026-04-01T10:30:00Z",
                "auth_status": "failed",
                "auth_outcome_mode": "unknown",
                "auth_diagnostic_ref": f"sha256:{'a' * 64}",
                "year_from": 2024,
                "year_to": 2024,
                "target_year": 2026,
                "target_period": "1T",
                "filed_history_succeeded": False,
                "wallet_succeeded": False,
                "surfaces": (),
            },
        )

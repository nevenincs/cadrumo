"""Negative-space contract for existing-password proof classification."""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage import KeyringUnavailableError
from ....adapters.persistence.storage.custody import (
    ProfileCustodyRecordError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from .. import ProfilePasswordProofOperation, map_profile_password_proof_failure
from .._custody_transactions import ProfileCustodyTransactionConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "fault",
    (
        ProfileCustodyRecordError("record integrity failure"),
        ProfileCustodyTransactionConflictError("transaction conflict"),
        ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_RESOURCE_LIMIT),
        ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE),
        KeyringUnavailableError("keyring unavailable"),
    ),
)
@pytest.mark.parametrize("operation", tuple(ProfilePasswordProofOperation))
def test_operational_failures_never_map_to_authentication_refusal(
    fault: BaseException,
    operation: ProfilePasswordProofOperation,
) -> None:
    """Every representative non-password family keeps its original classification."""
    assert map_profile_password_proof_failure(fault, operation=operation) is None

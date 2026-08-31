"""Negative-space contract for existing-password proof classification."""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage.custody.errors import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRecoverySecretError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from ....adapters.persistence.storage.errors import KeyringUnavailableError
from ..authentication import (
    ProfileAuthenticationRefusedError,
    ProfilePasswordProofOperation,
)
from ..custody_ports import map_profile_authentication_proof_failure
from ..custody_transactions import ProfileCustodyTransactionConflictError

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
    assert map_profile_authentication_proof_failure(fault, operation=operation) is None


def test_only_recovery_restore_maps_recovery_secret_refusal() -> None:
    fault = ProfileCustodyRecoverySecretError("internal recovery diagnostic")

    for operation in ProfilePasswordProofOperation:
        mapped = map_profile_authentication_proof_failure(fault, operation=operation)
        if operation is ProfilePasswordProofOperation.RECOVERY_RESTORE:
            assert isinstance(mapped, ProfileAuthenticationRefusedError)
            assert mapped.context is None
        else:
            assert mapped is None


def test_recovery_restore_does_not_map_password_refusal() -> None:
    assert (
        map_profile_authentication_proof_failure(
            ProfileCustodyPasswordError("internal password diagnostic"),
            operation=ProfilePasswordProofOperation.RECOVERY_RESTORE,
        )
        is None
    )

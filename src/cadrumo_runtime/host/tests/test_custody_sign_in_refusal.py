"""A custody refusal of a password sign-in is unavailable for now only when load alone caused it."""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from cadrumo.adapters.persistence.storage.custody.kdf_refusals import (
    busy_refusal,
    resource_busy_refusal,
    resource_refusal,
    supervision_refusal,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.deadline_budget import OrchestrationTimeoutError

from ..profile_login import custody_sign_in_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOAD_DRIVEN = {ProfileCustodyRefusal.KDF_RESOURCE_BUSY, ProfileCustodyRefusal.KDF_SUPERVISION_BUSY}
"""The derivation's permit, lock, child or derivation was late: nothing about the host or the password is known."""


@pytest.mark.parametrize("refusal", [busy_refusal(), resource_busy_refusal()], ids=lambda error: error.refusal.value)
def test_a_load_driven_refusal_is_unavailable_for_now(refusal: ProfileCustodyRefusedError) -> None:
    mapped = custody_sign_in_refusal(refusal)

    assert isinstance(mapped, AutomationCustodyError)
    assert mapped.reason is AutomationCustodyCode.UNAVAILABLE


@pytest.mark.parametrize("refusal", [resource_refusal(), supervision_refusal()], ids=lambda error: error.refusal.value)
def test_a_lasting_host_refusal_keeps_its_typed_reason(refusal: ProfileCustodyRefusedError) -> None:
    assert custody_sign_in_refusal(refusal) is None


def test_the_owner_deadline_is_a_timeout() -> None:
    mapped = custody_sign_in_refusal(ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_TIMEOUT))

    assert isinstance(mapped, OrchestrationTimeoutError)


@pytest.mark.parametrize(
    "reason", sorted(set(ProfileCustodyRefusal) - _LOAD_DRIVEN - {ProfileCustodyRefusal.KDF_TIMEOUT})
)
def test_no_other_refusal_is_told_to_try_again(reason: ProfileCustodyRefusal) -> None:
    assert custody_sign_in_refusal(ProfileCustodyRefusedError(reason)) is None

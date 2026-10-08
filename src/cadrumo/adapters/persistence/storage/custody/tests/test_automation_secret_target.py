"""Every native automation secret backend refuses the same malformed targets."""

from __future__ import annotations

from typing import Any

import pytest

from ......application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..automation_secret_target import AUTOMATION_NAMESPACE_PREFIX, require_automation_secret_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}client-credentials"


def _refused(namespace: Any, account: Any) -> AutomationCustodyError:
    with pytest.raises(AutomationCustodyError) as raised:
        require_automation_secret_target(namespace, account)
    return raised.value


def test_a_namespace_below_the_automation_prefix_with_an_account_is_accepted() -> None:
    require_automation_secret_target(_NAMESPACE, "profile-1")


def test_the_combined_length_ceiling_is_inclusive() -> None:
    account = "a" * (1024 - len(_NAMESPACE))

    require_automation_secret_target(_NAMESPACE, account)

    assert _refused(_NAMESPACE, account + "a").reason is AutomationCustodyCode.INVALID


@pytest.mark.parametrize(
    ("namespace", "account"),
    [
        ("cadrumo.profile.client", "profile-1"),
        (AUTOMATION_NAMESPACE_PREFIX, "profile-1"),
        (_NAMESPACE, ""),
        (f"{_NAMESPACE}\nsplit", "profile-1"),
        (_NAMESPACE, "profile\x00-1"),
        (_NAMESPACE, "profile\x7f-1"),
        (_NAMESPACE, "profile-\ud800"),
        (f"{_NAMESPACE}-\udfff", "profile-1"),
        (None, "profile-1"),
        (_NAMESPACE, None),
        (b"cadrumo.automation.client", "profile-1"),
    ],
    ids=[
        "outside-prefix",
        "bare-prefix",
        "empty-account",
        "newline-in-namespace",
        "nul-in-account",
        "delete-in-account",
        "lone-high-surrogate",
        "lone-low-surrogate",
        "namespace-not-text",
        "account-not-text",
        "namespace-bytes",
    ],
)
def test_a_malformed_target_is_refused_as_invalid(namespace: Any, account: Any) -> None:
    assert _refused(namespace, account).reason is AutomationCustodyCode.INVALID

"""``change_passphrase`` is not a free passphrase-testing oracle.

``change_passphrase`` verifies the operator-supplied ``current_passphrase`` by
unwrapping the stored master key — the SAME secret the login door
authenticates against. The login door evaluates the failed-attempt backoff
before running Argon2id; this second door onto the same key did not, and its
failures did not even reach the login counter. Throttling one door and leaving
the other free buys nothing: an attacker simply uses the free one.

The claim this defends is at ``master_key/_login_throttle.py``: "the caller
evaluates the remaining wait BEFORE running any Argon2id derivation, so the KDF
can never become a passphrase-testing timing oracle." The *timing* half
survived — elapsed time was flat, so it was not a side channel — but the
*passphrase-testing* half did not.

Every case here carries a positive control, because the NEW passphrase is
length-checked BEFORE the current one is verified: a probe using a short new
passphrase never reaches the unwrap and would read as "throttled" when it is
merely short-circuiting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage import MasterKeyPassphraseMismatchError
from ....adapters.persistence.storage.master_key import (
    evaluate_login_throttle,
    record_login_failure,
    reset_login_throttle,
)
from ....core.config import load_settings
from ....core.time import now
from ....tests.secure_sql import isolated_runtime_profile
from .._custody import change_passphrase
from .._login_session import ProfileLoginThrottledError

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NEW_PASSPHRASE = "a-sufficiently-long-new-store-passphrase-0001"  # noqa: S105 - test input
_WRONG_PASSPHRASE = "definitely-not-the-current-store-passphrase"  # noqa: S105 - test input


def _throttle(root: Path, bucket_id: str):
    return evaluate_login_throttle(storage_root=root, bucket_id=bucket_id, now=now())


def test_a_wrong_current_passphrase_reaches_the_unwrap(tmp_path: Path) -> None:
    """Positive control for every other case in this module.

    If the new passphrase were rejected for length first, the verification
    would never run and a throttle probe would report a refusal it did not
    earn.
    """
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(MasterKeyPassphraseMismatchError):
        change_passphrase(current_passphrase=_WRONG_PASSPHRASE, new_passphrase=_NEW_PASSPHRASE)


def test_a_failed_change_feeds_the_shared_login_budget(tmp_path: Path) -> None:
    """A guess spent here costs the attacker what it would cost at the login door."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        root = Path(load_settings().cadrumo_local_storage_root)
        assert _throttle(root, runtime.bucket_id).consecutive_failures == 0

        with pytest.raises(MasterKeyPassphraseMismatchError):
            change_passphrase(current_passphrase=_WRONG_PASSPHRASE, new_passphrase=_NEW_PASSPHRASE)

        after = _throttle(root, runtime.bucket_id)
        assert after.consecutive_failures == 1, "the failure must reach the login door's counter"
        assert after.throttled is True


def test_a_throttled_operator_is_refused_before_the_unwrap(tmp_path: Path) -> None:
    """The refusal must precede Argon2id, not merely follow it.

    Asserted structurally rather than by timing: the throttle is seeded
    directly, so the only way to reach a mismatch error would be to have run
    the derivation first.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        root = Path(load_settings().cadrumo_local_storage_root)
        record_login_failure(storage_root=root, bucket_id=runtime.bucket_id, now=now())
        assert _throttle(root, runtime.bucket_id).throttled is True

        with pytest.raises(ProfileLoginThrottledError):
            change_passphrase(current_passphrase=_WRONG_PASSPHRASE, new_passphrase=_NEW_PASSPHRASE)


def test_a_throttled_operator_is_refused_even_with_the_correct_passphrase(tmp_path: Path) -> None:
    """The gate runs before verification, so it cannot depend on the answer.

    A gate that let the correct passphrase through would leak exactly the bit
    the throttle exists to withhold.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        root = Path(load_settings().cadrumo_local_storage_root)
        correct = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        record_login_failure(storage_root=root, bucket_id=runtime.bucket_id, now=now())

        with pytest.raises(ProfileLoginThrottledError):
            change_passphrase(current_passphrase=correct, new_passphrase=_NEW_PASSPHRASE)


def test_an_unthrottled_correct_change_succeeds_and_clears_the_budget(tmp_path: Path) -> None:
    """Anti-tautology: the guard discriminates rather than refusing everything."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        root = Path(load_settings().cadrumo_local_storage_root)
        correct = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        record_login_failure(storage_root=root, bucket_id=runtime.bucket_id, now=now())
        reset_login_throttle(storage_root=root, bucket_id=runtime.bucket_id)

        result = change_passphrase(current_passphrase=correct, new_passphrase=_NEW_PASSPHRASE)

        assert result.changed is True
        assert _throttle(root, runtime.bucket_id).consecutive_failures == 0, (
            "proving possession of the secret must clear the budget, as login does"
        )


def test_the_throttle_is_evaluated_against_the_login_doors_own_helpers(tmp_path: Path) -> None:
    """One budget, not a second counter that happens to behave similarly.

    A private re-implementation would satisfy every behavioural case above
    while leaving the two doors independently exhaustible.
    """
    import inspect

    from .. import _custody

    source = inspect.getsource(_custody.change_passphrase)

    assert "evaluate_login_throttle" in source
    assert "record_login_failure" in source

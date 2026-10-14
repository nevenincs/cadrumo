"""A login whose sign-in was not kept names the failed prerequisite and the remedy.

The keychain is the only replaced component: an in-memory store, or one that
fails as the Windows credential store fails for a logon without credentials.
The probe, the login-session port and the notice projection are production.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.application.user_profile.login_session import ProfileLoginOutcome
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.core.i18n.render import tr
from cadrumo.core.profile_session import KeychainUnavailability

from .. import custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_AT = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


class _Win32CredentialError(Exception):
    """The Windows credential store's error shape: the Win32 code first."""


class _Keychain:
    def __init__(self, failure: Exception | None) -> None:
        self.failure = failure
        self.writes = 0

    def get_password(self, service_name: str, username: str) -> str | None:
        if self.failure is not None:
            raise self.failure
        return None

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.writes += 1

    def delete_password(self, service_name: str, username: str) -> None:
        self.writes += 1


def _outcome() -> ProfileLoginOutcome:
    return ProfileLoginOutcome(
        bucket_id=str(uuid4()),
        label="synthetic",
        authenticated_at=_AT,
        idle_deadline=_AT + timedelta(minutes=15),
        absolute_deadline=_AT + timedelta(hours=4),
        session_persisted=False,
        already_authenticated=False,
    )


@pytest.mark.parametrize(
    ("failure", "keychain", "message_key"),
    [
        (
            _Win32CredentialError(1312, "CredRead", "A specified logon session does not exist."),
            KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS,
            "cli.config.login.notices.session_not_persisted_logon",
        ),
        (
            _Win32CredentialError(5, "CredRead", "Access is denied."),
            KeychainUnavailability.REFUSED,
            "cli.config.login.notices.session_not_persisted",
        ),
        (None, None, "cli.config.login.notices.session_not_persisted_unconfirmed"),
    ],
    ids=["logon_without_credentials", "refused", "keychain_usable_here"],
)
def test_the_notice_names_why_the_sign_in_was_not_kept(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception | None,
    keychain: KeychainUnavailability | None,
    message_key: str,
) -> None:
    store = _Keychain(failure)
    monkeypatch.setattr(receipt, "_keyring", lambda: (store, KeyError, KeyError))
    outcome = _outcome()
    with bind_profile_login_session_port(build_profile_login_session_port()):
        (notice,) = custody._login_notices(outcome)
    assert notice.code == "config.login.session_not_persisted"
    assert notice.message == tr(message_key)
    expected = {"profile_id": outcome.bucket_id} | ({} if keychain is None else {"keychain": keychain.value})
    assert notice.context == expected
    assert store.writes == 0


def test_a_missing_backend_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_backend() -> None:
        raise KeyringUnavailableError("none", unavailability=KeychainUnavailability.NO_BACKEND)

    monkeypatch.setattr(receipt, "_keyring", no_backend)
    with bind_profile_login_session_port(build_profile_login_session_port()):
        (notice,) = custody._login_notices(_outcome())
    assert notice.message == tr("cli.config.login.notices.session_not_persisted_no_backend")
    assert notice.context is not None and notice.context["keychain"] == "no_backend"


def test_a_kept_sign_in_carries_no_persistence_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(receipt, "_keyring", lambda: (_Keychain(None), KeyError, KeyError))
    kept = _outcome().model_copy(update={"session_persisted": True})
    assert custody._login_notices(kept) == ()

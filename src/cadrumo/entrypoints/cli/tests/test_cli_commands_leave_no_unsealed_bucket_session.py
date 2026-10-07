"""Supported CLI and explicit local authentication leave no unreachable key holders."""

from __future__ import annotations

import gc
from collections.abc import Callable, Iterator
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import isolated_profile_storage_fixture
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli

from ....application.user_profile.login_session import ProfileLoginOutcome, authenticate_profile_for_invocation
from ....application.user_profile.login_session_port import (
    ProfileBucketSessionPort,
    ProfileLoginSessionPort,
    bind_profile_login_session_port,
)
from ....application.user_profile.profile_record_repository import profile_record_session_if_authenticated
from ....application.user_profile.session_admission import (
    ProfileCredentialRequestV1,
    ProfileSessionAdmissionState,
    admit_profile_session,
)
from ....core.config import load_settings
from ....core.paths import effective_storage_root
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.authority_artifact import ProfileDecodeContext
from .portable_human_cli_runtime import portable_human_cli_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated = isolated_profile_storage_fixture(name="_isolated", dispose_engine_around=True)

_LEDGER_ADD = (
    "app", "ledger", "add", "--date", "2026-03-10", "--amount", "121.00",
    "--direction", "OUTGOING", "--description", "Supplier",
)  # fmt: skip


def _live_sessions() -> list[BucketSession]:
    gc.collect()
    return [candidate for candidate in gc.get_objects() if isinstance(candidate, BucketSession)]


@pytest.fixture
def unreachable_key_holders() -> Callable[[], list[BucketSession]]:
    """Report unsealed, unbound sessions opened since the case started."""
    preexisting = _live_sessions()

    def report() -> list[BucketSession]:
        bound = current_active_bucket_session()
        return [
            candidate
            for candidate in _live_sessions()
            if not candidate.sealed
            and candidate is not bound
            and not any(candidate is existing for existing in preexisting)
        ]

    return report


def test_read_write_and_refusal_commands_leave_no_unreachable_session(
    unreachable_key_holders: Callable[[], list[BucketSession]],
) -> None:
    refused = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert refused.exit_code != 0, refused.output
    assert unreachable_key_holders() == []

    for label in ("first", "second"):
        profile_id = register_cli_profile(label=label, log_in=False)
        session = current_active_bucket_session()
        assert session is not None
        with portable_human_cli_runtime(
            storage_root=effective_storage_root(),
            profile_id=UUID(profile_id),
            label=label,
        ) as runtime:
            written = runtime.invoke(list(_LEDGER_ADD))
            assert written.exit_code == 0, written.output
            listed = runtime.invoke(["--format", "json", "app", "ledger", "list"])
            assert listed.exit_code == 0, listed.output
        assert unreachable_key_holders() == []


@pytest.fixture
def decode_context() -> Iterator[ProfileDecodeContext]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_decode_context()


def _credentials(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome:
    return authenticate_profile_for_invocation(
        name="first",
        passphrase_callback=lambda: load_settings().cadrumo_dev_test_database_password.get_secret_value(),
        profile_decode_context=request.profile_decode_context,
    )


def test_authenticating_another_profile_seals_the_displaced_session(
    decode_context: ProfileDecodeContext,
    unreachable_key_holders: Callable[[], list[BucketSession]],
) -> None:
    first = register_cli_profile(label="first", log_in=False)
    second = register_cli_profile(label="second", log_in=False)
    displaced = current_active_bucket_session()
    assert displaced is not None and displaced.bucket_id == second

    admission = admit_profile_session(
        bucket_id=first,
        profile_decode_context=decode_context,
        credentials=_credentials,
    )

    assert admission.state is ProfileSessionAdmissionState.AUTHENTICATED
    assert displaced.sealed
    authenticated = current_active_bucket_session()
    assert authenticated is not None and authenticated.bucket_id == first and not authenticated.sealed
    assert profile_record_session_if_authenticated(first, profile_decode_context=decode_context) is not None
    assert profile_record_session_if_authenticated(second, profile_decode_context=decode_context) is None
    assert unreachable_key_holders() == []


def test_authentication_binding_failure_leaves_no_unreachable_key_holder(
    decode_context: ProfileDecodeContext,
    unreachable_key_holders: Callable[[], list[BucketSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = register_cli_profile(label="first", log_in=False)
    second = register_cli_profile(label="second", log_in=False)
    displaced = current_active_bucket_session()
    assert displaced is not None and displaced.bucket_id == second
    port = build_profile_login_session_port()
    original_bind = type(port).bind_session

    def refuse_binding(self: ProfileLoginSessionPort, session: ProfileBucketSessionPort) -> None:
        original_bind(self, session)
        raise RuntimeError("session binding refused")

    monkeypatch.setattr(type(port), "bind_session", refuse_binding)
    with bind_profile_login_session_port(port), pytest.raises(RuntimeError, match="session binding refused"):
        admit_profile_session(bucket_id=first, profile_decode_context=decode_context, credentials=_credentials)

    assert displaced.sealed
    bound = current_active_bucket_session()
    assert bound is None or bound.sealed
    assert profile_record_session_if_authenticated(first, profile_decode_context=decode_context) is None
    assert profile_record_session_if_authenticated(second, profile_decode_context=decode_context) is None
    assert unreachable_key_holders() == []

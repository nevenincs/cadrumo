"""Candidate receipt publication against real encrypted profile custody."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import RECEIPT_LOGIN_ID, committed_sign_in
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.profile_login_session import build_profile_login_session_port
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import publish_test_profile_capsule
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.login_session import (
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
    borrow_profile_receipt_key,
    resume_profile_candidate,
)
from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_PROFILE_CREDENTIAL = "candidate-receipt-test-passphrase"
_REPLACEMENT = "candidate-receipt-replacement-passphrase"


class _KeyringError(Exception):
    """Controlled optional OS credential-store failure."""


class _Keyring:
    """Exact service/account store for the real encrypted receipt writer."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.writes = 0
        self.unavailable = False

    def get_password(self, service_name: str, username: str) -> str | None:
        if self.unavailable:
            raise _KeyringError("unavailable")
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        if self.unavailable:
            raise _KeyringError("unavailable")
        self.writes += 1
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.entries.pop((service_name, username), None)


@pytest.fixture
def keyring(monkeypatch: pytest.MonkeyPatch) -> _Keyring:
    store = _Keyring()
    monkeypatch.setattr(receipt, "_keyring", lambda: (store, _KeyringError, _KeyringError))
    return store


@pytest.fixture
def registered(tmp_path: Path) -> Generator[tuple[Path, UUID]]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        with bundled_indexed_authority().operation() as authority:
            result = register_profile_with_credentials(
                label="Candidate receipt profile",
                passphrase=_PROFILE_CREDENTIAL,
                profile_create_context=authority.profile_create_context(),
                profile_decode_context=authority.profile_decode_context(),
            )
        yield root, UUID(result.profile_id)


def test_password_candidate_publishes_once_without_promoting_custody(
    registered: tuple[Path, UUID], keyring: _Keyring
) -> None:
    root, profile_id = registered
    binding = committed_sign_in(root, profile_id).binding
    captured = committed_sign_in(root, profile_id).establish().current
    other_id = uuid4()
    publish_test_profile_capsule(other_id, label="Other receipt profile", root=root)
    other = receipt.mint_profile_session(
        storage_root=root,
        profile_id=other_id,
        custody_generation=1,
        dek_epoch="other-epoch",
        dek=bytes(range(32)),
        now=datetime.now(UTC),
        idle_minutes=15,
        absolute_minutes=240,
        login_id=RECEIPT_LOGIN_ID,
        sign_in=committed_sign_in(root, other_id),
        generation=committed_sign_in(root, other_id).establish().current,
    )
    other_path = receipt.profile_session_path(storage_root=root, profile_id=other_id)
    other_bytes = other_path.read_bytes()
    other_entry = keyring.entries[(receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{other_id}:{other.session_id}")]
    target_path = receipt.profile_session_path(storage_root=root, profile_id=profile_id)
    assert not target_path.exists()

    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
    ):
        active = current_active_bucket_session()
        selected = resolve_active_bucket_id()
        with authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        ) as candidate:
            assert not candidate.outcome.session_persisted
            assert candidate.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
            persisted_bytes = target_path.read_bytes()
            fence = committed_sign_in(root, profile_id).observe().current
            assert fence is not None
            assert f'"sign_in_lineage":"{fence.lineage}"'.encode() in persisted_bytes
            entries = dict(keyring.entries)
            writes = keyring.writes
            assert candidate.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
            assert target_path.read_bytes() == persisted_bytes
            assert keyring.entries == entries and keyring.writes == writes
            assert current_active_bucket_session() is active
            assert resolve_active_bucket_id() == selected
            original = candidate.outcome
        with (
            borrow_profile_receipt_key(bucket_id=profile_id) as proof,
            resume_profile_candidate(
                bucket_id=profile_id,
                receipt_key=proof,
                profile_decode_context=authority.profile_decode_context(),
            ) as resumed,
        ):
            assert resumed.outcome.session_persisted
            assert resumed.outcome.already_authenticated
            assert resumed.outcome.authenticated_at == original.authenticated_at
            assert resumed.outcome.idle_deadline == original.idle_deadline
            assert resumed.outcome.absolute_deadline == original.absolute_deadline
            assert resumed.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
            assert target_path.read_bytes() == persisted_bytes
            assert keyring.writes == writes
            assert current_active_bucket_session() is active
            assert resolve_active_bucket_id() == selected
    assert other_path.read_bytes() == other_bytes
    assert keyring.entries[(receipt.PROFILE_SESSION_KEYCHAIN_SERVICE, f"{other_id}:{other.session_id}")] == other_entry


def test_unavailable_keyring_does_not_invalidate_password_candidate(
    registered: tuple[Path, UUID], keyring: _Keyring
) -> None:
    root, profile_id = registered
    binding = committed_sign_in(root, profile_id).binding
    captured = committed_sign_in(root, profile_id).establish().current
    keyring.unavailable = True
    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
        authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        ) as candidate,
    ):
        assert not candidate.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
        assert not candidate.session.sealed
        assert candidate.session.dek
        assert not receipt.profile_session_path(storage_root=root, profile_id=profile_id).exists()


def test_closed_and_expired_candidates_cannot_publish(registered: tuple[Path, UUID], keyring: _Keyring) -> None:
    root, profile_id = registered
    binding = committed_sign_in(root, profile_id).binding
    captured = committed_sign_in(root, profile_id).establish().current
    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
    ):
        with authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        ) as closed:
            pass
        with pytest.raises(ProfileReceiptRefusedError):
            closed.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
        with authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
            now=datetime.now(UTC) - timedelta(minutes=30),
        ) as expired:
            with pytest.raises(ProfileReceiptRefusedError) as caught:
                expired.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
            assert caught.value.reason is ProfileSessionRefusalReason.EXPIRED_IDLE
    assert not receipt.profile_session_path(storage_root=root, profile_id=profile_id).exists()
    assert keyring.writes == 0


def test_changed_committed_custody_refuses_before_receipt_mint(
    registered: tuple[Path, UUID], keyring: _Keyring
) -> None:
    root, profile_id = registered
    binding = committed_sign_in(root, profile_id).binding
    captured = committed_sign_in(root, profile_id).establish().current
    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
        authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        ) as candidate,
    ):
        before = load_committed_profile_password_material(profile_id, root=root).envelope
        rotated = rotate_profile_passphrase(
            profile_id=profile_id,
            current_passphrase=_PROFILE_CREDENTIAL,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
            profile_decode_context=authority.profile_decode_context(),
        )
        assert rotated.password_generation == before.password_generation + 1
        with pytest.raises(ProfileReceiptRefusedError) as caught:
            candidate.persist_acceleration_receipt(login_id=RECEIPT_LOGIN_ID, binding=binding, sign_in=captured)
        assert caught.value.reason is ProfileSessionRefusalReason.CUSTODY_CHANGED
    assert not receipt.profile_session_path(storage_root=root, profile_id=profile_id).exists()
    assert keyring.writes == 0


def test_generation_advanced_after_publication_leaves_no_receipt(
    registered: tuple[Path, UUID], keyring: _Keyring
) -> None:
    root, profile_id = registered
    sign_in = committed_sign_in(root, profile_id)
    captured = sign_in.establish().current
    advanced = sign_in.advance().current
    with (
        bundled_indexed_authority().operation() as authority,
        bind_profile_custody_port(build_profile_custody_port()),
        bind_profile_login_session_port(build_profile_login_session_port()),
        authenticate_profile_candidate(
            bucket_id=profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        ) as candidate,
    ):
        assert candidate.mints_receipt
        assert not candidate.persist_acceleration_receipt(
            login_id=RECEIPT_LOGIN_ID, binding=sign_in.binding, sign_in=captured
        )
        assert not candidate.session.sealed
    assert not receipt.profile_session_path(storage_root=root, profile_id=profile_id).exists()
    assert keyring.writes == 0 and keyring.entries == {}
    assert sign_in.observe().current == advanced

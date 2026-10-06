"""The receipt's sign-in binding: originating login, sign-in generation and schema dispatch.

Receipts are minted by the production writer against committed custody and a
real sign-in generation record. The OS keychain is the in-memory store the
sibling receipt tests use, because this logon session cannot custody a key.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests import receipt_binding_probe as binding_probe
from cadrumo.adapters.persistence.storage.custody.tests.receipt_runtime_resume import resume_receipt_as_runtime

from ......application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ......core.base64_codec import b64_decode, b64_encode
from ......core.hashing import canonical_json_bytes
from ......core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from ...errors import DecryptionError, StorageValidationError
from .. import acceleration_receipt as receipt
from ..acceleration_receipt_crypto import (
    PROFILE_SESSION_SCHEMA_VERSION,
    PersistedProfileSession,
    profile_session_login_binding,
    unwrap_profile_session_dek,
)
from ..filesystem_primitives import ensure_profile_custody_local_directory
from ..sign_in_generation import (
    SignInGeneration,
    SignInGenerationCustody,
    SignInGenerationObservation,
    SignInGenerationState,
)
from .receipt_sign_in import OTHER_LOGIN_ID, RECEIPT_LOGIN_ID, publish_sign_in_custody, uncommitted_sign_in

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
_EPOCH = "binding-epoch"
_SERVICE = receipt.PROFILE_SESSION_KEYCHAIN_SERVICE


class _KeyringError(Exception):
    """Controlled keychain failure."""


class _Keyring:
    """Exact service/account store standing in for the OS credential manager."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.unavailable = False

    def get_password(self, service_name: str, username: str) -> str | None:
        if self.unavailable:
            raise _KeyringError("unavailable")
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        if self.unavailable:
            raise _KeyringError("unavailable")
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        if self.unavailable:
            raise _KeyringError("unavailable")
        self.entries.pop((service_name, username), None)


@pytest.fixture
def keychain(monkeypatch: pytest.MonkeyPatch) -> _Keyring:
    store = _Keyring()
    monkeypatch.setattr(receipt, "_keyring", lambda: (store, _KeyringError, _KeyringError))
    return store


@pytest.fixture
def profile_id() -> UUID:
    return uuid4()


@pytest.fixture
def sign_in(tmp_path: Path, profile_id: UUID) -> SignInGenerationCustody:
    return publish_sign_in_custody(tmp_path, profile_id)


def _mint(
    sign_in: SignInGenerationCustody,
    *,
    login_id: str = RECEIPT_LOGIN_ID,
    generation: SignInGeneration | None = None,
) -> PersistedProfileSession:
    """Mint as the runtime does: with the generation captured when the session was published."""
    captured = sign_in.establish().current if generation is None else generation
    return receipt.mint_profile_session(
        storage_root=sign_in.root,
        profile_id=sign_in.binding.profile_id,
        custody_generation=sign_in.binding.custody_generation,
        dek_epoch=_EPOCH,
        dek=bytes(range(32)),
        now=_NOW,
        idle_minutes=15,
        absolute_minutes=240,
        login_id=login_id,
        sign_in=sign_in,
        generation=captured,
    )


def _resume(sign_in: SignInGenerationCustody) -> receipt.ProfileSessionResumeOutcome:
    outcome, dek = resume_receipt_as_runtime(
        storage_root=sign_in.root,
        profile_id=sign_in.binding.profile_id,
        custody_generation=sign_in.binding.custody_generation,
        dek_epoch=_EPOCH,
        now=_NOW + timedelta(minutes=1),
    )
    if dek is not None:
        assert bytes(dek) == bytes(range(32))
        dek[:] = bytes(len(dek))
    return outcome


def _path(sign_in: SignInGenerationCustody) -> Path:
    return receipt.profile_session_path(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)


def test_custody_cleanup_retains_key_locator_until_keychain_confirms_absence(
    sign_in: SignInGenerationCustody,
    keychain: _Keyring,
) -> None:
    record = _mint(sign_in)
    original = _path(sign_in).read_bytes()
    keychain.unavailable = True
    with pytest.raises(receipt.KeyringUnavailableError):
        receipt.delete_profile_session(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
    assert _path(sign_in).read_bytes() == original
    keychain.unavailable = False
    receipt.delete_profile_session(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
    assert not _path(sign_in).exists()
    assert _account(sign_in.binding.profile_id, record.session_id) not in keychain.entries


def _account(profile_id: UUID, session_id: UUID) -> tuple[str, str]:
    return (_SERVICE, f"{profile_id}:{session_id}")


def _write_schema_2_receipt(sign_in: SignInGenerationCustody, keychain: _Keyring) -> tuple[Path, UUID]:
    """Publish a receipt exactly as the previous build wrote it, with its keychain half.

    The schema-2 document has no sign-in fields, so a strict schema-3 parse of
    it fails. Its bytes are canonical, as the previous writer emitted them.
    """
    profile_id = sign_in.binding.profile_id
    session_id = uuid4()
    document = {
        "absolute_deadline": (_NOW + timedelta(hours=4)).isoformat(),
        "ciphertext_b64": b64_encode(secrets.token_bytes(32)),
        "custody_generation": sign_in.binding.custody_generation,
        "dek_epoch": _EPOCH,
        "idle_deadline": (_NOW + timedelta(minutes=15)).isoformat(),
        "issued_at": _NOW.isoformat(),
        "nonce_b64": b64_encode(secrets.token_bytes(12)),
        "profile_id": str(profile_id),
        "schema_version": 2,
        "session_id": str(session_id),
        "tag_b64": b64_encode(secrets.token_bytes(16)),
    }
    path = _path(sign_in)
    ensure_profile_custody_local_directory(path.parent.parent)
    ensure_profile_custody_local_directory(path.parent)
    path.write_bytes(canonical_json_bytes(document))
    keychain.entries[_account(profile_id, session_id)] = b64_encode(secrets.token_bytes(32))
    return path, session_id


class TestMintBinding:
    """A minted receipt carries the login commitment and the durable generation."""

    def test_mint_stamps_the_established_generation_and_resumes(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        assert sign_in.observe().state is SignInGenerationState.MISSING

        record = _mint(sign_in)

        observed = sign_in.observe()
        assert observed.state is SignInGenerationState.PRESENT
        assert record.sign_in == observed.current
        assert record.schema_version == PROFILE_SESSION_SCHEMA_VERSION == 3
        assert record.login_binding == profile_session_login_binding(
            profile_id=record.profile_id, session_id=record.session_id, login_id=RECEIPT_LOGIN_ID
        )
        payload = _path(sign_in).read_bytes()
        stored = json.loads(payload)
        assert stored["schema_version"] == 3
        assert stored["sign_in_lineage"] == str(record.sign_in.lineage)
        assert stored["sign_in_generation"] == record.sign_in.generation
        assert stored["login_binding"] == record.login_binding
        assert RECEIPT_LOGIN_ID.encode() not in payload
        assert _path(sign_in).name == "session.v2.json"
        assert _account(record.profile_id, record.session_id) in keychain.entries

        outcome = _resume(sign_in)
        assert outcome.resumed and outcome.record == record

    def test_a_later_mint_keeps_the_existing_generation(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        first = _mint(sign_in)
        second = _mint(sign_in)

        assert first.sign_in == second.sign_in
        assert _account(first.profile_id, first.session_id) not in keychain.entries
        assert _account(second.profile_id, second.session_id) in keychain.entries

    def test_a_mint_after_an_advance_stamps_the_advanced_generation(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        first = _mint(sign_in)
        advanced = sign_in.advance().current

        second = _mint(sign_in)

        assert second.sign_in == advanced != first.sign_in

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("login_binding", "f" * 64),
            ("sign_in", SignInGeneration(lineage=uuid4(), generation=1)),
            ("sign_in", "advanced"),
        ],
        ids=("login-binding", "sign-in-lineage", "sign-in-generation"),
    )
    def test_a_substituted_binding_fails_the_tag_and_is_removed(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring, field: str, value: object
    ) -> None:
        record = _mint(sign_in)
        if value == "advanced":
            value = SignInGeneration(lineage=record.sign_in.lineage, generation=record.sign_in.generation + 1)
        forged = record.model_copy(update={field: value})
        key = keychain.entries[_account(record.profile_id, record.session_id)]
        with pytest.raises(DecryptionError):
            unwrap_profile_session_dek(session_key=b64_decode(key), record=forged)
        _path(sign_in).write_bytes(receipt._receipt_bytes(forged))

        outcome = _resume(sign_in)

        assert outcome.refusal is ProfileSessionRefusalReason.ABSENT
        assert outcome.binding is (
            ReceiptBindingRefusal.LOGIN_MISMATCH
            if field == "login_binding"
            else ReceiptBindingRefusal.GENERATION_CHANGED
        )
        assert not _path(sign_in).exists()
        assert _account(record.profile_id, record.session_id) not in keychain.entries

    def test_mint_refuses_uncommitted_custody_without_any_artifact(
        self, tmp_path: Path, profile_id: UUID, keychain: _Keyring
    ) -> None:
        unbacked = uncommitted_sign_in(tmp_path, profile_id)

        with pytest.raises(AutomationCustodyError) as refused:
            _mint(unbacked, generation=SignInGeneration(lineage=uuid4(), generation=1))

        assert refused.value.reason is AutomationCustodyCode.INVALID

        assert not _path(unbacked).exists()
        assert unbacked.observe().state is SignInGenerationState.MISSING
        assert keychain.entries == {}

    @pytest.mark.parametrize("mismatch", ["profile", "custody-generation", "root", "empty-login", "long-login"])
    def test_mint_refuses_inputs_that_do_not_belong_together(
        self, tmp_path: Path, sign_in: SignInGenerationCustody, keychain: _Keyring, mismatch: str
    ) -> None:
        profile = sign_in.binding.profile_id
        generation = sign_in.binding.custody_generation
        root = sign_in.root
        login = RECEIPT_LOGIN_ID
        if mismatch == "profile":
            profile = uuid4()
        elif mismatch == "custody-generation":
            generation += 1
        elif mismatch == "root":
            root = tmp_path / "elsewhere"
        elif mismatch == "empty-login":
            login = ""
        else:
            login = "x" * 257
        with pytest.raises(StorageValidationError):
            receipt.mint_profile_session(
                storage_root=root,
                profile_id=profile,
                custody_generation=generation,
                dek_epoch=_EPOCH,
                dek=bytes(range(32)),
                now=_NOW,
                idle_minutes=15,
                absolute_minutes=240,
                login_id=login,
                sign_in=sign_in,
                generation=SignInGeneration(lineage=uuid4(), generation=1),
            )
        assert sign_in.observe().state is SignInGenerationState.MISSING
        assert keychain.entries == {}


class TestCapturedGeneration:
    """A mint stamps the generation captured at publication, or writes nothing."""

    def test_a_generation_advanced_after_capture_leaves_no_receipt(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        captured = sign_in.establish().current
        advanced = sign_in.advance().current

        with pytest.raises(AutomationCustodyError) as refused:
            _mint(sign_in, generation=captured)

        assert refused.value.reason is AutomationCustodyCode.CONFLICT
        assert not _path(sign_in).exists()
        assert keychain.entries == {}
        assert sign_in.observe().current == advanced

    def test_a_mint_never_creates_the_generation_record(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        with pytest.raises(AutomationCustodyError) as refused:
            _mint(sign_in, generation=SignInGeneration(lineage=uuid4(), generation=1))

        assert refused.value.reason is AutomationCustodyCode.CONFLICT
        assert sign_in.observe().state is SignInGenerationState.MISSING
        assert not _path(sign_in).exists()
        assert keychain.entries == {}

    def test_a_record_that_became_unreadable_after_capture_leaves_no_receipt(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        captured = sign_in.establish().current
        sign_in.path.write_bytes(b"{not a record")

        with pytest.raises(AutomationCustodyError) as refused:
            _mint(sign_in, generation=captured)

        assert refused.value.reason is AutomationCustodyCode.CONFLICT
        assert sign_in.observe().state is SignInGenerationState.UNREADABLE
        assert not _path(sign_in).exists()
        assert keychain.entries == {}

    def test_the_mint_stamps_the_capture_not_a_later_lineage(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        captured = sign_in.establish().current

        record = _mint(sign_in, generation=captured)

        assert record.sign_in == captured == sign_in.observe().current
        assert _resume(sign_in).resumed


class TestOlderSchemaDispatch:
    """A record from the previous schema is deleted by every keychain-backed reader."""

    def test_resume_deletes_both_halves(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        path, session_id = _write_schema_2_receipt(sign_in, keychain)

        outcome = _resume(sign_in)

        assert outcome.refusal is ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH
        assert outcome.record is None
        assert not path.exists()
        assert _account(sign_in.binding.profile_id, session_id) not in keychain.entries

    def test_borrow_reads_only_the_legacy_locator_proof(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        path, session_id = _write_schema_2_receipt(sign_in, keychain)
        before = path.read_bytes()
        outcome, key = receipt.borrow_profile_session_key(
            storage_root=sign_in.root,
            profile_id=sign_in.binding.profile_id,
        )
        assert key is not None
        try:
            assert outcome.resumed and outcome.record is None
            assert len(key) == 32
            assert path.read_bytes() == before
            assert _account(sign_in.binding.profile_id, session_id) in keychain.entries
        finally:
            key[:] = b"\x00" * len(key)

    def test_revocation_deletes_both_halves(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        path, session_id = _write_schema_2_receipt(sign_in, keychain)

        receipt.delete_profile_session(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)

        assert not path.exists()
        assert _account(sign_in.binding.profile_id, session_id) not in keychain.entries

    def test_runtime_supplied_key_reader_retires_a_legacy_receipt(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        path, session_id = _write_schema_2_receipt(sign_in, keychain)

        outcome, dek = receipt.resume_profile_session_with_key(
            storage_root=sign_in.root,
            profile_id=sign_in.binding.profile_id,
            custody_generation=sign_in.binding.custody_generation,
            dek_epoch=_EPOCH,
            now=_NOW + timedelta(minutes=1),
            receipt_key=bytearray(32),
            login_id=RECEIPT_LOGIN_ID,
            sign_in=sign_in,
        )

        assert outcome.refusal is ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH and dek is None
        assert not path.exists()
        assert _account(sign_in.binding.profile_id, session_id) not in keychain.entries
        assert outcome.deletion is receipt.ReceiptDeletion.DELETED

    def test_upgrade_mint_replaces_a_live_schema_2_receipt(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        path, old_session = _write_schema_2_receipt(sign_in, keychain)

        record = _mint(sign_in)

        assert json.loads(path.read_bytes())["schema_version"] == 3
        assert _account(sign_in.binding.profile_id, old_session) not in keychain.entries
        assert not receipt._profile_session_retirement_path(
            storage_root=sign_in.root, profile_id=sign_in.binding.profile_id
        ).exists()
        outcome = _resume(sign_in)
        assert outcome.resumed and outcome.record == record


class TestBindingVerification:
    """The verification door refuses and deletes every receipt that is not bound."""

    def test_bound_receipt_is_kept(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        record = _mint(sign_in)

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.BOUND
        assert check.deletion is binding_probe.ReceiptDeletion.NOT_REQUIRED
        assert check.record == record
        assert _path(sign_in).exists()

    def test_absent_receipt_needs_no_deletion(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.ABSENT
        assert check.deletion is binding_probe.ReceiptDeletion.NOT_REQUIRED

    def test_another_login_is_refused_and_deleted(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        record = _mint(sign_in)

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=OTHER_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.LOGIN_MISMATCH
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert not _path(sign_in).exists()
        assert _account(record.profile_id, record.session_id) not in keychain.entries

    def test_an_advanced_generation_is_refused_and_deleted(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        record = _mint(sign_in)
        sign_in.advance()

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.GENERATION_CHANGED
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert not _path(sign_in).exists()
        assert _account(record.profile_id, record.session_id) not in keychain.entries

    def test_a_missing_generation_record_is_refused_and_deleted(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        _mint(sign_in)
        sign_in.path.unlink()

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.GENERATION_MISSING
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert not _path(sign_in).exists()
        assert sign_in.observe().state is SignInGenerationState.MISSING, "verification never recreates the fence"

    def test_an_unreadable_generation_record_is_refused_and_deleted(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        _mint(sign_in)
        sign_in.path.write_bytes(b"{not a generation record")

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.GENERATION_UNREADABLE
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert not _path(sign_in).exists()

    def test_an_older_schema_is_refused_and_deleted(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        sign_in.establish()
        path, session_id = _write_schema_2_receipt(sign_in, keychain)

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.SCHEMA_VERSION_MISMATCH
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert check.record is None
        assert not path.exists()
        assert _account(sign_in.binding.profile_id, session_id) not in keychain.entries

    def test_malformed_bytes_are_refused_and_cleared(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        sign_in.establish()
        path = _path(sign_in)
        ensure_profile_custody_local_directory(path.parent.parent)
        ensure_profile_custody_local_directory(path.parent)
        path.write_bytes(b"[]")

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=RECEIPT_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.MALFORMED
        assert check.deletion is binding_probe.ReceiptDeletion.DELETED
        assert not path.exists()

    def test_an_unavailable_keychain_still_clears_the_disk_half_and_says_so(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        record = _mint(sign_in)
        keychain.unavailable = True

        check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=OTHER_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.LOGIN_MISMATCH
        assert check.deletion is binding_probe.ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED
        assert not _path(sign_in).exists()
        assert _account(record.profile_id, record.session_id) in keychain.entries

    def test_a_receipt_that_survives_its_clear_is_reported(
        self, sign_in: SignInGenerationCustody, keychain: _Keyring
    ) -> None:
        _mint(sign_in)
        with _path(sign_in).open("rb"):
            check = binding_probe.verify_profile_session_binding(sign_in=sign_in, login_id=OTHER_LOGIN_ID)

        assert check.verdict is binding_probe.ReceiptBindingVerdict.LOGIN_MISMATCH
        if _path(sign_in).exists():
            assert check.deletion is binding_probe.ReceiptDeletion.RECEIPT_RETAINED
        else:
            # POSIX removes a file another handle holds open.
            assert check.deletion is binding_probe.ReceiptDeletion.DELETED


class TestBindingClassifier:
    """The pure decision, for callers that observe the generation themselves."""

    @staticmethod
    def _record(sign_in: SignInGenerationCustody) -> PersistedProfileSession:
        return _mint(sign_in)

    def test_each_refusal_is_distinct(self, sign_in: SignInGenerationCustody, keychain: _Keyring) -> None:
        record = self._record(sign_in)
        current = sign_in.observe()
        profile = record.profile_id

        def classify(
            *, profile_id: UUID = profile, login_id: str = RECEIPT_LOGIN_ID, generation: SignInGenerationObservation
        ) -> binding_probe.ReceiptBindingVerdict:
            return binding_probe.classify_profile_session_binding(
                record=record, profile_id=profile_id, login_id=login_id, generation=generation
            )

        verdict = binding_probe.ReceiptBindingVerdict
        assert classify(generation=current) is verdict.BOUND
        assert classify(profile_id=uuid4(), generation=current) is verdict.PROFILE_MISMATCH
        assert classify(login_id=OTHER_LOGIN_ID, generation=current) is verdict.LOGIN_MISMATCH
        assert classify(login_id="", generation=current) is verdict.LOGIN_MISMATCH
        for state, expected in (
            (SignInGenerationState.MISSING, verdict.GENERATION_MISSING),
            (SignInGenerationState.UNREADABLE, verdict.GENERATION_UNREADABLE),
            (SignInGenerationState.BINDING_MISMATCH, verdict.GENERATION_BINDING_MISMATCH),
        ):
            assert classify(generation=SignInGenerationObservation(state=state)) is expected
        assert current.current is not None
        later = SignInGenerationObservation(
            state=SignInGenerationState.PRESENT,
            current=SignInGeneration(lineage=current.current.lineage, generation=current.current.generation + 1),
        )
        assert classify(generation=later) is verdict.GENERATION_CHANGED
        assert classify(login_id=OTHER_LOGIN_ID, generation=later) is verdict.GENERATION_CHANGED

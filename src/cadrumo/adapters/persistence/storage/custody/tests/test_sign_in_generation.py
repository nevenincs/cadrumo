"""The sign-in generation record on the real filesystem against committed custody."""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ......application.storage_management.service import storage_lifecycle_permits_reclaim
from ......application.user_profile.access_contracts import ProfileAccessBinding
from ......application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ......core.config import Settings
from ......core.identity.profile import canonical_profile_bucket_id
from ......core.profile_publication import ProfilePublicationKind
from ......core.storage_taxonomy import StorageCategory, StorageNodeKind, StorageScope
from ......core.storage_taxonomy_locations import bucket_scoped_storage_path, storage_location, storage_path
from ...namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..automation_crypto import canonical_record
from ..capsule import publish_profile_custody_capsule
from ..errors import ProfileCustodyRecordError
from ..records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ..sentinel import create_profile_custody_sentinel
from ..sign_in_generation import (
    MAX_SIGN_IN_GENERATION_BYTES,
    SignInGeneration,
    SignInGenerationChange,
    SignInGenerationCustody,
    SignInGenerationObservation,
    SignInGenerationRecord,
    SignInGenerationState,
    fence_profile_sign_in_for_custody_transition,
    sign_in_generation_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("6f1c2d3e-4b5a-4c7d-8e9f-0a1b2c3d4e5f")
_EPOCH_BYTES = b"g" * 16
_DEK = bytes(range(32))


def _envelope() -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
        password_generation=1,
        dek_epoch=base64.b64encode(_EPOCH_BYTES).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )


def _binding(*, installation_id: UUID | None = None, custody_generation: int = 1) -> ProfileAccessBinding:
    return ProfileAccessBinding(
        profile_id=_PROFILE_ID,
        installation_id=installation_id or UUID("11111111-2222-4333-8444-555555555555"),
        os_owner_id="synthetic-os-owner",
        custody_generation=custody_generation,
        dek_epoch=UUID(bytes=_EPOCH_BYTES),
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A storage root holding one committed profile capsule at custody generation 1."""
    envelope = _envelope()
    publish_profile_custody_capsule(
        profile_id=_PROFILE_ID,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={"state/current.bin": b"synthetic encrypted payload"},
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    return tmp_path


def _custody(
    root: Path, *, installation_id: UUID | None = None, custody_generation: int = 1
) -> SignInGenerationCustody:
    binding = _binding(installation_id=installation_id, custody_generation=custody_generation)
    return SignInGenerationCustody(root=root, binding=binding)


def test_a_profile_that_never_signed_in_reads_missing_not_a_starting_value(root: Path) -> None:
    custody = _custody(root)
    assert not custody.path.parent.exists()

    observed = custody.observe()

    assert observed == SignInGenerationObservation(state=SignInGenerationState.MISSING)
    assert observed.current is None
    assert not custody.path.parent.exists(), "a read must not create the keystore directory"


def test_establish_creates_once_then_returns_the_same_generation(root: Path) -> None:
    custody = _custody(root)

    created = custody.establish()
    again = custody.establish()

    assert created.change is SignInGenerationChange.CREATED
    assert created.prior is SignInGenerationState.MISSING
    assert created.current.generation == 1
    assert again.change is SignInGenerationChange.UNCHANGED
    assert again.prior is SignInGenerationState.PRESENT
    assert again.current == created.current
    assert custody.observe() == SignInGenerationObservation(
        state=SignInGenerationState.PRESENT, current=created.current
    )


def test_the_record_lives_in_the_keystore_and_carries_no_secret(root: Path) -> None:
    custody = _custody(root)
    created = custody.establish().current

    settings = Settings(cadrumo_local_storage_root=root)
    assert custody.path == bucket_scoped_storage_path(
        StorageCategory.KEYSTORE_SIGN_IN_GENERATION,
        canonical_profile_bucket_id(_PROFILE_ID),
        settings=settings,
    )
    assert not custody.path.is_relative_to(storage_path(StorageCategory.BUCKETS, settings=settings))
    stored = json.loads(custody.path.read_bytes())
    assert set(stored) == {"schema_version", "binding", "current"}
    assert stored["current"] == {"lineage": str(created.lineage), "generation": 1}
    assert set(stored["binding"]) == set(ProfileAccessBinding.model_fields)


def test_advance_keeps_the_lineage_and_is_durable_before_it_returns(root: Path) -> None:
    custody = _custody(root)
    first = custody.establish().current

    advanced = custody.advance()
    advanced_again = custody.advance()

    assert advanced.change is SignInGenerationChange.ADVANCED
    assert advanced.current == SignInGeneration(lineage=first.lineage, generation=2)
    assert advanced_again.current == SignInGeneration(lineage=first.lineage, generation=3)
    # A fresh owner, as after a runtime restart, observes the published value.
    assert _custody(root).observe().current == advanced_again.current
    # Publication is atomic: no staging leaf survives beside the record.
    assert [path.name for path in custody.path.parent.iterdir()] == ["sign-in-generation.json"]


def test_advance_without_a_record_starts_a_lineage(root: Path) -> None:
    custody = _custody(root)

    write = custody.advance()

    assert write.change is SignInGenerationChange.CREATED
    assert write.prior is SignInGenerationState.MISSING
    assert write.current.generation == 1
    assert custody.observe().current == write.current


def test_a_deleted_record_is_never_resurrected_at_an_issued_generation(root: Path) -> None:
    custody = _custody(root)
    custody.establish()
    revoked = custody.advance().current
    issued = {custody.establish().current, revoked}

    custody.path.unlink()

    assert custody.observe().state is SignInGenerationState.MISSING
    recreated = custody.establish()
    assert recreated.change is SignInGenerationChange.CREATED
    assert recreated.current not in issued
    assert recreated.current.lineage != revoked.lineage
    advanced = custody.advance().current
    assert advanced.lineage == recreated.current.lineage
    assert advanced not in issued


@pytest.mark.parametrize(
    "corruption",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"{not json", id="malformed"),
        pytest.param(b"x" * (MAX_SIGN_IN_GENERATION_BYTES + 1), id="oversized"),
        pytest.param("noncanonical", id="noncanonical"),
        pytest.param("duplicate-key", id="duplicate-key"),
        pytest.param("unknown-field", id="unknown-field"),
        pytest.param("zero-generation", id="zero-generation"),
        pytest.param("future-schema", id="future-schema"),
    ],
)
def test_a_corrupt_record_reads_unreadable_and_is_replaced_by_a_fresh_lineage(
    root: Path, corruption: bytes | str
) -> None:
    custody = _custody(root)
    original = custody.establish().current
    canonical = custody.path.read_bytes()
    document = json.loads(canonical)
    match corruption:
        case "noncanonical":
            raw = json.dumps(document, indent=2).encode()
        case "duplicate-key":
            raw = canonical[:-1] + b',"current":' + json.dumps(document["current"]).encode() + b"}"
        case "unknown-field":
            raw = canonical_record_bytes({**document, "dek": "AAAA"})
        case "zero-generation":
            raw = canonical_record_bytes({**document, "current": {**document["current"], "generation": 0}})
        case "future-schema":
            raw = canonical_record_bytes({**document, "schema_version": 2})
        case bytes():
            raw = corruption
        case _:
            raise AssertionError(corruption)
    custody.path.write_bytes(raw)

    assert custody.observe() == SignInGenerationObservation(state=SignInGenerationState.UNREADABLE)
    replaced = custody.establish()
    assert replaced.change is SignInGenerationChange.REPLACED
    assert replaced.prior is SignInGenerationState.UNREADABLE
    assert replaced.current.lineage != original.lineage
    assert custody.observe().current == replaced.current


def canonical_record_bytes(document: dict[str, object]) -> bytes:
    """Serialize like the record codec does, so only the named defect differs."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_the_codec_spelling_used_above_is_the_canonical_one(root: Path) -> None:
    custody = _custody(root)
    custody.establish()
    record = SignInGenerationRecord.model_validate_json(custody.path.read_bytes())

    assert canonical_record_bytes(json.loads(custody.path.read_bytes())) == custody.path.read_bytes()
    assert canonical_record(record) == custody.path.read_bytes()


def test_a_directory_at_the_record_path_is_unreadable_and_never_missing(root: Path) -> None:
    custody = _custody(root)
    custody.path.parent.parent.mkdir()
    custody.path.parent.mkdir()
    custody.path.mkdir()

    assert custody.observe().state is SignInGenerationState.UNREADABLE
    with pytest.raises(ProfileCustodyRecordError):
        custody.advance()
    assert custody.path.is_dir()
    assert custody.observe().state is SignInGenerationState.UNREADABLE


def test_a_record_bound_to_other_custody_is_refused_and_superseded(root: Path) -> None:
    owner = _custody(root)
    owned = owner.establish().current
    other = _custody(root, installation_id=uuid4())

    assert other.observe() == SignInGenerationObservation(state=SignInGenerationState.BINDING_MISMATCH)
    superseded = other.establish()

    assert superseded.change is SignInGenerationChange.REPLACED
    assert superseded.prior is SignInGenerationState.BINDING_MISMATCH
    assert superseded.current.lineage != owned.lineage
    assert owner.observe().state is SignInGenerationState.BINDING_MISMATCH


@pytest.mark.parametrize("operation", ["establish", "advance"])
def test_a_binding_that_is_not_the_committed_custody_cannot_write(root: Path, operation: str) -> None:
    current = _custody(root)
    issued = current.establish().current
    stale = _custody(root, custody_generation=2)

    with pytest.raises(AutomationCustodyError) as refusal:
        getattr(stale, operation)()

    assert refusal.value.reason is AutomationCustodyCode.INVALID
    assert current.observe().current == issued


def test_a_relative_root_is_refused(root: Path) -> None:
    with pytest.raises(AutomationCustodyError):
        SignInGenerationCustody(root=Path("relative"), binding=_binding())


def test_concurrent_advances_serialize_under_the_custody_root_lock(root: Path) -> None:
    custody = _custody(root)
    start = custody.establish().current
    workers, rounds = 6, 5
    barrier = threading.Barrier(workers)
    results: list[SignInGeneration] = []
    failures: list[BaseException] = []
    results_lock = threading.Lock()

    def run() -> None:
        own = _custody(root)
        try:
            barrier.wait(timeout=30)
            for _ in range(rounds):
                write = own.advance()
                with results_lock:
                    results.append(write.current)
        except BaseException as exc:  # surfaced below with the thread's own failure
            with results_lock:
                failures.append(exc)

    threads = [threading.Thread(target=run) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    assert {item.lineage for item in results} == {start.lineage}
    assert sorted(item.generation for item in results) == list(range(2, 2 + workers * rounds))
    assert custody.observe().current == SignInGeneration(lineage=start.lineage, generation=1 + workers * rounds)


def test_the_record_is_a_protected_keystore_member_of_the_storage_taxonomy(tmp_path: Path) -> None:
    location = storage_location(StorageCategory.KEYSTORE_SIGN_IN_GENERATION)

    assert location.node_kind is StorageNodeKind.FILE
    assert location.scope is StorageScope.KEYSTORE_RELATIVE
    assert not storage_lifecycle_permits_reclaim(location.lifecycle)
    assert sign_in_generation_path(storage_root=tmp_path, profile_id=_PROFILE_ID) == bucket_scoped_storage_path(
        StorageCategory.KEYSTORE_SIGN_IN_GENERATION,
        canonical_profile_bucket_id(_PROFILE_ID),
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    declared = {definition.key: definition for definition in STORAGE_NAMESPACE_REGISTRY.paths}
    assert declared["sign_in_generation"].owner == "cadrumo.adapters.persistence.storage.custody"


def test_custody_transition_fences_a_captured_generation_without_touching_receipts(root: Path) -> None:
    custody = _custody(root)
    captured = custody.establish().current
    fence_profile_sign_in_for_custody_transition(root=root, profile_id=_PROFILE_ID)
    assert custody.observe().current == SignInGeneration(lineage=captured.lineage, generation=2)
    with pytest.raises(AutomationCustodyError):
        custody.require_current(captured)


def test_custody_transition_without_sign_in_creates_no_generation(root: Path) -> None:
    custody = _custody(root)
    fence_profile_sign_in_for_custody_transition(root=root, profile_id=_PROFILE_ID)
    assert not custody.path.parent.exists()


def test_custody_transition_refuses_unreadable_generation(root: Path) -> None:
    custody = _custody(root)
    custody.establish()
    custody.path.write_bytes(b"unreadable")
    with pytest.raises(AutomationCustodyError):
        fence_profile_sign_in_for_custody_transition(root=root, profile_id=_PROFILE_ID)
    assert custody.path.read_bytes() == b"unreadable"

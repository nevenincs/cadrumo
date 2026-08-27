"""Cold-process contract for ``aeat config profile list``.

The listing is the campaign's worked example of a read that must stay cheap:
it answers "what profiles do I have" and nothing else.  Every assertion here
runs against a real child interpreter, a real storage root, and real capsules,
because the properties under test -- what a fresh process imports, what it
writes, which storage functions it calls -- are invisible in-process.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .....adapters.persistence.storage.custody import (
    ProfileCustodyCapsuleLabel,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
    publish_profile_custody_capsule,
)
from .....core.config import Settings
from .....tests.cli_performance import (
    DIAGNOSTIC_ONLY_PATHS,
    CliPerformanceObservation,
    profile_cli_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIST_PATH = ("config", "profile", "list")
_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")

# Custody functions that authenticate, derive, publish, or repair. A pure
# listing may call none of them; each is named by its own qualified name so a
# rename surfaces here rather than silently emptying the guard.
_FORBIDDEN_STORAGE_CALL_MARKERS = (
    "unlock_profile_custody",
    "load_committed_profile_password_material",
    "verify_profile_custody_sentinel",
    "publish_initial",
    "recover_pending",
    "ProfileLabelHeadRepository",
    "unwrap",
    "derive",
    "mint_profile_session",
    "resume_profile_session",
)


def _publish(root: Path, profile_id: UUID, label: str) -> None:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=_EPOCH,
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
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind="enroll",
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={
            "profile-label.v1.json": ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label=label,
            ).canonical_json_bytes()
        },
        settings=Settings(cadrumo_local_storage_root=root),
    )


def _storage_state(paths: tuple[str, ...]) -> list[str]:
    return sorted(path for path in paths if path not in DIAGNOSTIC_ONLY_PATHS)


def _assert_created_no_state(observation: CliPerformanceObservation) -> None:
    assert observation.failure_kind == "none", observation.stderr
    assert observation.exit_code == 0, observation.stderr
    assert _storage_state(observation.filesystem_created) == [], observation.filesystem_created
    assert _storage_state(observation.filesystem_modified) == [], observation.filesystem_modified
    assert _storage_state(observation.filesystem_deleted) == [], observation.filesystem_deleted


def _forbidden_calls(observation: CliPerformanceObservation) -> list[str]:
    return sorted(
        call
        for call in observation.storage_operation_calls
        if any(marker in call for marker in _FORBIDDEN_STORAGE_CALL_MARKERS)
    )


@pytest.fixture
def populated_root(tmp_path: Path) -> Path:
    root = tmp_path / "populated"
    root.mkdir()
    _publish(root, UUID("11111111-1111-4111-8111-111111111111"), "Alpha")
    _publish(root, UUID("22222222-2222-4222-8222-222222222222"), "Beta")
    return root


def test_listing_an_empty_store_creates_no_state_at_all(tmp_path: Path) -> None:
    """A first-run listing must not materialize the storage tree it reports on."""
    root = tmp_path / "empty"
    profile = profile_cli_path(_LIST_PATH, storage_root=root)

    _assert_created_no_state(profile.invocation)
    assert "profiles\t<none>" in profile.invocation.stdout


def test_listing_a_populated_store_reads_without_writing_anything(populated_root: Path) -> None:
    """Listing real capsules must leave every byte of the store untouched."""
    before = _storage_state(tuple(path.relative_to(populated_root).as_posix() for path in populated_root.rglob("*")))
    profile = profile_cli_path(_LIST_PATH, storage_root=populated_root)
    after = _storage_state(tuple(path.relative_to(populated_root).as_posix() for path in populated_root.rglob("*")))

    _assert_created_no_state(profile.invocation)
    assert before == after
    assert "Alpha" in profile.invocation.stdout
    assert "Beta" in profile.invocation.stdout


def test_listing_never_enters_custody_authentication_publication_or_repair(populated_root: Path) -> None:
    """The listing must reach no unlock, key-derivation, session, or head-publish path."""
    profile = profile_cli_path(_LIST_PATH, storage_root=populated_root)

    assert _forbidden_calls(profile.invocation) == []
    assert _forbidden_calls(profile.resolution) == []


def test_resolving_the_listing_path_loads_no_registry_crypto_or_keyring_family(populated_root: Path) -> None:
    """Merely resolving the leaf must not pay for capabilities it never uses."""
    resolution = profile_cli_path(_LIST_PATH, storage_root=populated_root).resolution

    for family in ("registry", "crypto", "keyring"):
        assert resolution.import_families[family] == (), (family, resolution.import_families[family])


def test_listing_does_not_import_the_authenticated_profile_aggregate(populated_root: Path) -> None:
    """The heavy aggregate is the exact cost this leaf was rebuilt to stop paying."""
    invocation = profile_cli_path(_LIST_PATH, storage_root=populated_root).invocation

    aggregate_modules = sorted(
        module
        for module in invocation.imported_modules
        if module.endswith(
            (
                ".user_profile.profile_repository",
                ".user_profile.custody_service",
                ".user_profile.recovery_custody",
                ".user_profile.passphrase_rotation",
            )
        )
    )

    assert aggregate_modules == [], aggregate_modules


def test_listing_cost_does_not_scale_with_the_number_of_profiles(tmp_path: Path) -> None:
    """Per-profile work must stay two bounded reads, not a per-profile custody entry.

    Scaling is asserted on the storage-call count rather than on wall time,
    because a latency comparison on a shared runner measures the runner. A
    listing that re-entered custody per profile would show call growth far
    steeper than the linear two-reads-per-capsule this boundary promises.
    """
    small = tmp_path / "small"
    large = tmp_path / "large"
    small.mkdir()
    large.mkdir()
    _publish(small, UUID("31111111-1111-4111-8111-111111111111"), "Only")
    for index in range(8):
        _publish(large, UUID(f"4{index}111111-1111-4111-8111-111111111111"), f"Profile {index}")

    small_calls = sum(profile_cli_path(_LIST_PATH, storage_root=small).invocation.storage_operation_calls.values())
    large_calls = sum(profile_cli_path(_LIST_PATH, storage_root=large).invocation.storage_operation_calls.values())

    assert large_calls > small_calls
    assert large_calls < small_calls * 8, (small_calls, large_calls)

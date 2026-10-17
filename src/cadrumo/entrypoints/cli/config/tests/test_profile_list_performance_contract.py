"""Cold-process contract for ``aeat config profile list``.

The listing is the campaign's worked example of a read that must stay cheap:
it answers "what profiles do I have" and nothing else.  Every assertion here
runs against a real child interpreter, a real storage root, and real capsules,
because the properties under test -- what a fresh process imports, what it
writes, which storage functions it calls -- are invisible in-process.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .....adapters.persistence.storage.custody.capsule import publish_profile_custody_capsule
from .....adapters.persistence.storage.custody.capsule_records import ProfileCustodyCapsuleLabel
from .....adapters.persistence.storage.custody.records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from .....adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from .....core.config import Settings
from .....core.profile_publication import ProfilePublicationKind
from ...tests.cli_performance import (
    CliPerformanceObservation,
    CliPerformanceProfile,
    is_non_authoritative_artifact,
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
        publication_kind=ProfilePublicationKind.ENROLL,
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
    return sorted(path for path in paths if not is_non_authoritative_artifact(path))


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


def _root_state(root: Path) -> list[str]:
    return _storage_state(tuple(path.relative_to(root).as_posix() for path in root.rglob("*")))


@dataclass(frozen=True, slots=True)
class _PopulatedListing:
    profile: CliPerformanceProfile
    state_before: list[str]
    state_after: list[str]


@pytest.fixture(scope="module")
def populated_listing(tmp_path_factory: pytest.TempPathFactory) -> _PopulatedListing:
    """One cold profile of the listing over real capsules, shared by the read-only assertions.

    Every consumer only inspects the observation, and each observation already
    comes from its own fresh interpreter, so profiling the same argv against the
    same starting store once per test repeated two child processes per test
    without observing anything new.
    """
    root = tmp_path_factory.mktemp("profile-list") / "populated"
    root.mkdir()
    _publish(root, UUID("11111111-1111-4111-8111-111111111111"), "Alpha")
    _publish(root, UUID("22222222-2222-4222-8222-222222222222"), "Beta")
    state_before = _root_state(root)
    profile = profile_cli_path(_LIST_PATH, storage_root=root)
    return _PopulatedListing(profile=profile, state_before=state_before, state_after=_root_state(root))


def test_listing_an_empty_store_creates_no_state_at_all(tmp_path: Path) -> None:
    """A first-run listing must not materialize the storage tree it reports on."""
    root = tmp_path / "empty"
    profile = profile_cli_path(_LIST_PATH, storage_root=root)

    _assert_created_no_state(profile.invocation)
    assert "profiles\t<none>" in profile.invocation.stdout


def test_listing_a_populated_store_reads_without_writing_anything(populated_listing: _PopulatedListing) -> None:
    """Listing real capsules must leave every byte of the store untouched."""
    profile = populated_listing.profile

    _assert_created_no_state(profile.invocation)
    assert populated_listing.state_before == populated_listing.state_after
    assert "Alpha" in profile.invocation.stdout
    assert "Beta" in profile.invocation.stdout


def test_listing_never_enters_custody_authentication_publication_or_repair(
    populated_listing: _PopulatedListing,
) -> None:
    """The listing must reach no unlock, key-derivation, session, or head-publish path."""
    profile = populated_listing.profile

    assert _forbidden_calls(profile.invocation) == []
    assert _forbidden_calls(profile.resolution) == []


def test_resolving_the_listing_path_loads_no_registry_crypto_or_keyring_family(
    populated_listing: _PopulatedListing,
) -> None:
    """Merely resolving the leaf must not pay for capabilities it never uses."""
    resolution = populated_listing.profile.resolution

    for family in ("registry", "crypto", "keyring"):
        assert resolution.import_families[family] == (), (family, resolution.import_families[family])


def test_listing_does_not_import_the_authenticated_profile_aggregate(populated_listing: _PopulatedListing) -> None:
    """The heavy aggregate is the exact cost this leaf was rebuilt to stop paying."""
    invocation = populated_listing.profile.invocation

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

"""Runtime identity contract for the custody path builder.

The builder turns a profile identity into a filesystem name, so its ``UUID``
annotation is a claim about callers, not a runtime bound. These tests exercise
the bound itself in both directions: what must refuse, and what must keep
working. A validator that refused a real profile identifier would break custody
outright, so the acceptance direction is as load-bearing as the refusal one.

Most refusal cases address :func:`profile_custody_directory_name` directly.
That primitive declares its parameter as ``object`` precisely because it does
not trust its input, so a wrong-typed argument needs no checker suppression --
the same shape the wipe primitive takes. The suppressed cases below exist to
prove the refusal also stands at the composed builder, which is the function
that produces a real filesystem path.
"""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid1, uuid3, uuid4, uuid5

import pytest

from ......core import StorageCategory
from ...errors import PathContainmentError
from ..capsule_discovery import _canonical_profile_id
from ..paths import profile_custody_directory_name, profile_custody_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


# Real bucket-identity sentinels minted elsewhere in the system. A bucket
# identity is a plain string whose accepted set is wider than "profile UUID",
# so these are the values that would actually be in flight if one ever reached
# this boundary.
_SYSTEM_SENTINELS = ("system", "__unbound_session__")

_RELATIVE_PATH_TOKENS = (".", "..", "../../escape", "..\\..\\escape", "buckets/nested")

_NON_CANONICAL_UUID_SPELLINGS = (
    "AEF86776-E8B4-4CD2-8C1B-F96099261AD6",
    "{ac63571e-4135-4723-8535-f7ac7bbbc03c}",
    "2691dda2224b48b5bdf4b6a8685d7c6a",
    "urn:uuid:2691dda2-224b-48b5-bdf4-b6a8685d7c6a",
)

_WRONG_TYPES: tuple[object, ...] = ("", None, 42, b"2691dda2-224b-48b5-bdf4-b6a8685d7c6a")


def _mintable_profile_ids() -> tuple[UUID, ...]:
    """Every ``UUID`` the profile aggregate actually mints.

    The aggregate mints version 4 exclusively (``new_profile_id`` and the
    capsule lifecycle both call :func:`uuid.uuid4`), and ``ProfileId``
    constrains the persisted spelling to that version. Enumerating other UUID
    versions here would assert an acceptance the identity boundary is
    deliberately narrower than; those shapes are exercised as refusals below.
    """
    return (
        uuid4(),
        # Constructed from non-canonical input: the boundary must judge the
        # value, not the spelling it arrived in.
        UUID("AEF86776-E8B4-4CD2-8C1B-F96099261AD6"),
        UUID("{ac63571e-4135-4723-8535-f7ac7bbbc03c}"),
        UUID("2691dda2224b48b5bdf4b6a8685d7c6a"),
    )


def _unmintable_profile_ids() -> tuple[UUID, ...]:
    """``UUID`` values that parse but are not profile identities.

    A profile identity is a version-4 UUID. Every other version, plus the nil
    and max sentinels, is a value no minting path in this system produces, so
    the boundary must refuse it rather than publish a capsule under a name the
    anchored discoverer would not recognise.
    """
    return (
        uuid1(),
        uuid3(NAMESPACE_DNS, "cadrumo"),
        uuid5(NAMESPACE_DNS, "cadrumo"),
        UUID(int=0),
        UUID(int=(1 << 128) - 1),
    )


class TestRefusedIdentifiers:
    """Nothing but a ``UUID`` may become a custody directory name."""

    @pytest.mark.parametrize("sentinel", _SYSTEM_SENTINELS)
    def test_system_sentinels_refuse(self, sentinel: str) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(sentinel)

    @pytest.mark.parametrize("token", _RELATIVE_PATH_TOKENS)
    def test_relative_path_tokens_refuse(self, token: str) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(token)

    @pytest.mark.parametrize("spelling", _NON_CANONICAL_UUID_SPELLINGS)
    def test_non_canonical_uuid_strings_refuse(self, spelling: str) -> None:
        """A string that merely parses as a UUID is still not a profile identity.

        Accepting one would publish a capsule under a name the anchored
        discoverer rejects, leaving real custody material invisible.
        """
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(spelling)

    @pytest.mark.parametrize("value", _WRONG_TYPES)
    def test_wrong_typed_identifiers_refuse(self, value: object) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(value)

    @pytest.mark.parametrize("profile_id", _unmintable_profile_ids())
    def test_non_version_4_uuids_refuse(self, profile_id: UUID) -> None:
        """A UUID of a version no minting path produces is not an identity.

        The refusal arrives as the boundary's own documented error class, not
        as the bare ``ValueError`` the identity helper raises: a caller
        translating custody refusals must not have to catch two classes to
        cover one boundary.
        """
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(profile_id)

    def test_canonical_uuid_string_refuses(self) -> None:
        """Even the canonical rendering refuses: the type is the contract."""
        with pytest.raises(PathContainmentError):
            profile_custody_directory_name(str(uuid4()))


class TestRefusalStandsAtTheComposedBuilder:
    """The refusal must hold at the function that yields a real path."""

    @pytest.mark.parametrize(
        "candidate",
        ["system", "..", "../../escape", "", "2691dda2-224b-48b5-bdf4-b6a8685d7c6a"],
    )
    def test_builder_refuses(self, candidate: str, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                candidate,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: passing the wrong type IS the refusal under test
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    def test_refusal_creates_nothing(self, tmp_path: Path) -> None:
        for candidate in (*_SYSTEM_SENTINELS, *_RELATIVE_PATH_TOKENS, ""):
            with pytest.raises(PathContainmentError):
                profile_custody_path(
                    candidate,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: passing the wrong type IS the refusal under test
                    StorageCategory.PROFILE_CAPSULE_COMMIT,
                    root=tmp_path,
                )
        assert list(tmp_path.rglob("*")) == []


class TestAcceptedIdentifiers:
    """Every identifier the system mints must still build its capsule path."""

    @pytest.mark.parametrize("profile_id", _mintable_profile_ids())
    def test_mintable_uuid_builds_canonical_directory(self, profile_id: UUID, tmp_path: Path) -> None:
        built = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=tmp_path)
        assert built.parent.name == str(profile_id)

    @pytest.mark.parametrize("profile_id", _mintable_profile_ids())
    def test_built_name_is_recognised_by_the_discoverer(self, profile_id: UUID, tmp_path: Path) -> None:
        """The writer's name and the reader's recognition test are one rule.

        Two spellings of canonicality can disagree, and the disagreement is
        silent in the worst direction: a published capsule the discoverer
        rejects is undiscoverable while its material sits on disk.
        """
        built = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=tmp_path)
        assert _canonical_profile_id(built.parent.name) == profile_id

    @pytest.mark.parametrize("profile_id", _mintable_profile_ids())
    def test_directory_name_helper_agrees_with_the_builder(self, profile_id: UUID, tmp_path: Path) -> None:
        built = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=tmp_path)
        assert profile_custody_directory_name(profile_id) == built.parent.name

    @pytest.mark.parametrize("candidate", [*_SYSTEM_SENTINELS, *_NON_CANONICAL_UUID_SPELLINGS])
    def test_discoverer_rejects_names_the_builder_cannot_emit(self, candidate: str) -> None:
        assert _canonical_profile_id(candidate) is None

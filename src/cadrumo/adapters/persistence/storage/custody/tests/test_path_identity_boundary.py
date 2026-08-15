"""Runtime identity contract for the custody path builder.

The builder turns a profile identity into a filesystem name, so its
``UUID`` annotation is a claim about callers, not a runtime bound. These
tests exercise the bound itself in both directions: what must refuse, and
what must keep working. A validator that refused a real profile identifier
would break custody outright, so the acceptance direction is as load-bearing
as the refusal direction.
"""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid1, uuid3, uuid4, uuid5

import pytest

from ......core import StorageCategory
from ...errors import PathContainmentError
from .. import profile_custody_path
from .._capsule_discovery import _canonical_profile_id
from .._paths import profile_custody_directory_name

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


def _mintable_profile_ids() -> tuple[UUID, ...]:
    """Every shape of ``UUID`` the system can put in front of this boundary."""
    return (
        uuid4(),
        uuid1(),
        uuid3(NAMESPACE_DNS, "cadrumo"),
        uuid5(NAMESPACE_DNS, "cadrumo"),
        UUID(int=0),
        UUID(int=(1 << 128) - 1),
        # Constructed from non-canonical input: the boundary must judge the
        # value, not the spelling it arrived in.
        UUID("AEF86776-E8B4-4CD2-8C1B-F96099261AD6"),
        UUID("{ac63571e-4135-4723-8535-f7ac7bbbc03c}"),
        UUID("2691dda2224b48b5bdf4b6a8685d7c6a"),
    )


class TestRefusedIdentifiers:
    """Nothing but a ``UUID`` may become a custody directory name."""

    @pytest.mark.parametrize("sentinel", _SYSTEM_SENTINELS)
    def test_system_sentinels_refuse(self, sentinel: str, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                sentinel,  # type: ignore[arg-type]
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    @pytest.mark.parametrize("token", _RELATIVE_PATH_TOKENS)
    def test_relative_path_tokens_refuse(self, token: str, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                token,  # type: ignore[arg-type]
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    @pytest.mark.parametrize("spelling", _NON_CANONICAL_UUID_SPELLINGS)
    def test_non_canonical_uuid_strings_refuse(self, spelling: str, tmp_path: Path) -> None:
        """A string that merely parses as a UUID is still not a profile identity.

        Accepting one would publish a capsule under a name the anchored
        discoverer rejects, leaving real custody material invisible.
        """
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                spelling,  # type: ignore[arg-type]
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    @pytest.mark.parametrize("value", ["", None, 42, b"2691dda2-224b-48b5-bdf4-b6a8685d7c6a"])
    def test_wrong_typed_identifiers_refuse(self, value: object, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                value,  # type: ignore[arg-type]
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    def test_canonical_uuid_string_refuses(self, tmp_path: Path) -> None:
        """Even the canonical rendering refuses: the type is the contract."""
        with pytest.raises(PathContainmentError):
            profile_custody_path(
                str(uuid4()),  # type: ignore[arg-type]
                StorageCategory.PROFILE_CAPSULE_COMMIT,
                root=tmp_path,
            )

    def test_refusal_creates_nothing(self, tmp_path: Path) -> None:
        for candidate in (*_SYSTEM_SENTINELS, *_RELATIVE_PATH_TOKENS, ""):
            with pytest.raises(PathContainmentError):
                profile_custody_path(
                    candidate,  # type: ignore[arg-type]
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

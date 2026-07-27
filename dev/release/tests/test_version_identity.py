"""Proof that the identity guard refuses on every destination, not just one.

The defect this closes was not a wrong check but a partial one: the previous
guard asked only whether a package index owned the version, and that passed on
the day it mattered because the index was the single destination that did not.
So the load-bearing assertion here is per-destination coverage -- one refusal
case for each class of owner -- plus the proof that a clean version still
passes, since a guard that refuses everything is no more useful than one that
refuses nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.release.version_identity import (
    PYPI_PROJECTS,
    VersionIdentityError,
    assert_version_available,
    manifest_floor,
    releases_owning,
    version_conflicts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Comfortably above the shipped floor and not burned, so it isolates whichever
#: single conflict a case is exercising.
_CLEAN: str = "9.9.9"


def _floor_file(tmp_path: Path, version: str) -> Path:
    path = tmp_path / ".release-please-manifest.json"
    path.write_text(json.dumps({".": version}), encoding="utf-8")
    return path


def test_a_clean_version_conflicts_with_nothing() -> None:
    """The guard must permit, or its refusals prove nothing."""
    assert version_conflicts(_CLEAN, floor="0.0.0") == ()


def test_every_pypi_project_is_covered() -> None:
    """A conflict on any one of the three refuses the whole cohort."""
    for project in PYPI_PROJECTS:
        (refusal,) = version_conflicts(_CLEAN, owning_projects=[project], floor="0.0.0")
        assert project in refusal
        assert "cannot be undone" in refusal


def test_the_tag_namespace_is_a_destination() -> None:
    """The collision the previous guard could not see."""
    (refusal,) = version_conflicts(_CLEAN, existing_tags=["v9.9.9"], floor="0.0.0")
    assert "tag namespace" in refusal
    assert "v9.9.9" in refusal


def test_a_draft_release_still_owns_its_tag() -> None:
    """Drafts count: a draft holds the tag, so creation would still fail."""
    (refusal,) = version_conflicts(_CLEAN, existing_releases=["v9.9.9"], floor="0.0.0")
    assert "release namespace" in refusal
    assert "draft" in refusal


def test_a_burned_version_is_refused_with_its_recorded_reason() -> None:
    """The operator learns why from the refusal, not from a separate lookup."""
    refusals = version_conflicts("0.2.1", floor="0.0.0")
    burned = [line for line in refusals if "burned" in line]
    assert burned, "0.2.1 was publicly downloadable and must be refused"
    assert "deleted" in burned[0], "the refusal must quote the ledger's recorded reason"


def test_the_floor_refuses_at_and_below_itself() -> None:
    """Equal is a collision too: the floor records a version already reached."""
    assert any("not above the recorded floor" in line for line in version_conflicts("0.3.0", floor="0.3.0"))
    assert any("not above the recorded floor" in line for line in version_conflicts("0.2.9", floor="0.3.0"))
    assert version_conflicts("0.3.1", floor="0.3.0") == ()


def test_the_floor_survives_deleting_the_destination_that_held_it() -> None:
    """The whole point of keying on the manifest rather than live state.

    Both burned versions sit below a 0.3.0 floor and their releases are gone, so
    only the manifest and the ledger still know those numbers were reached.
    """
    for version in ("0.2.0", "0.2.1"):
        refusals = version_conflicts(version, floor="0.3.0")
        assert any("floor" in line for line in refusals)
        assert any("burned" in line for line in refusals)


def test_every_conflict_is_reported_not_just_the_first() -> None:
    """An operator fixing one collision should not re-run to find the next."""
    refusals = version_conflicts(
        "0.2.1",
        owning_projects=list(PYPI_PROJECTS),
        existing_tags=["v0.2.1"],
        existing_releases=["v0.2.1"],
        floor="0.3.0",
    )
    # one per index (3) + tags + releases + burned + floor
    assert len(refusals) == 7
    assert sum("cannot be undone" in line for line in refusals) == 3
    # Every conflict class is represented, so none can be dropped unnoticed.
    for fragment in ("package index", "tag namespace", "release namespace", "burned", "floor"):
        assert any(fragment in line for line in refusals), f"no refusal covers {fragment}"


def test_the_shipped_manifest_floor_is_readable() -> None:
    """The real floor must parse, or the guard cannot run in production."""
    assert manifest_floor()


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        pytest.param({"other": "1.0.0"}, "records no root version", id="no-root-key"),
        pytest.param({".": ""}, "records no root version", id="blank-version"),
        pytest.param({".": 3}, "records no root version", id="non-string"),
    ],
)
def test_an_unusable_manifest_refuses_rather_than_defaulting(
    payload: dict[str, object],
    fragment: str,
    tmp_path: Path,
) -> None:
    """Defaulting the floor would silently permit a version below it."""
    path = tmp_path / ".release-please-manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VersionIdentityError, match=fragment):
        manifest_floor(path)


def test_an_absent_manifest_refuses(tmp_path: Path) -> None:
    """A missing floor is not an absent constraint."""
    with pytest.raises(VersionIdentityError, match="absent"):
        manifest_floor(tmp_path / "nope.json")


@pytest.mark.parametrize("bad", ["", "not-a-version", "1.2.3.4.5.6-"])
def test_an_unparseable_candidate_refuses(bad: str) -> None:
    """Refusing beats comparing garbage and reporting no conflict."""
    with pytest.raises(VersionIdentityError, match="not a valid version"):
        version_conflicts(bad, floor="0.0.0")


def test_assert_names_every_owner_in_one_message(tmp_path: Path) -> None:
    """The shell raises with the whole problem, not the first line of it."""
    with pytest.raises(VersionIdentityError) as excinfo:
        assert_version_available(
            "0.2.1",
            owning_projects=["cadrumo"],
            existing_tags=["v0.2.1"],
            manifest_path=_floor_file(tmp_path, "0.3.0"),
        )
    message = str(excinfo.value)
    assert "cadrumo" in message
    assert "tag namespace" in message
    assert "burned" in message
    assert "floor" in message


def test_assert_passes_a_genuinely_available_version(tmp_path: Path) -> None:
    """The permit path must work against the real reader, not only the core."""
    assert_version_available(_CLEAN, manifest_path=_floor_file(tmp_path, "0.0.0"))


_OURS: str = "aaaaaaaaaaaaaaaa"
_THEIRS: str = "bbbbbbbbbbbbbbbb"


def test_our_own_prior_release_is_exempted_so_a_redispatch_converges() -> None:
    """Ordering the upload last only helps if re-dispatch is actually possible.

    A re-dispatch after a mid-run failure finds the release IT created. Refusing
    that would make the recovery path unreachable and the ordering pointless.
    """
    entries = [f"v{_CLEAN} {_OURS}"]
    assert releases_owning(entries, _CLEAN, own_source_commit=_OURS) == ()
    # Without the exemption the same row is an owner, which is what makes the
    # exemption load-bearing rather than incidental.
    assert releases_owning(entries, _CLEAN) == (f"v{_CLEAN}",)


def test_a_release_on_another_commit_is_never_exempted() -> None:
    """The exemption is identity, not a bypass: it cannot launder a stranger."""
    entries = [f"v{_CLEAN} {_THEIRS}"]
    assert releases_owning(entries, _CLEAN, own_source_commit=_OURS) == (f"v{_CLEAN}",)


def test_the_exemption_is_per_row_not_per_version() -> None:
    """Ours and a stranger's can both carry the tag; only ours is exempt."""
    entries = [f"v{_CLEAN} {_OURS}", f"v{_CLEAN} {_THEIRS}"]
    assert releases_owning(entries, _CLEAN, own_source_commit=_OURS) == (f"v{_CLEAN}",)


def test_unrelated_versions_are_ignored_entirely() -> None:
    """A different version's release is not this version's collision."""
    assert releases_owning([f"v0.4.0 {_THEIRS}"], _CLEAN, own_source_commit=_OURS) == ()

"""Proof that each gate refuses what it must and permits what it must.

Two failures are being held off at once, and they pull in opposite directions.

A guard that refuses too little is how a version some destination already owned
reached an irreversible upload: the previous guard asked only whether a package
index owned the version, and that passed on the day it mattered because the
index was the single destination that did not. So every destination keeps a
refusal case here.

A guard that refuses too much is how the cohort lane stopped building at all:
the collision rules were applied to a build that uploads nothing, so every push
after a release was refused for a collision it could not cause. So every rule
also keeps a case proving what it must let through.

That is why the gate cases below always come in pairs. A rule is only proved by
both directions; either one alone is satisfied by a gate stuck open or stuck
shut.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..version_identity import (
    GATES,
    PUBLISH,
    PYPI_PROJECTS,
    SEAL,
    Gate,
    VersionIdentityError,
    assert_gate_permits,
    forge_arguments,
    gate_conflicts,
    main,
    manifest_floor,
    refs_owning,
    version_conflicts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Comfortably above the shipped floor and not burned, so it isolates whichever
#: single conflict a case is exercising.
_CLEAN: str = "9.9.9"

#: A version this project published and then deleted, recorded in the ledger.
_BURNED: str = "0.2.1"


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


def test_every_refusal_tells_the_operator_what_to_do() -> None:
    """A refusal an operator cannot act on sends them to read the source."""
    refusals = version_conflicts(
        _BURNED,
        owning_projects=list(PYPI_PROJECTS),
        existing_tags=[f"v{_BURNED}"],
        existing_releases=[f"v{_BURNED}"],
    )
    assert refusals
    for refusal in refusals:
        assert "cut a new version" in refusal or "burned" in refusal, refusal


def test_a_burned_version_is_refused_with_its_recorded_reason() -> None:
    """The operator learns why from the refusal, not from a separate lookup."""
    refusals = version_conflicts(_BURNED, floor="0.0.0")
    burned = [line for line in refusals if "burned" in line]
    assert burned, f"{_BURNED} was publicly downloadable and must be refused"
    assert "deleted" in burned[0], "the refusal must quote the ledger's recorded reason"


def test_the_floor_refuses_below_itself_and_permits_equality() -> None:
    """The floor is a regression bound, not a monotonicity one.

    Equality was once a refusal, on the reading that the floor records a version
    already reached. That reading made the rule unsatisfiable: release-please
    writes the manifest and the declared version together, so the floor equals
    the candidate at every commit a gate can observe, and refusing equality
    refused every release. What remains is the case the tool cannot catch --
    a version edited to sit BELOW what already shipped.
    """
    assert any("below the recorded floor" in line for line in version_conflicts("0.2.9", floor="0.3.0"))
    assert version_conflicts("0.3.0", floor="0.3.0") == ()
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
        _BURNED,
        owning_projects=list(PYPI_PROJECTS),
        existing_tags=[f"v{_BURNED}"],
        existing_releases=[f"v{_BURNED}"],
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


def test_assert_names_every_owner_in_one_message() -> None:
    """The shell raises with the whole problem, not the first line of it."""
    with pytest.raises(VersionIdentityError) as excinfo:
        assert_gate_permits(
            PUBLISH,
            _BURNED,
            owning_projects=["cadrumo"],
            existing_tags=[f"v{_BURNED}"],
        )
    message = str(excinfo.value)
    assert "cadrumo" in message
    assert "tag namespace" in message
    assert "burned" in message
    assert "publish" in message


def test_assert_passes_a_genuinely_available_version() -> None:
    """The permit path must work through the shell, not only the core."""
    assert_gate_permits(PUBLISH, _CLEAN)


_OURS: str = "aaaaaaaaaaaaaaaa"
_THEIRS: str = "bbbbbbbbbbbbbbbb"


def test_our_own_ref_is_exempted_so_the_run_it_belongs_to_can_proceed() -> None:
    """The tag and release being published exist by the time the guard runs.

    They were cut by the release that dispatched this run, from this commit.
    Refusing them would refuse every release for colliding with itself.
    """
    entries = [f"v{_CLEAN} {_OURS}"]
    assert refs_owning(entries, _CLEAN, own_source_commit=_OURS) == ()
    # Without the exemption the same row is an owner, which is what makes the
    # exemption load-bearing rather than incidental.
    assert refs_owning(entries, _CLEAN) == (f"v{_CLEAN}",)


def test_a_ref_on_another_commit_is_never_exempted() -> None:
    """The exemption is identity, not a bypass: it cannot launder a stranger."""
    entries = [f"v{_CLEAN} {_THEIRS}"]
    assert refs_owning(entries, _CLEAN, own_source_commit=_OURS) == (f"v{_CLEAN}",)


def test_the_exemption_is_per_row_not_per_version() -> None:
    """Ours and a stranger's can both carry the tag; only ours is exempt."""
    entries = [f"v{_CLEAN} {_OURS}", f"v{_CLEAN} {_THEIRS}"]
    assert refs_owning(entries, _CLEAN, own_source_commit=_OURS) == (f"v{_CLEAN}",)


def test_unrelated_versions_are_ignored_entirely() -> None:
    """A different version's ref is not this version's collision."""
    assert refs_owning([f"v0.4.0 {_THEIRS}"], _CLEAN, own_source_commit=_OURS) == ()


def test_one_identity_rule_serves_both_forge_namespaces() -> None:
    """Tags and releases are exempted by the same rule, not two of them.

    A tag row carries the commit it points at and a release row the commit it
    targets, so one rule reads both. Two rules is how one namespace kept an
    exemption the other never got.
    """
    tag_row = f"v{_CLEAN} {_OURS}"
    release_row = f"v{_CLEAN} {_OURS}"
    assert refs_owning([tag_row], _CLEAN, own_source_commit=_OURS) == ()
    assert refs_owning([release_row], _CLEAN, own_source_commit=_OURS) == ()


# --- The two gates -------------------------------------------------------
#
# Each case states one observation and asserts what BOTH gates make of it, so a
# gate can be neither stuck open nor stuck shut without a case going red.

#: The exact state that stopped the cohort lane: the shipped release's version,
#: owned by all three indexes, by the tag namespace and by the release
#: namespace. Read from the manifest so the case follows the project's real
#: released version rather than freezing one.
_SHIPPED: str = manifest_floor()


def test_sealing_permits_a_version_every_destination_already_owns() -> None:
    """The case that refused every cohort build from a release until the bump.

    A seal uploads nothing. The version it stamps into an artefact is a label,
    and every collision rule states an upload as its reason, so none of them
    can bear on the build. Refusing here refused the lane's whole working
    interval.
    """
    assert (
        gate_conflicts(
            SEAL,
            _SHIPPED,
            owning_projects=PYPI_PROJECTS,
            existing_tags=[f"v{_SHIPPED}"],
            existing_releases=[f"v{_SHIPPED}"],
        )
        == ()
    )


def test_publishing_that_same_version_is_still_refused_by_every_destination() -> None:
    """The other direction of the same observation, at the gate that uploads.

    Loosening the seal is only safe because this refuses. If both directions
    were not asserted from one set of observations, a gate stuck open would
    read exactly like a gate that had been correctly relaxed.
    """
    refusals = gate_conflicts(
        PUBLISH,
        _SHIPPED,
        owning_projects=PYPI_PROJECTS,
        existing_tags=[f"v{_SHIPPED}"],
        existing_releases=[f"v{_SHIPPED}"],
    )
    # one per index (3) + tags + releases
    assert len(refusals) == 5
    for fragment in ("package index", "tag namespace", "release namespace"):
        assert any(fragment in line for line in refusals), f"no refusal covers {fragment}"


def test_publishing_is_refused_by_the_index_alone() -> None:
    """The index is the collision with no remedy, and it refuses on its own."""
    refusals = gate_conflicts(PUBLISH, _SHIPPED, owning_projects=["cadrumo"])
    assert len(refusals) == 1
    assert "cannot be undone" in refusals[0]


@pytest.mark.parametrize("gate", list(GATES.values()), ids=list(GATES))
def test_a_burned_version_is_refused_at_every_gate(gate: Gate) -> None:
    """The ledger is the one rule that is not about a destination.

    A burned number must never label bytes again, whether or not those bytes
    are ever uploaded, so relaxing the seal must not relax this.
    """
    with pytest.raises(VersionIdentityError, match="burned"):
        assert_gate_permits(gate, _BURNED)


@pytest.mark.parametrize("gate", list(GATES.values()), ids=list(GATES))
def test_a_clean_version_passes_every_gate(gate: Gate) -> None:
    """A gate that refuses everything is no more useful than one that refuses nothing."""
    assert gate_conflicts(gate, _CLEAN) == ()


@pytest.mark.parametrize("gate", list(GATES.values()), ids=list(GATES))
def test_no_gate_enforces_the_manifest_floor(gate: Gate) -> None:
    """The floor equals the declared version at every commit a gate can observe.

    Release-please writes the manifest to the released version as part of the
    release change, so on the branch between releases, on the release pull
    request and at the tagged commit the upload runs from, the recorded floor
    and the declared version are the same number. Enforcing "above the floor"
    there refuses every build and every release.
    """
    assert gate_conflicts(gate, manifest_floor()) == ()


def test_the_gate_names_are_the_scope_vocabulary() -> None:
    """The CLI's choices and the gate table cannot drift apart."""
    assert set(GATES) == {"seal", "publish"}
    assert all(name == gate.name for name, gate in GATES.items())


def test_the_seal_asks_no_destination_and_publication_asks_every_one() -> None:
    """The table is the single expression of what separates the two gates."""
    assert (SEAL.checks_index, SEAL.checks_forge) == (False, False)
    assert (PUBLISH.checks_index, PUBLISH.checks_forge) == (True, True)


def test_each_gate_reports_what_it_checked() -> None:
    """A pass that overstates its reach is how a partial check went unnoticed."""
    assert SEAL.summary() == "the burned ledger"
    assert PUBLISH.summary() == (
        "the package indexes, the tag and release namespaces, the recorded floor, the burned ledger"
    )


# --- The command line ----------------------------------------------------
#
# The seal gate reaches no network, so its whole path runs here for real: no
# probe is stubbed out, because none is made.


def test_the_declared_version_seals_even_though_every_destination_owns_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End to end through the entry point, on the version that is blocked today.

    The shipped release's version is carried by all three indexes, by the tag
    namespace and by the release namespace, and the packaging lane must still
    build a cohort labelled with it on every push.
    """
    assert main(["--version", _SHIPPED, "--scope", "seal"]) == 0
    assert "available to seal" in capsys.readouterr().out


def test_sealing_a_burned_version_is_refused_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    """The seal's one rule, proved through the entry point rather than around it."""
    assert main(["--version", _BURNED, "--scope", "seal"]) == 1
    assert "REFUSED" in capsys.readouterr().err


def test_a_seal_needs_neither_repository_nor_commit() -> None:
    """It asks the forge nothing, so demanding forge arguments would be noise."""
    assert main(["--version", _CLEAN, "--scope", "seal"]) == 0


def test_publication_refuses_before_probing_when_the_repository_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An under-specified ask is an operator error, reported without a round trip."""
    assert main(["--version", _CLEAN, "--scope", "publish"]) == 1
    assert "--repository is required" in capsys.readouterr().err


def test_publication_refuses_before_probing_when_the_own_commit_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without it the run's own tag and release read as a stranger's.

    Defaulting it to absent would refuse every release moments before its
    upload, for a collision with itself, so it is demanded instead.
    """
    assert main(["--version", _CLEAN, "--scope", "publish", "--repository", "owner/name"]) == 1
    assert "--own-source-commit is required" in capsys.readouterr().err


def test_the_forge_arguments_are_returned_when_both_are_given() -> None:
    """The permit direction of the same validation."""
    assert forge_arguments("owner/name", _OURS) == ("owner/name", _OURS)


def test_the_scope_is_required_rather_than_defaulted() -> None:
    """A forgotten scope must not silently pick a gate."""
    with pytest.raises(SystemExit):
        main(["--version", _CLEAN])


def test_an_unknown_scope_is_rejected() -> None:
    """The gate table is the whole vocabulary."""
    with pytest.raises(SystemExit):
        main(["--version", _CLEAN, "--scope", "promote"])


def test_a_temporary_floor_file_is_read_from_where_it_is_pointed(tmp_path: Path) -> None:
    """The reader is a function of the path it is handed, not of a module global."""
    assert manifest_floor(_floor_file(tmp_path, "1.2.3")) == "1.2.3"


def test_publishing_below_the_recorded_floor_is_refused() -> None:
    """The one regression the release tool cannot catch for us.

    Release-please writes the manifest and the declared version together, so it
    guarantees monotonicity only for versions it computed. A version edited by
    hand to sit below what has already shipped is invisible to every other rule
    here: a number skipped on the way up was never uploaded, so it collides with
    no index, no tag and no release.
    """
    refusals = gate_conflicts(PUBLISH, "0.3.9", floor="0.4.0")

    assert len(refusals) == 1
    assert "below the recorded floor 0.4.0" in refusals[0]


def test_publishing_at_the_recorded_floor_is_permitted() -> None:
    """Equality is the NORMAL state, and refusing it would refuse every release.

    This is the direction that makes the check satisfiable at all. The tool
    writes the manifest to the version being released, so at the tagged commit
    the floor equals the candidate; a monotonic `candidate > floor` rule would
    refuse here and could never pass anywhere it was asked.
    """
    assert gate_conflicts(PUBLISH, "0.4.0", floor="0.4.0") == ()


def test_sealing_ignores_the_floor_entirely() -> None:
    """A build writes nothing, so ordering against shipped releases is not its question."""
    assert gate_conflicts(SEAL, "0.3.9", floor="0.4.0") == ()

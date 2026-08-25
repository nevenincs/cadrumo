"""Loader behaviour for the declared per-revision governance stamp.

Every test here drives the real directory loader over a real on-disk TOML tree.
The stamp is a provenance claim, so a test double anywhere in this module would
verify the double rather than the claim.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import pytest

from .....core import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from .....tests.registry_tree import bundled_registry_tree
from .. import _loader
from ..errors import RegistryLoadError
from .._loader import load_modelo_directory
from .._schema import REVISION_GOVERNANCE_FIELDS, ModeloRevision
from .._schema_base import GOVERNANCE_STAMP, governance_stamp_fields
from .._schema_governance import REVISION_REVIEW_DATE_CEILING, REVISION_REVIEW_DATE_FLOOR
from ._loader_directory_mode_support import _load_revision as _shared_load_revision
from ._loader_directory_mode_support import _write_modelo as _shared_write_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2025"
_CASILLA_FRAGMENT = """
[[revisions."2025".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()

_FULL_STAMP = """
engineered_by = "registry schema campaign"
review_status = "operator_reviewed"
reviewed_by = "operator"
reviewed_at = 2026-07-27
""".lstrip()


def _write_modelo(
    root: Path,
    *,
    manifest_extra: str = "",
    fragment_extra: str = "",
) -> Path:
    return _shared_write_modelo(
        root,
        casilla_fragment=_CASILLA_FRAGMENT,
        revision_id=_REVISION_ID,
        manifest_extra=manifest_extra,
        fragment_extra=fragment_extra,
    )


def _load_revision(modelo_dir: Path) -> ModeloRevision:
    return _shared_load_revision(modelo_dir, revision_id=_REVISION_ID)


def _revision_manifest(modelo_dir: Path) -> Path:
    return modelo_dir / "revisions" / _REVISION_ID / "revision.toml"


def test_absent_governance_block_reads_as_pending_review(tmp_path: Path) -> None:
    """A revision that declares no stamp is unreviewed, not unknown."""
    revision = _load_revision(_write_modelo(tmp_path))

    assert revision.review_status is RevisionReviewStatus.PENDING_REVIEW
    assert revision.engineered_by is None
    assert revision.reviewed_by is None
    assert revision.reviewed_at is None


def test_declared_stamp_roundtrips_through_the_real_loader(tmp_path: Path) -> None:
    """Every stamp scalar written to the manifest survives compilation."""
    revision = _load_revision(_write_modelo(tmp_path, manifest_extra=_FULL_STAMP))

    assert revision.engineered_by == "registry schema campaign"
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == "operator"
    assert revision.reviewed_at == date(2026, 7, 27)


def test_mutating_the_persisted_stamp_moves_every_loaded_field(tmp_path: Path) -> None:
    """Anti-tautology: rewrite the stamp on disk and watch each assertion flip.

    The roundtrip test above would pass just as happily against defaults baked
    into the schema. This test proves the loaded values track the bytes: it
    asserts the original stamp, rewrites every scalar on disk, reloads, and
    asserts strict inequality against each previously-passing expectation.
    """
    modelo_dir = _write_modelo(tmp_path, manifest_extra=_FULL_STAMP)
    before = _load_revision(modelo_dir)
    assert before.engineered_by == "registry schema campaign"
    assert before.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert before.reviewed_by == "operator"
    assert before.reviewed_at == date(2026, 7, 27)

    manifest = _revision_manifest(modelo_dir)
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace('engineered_by = "registry schema campaign"', 'engineered_by = "a different campaign"')
        .replace('review_status = "operator_reviewed"', 'review_status = "agent_reviewed"')
        .replace('reviewed_by = "operator"', 'reviewed_by = "agent-review"')
        .replace("reviewed_at = 2026-07-27", "reviewed_at = 2019-01-31"),
        encoding="utf-8",
    )
    after = _load_revision(modelo_dir)

    assert after.engineered_by != before.engineered_by
    assert after.review_status is not before.review_status
    assert after.reviewed_by != before.reviewed_by
    assert after.reviewed_at != before.reviewed_at
    assert after.review_status is RevisionReviewStatus.AGENT_REVIEWED
    assert after.reviewed_at == date(2019, 1, 31)


def test_deleting_the_reviewer_from_a_reviewed_stamp_turns_a_load_into_a_refusal(tmp_path: Path) -> None:
    """Anti-tautology: the same tree loads, then refuses, on one deleted line."""
    modelo_dir = _write_modelo(tmp_path, manifest_extra=_FULL_STAMP)
    assert _load_revision(modelo_dir).reviewed_by == "operator"

    manifest = _revision_manifest(modelo_dir)
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('reviewed_by = "operator"\n', ""),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="reviewed_by"):
        load_modelo_directory(modelo_dir)


@pytest.mark.parametrize(
    "stamp",
    [
        pytest.param('review_status = "operator_reviewed"\n', id="no-companions"),
        pytest.param('review_status = "agent_reviewed"\nreviewed_by = "agent-review"\n', id="no-date"),
        pytest.param('review_status = "agent_reviewed"\nreviewed_at = 2026-07-27\n', id="no-reviewer"),
    ],
)
def test_reviewed_status_without_its_companions_is_refused(tmp_path: Path, stamp: str) -> None:
    """A review nobody signed and nobody dated is an unfalsifiable claim."""
    with pytest.raises(RegistryLoadError, match="must name its reviewer"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=stamp))


@pytest.mark.parametrize(
    "stamp",
    [
        pytest.param('reviewed_by = "operator"\n', id="implicit-pending"),
        pytest.param('review_status = "pending_review"\nreviewed_at = 2026-07-27\n', id="explicit-pending"),
    ],
)
def test_pending_status_carrying_reviewer_fields_is_refused(tmp_path: Path, stamp: str) -> None:
    """A reviewer recorded against pending is a review the status denies."""
    with pytest.raises(RegistryLoadError, match="advancing review_status"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=stamp))


@pytest.mark.parametrize(
    "stamp",
    [
        pytest.param('engineered_by = ""\n', id="engineered-by-empty"),
        pytest.param('engineered_by = "   "\n', id="engineered-by-spaces"),
        pytest.param('engineered_by = "\\t"\n', id="engineered-by-tab"),
        pytest.param(
            'review_status = "operator_reviewed"\nreviewed_by = ""\nreviewed_at = 2026-07-27\n',
            id="reviewed-by-empty",
        ),
        pytest.param(
            'review_status = "operator_reviewed"\nreviewed_by = "   "\nreviewed_at = 2026-07-27\n',
            id="reviewed-by-spaces",
        ),
        pytest.param(
            'review_status = "operator_reviewed"\nreviewed_by = "\\t"\nreviewed_at = 2026-07-27\n',
            id="reviewed-by-tab",
        ),
    ],
)
def test_blank_attribution_is_refused(tmp_path: Path, stamp: str) -> None:
    """An attribution that names nobody is the claim the stamp exists to refuse.

    A present-but-blank ``reviewed_by`` carries a reviewed status past the
    companion check while naming no reviewer, which is exactly as unfalsifiable
    as the omission the companion check refuses.
    """
    with pytest.raises(RegistryLoadError, match="must name somebody"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=stamp))


def test_the_blank_refusal_is_about_emptiness_not_the_whitespace_character(tmp_path: Path) -> None:
    """Differential proof: the same padded value loads once it names somebody.

    Without this pairing the refusal above could be passing because the loader
    rejects whitespace in an attribution at all rather than an empty claim.
    """
    stamp = 'review_status = "operator_reviewed"\nreviewed_by = "  operator  "\nreviewed_at = 2026-07-27\n'

    revision = _load_revision(_write_modelo(tmp_path, manifest_extra=stamp))

    assert revision.reviewed_by == "  operator  "


def test_reviewed_at_beyond_the_signoff_horizon_is_refused(tmp_path: Path) -> None:
    """A sentinel date cannot denote a signoff any auditor could check."""
    stamp = 'review_status = "operator_reviewed"\nreviewed_by = "operator"\nreviewed_at = 3999-12-31\n'

    with pytest.raises(RegistryLoadError, match="signoff horizon"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=stamp))


def test_a_date_below_the_signoff_horizon_still_loads(tmp_path: Path) -> None:
    """Differential proof: the bound is a boundary, not a blanket date refusal.

    The horizon is a fixed calendar date rather than a reading of the local
    clock, so this assertion holds identically on every machine and in every
    year the project can plausibly run.
    """
    latest = REVISION_REVIEW_DATE_CEILING - timedelta(days=1)
    stamp = f'review_status = "operator_reviewed"\nreviewed_by = "operator"\nreviewed_at = {latest.isoformat()}\n'

    assert _load_revision(_write_modelo(tmp_path, manifest_extra=stamp)).reviewed_at == latest


def test_reviewed_at_before_the_signoff_floor_is_refused(tmp_path: Path) -> None:
    """A sentinel date from before the year 2000 cannot denote a signoff anyone can verify."""
    stamp = 'review_status = "operator_reviewed"\nreviewed_by = "operator"\nreviewed_at = 1970-01-01\n'

    with pytest.raises(RegistryLoadError, match="signoff floor"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra=stamp))


def test_a_date_at_the_signoff_floor_still_loads(tmp_path: Path) -> None:
    """Differential proof: the floor is a boundary, not a blanket refusal of older dates.

    The floor is a fixed calendar date (same rationale as the ceiling), so this
    assertion holds identically on every machine and in every year the project
    can plausibly run. A date exactly at the floor must load; one day before it
    must refuse (proven in the paired refusal test above).
    """
    at_floor = REVISION_REVIEW_DATE_FLOOR
    stamp = f'review_status = "operator_reviewed"\nreviewed_by = "operator"\nreviewed_at = {at_floor.isoformat()}\n'

    assert _load_revision(_write_modelo(tmp_path, manifest_extra=stamp)).reviewed_at == at_floor


def test_unknown_review_status_token_is_refused(tmp_path: Path) -> None:
    """The status vocabulary is closed at load time, not at a later branch."""
    with pytest.raises(RegistryLoadError, match="RevisionReviewStatus"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra='review_status = "totally_reviewed"\n'))


def test_misspelled_governance_key_is_refused(tmp_path: Path) -> None:
    """A typo must fail the load, never sit inert as an ignored key."""
    with pytest.raises(RegistryLoadError, match="reviewed_bye"):
        load_modelo_directory(_write_modelo(tmp_path, manifest_extra='reviewed_bye = "operator"\n'))


@pytest.mark.parametrize("field_name", sorted(REVISION_GOVERNANCE_FIELDS))
def test_governance_field_declared_in_a_section_fragment_is_refused(tmp_path: Path, field_name: str) -> None:
    """A stamp hidden among the fragments would be invisible to a reviewer."""
    literal = "2026-07-27" if field_name == "reviewed_at" else '"operator_reviewed"'
    fragment_extra = f'\n[revisions."{_REVISION_ID}"]\n{field_name} = {literal}\n'

    with pytest.raises(RegistryLoadError, match=re.escape("revision.toml")):
        load_modelo_directory(_write_modelo(tmp_path, fragment_extra=fragment_extra))


def test_the_fragment_refusal_is_about_placement_not_content(tmp_path: Path) -> None:
    """Differential proof: identical stamp text, manifest passes, fragment fails.

    Without this pairing the refusal test above could be passing because the
    stamp text is malformed rather than misplaced.
    """
    stamp_body = 'review_status = "agent_reviewed"\nreviewed_by = "agent-review"\nreviewed_at = 2026-07-27\n'

    accepted = _load_revision(_write_modelo(tmp_path / "manifest-home", manifest_extra=stamp_body))
    assert accepted.review_status is RevisionReviewStatus.AGENT_REVIEWED

    with pytest.raises(RegistryLoadError, match=re.escape("must be declared in the revision's revision.toml")):
        load_modelo_directory(
            _write_modelo(
                tmp_path / "fragment-home",
                fragment_extra=f'\n[revisions."{_REVISION_ID}"]\n{stamp_body}',
            ),
        )


def test_governance_field_set_names_only_real_revision_fields() -> None:
    """Anti-rot: a renamed field must not silently orphan the placement gate."""
    assert REVISION_GOVERNANCE_FIELDS
    assert set(ModeloRevision.model_fields) >= REVISION_GOVERNANCE_FIELDS


def test_governance_field_set_is_exactly_todays_declared_stamp() -> None:
    """Pin the derived set, so a marker lost in a rebase is a red test."""
    declared_today = {"engineered_by", "review_status", "reviewed_by", "reviewed_at"}

    assert declared_today == REVISION_GOVERNANCE_FIELDS


def test_the_placement_refusal_reads_the_derived_set_itself() -> None:
    """The loader gate and the declarations must be one set, not two.

    Deriving the set is worthless if the loader consults a second copy, so this
    pins the gate's input to the object the declarations produce.
    """
    assert _loader.REVISION_GOVERNANCE_FIELDS is REVISION_GOVERNANCE_FIELDS


def test_a_new_marked_field_enrols_itself_without_editing_the_field_set() -> None:
    """The addition case a hand-written list cannot catch.

    A fifth governance scalar is added to the model here carrying nothing but
    the marker. The derivation must pick it up - and an unmarked field added
    beside it must stay out, so the enrolment tracks the marker rather than
    merely counting new fields.
    """

    class _CountersignedRevision(ModeloRevision):
        countersigned_by: Annotated[str | None, GOVERNANCE_STAMP] = None
        internal_note: str | None = None

    derived = governance_stamp_fields(_CountersignedRevision)

    assert "countersigned_by" in derived
    assert derived == REVISION_GOVERNANCE_FIELDS | {"countersigned_by"}
    assert "internal_note" not in derived


def test_dropping_the_marker_drops_the_field_from_the_gate() -> None:
    """Anti-tautology: the same field, marked and unmarked, flips the assertion.

    Without this pairing the enrolment proof above could be passing because the
    derivation returns every field a subclass declares.
    """

    class _MarkedRevision(ModeloRevision):
        countersigned_by: Annotated[str | None, GOVERNANCE_STAMP] = None

    class _UnmarkedRevision(ModeloRevision):
        countersigned_by: str | None = None

    assert "countersigned_by" in governance_stamp_fields(_MarkedRevision)
    assert "countersigned_by" not in governance_stamp_fields(_UnmarkedRevision)


def test_bundled_revisions_carry_a_coherent_stamp() -> None:
    """The whole shipped tree obeys the stamp invariant, and is non-empty."""
    modelos, _catalogues = bundled_registry_tree()
    revisions = [revision for modelo in modelos for revision in modelo.revisions.values()]
    assert revisions, "the bundled registry must load at least one revision"

    for revision in revisions:
        companions = (revision.reviewed_by, revision.reviewed_at)
        assert revision.engineered_by is None or revision.engineered_by.strip(), revision.id
        if revision.review_status in REVIEWED_REVISION_REVIEW_STATUSES:
            assert all(value is not None for value in companions), revision.id
            # not-null is satisfied by a blank reviewer, which names nobody.
            assert revision.reviewed_by is not None
            assert revision.reviewed_by.strip(), revision.id
            assert revision.reviewed_at is not None
            assert revision.reviewed_at >= REVISION_REVIEW_DATE_FLOOR, revision.id
            assert revision.reviewed_at < REVISION_REVIEW_DATE_CEILING, revision.id
        else:
            assert revision.review_status is RevisionReviewStatus.PENDING_REVIEW, revision.id
            assert all(value is None for value in companions), revision.id

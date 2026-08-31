"""Deletion-preflight contract for ``BucketMaintenanceService.assess_deletion``.

Exercises the retention wiring against a real isolated storage root, a real
published profile capsule, and the real filing-retention owner: no substitute
snapshot store and no substitute floor. The preflight runs against profiles it
has NOT unlocked, so the only retention evidence available to it is the
plaintext snapshot the filing owner records at profile creation and refreshes
on every filing; these tests write that snapshot through the same recorder
production writes it with.

The subject is the three states a snapshot can be in, which are NOT three
spellings of one thing:

* a RECORDED snapshot listing no filings is an answer, and permits the erase;
* an ABSENT snapshot is nobody having been asked, and must refuse;
* a snapshot present but unreadable is the same non-answer, and must refuse.

Conflating the first two would turn every best-effort snapshot write into
permission to erase records Ley 58/2003 (LGT) arts. 66 and 70.2 require kept,
so the first two are asserted in ONE test: separated, they could quietly
converge without either failing.

Authority: ``no-silent-under-declaration`` (an absent fact is never read as a
cleared one); ``sensitive-financial-data-secure-storage-only`` (the preflight
never opens the bucket's encrypted store); ``aeat-quality-gates`` (real
adapters, both directions of the guard proven).

See Also:
    :class:`~application.bucket_maintenance.BucketMaintenanceService`
        Application facade whose deletion preflight is exercised here.
    :class:`~application.filing.FilingRetentionAuthority`
        Owner of the plaintext snapshot this preflight reads.
    :class:`~domain.retention.RetentionFloorAssessment`
        Retention position the preflight carries to the operator.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ....domain.buckets.errors import BucketDeleteRefusedError
from ....domain.modelos.filing_record import ModeloRecord
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .. import AssessBucketDeletionCommand, BucketDeletionAssessment, BucketMaintenanceService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"

#: Four whole years past this instant is still ahead of any plausible run date,
#: so the record is inside the LGT art. 66 window by law rather than by fixture.
_RETAINED_FILED_AT = datetime(2025, 7, 1, tzinfo=UTC)

#: Four whole years past this instant elapsed in 2023, so the record is outside
#: the window and may be erased.
_ELAPSED_FILED_AT = datetime(2019, 7, 1, tzinfo=UTC)


@contextmanager
def _published_profile(tmp_path: Path) -> Generator[Path]:
    """Publish one real capsule and yield the storage root holding it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        with open_test_profile_session(_PROFILE_ID):
            register_minimal_profile(
                profile_id=_PROFILE_ID,
                display_name="Alpha operator",
                overrides={"identity.tax_id": "00000000T", "identity.name": "Alpha operator"},
            )
        yield root


def _filing_record(*, filed_at: datetime, seed: str) -> ModeloRecord:
    from ....core.period import Period
    from ....domain.modelos.codes import ModeloCode
    from ....domain.modelos.filing_record import derive_filing_record_id

    work_unit_id = (seed * 64)[:64]
    revision_id = (chr(ord(seed) + 1) * 64)[:64]
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="aeat.cli.modelo.file",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_PROFILE_ID,
        modelo=ModeloCode("303"),
        filing_year=filed_at.year,
        period=Period.from_year_and_code(filed_at.year, "2T"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )


def _record_snapshot(root: Path, *records: ModeloRecord) -> None:
    from ...filing import FilingRetentionAuthority

    FilingRetentionAuthority(root=root).record_filing_catalogue(
        profile_id=UUID(_PROFILE_ID),
        records=records,
        observed_at=datetime.now(UTC),
    )


def _assess() -> BucketDeletionAssessment:
    return BucketMaintenanceService().assess_deletion(
        AssessBucketDeletionCommand(bucket_id=_PROFILE_ID),
    )


def _refusal_verdict(error: BucketDeleteRefusedError):
    """Return the typed safety refusal without a hand-authored recovery hint."""
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert error.context == {"bucket_id": _PROFILE_ID}
    assert error.translated_message == "errors.error.error_storage_bucket"
    assert str(error) == "errors.error.error_storage_bucket"
    return verdict


def _remove_snapshot(root: Path) -> None:
    """Make the filing owner's otherwise-normal empty snapshot truly absent."""
    from ...filing import FilingRetentionAuthority

    snapshot_path = FilingRetentionAuthority(root=root).path(UUID(_PROFILE_ID))
    assert snapshot_path.exists()
    snapshot_path.unlink()


def test_a_recorded_empty_snapshot_answers_while_an_absent_one_refuses(tmp_path: Path) -> None:
    """Absence and recorded-emptiness must stay two different observables.

    Asserted together on purpose. A regression that degraded absence into an
    empty assessment would leave a separated pair of tests both green, and the
    resulting fail-open erases taxpayer records nobody proved were erasable.
    """
    with _published_profile(tmp_path) as root:
        _remove_snapshot(root)
        with pytest.raises(BucketDeleteRefusedError) as refused:
            _assess()
        verdict = _refusal_verdict(refused.value)
        assert verdict.failed_condition_id == "bucket_maintenance.filing.retention_snapshot_assessable"
        assert verdict.evidence[0].values == {
            "bucket_id": _PROFILE_ID,
            "retention_snapshot_present": False,
            "retention_snapshot_readable": False,
        }

        _record_snapshot(root)

        assessment = _assess()
        assert assessment.exists is True
        assert assessment.retention is not None
        assert assessment.retention.blocks_erase is False
        assert assessment.retention.retained == ()
        assert assessment.retention.latest_safe_erase_date is None


def test_the_floor_blocks_a_recent_filing_and_clears_a_prescribed_one(tmp_path: Path) -> None:
    """Prove the guard bites in BOTH directions against one real profile.

    A guard that refuses everything is exactly as broken as one that refuses
    nothing, and refusing everything was this preflight's actual defect. The
    same profile is therefore assessed twice, once inside the LGT art. 66
    four-year window and once outside it, so a difference in verdict can only
    come from the floor.
    """
    with _published_profile(tmp_path) as root:
        _record_snapshot(root, _filing_record(filed_at=_RETAINED_FILED_AT, seed="a"))
        blocked = _assess()
        assert blocked.retention is not None
        assert blocked.retention.blocks_erase is True
        assert len(blocked.retention.retained) == 1
        assert blocked.retention.retained[0].filing_year == _RETAINED_FILED_AT.year
        assert blocked.retention.latest_safe_erase_date is not None
        assert blocked.retention.latest_safe_erase_date.year == _RETAINED_FILED_AT.year + 4

        _record_snapshot(root, _filing_record(filed_at=_ELAPSED_FILED_AT, seed="c"))
        cleared = _assess()
        assert cleared.retention is not None
        assert cleared.retention.blocks_erase is False
        assert cleared.retention.retained == ()


def test_a_snapshot_that_cannot_be_authenticated_refuses_distinctly(tmp_path: Path) -> None:
    """A present-but-unreadable snapshot is a non-answer, not a cleared one.

    Its context distinguishes it from absence because the two have different
    remedies: absence needs the owner to record, corruption needs the record
    restored. An operator told only "retention assessment required" can act on
    neither.
    """
    from ...filing import FilingRetentionAuthority

    with _published_profile(tmp_path) as root:
        _record_snapshot(root)
        snapshot_path = FilingRetentionAuthority(root=root).path(UUID(_PROFILE_ID))
        intact = snapshot_path.read_bytes()
        assert intact

        snapshot_path.write_bytes(intact.replace(b'"filing_records"', b'"filing_recordz"'))
        with pytest.raises(BucketDeleteRefusedError) as refused:
            _assess()
        verdict = _refusal_verdict(refused.value)
        assert verdict.failed_condition_id == "bucket_maintenance.filing.retention_snapshot_assessable"
        assert verdict.evidence[0].values == {
            "bucket_id": _PROFILE_ID,
            "retention_snapshot_present": True,
            "retention_snapshot_readable": False,
        }

        snapshot_path.write_bytes(intact)
        assert _assess().retention is not None


def test_a_linked_custody_target_refuses_with_its_exact_safety_verdict(tmp_path: Path) -> None:
    """The preflight must not follow a redirected capsule directory."""
    from ....adapters.persistence.storage.bucket import bucket_paths

    with _published_profile(tmp_path) as root:
        paths = bucket_paths(root, _PROFILE_ID)
        redirected = tmp_path / "redirected-capsule"
        paths.bucket_dir.rename(redirected)
        os.symlink(redirected, paths.bucket_dir, target_is_directory=True)
        try:
            with pytest.raises(BucketDeleteRefusedError) as refused:
                _assess()
            verdict = _refusal_verdict(refused.value)
            assert verdict.failed_condition_id == "bucket_maintenance.custody.target_unlinked"
            assert verdict.evidence[0].values == {
                "bucket_id": _PROFILE_ID,
                "custody_target_unlinked": False,
            }
        finally:
            paths.bucket_dir.unlink()
            redirected.rename(paths.bucket_dir)


def test_a_missing_label_projection_refuses_with_its_exact_safety_verdict(tmp_path: Path) -> None:
    """A present capsule without a committed projection is not a deletable target."""
    from ....adapters.persistence.storage.custody.paths import profile_custody_path
    from ....core.storage_taxonomy import StorageCategory

    with _published_profile(tmp_path) as root:
        commit_path = profile_custody_path(
            UUID(_PROFILE_ID),
            StorageCategory.PROFILE_CAPSULE_COMMIT,
            root=root,
        )
        commit = commit_path.read_bytes()
        commit_path.unlink()
        try:
            with pytest.raises(BucketDeleteRefusedError) as refused:
                _assess()
            verdict = _refusal_verdict(refused.value)
            assert verdict.failed_condition_id == "bucket_maintenance.custody.label_projection_present"
            assert verdict.evidence[0].values == {
                "bucket_id": _PROFILE_ID,
                "custody_record_present": False,
            }
        finally:
            commit_path.write_bytes(commit)


def test_an_unreadable_capsule_inventory_refuses_with_its_exact_safety_verdict(tmp_path: Path) -> None:
    """A linked capsule member makes the deletion fingerprint untrustworthy."""
    from ....adapters.persistence.storage.custody.paths import profile_custody_path
    from ....core.storage_taxonomy import StorageCategory

    with _published_profile(tmp_path) as root:
        _record_snapshot(root)
        capsule_path = profile_custody_path(
            UUID(_PROFILE_ID),
            StorageCategory.PROFILE_CAPSULE_COMMIT,
            root=root,
        ).parent
        external = tmp_path / "outside-capsule"
        external.write_bytes(b"outside custody")
        linked_member = capsule_path / "data" / "outside-capsule"
        os.symlink(external, linked_member)
        try:
            with pytest.raises(BucketDeleteRefusedError) as refused:
                _assess()
            verdict = _refusal_verdict(refused.value)
            assert verdict.failed_condition_id == "bucket_maintenance.custody.capsule_inventory_readable"
            assert verdict.evidence[0].values == {
                "bucket_id": _PROFILE_ID,
                "capsule_inventory_readable": False,
            }
        finally:
            linked_member.unlink()


def test_the_fingerprint_folds_the_real_capsule_and_moves_with_it(tmp_path: Path) -> None:
    """The fingerprint must track real bucket bytes, not a constant.

    A later resume compares this value to detect a target changing beneath the
    operation, so a fingerprint that did not move would make that detector
    silently blind.
    """
    from ....adapters.persistence.storage.bucket import bucket_paths

    with _published_profile(tmp_path) as root:
        _record_snapshot(root)
        before = _assess()
        assert before.fingerprint is not None
        assert before.fingerprint.file_count >= 1
        assert before.fingerprint.total_bytes > 0
        assert len(before.fingerprint.digest) == 64

        planted = bucket_paths(root, _PROFILE_ID).blobs_dir / "planted-capsule-content"
        planted.write_bytes(b"content the inventory must fold in")

        after = _assess()
        assert after.fingerprint is not None
        assert after.fingerprint.digest != before.fingerprint.digest
        assert after.fingerprint.total_bytes > before.fingerprint.total_bytes


def test_an_absent_target_is_reported_rather_than_refused(tmp_path: Path) -> None:
    """A bucket that is not on disk carries no metadata and no retention claim."""
    with _published_profile(tmp_path):
        assessment = BucketMaintenanceService().assess_deletion(
            AssessBucketDeletionCommand(bucket_id="44444444-4444-4444-8444-444444444444"),
        )
        assert assessment.exists is False
        assert assessment.label is None
        assert assessment.fingerprint is None
        assert assessment.retention is None

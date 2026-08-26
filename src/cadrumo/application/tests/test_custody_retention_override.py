"""The retention override clears the filing hold, and nothing else.

``aeat config reset start --yes --override-retention --reason "..."`` records an
operator decision to erase despite the statutory retention floor. The custody
delete transaction is the gate that actually stands in front of the destruction,
and these cases pin exactly how far that authorisation reaches.

The filing half of the custody hold IS the retention floor -- both sides compute
from one ``assess_retention_floor`` -- so an override clears it by design, and
the reset's own backstop has always let a recorded override past. The legal half
is a different fact entirely, and no operator authorisation touches it.

The negative cases carry the weight here. A change that let the override clear a
legal hold, or that let a token ride along where nothing blocks, would pass every
positive case in this file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ...tests.profile_capsule import open_test_profile_session
from ..user_profile.custody_hold_models import ProfileCustodyRetentionOverride
from .test_config_reset import (
    _OVERRIDE_REASON,
    _create_profile,
    _isolated_reset_root,
    _persist_filing,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = "31313131-3131-4131-8131-313131313131"


def _override(*, retained: int = 1) -> ProfileCustodyRetentionOverride:
    return ProfileCustodyRetentionOverride(
        reason=_OVERRIDE_REASON,
        approved_at=datetime.now(UTC),
        retained_record_count=retained,
    )


def _held_profile(root: Path) -> None:
    """Seed one profile carrying a filing, so the retention floor blocks it."""
    _create_profile(_PROFILE_ID, label="Retention held", tax_id="22222222J")
    _persist_filing(_PROFILE_ID, filing_year=2025, seed="3")


def _bucket_dir(root: Path) -> Path:
    from ...adapters.persistence.storage import BUCKETS_DIRNAME

    return root / BUCKETS_DIRNAME / _PROFILE_ID


def test_the_override_clears_a_filing_hold_and_is_recorded_in_the_journal(tmp_path: Path) -> None:
    """The authorisation travels with the transaction that acted on it.

    Asserting the journal, not just the return, because the recorded reason is
    what makes the destruction auditable afterwards -- an override that cleared
    the gate and left no account of itself would satisfy the operator and tell a
    later reader nothing.
    """
    from ..user_profile.lifecycle import ProfileCapsuleLifecycle

    with _isolated_reset_root(tmp_path) as root:
        _held_profile(root)
        with open_test_profile_session(_PROFILE_ID):
            journal = ProfileCapsuleLifecycle().prepare_delete(
                profile_id=UUID(_PROFILE_ID),
                retention_override=_override(),
            )

        assert journal.hold_assessment is not None
        assert journal.hold_assessment.filing_hold is True
        assert journal.retention_override is not None
        assert journal.retention_override.reason == _OVERRIDE_REASON


def test_an_open_legal_case_still_refuses_with_a_valid_override(tmp_path: Path) -> None:
    """The load-bearing case: a legal hold is absolute.

    The capsule is asserted still on disk after the refusal. Without that, a
    future regression that refused only AFTER renaming the capsule to its
    tombstone would read as a pass here while having already destroyed the
    thing the refusal exists to protect.
    """
    from ..evidence import LegalHoldCaseAuthority
    from ..user_profile.custody_transactions import ProfileCustodyTransactionRefusalError
    from ..user_profile.lifecycle import ProfileCapsuleLifecycle

    with _isolated_reset_root(tmp_path) as root:
        _held_profile(root)
        LegalHoldCaseAuthority(root=root).record_open_case_snapshot(
            profile_id=UUID(_PROFILE_ID),
            open_case_ids=("case-1",),
            observed_at=datetime.now(UTC),
        )

        with open_test_profile_session(_PROFILE_ID), pytest.raises(ProfileCustodyTransactionRefusalError):
            ProfileCapsuleLifecycle().prepare_delete(
                profile_id=UUID(_PROFILE_ID),
                retention_override=_override(),
            )

        assert _bucket_dir(root).is_dir()


def test_an_override_is_refused_where_no_filing_hold_blocks(tmp_path: Path) -> None:
    """A token answers an assessed block; it is never a free pass carried along.

    Without this, an override could be attached by default to every deletion and
    nothing would notice, because a profile with no hold deletes cleanly either
    way.
    """
    from ..user_profile.custody_transactions import ProfileCustodyTransactionRefusalError
    from ..user_profile.lifecycle import ProfileCapsuleLifecycle

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_ID, label="No hold", tax_id="22222222J")

        with open_test_profile_session(_PROFILE_ID), pytest.raises(ProfileCustodyTransactionRefusalError):
            ProfileCapsuleLifecycle().prepare_delete(
                profile_id=UUID(_PROFILE_ID),
                retention_override=_override(),
            )

        assert _bucket_dir(root).is_dir()


def test_a_legal_case_opened_after_preparation_still_stops_the_execution(tmp_path: Path) -> None:
    """The journaled override is not blanket clearance for the pre-effect re-check.

    Preparation happens while only a filing hold stands; the legal case opens
    afterwards. The execution must refuse, and the capsule must survive.
    """
    from ..evidence import LegalHoldCaseAuthority
    from ..user_profile.custody_transactions import ProfileCustodyTransactionRefusalError
    from ..user_profile.lifecycle import ProfileCapsuleLifecycle

    with _isolated_reset_root(tmp_path) as root:
        _held_profile(root)
        with open_test_profile_session(_PROFILE_ID):
            lifecycle = ProfileCapsuleLifecycle()
            journal = lifecycle.prepare_delete(
                profile_id=UUID(_PROFILE_ID),
                retention_override=_override(),
            )
            confirmation = lifecycle.confirm_delete(journal)

            LegalHoldCaseAuthority(root=root).record_open_case_snapshot(
                profile_id=UUID(_PROFILE_ID),
                open_case_ids=("case-2",),
                observed_at=datetime.now(UTC),
            )

            with pytest.raises(ProfileCustodyTransactionRefusalError):
                lifecycle.delete(confirmation)

        assert _bucket_dir(root).is_dir()

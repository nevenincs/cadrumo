"""The retention-floor refusal reaches the operator with its numbers filled in.

An error that is defined, registered and raised is still broken if the message
cannot find the values it interpolates. This one carries the whole point of the
refusal in its placeholders: how many filed records are still retained, and the
date erasure becomes safe. Rendered without them it says a statute forbids
something and declines to say what or until when.

The refusal itself is a backstop. The reset pauses earlier, before a blocked
target reaches deletion, so no supported flow arrives here -- which is exactly
why the state has to be forged to test it. A guard that only ever runs behind
another guard is proven by constructing the state the first one prevents.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...core.errors import render_error_text
from ...domain.retention import RetentionFloorError
from .._bucket_deletion_contracts import BucketDeletionFingerprint
from .._config_reset_models import (
    ConfigResetRetentionDecision,
    ConfigResetTarget,
    ConfigResetTargetPhase,
)
from ..config_reset import _refuse_erase_inside_the_retention_floor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "6d1f0c58-9b42-4e7a-8c31-0af5e6b27d94"
_SAFE_FROM = datetime(2031, 3, 1, tzinfo=UTC)


def _target(*, blocks_erase: bool, override_approved: bool, retained: int) -> ConfigResetTarget:
    """Build a snapshotted reset target carrying a recorded retention decision."""
    return ConfigResetTarget(
        bucket_id=_BUCKET_ID,
        label="Retention subject",
        exists_at_snapshot=True,
        fingerprint=BucketDeletionFingerprint(
            digest="a" * 64,
            file_count=3,
            total_bytes=4096,
        ),
        phase=ConfigResetTargetPhase.POINTER_RECONCILED,
        retention=ConfigResetRetentionDecision(
            assessed_at=datetime(2026, 8, 15, tzinfo=UTC),
            blocks_erase=blocks_erase,
            retained_record_count=retained,
            latest_safe_erase_date=_SAFE_FROM if blocks_erase else None,
            override_approved=override_approved,
            override_reason="Court order requiring erasure." if override_approved else None,
        ),
    )


def test_the_refusal_renders_both_of_its_numbers_and_the_statute() -> None:
    """The operator is told how many records, and the date they clear.

    Asserted on the interpolated values and the invariant tokens rather than on
    one language's prose: this message ships in four catalogues and renders in
    the operator's own, so pinning English wording would test the environment's
    locale instead of the contract. What must hold in every language is that
    both placeholders resolved, the statute is cited, and the way out names a
    real option.
    """
    with pytest.raises(RetentionFloorError) as raised:
        _refuse_erase_inside_the_retention_floor(_target(blocks_erase=True, override_approved=False, retained=4))

    rendered = render_error_text(raised.value)
    headline = rendered.splitlines()[0]

    # The load-bearing assertion: an unresolved placeholder leaves its literal
    # token behind, which is the exact failure this whole chain was about.
    assert "%{" not in rendered, rendered
    # Both values reached the SENTENCE, not merely the context block beneath it.
    assert "4" in headline, headline
    assert "2031-03-01" in headline, headline
    # Invariant across all four catalogues.
    assert "Ley 58/2003" in headline, headline
    assert "--override-retention" in headline, headline


def test_an_approved_override_is_permitted_through() -> None:
    """The refusal is a floor, not a wall: a recorded override proceeds."""
    _refuse_erase_inside_the_retention_floor(_target(blocks_erase=True, override_approved=True, retained=4))


def test_a_cleared_target_is_permitted_through() -> None:
    """Nothing retained is not a refusal, and must not be treated as one."""
    _refuse_erase_inside_the_retention_floor(_target(blocks_erase=False, override_approved=False, retained=0))

"""The reset's own tamper detector still bites on a custody record change.

A reset fingerprints each target at snapshot and compares on resume, so a
capsule mutated between the operator's confirmation and the destruction is
refused rather than erased under a decision taken about different bytes.

Nothing at reset level proved that. The suite's existing content-changed case
persists a FILING between snapshot and resume, and a filing does not move the
digest: it lands in the capsule database, which the inventory covers by path
only, and in a retention snapshot that lives outside the capsule entirely. So
that case never exercised the detector it was named for.

This plants a foreign file inside the capsule, which the inventory folds into
the digest by path and content, and asserts the resume pauses. It deliberately
stops at the pause: the detector fires in the resume preflight, before any
destructive step, so proving it bites needs no erase and the test stays honest
about what it covers.

A foreign file rather than a mutated custody record, on purpose. Corrupting a
record the capsule reader PARSES -- the envelope, say -- never reaches the
fingerprint comparison at all: it raises a hard integrity refusal first
("profile custody envelope is not a valid current-format record"). That is
sound behaviour, and it is a different guard from the one under test here.

The inventory-level counterpart, which pins WHICH members the digest claims,
lives in `adapters/persistence/storage/custody/tests/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .test_config_reset import (
    _OVERRIDE_REASON,
    _create_profile,
    _isolated_reset_root,
    _persist_filing,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = "61616161-6161-4161-8161-616161616161"
_CUSTODY_ENVELOPE = "custody/envelope.v1.json"


def _capsule_dir(root: Path) -> Path:
    from ...adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME

    return root / BUCKETS_DIRNAME / _PROFILE_ID


def test_resume_pauses_when_a_content_covered_custody_record_changed(tmp_path: Path) -> None:
    """Bytes appearing under the operator's feet stop the reset.

    The capsule still parses cleanly afterwards, so nothing but the digest
    comparison can be what refuses it -- which is precisely the claim.
    """
    from ..config_reset import resume_config_reset, start_config_reset
    from ..config_reset_models import ConfigResetOperationStatus, ConfigResetPauseReason

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_ID, label="Tamper target", tax_id="00000000T")
        # The filing is what HOLDS the reset at a pause. Without one, a confirmed
        # start runs straight through to the erase and leaves no window in which
        # a target could be tampered with.
        _persist_filing(_PROFILE_ID, filing_year=2025, seed="7")

        operation = start_config_reset(confirmed=True)
        original = operation.targets[0].fingerprint
        assert original is not None

        assert (_capsule_dir(root) / _CUSTODY_ENVELOPE).is_file(), "capsule laid out as expected"
        planted = _capsule_dir(root) / "planted.v1.json"
        planted.write_bytes(b'{"planted": true}')

        resumed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )

        assert resumed.status is ConfigResetOperationStatus.PAUSED
        assert resumed.pause_reason is ConfigResetPauseReason.TARGET_STATE_CHANGED
        assert resumed.paused_target_ids == (_PROFILE_ID,)
        assert resumed.targets[0].fingerprint is not None
        assert resumed.targets[0].fingerprint.digest != original.digest
        assert _capsule_dir(root).is_dir(), "a refused reset must not have destroyed the target"

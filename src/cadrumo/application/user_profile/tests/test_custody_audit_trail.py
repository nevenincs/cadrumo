"""Real-behaviour proof that custody mutations leave a queryable audit trail.

Passphrase rotation and the recovery-code lifecycle govern access to
everything else the vault holds, yet they previously emitted no bucket event
at all — an operator, or an investigator after a suspected compromise, had no
persisted record that any of them ever happened.

This drives the four production operations against a real bucket runtime and a
real encrypted file secret store: real master-key provider, real BIP-39 mint,
real atomic envelope install, real passphrase rewrap, real recovery unwrap. No
mocks, stubs, monkeypatches, skips, or expected-fail markers. The final test is
the standing guarantee that no secret material ever reaches an event payload.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.config import load_settings, override_settings
from ....domain.buckets import BucketEvent, BucketEventObjectType, BucketEventType
from ....tests.secure_sql import isolated_runtime_profile
from .._custody import (
    change_passphrase,
    create_recovery_code,
    recover_secret_store,
    rotate_recovery_code,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ROTATED_PASSPHRASE = "rotated-store-passphrase-9f2a"  # noqa: S105 - test fixture input
_RECOVERED_PASSPHRASE = "recovered-store-passphrase-4c7b"  # noqa: S105 - test fixture input


def _history() -> tuple[BucketEvent, ...]:
    """Load every persisted bucket event from the active bucket."""
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    return tuple(BucketEventHistoryRepository().load().events.values())


def _events_of(event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    return tuple(event for event in _history() if event.event_type is event_type)


def _enroll(*, rotate: bool) -> tuple[str, str]:
    """Run a real enrollment and return ``(mnemonic, fingerprint)``."""
    shown: dict[str, str] = {}

    def confirm(words: str) -> str:
        shown["words"] = words
        return words

    enroll = rotate_recovery_code if rotate else create_recovery_code
    result = enroll(confirm=confirm)
    return shown["words"], result.recovery_fingerprint


def test_recovery_create_and_rotate_each_record_their_own_event(tmp_path: Path) -> None:
    """A real create and a real rotate append distinct, correctly-typed events."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        assert _events_of(BucketEventType.CUSTODY_RECOVERY_CODE_CREATED) == (), (
            "no custody event may exist before the operation runs"
        )

        _, created_fingerprint = _enroll(rotate=False)

        created = _events_of(BucketEventType.CUSTODY_RECOVERY_CODE_CREATED)
        assert len(created) == 1, f"expected exactly one create event, got {len(created)}"
        assert created[0].bucket_id == runtime.bucket_id
        assert created[0].object_type is BucketEventObjectType.BUCKET
        assert created[0].payload["recovery_fingerprint"] == created_fingerprint, (
            "the event must carry the same non-secret fingerprint the operation returned"
        )
        assert _events_of(BucketEventType.CUSTODY_RECOVERY_CODE_ROTATED) == (), (
            "a create must not be recorded as a rotate"
        )

        _, rotated_fingerprint = _enroll(rotate=True)

        rotated = _events_of(BucketEventType.CUSTODY_RECOVERY_CODE_ROTATED)
        assert len(rotated) == 1, f"expected exactly one rotate event, got {len(rotated)}"
        assert rotated[0].payload["recovery_fingerprint"] == rotated_fingerprint
        assert rotated[0].payload["rotated"] == "true"
        assert len(_events_of(BucketEventType.CUSTODY_RECOVERY_CODE_CREATED)) == 1, (
            "the rotate must not retroactively duplicate the create event"
        )


def test_passphrase_change_records_an_event(tmp_path: Path) -> None:
    """A real passphrase rewrap appends exactly one audit event."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        current = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        assert _events_of(BucketEventType.CUSTODY_PASSPHRASE_CHANGED) == ()

        result = change_passphrase(current_passphrase=current, new_passphrase=_ROTATED_PASSPHRASE)
        assert result.changed is True

        changed = _events_of(BucketEventType.CUSTODY_PASSPHRASE_CHANGED)
        assert len(changed) == 1, f"expected exactly one passphrase-change event, got {len(changed)}"
        assert changed[0].bucket_id == runtime.bucket_id
        assert changed[0].payload["secret_store_dir"] == str(result.secret_store_dir)


def test_secret_store_recovery_records_an_event(tmp_path: Path) -> None:
    """A real mnemonic-driven recovery appends exactly one audit event."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        mnemonic, _ = _enroll(rotate=False)
        assert _events_of(BucketEventType.CUSTODY_SECRET_STORE_RECOVERED) == ()

        result = recover_secret_store(mnemonic=mnemonic, new_passphrase=_RECOVERED_PASSPHRASE)
        assert result.recovered is True

        recovered = _events_of(BucketEventType.CUSTODY_SECRET_STORE_RECOVERED)
        assert len(recovered) == 1, f"expected exactly one recover event, got {len(recovered)}"
        assert recovered[0].payload["secret_store_dir"] == str(result.secret_store_dir)


def test_custody_mutation_succeeds_when_the_audit_trail_is_unreachable(tmp_path: Path) -> None:
    """A locked profile store degrades the trail to a no-op, never the mutation.

    The event history is per-bucket encrypted storage, so it is unreachable
    with no unlocked profile — exactly the state ``config recover`` runs in.
    Making the trail a hard dependency would fail an already-durable custody
    mutation and make recovery depend on the access it exists to restore.
    """
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()

    # Provision a real secret store, then let the bucket session close.
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        storage_root = runtime.storage_root
        secret_store_dir = runtime.settings.cadrumo_secret_store_dir
        bucket_id = runtime.bucket_id

    # The master key is on disk and a profile is still selected, but nothing is
    # unlocked: the enrollment must commit and the trail must simply not record.
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=bucket_id,
        cadrumo_secret_store_backend="file",  # noqa: S106 - backend selector, not a credential
        cadrumo_secret_store_dir=secret_store_dir,
        cadrumo_secret_passphrase=passphrase,
    ):
        mnemonic, fingerprint = _enroll(rotate=False)

    assert fingerprint, "the enrollment must still commit and return its fingerprint"
    assert len(mnemonic.split()) == 24, "the real BIP-39 mint must still have run"


def test_no_custody_event_payload_carries_secret_material(tmp_path: Path) -> None:
    """Across the whole lifecycle, no event records a mnemonic word or passphrase.

    This is the standing guarantee behind the audit trail: the events exist to
    prove *that* a custody mutation happened, never to reveal *what* the secret
    was. Asserting per-word (not just the joined phrase) means a payload that
    leaked even a fragment of the mnemonic fails.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        current = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        mnemonic, _ = _enroll(rotate=False)
        rotated_mnemonic, _ = _enroll(rotate=True)
        change_passphrase(current_passphrase=current, new_passphrase=_ROTATED_PASSPHRASE)
        recover_secret_store(mnemonic=rotated_mnemonic, new_passphrase=_RECOVERED_PASSPHRASE)

        events = _history()
        custody_events = tuple(event for event in events if event.event_type.value.startswith("custody."))
        assert len(custody_events) == 4, (
            f"expected one event per custody mutation, got {[e.event_type.value for e in custody_events]}"
        )

        forbidden = {
            *mnemonic.split(),
            *rotated_mnemonic.split(),
            current,
            _ROTATED_PASSPHRASE,
            _RECOVERED_PASSPHRASE,
        }
        for event in events:
            rendered = " ".join((*event.payload.keys(), *event.payload.values(), event.object_id))
            leaked = sorted(token for token in forbidden if token and token in rendered.split())
            assert not leaked, f"event {event.event_type.value} leaked secret material: {leaked}"

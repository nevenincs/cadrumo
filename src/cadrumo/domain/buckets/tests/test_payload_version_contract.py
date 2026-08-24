"""Pin the persisted ``payload_version`` each emitting domain writes.

``payload_version`` is the one :class:`BucketEvent` field that does NOT feed
:func:`derive_bucket_event_id`, so a wrong value passes the model's own derived-id
check and silently misdeclares the payload contract of already-written events. It
is therefore the field a consolidation can change without any other test noticing
— which is exactly what nearly happened when the per-domain emitters were routed
through the shared :func:`emit_bucket_event` primitive: the primitive had a
modelo-flavoured default of 2, and every other domain writes 1.

Each case below drives a real emitting path against a real bucket runtime and real
encrypted SQLite, then reads the version back off the persisted event. No mocks,
stubs, monkeypatches, skips, or expected-fail markers. The numbers here are the
versions those domains write today; changing one means changing a persisted data
contract, so a diff to this file is the signal that a payload contract moved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from .. import BucketEvent, BucketEventType

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_BUCKET_ID = "8c40b7e1-59da-4f6c-b3a7-1e05d9c2f483"

#: Persisted payload-schema version per emitting domain, as written today. Modelo
#: sits at 2 and every other domain at 1, so the versions genuinely differ and a
#: consolidation that collapsed them would have to break one of these numbers.
#: Modelo's own 2 is pinned on real calculate and live-capture paths by
#: application/modelo/tests/test_borrador_binding.py and
#: application/live/tests/test_justificante_capture_stamp.py.
_PROFILE_LIFECYCLE_PAYLOAD_VERSION = 1
_WORKFLOW_PAYLOAD_VERSION = 1
_INVENTORY_PAYLOAD_VERSION = 1
_PROFILE_PASSPHRASE = "payload-version-profile-secret"  # noqa: S105 - synthetic test fixture

# The portable-bundle families are pinned where their own real drivers live: the
# import event in application/user_profile/tests/test_bundle_import_event.py, and
# the export event alongside the reconciliation cases that already exercise it.


def _event_of(event_type: BucketEventType) -> BucketEvent:
    """Return the single persisted event of ``event_type``, refusing any other count."""
    matching = tuple(
        event for event in BucketEventHistoryRepository().load().events.values() if event.event_type is event_type
    )
    assert len(matching) == 1, f"expected exactly one {event_type.value} event, got {len(matching)}"
    return matching[0]


def test_the_shared_primitive_requires_an_explicit_payload_version() -> None:
    """No domain can inherit another's version by omission.

    The guard behind every case below: while the primitive carried a default, a
    routed wrapper that forgot to pass its own version silently adopted modelo's.
    """
    import inspect

    from .. import emit_bucket_event

    parameter = inspect.signature(emit_bucket_event).parameters["payload_version"]
    assert parameter.default is inspect.Parameter.empty, (
        "emit_bucket_event grew a payload_version default; a routed domain that omits "
        "the argument would then persist another domain's payload contract"
    )


def test_profile_lifecycle_events_persist_version_one(tmp_path: Path) -> None:
    """Registering a profile writes the profile-lifecycle payload contract."""
    from ....application.user_profile import (
        login_profile,
        register_profile_with_credentials,
    )

    label = "Payload version probe"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=label,
            passphrase=_PROFILE_PASSPHRASE,
        )
        # Registration closes the session it opened, so a freshly registered
        # profile is LOCKED and the event catalogue cannot be read back through
        # an authenticated session. Reading the event this test is about needs
        # the profile open, and the storage runtime says so rather than
        # returning an empty catalogue.
        login_profile(name=label, passphrase_callback=lambda: _PROFILE_PASSPHRASE)

        event = _event_of(BucketEventType.PROFILE_BUCKET_CREATED)
        assert event.payload_version == _PROFILE_LIFECYCLE_PAYLOAD_VERSION


def test_workflow_state_reset_persists_version_one(tmp_path: Path) -> None:
    """The workflow-reset audit event writes the workflow payload contract."""
    from ....application.workflow import reset_workflow_state

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        reset_workflow_state(actor="operator", source="payload-version-probe")

        assert _event_of(BucketEventType.WORKFLOW_STATE_RESET).payload_version == _WORKFLOW_PAYLOAD_VERSION


def test_inventory_events_persist_version_one(tmp_path: Path) -> None:
    """An inventory ledger create writes the inventory payload contract."""
    from ....application.inventory import InventoryService

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        InventoryService(
            settings=profile.settings,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        ).create(
            bucket_id=profile.bucket_id,
            actividad_id="A1",
            year=2025,
            valuation_method="fifo",
            actor="operator",
        )

        assert _event_of(BucketEventType.LEDGER_INVENTORY_CREATED).payload_version == _INVENTORY_PAYLOAD_VERSION

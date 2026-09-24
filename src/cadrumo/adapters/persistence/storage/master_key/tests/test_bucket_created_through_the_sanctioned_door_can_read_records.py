"""The sanctioned creation door yields a bucket whose records decrypt.

This module exists because the same wrong claim was measured twice, and both
times the measurement stopped one step short. A probe created a profile, read
a record *without authenticating*, saw a refusal, and reported it as "the door
creates a bucket the storage layer will never open". Registration leaves the
new profile unlocked only in the process that created it, and mints no
acceleration receipt, so every other process finds it LOCKED until it
authenticates. That is the contract, not a defect.

The property worth holding is therefore the WHOLE door and nothing shorter:
create, **authenticate**, then decrypt what is actually on disk. The two reads
below are deliberately the same two calls the mistaken probes used --
:func:`secure_object_repository_for_active_bucket` and
:meth:`WorkflowStateRepository.load` -- so the pair of tests here shows the
identical call refusing before login and succeeding after it. The refusal a
probe can observe and the defect it inferred are not the same finding, and
the only thing that separates them is the login step.

Everything is real: a real custody envelope, a real Argon2id-derived wrap, a
real per-bucket encrypted SQLite store, on an isolated storage root. No
substitute provider and no synthetic session. Row decryptability is asserted
through the integrity probe, which unwraps every row's ciphertext and returns
counts rather than plaintext.

See Also:
    :class:`~cadrumo.adapters.persistence.storage.sql.secure_object_records.SecureObjectNamespaceIntegrity`
        The per-namespace decryptability counts the readback assertion rests on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)

from ......application.user_profile.login_session import login_profile
from ......application.user_profile.profile_record_repository import close_active_profile_record_session
from ......application.user_profile.registration import register_profile_with_credentials
from ......application.workflow.persistence import workflow_state_repository
from ......core.bucket_pointer import resolve_active_bucket_id
from ......domain.user_profile.values import ProfileSetupState
from ...custody.errors import ProfileCustodyRecordError
from ...errors import StorageValidationError
from ...runtime_repository import secure_object_repository_for_active_bucket
from ...tests.secure_sql import isolated_profile_storage_root
from ..active_session import close_active_bucket_session

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


_LABEL = "sanctioned-door-readback"
_CREDENTIAL_INPUT = "sanctioned-door-readback-passphrase"

_PROFILE_VALUE_NAMESPACE = "cadrumo.application.user_profile.value"
_NOT_READY = "errors.storage.runtime.not_ready"


def test_bucket_created_through_the_sanctioned_door_can_read_records(tmp_path: Path) -> None:
    """Create, authenticate, then decrypt the profile rows written at creation."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label=_LABEL,
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        assert outcome.setup_state is ProfileSetupState.INCOMPLETE

        login_profile(
            name=_LABEL,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=_profile_decode_context_for_test,
        )

        repository = secure_object_repository_for_active_bucket()
        assert _PROFILE_VALUE_NAMESPACE in set(repository.list_namespaces())

        # Unwraps every row in the namespace under the session key. A bucket
        # the storage layer cannot open reports zero readable rows here, so
        # this is the assertion the original claim would have had to fail.
        integrity = repository.probe_namespace_integrity(_PROFILE_VALUE_NAMESPACE)
        assert integrity.readable > 0
        assert integrity.unreadable == 0

        assert workflow_state_repository().load() is not None


def test_the_same_reads_refuse_before_authentication(tmp_path: Path) -> None:
    """The lock the earlier probes mistook for a defect is real and holds.

    Without this the test above proves nothing: a door that never locks would
    satisfy it just as well as a door that locks and then opens. Asserting the
    refusal is what makes the login step load-bearing, and pinning the shared
    ``not_ready`` key is what shows the pre-login observation was a routine
    lock rather than evidence about key material.

    The creating process keeps the session it just opened, so this releases
    that process's authorities first: what remains is exactly what any other
    process sees, a selected profile with no key in memory.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            label=_LABEL,
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        close_active_profile_record_session()
        close_active_bucket_session()
        assert resolve_active_bucket_id() is not None, "the profile must stay selected, or the refusal proves nothing"

        with pytest.raises(StorageValidationError, match=_NOT_READY):
            secure_object_repository_for_active_bucket()

        with pytest.raises(StorageValidationError, match=_NOT_READY):
            workflow_state_repository().load()


def test_readback_depends_on_the_on_disk_custody_envelope(tmp_path: Path) -> None:
    """Anti-tautology: destroy the persisted custody material and lose the read.

    Without this, the passing readback above could in principle be served by
    something the create span left in process memory, and the module would
    prove nothing about what is on disk. Overwriting
    ``custody/envelope.v1.json`` is the narrowest edit that must cost the
    operator their key, so a login that still succeeded afterwards would mean
    the wrap is not the thing gating access.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(
            label=_LABEL,
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )

        envelope = storage_root / "buckets" / outcome.bucket_id / "custody" / "envelope.v1.json"
        assert envelope.is_file()
        envelope.write_text("{}", encoding="utf-8")

        # The refusal names the CURRENT format rather than reaching for an
        # older one: a custody envelope that does not parse as the current
        # record is corruption now, not a shape to tolerate.
        with pytest.raises(ProfileCustodyRecordError, match="current-format record"):
            login_profile(
                name=_LABEL,
                passphrase_callback=lambda: _CREDENTIAL_INPUT,
                profile_decode_context=_profile_decode_context_for_test,
            )

"""Precedence-chain tests for the active-profile resolver.

The resolver lives at `cadrumo.core.resolve_active_bucket_id`. It consults
two precedence rungs in order:

1. `Settings.cadrumo_active_profile` (`CADRUMO_ACTIVE_PROFILE` env var, or
   an `override_settings(cadrumo_active_profile=...)` context manager).
2. The plaintext `<cadrumo-root>/active-profile` pointer file written
   by `register_active_profile` / `select_profile`.

A missing pointer + missing env override returns `None` so callers
that surface it to the operator can refuse with a typed
`NoActiveProfileError`.
"""

from __future__ import annotations

import logging
from base64 import b64encode
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....application.user_profile._capsule_record import ProfileRecordSession
from ....application.user_profile._lifecycle import ProfileCapsuleLifecycle
from ....application.user_profile._profile_record_repository import bound_profile_record_session
from ....core import (
    BucketPointer,
    ProfileRecordUnavailability,
    pointer_path,
    read_pointer,
    resolve_active_bucket_id,
    write_pointer,
)
from ....core.config import override_settings
from ....core.errors import NoActiveProfileError, get_registered_error_code
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ... import wizard as _wizard  # noqa: F401
from .._models import WorkflowState
from .._profile_bucket_scan import resolve_profile_bucket
from .._profile_health import assess_active_profile_health, repair_active_profile_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_DEK = bytes(range(32))


def _current_profile_session(profile_id: str, *, root: Path, label: str) -> ProfileRecordSession:
    """Create one real committed current capsule and return its live record session."""
    identity = UUID(profile_id)
    seed = identity.bytes + identity.bytes
    envelope = ProfileCustodyEnvelope.create(
        profile_id=identity,
        password_generation=1,
        dek_epoch=b64encode(seed[:16]).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(seed[16:]).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(seed[:12]).decode("ascii"),
            ciphertext_b64=b64encode(seed).decode("ascii"),
            tag_b64=b64encode(seed[:16]).decode("ascii"),
        ),
    )
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_PROFILE_DEK)
    ProfileCapsuleLifecycle(root=root).create(
        label=label,
        profile_id=identity,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_PROFILE_DEK),
        data_files={},
        initial_record=UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=str(identity),
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        ),
        record_session=session,
    )
    return session


def test_workflow_models_do_not_expose_active_bucket_resolver_shims() -> None:
    """Workflow models must not be an alternate import path for core resolvers."""

    from .. import _models as workflow_models

    assert not hasattr(workflow_models, "resolve_active_bucket_id")
    assert not hasattr(workflow_models, "require_active_bucket_id")


def test_resolver_uses_active_profile_precedence_chain(tmp_path: Path) -> None:
    """Settings override wins over the active-profile pointer; blank settings fall through."""
    cases = (
        (None, None, None),
        (None, "catering", "catering"),
        ("translation", "catering", "translation"),
        ("   ", "catering", "catering"),
    )

    for index, (settings_profile, pointer_bucket_id, expected_bucket_id) in enumerate(cases):
        case_root = tmp_path / f"precedence-{index}"
        case_root.mkdir()
        if pointer_bucket_id is not None:
            write_pointer(case_root, BucketPointer(bucket_id=pointer_bucket_id, schema_version=1))

        with override_settings(cadrumo_active_profile=settings_profile, cadrumo_local_storage_root=case_root):
            assert resolve_active_bucket_id() == expected_bucket_id


def test_no_active_profile_error_has_registered_error_code() -> None:
    """The workflow no-active-profile export must bind to the relocated core error."""

    code = get_registered_error_code(NoActiveProfileError)
    assert code.code == "REFUSED_NO_ACTIVE_PROFILE"
    assert code.message_key == "errors.refused.refused_no_active_profile"


def test_active_profile_record_names_an_absent_capsule_as_the_reason(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pointer without a current capsule returns no record, and says which absence it is.

    The convenience accessor still collapses to ``None``; the resolution beside
    it carries the reason, which is what a projection reporting the absence to
    an operator must read. A selector with no committed capsule is the one
    absence that genuinely means the record is not there.
    """

    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    write_pointer(tmp_path, BucketPointer(bucket_id=bucket_id, schema_version=1))
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        caplog.set_level(logging.DEBUG, logger="cadrumo.application.workflow._models")

        state = WorkflowState()
        assert state.active_profile_record() is None
        resolution = state.resolve_active_profile_record()

    assert resolution.record is None
    assert resolution.unavailability is ProfileRecordUnavailability.NO_LIVE_CAPSULE
    assert "active profile record resolution found no live bucket for the selected profile" in caplog.text
    # The reason-erasing framing this replaced must not return unnoticed.
    assert "returned no profile record" not in caplog.text
    assert bucket_id not in caplog.text


def test_label_override_resolves_real_record_and_masks_dangling_pointer_repair(tmp_path: Path) -> None:
    """Canonicalize an override label before secure reads while preserving pointer precedence."""

    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    dangling_id = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    session = _current_profile_session(bucket_id, root=tmp_path, label="Operator")
    try:
        write_pointer(tmp_path, BucketPointer(bucket_id=dangling_id, schema_version=1))
        target = pointer_path(tmp_path)
        dangling_bytes = target.read_bytes()

        with (
            override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile="operator"),
            bound_profile_record_session(session),
        ):
            state = WorkflowState()
            assert state.active_profile_bucket_id() == bucket_id
            assert state.active_profile_record() is not None

            protected_health = assess_active_profile_health(state)

            assert protected_health.active_profile == bucket_id
            assert protected_health.source == "env_override"
            assert protected_health.status == "incomplete"
            assert protected_health.registered_bucket is True
            assert protected_health.profile_record_present is True
            assert protected_health.repairable_by_clearing_pointer is False
            assert target.read_bytes() == dangling_bytes

        with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
            exposed_health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert exposed_health.active_profile == dangling_id
        assert exposed_health.source == "pointer"
        assert exposed_health.status == "dangling_pointer"
        assert exposed_health.repairable_by_clearing_pointer is True
        assert repaired.before == exposed_health
        assert repaired.dry_run is False
        assert repaired.cleared_pointer is True
        assert repaired.after is not None
        assert repaired.after.status == "none"
        assert read_pointer(tmp_path) is None
    finally:
        session.close()


def test_resolve_profile_bucket_refuses_a_retired_manifest_without_reading_it(tmp_path: Path) -> None:
    """A retired manifest is a typed custody refusal, not an alternate discovery route."""
    from ....adapters.persistence.storage.custody import ProfileCustodyRefusal, ProfileCustodyRefusedError

    retired = tmp_path / "buckets" / "51c1fa97-28e1-4700-ac1e-ed7cf094d37b" / "manifest.toml"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(b"this retired document is deliberately malformed")

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        resolve_profile_bucket("operator", root=tmp_path)

    assert captured.value.refusal is ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED


def test_resolve_profile_bucket_resolves_an_active_profile_by_display_name(tmp_path: Path) -> None:
    """A display-name identifier resolves to the UUID bucket via the label fallback.

    This is the real operator path: ``CADRUMO_ACTIVE_PROFILE=operator`` (or any
    active-profile pointer carrying the operator label the user chose at
    registration, never the UUID they never see). The by-UUID-direct lookup
    misses on the label, so the same committed-capsule projection resolves the
    label and returns the correct immutable identity.
    """

    uuid = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    session = _current_profile_session(uuid, root=tmp_path, label="operator")
    session.close()

    pointer = resolve_profile_bucket("operator", root=tmp_path)

    assert pointer is not None
    assert pointer.bucket_id == uuid, "the display name must resolve to the immutable UUID bucket id"
    assert pointer.label == "operator"


def test_resolve_profile_bucket_returns_none_for_an_unknown_identifier(tmp_path: Path) -> None:
    """Neither a UUID-shaped nor a label-shaped unknown identifier resolves."""

    session = _current_profile_session(
        "51c1fa97-28e1-4700-ac1e-ed7cf094d37b",
        root=tmp_path,
        label="operator",
    )
    session.close()

    assert resolve_profile_bucket("nonexistent", root=tmp_path) is None


def test_duplicate_label_is_refused_before_a_second_capsule_can_enter_discovery(tmp_path: Path) -> None:
    """Current projections never carry a legacy ambiguous-label state."""
    from ...user_profile._custody_transactions import ProfileCustodyTransactionConflictError

    first = _current_profile_session(
        "51c1fa97-28e1-4700-ac1e-ed7cf094d37b",
        root=tmp_path,
        label="operator",
    )
    first.close()

    with pytest.raises(ProfileCustodyTransactionConflictError):
        _current_profile_session(
            "62d2ab08-39f2-4811-bd2a-fe48fd105e4a",
            root=tmp_path,
            label="operator",
        )

    resolved = resolve_profile_bucket("operator", root=tmp_path)
    assert resolved is not None
    assert resolved.bucket_id == "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"

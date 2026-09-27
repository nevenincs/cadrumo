"""Durable denial over real encrypted custody with native fault injection."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_crypto import api_key_verifier
from cadrumo.adapters.persistence.storage.custody.automation_store import (
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
    AutomationControlStore,
    retire_profile_automation,
)
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.access_contracts import AuthorityState
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo.application.user_profile.capsule_archive import (
    export_profile_capsule_archive,
    read_profile_capsule_archive,
)
from cadrumo.application.user_profile.capsule_restore import restore_profile_capsule_with_password
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.custody_service import ProfileCustodyTransactionService
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.application.user_profile.recovery_custody import (
    enroll_profile_recovery,
    reset_profile_passphrase_with_recovery,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


def enroll(subject: AdministrationSubject) -> SecretBytes:
    request_id = uuid4()
    subject.service.request(request_id, subject.proposal)
    subject.approve(request_id)
    request = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
    credential = subject.owner.delivery.endpoint.possession(request)
    assert credential is not None
    return credential


@pytest.fixture
def enrolled(tmp_path: Path) -> Iterator[tuple[AdministrationSubject, SecretBytes]]:
    with administration_subject(tmp_path) as subject:
        yield subject, enroll(subject)


@pytest.mark.parametrize("kind", list(AutomationDenialKind))
def test_denial_removes_unwrap_material_and_survives_fresh_store(
    enrolled: tuple[AdministrationSubject, SecretBytes], kind: AutomationDenialKind
) -> None:
    subject, credential = enrolled
    before = subject.store.snapshot()
    target = before.keys[0].key_id if kind is AutomationDenialKind.KEY else before.grants[0].grant_id
    change = AutomationDenial(
        request_id=uuid4(),
        binding=before.binding,
        kind=kind,
        target_id=target if kind in {AutomationDenialKind.KEY, AutomationDenialKind.GRANT} else None,
    )
    result = subject.store.deny(change)
    assert result.access_denied and not result.cleanup_pending
    assert not any(namespace == WRAP_NAMESPACE for namespace, _ in subject.native.items)
    restarted = AutomationControlStore(root=subject.store.root, binding=before.binding, secrets_store=subject.native)
    with pytest.raises(AutomationCustodyError) as error:
        restarted.unwrap(credential=credential, now=subject.owner.current.context.now)
    assert error.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
    after = restarted.snapshot()
    assert after.grants[0].state is (
        AuthorityState.SUSPENDED if kind is AutomationDenialKind.PROFILE_LOCK else AuthorityState.REVOKED
    )
    assert after.profile_lock_generation == before.profile_lock_generation + int(
        kind is AutomationDenialKind.PROFILE_LOCK
    )
    assert restarted.deny(change).revision == result.revision
    assert restarted.reconcile_denial() is None


@pytest.mark.parametrize("failure", ["read", "anchor_before", "anchor_after", "delete"])
def test_native_failure_keeps_restart_denial_until_exact_cleanup_completes(
    enrolled: tuple[AdministrationSubject, SecretBytes], failure: str
) -> None:
    subject, credential = enrolled
    change = AutomationDenial(request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.ALL)
    subject.native.unavailable = failure == "read"
    subject.native.fail_delete = failure == "delete"
    if failure.startswith("anchor"):
        subject.native.fail_write = CONTROL_NAMESPACE
        subject.native.commit_before_failure = failure == "anchor_after"
    result = subject.store.deny(change)
    assert result.access_denied and result.cleanup_pending
    restarted = AutomationControlStore(
        root=subject.store.root, binding=subject.store.binding, secrets_store=subject.native
    )
    subject.native.unavailable = subject.native.fail_delete = False
    subject.native.fail_write = None
    with pytest.raises(AutomationCustodyError) as error:
        restarted.unwrap(credential=credential, now=subject.owner.current.context.now)
    assert error.value.reason is AutomationCustodyCode.NEEDS_USER
    # Ordinary publication cannot clear the denial as a side effect.
    with pytest.raises(AutomationCustodyError):
        restarted.enrollment_state()
    settled = restarted.reconcile_denial()
    assert settled is not None and settled.access_denied and not settled.cleanup_pending
    assert not any(namespace == WRAP_NAMESPACE for namespace, _ in subject.native.items)
    with pytest.raises(AutomationCustodyError) as error:
        restarted.unwrap(credential=credential, now=subject.owner.current.context.now)
    assert error.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED


def test_targeted_revocation_preserves_an_independent_grant(
    enrolled: tuple[AdministrationSubject, SecretBytes],
) -> None:
    subject, first = enrolled
    second = enroll(subject)
    before = subject.store.snapshot()
    change = AutomationDenial(
        request_id=uuid4(), binding=before.binding, kind=AutomationDenialKind.KEY, target_id=api_key_verifier(first)[0]
    )
    assert not subject.store.deny(change).cleanup_pending
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=first, now=subject.owner.current.context.now)
    with subject.store.unlocked(credential=second, now=subject.owner.current.context.now) as dek:
        assert len(dek) == 32 and any(dek)
    assert not any(dek)


def test_old_files_cannot_resurrect_revocation(enrolled: tuple[AdministrationSubject, SecretBytes]) -> None:
    subject, credential = enrolled
    old_pointer = (subject.store.directory / "current.json").read_bytes()
    change = AutomationDenial(request_id=uuid4(), binding=subject.store.binding, kind=AutomationDenialKind.ALL)
    assert not subject.store.deny(change).cleanup_pending
    (subject.store.directory / "current.json").write_bytes(old_pointer)
    with pytest.raises(AutomationCustodyError) as error:
        subject.store.unwrap(credential=credential, now=subject.owner.current.context.now)
    assert error.value.reason is AutomationCustodyCode.INVALID


@pytest.mark.parametrize("transition", ["rotation", "recovery", "delete"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_custody_transition_retires_automation_with_optional_native_store_unavailable(
    enrolled: tuple[AdministrationSubject, SecretBytes], transition: str, unavailable: bool
) -> None:
    subject, credential = enrolled
    profile_id, root = subject.store.binding.profile_id, subject.store.root
    _, decode = profile_authority_contexts()
    replacement = "synthetic-replacement-input"
    subject.native.unavailable = unavailable
    port = build_profile_custody_port(automation_secrets_store=subject.native)
    with bind_profile_custody_port(port):
        if transition == "rotation":
            outcome = rotate_profile_passphrase(
                profile_id=profile_id,
                current_passphrase=PROFILE_INPUT,
                new_passphrase=replacement,
                new_passphrase_confirmation=replacement,
                root=root,
                profile_decode_context=decode,
            )
            assert outcome.password_generation == subject.store.binding.custody_generation + 1
        elif transition == "recovery":
            handed: list[str] = []
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=PROFILE_INPUT,
                root=root,
                recovery_handover=lambda value: handed.append(value.recovery_key.code) or handed[-1],
            )
            reset = reset_profile_passphrase_with_recovery(
                profile_id=profile_id,
                recovery_code=handed[0],
                new_passphrase=replacement,
                new_passphrase_confirmation=replacement,
                root=root,
                profile_decode_context=decode,
            )
            assert reset.password_generation == subject.store.binding.custody_generation + 1
        else:
            service = ProfileCustodyTransactionService(root=root)
            journal = service.prepare_delete(profile_id=profile_id)
            service.execute_delete(service.confirmation_for(journal))
    if unavailable:
        assert (subject.store.directory / "retirement.json").is_file()
    subject.native.unavailable = False
    assert retire_profile_automation(root=root, profile_id=profile_id, secrets_store=subject.native)
    assert not subject.native.items
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=credential, now=subject.owner.current.context.now)
    if transition != "delete":
        material = load_committed_profile_password_material(profile_id, root=root)
        current = changed(subject.store.binding, custody_generation=material.envelope.password_generation)
        fresh = AutomationControlStore(root=root, binding=current, secrets_store=subject.native)
        assert fresh.enrollment_state().revision == 0
        assert not fresh.enrollment_state().grants


def test_restoring_pre_delete_backup_in_same_root_cannot_restore_delegation(
    enrolled: tuple[AdministrationSubject, SecretBytes], tmp_path: Path
) -> None:
    subject, credential = enrolled
    root, profile_id = subject.store.root, subject.store.binding.profile_id
    archive = tmp_path / "before-delete.cadrumo-bucket.tar.gz"
    export_profile_capsule_archive(profile_id=profile_id, target=archive)
    subject.native.unavailable = True
    with bind_profile_custody_port(build_profile_custody_port(automation_secrets_store=subject.native)):
        service = ProfileCustodyTransactionService(root=root)
        journal = service.prepare_delete(profile_id=profile_id)
        service.execute_delete(service.confirmation_for(journal))
        _, decode = profile_authority_contexts()
        restored = restore_profile_capsule_with_password(
            label="Enrollment tests",
            capsule=read_profile_capsule_archive(archive),
            password=PROFILE_INPUT,
            root=root,
            profile_decode_context=decode,
        )
    assert str(restored.profile_id) == str(profile_id)
    with pytest.raises(AutomationCustodyError):
        subject.store.unwrap(credential=credential, now=subject.owner.current.context.now)
    subject.native.unavailable = False
    with pytest.raises(AutomationCustodyError) as error:
        subject.store.unwrap(credential=credential, now=subject.owner.current.context.now)
    assert error.value.reason is AutomationCustodyCode.MISSING
    assert not subject.native.items
    assert not subject.store.enrollment_state().grants

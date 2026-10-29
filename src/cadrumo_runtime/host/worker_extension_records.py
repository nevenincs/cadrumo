"""Encrypted opaque byte custody on the existing profile-worker secret channel."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from cadrumo.adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from cadrumo.adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.sql.secure_object_records import SecureObjectDeletion
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.core.config import load_settings
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordCapability,
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
    ProfileWorkerExtensionRecordRequest,
)
from cadrumo_client.transport.frame_io import read_secret, write_document, write_secret
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerExtensionRecordReply

from ..adapters.worker_transport import WorkerChannel


def read_extension_record(
    repository: SecureObjectRepository,
    policy: ExtensionRecordCapability,
    key: str,
    revisions: Mapping[str, str | None],
    material: bytearray,
) -> tuple[Literal["absent", "unreadable", "present"], str | None]:
    """Read one bounded opaque record and keep its revision coupled to the bytes."""
    revision = revisions.get(key)
    if key not in revisions:
        return "absent", revision
    try:
        row = repository.load(
            policy.namespace, key, expected_class=policy.classification, max_supported_version=policy.schema_version
        )
    except (CadrumoError, SQLAlchemyError, ValueError):
        return "unreadable", revision
    if row is None:
        return "absent", revision
    if len(row.payload) > policy.maximum_bytes:
        return "unreadable", revision
    material.extend(row.payload)
    return "present", row.revision_id


def write_extension_record(
    channel: WorkerChannel,
    custody: ProfileWorkerCustody,
    repository: SecureObjectRepository,
    request: ExtensionRecordRequest,
    policy: ExtensionRecordCapability,
    key: str,
    revision: str | None,
) -> tuple[Literal["refused", "written"], str | None, ExtensionRecordRefusal | None]:
    """Read one bounded secret and commit it only under current custody."""
    with read_secret(channel, deadline=time.monotonic() + 5) as incoming:
        if len(incoming) != request.byte_count or len(incoming) > policy.maximum_bytes:
            return "refused", revision, ExtensionRecordRefusal.INVALID
        custody.require(request.session_id)
        repository.save(
            namespace=policy.namespace,
            object_key=key,
            classification=policy.classification,
            schema_version=policy.schema_version,
            written_at=now(),
            payload=bytes(incoming),
            write_provenance="extension-record",
            expected_revision_id=request.expected_revision,
        )
        return "written", repository.peek_many_revision_ids(policy.namespace, (key,)).get(key), None


def delete_extension_record(
    repository: SecureObjectRepository,
    request: ExtensionRecordRequest,
    policy: ExtensionRecordCapability,
    key: str,
    revisions: Mapping[str, str | None],
    revision: str | None,
) -> tuple[Literal["refused", "deleted"], str | None, ExtensionRecordRefusal | None]:
    """Apply the exact expected revision to one deletion."""
    if request.expected_revision == ABSENT_SECURE_OBJECT_REVISION_ID:
        if key in revisions:
            return "refused", revision, ExtensionRecordRefusal.REVISION_CONFLICT
        return "deleted", revision, None
    repository.apply_batch(
        writes=(),
        deletions=(
            SecureObjectDeletion(
                namespace=policy.namespace,
                hashed_object_key=secure_object_key_digest(key),
                expected_revision_id=request.expected_revision,
            ),
        ),
    )
    return "deleted", None, None


def perform_extension_action(
    channel: WorkerChannel,
    custody: ProfileWorkerCustody,
    repository: SecureObjectRepository,
    request: ExtensionRecordRequest,
    policy: ExtensionRecordCapability,
    action: str,
    material: bytearray,
) -> tuple[
    Literal["refused", "present", "absent", "unreadable", "written", "deleted", "generation"],
    str | None,
    ExtensionRecordRefusal | None,
    str | None,
]:
    """Perform the requested repository action under the held custody section."""
    state: Literal["refused", "present", "absent", "unreadable", "written", "deleted", "generation"] = "refused"
    revision: str | None = None
    refusal: ExtensionRecordRefusal | None = None
    generation: str | None = None
    key = request.object_key
    if action == "generation":
        revisions = repository.observe_revision_ids(policy.namespace)
        generation = sha256_hex("\x1f".join(item or "" for item in revisions).encode())
        state = "generation"
    elif key is not None:
        revisions = repository.peek_many_revision_ids(policy.namespace, (key,))
        revision = revisions.get(key)
        if action == "read":
            state, revision = read_extension_record(repository, policy, key, revisions, material)
        elif action == "write":
            state, revision, refusal = write_extension_record(
                channel, custody, repository, request, policy, key, revision
            )
        else:
            state, revision, refusal = delete_extension_record(repository, request, policy, key, revisions, revision)
    return state, revision, refusal, generation


def serve_extension_record(
    channel: WorkerChannel, custody: ProfileWorkerCustody, command: ProfileWorkerExtensionRecordRequest
) -> None:
    """Recheck exact lease and policy, then use the repository's canonical CAS."""
    request, policy = command.request, command.policy
    action = request.action.removeprefix("extension_record_")
    material = bytearray()
    state = "refused"
    revision = None
    refusal = None
    generation = None
    try:
        if request.capability != policy.capability or action not in policy.actions:
            refusal = ExtensionRecordRefusal.CAPABILITY_DENIED
        elif request.object_key is not None and re.fullmatch(policy.key_pattern, request.object_key) is None:
            refusal = ExtensionRecordRefusal.INVALID
        else:
            # Parent owns the authority fence across this whole exchange. The worker
            # also checks physical custody before reading, writing and disclosure.
            with custody.section(request.session_id):
                repository = secure_object_repository_for_bucket(
                    str(custody.identity.binding.profile_id), load_settings()
                )
                state, revision, refusal, generation = perform_extension_action(
                    channel, custody, repository, request, policy, action, material
                )
                custody.require(request.session_id)
                reply = ExtensionRecordReply(
                    request_id=request.request_id,
                    runtime_boot_id=custody.identity.runtime_boot_id,
                    connection_id=custody.require(request.session_id).connection_id,
                    state=state,
                    revision=revision,
                    byte_count=len(material),
                    refusal=refusal,
                    custody_generation=str(custody.identity.binding.custody_generation),
                    records_generation=generation,
                )
                write_document(
                    channel,
                    ProfileWorkerExtensionRecordReply(
                        identity=custody.identity, request_id=command.request_id, result=reply
                    ),
                    deadline=time.monotonic() + 5,
                )
                if material:
                    write_secret(channel, material, deadline=time.monotonic() + 5)
                return
    except SecureObjectRevisionConflictError:
        refusal = ExtensionRecordRefusal.REVISION_CONFLICT
    except (CadrumoError, SQLAlchemyError, OSError):
        refusal = ExtensionRecordRefusal.UNAVAILABLE
    finally:
        material[:] = bytes(len(material))
    write_document(
        channel,
        ProfileWorkerExtensionRecordReply(
            identity=custody.identity,
            request_id=command.request_id,
            result=ExtensionRecordReply(
                request_id=request.request_id,
                runtime_boot_id=custody.identity.runtime_boot_id,
                connection_id=custody.require(request.session_id).connection_id,
                state="refused",
                refusal=refusal,
            ),
        ),
        deadline=time.monotonic() + 5,
    )

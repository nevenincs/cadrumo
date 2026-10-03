"""Serialized, recoverable automation custody outside portable profile capsules.

The native anchor is authoritative. Filesystem publication and credential-store
replacement are separate durability boundaries. Recovery never infers a rollback
from a timeout and never adopts an unwitnessed successor. This is a custody door,
not session admission: the application must separately enforce current policy.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes

from .....application.user_profile.access_contracts import AuthorityState, ProfileAccessBinding
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationCustodySnapshot,
    AutomationGrantMaterial,
    AutomationSecretStore,
    NativeSecretBackend,
)
from .....application.user_profile.automation_enrollment import (
    EnrollmentControlState,
    EnrollmentGrant,
    EnrollmentRecord,
    EnrollmentStage,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
    AutomationDenialReceipt,
    ProfileGlobalLockState,
)
from .....core.base64_codec import b64_decode_canonical
from .....core.hashing import canonical_json_bytes, sha256_hex
from .....core.time.utc import UtcInstant
from .automation_crypto import (
    MAX_CONTROL_BYTES,
    api_key_verifier,
    canonical_record,
    open_automation,
    parse_record,
    seal_automation,
)
from .automation_profile import validate_automation_profile_binding
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
    AutomationRetirementIntent,
    ControlPublicationIntent,
    ControlWitness,
    ProfileGlobalLockRecord,
    ProtectedControlAnchor,
    SealedAutomationControl,
    StoredAutomationGrant,
)
from .automation_secret_store import native_automation_secret_store
from .automation_secret_target import AUTOMATION_NAMESPACE_PREFIX
from .errors import ProfileCustodyRecordError
from .filesystem import (
    clear_profile_custody_local_record,
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from .filesystem_primitives import anchor_directory, ensure_profile_custody_local_directory
from .zeroise import zeroise

CONTROL_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}control-anchor.v1"
WRAP_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}grant-wrap.v1"
CLIENT_NAMESPACE = f"{AUTOMATION_NAMESPACE_PREFIX}client-key.v1"


def _native_account(root: Path, installation_id: UUID, profile_id: UUID) -> str:
    """Name one profile's native credentials, scoped to the storage root they belong to."""
    root_digest = sha256_hex(str(root.resolve()).encode("utf-8"))
    return f"{root_digest}/{installation_id}/{profile_id}"


def _changed[T: BaseModel](value: T, **changes: object) -> T:
    model_type = value.__class__
    return model_type.model_validate({**{name: getattr(value, name) for name in model_type.model_fields}, **changes})


class AutomationControlStore:
    """One exact installation/profile binding and native-store dependency.

    Callers supply current identity from the trusted lifecycle owner. The store
    independently reads the committed password envelope and sentinel under the
    existing root lock. It never selects/unlocks the ambient human profile.
    """

    def __init__(
        self,
        *,
        root: Path,
        binding: ProfileAccessBinding,
        secrets_store: AutomationSecretStore | None = None,
        secrets_store_factory: Callable[[], AutomationSecretStore] | None = None,
    ) -> None:
        """Bind trusted composition to one local custody owner."""
        if (
            not root.is_absolute()
            or (secrets_store is None) == (secrets_store_factory is None)
            or (secrets_store_factory is not None and not callable(secrets_store_factory))
        ):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.root = root
        self.binding = binding
        self._secrets_lock = Lock()
        self._secrets_store: AutomationSecretStore | None = None
        self._secrets_store_factory = secrets_store_factory
        if secrets_store is not None:
            self.secrets = secrets_store
        self.directory = root / ".automation-v1" / str(binding.installation_id) / str(binding.profile_id)
        self.account = _native_account(root, binding.installation_id, binding.profile_id)

    @property
    def secrets(self) -> AutomationSecretStore:
        """Acquire optional native custody only when an automation operation needs it."""
        with self._secrets_lock:
            if self._secrets_store is None:
                factory = self._secrets_store_factory
                if factory is None:
                    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
                acquired = factory()
                if not isinstance(acquired.backend, NativeSecretBackend):
                    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
                self._secrets_store = acquired
            return self._secrets_store

    @secrets.setter
    def secrets(self, value: AutomationSecretStore) -> None:
        """Replace the native port supplied by trusted custody composition."""
        with self._secrets_lock:
            if not isinstance(value.backend, NativeSecretBackend):
                raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
            self._secrets_store = value

    def _prepare(self) -> None:
        self._prepare_directories()
        if self._read_file("retirement.json") is not None:
            AutomationControlStore.retire_directory(
                root=self.root, directory=self.directory, secrets_store=self.secrets
            )
        validate_automation_profile_binding(self.binding, root=self.root)

    def _prepare_directories(self) -> None:
        for path in (self.root / ".automation-v1", self.directory.parent, self.directory):
            ensure_profile_custody_local_directory(path)

    def _local_lock(self) -> ProfileGlobalLockRecord:
        raw = self._read_file("profile-lock.json")
        if raw is None:
            return ProfileGlobalLockRecord(binding=self.binding, generation=0, globally_locked=False)
        record = parse_record(ProfileGlobalLockRecord, raw)
        if record.binding != self.binding:
            # A password/recovery transition can finish while native retirement
            # remains pending. Old automation stays denied; fresh human custody
            # is independent. Never accept an unexplained identity mismatch.
            retirement = self._read_file("retirement.json")
            if retirement is None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            intent = parse_record(AutomationRetirementIntent, retirement)
            if (
                intent.profile_id != self.binding.profile_id
                or intent.installation_id != self.binding.installation_id
                or record.binding.profile_id != self.binding.profile_id
                or record.binding.installation_id != self.binding.installation_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            return ProfileGlobalLockRecord(binding=self.binding, generation=0, globally_locked=False)
        return record

    def _record_profile_lock(self, change: AutomationDenial) -> ProfileGlobalLockRecord:
        record = self._local_lock()
        if record.request_id != change.request_id:
            record = _changed(
                record, request_id=change.request_id, generation=record.generation + 1, globally_locked=True
            )
            self._write_file("profile-lock.json", canonical_record(record))
        return record

    def profile_lock_state(self) -> ProfileGlobalLockState:
        """Observe human-access fencing even while optional credentials are unavailable."""
        with profile_custody_root_lock(self.root):
            self._prepare_directories()
            validate_automation_profile_binding(self.binding, root=self.root)
            raw = self._read_file("denial.json")
            change = None if raw is None else parse_record(AutomationDenial, raw)
            record = self._local_lock()
            if (
                change is not None
                and change.binding == self.binding
                and change.kind is AutomationDenialKind.PROFILE_LOCK
            ):
                record = self._record_profile_lock(change)
            return ProfileGlobalLockState(
                binding=record.binding, generation=record.generation, globally_locked=record.globally_locked
            )

    def unlock_profile(self, *, generation: int) -> ProfileGlobalLockState:
        """CAS the human lock only; the caller must supply fresh password authority."""
        with profile_custody_root_lock(self.root):
            state = self.profile_lock_state()
            if state.generation != generation:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            record = _changed(self._local_lock(), globally_locked=False)
            self._write_file("profile-lock.json", canonical_record(record))
            return ProfileGlobalLockState(binding=self.binding, generation=generation, globally_locked=False)

    def _read_file(self, name: str) -> bytes | None:
        try:
            return read_optional_profile_custody_local_record(self.directory / name, maximum_bytes=MAX_CONTROL_BYTES)
        except ProfileCustodyRecordError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None

    def _write_file(self, name: str, raw: bytes, *, once: bool = False) -> None:
        if len(raw) > MAX_CONTROL_BYTES:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        write_profile_custody_local_record(self.directory / name, raw, publish_once=once)

    def _anchor(self) -> ProtectedControlAnchor | None:
        secret = self.secrets.read(CONTROL_NAMESPACE, self.account)
        if secret is None:
            return None
        anchor = parse_record(ProtectedControlAnchor, secret.get_secret_value())
        if anchor.binding != self.binding:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        self._control_key(anchor)
        return anchor

    @staticmethod
    def _control_key(anchor: ProtectedControlAnchor) -> SecretBytes:
        try:
            key = b64_decode_canonical(anchor.control_key_b64)
            if len(key) != 32:
                raise ValueError
            return SecretBytes(key)
        except ValueError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None

    def _aad(self, header: AutomationRecordHeader, grant_id: UUID | None = None) -> bytes:
        return canonical_json_bytes(
            {
                "purpose": "cadrumo.automation-dek/v1" if grant_id else header.purpose,
                "header": header.model_dump(mode="json"),
                "binding": self.binding.model_dump(mode="json"),
                "grant_id": None if grant_id is None else str(grant_id),
            }
        )

    def _load(self, anchor: ProtectedControlAnchor) -> tuple[AutomationRecordHeader, AutomationControlPayload]:
        witness = anchor.witness
        raw = self._read_file(f"{witness.record_id}.json")
        if raw is None or not secrets.compare_digest(sha256_hex(raw), witness.digest):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        sealed = parse_record(SealedAutomationControl, raw)
        header = sealed.header
        if (
            header.record_id != witness.record_id
            or header.revision != witness.revision
            or header.profile_id != self.binding.profile_id
            or header.installation_id != self.binding.installation_id
            or header.custody_generation != self.binding.custody_generation
            or header.dek_epoch != self.binding.dek_epoch
        ):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        payload = parse_record(
            AutomationControlPayload, open_automation(sealed.ciphertext, self._control_key(anchor), self._aad(header))
        )
        if payload.binding != self.binding:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return header, payload

    def _delete_wraps(self, identities: tuple[UUID, ...]) -> None:
        for identity in identities:
            account = self.account + "/" + str(identity)
            self.secrets.delete(WRAP_NAMESPACE, account)
            if self.secrets.read(WRAP_NAMESPACE, account) is not None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    def _recover(self) -> ProtectedControlAnchor | None:
        if self._read_file("denial.json") is not None:
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
        return self._recover_publication()

    def _recover_publication(self) -> ProtectedControlAnchor | None:
        anchor = self._anchor()
        raw_pointer = self._read_file("current.json")
        pointer = None if raw_pointer is None else parse_record(ControlWitness, raw_pointer)
        raw_intent = self._read_file("publication.json")
        if raw_intent is not None:
            intent = parse_record(ControlPublicationIntent, raw_intent)
            witness = None if anchor is None else anchor.witness
            if witness == intent.successor and anchor is not None:
                self._load(anchor)
                if pointer not in (None, intent.predecessor, intent.successor):
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID)
                self._write_file("current.json", canonical_record(anchor.witness))
                self._delete_wraps(intent.retired_wrap_keys)
            elif witness == intent.predecessor and pointer == intent.predecessor:
                if anchor is not None:
                    self._load(anchor)
                self._delete_wraps(intent.created_wrap_keys)
            else:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            clear_profile_custody_local_record(self.directory / "publication.json")
            pointer = witness
        if pointer != (None if anchor is None else anchor.witness):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return anchor

    def read(self) -> tuple[int, AutomationControlPayload]:
        """Read private current control state for the trusted application owner."""
        with profile_custody_root_lock(self.root):
            self._prepare()
            anchor = self._recover()
            if anchor is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            return anchor.witness.revision, self._load(anchor)[1]

    def snapshot(self) -> AutomationCustodySnapshot:
        """Expose verified application facts through the inward custody port."""
        revision, payload = self.read()
        return AutomationCustodySnapshot(
            revision=revision,
            binding=payload.binding,
            profile_lock_generation=payload.profile_lock_generation,
            automation_enabled=payload.automation_enabled,
            grants=tuple(item.grant for item in payload.grants),
            keys=tuple(key.key for item in payload.grants for key in item.keys),
        )

    def publish(
        self,
        *,
        grants: tuple[AutomationGrantMaterial, ...],
        expected_revision: int,
        profile_lock_generation: int,
        automation_enabled: bool,
        requests: tuple[EnrollmentRecord, ...] | None = None,
    ) -> int:
        """Publish custody only when no durable denial remains unresolved."""
        return self._publish(
            grants=grants,
            expected_revision=expected_revision,
            profile_lock_generation=profile_lock_generation,
            automation_enabled=automation_enabled,
            requests=requests,
        )

    def _publish(
        self,
        *,
        grants: tuple[AutomationGrantMaterial, ...],
        expected_revision: int,
        profile_lock_generation: int,
        automation_enabled: bool,
        requests: tuple[EnrollmentRecord, ...] | None,
        denial: AutomationDenial | None = None,
    ) -> int:
        """Publish reviewed custody facts; workflow consent/delivery remains separate.

        Every successor uses fresh separate per-grant keys and rewraps DEKs with
        its revision. Failure may leave a recoverable staged publication. Never
        report a failed native write as rollback or retry it without recovery.
        """
        with profile_custody_root_lock(self.root):
            self._prepare()
            previous = self._recover() if denial is None else self._recover_publication()
            revision = 0 if previous is None else previous.witness.revision
            if revision != expected_revision:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            old_payload = None if previous is None else self._load(previous)[1]
            if old_payload is not None and profile_lock_generation < old_payload.profile_lock_generation:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            header = AutomationRecordHeader(
                record_id=uuid4(),
                profile_id=self.binding.profile_id,
                installation_id=self.binding.installation_id,
                custody_generation=self.binding.custody_generation,
                dek_epoch=self.binding.dek_epoch,
                revision=revision + 1,
            )
            wraps: dict[UUID, SecretBytes] = {}
            entries: list[StoredAutomationGrant] = []
            for material in grants:
                if material.grant.state in {AuthorityState.SUSPENDED, AuthorityState.REVOKED}:
                    entries.append(
                        StoredAutomationGrant(
                            grant=material.grant, keys=material.keys, wrap_key_id=None, wrapped_dek=None
                        )
                    )
                    continue
                if material.dek is None:
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                validate_automation_profile_binding(self.binding, root=self.root, dek=material.dek.get_secret_value())
                identity, key = uuid4(), SecretBytes(secrets.token_bytes(32))
                wraps[identity] = key
                entries.append(
                    StoredAutomationGrant(
                        grant=material.grant,
                        keys=material.keys,
                        wrap_key_id=identity,
                        wrapped_dek=seal_automation(
                            material.dek.get_secret_value(), key, self._aad(header, material.grant.grant_id)
                        ),
                    )
                )
            payload = AutomationControlPayload(
                binding=self.binding,
                profile_lock_generation=profile_lock_generation,
                automation_enabled=automation_enabled,
                grants=tuple(entries),
                requests=requests if requests is not None else (() if old_payload is None else old_payload.requests),
                last_denial=denial
                if denial is not None
                else (None if old_payload is None else old_payload.last_denial),
            )
            control_key = SecretBytes(secrets.token_bytes(32)) if previous is None else self._control_key(previous)
            sealed = SealedAutomationControl(
                header=header, ciphertext=seal_automation(canonical_record(payload), control_key, self._aad(header))
            )
            raw = canonical_record(sealed)
            witness = ControlWitness(record_id=header.record_id, revision=header.revision, digest=sha256_hex(raw))
            intent = ControlPublicationIntent(
                predecessor=None if previous is None else previous.witness,
                successor=witness,
                created_wrap_keys=tuple(wraps),
                retired_wrap_keys=()
                if old_payload is None
                else tuple(item.wrap_key_id for item in old_payload.grants if item.wrap_key_id is not None),
            )
            self._write_file(f"{header.record_id}.json", raw, once=True)
            self._write_file("publication.json", canonical_record(intent))
            for identity, key in wraps.items():
                account = self.account + "/" + str(identity)
                self.secrets.replace(WRAP_NAMESPACE, account, key)
                observed = self.secrets.read(WRAP_NAMESPACE, account)
                if observed is None or not secrets.compare_digest(observed.get_secret_value(), key.get_secret_value()):
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            anchor = ProtectedControlAnchor(
                binding=self.binding,
                witness=witness,
                control_key_b64=base64.b64encode(control_key.get_secret_value()).decode("ascii"),
            )
            self.secrets.replace(CONTROL_NAMESPACE, self.account, SecretBytes(canonical_record(anchor)))
            if self._anchor() != anchor:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            self._recover_publication()
            return header.revision

    def enrollment_state(self) -> EnrollmentControlState:
        """Read verified administration facts without releasing DEKs or native keys."""
        with profile_custody_root_lock(self.root):
            self._prepare()
            anchor = self._recover()
            payload = None if anchor is None else self._load(anchor)[1]
            return EnrollmentControlState(
                revision=0 if anchor is None else anchor.witness.revision,
                binding=self.binding,
                profile_lock_generation=0 if payload is None else payload.profile_lock_generation,
                automation_enabled=True if payload is None else payload.automation_enabled,
                grants=()
                if payload is None
                else tuple(EnrollmentGrant(grant=item.grant, keys=item.keys) for item in payload.grants),
                requests=() if payload is None else payload.requests,
            )

    def publish_enrollment(self, state: EnrollmentControlState, *, fresh_dek: SecretBytes | None = None) -> int:
        """CAS administration facts without bypassing a surviving denial."""
        return self._publish_enrollment(state, fresh_dek=fresh_dek)

    def _publish_enrollment(
        self,
        state: EnrollmentControlState,
        *,
        fresh_dek: SecretBytes | None = None,
        denial: AutomationDenial | None = None,
    ) -> int:
        """CAS enrollment alongside grants using the existing staged publication.

        Existing grant DEKs are rewrapped inside custody. A new grant requires a
        fresh password-proven DEK. Filesystem and native writes remain separate
        durability boundaries, and the same recovery witness chooses the winner.
        """
        with profile_custody_root_lock(self.root):
            self._prepare()
            anchor = self._recover() if denial is None else self._recover_publication()
            revision = 0 if anchor is None else anchor.witness.revision
            if state.binding != self.binding or state.revision != revision:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            previous = None if anchor is None else self._load(anchor)
            materials: list[AutomationGrantMaterial] = []
            for entry in state.grants:
                if entry.grant.state in {AuthorityState.SUSPENDED, AuthorityState.REVOKED}:
                    materials.append(AutomationGrantMaterial(grant=entry.grant, keys=entry.keys, dek=None))
                    continue
                old = (
                    None
                    if previous is None
                    else next(
                        (item for item in previous[1].grants if item.grant.grant_id == entry.grant.grant_id), None
                    )
                )
                dek = fresh_dek
                if (
                    dek is None
                    and old is not None
                    and previous is not None
                    and old.wrap_key_id is not None
                    and old.wrapped_dek is not None
                ):
                    key = self.secrets.read(WRAP_NAMESPACE, self.account + "/" + str(old.wrap_key_id))
                    if key is None:
                        raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                    dek = SecretBytes(open_automation(old.wrapped_dek, key, self._aad(previous[0], old.grant.grant_id)))
                if dek is None:
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                materials.append(AutomationGrantMaterial(grant=entry.grant, keys=entry.keys, dek=dek))
            return self._publish(
                grants=tuple(materials),
                expected_revision=revision,
                profile_lock_generation=state.profile_lock_generation,
                automation_enabled=state.automation_enabled,
                requests=state.requests,
                denial=denial,
            )

    def deny(self, change: AutomationDenial) -> AutomationDenialReceipt:
        """Fence durably before attempting native reads, updates or deletion.

        Until protected publication and cleanup both complete, every ordinary
        custody door refuses. Password authentication uses its independent door.
        """
        with profile_custody_root_lock(self.root):
            self._prepare()
            if change.binding != self.binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            raw = self._read_file("denial.json")
            if raw is not None and parse_record(AutomationDenial, raw) != change:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._write_file("denial.json", canonical_record(change))
            if change.kind is AutomationDenialKind.PROFILE_LOCK:
                self._record_profile_lock(change)
            return self._finish_denial(change)

    def reconcile_denial(self) -> AutomationDenialReceipt | None:
        """Retry only the surviving exact change; missing means no pending denial."""
        with profile_custody_root_lock(self.root):
            self._prepare()
            raw = self._read_file("denial.json")
            return None if raw is None else self._finish_denial(parse_record(AutomationDenial, raw))

    def _finish_denial(self, change: AutomationDenial) -> AutomationDenialReceipt:
        revision, generation = None, None
        try:
            if change.binding != self.binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            if change.kind is AutomationDenialKind.PROFILE_LOCK:
                generation = self._record_profile_lock(change).generation
            anchor = self._recover_publication()
            payload = None if anchor is None else self._load(anchor)[1]
            if payload is None or payload.last_denial != change:
                state = self._denied_state(change, anchor, payload)
                revision = self._publish_enrollment(state, denial=change)
                generation = state.profile_lock_generation
            else:
                revision = anchor.witness.revision if anchor is not None else None
                generation = payload.profile_lock_generation
            clear_profile_custody_local_record(self.directory / "denial.json")
        except AutomationCustodyError:
            return AutomationDenialReceipt(
                request_id=change.request_id,
                profile_id=self.binding.profile_id,
                access_denied=True,
                cleanup_pending=True,
                revision=revision,
                profile_lock_generation=generation,
            )
        return AutomationDenialReceipt(
            request_id=change.request_id,
            profile_id=self.binding.profile_id,
            access_denied=True,
            cleanup_pending=False,
            revision=revision,
            profile_lock_generation=generation,
        )

    def _denied_state(
        self,
        change: AutomationDenial,
        anchor: ProtectedControlAnchor | None,
        payload: AutomationControlPayload | None,
    ) -> EnrollmentControlState:
        locking = change.kind is AutomationDenialKind.PROFILE_LOCK
        generation = (
            self._local_lock().generation if locking else (0 if payload is None else payload.profile_lock_generation)
        )
        if payload is not None and generation < payload.profile_lock_generation:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        entries: list[EnrollmentGrant] = []
        for stored in () if payload is None else payload.grants:
            grant, keys = stored.grant, stored.keys
            affected = change.kind in {AutomationDenialKind.ALL, AutomationDenialKind.PROFILE_LOCK} or (
                change.kind is AutomationDenialKind.GRANT and change.target_id == grant.grant_id
            )
            if affected:
                # Incomplete enrollment can never become active through unlock.
                state = (
                    AuthorityState.SUSPENDED
                    if locking and grant.state in {AuthorityState.ACTIVE, AuthorityState.SUSPENDED}
                    else AuthorityState.REVOKED
                )
                if grant.state is AuthorityState.REVOKED:
                    state = AuthorityState.REVOKED
                grant = _changed(grant, state=state, generation=grant.generation + 1)
                keys = tuple(
                    _changed(
                        item,
                        key=_changed(
                            item.key,
                            state=AuthorityState.SUSPENDED
                            if state is AuthorityState.SUSPENDED
                            and item.key.state in {AuthorityState.ACTIVE, AuthorityState.SUSPENDED}
                            else AuthorityState.REVOKED,
                            generation=item.key.generation + 1,
                        ),
                    )
                    for item in keys
                )
            elif change.kind is AutomationDenialKind.KEY:
                keys = tuple(
                    _changed(
                        item, key=_changed(item.key, state=AuthorityState.REVOKED, generation=item.key.generation + 1)
                    )
                    if item.key.key_id == change.target_id
                    else item
                    for item in keys
                )
                if grant.unattended and keys and all(item.key.state is AuthorityState.REVOKED for item in keys):
                    grant = _changed(grant, state=AuthorityState.REVOKED, generation=grant.generation + 1)
            entries.append(EnrollmentGrant(grant=grant, keys=keys))
        return EnrollmentControlState(
            revision=0 if anchor is None else anchor.witness.revision,
            binding=self.binding,
            profile_lock_generation=generation,
            automation_enabled=not locking and (payload is None or payload.automation_enabled),
            grants=tuple(entries),
            requests=()
            if payload is None
            else tuple(
                _changed(item, stage=EnrollmentStage.DECLINED) if item.stage is not EnrollmentStage.COMPLETE else item
                for item in payload.requests
            ),
        )

    @staticmethod
    def retire_directory(*, root: Path, directory: Path, secrets_store: AutomationSecretStore) -> None:
        """Finish a durable lifecycle denial, without requiring a surviving capsule."""
        raw = read_optional_profile_custody_local_record(directory / "retirement.json", maximum_bytes=MAX_CONTROL_BYTES)
        if raw is None:
            return
        intent = parse_record(AutomationRetirementIntent, raw)
        if directory != root / ".automation-v1" / str(intent.installation_id) / str(intent.profile_id):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        account = _native_account(root, intent.installation_id, intent.profile_id)
        protected = secrets_store.read(CONTROL_NAMESPACE, account)
        wraps: set[UUID] = set()
        if protected is not None:
            anchor = parse_record(ProtectedControlAnchor, protected.get_secret_value())
            if (
                anchor.binding.profile_id != intent.profile_id
                or anchor.binding.installation_id != intent.installation_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            old = AutomationControlStore(root=root, binding=anchor.binding, secrets_store=secrets_store)
            # The old envelope may already have changed or been deleted. Cleanup
            # authenticates the control witness; it never unwraps a profile DEK.
            payload = old._load(anchor)[1]
            wraps.update(entry.wrap_key_id for entry in payload.grants if entry.wrap_key_id is not None)
        publication = read_optional_profile_custody_local_record(
            directory / "publication.json", maximum_bytes=MAX_CONTROL_BYTES
        )
        if publication is not None:
            pending = parse_record(ControlPublicationIntent, publication)
            wraps.update(pending.created_wrap_keys)
            wraps.update(pending.retired_wrap_keys)
        for identity in wraps:
            target = account + "/" + str(identity)
            secrets_store.delete(WRAP_NAMESPACE, target)
            if secrets_store.read(WRAP_NAMESPACE, target) is not None:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        secrets_store.delete(CONTROL_NAMESPACE, account)
        if secrets_store.read(CONTROL_NAMESPACE, account) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        for name in ("current.json", "publication.json", "denial.json", "profile-lock.json", "retirement.json"):
            clear_profile_custody_local_record(directory / name)

    @contextmanager
    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> Generator[bytearray]:
        """Lend verified material, wiping the mutable buffer on success or failure."""
        material = self.unwrap(credential=credential, now=now)
        try:
            yield material
        finally:
            zeroise(material)

    def unwrap(self, *, credential: SecretBytes, now: UtcInstant) -> bytearray:
        """Return a wipeable DEK only after credential, control and sentinel proof.

        Does not admit a connection or grant operation authority. The lifecycle
        owner must evaluate login eligibility and session policy separately.
        """
        key_id, verifier = api_key_verifier(credential)
        with profile_custody_root_lock(self.root):
            self._prepare()
            if self._local_lock().globally_locked:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            anchor = self._recover()
            if anchor is None:
                raise AutomationCustodyError(AutomationCustodyCode.MISSING)
            header, payload = self._load(anchor)
            for entry in payload.grants:
                for item in entry.keys:
                    if item.key.key_id != key_id:
                        continue
                    grant, key = entry.grant, item.key
                    if (
                        not secrets.compare_digest(verifier, item.verifier)
                        or not payload.automation_enabled
                        or not grant.unattended
                        or grant.state is not AuthorityState.ACTIVE
                        or key.state is not AuthorityState.ACTIVE
                        or grant.profile_lock_generation != payload.profile_lock_generation
                        or not grant.valid_from <= now < grant.expires_at
                        or not key.valid_from <= now < key.expires_at
                        or entry.wrap_key_id is None
                        or entry.wrapped_dek is None
                    ):
                        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                    wrapping_key = self.secrets.read(WRAP_NAMESPACE, self.account + "/" + str(entry.wrap_key_id))
                    if wrapping_key is None:
                        raise AutomationCustodyError(AutomationCustodyCode.MISSING)
                    dek = bytearray(open_automation(entry.wrapped_dek, wrapping_key, self._aad(header, grant.grant_id)))
                    try:
                        validate_automation_profile_binding(self.binding, root=self.root, dek=bytes(dek))
                    except BaseException:
                        zeroise(dek)
                        raise
                    return dek
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)


def retire_profile_automation(
    *, root: Path, profile_id: UUID, secrets_store: AutomationSecretStore | None = None
) -> bool:
    """Durably deny every local installation before a profile custody transition.

    Return whether native cleanup finished. Failure of optional native facilities
    leaves denial intents, allowing the password/recovery/delete transition to
    proceed. Failure to persist denial propagates before the transition commits.
    Portable capsules never include this external installation custody.
    """
    with profile_custody_root_lock(root), ExitStack() as anchors:
        base = root / ".automation-v1"
        if not os.path.lexists(base):
            return True
        anchor_directory(anchors, base)
        directories: list[Path] = []
        for installation in base.iterdir():
            try:
                installation_id = UUID(installation.name)
            except ValueError:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
            if str(installation_id) != installation.name:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            anchor_directory(anchors, installation)
            directory = installation / str(profile_id)
            if not os.path.lexists(directory):
                continue
            anchor_directory(anchors, directory)
            write_profile_custody_local_record(
                directory / "retirement.json",
                canonical_record(AutomationRetirementIntent(profile_id=profile_id, installation_id=installation_id)),
                publish_once=False,
            )
            directories.append(directory)
        if not directories:
            return True
        try:
            backend = {
                "win32": NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER,
                "darwin": NativeSecretBackend.MACOS_KEYCHAIN,
                "linux": NativeSecretBackend.LINUX_DBUS,
            }.get(sys.platform)
            if secrets_store is None:
                if backend is None:
                    return False
                secrets_store = native_automation_secret_store(backend)
            for directory in directories:
                AutomationControlStore.retire_directory(root=root, directory=directory, secrets_store=secrets_store)
        except AutomationCustodyError:
            return False
        return True

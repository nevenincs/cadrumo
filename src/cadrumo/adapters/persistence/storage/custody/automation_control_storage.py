"""AutomationControlStorage for exact witnessed profile automation custody."""

from __future__ import annotations

import secrets
from pathlib import Path
from uuid import UUID

from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from .....core.base64_codec import b64_decode_canonical
from .....core.hashing import canonical_json_bytes, sha256_hex
from .automation_crypto import (
    MAX_CONTROL_BYTES,
    open_automation,
    parse_record,
)
from .automation_native_binding import AutomationNativeBinding
from .automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE, automation_native_account
from .automation_profile import validate_automation_profile_binding
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
    AutomationRetirementIntent,
    ControlPublicationIntent,
    ProtectedControlAnchor,
    SealedAutomationControl,
)
from .automation_retirement_io import clear_retired_control_files, retire_wrap_keys
from .errors import ProfileCustodyRecordError
from .filesystem import (
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from .filesystem_primitives import ensure_profile_custody_local_directory


class AutomationControlStorage(AutomationNativeBinding):
    """Own the native custody stages for this capability."""

    def _prepare(self) -> None:
        self._prepare_directories()
        if self._read_file("retirement.json") is not None:
            AutomationControlStorage.retire_directory(
                root=self.root, directory=self.directory, secrets_store=self.secrets
            )
        validate_automation_profile_binding(self.binding, root=self.root)

    def _prepare_directories(self) -> None:
        for path in (self.root / ".automation-v1", self.directory.parent, self.directory):
            ensure_profile_custody_local_directory(path)

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

    @staticmethod
    def retire_directory(*, root: Path, directory: Path, secrets_store: AutomationSecretStore) -> None:
        """Finish a durable lifecycle denial, without requiring a surviving capsule."""
        raw = read_optional_profile_custody_local_record(directory / "retirement.json", maximum_bytes=MAX_CONTROL_BYTES)
        if raw is None:
            return
        intent = parse_record(AutomationRetirementIntent, raw)
        if directory != root / ".automation-v1" / str(intent.installation_id) / str(intent.profile_id):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        account = automation_native_account(root, intent.installation_id, intent.profile_id)
        protected = secrets_store.read(CONTROL_NAMESPACE, account)
        wraps: set[UUID] = set()
        if protected is not None:
            anchor = parse_record(ProtectedControlAnchor, protected.get_secret_value())
            if (
                anchor.binding.profile_id != intent.profile_id
                or anchor.binding.installation_id != intent.installation_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
            old = AutomationControlStorage(root=root, binding=anchor.binding, secrets_store=secrets_store)
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
        retire_wrap_keys(secrets_store, account, wraps)
        secrets_store.delete(CONTROL_NAMESPACE, account)
        if secrets_store.read(CONTROL_NAMESPACE, account) is not None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        clear_retired_control_files(directory)

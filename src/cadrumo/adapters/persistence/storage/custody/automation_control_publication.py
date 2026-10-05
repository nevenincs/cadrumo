"""AutomationControlPublication for exact witnessed profile automation custody."""

from __future__ import annotations

import base64
import secrets
from uuid import UUID, uuid4

from pydantic import SecretBytes

from .....application.user_profile.access_contracts import (
    AuthorityState,
)
from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationCustodySnapshot,
    AutomationGrantMaterial,
)
from .....application.user_profile.automation_enrollment import (
    EnrollmentRecord,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
)
from .....core.hashing import sha256_hex
from .automation_control_projection import publication_intent, publication_payload
from .automation_crypto import (
    canonical_record,
    parse_record,
    seal_automation,
)
from .automation_native_identity import CONTROL_NAMESPACE, WRAP_NAMESPACE
from .automation_profile import validate_automation_profile_binding
from .automation_profile_lock import AutomationProfileLock
from .automation_records import (
    AutomationControlPayload,
    AutomationRecordHeader,
    ControlPublicationIntent,
    ControlWitness,
    ProtectedControlAnchor,
    SealedAutomationControl,
    StoredAutomationGrant,
)
from .filesystem import (
    clear_profile_custody_local_record,
    profile_custody_root_lock,
)


class AutomationControlPublication(AutomationProfileLock):
    """Own the native custody stages for this capability."""

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
            pointer = self._reconcile_publication_intent(anchor, pointer, raw_intent)
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
            wraps, entries = self._wrapped_grant_entries(grants, header)
            payload = publication_payload(
                self.binding, profile_lock_generation, automation_enabled, entries, requests, old_payload, denial
            )
            control_key = SecretBytes(secrets.token_bytes(32)) if previous is None else self._control_key(previous)
            sealed = SealedAutomationControl(
                header=header, ciphertext=seal_automation(canonical_record(payload), control_key, self._aad(header))
            )
            raw = canonical_record(sealed)
            witness = ControlWitness(record_id=header.record_id, revision=header.revision, digest=sha256_hex(raw))
            intent = publication_intent(previous, witness, wraps, old_payload)
            self._write_file(f"{header.record_id}.json", raw, once=True)
            self._write_file("publication.json", canonical_record(intent))
            self._publish_wrap_keys(wraps)
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

    def _wrapped_grant_entries(
        self,
        grants: tuple[AutomationGrantMaterial, ...],
        header: AutomationRecordHeader,
    ) -> tuple[dict[UUID, SecretBytes], list[StoredAutomationGrant]]:
        """Prepare fresh per-grant wrappers after current profile identity is proven."""
        wraps: dict[UUID, SecretBytes] = {}
        entries: list[StoredAutomationGrant] = []
        for material in grants:
            if material.grant.state in {AuthorityState.SUSPENDED, AuthorityState.REVOKED}:
                entries.append(
                    StoredAutomationGrant(grant=material.grant, keys=material.keys, wrap_key_id=None, wrapped_dek=None)
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
        return wraps, entries

    def _publish_wrap_keys(self, wraps: dict[UUID, SecretBytes]) -> None:
        """Read back each native key in the original staged publication order."""
        for identity, key in wraps.items():
            account = self.account + "/" + str(identity)
            self.secrets.replace(WRAP_NAMESPACE, account, key)
            observed = self.secrets.read(WRAP_NAMESPACE, account)
            if observed is None or not secrets.compare_digest(observed.get_secret_value(), key.get_secret_value()):
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    def _reconcile_publication_intent(
        self,
        anchor: ProtectedControlAnchor | None,
        pointer: ControlWitness | None,
        raw_intent: bytes,
    ) -> ControlWitness | None:
        """Recover only the native-witnessed successor or exact unchanged predecessor."""
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
        return witness

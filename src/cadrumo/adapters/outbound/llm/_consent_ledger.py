"""The off-host evidence-consent audit ledger.

Persists one :class:`~domain.evidence_consent.EvidenceConsentLedgerEntry` per
off-host evidence dispatch that a consent token permitted, to encrypted
secure-object storage under
:data:`~adapters.persistence.storage.LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE`.
The entry is appended by :class:`~llm.LLMClient` at the same
choke point that HONOURS the token, before the cache read and before any
adapter exists, so a dispatch that cannot append refuses rather than
transmitting unrecorded. Completeness is therefore a property of the code path
rather than of a caller remembering to log.

**It records that a transmission was consented, never what was transmitted.**
The entry carries the evidence's SHA-256 content ADDRESS, the resolved provider
and model, the operator surface that took the acknowledgement, and the
timestamp -- never the document bytes, the prompt, or the response. That is the
same "the address, never the bytes" line
:class:`~llm.EvidenceConsentToken` already draws, and it is what keeps the audit
trail from becoming a second copy of the confidentiality problem it exists to
document.

**It is deliberately not pruned.** Its three sibling LLM stores (cache, usage,
run-telemetry) are swept by
:meth:`~llm.LLMClient._sweep_retention_stores` because they
are diagnostic and regenerable. This one is neither: a consent withdrawal reads
it to enumerate which artefacts depend on a cloud read, so an entry aged out of
existence would make that withdrawal silently incomplete.

See Also:
    :func:`~llm.cloud_evidence_read_permitted`
        The gate whose honoured decisions this ledger records.
    :class:`~llm.EvidenceConsentToken`
        The per-invocation carrier proving the gate ran; never persisted
        itself, its two fields are copied into the entry.
    :data:`~adapters.persistence.storage.LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE`
        Secure-object namespace used for the encrypted local store.
    :mod:`~domain.evidence_consent`
        Owns the entry's record shape and its natural key grammar, so a
        consumer inside the application layer can recover a stored row's key
        without importing this outbound adapter.
"""

from __future__ import annotations

import json
from uuid import uuid4

from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import canonical_json_bytes
from ....core.time.clock import now
from ....domain.evidence_consent._record import EvidenceConsentLedgerEntry, evidence_consent_ledger_entry_object_key
from ....llm.errors import LLMConsentError
from ...persistence.storage._secure_object_namespaces import LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE
from ...persistence.storage.master_key.active_session import current_active_bucket_session
from ...persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

__all__ = ["EvidenceConsentLedger"]

_NAMESPACE = LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.namespace
_VERSION = LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.schema_version
_SENSITIVITY = LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.sensitivity


class EvidenceConsentLedger:
    """Append-and-read access to the off-host evidence-consent audit trail.

    :meth:`append` is called from the dispatch choke point and raises on ANY
    failure, so the caller's refusal is the only possible outcome of a failed
    write. That is the opposite of
    :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.record`'s
    best-effort posture, and deliberately: run-telemetry losing a row costs a
    diagnostic, this losing a row costs the audit trail its completeness claim.
    """

    def append(
        self,
        *,
        evidence_content_address: str,
        provider: str,
        model: str,
        surface: str,
    ) -> EvidenceConsentLedgerEntry:
        """Record one honoured off-host consent decision.

        Args:
            evidence_content_address: SHA-256 content address from the token.
            provider: Resolved off-host provider label.
            model: Resolved model identifier.
            surface: Operator surface that took the acknowledgement.

        Returns:
            The appended :class:`EvidenceConsentLedgerEntry`.

        Raises:
            LLMConsentError: When no bucket session is bound (nothing to record
                against) or the encrypted write fails. The caller MUST let this
                propagate: an unrecorded off-host dispatch is exactly what this
                ledger exists to make impossible.
        """
        session = current_active_bucket_session()
        if session is None:
            msg = (
                "Cannot record an off-host evidence-consent entry: no profile bucket session is open, "
                "so the consented dispatch would leave no audit trail."
            )
            raise LLMConsentError(msg)
        entry = EvidenceConsentLedgerEntry(
            entry_id=uuid4().hex,
            profile_bucket_id=session.bucket_id,
            evidence_content_address=evidence_content_address,
            provider=provider,
            model=model,
            surface=surface,
            recorded_at=now(),
        )
        try:
            secure_object_repository_for_active_bucket().save(
                namespace=_NAMESPACE,
                object_key=evidence_consent_ledger_entry_object_key(entry),
                classification=_SENSITIVITY,
                schema_version=_VERSION,
                written_at=entry.recorded_at,
                payload=canonical_json_bytes({"entry": entry.model_dump(mode="json")}),
            )
        except Exception as exc:  # any storage failure must refuse the dispatch, never degrade it
            msg = (
                "Failed to record the off-host evidence-consent entry; the dispatch is refused rather "
                "than transmitted without an audit trail."
            )
            raise LLMConsentError(msg) from exc
        return entry

    def load_entries(self) -> tuple[EvidenceConsentLedgerEntry, ...]:
        """Load every consent entry for the active profile, oldest first.

        Returns:
            The profile's consent history, the enumeration a withdrawal reads.
        """
        entries = [
            # ``model_validate_json`` rather than ``model_validate``: the model is
            # strict, so a round-tripped ISO timestamp is a `str` the object form
            # rejects but the JSON form parses.
            EvidenceConsentLedgerEntry.model_validate_json(
                json.dumps(json.loads(stored.payload.decode(UTF_8_ENCODING))["entry"]),
            )
            for stored in secure_object_repository_for_active_bucket().list_records(
                _NAMESPACE,
                expected_class=_SENSITIVITY,
                max_supported_version=_VERSION,
            )
        ]
        return tuple(sorted(entries, key=lambda entry: (entry.recorded_at, entry.entry_id)))

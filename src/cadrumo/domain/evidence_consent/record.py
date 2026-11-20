"""The off-host evidence-consent audit record and its natural key grammar.

Owns the shape of one recorded consent decision and the object key it is stored
under. Both are pure data: the record carries no persistence, and the key
function is a total function of the record's own fields, so the application
layer can recover a stored row's natural key without reaching into the outbound
adapter that writes it.

**The record documents that a transmission was consented, never what was
transmitted.** It carries the evidence's SHA-256 content ADDRESS, the resolved
provider and model, the operator surface that took the acknowledgement, and the
timestamp -- never the document bytes, the prompt, or the response. That is the
same "the address, never the bytes" line the consent token itself draws, and it
is what keeps the audit trail from becoming a second copy of the
confidentiality problem it exists to document.

**The same ledger records a person's standing grants and their revocation.**
A dispatch entry records one honoured transmission. A grant entry records the
person's consent to off-host reads of one task kind on one lane, for one job,
for the agent session it was given in, or until revoked; a revocation entry
withdraws a grant from the next read onwards. Grant and revocation entries name
no document: their content address is the digest of the grant's own binding,
so the ledger keeps one key grammar for every row.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import UtcInstant
from ..transactions.classification_job import ClassificationConsentScope

__all__ = [
    "EvidenceConsentGrantTerms",
    "EvidenceConsentLedgerEntry",
    "EvidenceConsentRecordKind",
    "evidence_consent_grant_address",
    "evidence_consent_ledger_entry_object_key",
]

_Token = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class EvidenceConsentRecordKind(StrEnum):
    """What one ledger row records."""

    DISPATCH = "dispatch"
    """One off-host transmission a consent permitted."""
    GRANT = "grant"
    """A person's consent to off-host reads of one task kind on one lane."""
    REVOCATION = "revocation"
    """The person withdrew a grant; it covers no read from then on."""


class EvidenceConsentGrantTerms(BaseModel):
    """What a person's grant covers: one task kind on one lane, for one scope.

    ``job_id`` binds a grant of scope once to the one job it was given for.
    ``session_reference`` binds a grant of scope agent session to the profile
    session it was given in; it is a digest of that session's identity, never
    the session itself. A remembered grant names neither and lasts until it is
    revoked.
    """

    model_config = STRICT_FROZEN_CONFIG

    grant_id: Hex64Str
    scope: ClassificationConsentScope
    task_kind: _Token
    transport: _Token
    job_id: Hex64Str | None = None
    session_reference: Hex64Str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _binding_matches_scope(self) -> Self:
        if (self.scope is ClassificationConsentScope.ONCE) != (self.job_id is not None):
            raise CoreValidationError("only a grant for one job names the job")
        if (self.scope is ClassificationConsentScope.AGENT_SESSION) != (self.session_reference is not None):
            raise CoreValidationError("only a grant for the agent session names the session")
        return self


class EvidenceConsentLedgerEntry(BaseModel):
    """One consented off-host evidence dispatch, recorded for later audit.

    Every field is metadata ABOUT the transmission. Nothing here reconstructs
    the document: ``evidence_content_address`` is a digest, and there is no
    field for prompt or response text.
    """

    model_config = STRICT_FROZEN_CONFIG

    entry_id: str = Field(min_length=1, description="Stable id for this ledger entry (a UUID4 hex).")
    profile_bucket_id: BucketId
    evidence_content_address: str = Field(
        min_length=1,
        description="SHA-256 content address of the evidence the acknowledgement covered.",
    )
    provider: str = Field(min_length=1, description="Resolved off-host provider the request dispatched at.")
    model: str = Field(min_length=1, description="Resolved model identifier the request dispatched at.")
    surface: str = Field(min_length=1, description="Operator surface that took the acknowledgement.")
    recorded_at: UtcInstant = Field(description="UTC timestamp the consent was honoured.")
    record_kind: EvidenceConsentRecordKind = EvidenceConsentRecordKind.DISPATCH
    grant: EvidenceConsentGrantTerms | None = Field(
        default=None, description="The terms a grant entry records; absent on every other entry."
    )
    revoked_grant_id: Hex64Str | None = Field(
        default=None, description="The grant a revocation entry withdraws; absent on every other entry."
    )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _kind_matches_fields(self) -> Self:
        if (self.record_kind is EvidenceConsentRecordKind.GRANT) != (self.grant is not None):
            raise CoreValidationError("only a grant entry carries grant terms")
        if (self.record_kind is EvidenceConsentRecordKind.REVOCATION) != (self.revoked_grant_id is not None):
            raise CoreValidationError("only a revocation entry names the grant it withdraws")
        return self


def evidence_consent_grant_address(
    *, profile_bucket_id: str, provider: str, model: str, grant: EvidenceConsentGrantTerms
) -> str:
    """Return the content address a grant or its revocation is recorded under: the digest of the grant's binding.

    A grant names no document, so the address it is keyed by is its own
    binding: the profile, the lane and the terms. It names nothing the person
    read and nothing a model was sent.
    """
    return sha256_hex(
        canonical_json_bytes(
            {
                "profile_bucket_id": profile_bucket_id,
                "provider": provider,
                "model": model,
                "grant": grant.model_dump(mode="json"),
            }
        )
    )


def evidence_consent_ledger_entry_object_key(entry: EvidenceConsentLedgerEntry) -> str:
    """Return the unique natural key one consent entry is saved under.

    The grammar lives beside the record rather than beside the store, so the
    writer and the custody carry that must recover the same key read one
    authority instead of re-deriving it a second time on either side of the
    persistence boundary.
    """
    return "|".join((entry.recorded_at.isoformat(), entry.evidence_content_address, entry.entry_id))

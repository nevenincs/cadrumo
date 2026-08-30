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
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.identity import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time import UtcInstant

__all__ = ["EvidenceConsentLedgerEntry", "evidence_consent_ledger_entry_object_key"]



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


def evidence_consent_ledger_entry_object_key(entry: EvidenceConsentLedgerEntry) -> str:
    """Return the unique natural key one consent entry is saved under.

    The grammar lives beside the record rather than beside the store, so the
    writer and the custody carry that must recover the same key read one
    authority instead of re-deriving it a second time on either side of the
    persistence boundary.
    """
    return "|".join((entry.recorded_at.isoformat(), entry.evidence_content_address, entry.entry_id))

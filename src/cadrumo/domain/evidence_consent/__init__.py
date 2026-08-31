"""Public facade for the off-host evidence-consent audit record.

This package owns the RECORD SHAPE of one honoured consent decision --
:class:`EvidenceConsentLedgerEntry` -- and the natural key it is stored under,
:func:`evidence_consent_ledger_entry_object_key`. It owns nothing else: the
encrypted append-and-read store is
:class:`adapters.outbound.llm.EvidenceConsentLedger`, the per-invocation
consent carrier is :class:`llm.EvidenceConsentToken`, and the gate whose
honoured decisions produce these rows is :func:`llm.cloud_evidence_read_permitted`.

Splitting the record from its store is what lets the profile custody carry
recover a decrypted row's natural key while staying inside the application
layer: the key grammar is a pure function of the record, so no consumer needs
the outbound adapter to derive it.

The store is deliberately not pruned. Its sibling LLM stores (cache, usage,
run-telemetry) are swept on retention because they are diagnostic and
regenerable; this one is neither, because a consent withdrawal reads it to
enumerate which artefacts depend on a cloud read, and an entry aged out of
existence would make that withdrawal silently incomplete.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()

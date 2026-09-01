"""The persistence-backed stores that sit beside an outbound model-provider call.

The ``__all__`` contract of this package is four encrypted stores and the two
record types the telemetry store produces -- nothing else. The completion
surface itself lives in :mod:`llm`: :class:`~llm.LLMClient` and its
:class:`~llm.LLMRequest` / :class:`~llm.LLMResponse` records, the
:class:`~llm.LLMProvider` enum, the prompt registry, the strict model types,
the PDF rasterisation helper and the error hierarchy are all imported from
there, not from here.

:class:`LLMCache` derives a content address from request content and provider
and serves a repeat completion without a provider call. Entries are encrypted
secure objects classified ``DIAGNOSTIC``, never plaintext files.

:class:`UsageRecorder` persists per-call usage and cost to the same encrypted
backend, routed through the structured redaction pass first, so NIFs and
bearer-shaped tokens never reach storage.

:class:`LLMRunTelemetryRecorder` persists one local-only :class:`LLMRunRecord`
per invocation -- provider label, duration, success flag, optional error kind,
and never prompt or response text -- and folds them into
:class:`LLMRunTelemetrySummary` reports backing the
``aeat app diagnostics run-health`` operator surface. It has no network
transport of any kind.

:class:`EvidenceConsentLedger` appends one
:class:`domain.evidence_consent.EvidenceConsentLedgerEntry` per off-host
evidence dispatch a consent token permitted -- the content address, provider,
model and surface, never the bytes -- and is the only one of these four stores
that refuses rather than degrading when its write fails, so an unrecordable
dispatch does not transmit. The entry's record shape and natural key grammar
are owned by :mod:`domain.evidence_consent`, not re-exported here.

Every store resolves the active profile bucket's encrypted secure-object
repository at each read and write rather than holding one, so a store is
constructed from a settings-derived partition alone while its operations
require a live bucket session. Importing this outbound adapter must remain
silent.
"""

from .cache import LLMCache
from .consent_ledger import EvidenceConsentLedger
from .run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder, LLMRunTelemetrySummary
from .usage import UsageRecorder

__all__ = [
    "EvidenceConsentLedger",
    "LLMCache",
    "LLMRunRecord",
    "LLMRunTelemetryRecorder",
    "LLMRunTelemetrySummary",
    "UsageRecorder",
]

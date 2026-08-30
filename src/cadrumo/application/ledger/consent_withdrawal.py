"""Consent withdrawal: what it can undo, what it cannot, and the way back on-host.

Withdrawing consent for off-host evidence reading cannot recall bytes that were
already transmitted. No verb in this product can, and a surface that implies
otherwise is worse than no surface at all, because an operator would act on a
guarantee that does not exist. What withdrawal actually does is three things,
and this module supplies all three:

* **Enumerate** what was transmitted, from the consent ledger's own entries --
  the ledger records that a dispatch was consented, so the enumeration is
  complete by construction rather than by anyone remembering to log.
* **Mark** which persisted artefacts were derived from an off-host read, by the
  transport segment of their provenance stamp.
* **Offer** local re-derivation from the cached transcription, producing a NEW
  artefact carrying a local stamp.

**Re-derivation asserts, it does not overwrite.** The prior stamp is returned
beside the new one and the consent-ledger entries are never touched: they are
the honest history of what did leave the host, and rewriting them would convert
an audit trail into a claim that the transmission never happened. What changes
after re-derivation is that no CURRENT artefact depends on the cloud read --
which is a different and smaller statement than "the cloud read is undone", and
the operator-facing text says so.

**Re-derivation re-runs the cheap stage only.** The expensive half of ingestion
is the transcription, and it is already cached; what a cloud read produced that
this replaces is the semantic reading of that text. So a re-derivation needs no
document re-read and, deliberately, no off-host access of any kind.

**Both the ledger and the on-host reader are injected**, not imported. The
consent ledger lives on the adapter side and the readers live in the gated
inference subpackage; this layer reaches neither, which is what keeps the
module testable against real records without owning either dependency.

See Also:
    :class:`~domain.evidence_consent.EvidenceConsentLedgerEntry`
        One recorded off-host dispatch; the unit this survey enumerates.
    :func:`~application.ledger.extracted_document_cache.read_cached_transcription`
        The stage-1 cache a local re-derivation reads instead of the document.
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        The artefact class re-derivation replaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from ...core import LOCAL_TRANSPORT_LABEL, provenance_stamp_transport
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time import UtcInstant
from .evidence import PurchaseInvoiceEvidenceInputError
from .extracted_document_cache import read_cached_transcription
from .extraction_draft_store import load_extraction_drafts, write_extraction_draft
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from ...core.config import Settings
    from .document_transcription import DocumentTranscription
    from .evidence_draft import InvoiceDraft

__all__ = [
    "CloudDerivedArtefact",
    "ConsentRederivationError",
    "ConsentWithdrawalSurvey",
    "ConsentedDispatch",
    "LocalRederivation",
    "OnHostReader",
    "artefact_is_cloud_derived",
    "rederive_artefact_on_host",
    "survey_cloud_consent",
]


class ConsentRederivationError(PurchaseInvoiceEvidenceInputError):
    """Typed refusal for an unsatisfied local re-derivation predicate."""


class OnHostReader(Protocol):
    """Re-reads an already-produced transcription on this host, returning draft and stamp.

    A Protocol rather than a concrete reader so this layer never constructs the
    gated inference subpackage: the caller supplies something that reads
    on-host, and the return's stamp is what proves it did.

    Takes the TRANSCRIPTION rather than its text. The semantic stage stamps
    every envelope with the origin it reads off the transcriber, so handing it a
    bare string would strip the record of which reader acquired the characters
    and silently re-stamp a vision-acquired document as a text-layer one --
    turning a re-derivation into a quiet upgrade of the provenance it exists to
    preserve.
    """

    def __call__(self, transcription: DocumentTranscription, /) -> tuple[InvoiceDraft, str]:
        """Return the re-read draft and the provenance stamp of the reader."""
        ...


class ContentAddressResolver(Protocol):
    """Resolves an evidence reference to the content address of its bytes.

    Injected because the draft store keys artefacts by evidence reference while
    the transcription cache keys them by content address, and nothing in this
    layer can bridge the two without reading bytes it has no handle for.
    """

    def __call__(self, evidence_reference: str, /) -> str | None:
        """Return the document's SHA-256 content address, or ``None``."""
        ...


class ConsentedDispatch(BaseModel):
    """One recorded off-host dispatch, as this layer sees it.

    A projection of the adapter-side consent-ledger entry rather than that
    record itself. The ledger belongs to the transport that writes it; an
    application service that imported its shape would couple the withdrawal
    surface to a storage record it does not own, and this layer's dependency
    direction forbids the import anyway. Mapping is the caller's one line.

    Attributes:
        evidence_content_address: SHA-256 address of the document transmitted.
            The address, never the bytes -- the same line the ledger draws.
        provider: The off-host provider the request dispatched at.
        model: The model identifier the request dispatched at.
        surface: The operator surface that took the acknowledgement.
        recorded_at: When the consent was honoured.
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_content_address: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    recorded_at: UtcInstant


class CloudDerivedArtefact(BaseModel):
    """One persisted artefact whose provenance names an off-host read.

    Attributes:
        evidence_reference: The evidence or attachment id the artefact was read
            from, and the handle a re-derivation is invoked with.
        provenance_stamp: The stamp exactly as persisted. Carried verbatim
            rather than summarised, because it is the evidence for this row's
            own claim and an operator disputing the classification needs to see
            what was read.
        transport: The transport the stamp names, or ``None`` when the stamp
            carries none and the artefact is surfaced out of caution.
        drafted_at: When the artefact was written.
        rederivable_on_host: ``True`` when a cached transcription can supply a
            local re-derivation, ``False`` when none exists, and ``None`` when
            the caller supplied no resolver so the question was never asked.
            ``None`` is distinct from ``False`` deliberately: "cannot" and
            "cannot say" lead an operator to different actions.
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1)
    provenance_stamp: str = Field(min_length=1)
    transport: str | None = None
    drafted_at: UtcInstant
    rederivable_on_host: bool | None = None


class ConsentWithdrawalSurvey(BaseModel):
    """What withdrawal can enumerate, and what it cannot undo.

    ``transmitted_bytes_are_unrecallable`` is a constant ``True`` rather than a
    computed field, and a field rather than prose in a docstring, so that every
    consumer -- the CLI text, the JSON payload, any later surface -- has to
    carry it. A caveat that lives only in documentation is a caveat the
    operator reading machine output never sees.

    Attributes:
        consented_dispatches: Every recorded off-host dispatch, oldest first.
        cloud_derived_artefacts: Persisted artefacts whose provenance names an
            off-host read, or whose stamp cannot be read.
        transmitted_bytes_are_unrecallable: Always ``True``.
    """

    model_config = STRICT_FROZEN_CONFIG

    consented_dispatches: tuple[ConsentedDispatch, ...] = ()
    cloud_derived_artefacts: tuple[CloudDerivedArtefact, ...] = ()
    transmitted_bytes_are_unrecallable: bool = True


class LocalRederivation(BaseModel):
    """The outcome of re-deriving one artefact on this host.

    Carries BOTH stamps because the point of the operation is the difference
    between them, and because the prior stamp is not deleted anywhere -- this
    record asserts a new derivation rather than relabelling the old one.

    Attributes:
        evidence_reference: The document re-derived.
        previous_provenance_stamp: The stamp the superseded artefact carried.
        provenance_stamp: The stamp the new artefact carries.
        transcription_reused: Whether the cached transcription supplied the
            text, which is what makes the re-derivation free of any model read
            of the document.
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1)
    previous_provenance_stamp: str = Field(min_length=1)
    provenance_stamp: str = Field(min_length=1)
    transcription_reused: bool


def artefact_is_cloud_derived(read_transports: tuple[str, ...]) -> bool:
    """Whether an artefact should be surfaced to a withdrawing operator.

    Reads the recorded TRANSPORTS rather than parsing a reader label. The label
    was never a transport claim -- the batch path stores a function name, by a
    deliberate rule against claiming one reader for a draft assembled from
    several -- so parsing it for transport marked every batch-ingested draft
    cloud-derived. Fail-open noise on a confidentiality surface is not caution;
    it trains an operator to ignore the surface.

    Fails open toward SURFACING on genuine uncertainty: an EMPTY tuple means
    the writer could not establish where the read ran, and that is surfaced
    rather than resolved as on-host. A withdrawal that omits an artefact tells
    the operator they are clean when they may not be.

    The fact is monotone: any non-local transport makes the document off-host,
    because if any field left the host then the document did.
    """
    if not read_transports:
        return True
    return any(transport != LOCAL_TRANSPORT_LABEL for transport in read_transports)


def _off_host_transport(read_transports: tuple[str, ...]) -> str | None:
    """Return the off-host transport to show, or ``None`` when there is none to name.

    ``None`` covers both "recorded as on-host" and "never established"; the row
    exists at all only because :func:`artefact_is_cloud_derived` selected it, so
    the operator already knows it needs attention.
    """
    off_host = [transport for transport in read_transports if transport != LOCAL_TRANSPORT_LABEL]
    return off_host[0] if off_host else None


def survey_cloud_consent(
    *,
    bucket_id: str,
    settings: Settings,
    consent_entries: tuple[ConsentedDispatch, ...],
    resolve_content_address: ContentAddressResolver | None = None,
    transcriber_cache_key: str | None = None,
) -> ConsentWithdrawalSurvey:
    """Enumerate the profile's off-host history and its surviving artefacts.

    ``consent_entries`` is REQUIRED and carries no default, because the only
    plausible default is the empty tuple and the empty tuple is a claim: it
    tells the operator nothing has left this host. A caller that omits it must
    fail with a ``TypeError`` rather than silently produce a clean survey --
    the same reason the eligibility bar upstream is keyword-only and
    undefaultable. Passing ``()`` deliberately remains available, and is then a
    statement the caller made rather than one it inherited.

    Args:
        bucket_id: The profile bucket to survey.
        settings: Deployment settings resolving the storage route.
        consent_entries: The profile's consent history, projected by the caller
            from the adapter-side ledger this layer does not import. Required:
            see above.
        resolve_content_address: Optional resolver from an evidence reference to
            the document's content address. Without it, re-derivability is
            reported as unknown rather than guessed.
        transcriber_cache_key: Which transcription would be reused. Required
            alongside the resolver for re-derivability to be established.

    Returns:
        The survey, including the standing statement that transmitted bytes
        cannot be recalled.
    """
    drafts = load_extraction_drafts(bucket_id, settings).drafts
    artefacts = tuple(
        CloudDerivedArtefact(
            evidence_reference=stored.evidence_reference,
            provenance_stamp=stored.extractor,
            transport=_off_host_transport(stored.read_transports),
            drafted_at=stored.drafted_at,
            rederivable_on_host=_rederivable(
                stored.evidence_reference,
                bucket_id=bucket_id,
                settings=settings,
                resolve_content_address=resolve_content_address,
                transcriber_cache_key=transcriber_cache_key,
            ),
        )
        for stored in drafts
        if artefact_is_cloud_derived(stored.read_transports)
    )
    return ConsentWithdrawalSurvey(
        consented_dispatches=consent_entries,
        cloud_derived_artefacts=artefacts,
    )


def _rederivable(
    evidence_reference: str,
    *,
    bucket_id: str,
    settings: Settings,
    resolve_content_address: ContentAddressResolver | None,
    transcriber_cache_key: str | None,
) -> bool | None:
    """Whether a cached transcription can supply this artefact's re-derivation.

    Returns ``None`` -- not ``False`` -- when the caller gave this function no
    way to ask. The draft store keys by evidence reference and the transcription
    cache keys by content address, so without a resolver the two cannot be
    joined, and reporting ``False`` would state a fact nobody established.
    """
    if resolve_content_address is None or transcriber_cache_key is None:
        return None
    content_address = resolve_content_address(evidence_reference)
    if content_address is None:
        return False
    return (
        read_cached_transcription(
            bucket_id=bucket_id,
            source_content_sha256=content_address,
            transcriber_cache_key=transcriber_cache_key,
            settings=settings,
        )
        is not None
    )


def rederive_artefact_on_host(
    *,
    bucket_id: str,
    evidence_reference: str,
    source_content_sha256: str,
    transcriber_cache_key: str,
    settings: Settings,
    read_on_host: OnHostReader,
) -> LocalRederivation:
    """Re-derive one artefact from its cached transcription, on this host.

    Args:
        bucket_id: The profile bucket holding the artefact and the cache.
        evidence_reference: Which artefact to re-derive.
        source_content_sha256: Content address of the document's bytes.
        transcriber_cache_key: Which transcription to reuse.
        settings: Deployment settings resolving the storage route.
        read_on_host: The on-host reader, returning its draft and stamp.

    Returns:
        The re-derivation, carrying the superseded stamp beside the new one.

    Raises:
        ConsentRederivationError: When no artefact exists for ``evidence_reference``, when no
            cached transcription exists, or when the reader returned a stamp
            that does not name an on-host transport. All three refuse rather
            than degrading: a re-derivation that quietly re-reads the document
            is a different operation with a different cost, and one that
            re-stamps with a cloud transport would leave the operator believing
            a withdrawal completed when it had just repeated the transmission.
    """
    stored = next(
        (
            row
            for row in load_extraction_drafts(bucket_id, settings).drafts
            if row.evidence_reference == evidence_reference
        ),
        None,
    )
    if stored is None:
        raise ConsentRederivationError(
            context={"evidence_reference": evidence_reference, "artefact_available": False},
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.CONSENT_REDERIVATION_ARTEFACT_AVAILABLE,
                facts={"artefact_available": False},
            ),
        )
    transcription = read_cached_transcription(
        bucket_id=bucket_id,
        source_content_sha256=source_content_sha256,
        transcriber_cache_key=transcriber_cache_key,
        settings=settings,
    )
    if transcription is None:
        raise ConsentRederivationError(
            context={"evidence_reference": evidence_reference, "transcription_available": False},
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.CONSENT_REDERIVATION_TRANSCRIPTION_AVAILABLE,
                facts={"transcription_available": False},
            ),
        )
    draft, stamp = read_on_host(transcription)
    transport = provenance_stamp_transport(stamp)
    if transport != LOCAL_TRANSPORT_LABEL:
        raise ConsentRederivationError(
            context={"transport": transport, "on_host": False},
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.CONSENT_REDERIVATION_ON_HOST,
                facts={"on_host": False, "transport": transport or "unknown"},
            ),
        )
    write_extraction_draft(
        bucket_id=bucket_id,
        evidence_reference=evidence_reference,
        draft=draft,
        extractor=stamp,
        # The transport is READ BACK from the stamp the reader just produced,
        # not asserted alongside it: the refusal above already established that
        # the stamp names an on-host transport, so recording anything else here
        # would contradict the check that let this line run.
        read_transports=(transport,),
        settings=settings,
    )
    return LocalRederivation(
        evidence_reference=evidence_reference,
        previous_provenance_stamp=stored.extractor,
        provenance_stamp=stamp,
        transcription_reused=True,
    )

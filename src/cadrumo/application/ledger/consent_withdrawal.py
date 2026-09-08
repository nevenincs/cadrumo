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
The consent ledger is injected rather than imported. It lives on the adapter
side; this layer receives its projection so it can enumerate the honest history
without reversing the dependency direction.

See Also:
    :class:`~domain.evidence_consent.EvidenceConsentLedgerEntry`
        One recorded off-host dispatch; the unit this survey enumerates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ...core.time.utc import UtcInstant
from .extraction_draft_store import load_extraction_drafts

if TYPE_CHECKING:
    from ...core.config import Settings

__all__ = [
    "CloudDerivedArtefact",
    "ConsentWithdrawalSurvey",
    "ConsentedDispatch",
    "artefact_is_cloud_derived",
    "survey_cloud_consent",
]


class ConsentedDispatch(BaseModel):
    """One recorded off-host dispatch, as this layer sees it.

    A projection of the adapter-side consent-ledger entry rather than that
    record itself. The ledger belongs to the transport that writes it; an
    application service that imported its shape would couple the withdrawal
    surface to a storage record it does not own, and this layer's dependency
    direction forbids the import anyway. Mapping is the caller's one line.

    Attributes:
        profile_bucket_id: The profile the dispatch ran under. Carried rather
            than dropped so the survey can scope its own input: without it the
            survey has to trust that a caller filtered, and a caller that did
            not would show one profile another profile's off-host history.
        evidence_content_address: SHA-256 address of the document transmitted.
            The address, never the bytes -- the same line the ledger draws.
        provider: The off-host provider the request dispatched at.
        model: The model identifier the request dispatched at.
        surface: The operator surface that took the acknowledgement.
        recorded_at: When the consent was honoured.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_bucket_id: str = Field(min_length=1)
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
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1)
    provenance_stamp: str = Field(min_length=1)
    transport: str | None = None
    drafted_at: UtcInstant


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
        consent_entries: Consent history projected by the caller from the
            adapter-side ledger this layer does not import. Required: see
            above. Entries recorded under another profile are dropped here, so
            a caller may pass the whole ledger without scoping it first.

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
        )
        for stored in drafts
        if artefact_is_cloud_derived(stored.read_transports)
    )
    return ConsentWithdrawalSurvey(
        # Scoped HERE rather than trusted from the caller. The artefacts above
        # are already bucket-scoped by their own load, and leaving the
        # dispatches on trust made the two halves of one survey disagree about
        # who is responsible for scoping -- the half that trusted being the one
        # that would disclose another profile's history.
        consented_dispatches=tuple(entry for entry in consent_entries if entry.profile_bucket_id == bucket_id),
        cloud_derived_artefacts=artefacts,
    )



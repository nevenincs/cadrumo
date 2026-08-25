"""The off-host evidence-read consent gate, and the token that satisfies it.

Reading a taxpayer's invoice at a hosted model removes that document from the
host, which `sensitive-financial-data-secure-storage-only` permits only behind
an explicit, per-invocation, default-off, gestor-barred acknowledgement. This
module holds the decision function and the carrier that proves the decision was
taken; :meth:`~llm.LLMClient.complete` applies it at the
single dispatch point so no caller can construct a request that reaches around
it.

**Why a token rather than a boolean argument.** A boolean threaded through the
call chain is indistinguishable, at the point it is read, from a default that
nobody set. The token can only come from :func:`mint_evidence_consent_token`,
which refuses unless the gate permits, so its mere presence at the dispatch
point is evidence that the gate ran -- and the dispatch re-applies the gestor
bar anyway, because a defence that depends on the minting site remembering is
not a defence.

**It is never persisted.** The token is per-invocation and holds the operator's
acknowledgement, not a durable grant; a stored one would be exactly the sticky
enablement this posture forbids. ``model_dump`` and ``model_dump_json`` are
overridden to raise, mirroring
:class:`~application.ledger.evidence_input.EvidenceInput`'s refusal, so a stray persistence
call fails loudly rather than minting a consent record that outlives the
invocation.

See Also:
    :class:`~core.config.Settings`
        Carries the deployment half of the posture (the gestor bar and the
        opt-in flag) that this gate reads.
    :func:`~core.telemetry.telemetry_emit_permitted`
        The sibling off-host consent gate, deliberately the same shape.
"""

from __future__ import annotations

from typing import Never, Self, override

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from ..core import ActionEvidenceProvenance
from ..core.config import LLMProvider, Settings
from ._errors import LLMConsentError
from ._preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

__all__ = [
    "EvidenceConsentToken",
    "cloud_evidence_read_permitted",
    "mint_evidence_consent_token",
    "provider_reads_off_host",
]

_MINT_REFUSAL_LOCALE_KEY = "llm.evidence.consent.mint_refused"


def provider_reads_off_host(provider: LLMProvider) -> bool:
    """Whether dispatching at ``provider`` removes the request from this host.

    Derived from the enum rather than listed, so a provider added later is
    off-host by construction: a new member is a new vendor until someone
    deliberately makes it local, and the failure of a hand-kept cloud list is
    that the newest transport is the one missing from it.
    """
    return provider is not LLMProvider.LOCAL


def cloud_evidence_read_permitted(settings: Settings, *, profile_eligible: bool, acknowledged: bool) -> bool:
    """Whether an off-host read of taxpayer evidence is permitted for THIS invocation.

    On-host reading is always permitted and is the default; this gate governs
    only the off-host exception. Permitted only when every one of the following
    holds:

    1. Gestor/professional mode is OFF (``settings.cadrumo_evidence_gestor_mode``
       is ``False``). An absolute, categorical bar: a gestor deployment never
       transmits a client's document regardless of the other three conditions.
    2. The deployment has opted in
       (``settings.cadrumo_evidence_cloud_upload_permitted`` is ``True``).
    3. The ACTIVE PROFILE carries the standing eligibility bar
       (``profile_eligible``), resolved by
       :func:`~application.user_profile.cloud_evidence_upload_eligible_for_active_profile`.
       Deployment opt-in and profile eligibility are separate questions: one
       machine can serve several taxpayers, and one of them permitting an
       off-host read must not decide it for the others.
    4. The operator acknowledged this specific invocation (``acknowledged`` is
       ``True``). The acknowledgement is never sticky; it must be re-affirmed at
       every call.

    ``profile_eligible`` is a REQUIRED keyword with no default, deliberately: a
    defaulted bar is one a caller can forget, and forgetting this one would
    reinstate exactly the machine-wide posture condition 3 exists to split.
    Omitting it is a :exc:`TypeError` at the call site rather than an open door.

    Args:
        settings: Resolved deployment settings carrying the consent posture.
        profile_eligible: Whether the active profile's standing eligibility bar
            is on.
        acknowledged: Whether the operator acknowledged the off-host read for
            this specific invocation.

    Returns:
        ``True`` only when all four conditions above hold.
    """
    if settings.cadrumo_evidence_gestor_mode:
        return False
    if not settings.cadrumo_evidence_cloud_upload_permitted:
        return False
    if not profile_eligible:
        return False
    return acknowledged


class EvidenceConsentToken(BaseModel):
    """Proof that the off-host consent gate ran and permitted THIS invocation.

    Args:
        surface: The operator-facing surface that took the acknowledgement (a
            CLI verb path). Recorded so a later audit can say WHERE the operator
            was asked, which a bare boolean cannot answer.
        evidence_content_address: SHA-256 content address of the evidence about
            to be transmitted, binding the acknowledgement to one document
            rather than to the session. The address, never the bytes.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    surface: str = Field(min_length=1, description="Operator surface that took the acknowledgement.")
    evidence_content_address: str = Field(
        min_length=1,
        description="SHA-256 content address of the evidence this acknowledgement covers.",
    )

    @model_validator(mode="after")
    def reject_a_placeholder_address(self) -> Self:
        """Refuse a blank-in-substance content address.

        ``min_length`` alone accepts a single space, and an acknowledgement
        bound to nothing is bound to everything.

        Raises:
            ValueError: When either field is whitespace-only.
        """
        if not self.surface.strip() or not self.evidence_content_address.strip():
            raise LLMConsentError(
                context={"consent_token_binding_valid": False},
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.EVIDENCE_TOKEN_BOUND,
                    facts={"consent_token_binding_valid": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            )
        return self

    @model_serializer
    def refuse_serialization(self) -> dict[str, object]:
        """Refuse every serialization path pydantic can route.

        Registered as the model's serializer, so a NESTED dump -- a containing
        model dumping its fields, which is how the token would most plausibly
        escape -- fails too, not only the two methods overridden below. Pydantic
        wraps a serializer exception, so those two overrides exist to hand a
        direct caller the typed error rather than a wrapped one.

        Raises:
            LLMConsentError: Always.
        """
        raise _token_serialization_refusal()

    @override
    def model_dump(self, *args: object, **kwargs: object) -> Never:
        """Refuse a direct dump.

        Raises:
            LLMConsentError: Always.
        """
        raise _token_serialization_refusal()

    @override
    def model_dump_json(self, *args: object, **kwargs: object) -> Never:
        """Refuse a direct JSON dump.

        Raises:
            LLMConsentError: Always.
        """
        raise _token_serialization_refusal()


def mint_evidence_consent_token(
    *,
    settings: Settings,
    profile_eligible: bool,
    acknowledged: bool,
    surface: str,
    evidence_content_address: str,
) -> EvidenceConsentToken:
    """Mint a token for one off-host evidence read, or refuse.

    The ONLY constructor a caller should use: it runs
    :func:`cloud_evidence_read_permitted` first, so a token cannot exist for an
    invocation the gate refused.

    Because this is the sole minting path, routing the per-profile eligibility
    bar through it is what makes "while the bar is off, no surface offers the
    consent gate" true by construction rather than by convention. A surface that
    forgot to hide its prompt would still obtain no token, so the operator can
    be misled at most into an acknowledgement that changes nothing.

    Args:
        settings: Resolved deployment settings carrying the consent posture.
        profile_eligible: The active profile's standing eligibility bar, from
            :func:`~application.user_profile.cloud_evidence_upload_eligible_for_active_profile`.
        acknowledged: Whether the operator acknowledged this specific read.
        surface: Operator surface that took the acknowledgement.
        evidence_content_address: SHA-256 content address of the evidence.

    Returns:
        A token satisfying the dispatch-point gate for this invocation.

    Raises:
        LLMConsentError: When the deployment posture, the profile's eligibility
            bar, or the missing acknowledgement refuses the read. The refusal is
            localized and names what the operator would do to proceed.
    """
    if not cloud_evidence_read_permitted(settings, profile_eligible=profile_eligible, acknowledged=acknowledged):
        raise LLMConsentError(
            translated_message=_MINT_REFUSAL_LOCALE_KEY,
            context={
                "gestor_mode": settings.cadrumo_evidence_gestor_mode,
                "deployment_permitted": settings.cadrumo_evidence_cloud_upload_permitted,
                "profile_eligible": profile_eligible,
                "acknowledged": acknowledged,
            },
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_OFF_HOST_DISPATCH_PERMITTED,
                facts={
                    "gestor_mode": settings.cadrumo_evidence_gestor_mode,
                    "deployment_permitted": settings.cadrumo_evidence_cloud_upload_permitted,
                    "profile_eligible": profile_eligible,
                    "acknowledged": acknowledged,
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
    return EvidenceConsentToken(surface=surface, evidence_content_address=evidence_content_address)


def _token_serialization_refusal() -> LLMConsentError:
    """Return the terminal refusal for any attempt to persist a consent token."""
    facts = {"consent_token_serializable": False}
    return LLMConsentError(
        context=facts,
        precondition_verdict=llm_no_recovery_verdict(
            LLMPreconditionCondition.EVIDENCE_TOKEN_EPHEMERAL,
            facts=facts,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )

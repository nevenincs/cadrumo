"""The filer's own IVA territory, read from the profile rather than from paper.

An IVA classification needs the territorial scope of BOTH parties to an
operation, and a Spanish country code cannot supply it: the three Spanish IVA
territories -- peninsula and Balears inside the TAI, Canarias under IGIC, Ceuta
and Melilla under IPSI -- all share ``ES``. The commonest ingested document, a
domestic invoice printing a bare CIF and no address country, establishes neither
party's scope from its face.

**One of those two parties is never a document question.** Every ingested
invoice has the operator on one side of it, and the operator's own establishment
is a profile and censo fact: system-authoritative, declared once, and consumed
from the profile authority exactly like the taxpayer's own IVA regime. Reading
it off the paper would be asking a probabilistic reader for something already
known with certainty. That halves the problem by construction -- only the
counterparty's scope is ever sought on the document.

**So an incomplete profile refuses at setup, never per document.** A prompt on
every invoice for a fact the profile is supposed to carry is both the wrong
place to ask and the reliable way to train an operator into clicking through
without reading. The refusal here is a completeness refusal: it names the fact
that is missing and the verb that supplies it.

**Absence never resolves to the mainland.** The peninsula is the majority
population, so defaulting there is invisible in testing while silently placing
Canarian and Ceutan filers inside a territory their operations are not subject
to. Nothing here has a branch that answers without evidence -- the refusal is
the only exit when the fact cannot be read, which is the same asymmetry
:func:`~domain.iva.territorial_scope_for_spanish_postal_code` documents on its
own return.

See Also:
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The territorial derivation this module delegates to; it owns the
        five-digit judgment and refuses an unreadable code to ``None``.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territorial classification a resolved fact produces.
    :func:`~application.user_profile.fact_value`
        The canonical single-fact reader on a
        :class:`~domain.user_profile.UserProfileRecord`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...domain.iva import IvaTerritorialScope, territorial_scope_for_spanish_postal_code
from ._evidence_draft import PurchaseInvoiceEvidenceInputError
from ._preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from ...domain.user_profile import UserProfileRecord

__all__ = [
    "FILER_POSTCODE_FACT_PATH",
    "FILER_TAX_ID_FACT_PATH",
    "resolve_filer_tax_id",
    "resolve_filer_territorial_scope",
]

FILER_TAX_ID_FACT_PATH: Final[str] = "identity.tax_id"
"""Profile fact path carrying the taxpayer's own tax identifier.

Declared beside the postcode path for the same reason it is: the reading path
reads it, and spelling it at each use site is how a fact comes to be read at a
path nothing writes.

**Not ``tax.id``.** That spelling exists and is load-bearing elsewhere -- it is
the registry SELECTOR key a binding names, projected FROM this fact -- so it
reads as the obvious answer and the profile schema rejects it. A fact read at a
path nothing writes is indistinguishable from a profile that declares none, and
the difference between the two spellings is invisible at every call site.
"""

FILER_POSTCODE_FACT_PATH: Final[str] = "contact.postcode"
"""Profile fact path carrying the taxpayer's own fiscal-address postcode.

Declared here rather than spelled at each use site because three things must
agree on it exactly: this resolver reads it, the refusal message names it so the
operator knows what to supply, and the censal sync writes it. A path spelled
twice drifts silently -- a fact read at a path nothing writes is indistinguishable
from a profile that never declared one.

This is the SAME path ``aeat config profile censo pull`` adopts from the
authority's ``domicilio_fiscal``, which is why the recovery the refusal names is
a censal read rather than a hand-entered value.
"""


def resolve_filer_territorial_scope(
    *,
    profile_record: UserProfileRecord | None,
) -> IvaTerritorialScope:
    """Return the IVA territory the taxpayer's own establishment sits in.

    Args:
        profile_record: The taxpayer's :class:`UserProfileRecord`, or ``None``
            when none was resolvable. ``None`` refuses rather than defaulting:
            no profile is not an empty profile, and neither of them is a
            territory.

    Returns:
        :class:`~domain.iva.IvaTerritorialScope`: The filer's own territory.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the profile carries no readable
            fiscal-address postcode. Raising is the whole point rather than an
            edge case -- every alternative exit from this function answers a
            regulatory question with no evidence behind it. The message
            distinguishes an undeclared fact from an unreadable one, because an
            operator told a malformed value is "missing" re-supplies the same
            malformed value.
    """
    declared = _declared_postcode(profile_record)
    if declared is None:
        raise PurchaseInvoiceEvidenceInputError(
            "this profile declares no fiscal-address postcode "
            f"({FILER_POSTCODE_FACT_PATH}), so the taxpayer's own IVA territory "
            "cannot be established; it separates the peninsula from Canarias and "
            "from Ceuta y Melilla and is never read off an invoice",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.FILER_POSTCODE_VALID,
                facts={"filer_postcode_present": False},
            ),
        )

    scope = territorial_scope_for_spanish_postal_code(declared)
    if scope is None:
        raise PurchaseInvoiceEvidenceInputError(
            f"the fiscal-address postcode this profile declares ({declared!r}) is "
            f"not a readable Spanish postal code, so the taxpayer's own IVA "
            f"territory cannot be established from {FILER_POSTCODE_FACT_PATH}",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.FILER_POSTCODE_VALID,
                facts={"filer_postcode_readable": False},
            ),
        )
    return scope


def resolve_filer_tax_id(*, profile_record: UserProfileRecord | None) -> str | None:
    """Return the taxpayer's own tax identifier, or ``None`` when none is declared.

    **Answers ``None`` rather than refusing, unlike its sibling above, and the
    asymmetry is deliberate.** The filer's territory is required to classify an
    operation at all, so a profile that declares no postcode must stop the
    confirm. The filer's IDENTIFIER is required only to do BETTER: without it
    the counterparty role resolution declines to run and the direction
    derivation reports that it was never supplied. Both degrade to exactly the
    behaviour that shipped before either existed, so refusing here would turn a
    profile gap into a refusal to read a document that reads perfectly well.

    Args:
        profile_record: The taxpayer's :class:`UserProfileRecord`, or ``None``
            when none was resolvable.

    Returns:
        The declared identifier, trimmed, or ``None``. A blank value is
        undeclared rather than unreadable -- nothing was stated.
    """
    # Imported here rather than at module scope for the cycle-break the sibling
    # below documents: the user-profile application package reaches back into
    # this one. Read exactly as if written at module scope.
    from ..user_profile.projections import fact_value

    if profile_record is None:
        return None
    declared = fact_value(profile_record, FILER_TAX_ID_FACT_PATH)
    if declared is None:
        return None
    return declared.strip() or None


def _declared_postcode(profile_record: UserProfileRecord | None) -> str | None:
    """Return the postcode the profile declares, or ``None`` when it declares none.

    A blank or whitespace-only value is treated as undeclared rather than as an
    unreadable one: nothing was stated, so the operator's action is to supply
    the fact rather than to correct it, and the two refusals send them different
    places.
    """
    # Imported here rather than at module scope: the user-profile application
    # package reaches back into the ledger package, so a module-scope import
    # closes a cycle at import time. Read exactly as if written at module scope.
    from ..user_profile.projections import fact_value

    if profile_record is None:
        return None
    declared = fact_value(profile_record, FILER_POSTCODE_FACT_PATH)
    if declared is None:
        return None
    trimmed = declared.strip()
    return trimmed or None

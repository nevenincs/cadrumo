"""Who the two parties are, adjudicated at the confirm boundary.

Three refusals live here, and all three answer the same class of question: does
the identity a confirm is about to record match the identity the document and
the profile actually support. They are grouped because they share one failure
mode -- a checksum-valid identifier belonging to the wrong real taxpayer, which
every downstream validity check passes and which reaches Modelo 347 / 349, where
AEAT reconciles the two counterparties' declarations against each other.

- :func:`agreed_counterparty_tax_id` treats an operator-supplied counterparty
  identifier as an ASSERTION rather than an override: a disagreement with what
  the reader recovered refuses, so typing to CHECK can never become typing to
  SET. Its one relaxation is the counterparty's OWN country prefix, a fact this
  boundary holds and the shared same-bearer predicate does not.
- :func:`refuse_a_counterparty_that_is_the_filer` refuses a record naming the
  taxpayer as their own counterparty -- the shape an ISSUED document produces
  whenever the supplier side is taken as the counterparty.
- :func:`refuse_an_issued_document_the_filer_did_not_issue` refuses the
  opposite mis-direction: a supplier's invoice TO the taxpayer, confirmed as
  issued BY them, which is internally coherent and simply describes the wrong
  direction.

Each guard declines to judge what it cannot: an absent identifier on either
side, or a profile carrying no tax id, returns without refusing. A guard that
cannot run must not block a path it cannot judge.

Deciding which identifier on the page belongs to the counterparty at all is a
READING-stage question and lives in
:mod:`~application.ledger.identity_roles`; these guards run afterwards, on the
value a confirm is about to persist.
"""

from __future__ import annotations

from ...core.identity import same_tax_identifier
from ...domain.iva.classification import InvoiceKind
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = [
    "agreed_counterparty_tax_id",
    "refuse_a_counterparty_that_is_the_filer",
    "refuse_an_issued_document_the_filer_did_not_issue",
]


def _without_own_country_prefix(value: str, *, country: str) -> str:
    """Return *value* with a leading prefix naming *country* removed.

    Only that country's own prefix, never any alpha-2. A German-prefixed number
    on a counterparty recorded in Spain keeps its prefix and therefore keeps
    disagreeing, which is the outcome that must survive: the point is to stop
    refusing two spellings of ONE bearer, not to stop distinguishing two.
    """
    token = value.strip().upper()
    head = country.strip().upper()
    if len(head) == 2 and token.startswith(head) and len(token) > 2:
        return token[2:]
    return token


def _same_bearer_allowing_own_country_prefix(left: str, right: str, *, country: str) -> bool:
    """Whether two spellings name one bearer, discounting this country's prefix.

    Delegates to the canonical same-bearer predicate rather than reimplementing
    it, so the separator rule stays in one place and this function adds exactly
    one axis on top of it.
    """
    if same_tax_identifier(left, right):
        return True
    return same_tax_identifier(
        _without_own_country_prefix(left, country=country),
        _without_own_country_prefix(right, country=country),
    )


def agreed_counterparty_tax_id(
    *,
    supplied: str | None,
    extracted: str | None,
    counterparty_country: str,
) -> str | None:
    """Resolve the counterparty tax id, refusing a supplied/extracted disagreement.

    Every other field here layers an operator value over the extracted one and
    lets the operator win silently. This one does not, because the extracted
    value is the only field on the draft that nothing else checks: the
    counterparty NAME is supplied by the operator, so a misread name is caught
    by them typing it, while a misread tax id was accepted unseen.

    That matters past tidiness. A received invoice's supplier tax id drives
    deductibility and feeds Modelo 347 per counterparty, so a wrong one reaches
    a filing a human submits. The checksum on
    :func:`~core.identity.validate_spanish_tax_id` is the PRIMARY
    defence and it is a strong one -- a transposed digit breaks the check
    character and is refused outright. What it cannot catch is a misread that
    happens to be a different VALID identifier, which belongs to a different
    real taxpayer. This closes that residue.

    Supplying the value is therefore an ASSERTION rather than an override, and
    the difference is what makes it safe: typing to CHECK is not typing to SET.
    A typo here produces a refusal, never a wrong value on a filing -- unlike
    the transcription hazard that was removed from the extract hint, where what
    the operator typed silently became the data.

    Neither value is named in the refusal. The operator already knows the one
    they typed, and the machine only has to answer whether the extractor agrees;
    printing either would put a tax identity into a pasteable artefact for no
    gain.

    Comparison is on :func:`~cadrumo.core.identity.same_tax_identifier`, the
    canonical "are these the same identifier" predicate. It deliberately asserts
    no checksum -- a counterparty may be non-resident and carry a foreign
    identifier -- which is exactly right here: this answers "same identifier?",
    and the separate validation gate on the invoice model answers "valid Spanish
    identifier?".

    The axis that matters on THIS path is separators, not case. One side is
    whatever an on-host extractor read off a printed document, and printed
    identifiers carry hyphens and spaces routinely, so the comparison must
    normalise them away: ``B-1234567-4`` and ``B12345674`` are one identifier.
    :func:`~cadrumo.core.identity.tax_id_identity_token` would NOT match those
    two -- it stays trim-and-uppercase because it keys stored objects and must
    never merge two characters-differ identifiers into one row. Keying and
    comparing are different questions, and this one is comparing.

    A blank on either side answers "not the same" and refuses, because an
    invoice cannot be confirmed against an identity nothing supplied.

    **The second axis is the COUNTRY PREFIX, and it is handled here rather than
    in the shared predicate.** A document routinely states an identifier in its
    IVA form while an operator supplies the bare national form -- ``ESB12345674``
    against ``B12345674`` -- and those name one bearer. The shared predicate
    cannot know that: stripping a leading alpha-2 from both sides unconditionally
    would merge bearers ACROSS States, since the same national body can exist
    under two different prefixes, and that predicate is also consumed by the
    identity-role resolver and the direction deriver, where a looser rule would
    silently change who counts as the taxpayer on every document.

    So the prefix is stripped only when it names THIS counterparty's own country,
    which is a fact this call site has and the predicate does not. One side
    carrying ``DE`` against a counterparty recorded in Spain still disagrees, and
    must.

    Args:
        supplied: The operator's ``--counterparty-nif``, or ``None``.
        extracted: What the on-host extractor read, or ``None``.
        counterparty_country: The alpha-2 country recorded for this
            counterparty, which decides which prefix may be discounted.

    Returns:
        The value to confirm with, or ``None`` when neither side has one.

    Raises:
        PurchaseInvoiceEvidenceInputError: When both sides carry a value and
            they are not the same identifier.
    """
    if supplied is None:
        return extracted
    if extracted is None:
        # Extraction found nothing, so there is nothing to disagree with and
        # the operator's value is authoritative. This is the override case the
        # flag has always served, and it stays.
        return supplied
    if not _same_bearer_allowing_own_country_prefix(supplied, extracted, country=counterparty_country):
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID,
                facts={"counterparty_tax_id_matches_document": False},
            ),
        )
    return supplied


def refuse_a_counterparty_that_is_the_filer(counterparty_tax_id: str) -> None:
    """Refuse an invoice recording the taxpayer as their own counterparty.

    The reader no longer scans for the first checksum-valid tax id, and the
    field contract now asks for both parties separately by role, so the
    mechanism that first exposed this is gone. The exposure is not. On an ISSUED
    invoice the issuer IS the filer, so the supplier slot legitimately holds the
    filer's own identifier -- the document is right and the reading is right --
    and any path taking that side as the counterparty records the taxpayer
    against themselves. The value is checksum-valid, so every downstream
    identity check passes it, and it is bound for the Modelo 347 / 349
    counterparty totals AEAT reconciles against what the counterparty declared.

    Refusing is right rather than advisory: unlike an amount that is merely
    doubtful, a self-naming counterparty is wrong under every reading this
    codebase can represent (see
    :func:`~application.invoices.counterparty_is_the_filer` for the autoconsumo
    scope note). Minting the record and warning about it would put a fabricated
    counterparty identity in the catalogue.

    The profile carries the identity to compare against, so a bucket whose
    profile is absent or carries no tax id cannot be checked. That case returns
    without refusing -- a guard that cannot run must not block a path it cannot
    judge -- which does mean the protection is only as present as the profile.
    Every real bucket carries one; setup requires the tax id.

    Args:
        counterparty_tax_id: The identifier about to be recorded.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the identifier is the filer's
            own.
    """
    from ..invoices._self_counterparty import counterparty_is_the_filer
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    if not counterparty_is_the_filer(counterparty_tax_id=counterparty_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID,
            facts={"counterparty_is_filer": True},
        ),
    )


def refuse_an_issued_document_the_filer_did_not_issue(
    *,
    kind: InvoiceKind,
    extracted_supplier_tax_id: str | None,
) -> None:
    """Refuse a document confirmed as ISSUED that someone else issued.

    The sibling guard refuses a counterparty that names the filer. This one
    catches the opposite mis-direction: a supplier's invoice TO the taxpayer,
    confirmed as issued BY them. There the counterparty is a real third party,
    so the sibling guard sees nothing wrong -- the record is internally
    coherent and simply describes the wrong direction.

    The evidence itself settles it. On a genuinely issued document the printed
    supplier IS the filer, so an extracted supplier identity that is somebody
    else is positive evidence the document was issued by that somebody else.

    Direction is not cosmetic. It decides which informativa the record feeds
    and on which side: a received invoice booked as issued moves a purchase
    into the sales column, inverts the cuota's meaning between soportado and
    repercutido, and reaches Modelo 347 as an operation the counterparty will
    have declared with the opposite sign. AEAT reconciles those two
    declarations against each other.

    Refusing rather than warning, for the same reason the sibling guard does:
    the direction is wrong under every reading, not merely doubtful.

    The guard declines to judge where it cannot. An absent extracted supplier
    means the scan found no issuer identity, which is silence rather than
    evidence, and a bucket whose profile carries no tax id gives nothing to
    compare against. Both return without refusing -- a guard that cannot run
    must not block a path it cannot judge.

    Args:
        kind: The direction the operator is confirming the document as.
        extracted_supplier_tax_id: Issuer identity recovered from the document,
            or ``None`` when the scan found none.

    Raises:
        PurchaseInvoiceEvidenceInputError: The document names an issuer who is
            not the filer, yet is being confirmed as issued by the filer.
    """
    if kind is not InvoiceKind.ISSUED or extracted_supplier_tax_id is None:
        return

    from ..invoices._self_counterparty import counterparty_is_the_filer
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    # The loader raises rather than returning None, and that failure is already
    # handled by the except clause above, so the former None guard was unreachable.
    if counterparty_is_the_filer(counterparty_tax_id=extracted_supplier_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        "this document names another issuer, so it cannot be confirmed as issued by you; "
        "confirm it as received, or correct the document reference",
    )

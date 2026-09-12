"""On-host routing of one stored evidence reference to a typed invoice draft.

Holds the reading layer that decides which reader a given document is handed
to, and the three readers' wiring. It never persists an
:class:`~domain.invoices.Invoice` and never guesses a value no reader could
ground in the document: every field a reader could not recover is left ``None``
rather than fabricated (``no-silent-under-declaration`` in spirit: an unconfident
field is absent, not invented).

Three reading paths, chosen on the document's own shape rather than on its
stored MIME type:

- A **structured** e-invoice (Facturae, CII, UBL) is read exactly by
  :func:`~adapters.inbound.einvoice.parse_einvoice_document`. It reaches no model
  at all, so prompt injection is categorically impossible for that document
  rather than merely mitigated, and it is the only path that can recover the
  document's own line decomposition and per-rate breakdown.
- A **text-native PDF** is transcribed by
  :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`, read semantically by
  :func:`~llm.extract_invoice_fields_from_text`, and then grounded against that
  same transcription by
  :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`. The
  transcription is produced by a DIFFERENT reader than the one that proposes
  values, which is what makes the anchor check an external check rather than a
  model confirming itself.
- A **scan-only PDF or image** has nothing to transcribe, so it falls back to the
  on-host LOCAL vision reader (:mod:`~llm.evidence_draft_vision`) -- the same
  rasterise-then-read-with-Ollama transport
  :class:`~llm.vision_classifier.LocalVisionLLMClassifier` already uses for
  classification, gated by :attr:`~core.ServiceCapability.LLM_VISION` and never a
  cloud call.

The escalation is one-directional and the asymmetry is deliberate. A document
with no text layer genuinely needs a reader that works on pixels, so it escalates.
A readable document whose semantic reader is absent or unreachable is an
ENVIRONMENT failure, so it REFUSES in the operator's face rather than silently
running a heavier engine they did not ask for -- see
:func:`_refuse_a_text_read_with_no_reader`. A profile that has opted out of vision
reading likewise gets a typed, instructive refusal, never a silent empty draft.

Everything here runs on-host and in-memory only. The evidence bytes, the
transcription and the draft never touch disk and are never sent to a cloud
provider. This module performs no filesystem write.

:func:`extract_invoice_draft_from_evidence` is the CLI-facing
wiring layer: it resolves an already-stored ``purchase_invoice_evidence`` record
or a linked ``attachment_id`` to its in-memory bytes (through the private
evidence-input resolvers
:func:`~application.ledger.evidence_input.resolve_purchase_invoice_evidence_input`
and
:func:`~application.ledger.evidence_input.resolve_attachment_evidence_input`) and
routes them to one of the three readers above, so
``aeat app ledger evidence extract`` needs only a bucket id plus one of the two
reference ids.

Confirming a read draft into a catalogue record is a separate responsibility and
lives in :mod:`~application.ledger.invoice_confirmation`; the draft's own
direction-resolved projections live in
:mod:`~application.ledger.evidence_draft`.

See Also:
    :class:`~application.ledger.invoice_draft_records.InvoiceDraft`
        Public draft record returned before an invoice is persisted.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        Acquisition-stage primitive that turns a text-native PDF into the
        reading-order transcription the semantic reader is handed.
    :func:`~application.ledger.invoice_confirmation.confirm_invoice_draft_from_evidence`
        Non-interactive confirm step that re-extracts, applies overrides, and
        delegates the catalogue write.
    :mod:`~llm.evidence_draft_vision`
        On-host vision fallback for scan-only PDFs and image attachments.
"""

from __future__ import annotations

from typing import NoReturn

from ...core.capabilities import ServiceCapability
from ...core.config import Settings
from ...core.config import load_settings as _load_settings
from ...core.config_support import LLMProvider
from ...core.document_shape import PDF_CONTAINER_SHAPES, STRUCTURED_DOCUMENT_SHAPES
from ...core.external_constants import XML_MIME_TYPE
from ...core.image_media_type import ImageMediaType, detect_image_media_type
from ...core.logging import get_logger
from ...core.optional_extras import MissingOptionalExtraError
from ...domain.attachments.models import normalize_media_type
from ...domain.iva.supply_nature import SupplyNature
from ..provisioning import probe_ollama_vision
from ..user_profile.capabilities import resolve_active_capability
from .document_transcription import DocumentTranscription
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_input import EvidenceInput
from .evidence_textlayer import transcribe_text_layer
from .invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    StructuredInvoiceReadError,
    VisionImage,
)
from .invoice_draft_records import (
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
    facturae_invoice_class_findings,
)
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = ["extract_invoice_draft_from_evidence"]


_CONSENT_BINDING_REFUSAL_LOCALE_KEY = "llm.evidence.consent.binding_mismatch"


def _require_consent_token_binds_these_bytes(
    consent_token: EvidenceConsentProof | None,
    evidence_input: EvidenceInput,
    ports: InvoiceDraftExtractionPorts,
) -> None:
    """Refuse a consent token minted for a document other than this one.

    The token carries a content address precisely so an acknowledgement binds
    to ONE document rather than to the session, and until this ran nothing
    checked that binding. The dispatch point cannot: the request it inspects
    carries the prompt and the images, not the address of the evidence they
    were built from, so all it can ask is whether SOME token is present.

    Here both facts exist at once. ``content_sha256`` is the address the bytes
    were actually read under and is enforced against the bytes themselves, so
    comparing the two is the whole check.

    What it prevents is narrow and serious. The token travels as a parameter
    beside ``evidence_id`` rather than being derived from it, so a caller can
    pair them wrongly -- and the CLI pairing them correctly is a property of
    that one caller, not of this function, which is the door a second frontend
    comes through. A mismatched pair would send THIS document off-host under
    an acknowledgement taken for ANOTHER, and then record the other document's
    address in the consent ledger, so the audit trail would name a document
    that was never transmitted.

    ``None`` is not a mismatch and is not this function's business: an on-host
    read needs no token, and an off-host one without a token is refused at the
    dispatch point, which is where that decision already lives.

    Raises:
        LLMConsentError: When the token's content address is not the address
            these bytes were read under.
    """
    if consent_token is None:
        return
    if consent_token.evidence_content_address == evidence_input.content_sha256:
        return
    facts = {
        "consent_token_binding_valid": False,
        "evidence_content_address": evidence_input.content_sha256,
    }
    raise ports.consent_binding_error(facts)


def extract_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    settings: Settings | None = None,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentProof | None = None,
    ports: InvoiceDraftExtractionPorts,
) -> InvoiceDraft:
    """Resolve one stored evidence reference to bytes and extract its :class:`InvoiceDraft`.

    The CLI-facing wiring layer over the three readers: given
    either a ``purchase_invoice_evidence`` id (looked up through
    :class:`PurchaseInvoiceEvidenceService`) or a linked ``attachment_id``,
    reads the evidence's bytes from secure storage into memory
    (the private evidence-input resolvers
    :func:`~application.ledger.evidence_input.resolve_purchase_invoice_evidence_input`
    and
    :func:`~application.ledger.evidence_input.resolve_attachment_evidence_input`)
    and routes them to the reader the document's shape selects. Exactly one of *evidence_id* /
    *attachment_id* must be supplied.

    Nothing is written to disk and nothing leaves the host: the resolved
    bytes and the extracted text stay in process memory for the duration of
    this call (``sensitive-financial-data-secure-storage-only``).

    Args:
        bucket_id: Active ledger bucket the evidence or attachment belongs to.
        evidence_id: A ``purchase_invoice_evidence`` record id, or ``None``.
        attachment_id: A linked attachment id, or ``None``.
        settings: Resolved ``Settings``. When ``None``, ``load_settings()`` is
            used so test overrides via ``override_settings()`` are honoured.
        off_host_provider: Provider to route the MODEL-BEARING stages at, or
            ``None`` for the on-host default. Widening this signature does not
            widen the boundary: the refusal lives below this function, at the
            client's single dispatch point, so a caller naming a cloud provider
            without a token is refused there rather than trusted here.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm.mint_evidence_consent_token`. ``None`` is correct for
            every on-host read.

    Returns:
        :class:`InvoiceDraft`: The best-effort extracted fields, for operator
        review. Never itself persisted as an :class:`~domain.invoices.Invoice`.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when *evidence_id*
            resolves outside the bytes-bearing evidence-record id space (a
            catalogue-invoice id carries fiscal totals, not a document), when the
            resolved evidence's media type is unsupported, or when a scan-only
            PDF / image falls back to the on-host vision reader and that reader
            is disabled for the profile or the local Ollama runtime is
            unreachable.
    """
    if (evidence_id is None) == (attachment_id is None):
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_ATTACHMENT_SELECTION_VALID,
                facts={"exactly_one_evidence_source_supplied": False},
            ),
        )

    resolved_settings = settings or _load_settings()
    # Resolved HERE, once, and handed down. The filer's own identifier is a
    # PROFILE fact, never read off the invoice, and both consumers of it live at
    # the far end of the reading chain: the counterparty role resolution excludes
    # it from candidacy, and the direction derivation asks which party's block
    # prints it. Neither could reach it before, so both were structurally
    # unreachable on the live path however completely they were built.
    filer_tax_id = _active_filer_tax_id()
    evidence_input = ports.resolve_evidence_input(bucket_id, evidence_id, attachment_id, resolved_settings)

    _require_consent_token_binds_these_bytes(consent_token, evidence_input, ports)

    # Routing order, and the order is itself a control rather than an
    # optimisation: a document carrying a STRUCTURED record is read exactly and
    # reaches no model at all, which makes prompt injection categorically
    # impossible for that document rather than merely mitigated. The decision is
    # made on DocumentShape -- derived from the bytes -- because the stored MIME
    # type answers "pdf" for a ZUGFeRD invoice and a photograph alike, which is
    # how the most machine-readable document in the corpus ended up on the least
    # exact path.
    if evidence_input.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        try:
            return _extract_invoice_fields_from_structured_record(evidence_input, ports=ports)
        except StructuredInvoiceReadError:
            # A malformed structured record refuses rather than yielding a
            # partial one; fall through so a document whose embedded payload is
            # broken can still be read by the text or vision path.
            pass
    _refuse_an_unrecognised_xml_document(evidence_input)
    if evidence_input.document_shape in PDF_CONTAINER_SHAPES:
        # The `try` wraps ONLY the transcription, and that scoping is the whole
        # asymmetry rather than a formatting choice. A failure to transcribe is a
        # statement about the DOCUMENT -- no text layer, scan-only, XFA -- so
        # escalating to a reader that works on pixels is right. Everything after
        # it is a statement about the ENVIRONMENT and must refuse in the
        # operator's face.
        #
        # Wrapping the whole chain instead is a live defect this code already
        # had: the reader refusal raises `PurchaseInvoiceEvidenceInputError`, so
        # a broader `except` swallowed it and silently ran vision on a document
        # whose text layer was perfectly readable -- the exact escalation the
        # refusal exists to prevent, reported to the operator as a vision
        # failure on a text PDF.
        try:
            transcription = transcribe_text_layer(evidence_input)
        except PurchaseInvoiceEvidenceInputError:
            transcription = None
        if transcription is not None:
            return _read_transcription_semantically(
                evidence_input,
                transcription,
                settings=resolved_settings,
                off_host_provider=off_host_provider,
                consent_token=consent_token,
                taxpayer_tax_id=filer_tax_id,
                ports=ports,
            )
    return _extract_invoice_fields_via_vision(
        evidence_input,
        settings=resolved_settings,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
        taxpayer_tax_id=filer_tax_id,
        ports=ports,
    )


def _refuse_a_text_read_with_no_reader(exc: Exception) -> NoReturn:
    """Refuse a text-native document the semantic reader could not be run for.

    Deliberately a refusal rather than a fallback, and the distinction is a
    decision rather than an artefact of which exception type happens to be
    caught above.

    A missing or unreachable reader is a statement about the ENVIRONMENT, not
    about the document. Silently escalating to the vision reader would run a
    heavier engine the operator did not ask for, on a document whose text layer
    was perfectly readable -- and would do it invisibly, so the operator could
    not tell why an extract that used to be cheap became slow. The one case
    where escalation IS right is the opposite one, handled above: a document
    with no text layer genuinely needs a reader that works on pixels.

    The refusal carries only application-observed machine facts. Recovery is
    resolved later from the canonical action catalogue; this boundary neither
    invents a command nor copies dependency-owned presentation prose.

    Args:
        exc: The provider or dependency failure that prevented the read.

    Raises:
        PurchaseInvoiceEvidenceInputError: Always.
    """
    _refuse_with_unavailable_reader(exc, availability_fact="semantic_reader_available")


def _refuse_with_unavailable_reader(exc: Exception, *, availability_fact: str) -> NoReturn:
    """Preserve a reader refusal as typed facts, without presentation prose."""
    if isinstance(exc, MissingOptionalExtraError):
        facts: dict[str, str | bool] = {
            "extra": exc.extra.extra,
            "import_name": exc.extra.import_name,
            "importable": False,
        }
    else:
        facts = {
            availability_fact: False,
            "reader_error_type": exc.__class__.__name__,
        }
    raise PurchaseInvoiceEvidenceInputError(
        context=facts,
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
            facts=facts,
        ),
    ) from exc


def _active_filer_tax_id() -> str | None:
    """Return the active profile's own tax identifier, or ``None``.

    Answers ``None`` for every reason a profile might not yield one -- none
    active, none declared, the workflow state unreadable -- rather than
    propagating. That direction is deliberate and it is the conservative one:
    without the identifier the counterparty role resolution declines to run and
    the direction derivation reports that it was never supplied, which is
    exactly the behaviour that shipped before either existed. Letting a profile
    gap raise here would refuse to READ a document over a fact the document does
    not contain.
    """
    # Both imported at call time: the workflow package reaches this one, and the
    # filer-fact reader reaches the user-profile package which reaches back. The
    # sanctioned cycle breaks, read as if written at module scope.
    from ..workflow.persistence import workflow_state_repository
    from .filer_establishment import resolve_filer_tax_id

    try:
        state = workflow_state_repository().load()
    except Exception:
        return None
    return resolve_filer_tax_id(profile_record=state.active_profile_record())


def _proposed_supply_nature(
    transcription: DocumentTranscription,
    *,
    settings: Settings,
    ports: InvoiceDraftExtractionPorts,
) -> SupplyNature | None:
    """Return a model's proposal about goods-or-services, or ``None``.

    Advisory throughout. The proposal reaches a person on the review item that
    already asks them to state the nature; the value that reaches the classifier
    is the one they type at confirm, so nothing model-derived enters it.

    Never raises into the read. A proposal that could fail an extraction would
    make an optional convenience able to lose a document, so every failure --
    an absent extra, an unreachable provider, a reply that did not survive
    containment -- yields no proposal and leaves the operator asked exactly as
    they were.
    """
    try:
        proposal = ports.propose_supply_nature(transcription, settings)
    except Exception:
        proposal = None
    if proposal is None:
        get_logger(__name__).info("supply-nature proposal unavailable; the operator is asked as before")
    return proposal


def _read_transcription_semantically(
    evidence: EvidenceInput,
    transcription: DocumentTranscription,
    *,
    settings: Settings,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentProof | None = None,
    taxpayer_tax_id: str | None = None,
    propose_supply_nature: bool = False,
    ports: InvoiceDraftExtractionPorts,
) -> InvoiceDraft:
    """Read a text-native PDF through the transcribe-extract-ground chain.

    The three stages, and why the order is not arbitrary:

    **Transcribe.** :func:`~application.ledger.evidence_textlayer.transcribe_text_layer` produces the
    document's reading-order text with printed forms preserved verbatim. It is
    produced by a DIFFERENT reader than the one that proposes values, which is
    exactly what makes the anchor check in stage three an external check rather
    than a model verifying itself.

    **Extract semantically.** The reading model proposes values in their declared
    form beside the printed anchor each was read from, and stamps every envelope
    ``UNANCHORED`` -- an honest under-claim, because it holds no transcription to
    check its own claims against.

    **Ground.** :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`
    holds the transcription, so it runs the check the reader could not, upgrading
    each envelope to the outcome the evidence supports and appending the
    arithmetic-closure findings.

    Args:
        evidence: Resolved in-memory evidence bytes.
        transcription: The already-produced acquisition-stage text. Taken as an
            ARGUMENT rather than produced here so the caller's fallback ``try``
            can wrap the transcription alone. That scoping is what separates a
            DOCUMENT failure (no text layer -- escalate to vision) from an
            ENVIRONMENT failure (no reader -- refuse), and it has to be
            structural: when one ``try`` wrapped both, the refusal below raised
            the same exception type the fallback catches and was silently
            swallowed into a vision run.
        settings: Resolved settings, passed down rather than reloaded so the
            caller's overrides govern the model this stage resolves.
        off_host_provider: Provider to route the SEMANTIC stage at, or ``None``
            for the on-host default.
        consent_token: Per-invocation off-host consent proof, or ``None``.
        taxpayer_tax_id: The filer's own identifier, resolved once at the public
            entry from the active profile. Handed down rather than looked up
            here so one read of one document consults one profile, and so this
            function stays a pure reader of what it was given.
        propose_supply_nature: Whether to ask a model to PROPOSE goods-or-services
            from this transcription. Off by default and never consulted by the
            classifier: the proposal reaches a person, and the value that reaches
            the classifier is the one they state at confirm.

    Returns:
        The grounded draft.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the semantic reader cannot be
            run. Deliberately OUTSIDE the caller's fallback ``try`` -- see
            :func:`_refuse_a_text_read_with_no_reader`.
    """
    from .grounded_reading import ground_draft_against_transcription
    from .invoice_extraction_authority import (
        default_invoice_extraction_period,
        resolve_invoice_extraction_authority_values,
    )

    # Resolved HERE, once, and handed down. The rates, the statutory retención
    # figures and the no-printed-tax category set are regulatory values, so this
    # layer determines them and the reading adapter receives them; the adapter
    # holds no authority of its own and cannot print a rate this call did not
    # produce. Resolving once per document also means both branches below read
    # under the same values, which a per-prompt resolution does not guarantee.
    authority_values = resolve_invoice_extraction_authority_values(period=default_invoice_extraction_period())

    try:
        read = ports.read_text(transcription, settings, off_host_provider, consent_token, authority_values)
    except InvoiceDraftReaderUnavailableError as exc:
        # The reader is absent or unreachable. See the refusal's own docstring
        # for why this does not fall through to vision.
        _refuse_a_text_read_with_no_reader(exc.cause)
    grounded_input = read.model_copy(
        update={
            "transcription_sha256": transcription.source_content_sha256,
            # Proposed HERE because the transcription is still in hand. A later
            # verb would re-run the whole reading stage to recover text this
            # call already holds, spending a document read to answer a question
            # worth one short call. Off unless asked: a read that silently
            # reaches a second model changes what the verb costs and what
            # leaves the host.
            "proposed_supply_nature": (
                _proposed_supply_nature(transcription, settings=settings, ports=ports)
                if propose_supply_nature
                else None
            ),
        },
    )
    return ground_draft_against_transcription(
        draft=grounded_input,
        transcription=transcription,
        taxpayer_tax_id=taxpayer_tax_id,
    )


def _refuse_an_unrecognised_xml_document(evidence: EvidenceInput) -> None:
    """Refuse an XML document whose syntax no structured reader recognises.

    XML must never reach the text-layer or vision fallbacks. Those exist for
    documents whose content is RENDERED -- a PDF's text layer, a photograph of a
    receipt -- and an XML file is neither: extracting prose from markup yields
    tag soup, and rasterising it to read with a vision model is incoherent as
    well as expensive.

    This became reachable only when ``.xml`` was admitted at the evidence gate.
    Before that a structured document could not be ingested at all, so the
    fallback chain was never handed one. Admitting the extension without closing
    the chain would route every unrecognised XML -- a SII or VERI*FACTU record,
    a TicketBAI record, any XML at all -- to the on-host vision model, whose
    capability is ON by default.

    The refusal names the syntaxes that ARE read, so an operator holding a
    document we do not support learns which ones we do rather than watching a
    model fail to read their markup.
    """
    if normalize_media_type(evidence.mime_type) != XML_MIME_TYPE:
        return
    if evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        # Self-contained rather than relying on call position. Today the
        # structured branch returns before reaching here, so this is
        # unreachable in the live routing -- which is precisely why it is
        # asserted: a later refactor that moves this call earlier would
        # otherwise refuse every Facturae, CII and UBL document, and the guard
        # would look correct while removing the capability it protects.
        return
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_XML_INVOICE_SUPPORTED,
            facts={"xml_invoice_syntax_recognized": False},
        ),
    )


def _extract_invoice_fields_from_structured_record(
    evidence: EvidenceInput, *, ports: InvoiceDraftExtractionPorts
) -> InvoiceDraft:
    """Read a structured e-invoice exactly into the line-carrying draft.

    No model, no rasterisation, no network. The per-rate breakdown and the line
    set come from the document's own record, which is the whole reason the
    draft grew them: a flat base/rate/cuota triple structurally cannot hold a
    two-rate invoice.
    """
    # Function-local for the same cycle-break reason the grounding import in the
    # semantic path is: the findings module reaches back into this one for the
    # draft and finding types. Read it exactly as if it were written at module
    # scope.
    from .deterministic_findings import deterministic_findings
    from .grounding_anchor import (
        country_code_value,
        resolved_country_code,
        stated_country_code,
        structured_provenance,
    )

    parsed = ports.parse_structured_invoice(evidence.data)
    # Resolved once and used twice: the draft carries these values and their
    # provenance envelopes describe them, so grounding the parser's verbatim
    # string instead would attach an envelope to a value the draft does not hold.
    country_codes: dict[str, tuple[str, str] | None] = {
        f"{side}_country_code": resolved_country_code(getattr(parsed, f"{side}_country_code"))
        for side in ("supplier", "customer")
    }
    draft = InvoiceDraft(
        supplier_tax_id=parsed.supplier_tax_id,
        supplier_name=parsed.supplier_name,
        customer_tax_id=parsed.customer_tax_id,
        customer_name=parsed.customer_name,
        # Both sides, because which party is the counterparty is not decided
        # until confirm. A country code cannot separate Spain's three IVA
        # territories, so these codes are the only thing that settles where
        # either party is established -- and the exact reader was the one path
        # that recovered neither, leaving the most machine-readable documents in
        # the corpus unable to answer a question a text-read document could.
        supplier_postal_code=parsed.supplier_postal_code,
        customer_postal_code=parsed.customer_postal_code,
        # The country half of the same question, resolved to the one code system
        # everything downstream is keyed by. The formats disagree about which
        # system they state: UBL states alpha-2 and Facturae states alpha-3, so
        # carrying the record's own string through would hand `ESP` to a resolver
        # that shape-checks for two letters and returns nothing -- the country
        # element present, read, and establishing nothing, with the postal rung
        # it gates staying shut for the entire Spanish national format.
        supplier_country_code=country_code_value(country_codes["supplier_country_code"]),
        customer_country_code=country_code_value(country_codes["customer_country_code"]),
        # The record's own token, carried whether or not the line above could
        # place it. This is what keeps an unplaceable country visible: the
        # resolved field goes empty for `THA` exactly as it does for a document
        # with no address block, and every surface downstream -- the review row,
        # the provenance envelope, the country advisory -- read that emptiness
        # and said nothing. A Thai export is an ordinary document, not a
        # malformed one, and it must not arrive looking like a silent absence.
        supplier_stated_country_code=stated_country_code(parsed.supplier_country_code),
        customer_stated_country_code=stated_country_code(parsed.customer_country_code),
        invoice_number=parsed.invoice_number,
        invoice_series=parsed.invoice_series,
        # Read and DISCARDED until now. A rectificativa is a different class
        # of invoice under RD 1619/2012 art. 15, and a confirm that cannot say
        # so mints one as ordinaria -- so the Invoice model's own rectificativa
        # invariants never fire, because nothing ever states the class.
        rectifies_invoice_number=parsed.rectifies_invoice_number,
        invoice_date=parsed.invoice_date,
        taxable_base=parsed.taxable_base,
        iva_amount=parsed.iva_amount,
        grand_total=parsed.grand_total,
        currency=parsed.currency,
        recargo_amount=parsed.recargo_amount,
        # The other two terms of the closure identity, which the structured
        # reader recovers from the format's own dedicated elements. Carried here
        # or the read is unreachable: the identity is checked on the DRAFT, so a
        # parser that recovers a suplido the draft drops leaves the check
        # computing a total short by exactly it -- which is the shape this
        # mapping exists to close rather than to reproduce one field along.
        retencion_amount=parsed.retencion_amount,
        suplidos_amount=parsed.suplidos_amount,
        iva_category=parsed.iva_category,
        # The mention the document prints, carried on the model-free path too.
        # It was reaching the operator only from the reading model, so the one
        # path that recovers it EXACTLY -- no model, no anchor check needed,
        # because the text is the record -- was the one that dropped it.
        regime_legend=parsed.regime_legend,
        lines=tuple(
            InvoiceDraftLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                taxable_base=line.taxable_base,
                iva_rate=line.iva_rate,
                iva_amount=line.iva_amount,
            )
            for line in parsed.lines
        ),
        iva_breakdown=tuple(
            InvoiceDraftRateBreakdown(iva_rate=rate, taxable_base=base, iva_amount=cuota)
            for rate, base, cuota in parsed.iva_breakdown
        ),
        raw_text_length=len(evidence.data),
        provenance=structured_provenance(parsed=parsed, evidence=evidence, derived=country_codes),
    )
    draft.set_facturae_invoice_class(parsed.facturae_invoice_class)

    # Exactness is not correctness, and conflating the two is what left this path
    # unchecked. Reaching no model makes prompt injection categorically
    # impossible for this document -- it says nothing about whether its
    # arithmetic closes, or whether the regime it prints in words matches the tax
    # it charged. Those are questions about the ISSUER's document, not about the
    # reader, and an exactly-read wrong invoice is still a wrong invoice.
    return draft.model_copy(
        update={
            "discrepancies": (
                *deterministic_findings(draft),
                *facturae_invoice_class_findings(
                    declared=parsed.facturae_invoice_class,
                    rectifies_invoice_number=parsed.rectifies_invoice_number,
                ),
            ),
        },
    )


def _extract_invoice_fields_via_vision(
    evidence: EvidenceInput,
    *,
    settings: Settings,
    off_host_provider: LLMProvider | None = None,
    consent_token: EvidenceConsentProof | None = None,
    taxpayer_tax_id: str | None = None,
    ports: InvoiceDraftExtractionPorts,
) -> InvoiceDraft:
    """Rasterise/encode *evidence*, TRANSCRIBE it with the on-host vision model, then read it.

    Two stages, not one, and the split is what earns this path its grounding.
    The vision model produces a :class:`DocumentTranscription` and interprets
    nothing; the same semantic reader and the same anchor check the text lane
    uses then run over that text
    (:func:`_read_transcription_semantically`). Because the transcription is
    produced by a different call than the one that proposes values, the anchor
    check is an external check here exactly as it is on the text lane -- which
    it structurally could not be while one call went image-to-fields and the
    only thing an anchor could be compared against was the reply that asserted
    it.

    Gated by :attr:`~core.ServiceCapability.LLM_VISION` -- an operator who has
    opted out gets a typed refusal naming the capability toggle, never a silent
    empty draft. A missing/unreachable local Ollama runtime, or an unrasterisable
    PDF, is converted to the same instructive refusal the classification vision
    path uses (:func:`~application.provisioning.probe_ollama_vision`). An absent
    ``llm`` extra is reported separately as typed dependency facts, so a
    dependency gap is never mistaken for a daemon-reachability problem.
    """
    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        facts = {"llm_vision_enabled": False}
        raise PurchaseInvoiceEvidenceInputError(
            context=facts,
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED,
                facts=facts,
            ),
        )

    try:
        if evidence.document_shape in PDF_CONTAINER_SHAPES:
            images = tuple(
                VisionImage(base64_data=page, media_type=ImageMediaType.PNG)
                for page in ports.rasterise_pdf(evidence.data)
            )
        else:
            import base64

            # An attachment is whatever format the operator supplied, so the type is
            # detected from the bytes; an unsupported one refuses here rather than
            # travelling to a provider under a guessed label.
            images = (
                VisionImage(base64.b64encode(evidence.data).decode("ascii"), detect_image_media_type(evidence.data)),
            )
        # Content-addressed to the SOURCE bytes, never to the renders: the same
        # document rasterised at another resolution is one document, and hashing
        # the images would split it into two cache entries that can never hit.
        #
        # The consented route reaches stage ONE as well as stage two, and that
        # is deliberate rather than thorough: on a scan-only document the pixels
        # ARE the evidence, so a consent that covered only the semantic stage
        # would take an operator's acknowledgement and then leave the read
        # entirely on-host -- an acknowledgement that changes nothing, which is
        # worse than not asking.
        transcription = ports.transcribe_vision(
            images, evidence.content_sha256, settings, off_host_provider, consent_token
        )
    except InvoiceDraftReaderUnavailableError as exc:
        # Ordered ahead of the runtime-failure branch deliberately. A missing
        # `llm` extra is a dependency problem, not a reachability problem: the
        # branch below probes runtime reachability, which is a different failed
        # condition and must not replace the dependency identity.
        cause = exc.cause
        if isinstance(cause, MissingOptionalExtraError):
            _refuse_with_unavailable_reader(cause, availability_fact="vision_reader_available")
        status = probe_ollama_vision(settings)
        if status.precondition_verdict is not None:
            raise PurchaseInvoiceEvidenceInputError(precondition_verdict=status.precondition_verdict) from cause
        facts: dict[str, str | bool] = {
            "vision_reader_available": False,
            "vision_reader_probe_available": True,
            "vision_reader_error_type": cause.__class__.__name__,
        }
        raise PurchaseInvoiceEvidenceInputError(
            context=facts,
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
                facts=facts,
            ),
        ) from cause

    # OUTSIDE the try, deliberately, and for the same reason the text lane's
    # semantic read sits outside its transcription try: a failure here is a
    # statement about the semantic READER, and converting it into "vision
    # reading failed" would send the operator to restart a daemon that read the
    # page perfectly well.
    return _read_transcription_semantically(
        evidence,
        transcription,
        settings=settings,
        off_host_provider=off_host_provider,
        consent_token=consent_token,
        taxpayer_tax_id=taxpayer_tax_id,
        ports=ports,
    )

"""The router reaches the grounding stages, and the upgrade actually happens.

Every grounding stage was correct, gated and reached by nothing. These
cases gate the connection itself: that the router's text path runs
transcribe → extract → ground, and that the grounding stage converts a reader's
unverified claim into a checked verdict.

The upgrade is the thing to watch. A reader emits every envelope ``UNANCHORED``
while carrying the anchor it read -- an honest under-claim, because it holds no
transcription to check its own claims against. What the wiring buys is that
those envelopes become verdicts the evidence supports. A wired chain that left
them all ``UNANCHORED`` would be indistinguishable, in the persisted record, from
no wiring at all.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import pytest

from ....core.config import load_settings
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.optional_extras import LLM_EXTRA, MissingOptionalExtraError
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....llm.errors import LLMProviderError
from ....llm.invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from ....tests.attribute_scope import scoped_attribute

# The MODULE object, not names from it: the tests below scope an attribute
# on it. `from .. import <module>` is the relative form that yields one.
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer
from ..grounded_reading import (
    GROUNDABLE_ORIGINS,
    _identity_candidates,
    ground_draft_against_transcription,
    verified_provenance,
)
from ..identity_roles import IdentityCandidate, resolve_counterparty_identity
from ..invoice_draft_records import FieldProvenance, InvoiceDraft
from ..preconditions import LedgerPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_DOCUMENT_TEXT = (
    "FACTURA 2026-0142\n"
    "Proveedor: EJEMPLO SL B12345674\n"
    "Cliente: OTRA SL A82645177\n"
    "Base imponible 100,00 EUR\n"
    "TOTAL 121,00 EUR\n"
)

#: The defining module itself, for the attribute scoping below. Named through
#: `import_module` rather than `from .. import`: the ledger package facade is
#: inert and its tests may not import through it.
invoice_draft_extraction_module = import_module("cadrumo.application.ledger.invoice_draft_extraction")
"""A transcription printing BOTH party headings, so a heading claim can be true or false.

A fixture printing no heading at all would make every dropped-evidence
assertion pass for the wrong reason -- nothing could ever be found, so the
check would look decisive while testing nothing.
"""

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_CONTROL = _CORPUS / "com_2026_0005_layout_minimal.pdf"

#: The filer on this purchase invoice is the RECIPIENT, whose identifier is the
#: one checksum-valid token on the page.
_FILER_CIF = "B17283946"
_SUPPLIER_CIF_BAD_CHECKSUM = "B1234567X"


def _control_transcription():
    payload = _CONTROL.read_bytes()
    return transcribe_text_layer(
        EvidenceInput(
            mime_type="application/pdf",
            data=payload,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            attachment_id="b" * 64,
        ),
    )


def _control_evidence() -> EvidenceInput:
    payload = _CONTROL.read_bytes()
    return EvidenceInput(
        mime_type="application/pdf",
        data=payload,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        attachment_id="b" * 64,
    )


def _reader_output() -> InvoiceDraft:
    """Return a draft shaped exactly as a reader emits one.

    Every envelope ``UNANCHORED`` with the anchor carried -- the reader's honest
    under-claim. One anchor is deliberately fabricated so the upgrade has
    something to reject as well as something to accept.
    """

    def claim(field: str, anchor: str) -> FieldProvenance:
        return FieldProvenance(
            field=field,
            origin=FieldOrigin.TEXT_LAYER,
            grounding=FieldGroundingOutcome.UNANCHORED,
            anchor=anchor,
            note="the reading model reported this printed form; not yet checked",
        )

    return InvoiceDraft(
        taxable_base=Decimal("766.30"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("160.92"),
        grand_total=Decimal("890.00"),
        supplier_tax_id=_SUPPLIER_CIF_BAD_CHECKSUM,
        customer_tax_id=_FILER_CIF,
        provenance=(
            claim("taxable_base", "766,30"),
            claim("iva_rate", "21%"),
            claim("grand_total", "890,00"),
            claim("iva_amount", "9.999,99"),
        ),
    )


def test_the_reader_output_starts_entirely_unverified() -> None:
    """Anchor for every case below: the upgrade must have somewhere to go.

    If a future reader started emitting ``ANCHORED`` itself, the upgrade
    assertions would pass without the wiring doing anything, and this fails
    first to say so.
    """
    outcomes = {envelope.grounding for envelope in _reader_output().provenance}

    assert outcomes == {FieldGroundingOutcome.UNANCHORED}


def test_grounding_upgrades_a_real_anchor_to_anchored() -> None:
    """The upgrade the wiring exists to perform, on the real control document."""
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    by_field = {envelope.field: envelope for envelope in grounded.provenance}
    assert by_field["taxable_base"].grounding is FieldGroundingOutcome.ANCHORED
    assert by_field["grand_total"].grounding is FieldGroundingOutcome.ANCHORED


def test_grounding_upgrades_a_percentage_anchor() -> None:
    """`21%` is the most common field in the corpus; it must survive the chain."""
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    rate = next(e for e in grounded.provenance if e.field == "iva_rate")
    assert rate.grounding is FieldGroundingOutcome.ANCHORED
    assert rate.anchor == "21%", "the verbatim printed form must survive the upgrade"


def test_a_fabricated_anchor_is_not_upgraded() -> None:
    """Anti-fabrication reaching the live path, which is the point of wiring it.

    A figure nobody can point at on the page stays unverified and loses its
    anchor, no matter how confidently the reader claimed it.
    """
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    fabricated = next(e for e in grounded.provenance if e.field == "iva_amount")
    assert fabricated.grounding is FieldGroundingOutcome.UNANCHORED
    assert fabricated.anchor is None


def test_a_refused_anchor_stays_distinguishable_from_one_never_offered() -> None:
    """Clearing the anchor must not erase that a printed form was OFFERED.

    Both directions in one case, because either alone passes over the confusion
    it is meant to catch. A reader that pointed at a figure the document does
    not carry may have misread the page or been handed the wrong document; a
    reader that pointed at nothing simply could not find a printed form. The
    operator acts differently on the two, and downstream every trace of the
    first is gone the moment the anchor is cleared without recording it.
    """
    offered_nothing = FieldProvenance(
        field="currency",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        note="the reading model reported no printed form",
    )
    draft = _reader_output().model_copy(
        update={"currency": "EUR", "provenance": (*_reader_output().provenance, offered_nothing)},
    )

    grounded = ground_draft_against_transcription(draft=draft, transcription=_control_transcription())
    by_field = {envelope.field: envelope for envelope in grounded.provenance}

    refused = by_field["iva_amount"]
    assert refused.anchor is None, "a form the document does not carry must not read as evidence"
    assert refused.refused_anchor == "9.999,99", "the offered form is the only trace a claim was made"
    assert "9.999,99" in refused.note

    absent = by_field["currency"]
    assert absent.anchor is None
    assert absent.refused_anchor is None, "nothing was offered, so nothing was refused"


def test_a_located_anchor_records_no_refusal() -> None:
    """The negative leg: a passing check must not stamp a refusal it did not reach."""
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    anchored = next(e for e in grounded.provenance if e.field == "taxable_base")
    assert anchored.grounding is FieldGroundingOutcome.ANCHORED
    assert anchored.refused_anchor is None


def test_grounding_attaches_the_closure_finding() -> None:
    """The second leg runs on the wired path, not only in its own suite."""
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    kinds = {finding.kind for finding in grounded.discrepancies}
    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in kinds


def test_role_resolution_runs_when_the_filer_is_known() -> None:
    """Both identity guards reach the live path on the control document."""
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
        taxpayer_tax_id=_FILER_CIF,
    )

    kinds = {finding.kind for finding in grounded.discrepancies}
    assert DraftDiscrepancyKind.IDENTITY_UNVERIFIED in kinds
    assert DraftDiscrepancyKind.ROLE_UNRESOLVED in kinds
    supplier = next(e for e in grounded.provenance if e.field == "supplier_tax_id")
    assert supplier.grounding is not FieldGroundingOutcome.ANCHORED


def test_role_resolution_is_skipped_when_the_filer_is_unknown() -> None:
    """Resolving without the filer's identity would let their own id win the role.

    Skipping is the honest behaviour, and it must be visible as an absence of
    findings rather than as a resolution nobody could justify.
    """
    grounded = ground_draft_against_transcription(
        draft=_reader_output(),
        transcription=_control_transcription(),
    )

    kinds = {finding.kind for finding in grounded.discrepancies}
    assert DraftDiscrepancyKind.ROLE_UNRESOLVED not in kinds


def test_a_self_reported_anchor_is_never_upgraded_by_any_transcription() -> None:
    """The anchor-strength split survives the wiring, and it keys on the FLAG.

    A self-reported anchor has nothing independent behind it. Upgrading it
    against some other lane's transcription would manufacture exactly the
    verified-looking record the split exists to prevent.

    The guard is the ``anchor_self_reported`` flag, checked before and
    independently of the groundable-origin set. That independence is the whole
    point of asserting it here: ``VISION`` is now a groundable origin, because
    the vision lane transcribes and interprets in separate calls and its anchors
    are checked against the transcription stage one produced. A guard that had
    keyed on the origin instead would have silently opened at that moment.
    """
    self_reported = FieldProvenance(
        field="taxable_base",
        origin=FieldOrigin.VISION,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor="766,30",
        anchor_self_reported=True,
    )
    draft = InvoiceDraft(taxable_base=Decimal("766.30"), provenance=(self_reported,))

    upgraded = verified_provenance(draft=draft, transcription=_control_transcription())

    assert upgraded[0].grounding is FieldGroundingOutcome.UNANCHORED
    assert upgraded[0].anchor_self_reported is True
    assert FieldOrigin.VISION in GROUNDABLE_ORIGINS, (
        "the two-call vision lane produces an independent transcription, so its anchors are "
        "checkable; if this ever reverts, the refusal above must be re-derived rather than assumed"
    )


def test_the_router_text_path_runs_the_whole_chain() -> None:
    """The connection itself: the router must reach transcribe, extract and ground.

    Asserted structurally against the router's own source rather than by running
    a model, because the semantic read needs inference this gate must not
    perform. What is proven here is that the chain is WIRED -- the behavioural
    halves are proven above and in the stage suites.
    """
    router = Path(__file__).parents[1] / "invoice_draft_extraction.py"
    source = router.read_text(encoding="utf-8")

    assert "transcribe_text_layer(evidence_input)" in source
    assert "extract_invoice_fields_from_text" in source
    assert "ground_draft_against_transcription" in source
    # And the vision lane runs the SAME chain: transcribe with the vision model,
    # then hand the transcription to the one semantic-read-and-ground path. A
    # second, vision-specific field reader is the collapse this refit removed.
    assert "transcribe_document_images" in source
    assert "extract_invoice_fields_from_images" not in source


# The companion property -- that the label-regex family is not merely unreached
# but absent -- is owned by ``test_no_label_regex_reader.py``, which walks the
# router's AST rather than slicing its source text. A source slice cannot tell a
# call from the same characters inside a comment or docstring, and it silently
# truncates when the region it measures grows.


# ---------------------------------------------------------------------------
# A missing reader REFUSES; it never silently escalates to a heavier engine
# ---------------------------------------------------------------------------


def test_an_absent_reader_refuses_with_a_typed_environment_condition() -> None:
    """A missing reader is a typed refusal, not an inferred recovery command."""
    from ..invoice_draft_extraction import _refuse_a_text_read_with_no_reader

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _refuse_a_text_read_with_no_reader(LLMProviderError("no provider reachable"))

    assert raised.value.terminal_precondition_verdict is not None
    assert raised.value.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    )
    assert raised.value.args == ()
    assert raised.value.context == {
        "semantic_reader_available": False,
        "reader_error_type": "LLMProviderError",
    }
    assert raised.value.terminal_precondition_verdict.evidence[0].values == raised.value.context


def test_a_missing_optional_extra_preserves_registry_facts_without_install_prose() -> None:
    """The dependency registry identity crosses the ledger boundary unchanged."""
    from ..invoice_draft_extraction import _refuse_a_text_read_with_no_reader

    dependency_error = MissingOptionalExtraError(LLM_EXTRA)
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _refuse_a_text_read_with_no_reader(dependency_error)

    expected_facts = {
        "extra": LLM_EXTRA.extra,
        "import_name": LLM_EXTRA.import_name,
        "importable": False,
    }
    assert raised.value.args == ()
    assert raised.value.context == expected_facts
    assert raised.value.__cause__ is dependency_error
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    assert verdict.action is None
    assert verdict.evidence[0].values == expected_facts


def test_a_missing_reader_does_not_fall_through_to_the_vision_engine() -> None:
    """The decision, EXERCISED rather than inspected.

    A missing reader is a statement about the ENVIRONMENT, not the document.
    Escalating to vision would run a heavier engine the operator did not ask
    for, on a document whose text layer was perfectly readable, and would do it
    invisibly.

    This case originally asserted only the SOURCE TEXT of the semantic read, and
    it passed while the refusal was being swallowed whole: the refusal raises
    `PurchaseInvoiceEvidenceInputError`, the caller's fallback caught exactly
    that type, and every text PDF with no reader ran vision and reported a
    vision failure. A structural assertion on the callee cannot see what the
    CALLER does with what it raises, which is where the defect lived.

    Substituting the reader is not a test double for the code under test -- the
    reader is the ENVIRONMENT this case is about, and making it unavailable is
    the condition being reproduced. Nothing about the router is stubbed.
    """
    from .... import llm as llm_module
    from ..invoice_draft_extraction import _read_transcription_semantically

    def unavailable(*args: object, **kwargs: object) -> object:
        raise LLMProviderError("Ollama is not reachable")

    with (
        scoped_attribute(llm_module, "extract_invoice_fields_from_text", unavailable),
        pytest.raises(PurchaseInvoiceEvidenceInputError) as raised,
    ):
        _read_transcription_semantically(
            _control_evidence(),
            _control_transcription(),
            settings=load_settings(),
        )

    assert raised.value.terminal_precondition_verdict is not None
    assert raised.value.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    )


def test_the_routers_fallback_try_wraps_only_the_transcription() -> None:
    """The scoping that makes the asymmetry structural rather than incidental.

    If the fallback ``try`` ever widens to wrap the semantic read again, the
    refusal raises the very type the fallback catches, gets swallowed, and every
    text PDF with no reader silently runs vision -- reporting a vision failure
    on a document whose text layer was fine.

    Checked by walking the AST rather than slicing the source text. Two
    string-slicing attempts at this assertion both passed against a mutant that
    reintroduced the defect: the first found an earlier ``try:`` belonging to
    the structured-record branch, and the second was truncated to nothing
    because this function's own explanatory comment contains the word
    ``except``. Prose in the file is not a reliable delimiter for a claim about
    code, and a mutation is what exposed both.
    """
    import ast

    module = ast.parse(Path(inspect.getfile(invoice_draft_extraction_module)).read_text(encoding="utf-8"))
    router = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == "extract_invoice_draft_from_evidence"
    )

    guarded_calls = {
        call.func.id
        for handler in ast.walk(router)
        if isinstance(handler, ast.Try)
        for call in ast.walk(ast.Module(body=handler.body, type_ignores=[]))
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }

    assert "transcribe_text_layer" in guarded_calls, "the transcription is no longer inside a fallback try"
    assert "_read_transcription_semantically" not in guarded_calls, (
        "the fallback try wraps the semantic read; the missing-reader refusal will be swallowed"
    )


def test_the_no_text_layer_case_still_escalates_to_vision() -> None:
    """Positive control for the asymmetry above.

    Without this, "refuse on reader failure" could be implemented as "refuse
    always", silently removing the fallback that scan-only PDFs depend on.
    """
    from ..invoice_draft_extraction import extract_invoice_draft_from_evidence

    source = inspect.getsource(extract_invoice_draft_from_evidence)

    assert "except PurchaseInvoiceEvidenceInputError" in source
    assert "_extract_invoice_fields_via_vision" in source


def test_the_reader_refusal_preserves_its_typed_no_recovery_outcome() -> None:
    """The error boundary keeps the application-owned outcome without prose.

    `PurchaseInvoiceEvidenceInputError` is registered with a default suggestion
    of `aeat app ledger evidence list`, which is the right hint for a bad
    evidence reference and exactly the wrong one here -- listing evidence does
    not provision a reader. The resolver prefers a raised suggestion over the
    registered default, and this pins that: the behaviour is "the operator is
    told how to fix it", not an incidental string.

    Gated because the missing-reader case is a REFUSAL rather than a per-field
    notice. A missing reader is a statement about the ENVIRONMENT and produces
    no draft at all, so there is no provenance for a notice to describe; the
    non-blocking notice channel is for a draft that exists but degraded.
    """
    from ....core.errors.error_codes import build_error_envelope
    from ..invoice_draft_extraction import _refuse_a_text_read_with_no_reader

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _refuse_a_text_read_with_no_reader(LLMProviderError("Ollama is not reachable"))

    assert raised.value.terminal_precondition_verdict is not None
    assert raised.value.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    )

    # Delivery ground truth, so this cannot be read as proving the operator is told it.
    # The resolver that preferred a raised suggestion over the registered default was
    # retired with default suggestions as the authority, and
    # ``REFUSED_LEDGER_EVIDENCE_INPUT`` is not yet converted to a catalogue action
    # identity, so the envelope carries no next step today. Its conversion is the domain
    # part-one step, behind the registry migration contract.
    assert build_error_envelope(raised.value).action is None


class TestTheReadingPathAdmitsOnlyRoleEvidenceTheDocumentPrints:
    """The positive-role-evidence filter must be able to refuse on this path.

    The resolver grounds an identity only on positive role evidence, never on
    survival, because sole survivorship is first-match with the competitors
    removed beforehand. That filter is a truthiness test, so a reading path that
    manufactures a non-empty string for every candidate satisfies it always and
    the filter can never exclude anything.

    It did exactly that, passing ``the reader assigned this identifier to
    <field>`` -- a restatement of the reader's own assignment rather than
    anything the document says about the party. The resulting note read as
    positive evidence, which is what made it worse than supplying none.

    The reading stage now carries real role evidence: the printed heading or
    label the reader copied, per identity field. What makes it real rather than
    longer is that it can be WRONG, so every case below turns on the same
    distinction -- evidence the document prints is admitted, evidence it does
    not print is dropped, and an unevidenced identity still refuses.
    """

    @staticmethod
    def _transcription(text: str = _DOCUMENT_TEXT) -> DocumentTranscription:
        return DocumentTranscription(
            text=text,
            page_count=1,
            source_content_sha256="c" * 64,
            transcriber=TranscriberIdentity(
                transport=LOCAL_TRANSPORT_LABEL,
                origin=FieldOrigin.TEXT_LAYER,
                name="pdfplumber",
                revision="gate",
            ),
        )

    @classmethod
    def _candidates(
        cls,
        *,
        role_evidence: dict[str, str] | None = None,
        text: str = _DOCUMENT_TEXT,
        **values: str,
    ) -> tuple[IdentityCandidate, ...]:
        claimed = role_evidence or {}
        draft = InvoiceDraft(
            **values,
            provenance=tuple(
                FieldProvenance(
                    field=field,
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor=value,
                    role_evidence=claimed.get(field),
                )
                for field, value in values.items()
            ),
        )
        return _identity_candidates(
            draft=draft,
            envelopes=draft.provenance,
            transcription=cls._transcription(text),
        )

    def test_no_candidate_arrives_carrying_evidence_the_reader_merely_asserted(self) -> None:
        """With nothing printed to copy, the reader supplies nothing at all."""
        candidates = self._candidates(supplier_tax_id="B12345674", customer_tax_id="A82645177")

        assert candidates, "the fixture must produce candidates, or this passes vacuously"
        assert all(not candidate.role_evidence for candidate in candidates)

    def test_the_measured_defect_no_longer_grounds_the_lone_survivor(self) -> None:
        """True supplier's id fails its control character; an unrelated valid id survives.

        The case the filter exists for. Previously the survivor resolved with a
        note claiming role evidence picked it.
        """
        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=self._candidates(supplier_tax_id="B1234567X", customer_tax_id="B12345674"),
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved is None, "a lone survivor must not be grounded as the counterparty"
        assert resolution.provenance.grounding is not FieldGroundingOutcome.ANCHORED

    def test_the_filter_still_grounds_when_real_evidence_is_present(self) -> None:
        """The mechanism is intact and waiting on evidence, not disabled.

        Without this the change would be indistinguishable from deleting the
        resolution path outright, and a later stage supplying real evidence
        would have nothing proving the filter still promotes on it.
        """
        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=(
                IdentityCandidate(value="B12345674", role_evidence="printed under 'Proveedor'"),
                IdentityCandidate(value="A82645177"),
            ),
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved == "B12345674"
        assert resolution.provenance.grounding is FieldGroundingOutcome.ANCHORED

    def test_the_no_role_evidence_fallback_note_finally_renders(self) -> None:
        """That message was unreachable while every candidate carried manufactured evidence.

        Two identifiers both verify and neither is evidenced, so both are
        surfaced as competing rather than one being promoted. The note on each
        is the fallback branch, which could not render before: the ``or``
        supplying it was always short-circuited by the synthesised string.
        """
        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=self._candidates(supplier_tax_id="B12345674", customer_tax_id="A82645177"),
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved is None
        assert resolution.provenance.candidates, "both identifiers must be surfaced, not silently dropped"
        assert all(
            candidate.note == "no role evidence distinguishes this identifier"
            for candidate in resolution.provenance.candidates
        )

    def test_role_evidence_the_document_prints_reaches_the_resolver(self) -> None:
        """The half with teeth: a printed heading is admitted and promotes.

        Rows two and three of the measured table -- an ordinary invoice with one
        or two readable identifiers -- refused outright while nothing carried
        role evidence. This is what turns counterparty auto-fill back on, and it
        turns it on only for a document that actually says whose identifier is
        whose.
        """
        candidates = self._candidates(
            supplier_tax_id="B12345674",
            customer_tax_id="A82645177",
            role_evidence={"supplier_tax_id": "Proveedor:"},
        )

        evidenced = [candidate for candidate in candidates if candidate.role_evidence]
        assert [candidate.value for candidate in evidenced] == ["B12345674"]

        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=candidates,
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved == "B12345674"
        assert resolution.provenance.grounding is FieldGroundingOutcome.ANCHORED
        assert resolution.provenance.role_evidence is None or "Proveedor" in str(resolution.provenance.note)

    def test_role_evidence_the_document_does_not_print_is_dropped(self) -> None:
        """A reader that invents a heading loses its evidence and its identity.

        This is the assertion that distinguishes the new payload field from the
        synthesised string it replaces. The synthesised string was true by
        construction on every document; this one is checked against the page,
        so an invented heading cannot promote anything.

        Mutation that must trip this: drop the ``printed_excerpt_occurs`` guard
        in ``_identity_candidates`` and pass the claim through unchecked.
        """
        candidates = self._candidates(
            supplier_tax_id="B12345674",
            customer_tax_id="A82645177",
            role_evidence={"supplier_tax_id": "Lieferant:"},
        )

        assert candidates, "the fixture must produce candidates, or this passes vacuously"
        assert all(not candidate.role_evidence for candidate in candidates), (
            "role evidence the document does not print must never reach the resolver"
        )

        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=candidates,
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved is None
        assert resolution.provenance.grounding is not FieldGroundingOutcome.ANCHORED

    def test_two_printed_headings_compete_rather_than_one_winning(self) -> None:
        """Real evidence on both sides is ambiguity, not a ranking.

        The bound on the previous test: admitting printed evidence must not
        become "the first evidenced candidate wins", which would reintroduce
        first-match selection with a heading attached to it.
        """
        candidates = self._candidates(
            supplier_tax_id="B12345674",
            customer_tax_id="A82645177",
            role_evidence={"supplier_tax_id": "Proveedor:", "customer_tax_id": "Cliente:"},
        )

        assert all(candidate.role_evidence for candidate in candidates)

        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=candidates,
            taxpayer_tax_id=None,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert resolution.resolved is None
        assert resolution.provenance.grounding is FieldGroundingOutcome.AMBIGUOUS

    def test_the_reading_stage_records_the_claim_unchecked_and_the_grounding_stage_checks_it(self) -> None:
        """The two stages must not be collapsed, and each must do only its own half.

        The reading stage holds no transcription, so it records what the model
        claimed without verdict -- exactly as it does for an anchor. The check
        belongs to the stage that has the document. Collapsing them either
        stamps a verdict nobody ran or discards the claim before an operator
        can see it.
        """
        response = parse_invoice_extraction_response(
            json.dumps(
                {
                    "supplier_tax_id": "B12345674",
                    "supplier_tax_id_anchor": "B12345674",
                    "supplier_tax_id_role_evidence": "Lieferant:",
                },
            ),
        )
        draft = ground_extracted_fields(response, raw_text_length=64, origin=FieldOrigin.TEXT_LAYER)

        recorded = next(e for e in draft.provenance if e.field == "supplier_tax_id")
        assert recorded.role_evidence == "Lieferant:", "the reading stage must record the claim verbatim"
        assert recorded.grounding is FieldGroundingOutcome.UNANCHORED, "and must pass no verdict on it"

        candidates = _identity_candidates(
            draft=draft,
            envelopes=draft.provenance,
            transcription=self._transcription(),
        )
        assert all(not candidate.role_evidence for candidate in candidates), (
            "the grounding stage must drop a claim the document does not carry"
        )

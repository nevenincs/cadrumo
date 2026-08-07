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
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ....llm import LLMProviderError
from .. import _evidence_draft as _router_module
from .._evidence import PurchaseInvoiceEvidenceInputError
from .._evidence_draft import FieldProvenance, InvoiceDraft
from .._evidence_input import EvidenceInput
from .._evidence_textlayer import transcribe_text_layer
from .._grounded_reading import (
    GROUNDABLE_ORIGINS,
    _identity_candidates,
    ground_draft_against_transcription,
    verified_provenance,
)
from .._identity_roles import IdentityCandidate, resolve_counterparty_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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


def test_a_vision_envelope_is_never_upgraded_by_a_text_transcription() -> None:
    """The anchor-strength split survives the wiring.

    A self-reported anchor has nothing independent behind it. Upgrading it
    against some other lane's transcription would manufacture exactly the
    verified-looking record the split exists to prevent.
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
    assert FieldOrigin.VISION not in GROUNDABLE_ORIGINS


def test_the_router_text_path_runs_the_whole_chain() -> None:
    """The connection itself: the router must reach transcribe, extract and ground.

    Asserted structurally against the router's own source rather than by running
    a model, because the semantic read needs inference this gate must not
    perform. What is proven here is that the chain is WIRED -- the behavioural
    halves are proven above and in the stage suites.
    """
    router = Path(__file__).parents[1] / "_evidence_draft.py"
    source = router.read_text(encoding="utf-8")

    assert "transcribe_text_layer(evidence_input)" in source
    assert "extract_invoice_fields_from_text" in source
    assert "ground_draft_against_transcription" in source


# The companion property -- that the label-regex family is not merely unreached
# but absent -- is owned by ``test_no_label_regex_reader.py``, which walks the
# router's AST rather than slicing its source text. A source slice cannot tell a
# call from the same characters inside a comment or docstring, and it silently
# truncates when the region it measures grows.


# ---------------------------------------------------------------------------
# A missing reader REFUSES; it never silently escalates to a heavier engine
# ---------------------------------------------------------------------------


def test_an_absent_reader_refuses_and_names_the_provisioning_verb() -> None:
    """ "No reader" is a gap the operator can close, so the refusal says how.

    The message names ``aeat config provision pull`` rather than reporting a
    bare failure. A refusal that does not say how to fix itself is a dead end,
    and this is the most consequential degradation the path can produce: the
    operator gets no fields at all.
    """
    from .._evidence_draft import _refuse_a_text_read_with_no_reader

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _refuse_a_text_read_with_no_reader(LLMProviderError("no provider reachable"))

    assert raised.value.suggestion == "aeat config provision pull"
    message = str(raised.value)
    assert "was not read" in message, "the operator must be told nothing was extracted"
    assert "no value was guessed" in message


def test_a_missing_reader_does_not_fall_through_to_the_vision_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    import cadrumo.llm as llm_module

    from .._evidence_draft import _read_transcription_semantically

    def unavailable(*args: object, **kwargs: object) -> object:
        raise LLMProviderError("Ollama is not reachable")

    monkeypatch.setattr(llm_module, "extract_invoice_fields_from_text", unavailable)

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _read_transcription_semantically(_control_evidence(), _control_transcription())

    assert raised.value.suggestion == "aeat config provision pull"


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

    module = ast.parse(Path(inspect.getfile(_router_module)).read_text(encoding="utf-8"))
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
    from .._evidence_draft import extract_invoice_draft_from_evidence

    source = inspect.getsource(extract_invoice_draft_from_evidence)

    assert "except PurchaseInvoiceEvidenceInputError" in source
    assert "_extract_invoice_fields_via_vision" in source


def test_the_refusals_provision_verb_survives_to_the_error_envelope() -> None:
    """The remedy must reach the operator, not be replaced by the registry default.

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
    from ....core.errors import get_error_suggestion
    from .._evidence_draft import _refuse_a_text_read_with_no_reader

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _refuse_a_text_read_with_no_reader(LLMProviderError("Ollama is not reachable"))

    assert get_error_suggestion(raised.value) == "aeat config provision pull"


class TestTheReadingPathSuppliesNoManufacturedRoleEvidence:
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
    """

    @staticmethod
    def _candidates(**values: str) -> tuple[IdentityCandidate, ...]:
        draft = InvoiceDraft(**values)
        return _identity_candidates(draft=draft, envelopes=())

    def test_no_candidate_arrives_carrying_evidence(self) -> None:
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

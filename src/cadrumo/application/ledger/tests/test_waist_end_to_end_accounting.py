"""The end-to-end waist gate: one document, every hop, per-hop field accounting.

Every hop in the ingestion chain is individually gated elsewhere. Nothing proved
a document survives ALL of them, and that is precisely where this codebase's
recurring defect lives: a counterparty extracted correctly and discarded at a
projection, a foreign tax id read and dropped at grounding, provenance envelopes
gated over an empty tuple. **Every one was a value that survived its own hop and
died between hops.** An outcome test cannot catch that class -- it reports that
the end is wrong without saying where the value died.

So this gate accounts per hop: for each one it asserts what ENTERED and what
LEFT, and each assertion names its hop. A field lost anywhere is attributed to
the hop that lost it.

**No model in CI, by construction rather than by configuration.** The fixture is
a structured e-invoice, and the router sends a structured record to the exact
parser -- so this document reaches no model at all. That is the routing control
the accepted design specifies, and it makes the whole chain deterministic: a per-hop
accounting assertion over it is a statement about the pipeline rather than about
a model's mood.

**On the transcription hop.** The hop list names transcription between
ingest and extraction. For an exact-parse fixture that hop does not exist, and
its absence is the control, not a gap: a document that never becomes text for a
model cannot be prompt-injected. Rather than fabricate a transcription this route
does not produce, the gate asserts the bypass itself -- the document is a
structured shape, and it reaches the exact reader. That is the honest per-hop
statement for this route, and it is a stronger one than a transcription
assertion would have been.

Real behaviour throughout: the real parsers, the real invoice creation path, a
real encrypted bucket via the real repository, and the real invoice source
resolver that feeds Modelo 303. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....application.aggregation import CalculationSourceContext
from ....application.invoices import (
    InvoiceCatalogueSourceResolver,
    build_catalogue_invoice,
    create_catalogue_invoice,
)
from ....core import STRUCTURED_DOCUMENT_SHAPES, BindingSourceKind, Period
from ....core.aggregation import INVOICE_BINDING_SOURCE_KINDS
from ....domain.attachments import (
    AttachmentFileContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.invoices import Invoice
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import TestRuntimeProfile
from ..closure_findings import closure_findings
from ..evidence_draft import _extract_invoice_fields_from_structured_record
from ..evidence_input import EvidenceInput, resolve_attachment_evidence_input

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_FIXTURE = _CORPUS / "facturae_32_recargo_invoice.xml"
_BUCKET_ID = "40404040-4040-4040-8040-404040404040"
_CAPTURED_AT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)

#: The facts this document states, as the document states them. This is the
#: census every hop is accounted against: a hop that drops one of these is the
#: hop that broke the chain, and the assertion that fails names it.
_DOCUMENT_FACTS: dict[str, object] = {
    "invoice_number": "FAC-2024-0007",
    "supplier_tax_id": "ESB12345674",
    "taxable_base": Decimal("100.00"),
    "recargo_amount": Decimal("5.20"),
    "grand_total": Decimal("126.20"),
}

#: The cuota the document prints for its single rate band. Deliberately NOT the
#: draft's ``iva_amount``, which carries cuota PLUS recargo -- see the hop-4
#: class, where that difference in meaning is the defect under record.
_PRINTED_CUOTA = Decimal("21.00")


def _amount(key: str) -> Decimal:
    """Return one document fact as the Decimal it is.

    The census above is deliberately one mapping of mixed types, so reading a
    money term out of it yields ``object`` and any arithmetic on it checks
    nothing. Asserted rather than cast, so a fact that stops being a Decimal
    fails here by name.
    """
    value = _DOCUMENT_FACTS[key]
    assert isinstance(value, Decimal), f"{key} is {type(value).__name__}, not an amount"
    return value


#: The tax-id form the invoice boundary stores. The document states the IVA form
#: with its country prefix; the catalogue stores the bare Spanish NIF. This is a
#: normalisation, not a loss, and hop 5 asserts it AS a transformation so a
#: future silent change of form is still caught.
_STORED_TAX_ID = "B12345674"


runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _evidence() -> EvidenceInput:
    """Hop 1 -- ingest. Document bytes become the typed in-memory carrier."""
    data = _FIXTURE.read_bytes()
    return EvidenceInput(
        mime_type="application/xml",
        data=data,
        content_sha256=sha256(data).hexdigest(),
        evidence_id="ev-waist",
        attachment_id=None,
    )


class TestHop1Ingest:
    """The real ingest path: encrypted store in, typed in-memory carrier out.

    Driven through the production resolver over a real attachment store in a
    real encrypted bucket, rather than by constructing the carrier here. A test
    that builds the carrier from bytes it just read asserts its own arithmetic:
    nothing production-side sits between the two, so no mutation can break it
    and the hop is accounted in name only.
    """

    @staticmethod
    def _stored_attachment(tmp_path: Path) -> str:
        source = tmp_path / "waist-invoice.xml"
        source.write_bytes(_FIXTURE.read_bytes())
        return add_attachment(
            AttachmentStore(),
            content=AttachmentFileContent(path=source),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.OTHER,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="waist-gate",
                mime_type="application/xml",
                captured_at=_CAPTURED_AT,
            ),
        ).attachment_id

    def test_the_bytes_come_back_out_of_the_encrypted_store_unchanged(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        attachment_id = self._stored_attachment(tmp_path)

        evidence = resolve_attachment_evidence_input(attachment_id, store=AttachmentStore())

        assert evidence.data == _FIXTURE.read_bytes(), "hop 1 ingest: the stored bytes must survive the round trip"
        assert evidence.content_sha256 == sha256(_FIXTURE.read_bytes()).hexdigest(), "hop 1 ingest: content address"

    def test_the_resolved_carrier_still_routes_as_a_structured_record(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """The join to hop 2: bytes out of the store must reach the same routing."""
        attachment_id = self._stored_attachment(tmp_path)

        evidence = resolve_attachment_evidence_input(attachment_id, store=AttachmentStore())

        assert evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES
        assert evidence.attachment_id == attachment_id, "hop 1 ingest: provenance back to the stored blob"


class TestHop2RoutingBypassesTranscriptionAndTheModel:
    """The exact-parse route reaches no model, so there is no transcription to make.

    Asserted as the control it is. A document routed here cannot be
    prompt-injected, because nothing ever asks a model to read it.
    """

    def test_the_document_is_recognised_as_a_structured_shape(self) -> None:
        assert _evidence().document_shape in STRUCTURED_DOCUMENT_SHAPES, (
            "hop 2 routing: a structured record must be recognised, or it falls through to a model"
        )

    def test_the_shape_is_decided_on_the_bytes_not_the_declared_media_type(self) -> None:
        """The label says PDF; the bytes say XML. Routing on the label is the defect.

        The mislabel is deliberate and carries the whole assertion: this carrier
        announces ``application/pdf`` over a standalone structured XML invoice.
        A read path trusting the declared media type would call it a PDF and send
        it to prose extraction; the probe opens the bytes and routes it to the
        exact reader.
        """
        data = _FIXTURE.read_bytes()
        mislabelled = EvidenceInput(
            mime_type="application/pdf",
            data=data,
            content_sha256=sha256(data).hexdigest(),
            evidence_id="ev-waist-mislabelled",
            attachment_id=None,
        )

        assert mislabelled.document_shape in STRUCTURED_DOCUMENT_SHAPES


class TestHop3Extraction:
    """The exact reader turns the record into a draft, losing no stated fact."""

    def test_every_document_fact_reaches_the_draft(self) -> None:
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        for field, expected in _DOCUMENT_FACTS.items():
            assert getattr(draft, field) == expected, f"hop 3 extraction: {field} did not survive the read"

    def test_the_draft_carries_the_per_rate_breakdown_rather_than_a_flat_pair(self) -> None:
        """A collapsed breakdown is the loss this reading path exists to prevent."""
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        assert len(draft.iva_breakdown) == 1, "hop 3 extraction: invoice-level taxes only"
        band = draft.iva_breakdown[0]
        assert band.iva_rate == Decimal("21.00")
        assert band.taxable_base == _DOCUMENT_FACTS["taxable_base"]
        assert band.iva_amount == _PRINTED_CUOTA, "hop 3 extraction: the band carries the printed cuota"

    def test_the_scalar_iva_amount_carries_the_cuota_alone(self) -> None:
        """The scalar and the per-band figure now state the same thing.

        This assertion is inverted from the one that first recorded the defect.
        The scalar used to carry cuota PLUS recargo, because the source format
        states a combined output-tax total under a name the draft uses for the
        cuota term; the next hop read it as cuota alone and added the recargo
        again. The reader now takes the cuota from the per-band amount, whose
        sibling element carries the surcharge, so the two figures agree by
        construction rather than by coincidence.
        """
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        assert draft.iva_amount == _PRINTED_CUOTA
        assert draft.recargo_amount == Decimal("5.20"), "the surcharge is carried, in its own term"


class TestHop4Grounding:
    """The two hops now agree about what ``iva_amount`` means. Inverted on the fix.

    This class was written to pin a LIVE defect, with the instruction that a pass
    meant the double-count had been fixed and the class should be inverted. It
    has been. What the defect was, kept because the shape is what makes the
    regression legible: hop 3 wrote ``iva_amount`` as cuota PLUS recargo, hop 4
    read it as cuota alone and added ``recargo_amount`` on top, and the closure
    identity missed by exactly the surcharge. An arithmetically perfect document
    -- 100,00 base, 21,00 cuota, 5,20 recargo, 126,20 total -- was reported
    inconsistent, so every recargo de equivalencia invoice raised a spurious
    blocking finding at the confirm boundary. A real and common Spanish regime,
    refused on a correct invoice.

    Neither hop was wrong on its own and no single-hop test could see it, which
    is the defect class this waist gate exists to catch. The fix landed in the
    module that owns hop 3: the reader takes the cuota from the per-band amount
    rather than from the combined total, so the term cannot acquire a surcharge.
    The check at hop 4 was deliberately NOT relaxed -- it implements the
    canonical identity correctly, and loosening it would have silenced real
    closure failures along with this false one.
    """

    def test_a_consistent_recargo_document_is_reported_consistent(self) -> None:
        """The regression, driven end to end from the bundled document.

        Keyed on the terms rather than on which finding kind is absent: two
        different faults reach the same closure finding -- a document that omits
        the recargo and one that double-counts it -- so asserting on the kind
        alone could not tell the fixed state from either.
        """
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        assert [item for item in closure_findings(draft) if item.field == "grand_total"] == []
        iva_amount, recargo_amount = draft.iva_amount, draft.recargo_amount
        assert iva_amount is not None and recargo_amount is not None, "the reader dropped a term entirely"
        assert _amount("taxable_base") + iva_amount + recargo_amount == _amount("grand_total")

    def test_the_documents_own_arithmetic_actually_closes(self) -> None:
        """The proof that the finding above is spurious rather than a real defect."""
        base = _DOCUMENT_FACTS["taxable_base"]
        assert isinstance(base, Decimal)

        assert base + _PRINTED_CUOTA + Decimal("5.20") == _DOCUMENT_FACTS["grand_total"]

    def test_the_double_counted_shape_would_still_be_caught(self) -> None:
        """The defect's own input shape, re-fed deliberately.

        The producer no longer emits it, so the only way to keep proving the
        check would catch its return is to construct it: the cuota term carrying
        the surcharge while the surcharge is also stated in its own slot.
        """
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        doubled = draft.model_copy(update={"iva_amount": _PRINTED_CUOTA + Decimal("5.20")})

        assert closure_findings(doubled), "a term carrying the surcharge twice must still red"

    def test_positive_control_a_genuinely_broken_total_is_still_caught(self) -> None:
        """Without this, a check that fired on everything would satisfy the class above."""
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        broken = draft.model_copy(update={"grand_total": Decimal("999.99")})

        assert closure_findings(broken), "hop 4 grounding: a real inconsistency must still red"


class TestHop5ConfirmAndHop6Invoice:
    """The draft is confirmed into a persisted Invoice through the real path."""

    @staticmethod
    def _confirm(runtime_profile: TestRuntimeProfile) -> Invoice:
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        return create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Proveedor Waist SL",
                counterparty_tax_id=draft.supplier_tax_id,
                counterparty_country="ES",
                invoice_number=draft.invoice_number or "FAC-2024-0007",
                issued_at=date(2024, 3, 15),
                taxable_base=draft.taxable_base or Decimal("0"),
                iva_rate=Decimal("21"),
                currency="EUR",
            ),
        ).invoice

    def test_the_invoice_carries_the_facts_the_draft_carried(self, runtime_profile: TestRuntimeProfile) -> None:
        invoice = self._confirm(runtime_profile)

        # The draft calls it taxable_base and the Invoice calls it base_total.
        # The value must be identical across that rename; a rename is where a
        # projection quietly drops a field, so it is asserted rather than assumed.
        assert invoice.base_total == _DOCUMENT_FACTS["taxable_base"], "hop 5 confirm: the base across the rename"
        assert invoice.invoice_number == _DOCUMENT_FACTS["invoice_number"], "hop 5 confirm: the number"

    def test_the_counterparty_identifier_is_normalised_not_lost(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        """The document states the IVA form; the catalogue stores the bare NIF.

        Asserted as a TRANSFORMATION with both forms named, rather than as a
        pass on whichever the code happens to produce. The identifier is what
        AEAT reconciles a counterparty declaration against, so a silent change of
        stored form is a defect even though nothing is dropped -- and an
        assertion written against only the output form would not notice one.
        """
        invoice = self._confirm(runtime_profile)

        assert _DOCUMENT_FACTS["supplier_tax_id"] == "ES" + _STORED_TAX_ID, "the two forms differ only by prefix"
        assert invoice.counterparty_tax_id == _STORED_TAX_ID, "hop 5 confirm: the identifier's stored form"

    def test_the_invoice_is_readable_back_from_the_encrypted_catalogue(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        """Hop 6 -- Invoice. Persisted through the real repository, not held in memory."""
        self._confirm(runtime_profile)

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        stored = [
            item for item in catalogue.invoices.values() if item.invoice_number == _DOCUMENT_FACTS["invoice_number"]
        ]

        assert len(stored) == 1, "hop 6 Invoice: exactly one record must survive the round trip"
        assert stored[0].base_total == _DOCUMENT_FACTS["taxable_base"], "hop 6 Invoice: the base survived storage"
        assert stored[0].counterparty_tax_id == _STORED_TAX_ID, "hop 6 Invoice: the counterparty survived storage"


class TestHop7WhereTheChainActuallyTerminates:
    """Modelo 303 is ledger-fed, so a confirmed Invoice does not reach it directly.

    The hop list names a hop from ``Invoice`` to the Modelo 303 observation. Measured
    against the registry, that hop does not exist: the 303 revision declares its
    IVA inputs exclusively through ``ledger_iva_aggregation`` and carries NO
    invoice-source binding at all. An invoice reaches 303 only as evidence
    attached to a ledger movement, and it is the ledger row that declares.

    Rather than assert a hop that is not built -- or quietly stop at hop 6 and
    let the gate read as complete -- the terminus is asserted as the structural
    fact it is, keyed on the registry rather than on a count, so the day 303
    grows an invoice-source binding this class reds and the accounting is
    extended to cover it.
    """

    @staticmethod
    def _revision() -> ModeloRevision:
        period = Period.from_year_and_code(2024, "1T")
        return bundled_authority().snapshot("303", filing_year=2024, period=str(period.code)).revision

    def test_modelo_303_declares_no_invoice_source_binding(self) -> None:
        revision = self._revision()

        invoice_sourced = [binding for binding in revision.bindings if binding.source in INVOICE_BINDING_SOURCE_KINDS]

        assert invoice_sourced == [], (
            "hop 7: Modelo 303 has grown an invoice-source binding; the waist now reaches it "
            "and this gate must be extended to account for that hop"
        )

    def test_modelo_303_takes_its_iva_from_the_ledger(self) -> None:
        """The positive half: naming what DOES feed it, so the negative is not vacuous."""
        revision = self._revision()

        ledger_sourced = [
            binding for binding in revision.bindings if binding.source is BindingSourceKind.LEDGER_IVA_AGGREGATION
        ]

        assert ledger_sourced, "Modelo 303 must draw its IVA from the ledger aggregation"

    def test_the_invoice_resolver_runs_and_honestly_returns_nothing_for_303(
        self,
        runtime_profile: TestRuntimeProfile,
    ) -> None:
        """The resolver is reached and declines, rather than silently never running."""
        TestHop5ConfirmAndHop6Invoice._confirm(runtime_profile)
        period = Period.from_year_and_code(2024, "1T")
        context = CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2024,
            period=period,
            revision=self._revision(),
        )

        resolution = InvoiceCatalogueSourceResolver(
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID),
        ).resolve(context)

        assert resolution.resolver_id == "invoice_catalogue"
        assert resolution.binding_values == {}, "no invoice-source binding exists on 303 to populate"

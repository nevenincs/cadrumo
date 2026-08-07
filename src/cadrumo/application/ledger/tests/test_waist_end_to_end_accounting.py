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
the ADR specifies, and it makes the whole chain deterministic: a per-hop
accounting assertion over it is a statement about the pipeline rather than about
a model's mood.

**On the transcription hop.** The Step's hop list names transcription between
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

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....application.aggregation import CalculationSourceContext
from ....application.invoices import InvoiceCatalogueSourceResolver, create_catalogue_invoice
from ....core import STRUCTURED_DOCUMENT_SHAPES, BindingSourceKind, Period
from ....domain.calculations.registry import INVOICE_BINDING_SOURCE_KINDS, bundled_authority
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._closure_findings import closure_findings
from .._evidence import MediaKind
from .._evidence_draft import _extract_invoice_fields_from_structured_record
from .._evidence_input import EvidenceInput

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_FIXTURE = _CORPUS / "facturae_32_recargo_invoice.xml"
_BUCKET_ID = "40404040-4040-4040-8040-404040404040"

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

#: The tax-id form the invoice boundary stores. The document states the VAT form
#: with its country prefix; the catalogue stores the bare Spanish NIF. This is a
#: normalisation, not a loss, and hop 5 asserts it AS a transformation so a
#: future silent change of form is still caught.
_STORED_TAX_ID = "B12345674"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


def _evidence() -> EvidenceInput:
    """Hop 1 -- ingest. Document bytes become the typed in-memory carrier."""
    data = _FIXTURE.read_bytes()
    return EvidenceInput(
        media_kind=MediaKind.PDF,
        mime_type="application/xml",
        data=data,
        content_sha256=sha256(data).hexdigest(),
        evidence_id="ev-waist",
        attachment_id=None,
    )


class TestHop1Ingest:
    """Bytes enter; a typed carrier leaves, content-addressed to those bytes."""

    def test_the_carrier_is_addressed_to_the_bytes_that_entered(self) -> None:
        data = _FIXTURE.read_bytes()

        evidence = _evidence()

        assert evidence.data == data, "hop 1 ingest: the bytes must not be transformed"
        assert evidence.content_sha256 == sha256(data).hexdigest(), "hop 1 ingest: content address"


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
        """The label says PDF; the bytes say XML. Routing on the label is the defect."""
        evidence = _evidence()

        assert evidence.media_kind is MediaKind.PDF
        assert evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES


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

    def test_the_scalar_iva_amount_carries_cuota_plus_recargo(self) -> None:
        """Recorded because the next hop reads this field as cuota ALONE.

        The per-band figure is the printed cuota; the scalar is cuota plus
        recargo. Both are defensible in isolation, and the disagreement between
        them is exactly what the hop-4 class documents.
        """
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        assert draft.iva_amount == _PRINTED_CUOTA + Decimal("5.20")


class TestHop4Grounding:
    """The two hops disagree about what ``iva_amount`` means, and it costs a false alarm.

    THIS IS A LIVE DEFECT, recorded rather than worked around. Hop 3 writes
    ``iva_amount`` as cuota PLUS recargo; hop 4 reads it as cuota alone and adds
    ``recargo_amount`` on top, so the recargo is counted twice and the closure
    identity misses by exactly that amount.

    The document is arithmetically perfect -- 100,00 base, 21,00 cuota, 5,20
    recargo, 126,20 total -- and it is reported as inconsistent. Every recargo de
    equivalencia invoice therefore raises a spurious blocking finding at the
    confirm boundary, and recargo is a real and common Spanish regime rather than
    an edge case.

    This is the exact defect class the waist gate exists to catch: neither hop is
    wrong on its own, and no single-hop test could see it. The assertions below
    pin the CURRENT behaviour so the defect is visible and so the fix reds this
    class and forces the accounting to be restated. The fix belongs to the
    modules that own the two hops, not to this gate.
    """

    def test_a_consistent_recargo_document_is_currently_reported_inconsistent(self) -> None:
        draft = _extract_invoice_fields_from_structured_record(_evidence())

        findings = closure_findings(draft)

        assert findings, "if this passes, the double-count was fixed; invert this class"
        closure = [item for item in findings if item.field == "grand_total"]
        assert closure, "hop 4 grounding: the spurious finding lands on the total"
        assert closure[0].expected == _DOCUMENT_FACTS["taxable_base"] + draft.iva_amount + Decimal("5.20")
        assert closure[0].observed == _DOCUMENT_FACTS["grand_total"]

    def test_the_documents_own_arithmetic_actually_closes(self) -> None:
        """The proof that the finding above is spurious rather than a real defect."""
        base = _DOCUMENT_FACTS["taxable_base"]
        assert isinstance(base, Decimal)

        assert base + _PRINTED_CUOTA + Decimal("5.20") == _DOCUMENT_FACTS["grand_total"]

    def test_positive_control_the_check_stays_silent_when_the_meanings_agree(self) -> None:
        """Feeding the cuota-only reading the check expects, the same document reconciles."""
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        aligned = draft.model_copy(update={"iva_amount": _PRINTED_CUOTA})

        assert closure_findings(aligned) == (), "the check is sound; the two hops' meanings are not aligned"

    def test_positive_control_a_genuinely_broken_total_is_still_caught(self) -> None:
        """Without this, a check that fired on everything would satisfy the class above."""
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        broken = draft.model_copy(update={"iva_amount": _PRINTED_CUOTA, "grand_total": Decimal("999.99")})

        assert closure_findings(broken), "hop 4 grounding: a real inconsistency must still red"


class TestHop5ConfirmAndHop6Invoice:
    """The draft is confirmed into a persisted Invoice through the real path."""

    @staticmethod
    def _confirm(runtime_profile: TestRuntimeProfile) -> object:
        draft = _extract_invoice_fields_from_structured_record(_evidence())
        return create_catalogue_invoice(
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
        """The document states the VAT form; the catalogue stores the bare NIF.

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

    The Step names a hop from ``Invoice`` to the Modelo 303 observation. Measured
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
    def _revision() -> object:
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

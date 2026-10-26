"""Read and merge deterministic label-based invoice drafts."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.hashing import sha256_hex
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .document_transcription import DocumentTranscription
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_textlayer import text_layer_transcriber_identity
from .evidence_textlayer_ports import EvidenceTextLayerPorts
from .invoice_draft_records import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft
from .invoice_label_assembly import (
    ARITHMETIC_FINDING_KINDS,
    assemble_tax_figures,
    assemble_totals,
    field_provenance,
    record_ambiguous_amounts,
    single_consensus,
)
from .invoice_label_collection import collect_label_occurrences
from .invoice_label_models import InvoiceLabelAssembly

__all__ = [
    "LABEL_READER_REQUIRED_FIELDS",
    "LabelReading",
    "merge_label_reading_with_model_draft",
    "read_invoice_fields_by_labels",
    "text_layer_reads_completely_by_labels",
]


LABEL_READER_REQUIRED_FIELDS = frozenset(
    {
        "invoice_number",
        "invoice_date",
        "supplier_tax_id",
        "supplier_name",
        "taxable_base",
        "iva_amount",
        "grand_total",
        "currency",
    },
)


class LabelReading(BaseModel):
    """What the label rules recovered from one transcription.

    Attributes:
        draft: The rule-read draft: values, ``TEXT_RULES`` envelopes and the
            findings the rules raised.
        read_fields: The draft fields that carry a rule-read value.
    """

    model_config = STRICT_FROZEN_CONFIG

    draft: InvoiceDraft
    read_fields: frozenset[str]

    @property
    def required_fields(self) -> frozenset[str]:
        """The fields this document needs before the rules can stand alone.

        A single rate is required only where cuota was charged: a multi-rate
        document states its rates per tier, and a zero cuota states none.
        """
        if len(self.draft.iva_breakdown) > 1 or self.draft.iva_amount == 0:
            return LABEL_READER_REQUIRED_FIELDS
        return LABEL_READER_REQUIRED_FIELDS | {"iva_rate"}

    @property
    def missing_required_fields(self) -> frozenset[str]:
        """Required fields the rules did not read."""
        return self.required_fields - self.read_fields

    @property
    def complete(self) -> bool:
        """Whether every required field was read, so no model is needed."""
        return not self.missing_required_fields


def read_invoice_fields_by_labels(
    transcription: DocumentTranscription,
    *,
    operation: PinnedAuthorityOperation,
) -> LabelReading:
    """Read every labelled invoice field the transcription prints.

    Args:
        transcription: A text-layer transcription, printed forms intact.
        operation: The pinned authority the tax-identifier checks resolve
            their format declarations from.

    Returns:
        The rule-read draft and the set of fields it populated. Deterministic:
        the same text always yields the same reading.
    """
    with validating_governed_facts(operation):
        collected = collect_label_occurrences(transcription.text)
    assembly = InvoiceLabelAssembly()
    for name in (
        "invoice_number",
        "invoice_series",
        "invoice_date",
        "supplier_name",
        "customer_name",
        "supplier_tax_id",
        "customer_tax_id",
        "currency",
    ):
        assembly.put(name, single_consensus(name, collected.values.get(name, []), assembly))
        if name in assembly.values and name in collected.role_evidence:
            assembly.role_evidence[name] = collected.role_evidence[name]
    for role, printed in collected.rejected_tax_ids.items():
        if role in assembly.values:
            continue
        assembly.findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.IDENTITY_UNVERIFIED,
                field=role,
                detail=(
                    f"the document prints {printed!r} as this party's tax identifier, but it fails its "
                    f"control-character check, so it was not accepted as a verified identity"
                ),
            ),
        )
    assemble_tax_figures(collected, assembly)
    assemble_totals(collected, assembly)
    record_ambiguous_amounts(collected, assembly)

    draft = InvoiceDraft.model_validate(
        {
            **assembly.values,
            "provenance": field_provenance(assembly),
            "discrepancies": tuple(assembly.findings),
            "raw_text_length": len(transcription.text),
            "transcription_sha256": transcription.source_content_sha256,
        },
    )
    return LabelReading(draft=draft, read_fields=frozenset(assembly.values))


def text_layer_reads_completely_by_labels(
    data: bytes,
    *,
    text_layer_ports: EvidenceTextLayerPorts,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether a PDF's text layer reads completely without a model.

    The same predicate the extraction router applies before calling the text
    model, exposed for callers that must decide ahead of extraction whether a
    document needs the inference lane at all. A document without a usable text
    layer answers ``False``.
    """
    try:
        pages = text_layer_ports.extract_pages_text(data)
    except PurchaseInvoiceEvidenceInputError:
        return False
    text = "\n".join(page for page in pages if page)
    if not text.strip():
        return False
    transcription = DocumentTranscription(
        text=text,
        page_count=len(pages),
        source_content_sha256=sha256_hex(data),
        transcriber=text_layer_transcriber_identity(),
    )
    return read_invoice_fields_by_labels(transcription, operation=operation).complete


def merge_label_reading_with_model_draft(reading: LabelReading, model_draft: InvoiceDraft) -> InvoiceDraft:
    """Fill the fields the rules could not read from a model's draft.

    Every field the rules read keeps its rule value and envelope; the model
    contributes only the rest. The rules' arithmetic findings are dropped once
    the model has supplied figures, because the shared closure check re-runs on
    the merged figures and would otherwise report the same identity twice.
    Identity findings are kept once per field.
    """
    rule_draft = reading.draft
    bookkeeping = {"provenance", "discrepancies", "raw_text_length", "transcription_sha256"}
    rule_owned = _rule_owned_fields(reading)
    merged_values = _merged_values(rule_draft, model_draft, rule_owned, bookkeeping)
    envelopes = _merged_envelopes(rule_draft, model_draft, rule_owned)
    findings = _merged_findings(rule_draft, model_draft, rule_owned, merged_values)
    return rule_draft.model_copy(
        update={
            **merged_values,
            "provenance": tuple(envelopes),
            "discrepancies": tuple(findings.values()),
        },
    )


def _rule_owned_fields(reading: LabelReading) -> set[str]:
    rule_owned = set(reading.read_fields)
    if "iva_breakdown" in rule_owned:
        # A multi-rate document has no single rate; a model's pick of one tier
        # must not re-enter beside the breakdown.
        rule_owned.add("iva_rate")
    return rule_owned


def _merged_values(
    rule_draft: InvoiceDraft,
    model_draft: InvoiceDraft,
    rule_owned: set[str],
    bookkeeping: set[str],
) -> dict[str, object]:
    return {
        name: getattr(rule_draft if name in rule_owned else model_draft, name)
        for name in type(rule_draft).model_fields
        if name not in bookkeeping
    }


def _merged_envelopes(
    rule_draft: InvoiceDraft,
    model_draft: InvoiceDraft,
    rule_owned: set[str],
) -> list[FieldProvenance]:
    rule_envelopes = {envelope.field: envelope for envelope in rule_draft.provenance}
    model_envelopes = {envelope.field: envelope for envelope in model_draft.provenance}
    envelopes: list[FieldProvenance] = []
    for name in type(rule_draft).model_fields:
        source = model_envelopes if name not in rule_owned and name in model_envelopes else rule_envelopes
        if name in source:
            envelopes.append(source[name])
    return envelopes


def _merged_findings(
    rule_draft: InvoiceDraft,
    model_draft: InvoiceDraft,
    rule_owned: set[str],
    merged_values: dict[str, object],
) -> dict[tuple[DraftDiscrepancyKind, str | None], DraftDiscrepancyFinding]:
    findings: dict[tuple[DraftDiscrepancyKind, str | None], DraftDiscrepancyFinding] = {}
    for finding in rule_draft.discrepancies:
        # Superseded once the model filled the cleared figure: the shared
        # closure check judges the merged figures instead.
        if finding.kind in ARITHMETIC_FINDING_KINDS and merged_values.get(finding.field or "") not in (None, ()):
            continue
        findings.setdefault((finding.kind, finding.field), finding)
    for finding in model_draft.discrepancies:
        if finding.field in rule_owned:
            continue
        findings.setdefault((finding.kind, finding.field), finding)
    return findings

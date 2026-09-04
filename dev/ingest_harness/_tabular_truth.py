"""Operator-authored column-role truth for the nine tabular exports.

**This truth is OPERATOR-GROUNDED, and that is the weaker claim.** Every other
figure in this harness is scored against the pinned corpus key. This one cannot
be: the key authors no column-role mapping for any tabular document, and all nine
carry ``ground_truth == {}``, so
:func:`~dev.ingest_harness._scoring.score_emission` refuses every one of them for want of
a denominator. The choice is between an operator-authored expectation and no
mapping measurement at all. Anything derived from it — an acceptance floor above
all — is a floor against an operator's judgement, never against the corpus, and
must be labelled that way wherever it is quoted.

**Provenance, stated so a later reader need not take it on trust.** This mapping
was derived from two sources only: the :class:`~core.FieldRole` member semantics,
and the header text each file prints. It was authored **before any model output
for these headers existed** — the transport was blocked at the time of writing
and no mapping call had ever returned. A fixture written after seeing a reader's
output is fitted to that reader and cannot falsify it; this one predates the
measurement it will score, so it can. The ordering is the guarantee, so it is
recorded here rather than asserted in a report.

**Expected-unmapped columns are the fabrication traps.** A column no role fits is
declared with expectation ``None``, which projects to a ``null``-truth slot — so
a reader claiming a real role there scores FABRICATED rather than merely wrong,
under exactly the rule the extraction lane already uses. That is the correct
severity: inventing a meaning for a running-balance column is how a bank's
closing balance silently becomes a movement amount.

**Ambiguity is declared, never resolved by fiat.** A one-role-per-column
constraint makes some columns genuinely admit more than one defensible answer: a
value date beside a booked date, a debit column beside a credit column, a
reference column that duplicates the description. Those carry
:attr:`ColumnExpectation.also_defensible`. The headline score stays strict
against the primary; the defensible alternates are reported as a DECOMPOSITION of
the wrong verdicts, never folded into the numerator. Scoring a defensible answer
as simply wrong would understate the reader, and silently accepting it would
overstate it — so both numbers are printed and neither is called the score alone.

See Also:
    :func:`~dev.ingest_harness._scoring.score_emission`
        Consumes the projection this module builds. No second scorer exists.
    :data:`~dev.ingest_harness._field_mapping.KEY_FIELD_MAPPINGS`
        The neighbouring map, and a different concept that should not be merged
        with this one: it translates the key's own FIELD vocabulary onto the
        draft's for documents that DO carry authored truth. This module authors
        truth where the key carries none, over table COLUMNS rather than fields.
        One adapts an existing denominator; the other creates one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ._key import CorpusDocument, CorpusKey

__all__ = [
    "TABULAR_COLUMN_ROLE_TRUTH",
    "ColumnExpectation",
    "TabularTruthError",
    "column_role_truth_document",
    "defensible_alternate_fields",
    "emission_from_roles",
    "slot_name",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

#: The emitted spelling of "no role fits this column". Translated to ``None`` on
#: the way into scoring because the scorer's abstention sentinels are the
#: extraction lane's vocabulary and do not carry this lane's token -- and an
#: UNMAPPED emission on an expected-unmapped column is a CORRECT abstention, not
#: an answer. Left untranslated it would score as fabrication on every trap slot
#: and invert the measurement.
UNMAPPED_ROLE_SPELLING: Final = "unmapped"


class TabularTruthError(RuntimeError):
    """The authored truth does not describe the file it claims to describe."""


class ColumnExpectation(BaseModel):
    """What one column of one export means, and what else would be defensible."""

    model_config = _STRICT

    column_index: int = Field(ge=0)
    header: str = Field(description="The header cell exactly as the file prints it; may be empty.")
    expected: str | None = Field(
        description="The role token this column should receive, or None when no role fits and a "
        "claim would be a fabrication.",
    )
    also_defensible: frozenset[str | None] = Field(
        default=frozenset(),
        description="Alternate answers a careful reader could defend under the one-role-per-column "
        "constraint. Reported as a decomposition, never scored as matched.",
    )


def slot_name(expectation: ColumnExpectation) -> str:
    """Name one slot so a verdict identifies the column without a lookup.

    Carries the position and the printed header, because a bare index sends the
    reader back to the file and a bare header does not survive an export that
    repeats one.
    """
    return f"col{expectation.column_index:02d}:{expectation.header or '<blank>'}"


def _expect(index: int, header: str, expected: str | None, *alternates: str | None) -> ColumnExpectation:
    return ColumnExpectation(
        column_index=index,
        header=header,
        expected=expected,
        also_defensible=frozenset(alternates),
    )


#: One entry per tabular export, keyed by the key's own ``doc_id``. Every column
#: the file carries is declared; nothing is omitted, so the denominator is the
#: file's own column count rather than a subset someone found convenient.
TABULAR_COLUMN_ROLE_TRUTH: Final[Mapping[str, tuple[ColumnExpectation, ...]]] = {
    "OP-ISS-libro_facturas_expedidas_2025_2026": (
        _expect(0, "fecha_expedicion", "invoice_date"),
        _expect(1, "numero_factura", "invoice_number"),
        _expect(2, "destinatario", "counterparty_name"),
        _expect(3, "nif_destinatario", "counterparty_nif"),
        _expect(4, "base_imponible", "taxable_base"),
        _expect(5, "tipo_iva", "iva_rate"),
        _expect(6, "cuota_iva", "iva_amount"),
        # FieldRole carries a retencion AMOUNT and no retencion RATE, so a claim
        # here has no member that fits and the honest answer is unmapped.
        _expect(7, "tipo_retencion", None),
        _expect(8, "importe_retencion", "retencion_amount"),
        _expect(9, "total_factura", "grand_total"),
    ),
    "OP-ISS-pos_zreport_20260514": (
        _expect(0, "SEC", None),
        _expect(1, "TICKET", "invoice_number"),
        _expect(2, "HORA", None),
        _expect(3, "BASE", "taxable_base"),
        _expect(4, "IVA_PCT", "iva_rate"),
        _expect(5, "CUOTA", "iva_amount"),
        _expect(6, "TOTAL", "grand_total"),
        _expect(7, "MEDIO", None),
    ),
    "OP-PUR-bank_bbva_2026Q1": (
        _expect(0, "Fecha", "booked_date"),
        # A value date is a real date the product has no member for, and only one
        # column may hold booked_date -- so either assignment is defensible.
        _expect(1, "F.Valor", None, "booked_date"),
        _expect(2, "Concepto", "notes"),
        _expect(3, "Movimiento", None),
        _expect(4, "Importe", "movement_amount"),
        _expect(5, "Divisa", "currency"),
        _expect(6, "Disponible", None),
        _expect(7, "Observaciones", None, "notes"),
    ),
    "OP-PUR-bank_caixa_excel_export_2026Q1": (
        _expect(0, "Fecha", "booked_date"),
        _expect(1, "Concepto", "notes"),
        _expect(2, "Importe", "movement_amount"),
        _expect(3, "Saldo", None),
        _expect(4, "", None),
    ),
    "OP-PUR-bank_neobank_2026Q1": (
        _expect(0, "booking_date", "booked_date"),
        _expect(1, "value_date", None, "booked_date"),
        _expect(2, "partner_name", "counterparty_name"),
        _expect(3, "reference", "notes", None),
        _expect(4, "type", None),
        _expect(5, "amount_eur", "movement_amount"),
        _expect(6, "currency", "currency"),
        _expect(7, "exchange_rate", None),
    ),
    "OP-PUR-bank_statement_2026Q1_Q2": (
        _expect(0, "Fecha operacion", "booked_date"),
        _expect(1, "Fecha valor", None, "booked_date"),
        _expect(2, "Concepto", "notes"),
        _expect(3, "Importe", "movement_amount"),
        _expect(4, "Saldo", None),
    ),
    "OP-PUR-expenses_app_export_2026": (
        # An expense tool's own row id is not an identifier addressing a ledger
        # transaction, which is what TRANSACTION_ID means -- but reading it that
        # way is defensible.
        _expect(0, "id", None, "transaction_id"),
        _expect(1, "date", "invoice_date", "booked_date"),
        _expect(2, "merchant", "counterparty_name"),
        _expect(3, "category", "category_id"),
        _expect(4, "net", "taxable_base"),
        _expect(5, "vat_rate", "iva_rate"),
        _expect(6, "vat", "iva_amount"),
        _expect(7, "gross", "grand_total"),
        _expect(8, "notes", "notes"),
        _expect(9, "receipt_attached", None),
    ),
    "OP-REC-ledger_erp_export_2026Q1": (
        _expect(0, "FECHAMOV", "booked_date"),
        _expect(1, "TIPO", None),
        _expect(2, "DESCRIPCION", "notes"),
        # Debit and credit are never both populated, and only one column may hold
        # movement_amount, so the pair is defensible either way round.
        _expect(3, "DEBE", "movement_amount", None),
        _expect(4, "HABER", None, "movement_amount"),
        _expect(5, "CTA", None),
        _expect(6, "", None),
    ),
    "OP-REC-libro_facturas_recibidas_2025_2026": (
        _expect(0, "FECHA", "invoice_date"),
        _expect(1, "NUM_FACTURA", "invoice_number"),
        _expect(2, "PROVEEDOR", "counterparty_name"),
        _expect(3, "NIF", "counterparty_nif"),
        _expect(4, "CATEGORIA", "category_id"),
        _expect(5, "BASE", "taxable_base"),
        _expect(6, "TIPO_IVA", "iva_rate"),
        _expect(7, "CUOTA_IVA", "iva_amount"),
        _expect(8, "TOTAL", "grand_total"),
        _expect(9, "OBSERVACIONES", "notes"),
    ),
}


def column_role_truth_document(doc_id: str, *, key: CorpusKey) -> CorpusDocument:
    """Project one export into a document whose truth is the authored mapping.

    The corpus key is pinned by content hash and read-only, so the authored truth
    cannot live inside it. This builds the document the scorer needs instead:
    every non-key field is taken from the real corpus entry, so language-derived
    caveats stay correct, and only ``ground_truth`` is replaced.

    ``tolerance_cents`` is forced to zero. Role tokens are not amounts, and
    carrying the document's own amount tolerance into a token comparison would
    let a numeric tolerance apply to a string it can never legitimately affect.

    Raises:
        TabularTruthError: When no truth is authored for ``doc_id``.
    """
    expectations = TABULAR_COLUMN_ROLE_TRUTH.get(doc_id)
    if expectations is None:
        raise TabularTruthError(
            f"no column-role truth is authored for {doc_id!r}; the authored set covers "
            f"{sorted(TABULAR_COLUMN_ROLE_TRUTH)}",
        )
    source = key.document(doc_id)
    return CorpusDocument(
        doc_id=source.doc_id,
        path=source.path,
        provenance_class=source.provenance_class,
        language=source.language,
        file_format=source.file_format,
        tolerance_cents=0,
        ground_truth={slot_name(expectation): expectation.expected for expectation in expectations},
        notes=source.notes,
    )


def emission_from_roles(doc_id: str, roles: Sequence[str]) -> dict[str, str | None]:
    """Turn one proposal's positional roles into an emission the scorer can read.

    Translates the UNMAPPED token to ``None`` so the scorer reads it as an
    abstention. See :data:`UNMAPPED_ROLE_SPELLING`: without this, declining to label a
    column would score as fabrication on every trap slot and the abstaining
    reader would look like the worst offender.

    Raises:
        TabularTruthError: When the proposal's column count disagrees with the
            authored column count, which means the two are describing different
            files and every verdict below would be misaligned by position.
    """
    expectations = TABULAR_COLUMN_ROLE_TRUTH.get(doc_id)
    if expectations is None:
        raise TabularTruthError(f"no column-role truth is authored for {doc_id!r}")
    if len(roles) != len(expectations):
        raise TabularTruthError(
            f"{doc_id}: the proposal carries {len(roles)} role(s) but {len(expectations)} column(s) are "
            "authored; a positional score across a length mismatch would compare unrelated columns",
        )
    return {
        slot_name(expectation): (None if role == UNMAPPED_ROLE_SPELLING else role)
        for expectation, role in zip(expectations, roles, strict=True)
    }


def defensible_alternate_fields(doc_id: str, roles: Sequence[str]) -> tuple[str, ...]:
    """Return the slots where the proposal gave a declared-defensible alternate.

    The decomposition behind the headline score: these are slots the strict
    comparison counted against the reader that a careful operator would not.
    Reported beside the score and never added into it.
    """
    expectations = TABULAR_COLUMN_ROLE_TRUTH.get(doc_id)
    if expectations is None:
        raise TabularTruthError(f"no column-role truth is authored for {doc_id!r}")
    matched: list[str] = []
    for expectation, role in zip(expectations, roles, strict=True):
        answered = None if role == UNMAPPED_ROLE_SPELLING else role
        if answered != expectation.expected and answered in expectation.also_defensible:
            matched.append(slot_name(expectation))
    return tuple(matched)

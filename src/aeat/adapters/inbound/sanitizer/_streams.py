"""Content-stream rewrite for :mod:`aeat.adapters.inbound.sanitizer`.

Walks every text-show operator on every page of a PDF and rewrites
the operand text in place against a :class:`TokenMap`. Pikepdf's
:func:`pikepdf.parse_content_stream` abstracts the literal-vs-hex
distinction at parse time — both forms surface as
:class:`pikepdf.String` instances whose ``bytes()`` and ``str()``
yield the decoded payload. :func:`pikepdf.unparse_content_stream`
emits literal form on round-trip; that is acceptable for the
sanitiser because layout cues (``Tm``, ``Td``, fonts, colours) are
preserved by-reference and only the *string content* is rewritten.

Five text-show operators are handled (PDF 32000-2 §9.4.3):

* ``Tj`` — show one string.
* ``TJ`` — show an array of strings + kerning numbers.
* ``'``  — move to next line and show a string.
* ``"``  — set spacing then show a string.

Each replacement is recorded as one :class:`Replacement` row in the
result tuple so the audit log identifies every edit by surface,
page index, instruction index, and SHA-256 of the cleartext.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, cast

import pikepdf
from pikepdf import (
    ContentStreamInstruction,
    Operator,
    Page,
    Pdf,
    String,
    parse_content_stream,
    unparse_content_stream,
)
from pikepdf import (
    Object as PikepdfObject,
)

if TYPE_CHECKING:
    from pikepdf.models._content_stream import UnparseableContentStreamInstructions

from ._records import Replacement, TokenMap

# Pre-built operator instances kept module-local — `Operator(...)`
# constructs a fresh QPDF object on every call so caching them
# saves allocations on every page walked.
_TJ = Operator("Tj")
_TJ_ARRAY = Operator("TJ")
_QUOTE = Operator("'")
_DOUBLEQUOTE = Operator('"')
_TEXT_OPERATORS = frozenset({_TJ, _TJ_ARRAY, _QUOTE, _DOUBLEQUOTE})


def apply_token_map_to_pdf(pdf: Pdf, mapping: TokenMap) -> tuple[Replacement, ...]:
    """Rewrites every text-show operand in ``pdf`` against ``mapping``.

    Args:
        pdf: An open :class:`pikepdf.Pdf` whose content streams
            should be rewritten in place.
        mapping: The declarative cleartext-to-synthetic mapping.

    Returns:
        A tuple of :class:`Replacement` rows recording every edit
        applied. Empty when the mapping was empty or no operand
        contained any cleartext value.
    """
    if mapping.is_empty():
        return ()

    flat_replacements = _flatten_mapping(mapping)
    edits: list[Replacement] = []
    for page_index, page in enumerate(pdf.pages):
        page_edits = _rewrite_page(page, page_index, flat_replacements, pdf)
        edits.extend(page_edits)
    return tuple(edits)


def _flatten_mapping(mapping: TokenMap) -> tuple[tuple[str, str, str], ...]:
    """Returns every replacement as ``(real, synthetic, sha)`` triples.

    The triples are ordered longest-real-first so a longer match
    cannot be shadowed by a shorter prefix during operand
    rewriting (matters when the operator concatenates multiple
    cleartext values into one operand).
    """
    triples: list[tuple[str, str, str]] = []
    categories = (
        mapping.nif,
        mapping.name,
        mapping.address,
        mapping.expediente,
        mapping.csv,
        mapping.nrc,
        mapping.iban,
        mapping.importe,
        mapping.arbitrary,
    )
    for category in categories:
        for entry in category:
            real = entry.real.get_secret_value()
            sha = hashlib.sha256(real.encode("utf-8")).hexdigest()
            triples.append((real, entry.synthetic, sha))
    triples.sort(key=lambda triple: len(triple[0]), reverse=True)
    return tuple(triples)


def _rewrite_page(
    page: Page,
    page_index: int,
    triples: tuple[tuple[str, str, str], ...],
    pdf: Pdf,
) -> list[Replacement]:
    """Rewrites the content streams of a single page in place.

    Pikepdf's :class:`ContentStreamInstruction` exposes
    ``operands`` and ``operator`` as read-only views — mutating
    the destructured operand list does not propagate back into the
    instruction. This function rebuilds the instruction list with
    fresh :class:`ContentStreamInstruction` objects whenever a
    text-show operand needs replacing, then re-serialises and
    swaps the page's content stream.
    """
    instructions = list(parse_content_stream(page))
    edits: list[Replacement] = []
    rebuilt: list[UnparseableContentStreamInstructions] = []
    mutated = False

    for instruction_index, instruction in enumerate(instructions):
        # parse_content_stream returns
        # ``ContentStreamInstruction | ContentStreamInlineImage`` —
        # only the former carries text-show operators; inline
        # images pass through unmodified.
        if not isinstance(instruction, ContentStreamInstruction):
            rebuilt.append(instruction)
            continue

        operator = instruction.operator
        if operator not in _TEXT_OPERATORS:
            rebuilt.append(instruction)
            continue

        new_operands = _rewrite_text_show_operands(
            # CAST-RATIONALE-SANITIZER-PIKEPDF-OPERAND-LIST: pikepdf's
            # ``ContentStreamInstruction.operands`` is the private QPDF
            # ``_ObjectList`` type; it is a runtime sequence but is not
            # statically typed as ``Sequence[...]``, so the cast is
            # required to satisfy the type checker without any loss of
            # safety — the actual runtime object is already sequence-like.
            cast("Sequence[PikepdfObject | int | float]", instruction.operands),
            operator=operator,
            triples=triples,
            page_index=page_index,
            instruction_index=instruction_index,
            edits=edits,
        )
        if new_operands is None:
            rebuilt.append(instruction)
        else:
            # ContentStreamInstruction's typed overload expects a
            # pikepdf ``_ObjectList``; passing the iterable form
            # (the second overload) is functionally identical and
            # avoids depending on a private QPDF type.
            rebuilt.append(_build_instruction(new_operands, operator))
            mutated = True

    if mutated:
        new_bytes = unparse_content_stream(rebuilt)
        page.Contents = pdf.make_stream(new_bytes)
    return edits


def _rewrite_text_show_operands(
    operands: Sequence[PikepdfObject | int | float],
    *,
    operator: object,
    triples: tuple[tuple[str, str, str], ...],
    page_index: int,
    instruction_index: int,
    edits: list[Replacement],
) -> list[PikepdfObject | int | float] | None:
    """Rewrite text-show operands for one instruction.

    Returns ``None`` when nothing changed, otherwise the full new operand list.
    """
    if operator in (_TJ, _QUOTE):
        return _rewrite_single_string_at(
            operands,
            target_index=0,
            triples=triples,
            page_index=page_index,
            instruction_index=instruction_index,
            edits=edits,
        )
    if operator == _DOUBLEQUOTE:
        # `aw Tw ac Tc string "`  → operands = [aw, ac, string]
        return _rewrite_single_string_at(
            operands,
            target_index=2,
            triples=triples,
            page_index=page_index,
            instruction_index=instruction_index,
            edits=edits,
        )
    if operator == _TJ_ARRAY:
        return _rewrite_array_string_elements(
            operands,
            triples=triples,
            page_index=page_index,
            instruction_index=instruction_index,
            edits=edits,
        )
    return None


def _rewrite_single_string_at(
    operands: Sequence[PikepdfObject | int | float],
    *,
    target_index: int,
    triples: tuple[tuple[str, str, str], ...],
    page_index: int,
    instruction_index: int,
    edits: list[Replacement],
) -> list[PikepdfObject | int | float] | None:
    target_operand = operands[target_index]
    if not isinstance(target_operand, String):
        return None
    new_operand, hits = _rewrite_string_operand(
        target_operand,
        triples,
        page_index=page_index,
        instruction_index=instruction_index,
    )
    if not hits:
        return None
    operand_list: list[PikepdfObject | int | float] = list(operands)
    operand_list[target_index] = new_operand
    edits.extend(hits)
    return operand_list


def _rewrite_array_string_elements(
    operands: Sequence[PikepdfObject | int | float],
    *,
    triples: tuple[tuple[str, str, str], ...],
    page_index: int,
    instruction_index: int,
    edits: list[Replacement],
) -> list[PikepdfObject | int | float] | None:
    # CAST-RATIONALE-SANITIZER-PIKEPDF-ARRAY-ELEMENT: operands[0] is a
    # pikepdf ``Array`` of String + numeric kerning entries; the static
    # operand union ``PikepdfObject | int | float`` cannot express that
    # narrowing, so the cast is required at this third-party type boundary.
    array = cast("pikepdf.Array", operands[0])
    new_array_elements: list[PikepdfObject] = []
    local_hits: list[Replacement] = []
    array_mutated = False
    for element_index in range(len(array)):
        element = array[element_index]
        if not isinstance(element, String):
            new_array_elements.append(element)
            continue
        new_operand, hits = _rewrite_string_operand(
            element,
            triples,
            page_index=page_index,
            instruction_index=instruction_index,
        )
        if hits:
            new_array_elements.append(new_operand)
            local_hits.extend(hits)
            array_mutated = True
        else:
            new_array_elements.append(element)
    if not array_mutated:
        return None
    edits.extend(local_hits)
    return [pikepdf.Array(new_array_elements)]


def _rewrite_string_operand(
    operand: String,
    triples: tuple[tuple[str, str, str], ...],
    *,
    page_index: int,
    instruction_index: int,
) -> tuple[String, list[Replacement]]:
    """Rewrites a single :class:`pikepdf.String` operand against ``triples``.

    Args:
        operand: The pikepdf String to rewrite.
        triples: ``(real, synthetic, sha)`` triples sorted by
            decreasing real-length.
        page_index: Index of the page in the PDF (zero-based).
        instruction_index: Index of the operator in the page's
            content-stream instruction list (zero-based).

    Returns:
        A 2-tuple of (new_operand, edits). ``new_operand`` is the
        original operand when no replacement applied; otherwise a
        fresh :class:`pikepdf.String` carrying the rewritten text.
        ``edits`` lists one :class:`Replacement` per real-value
        match.
    """
    text = _decode_operand(operand)
    edits: list[Replacement] = []
    encoding: Literal["literal", "hex"] = _classify_encoding(operand)
    rewritten = text
    for real, synthetic, sha in triples:
        if real and real in rewritten:
            occurrences = rewritten.count(real)
            rewritten = rewritten.replace(real, synthetic)
            for _ in range(occurrences):
                edits.append(
                    Replacement(
                        surface="content_stream",
                        surface_index=(page_index, instruction_index),
                        real_sha256=sha,
                        synthetic=synthetic,
                        encoding=encoding,
                    ),
                )
    if not edits:
        return operand, edits
    return String(rewritten), edits


def _decode_operand(operand: String) -> str:
    """Returns the decoded text of a :class:`pikepdf.String` operand.

    Pikepdf's ``str()`` decodes the operand using its declared
    encoding (PDFDocEncoding for legacy literal strings, UTF-16
    for BOM-prefixed strings, etc.). The sanitiser trusts that
    decode and operates on the resulting text — re-implementing
    PDF text encodings would re-introduce every CVE pikepdf
    already handles.
    """
    return str(operand)


def _classify_encoding(operand: String) -> Literal["literal", "hex"]:
    """Heuristic guess of whether ``operand`` was hex- or literal-encoded.

    Pikepdf does not expose the original syntactic form. We label
    the encoding ``hex`` when the decoded bytes contain any byte
    that PDFDocEncoding cannot represent (i.e. the source likely
    used hex for cp1252 fidelity), and ``literal`` otherwise. This
    field is informational — the rewrite outputs literal form
    either way.
    """
    raw = bytes(operand)
    for byte in raw:
        # PDFDocEncoding has gaps at 0x9D-0x9F; cp1252-only chars
        # land in those slots and reliably indicate the source
        # used hex. ASCII-only operands are flagged "literal".
        if byte in (0x9D, 0x9E, 0x9F):
            return "hex"
    return "literal"


def _build_instruction(
    operands: list[PikepdfObject | int | float],
    operator: Operator,
) -> ContentStreamInstruction:
    """Construct a :class:`ContentStreamInstruction` from a plain operand list.

    Centralises the construction so the static-type-checker comment
    lives in one place and call sites stay legible.
    """
    return ContentStreamInstruction(operands, operator)


# Keep the runtime dep edge explicit so the type checker does not
# prune the import.
_ = pikepdf

"""BOE-Orden extractor backend for AEAT modelo schemas.

This module owns the pipeline that reads primary AEAT sources
(currently BOE-published *Ordenes ministeriales*) and emits the typed,
versioned pydantic v2 records defined in :mod:`aeat.domain.schema`.

The public surface is :class:`BoeOrdenExtractor`, a line-based PDF
extractor bound to a
:class:`aeat.adapters.inbound.schema._fetch.FetchedSchemaSource`.
Consumers MUST import from this module only; the implementation
details are internal to this inbound adapter.

The intermediate-representation types (:class:`aeat.domain.schema.Modelo`,
:class:`aeat.domain.schema.Casilla`, etc.) and cache helpers
(:func:`aeat.domain.schema.save_modelo_to_cache`,
:func:`aeat.domain.schema.load_modelo_from_cache`) live in
:mod:`aeat.domain.schema`; this adapter imports from there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ....core.i18n import Translatable
from ....core.logging import get_logger
from ....domain.modelos import ModeloCode
from ....domain.schema._enums import BinaryFormulaOp, CasillaDataType, SchemaSource
from ....domain.schema._errors import SchemaExtractionError
from ....domain.schema._models import (
    BinaryOp,
    Casilla,
    FormulaNode,
    LiteralFormula,
    Modelo,
    SchemaCasillaRef,
    SchemaProvenance,
    SchemaVersion,
    SumFormula,
    _collect_refs,
    validate_period_for_modelo,
)
from ._fetch import FetchedSchemaSource

_logger = get_logger(__name__)

_ANNEX_RE = re.compile(r"^\s*ANEXO(?:\s+[IVX]+)?(?:\W|$)", re.IGNORECASE)
"""Matches ``ANEXO``, ``ANEXO I``, ``Anexo I Ã¢â,¬â€ Modelo 130``, etc.

Accepts a trailing word-boundary so inline headings (the shape real
BOE PDFs typeset) are recognised; a standalone ``ANEXO`` line still
matches because ``$`` is in the alternation.
"""

_CASILLA_DECL_RE = re.compile(
    r"^\s*(?P<id>\d{2,4})\s+(?P<label>[A-Za-zÃƒÂÃƒâ€°ÃƒÂÃƒâ€œÃƒÅ¡ÃƒÅ“Ãƒâ€˜ÃƒÂ¡ÃƒÂ©ÃƒÂ­ÃƒÂ³ÃƒÂºÃƒÂ¼ÃƒÂ±Ã,Â¿\(].*?)\s*$",
)
"""Matches ``NN <Spanish label>`` where the label starts with a letter,
Spanish inverted question mark (``Ã,Â¿`` Ã¢â,¬â€ interrogative casillas on
Modelos 303 / 390), or an opening parenthesis (``(`` Ã¢â,¬â€ qualified
labels like ``"(Antes: Casilla 9a)"``).

Constraining the leading character rules out page-footer lines that
start with another digit (``"29330 Viernes..."``), URLs, or
typesetting artifacts.
"""

_FORMULA_RE = re.compile(
    r"^\s*Casilla\s+(?P<id>\d{2,4})\s*=\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(r"^\s*#\s+(?P<heading>.+?)\s*$")
_CASILLA_REF_IN_BODY = re.compile(r"Casilla\s+(\d{2,4})", re.IGNORECASE)
_PERCENT_LITERAL_RE = re.compile(r"0[,\.](\d+)")

_MINUS_CHARS = ("\u2212", "\u2013", "\u2014")
"""Unicode minus variants (U+2212, en-dash, em-dash) BOE typesets."""

_MUL_CHARS = ("x", "X", "\u00d7")
"""Characters normalised to ASCII ``*`` in formula bodies."""

_WORD_BOUNDARY_ES_TEMPLATE = r"(?<![\wÃƒÂ¡ÃƒÂ©ÃƒÂ­ÃƒÂ³ÃƒÂºÃƒÂ±ÃƒÂ¼ÃƒÂÃƒâ€°ÃƒÂÃƒâ€œÃƒÅ¡Ãƒâ€˜ÃƒÅ“]){word}(?![\wÃƒÂ¡ÃƒÂ©ÃƒÂ­ÃƒÂ³ÃƒÂºÃƒÂ±ÃƒÂ¼ÃƒÂÃƒâ€°ÃƒÂÃƒâ€œÃƒÅ¡Ãƒâ€˜ÃƒÅ“])"

_CURRENCY_KEYWORDS: tuple[str, ...] = (
    "cuota",
    "importe",
    "base",
    "resultado",
    "rendimiento",
    "pago",
    "ingreso",
    "gasto",
    "beneficio",
    "retencion",
    "retenciÃƒÂ³n",
)
_PERCENT_KEYWORDS: tuple[str, ...] = ("%", "porcentaje")
"""Drop ``"tipo"`` Ã¢â,¬â€ it collides with currency labels like
*"Base del tipo general"*. The word ``%`` remains as the canonical
percent marker; ``"porcentaje"`` covers labels that spell it out.
"""

_INTEGER_KEYWORDS: tuple[str, ...] = ("ejercicio", "aÃƒÂ±o", "ejercicios")
"""Drop the accentless ``"ano"`` variant: it matched ``"aÃƒÂ±o"`` as a
substring and mis-classified currency labels containing ``"ano"``
(frequent in gerund / plural forms).
"""

_DATE_KEYWORDS: tuple[str, ...] = ("fecha",)


def _has_word(text: str, word: str) -> bool:
    """Word-boundary aware keyword match that handles Spanish diacritics."""
    if word in {"%"}:
        return word in text
    pattern = _WORD_BOUNDARY_ES_TEMPLATE.format(word=re.escape(word))
    return re.search(pattern, text) is not None


@dataclass(frozen=True)
class _CasillaDraft:
    """Internal frozen staging record for a casilla under construction.

    New drafts are synthesised (never mutated) when a formula is
    attached; this keeps the extractor's intermediate state
    immutable even before the final :class:`Casilla` is built.
    """

    casilla_id: str
    label_es: str
    data_type: CasillaDataType
    block_es: str | None
    source_page: int
    formula: FormulaNode | None


def _guess_data_type(label: str) -> CasillaDataType:
    """Classify a Spanish casilla label into a :class:`CasillaDataType`.

    Currency is checked before integer/date/percentage so that a
    compound label like *"Cuota a compensar de ejercicios anteriores"*
    (currency + integer keyword) resolves to ``CURRENCY_EUR``, not
    ``INTEGER``. Keyword matches use whole-word comparison with
    Spanish-diacritic-aware boundaries so ``"ano"`` does not match
    ``"aÃƒÂ±o"`` and ``"base"`` is not swallowed by the percent branch.
    """
    lowered = label.lower()
    for kw in _CURRENCY_KEYWORDS:
        if _has_word(lowered, kw):
            return CasillaDataType.CURRENCY_EUR
    for kw in _PERCENT_KEYWORDS:
        if _has_word(lowered, kw):
            return CasillaDataType.PERCENTAGE
    for kw in _DATE_KEYWORDS:
        if _has_word(lowered, kw):
            return CasillaDataType.DATE
    for kw in _INTEGER_KEYWORDS:
        if _has_word(lowered, kw):
            return CasillaDataType.INTEGER
    return CasillaDataType.CURRENCY_EUR


def _normalise_formula_body(body: str) -> str:
    """Normalise BOE typographic variants to ASCII operators.

    BOE Ordenes typeset formula lines as Spanish sentences; trailing
    sentence punctuation (``.``, ``,``, ``;``, ``:``) is stripped
    here so :func:`_parse_signed_terms` can anchor on the body's
    true end without false negatives.
    """
    out = body
    for mul in _MUL_CHARS:
        out = out.replace(mul, "*")
    for minus in _MINUS_CHARS:
        out = out.replace(minus, "-")
    return out.rstrip(".,;: \t")


def _parse_signed_terms(normalised: str) -> tuple[tuple[str, str], ...]:
    """Tokenise a normalised additive chain into ``((sign, casilla_id), ...)``.

    Returns an empty tuple if the body is not a pure
    ``[+|-] Casilla N ( [+|-] Casilla M )*`` chain Ã¢â,¬â€ the caller falls
    back to other shapes when this happens.
    """
    pattern = re.compile(
        r"(?P<sign>[+\-])?\s*Casilla\s+(?P<id>\d{2,4})",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(normalised))
    if not matches:
        return ()
    # Require the chain to cover the body (ignoring trailing whitespace).
    last = matches[-1]
    if last.end() != len(normalised.rstrip()):
        # Trailing content we do not understand Ã¢â,¬â€ refuse to guess.
        return ()
    terms: list[tuple[str, str]] = []
    for match in matches:
        sign = match.group("sign") or "+"
        terms.append((sign, match.group("id")))
    return tuple(terms)


def _parse_formula_prose(casilla_id: str, body: str) -> FormulaNode:
    """Translate the Spanish prose after ``Casilla X =`` into a :class:`FormulaNode`.

    Supported shapes:

    - ``Casilla A + Casilla B`` and arbitrary ``+ / -`` chains (e.g.
      ``Casilla 01 + Casilla 02 - Casilla 03``). Unicode minus
      variants (``U+2212``, en-dash, em-dash) are normalised to ASCII.
    - ``Casilla A x 0,20`` / ``* 0,20`` (percent multiply Ã¢â,¬â€ BOE glyph
      U+00D7 MULTIPLICATION SIGN is normalised to ASCII ``*``).
    - A single ``Casilla A`` passthrough.

    Mixed ``+ / -`` chains are represented as a :class:`SumFormula`
    where the negative terms are wrapped in
    ``BinaryOp(SUB, 0, SchemaCasillaRef(id))``. Two-term subtractions
    collapse to a single :class:`BinaryOp` for readability.

    Raises:
        SchemaExtractionError: For any body that does not match one
            of the above shapes.
    """
    normalised = _normalise_formula_body(body)
    refs = _CASILLA_REF_IN_BODY.findall(body)
    if not refs:
        raise SchemaExtractionError(
            f"formula body for casilla {casilla_id!r} has no Casilla refs: {body!r}",
        )
    percent_match = _PERCENT_LITERAL_RE.search(normalised)
    if percent_match and len(refs) == 1 and "*" in normalised:
        literal = Decimal("0." + percent_match.group(1))
        return BinaryOp(
            op=BinaryFormulaOp.MUL,
            left=SchemaCasillaRef(casilla_id=refs[0]),
            right=LiteralFormula(value=literal),
        )
    terms = _parse_signed_terms(normalised)
    if terms:
        if len(terms) == 1 and terms[0][0] == "+":
            return SchemaCasillaRef(casilla_id=terms[0][1])
        if len(terms) == 2 and terms[0][0] == "+" and terms[1][0] == "-":
            return BinaryOp(
                op=BinaryFormulaOp.SUB,
                left=SchemaCasillaRef(casilla_id=terms[0][1]),
                right=SchemaCasillaRef(casilla_id=terms[1][1]),
            )
        sum_terms: list[FormulaNode] = []
        for sign, cid in terms:
            ref = SchemaCasillaRef(casilla_id=cid)
            if sign == "+":
                sum_terms.append(ref)
            else:
                sum_terms.append(
                    BinaryOp(
                        op=BinaryFormulaOp.SUB,
                        left=LiteralFormula(value=Decimal("0")),
                        right=ref,
                    ),
                )
        return SumFormula(terms=tuple(sum_terms))
    raise SchemaExtractionError(
        f"cannot parse formula body for casilla {casilla_id!r}: {body!r}",
    )


def _build_translatable(es_text: str) -> Translatable:
    return Translatable(es=es_text)


class BoeOrdenExtractor:
    """Line-based extractor for BOE-Orden PDFs approving an AEAT modelo.

    The extractor is deliberately narrow and targets the Modelo 130
    Orden layout. Subclasses are expected to extend the pattern
    library for 303, 390, and the remaining modelos covered by
    :class:`aeat.domain.modelos.ModeloCode`.
    """

    def __init__(
        self,
        source: FetchedSchemaSource,
        modelo_code: ModeloCode,
        period: str,
    ) -> None:
        """Build an extractor bound to a fetched source record.

        Args:
            source: Provenance + on-disk PDF path for the Orden.
            modelo_code: Target modelo identifier.
            period: Filing period string (validated against the
                modelo's cadence during :meth:`extract`).
        """
        if source.modelo_code != modelo_code:
            raise SchemaExtractionError(
                "BoeOrdenExtractor source.modelo_code "
                f"{source.modelo_code!r} does not match modelo_code "
                f"{modelo_code!r}",
            )
        self._source = source
        self._modelo_code = modelo_code
        self._period = period

    def extract(self) -> Modelo:
        """Parse the bound PDF and return the :class:`Modelo` record.

        Returns:
            The extracted :class:`Modelo` with provenance populated
            from the bound :class:`FetchedSchemaSource`.

        Raises:
            SchemaExtractionError: When the annex heading is absent
                or a formula body cannot be parsed.
        """
        validate_period_for_modelo(self._modelo_code, self._period)
        annex_lines = self._read_annex_lines()
        drafts = self._parse_annex_lines(annex_lines)
        casillas = tuple(
            Casilla(
                casilla_id=draft.casilla_id,
                label=_build_translatable(draft.label_es),
                block=(_build_translatable(draft.block_es) if draft.block_es else None),
                data_type=draft.data_type,
                required=draft.formula is None,
                computed=draft.formula is not None,
                formula=draft.formula,
                references_casillas=(tuple(sorted(_collect_refs(draft.formula))) if draft.formula is not None else ()),
                source_page=draft.source_page,
            )
            for draft in drafts
        )
        provenance = SchemaProvenance(
            source=SchemaSource.BOE_ORDEN,
            origin_url=self._source.origin_url,
            document_ref=self._source.boe_ref,
            sha256=self._source.sha256,
            content_length=self._source.content_length,
            fetched_at=self._source.fetched_at,
        )
        return Modelo(
            modelo_code=self._modelo_code,
            portal=None,
            period=self._period,
            casillas=casillas,
            provenance=provenance,
            extracted_at=datetime.now(tz=UTC),
            schema_version=SchemaVersion(boe_ref=self._source.boe_ref),
        )

    def _read_annex_lines(self) -> list[tuple[int, str]]:
        """Return ``(page_number, line)`` tuples starting after the annex heading.

        For compact BOE layouts where the annex heading and the first
        casilla share a single line (e.g. ``"ANEXO I 01 Base..."``),
        the residue to the right of the heading match is preserved as
        its own synthetic line so no declaration is lost.
        """
        # Lazy import: pdfplumber pulls in pdfminer.six + pillow, adding
        # hundreds of ms to every `aeat` CLI help screen. Defer the cost
        # to the point where it is actually required.
        import pdfplumber

        annex_start_page: int | None = None
        collected: list[tuple[int, str]] = []
        with pdfplumber.open(str(self._source.pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.splitlines()
                if annex_start_page is None:
                    for index, line in enumerate(lines):
                        match = _ANNEX_RE.match(line)
                        if match:
                            annex_start_page = page.page_number
                            residue = line[match.end() :].strip()
                            if residue:
                                collected.append((page.page_number, residue))
                            for remaining in lines[index + 1 :]:
                                collected.append((page.page_number, remaining))
                            break
                    continue
                for line in lines:
                    collected.append((page.page_number, line))
        if annex_start_page is None:
            raise SchemaExtractionError(
                f"annex heading (ANEXO) not found in BOE PDF {self._source.boe_ref!r}",
            )
        if not collected:
            raise SchemaExtractionError(
                f"annex is empty for BOE PDF {self._source.boe_ref!r}",
            )
        return collected

    def _parse_annex_lines(
        self,
        annex_lines: list[tuple[int, str]],
    ) -> list[_CasillaDraft]:
        """Two-pass parse: declarations first, formulas second.

        Pass 1 walks every line and records casilla declarations +
        block headings. Pass 2 walks again and binds formulas to
        already-declared casillas. This decouples the parser from
        pdfplumber's line-ordering guarantees (which can invert in
        column-based layouts) and allows a formula line to appear
        above its declaration without raising.

        Duplicate declarations: if a second declaration is *identical*
        to the first (same label and block heading), it is silently
        ignored Ã¢â,¬â€ BOE Ordenes occasionally repeat the form layout
        (e.g. multilingual annexes or summary pages). A conflicting
        duplicate (different label or different block) still raises
        so silent data loss is impossible.
        """
        declarations: dict[str, _CasillaDraft] = {}
        pending_formulas: list[tuple[int, str, str]] = []

        # Pass 1 Ã¢â,¬â€ declarations and blocks.
        current_block: str | None = None
        for page_number, raw_line in annex_lines:
            line = raw_line.strip()
            if not line:
                continue
            block_match = _BLOCK_RE.match(raw_line)
            if block_match:
                current_block = block_match.group("heading").strip() or None
                continue
            formula_match = _FORMULA_RE.match(line)
            if formula_match:
                pending_formulas.append(
                    (page_number, formula_match.group("id"), formula_match.group("body")),
                )
                continue
            casilla_match = _CASILLA_DECL_RE.match(line)
            if casilla_match and not line.lower().startswith("casilla"):
                casilla_id = casilla_match.group("id")
                label_es = casilla_match.group("label")
                incoming_block = current_block
                if casilla_id in declarations:
                    existing = declarations[casilla_id]
                    if existing.label_es == label_es and existing.block_es == incoming_block:
                        # Benign duplicate (repeated layout) Ã¢â,¬â€ ignore.
                        continue
                    raise SchemaExtractionError(
                        f"conflicting duplicate declaration for casilla "
                        f"{casilla_id!r} on page {page_number}: existing "
                        f"label/block {(existing.label_es, existing.block_es)!r} vs "
                        f"new {(label_es, incoming_block)!r}",
                    )
                declarations[casilla_id] = _CasillaDraft(
                    casilla_id=casilla_id,
                    label_es=label_es,
                    data_type=_guess_data_type(label_es),
                    block_es=incoming_block,
                    source_page=page_number,
                    formula=None,
                )
                continue

        # Pass 2 Ã¢â,¬â€ bind formulas to already-declared casillas.
        for page_number, formula_id, formula_body in pending_formulas:
            if formula_id not in declarations:
                raise SchemaExtractionError(
                    f"formula references undeclared casilla {formula_id!r} on page {page_number}",
                )
            draft = declarations[formula_id]
            if draft.formula is not None:
                raise SchemaExtractionError(
                    f"casilla {formula_id!r} has more than one formula",
                )
            declarations[formula_id] = _CasillaDraft(
                casilla_id=draft.casilla_id,
                label_es=draft.label_es,
                data_type=draft.data_type,
                block_es=draft.block_es,
                source_page=draft.source_page,
                formula=_parse_formula_prose(formula_id, formula_body),
            )

        if not declarations:
            raise SchemaExtractionError(
                f"no casillas detected in BOE PDF {self._source.boe_ref!r}",
            )
        return list(declarations.values())


__all__ = ("BoeOrdenExtractor",)



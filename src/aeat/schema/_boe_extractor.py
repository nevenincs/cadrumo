"""BOE-Orden extractor backend for :mod:`aeat.schema`.

Implements the line-based :class:`~aeat.schema.Extractor` for the
PDF form of an AEAT *Orden ministerial* published in the Boletín
Oficial del Estado. The extractor uses :mod:`pdfplumber` to read
text, skips every page up to and including the annex heading
(``ANEXO``), then walks subsequent pages line-by-line and classifies
each line as one of:

- ``CASILLA`` — declares a numbered box and its Spanish label.
- ``FORMULA`` — pins a casilla to an arithmetic expression referring
  to other casilla numbers.
- ``BLOCK`` — a heading line introducing a new section of the form.
- ``OTHER`` — ignored.

Pattern library is deliberately narrow and targets Modelo 130. The
2026-04-17 ADR §3 explains why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pdfplumber
from pydantic import AnyHttpUrl, AwareDatetime

from ..i18n import Translatable
from ..logging import get_logger
from ..models import ModeloCode
from ._enums import BinaryFormulaOp, CasillaDataType, SchemaSource
from ._errors import SchemaExtractionError
from ._fetch import FetchedSchemaSource
from ._models import (
    BinaryOp,
    Casilla,
    CasillaRef,
    FormulaNode,
    LiteralFormula,
    Modelo,
    SchemaProvenance,
    SchemaVersion,
    SumFormula,
    _collect_refs,
    validate_period_for_modelo,
)

_logger = get_logger(__name__)

_ANNEX_RE = re.compile(r"^\s*ANEXO(?:\s+[IVX]+)?\s*$", re.IGNORECASE)
_CASILLA_DECL_RE = re.compile(
    r"^\s*(?P<id>\d{2,4})\s+(?P<label>\S.+?)\s*$",
)
_FORMULA_RE = re.compile(
    r"^\s*Casilla\s+(?P<id>\d{2,4})\s*=\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(r"^\s*#\s+(?P<heading>.+?)\s*$")
_CASILLA_REF_IN_BODY = re.compile(r"Casilla\s+(\d{2,4})", re.IGNORECASE)
_PERCENT_LITERAL_RE = re.compile(r"0[,\.](\d+)")

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
    "retención",
)
_PERCENT_KEYWORDS: tuple[str, ...] = ("%", "tipo", "porcentaje")
_INTEGER_KEYWORDS: tuple[str, ...] = ("ejercicio", "año", "ano")
_DATE_KEYWORDS: tuple[str, ...] = ("fecha",)


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
    lowered = label.lower()
    for kw in _PERCENT_KEYWORDS:
        if kw in lowered:
            return CasillaDataType.PERCENTAGE
    for kw in _DATE_KEYWORDS:
        if kw in lowered:
            return CasillaDataType.DATE
    for kw in _INTEGER_KEYWORDS:
        if kw in lowered:
            return CasillaDataType.INTEGER
    for kw in _CURRENCY_KEYWORDS:
        if kw in lowered:
            return CasillaDataType.CURRENCY_EUR
    return CasillaDataType.CURRENCY_EUR


def _parse_formula_prose(casilla_id: str, body: str) -> FormulaNode:
    """Translate the Spanish prose after ``Casilla X =`` into a :class:`FormulaNode`.

    Supported shapes:

    - ``Casilla A + Casilla B`` (and ``+ ... + Casilla N`` chains).
    - ``Casilla A - Casilla B`` (two-term difference).
    - ``Casilla A x 0,20`` / ``* 0,20`` (percent multiply — the BOE
      glyph is U+00D7 MULTIPLICATION SIGN, normalised to ASCII ``*``).
    - A single ``Casilla A`` passthrough.

    Raises:
        SchemaExtractionError: For any body that does not match one
            of the above shapes.
    """
    normalised = re.sub(r"[xX\u00d7]", "*", body)
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
            left=CasillaRef(casilla_id=refs[0]),
            right=LiteralFormula(value=literal),
        )
    if "-" in normalised:
        if len(refs) != 2:
            raise SchemaExtractionError(
                f"formula for casilla {casilla_id!r} uses subtraction but "
                f"has {len(refs)} refs; only two-term differences are "
                f"supported in v1: {body!r}",
            )
        return BinaryOp(
            op=BinaryFormulaOp.SUB,
            left=CasillaRef(casilla_id=refs[0]),
            right=CasillaRef(casilla_id=refs[1]),
        )
    if "+" in normalised or len(refs) > 1:
        terms: tuple[FormulaNode, ...] = tuple(CasillaRef(casilla_id=r) for r in refs)
        return SumFormula(terms=terms)
    if len(refs) == 1:
        return CasillaRef(casilla_id=refs[0])
    raise SchemaExtractionError(
        f"cannot parse formula body for casilla {casilla_id!r}: {body!r}",
    )


def _build_translatable(es_text: str) -> Translatable:
    # ``Translatable`` is a TypedDict; constructing via dict keeps the
    # shape declarative and avoids a helper layer.
    return Translatable(es=es_text)


class BoeOrdenExtractor:
    """Line-based extractor for BOE-Orden PDFs approving an AEAT modelo.

    The extractor is deliberately narrow and targets the Modelo 130
    Orden layout. Follow-up PRs subclass / extend the pattern library
    for 303, 390, and the remaining modelos covered by
    :class:`aeat.models.ModeloCode`.
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
        if source.modelo_code is not modelo_code:
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
        fetched_at: AwareDatetime = self._source.fetched_at
        origin_url: AnyHttpUrl = self._source.origin_url
        provenance = SchemaProvenance(
            source=SchemaSource.BOE_ORDEN,
            origin_url=origin_url,
            document_ref=self._source.boe_ref,
            sha256=self._source.sha256,
            content_length=self._source.content_length,
            fetched_at=fetched_at,
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
        """Return ``(page_number, line)`` tuples starting after the annex heading."""
        annex_start_page: int | None = None
        collected: list[tuple[int, str]] = []
        with pdfplumber.open(str(self._source.pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.splitlines()
                if annex_start_page is None:
                    for line in lines:
                        if _ANNEX_RE.match(line):
                            annex_start_page = page.page_number
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
        declarations: dict[str, _CasillaDraft] = {}
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
                formula_id = formula_match.group("id")
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
                    formula=_parse_formula_prose(
                        formula_id,
                        formula_match.group("body"),
                    ),
                )
                continue
            casilla_match = _CASILLA_DECL_RE.match(line)
            if casilla_match and not line.lower().startswith("casilla"):
                casilla_id = casilla_match.group("id")
                if casilla_id in declarations:
                    raise SchemaExtractionError(
                        f"duplicate declaration for casilla {casilla_id!r} on page {page_number}",
                    )
                label_es = casilla_match.group("label")
                declarations[casilla_id] = _CasillaDraft(
                    casilla_id=casilla_id,
                    label_es=label_es,
                    data_type=_guess_data_type(label_es),
                    block_es=current_block,
                    source_page=page_number,
                    formula=None,
                )
                continue
        if not declarations:
            raise SchemaExtractionError(
                f"no casillas detected in BOE PDF {self._source.boe_ref!r}",
            )
        return list(declarations.values())

"""Deterministic regex parser for AEAT sanción / liquidación notification PDFs.

The documents AEAT serves behind a notification's *comparecencia* are text-native:
their printed figures carry a real text layer, so there is nothing to OCR and
nothing to infer. This parser is therefore **regex-first and fully
deterministic** — no language model sits anywhere on this path. The numbers it
returns are numbers a taxpayer pays or appeals against, and a probabilistic
reader that is usually right is the wrong instrument for a figure that gets
filed.

The parser has exactly two outcomes: a complete :class:`SancionLiquidacion`, or
a :class:`~adapters.inbound.notificacion.SancionParseError` naming every field
it could not resolve. There is deliberately no partial record and no
zero-filled record. A reader that returns clean zeros against a populated
surface reads as "nothing owed" at every layer above it, which is precisely how
a silent under-declaration reaches a filing.

Layout robustness rests on three independent guards rather than on trusting one
template:

* **Anchored value shapes.** Money must match the AEAT two-decimal
  comma-tailed shape end to end (:func:`~core.decimal.is_aeat_printed_money`,
  the one house grammar, which the IVA compensation wallet reader consults
  too), never merely contain one. A template that begins printing whole euros
  surfaces as the shape change it is instead of being silently reinterpreted as
  a thousands-grouped integer.
* **Conflicting-repeat detection.** AEAT repeats labels across page headers and
  summary blocks. A label repeated with the SAME value is a repeat; a label
  repeated with DIFFERENT values is genuinely ambiguous and refuses, because no
  single reading of it is defensible.
* **Printed-line reconciliation.** Every figure below is printed on the one
  document, so they must reconcile with each other. This checks the PARSE, not
  AEAT's arithmetic: a divergence means a label was bound to the wrong number.

Reconciliation is layout-independent by construction. AEAT prints the
reducciones either flat (each subtracted from the sanción) or sequentially
(each applied to the running amount), and both yield the same final payable:
``S - r30 - r40`` either way. Only the intermediate labels differ, so binding
the payable to ``Importe a ingresar`` when printed and to ``Diferencia``
otherwise reads both layouts correctly, and any third layout refuses loudly
rather than answering confidently.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel

from ....core.decimal._printed import is_aeat_printed_money
from ....core.i18n import tr
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from ....domain.notifications.sancion import SancionLiquidacion
from ..pdf._label_regex import parse_spanish_decimal
from .errors import SancionArithmeticError, SancionParseError

_CENT: Final = Decimal("0.01")
_ZERO: Final = Decimal("0.00")

_STRICT_PERCENTAGE_RE: Final[re.Pattern[str]] = re.compile(r"^\d{1,3}(?:,\d{1,2})?$")
"""Anchored percentage shape, comma-decimal, at most two decimals."""

# AEAT renders the amount with NO space before the unit: ``3.687,12euros``.
# The optional space is tolerated because the same template also renders
# ``1.234,56 euros`` in its summary blocks, but the unit itself is stripped
# before the anchored shape check runs, never matched loosely alongside it.
_CURRENCY_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"\s*(?:euros?|eur|€)\s*$", re.IGNORECASE)
_PERCENT_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"\s*%\s*$")

_NIF_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Z]{8,10}$")
_CLAVE_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Z]{10,30}$")
_REFERENCIA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Z/\-.]{4,40}$")

_MONEY_FIELDS: Final = ("base_sancion", "sancion_resultante", "reduccion_conformidad", "reduccion_pronto_pago")


# Label vocabulary. Keys are field names; values are the accent-stripped,
# whitespace-collapsed, lowercased label stems AEAT prints. Matching is done on
# a normalised copy of the line so ``Sanción``/``Sancion`` and single/double
# spacing are the same label, while the VALUE is always taken from the raw text.
_MONEY_LABELS: Final[Mapping[str, tuple[str, ...]]] = {
    "base_sancion": ("base sobre la que se liquida la sancion",),
    "sancion_resultante": ("sancion resultante",),
    "reduccion_conformidad": ("reduccion del 30%", "reduccion del 30 %"),
    "reduccion_pronto_pago": ("reduccion del 40%", "reduccion del 40 %"),
    "diferencia": ("diferencia",),
    "importe_a_ingresar": ("importe a ingresar",),
}
_PERCENT_LABELS: Final[Mapping[str, tuple[str, ...]]] = {
    "porcentaje_minimo": ("porcentaje minimo de sancion", "porcentaje de sancion"),
}
_TEXT_LABELS: Final[Mapping[str, tuple[str, ...]]] = {
    "clave_liquidacion": ("clave de liquidacion:",),
    "referencia": ("referencia:",),
    "nif": ("n.i.f.:", "nif:"),
}
_REQUIRED_FIELDS: Final = (
    "clave_liquidacion",
    "referencia",
    "nif",
    "base_sancion",
    "porcentaje_minimo",
    "sancion_resultante",
)
_TEXT_VALIDATORS: Final[Mapping[str, re.Pattern[str]]] = {
    "clave_liquidacion": _CLAVE_RE,
    "referencia": _REFERENCIA_RE,
    "nif": _NIF_RE,
}


def _fold_char(char: str) -> str:
    """Fold one character to its unaccented lowercase base, preserving length.

    Length preservation is the whole point: the folded line is searched for a
    label and the match's END OFFSET is reprojected onto the RAW line to take
    the value. A fold that changed length (plain NFKD decomposition does, and
    whitespace collapsing does) would shift that offset and slice the value in
    the wrong place.
    """
    base = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
    return (base[:1] or char).lower()


def _fold_line(line: str) -> str:
    """Return a length-aligned, accent-free, lowercase copy of ``line`` for label search."""
    return "".join(_fold_char(char) for char in line.replace("\xa0", " "))


def _normalise(text: str) -> str:
    """Fold and collapse whitespace, for whole-document vocabulary checks only.

    Values are never taken from this form: folding accents off a label is safe,
    but rewriting a printed figure is exactly how a decimal separator gets
    reinterpreted.
    """
    return re.sub(r"\s+", " ", _fold_line(text)).strip()


def _label_pattern(label: str) -> re.Pattern[str]:
    """Compile one label into a whitespace-tolerant pattern over folded text."""
    return re.compile(r"\s+".join(re.escape(part) for part in label.split()))


class _Hit(BaseModel):
    """One label match: the raw trailing text and the line it came from."""

    model_config = STRICT_FROZEN_CONFIG

    raw_value: str
    line_index: int


def _collect_hits(lines: Sequence[str], labels: Iterable[str]) -> list[_Hit]:
    """Return every place ``labels`` appears, paired with the raw text that follows it.

    A label whose own line carries no trailing text takes the next non-empty
    line's text instead: AEAT's templates print the value inline in the detail
    block and on the following line in the tabulated summary, and both are the
    same fact.

    The label is located on the length-aligned folded line and the value is
    then sliced from the RAW line at the same offset, so accent and spacing
    variation never touches the printed figure.
    """
    patterns = [_label_pattern(label) for label in labels]
    hits: list[_Hit] = []
    for index, line in enumerate(lines):
        folded = _fold_line(line)
        for pattern in patterns:
            match = pattern.search(folded)
            if match is None:
                continue
            trailing = line[match.end() :].strip() or _next_non_empty(lines, index)
            if trailing:
                hits.append(_Hit(raw_value=trailing, line_index=index))
            break
    return hits


def _next_non_empty(lines: Sequence[str], index: int) -> str:
    """Return the next non-blank line after ``index``, or an empty string."""
    for line in lines[index + 1 :]:
        if line.strip():
            return line.strip()
    return ""


def _resolve_single(
    field: str,
    hits: Sequence[_Hit],
    parse: Callable[[str], object],
    *,
    missing: list[str],
    malformed: list[str],
    ambiguous: list[str],
) -> object | None:
    """Reduce every hit for one field to a single value, or record why it cannot be.

    Repeats are expected — AEAT reprints labels in page headers and summary
    blocks — so identical parsed values collapse to one. Conflicting parsed
    values do not: the field is recorded ambiguous rather than resolved by
    position, because "the first one wins" is a guess about a template this
    parser does not control.
    """
    if not hits:
        missing.append(field)
        return None
    parsed: list[object] = []
    saw_malformed = False
    for hit in hits:
        try:
            parsed.append(parse(hit.raw_value))
        except SancionParseError:
            saw_malformed = True
    if not parsed:
        (malformed if saw_malformed else missing).append(field)
        return None
    distinct = {str(value) for value in parsed}
    if len(distinct) > 1:
        ambiguous.append(field)
        return None
    return parsed[0]


_DOT_LEADER_RE: Final[re.Pattern[str]] = re.compile(r"^[\s:]*(?:\.{2,}|_{2,}|…)[\s:]*")
"""Leading tabulation filler (a dot leader) AEAT prints between a label and its value.

Only a run of TWO OR MORE dots is stripped. A single leading dot is left in
place deliberately: it would be a malformed figure, and silently discarding it
would turn ``.843,56`` into a confident ``843,56``.
"""


def _strip_leaders(raw: str) -> str:
    r"""Remove tabulation filler and separator punctuation ahead of a printed value.

    Whitespace is trimmed from the ENDS and never rewritten inside the token.
    This function used to fold every non-breaking space to an ASCII space
    first, which destroyed the thousands separator AEAT actually prints: a
    genuine ``1\xa0234,56`` reached the anchored shape check as ``1 234,56``,
    and the check refuses that because an ASCII space is AEAT's column
    separator, not a thousands separator. The document was real and the reader
    rejected it.

    Nothing is lost by leaving the interior alone. ``str.strip`` already
    removes NBSP and narrow NBSP at the ends -- both answer ``str.isspace`` --
    and ``\s`` in the dot-leader pattern matches them too.
    """
    return _DOT_LEADER_RE.sub("", raw.strip()).strip()


def _parse_money(raw: str) -> Decimal:
    """Parse one AEAT money token, refusing anything that is not the exact shape.

    The shape check and the conversion are deliberately separate concerns. The
    anchored check is this reader's own strictness and stays here; turning a
    conforming Spanish-printed token into a :class:`~decimal.Decimal` is the
    project's one separator convention, so it is delegated rather than
    hand-rolled. Reversing that split -- delegating the check too -- would be a
    silent relaxation: the shared parser accepts ``1.843`` as US-style
    ``Decimal('1.843')``, which is exactly the reading the check exists to
    refuse.
    """
    cleaned = _CURRENCY_SUFFIX_RE.sub("", _strip_leaders(raw)).strip()
    if not is_aeat_printed_money(cleaned):
        raise SancionParseError(f"not an AEAT money shape: {raw!r}", malformed=("amount",))
    parsed = parse_spanish_decimal(cleaned)
    if parsed is None:  # pragma: no cover - the anchored shape check precedes this
        raise SancionParseError(f"money token failed decimal conversion: {raw!r}", malformed=("amount",))
    return round_to_cents(parsed)


def _parse_percentage(raw: str) -> Decimal:
    """Parse one AEAT percentage token as printed (``50,00 %`` is ``50.00``).

    Same split as :func:`_parse_money`: the anchored percentage shape is
    checked here, the comma-decimal conversion is delegated. The shape forbids
    a dot outright, so no thousands-versus-decimal reading arises.
    """
    cleaned = _PERCENT_SUFFIX_RE.sub("", _strip_leaders(raw)).strip()
    if not _STRICT_PERCENTAGE_RE.match(cleaned):
        raise SancionParseError(f"not an AEAT percentage shape: {raw!r}", malformed=("percentage",))
    parsed = parse_spanish_decimal(cleaned)
    if parsed is None:  # pragma: no cover - the anchored shape check precedes this
        raise SancionParseError(f"percentage token failed decimal conversion: {raw!r}", malformed=("percentage",))
    return parsed


def _text_parser(field: str) -> Callable[[str], object]:
    """Return a parser that accepts only the identifier shape declared for ``field``."""
    pattern = _TEXT_VALIDATORS[field]

    def parse(raw: str) -> str:
        stripped = _strip_leaders(raw)
        token = stripped.split()[0].strip().upper() if stripped else ""
        if not pattern.match(token):
            raise SancionParseError(f"not a valid {field}: {raw!r}", malformed=(field,))
        return token

    return parse


def _classify_objeto(normalised_text: str) -> Literal["sancion", "liquidacion"]:
    """Classify the act from the document's own vocabulary.

    A document printing a ``base sobre la que se liquida la sanción`` line is a
    sanción by its own words; anything else reaching this parser is read as a
    liquidación. The classification is never inferred from an amount.
    """
    return "sancion" if "sancion" in normalised_text else "liquidacion"


def parse_sancion_document(
    text: str,
    *,
    certificado_id: str,
    document_sha256: str,
) -> SancionLiquidacion:
    """Parse the extracted text of one AEAT sanción / liquidación PDF.

    Args:
        text: The document's extracted text layer, page order preserved and
            otherwise untransformed. Printed forms must survive verbatim:
            ``3.687,12`` stays ``3.687,12``, because the anchored shape check
            runs against exactly what AEAT printed.
        certificado_id: The notification the document was served under.
        document_sha256: Digest of the PDF bytes the text was extracted from.

    Returns:
        The complete :class:`SancionLiquidacion`.

    Raises:
        SancionParseError: When any required label is missing, any printed
            value fails its anchored shape check, or a label repeats with
            conflicting values. The error names every failing field.
        SancionArithmeticError: When the printed lines do not reconcile with
            each other, which means a label was bound to the wrong number.
    """
    lines = text.splitlines()
    missing: list[str] = []
    malformed: list[str] = []
    ambiguous: list[str] = []
    values = _parse_sancion_values(lines, missing=missing, malformed=malformed, ambiguous=ambiguous)
    payable = _resolve_payable(values, missing)
    _raise_if_sancion_parse_incomplete(
        certificado_id=certificado_id,
        missing=missing,
        malformed=malformed,
        ambiguous=ambiguous,
    )
    record = _build_sancion_record(
        values,
        text=text,
        payable=payable,
        certificado_id=certificado_id,
        document_sha256=document_sha256,
    )
    _assert_printed_lines_reconcile(record)
    return record


def _parse_sancion_values(
    lines: Sequence[str],
    *,
    missing: list[str],
    malformed: list[str],
    ambiguous: list[str],
) -> dict[str, object]:
    values: dict[str, object] = {}
    for field, labels in _TEXT_LABELS.items():
        values[field] = _resolve_single(
            field,
            _collect_hits(lines, labels),
            _text_parser(field),
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
        )
    for field, labels in _MONEY_LABELS.items():
        values[field] = _resolve_single(
            field,
            _collect_hits(lines, labels),
            _parse_money,
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
        )
    for field, labels in _PERCENT_LABELS.items():
        values[field] = _resolve_single(
            field,
            _collect_hits(lines, labels),
            _parse_percentage,
            missing=missing,
            malformed=malformed,
            ambiguous=ambiguous,
        )
    return values


def _resolve_payable(values: dict[str, object], missing: list[str]) -> object:
    # ``Importe a ingresar`` and ``Diferencia`` are alternative names for the
    # same fact across AEAT's two layouts. Presence, not truthiness, matters:
    # a printed ``0,00`` payable is still a stated fact.
    payable = values.get("importe_a_ingresar")
    if payable is None:
        payable = values.get("diferencia")
    if payable is not None:
        missing[:] = [field for field in missing if field not in {"importe_a_ingresar", "diferencia"}]
    else:
        missing.append("importe_a_ingresar")
    return payable


def _raise_if_sancion_parse_incomplete(
    *,
    certificado_id: str,
    missing: list[str],
    malformed: list[str],
    ambiguous: list[str],
) -> None:
    required_missing = tuple(f for f in missing if f in _REQUIRED_FIELDS or f == "importe_a_ingresar")
    required_malformed = tuple(f for f in malformed if f in _REQUIRED_FIELDS or f in _MONEY_FIELDS)
    if not (required_missing or required_malformed or ambiguous):
        return
    raise SancionParseError(
        "AEAT sanción document could not be read completely; refusing to return a partial record. "
        f"missing={required_missing!r} malformed={required_malformed!r} ambiguous={tuple(ambiguous)!r}",
        translated_message=tr("adapters.notificacion.errors.sancion_incomplete"),
        context={
            "certificado_id": certificado_id,
            "missing": ",".join(required_missing),
            "malformed": ",".join(required_malformed),
            "ambiguous": ",".join(ambiguous),
        },
        missing=required_missing,
        malformed=required_malformed,
        ambiguous=tuple(ambiguous),
    )


def _build_sancion_record(
    values: dict[str, object],
    *,
    text: str,
    payable: object,
    certificado_id: str,
    document_sha256: str,
) -> SancionLiquidacion:
    return SancionLiquidacion(
        certificado_id=certificado_id,
        clave_liquidacion=str(values["clave_liquidacion"]),
        referencia=str(values["referencia"]),
        nif=str(values["nif"]),
        objeto_tributario=_classify_objeto(_normalise(text)),
        base_sancion=_as_decimal(values["base_sancion"]),
        porcentaje_minimo=_as_decimal(values["porcentaje_minimo"]),
        sancion_resultante=_as_decimal(values["sancion_resultante"]),
        reduccion_conformidad=_optional_decimal(values.get("reduccion_conformidad")),
        reduccion_pronto_pago=_optional_decimal(values.get("reduccion_pronto_pago")),
        diferencia=_optional_decimal(values.get("diferencia")),
        importe_a_ingresar=_as_decimal(payable),
        document_sha256=document_sha256,
    )


def _as_decimal(value: object) -> Decimal:
    """Narrow a resolved value to ``Decimal``; unreachable unless resolution changed."""
    if not isinstance(value, Decimal):  # pragma: no cover - resolution guarantees the type
        raise SancionParseError(f"expected a parsed decimal, got {value!r}")
    return value


def _optional_decimal(value: object) -> Decimal | None:
    """Narrow an optional resolved value to ``Decimal | None``."""
    return value if isinstance(value, Decimal) else None


def _assert_printed_lines_reconcile(record: SancionLiquidacion) -> None:
    """Refuse a record whose printed lines contradict each other.

    Two independent checks, both over figures printed on the same document:

    * ``base × porcentaje`` must reproduce the printed ``sanción resultante``,
      which catches a base or a percentage bound to the wrong printed number.
    * ``sanción resultante`` minus the printed reducciones must reproduce the
      payable, which catches a reducción or a payable bound to the wrong line.

    Both allow one cent, and one cent only, for AEAT's own half-up rounding at
    the cent. A wider tolerance would start absorbing real mis-bindings, which
    is the entire failure this refuses.
    """
    expected_sancion = round_to_cents(record.base_sancion * record.porcentaje_minimo / Decimal("100"))
    if abs(expected_sancion - record.sancion_resultante) > _CENT:
        raise SancionArithmeticError(
            "AEAT sanción document does not reconcile: base times porcentaje does not reproduce the printed "
            f"sanción resultante. base={record.base_sancion} porcentaje={record.porcentaje_minimo} "
            f"printed={record.sancion_resultante} derived={expected_sancion}",
            translated_message=tr("adapters.notificacion.errors.sancion_does_not_reconcile"),
            context={
                "certificado_id": str(record.certificado_id),
                "check": "base_times_porcentaje",
                "printed": str(record.sancion_resultante),
                "derived": str(expected_sancion),
            },
            malformed=("sancion_resultante",),
        )

    expected_payable = record.sancion_resultante - record.reducciones_total
    if abs(expected_payable - record.importe_a_ingresar) > _CENT:
        raise SancionArithmeticError(
            "AEAT sanción document does not reconcile: sanción resultante less the printed reducciones does not "
            f"reproduce the payable amount. sancion={record.sancion_resultante} "
            f"reducciones={record.reducciones_total} printed={record.importe_a_ingresar} derived={expected_payable}",
            translated_message=tr("adapters.notificacion.errors.sancion_does_not_reconcile"),
            context={
                "certificado_id": str(record.certificado_id),
                "check": "sancion_less_reducciones",
                "printed": str(record.importe_a_ingresar),
                "derived": str(expected_payable),
            },
            malformed=("importe_a_ingresar",),
        )


__all__ = ["parse_sancion_document"]

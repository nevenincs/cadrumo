"""Vocabulary and helpers the tax literal sweep reads.

It holds the word lists and patterns, the registry readers and the small predicates the sweep
rules share.
"""

from __future__ import annotations

import ast
import re
import sys
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_LAST

_ROOT: Final = Path(__file__).resolve().parents[3]

SRC: Final = _ROOT / "src" / "cadrumo"

SCANNED: Final = (
    SRC / "domain",
    SRC / "application",
    SRC / "core",
    SRC / "adapters",
    SRC / "entrypoints",
    _ROOT / "src" / "cadrumo_client",
)

MACHINE_OWNERS: Final = ("cadrumo_client/", "adapters/persistence/storage/", "core/redaction/")

"""These read operating system answers, framing and byte sizes; no tax value reaches them."""

MECHANICS_OWNERS: Final = (
    "adapters/inbound/declaracion/bbox_extraction.py",
    "adapters/inbound/pdf/",
    "adapters/outbound/aeat/browser/",
    "adapters/outbound/calculation_summary_pdf/",
    "adapters/outbound/google/calc_sheets_apply_formatting.py",
    "adapters/outbound/workbook/",
    "adapters/outbound/llm/",
    "application/command_search/",
    "application/corpus_search/",
    "application/search/",
    "core/aeat_csv.py",
    "core/atomic_write.py",
    "core/connection_transport.py",
    "core/credentials.py",
    "core/darwin_transport.py",
    "core/decimal/",
    "core/errors/",
    "core/identity/",
    "core/xls_workbook.py",
    "core/log_",
    "core/logging.py",
    "core/paths.py",
    "core/period.py",
    "core/pid_liveness.py",
    "core/filing_year.py",
    "core/terminal_encoding.py",
    "core/text_fold.py",
    "core/windows_",
    "domain/calculations/registry/formula_operator_contracts.py",
    "entrypoints/tui/",
)

"""Terminal cells, page and sheet coordinates, search ranking, wire codecs, an identifier's lexical shape, Unicode
folding, platform codes, an operator's argument count and the calendar range of a period: these lay out, rank or
transport a value and hold none of their own."""

RECORD_DESIGN_OWNERS: Final = (
    "domain/calculations/registry/export_",
    "domain/calculations/registry/fixed_width_",
    "domain/calculations/registry/schema_exports.py",
)

RECORD_DESIGN_LETTERS: Final = frozenset({"A", "N"})

"""The field-type letters of a record design, read by the modules that parse its layout: the alphabet of what the
registry declares, not a value of any one form. Any other letter in these modules is still a finding."""

_MACHINE_UNIT_NAME: Final = re.compile(
    r"(?:^|_)(?:SECONDS|S|MS|MILLISECONDS|BYTES|KIB|PIXELS|POINTS|TOKENS|ATTEMPTS?|RETRIES|TEMPERATURE"
    r"|VERSION(?:_V\d+)?|TIMEOUT|AFTER_LOGIN|(?:CACHE|MEMO)_(?:MAX)?SIZE)$",
    re.IGNORECASE,
)

_PRODUCT_MECHANIC_WORDS: Final = frozenset(
    {
        "SAMPLE",
        "SAMPLES",
        "PREVIEW",
        "PREVIEWS",
        "SUMMARY",
        "MESSAGE",
        "MESSAGES",
        "ECHO",
        "ERRORS",
        "QUERY",
        "SEARCH",
        "PAGE",
        "PAGES",
        "FINDING",
        "FINDINGS",
        "INTENTS",
        "DISPLAY",
        "SCORE",
        "CONFIDENCE",
        "CHECKOUTS",
        "NONCE",
        "RETRY",
        "DIGESTS",
        "PAYLOAD",
        "EXPONENT",
        "FRESHNESS",
        "LOOKBACK",
        "HORIZON",
        "INSTANCES",
        "URGENT",
        "SOON",
        "RANK",
        "CONNECTIONS",
        "GAP",
        "LINES",
        "STATUS",
    }
)

"""One whole word of a name counting a mechanic of the product: a page, a retry, a sample, a score, a reading horizon.
A tax limit counts casillas, rows, amounts or days of a form, so ``RESEARCH_DEDUCTION_RATE`` does not borrow ``SEARCH``
and ``SOLIDARITY_SURCHARGE_THRESHOLD`` no longer reads as an operator's arity."""

_LEXICAL_NAME: Final = re.compile(
    r"(?:^|_)(?:EVENT_IDS|EXIT_CODE|STATUS_CODE|ISO_\d+|ALPHA\d|GROUP_WIDTH|GROUP_SIZE|FILE_NAME|KEY_MIN|SHORT_TEXT"
    r"|MODELO_ID|PERIOD_TOKEN|FRACTION_DIGITS|SHORTEST)(?:_|$)",
    re.IGNORECASE,
)

"""A whole phrase naming a lexical shape or transport code: a file name's length, an ISO code's width, an exit code."""

FILE_PERMISSION_NAME: Final = re.compile(r"(?:^|_)MODE$", re.IGNORECASE)

FILE_PERMISSIONS: Final = frozenset({0o600, 0o640, 0o644, 0o700, 0o750, 0o755})

YEAR_NAME: Final = re.compile(r"year|ejercicio", re.IGNORECASE)

_CENTURY: Final = 100

FORM_HANDING_MODULE: Final = re.compile(r"^producer_snapshot|_bindings|(?:^|_)rows?(?:_|$)|row_models")

FORM_HANDING_OWNERS: Final = (
    "application/filing/",
    "application/modelo/edit_apply_row_contracts.py",
    "domain/filing/",
    "domain/modelos/",
)

"""Where a value is on its way to a form's field: a width written here restates the record design."""

TEXT_WIDTH_CALLS: Final = frozenset({"ljust", "rjust", "center", "zfill"})

YEAR_WIDTH: Final = "4"

_NUMERIC_BOUNDS: Final = frozenset({"ge", "gt", "le", "lt"})

ARITHMETIC_BOUNDS: Final = frozenset({0, 1})

CODE_SHAPED: Final = re.compile(r"^\d{2,4}[A-Z]?$")

LETTER_CLAVE: Final = re.compile(r"^[A-Z]{1,2}$")

CLAVE_NAME: Final = re.compile(r"clave|subclave|tipo_|_code$|^code$|codigo", re.IGNORECASE)

MODELO_ADDRESS_CALLS: Final = frozenset(
    {
        "Modelo",
        "modelo_directory",
        "reading_snapshot",
        "revision",
        "revision_for_context",
        "select_revision_metadata",
        "snapshot",
    },
)

FORM_NAMED_MODULE: Final = re.compile(r"(?:^|_)m(\d{3})(?:_|$)")

MONTH_NAME: Final = re.compile(r"month", re.IGNORECASE)

DAY_NAME: Final = re.compile(r"days?(?:_|$)|dias", re.IGNORECASE)

COUNTRY_NAME: Final = re.compile(r"countr|iso", re.IGNORECASE)

LENGTH_BOUNDS: Final = frozenset({"min_length", "max_length"})

SHA256_HEX: Final = 64

_SMALLEST_CAPACITY: Final = 16

THOUSAND: Final = 1000

_COLLECTION_WIRE_FLOOR: Final = 10_000

LAST_FOUR_DIGIT_YEAR: Final = FOUR_DIGIT_YEAR_LAST

_CENT: Final = Decimal("0.01")

DATE_CALLS: Final = frozenset({"date", "datetime"})

ISO_DATE: Final = re.compile(r"^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?:$|T)")

_SINGLE_CODE_LETTER: Final = re.compile(r"^[A-Z]$")

CHECKBOX_MARK: Final = "X"

"""The record designs' affirmative mark on a flag; a name meaning clave still brings the same letter in."""

YES_NO_LETTERS: Final = frozenset({"S", "N"})

ARITHMETIC_OPERANDS: Final = frozenset({-1, 0, 1, 2, 10, 100})

"""Sign, halving, doubling, decimal shift and per cent scale: what a calculation does, not a fact it holds."""

_TAX_WORDS: Final = frozenset(
    {
        "AMORTIZATION",
        "AMOUNT",
        "BRACKETS",
        "CUOTA",
        "CUANTIA",
        "DEDUCTION",
        "EDAD",
        "IMPORTE",
        "INCOME",
        "LIMITE",
        "PERCENT",
        "PLAZO",
        "PORCENTAJE",
        "RATE",
        "RATES",
        "REDUCCION",
        "RENT",
        "RENTA",
        "RETENCION",
        "RETENTION",
        "THRESHOLD",
        "TIPO",
        "TOPE",
        "TRAMO",
        "TRAMOS",
        "TURNOVER",
    }
)

"""A word spoken of a tax value. It outranks every unit, mechanic and calendar word in the same name and every owner
that only lays values out: ``DEDUCTION_VERSION`` holds a deduction, whatever else the name says."""

_LIMIT_WORDS: Final = frozenset(
    {"BASE", "CAP", "CEILING", "FLOOR", "LIMIT", "MAX", "MAXIMUM", "MIN", "MINIMUM", "SLOTS"}
)

"""A word spoken of limits in general. A clear unit or mechanic can say what it limits; a capacity or a calendar
number alone cannot, and neither can a unit that also reads as something else."""

FACT_WORDS: Final = _TAX_WORDS | _LIMIT_WORDS

"""A number held under one of these words is what it says, however small."""

_AMBIGUOUS_UNIT_WORDS: Final = frozenset({"S", "POINTS", "VERSION"})

"""Units too short or too general to speak for a limit word: ``LIMIT_S`` says nothing about seconds."""

_NON_TAX_PHRASE: Final = re.compile(
    r"(?:^|_)(?:fx_rate|exchange_rate|rate_limit|(?:diagnostic|run|runs|record|records|cache|usage|settled|log|logs)_retention)",
    re.IGNORECASE,
)

"""Phrases that hold a tax word in another sense: an exchange rate read as data, a request rate, a log kept so long."""

SHEET_GEOMETRY_OWNERS: Final = ("application/storage/calc_sheets/", "application/modelo/reconciliation_export.py")

SHEET_GEOMETRY_WORDS: Final = frozenset(
    {
        "CELL",
        "CELLS",
        "COL",
        "COLUMN",
        "COLUMNS",
        "HEIGHT",
        "HEIGHTS",
        "PIXELS",
        "ROW",
        "ROWS",
        "SIZE",
        "WIDTH",
        "WIDTHS",
    }
)

"""A workbook module holds numbers of its own, but only under one of these names: a constant, a target, a keyword or
a function that says it measures the sheet. Anything else in such a module is read as in any other."""

SHEET_MEASURES: Final = frozenset(
    {
        "arithmetic",
        "call_value",
        "clamp",
        "default_value",
        "inner_value",
        "keyword_value",
        "module_value",
        "number_set",
        "position",
        "result_value",
        "threshold",
    }
)

FORM_SHAPE_WORDS: Final = frozenset({"BOX", "BOXES", "CASILLA", "CASILLAS", "FORM", "RECORD", "RECORDS", "ROW", "ROWS"})

"""A name counting a form's own parts: cutting a sequence short at this number is the form's limit, not a view."""

IDENTITY_NUMBERS: Final = frozenset({-1, 0, 1})

VALUE_KEYWORDS: Final = frozenset({"base", "count", "default", "offset", "position", "start", "step", "limit_rows"})

"""These keywords take a position or a count, and a fiscal value just as well: they speak only for a small number."""

SMALL_COUNT: Final = 13

"""Below this a bare integer is more often a position, a count or a width than a fact: the stated limit of the sweep."""

KEYWORD_MECHANICS: Final = frozenset(
    {
        "base",
        "column",
        "columns",
        "count",
        "default",
        "depth",
        "exclude_none",
        "height",
        "indent",
        "level",
        "limit_rows",
        "maxsplit",
        "ndigits",
        "offset",
        "padding",
        "position",
        "prec",
        "precision",
        "start",
        "stacklevel",
        "step",
        "width",
        "minimum_casilla_ids",
        "maximum_casilla_ids",
    }
)

YEAR_ARITHMETIC_CALLS: Final = frozenset({"range"})

DECIMAL_MODULE_NAMES: Final = frozenset({"Decimal"})

TEXT_NUMBER: Final = re.compile(r"^-?\d+(?:[.,]\d+)?$")

NUMBER_CALLS: Final = frozenset({"float", "int"})

DATE_TEXTS: Final = (
    re.compile(r"^(?:0[1-9]|[12]\d|3[01])[/-](?:0[1-9]|1[0-2])[/-](?:19|20)\d{2}$"),
    re.compile(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$"),
    re.compile(r"^(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$"),
)

SPELLED_BOX: Final = re.compile(r"(?i)^(?:[a-z_]*_)?casilla[_ -]?\d{2,4}$")

SPELLED_FORM: Final = re.compile(r"^(?:M|MODELO[_ -]?)(\d{3})$")

CODE_LIST: Final = re.compile(r"^\d{2,4}[A-Z]?(?:[,;\s]+\d{2,4}[A-Z]?)+$")

CODE_LETTERS: Final = re.compile(r"^[A-Z]{2,}$")

MODELO_TAIL: Final = re.compile(r"(?:^|_)(?:modelos?(?:_ids?|_codes?)?|models?)$", re.IGNORECASE)

PERIOD_TAIL: Final = re.compile(r"(?:^|_)(?:periods?(?:_codes?|_tokens?)?|quarters?|registry_token)$", re.IGNORECASE)

EDITION_TAIL: Final = re.compile(r"(?:^|_)(?:revision_id|design_epoch)$", re.IGNORECASE)

POSITIONAL_MECHANICS: Final = frozenset(
    {"ElidedProse", "_percentile", "chr", "divmod", "getattr", "int", "open", "sleep", "wait_for_timeout"}
)

"""These take a delay, a code point, a numeric base, a mode, a sentinel or a text bound as a bare argument."""

RECORD_DESIGN_READERS: Final = ("application/filing/export_xml_dictionary",)

"""These parse the printed dictionary of a published design; its grammar is what they read, not a width they restate."""

MODELO_ID_DECLARATION: Final = re.compile(r"ModeloCode")

EPOCHS: Final = frozenset({(1899, 12, 30), (1970, 1, 1)})

UNIT_CONVERSIONS: Final = frozenset({60, 1000, 3600, 86400})

"""Scaling by a time or metric unit converts a quantity; adding one of these is still a finding."""

CLOCK_CALLS: Final = frozenset({"monotonic", "perf_counter", "time"})

STANDARD_SHAPE_FUNCTION: Final = re.compile(
    r"(?:^|_|\.)(?:yyyymmdd|ddmmyyyy|territory_definition|jurisdictions|modelo_code|selector_address)(?:_|\.|s?$)",
    re.IGNORECASE,
)

STANDARD_SHAPE_WIDTHS: Final = {
    "yyyymmdd": 8,
    "ddmmyyyy": 8,
    "territory_definition": 5,
    "jurisdictions": 2,
    "modelo_code": 3,
    "selector_address": 16,
}

"""A standard shape states one width: a function so named is excused for that width and no other."""

PATTERN_CALLS: Final = frozenset({"Field", "StringConstraints", "constr"})

REGEX_CALLS: Final = frozenset(
    {"compile", "match", "fullmatch", "search", "sub", "subn", "findall", "finditer", "split"}
)

WIDTH_QUANTIFIER: Final = re.compile(r"(\[[^\]]*\]|\\[A-Za-z]|\.|\))\{(\d+)(?:,(\d*))?\}")

HEX_CLASSES: Final = frozenset({"[0-9a-f]", "[a-f0-9]", "[0-9A-Fa-f]", "[A-Fa-f0-9]", "[0-9a-fA-F]", "[a-fA-F0-9]"})

CALENDAR_RANGES: Final = frozenset({(1, 12), (1, 31), (1, 53), (1, 366), (365, 366), (1, 7), (1900, 9999)})

CALENDAR_VALUES: Final = frozenset({7, 12, 24, 28, 29, 30, 31, 52, 53, 60, 365, 366, 1900, 9999})

_DAY_WORDS: Final = frozenset({"DAY", "DAYS", "DIA", "DIAS"})

CALENDAR_UNITS: Final = {
    7: frozenset({"WEEK", "WEEKS", "DAY", "DAYS"}),
    12: frozenset({"MONTH", "MONTHS", "MESES"}),
    24: frozenset({"HOUR", "HOURS", "DAY"}),
    28: _DAY_WORDS,
    29: _DAY_WORDS,
    30: _DAY_WORDS,
    31: _DAY_WORDS,
    52: frozenset({"WEEK", "WEEKS"}),
    53: frozenset({"WEEK", "WEEKS"}),
    60: frozenset({"SECOND", "SECONDS", "MINUTE", "MINUTES", "HOUR"}),
    365: _DAY_WORDS,
    366: _DAY_WORDS,
}

ARITHMETIC_COMPARE: Final = frozenset({-1, 0, 1, 2, 100})

ARITHMETIC_PERCENT: Final = 100

CENTURY: Final = 100

FIRST_YEAR: Final = 19 * CENTURY

LAST_YEAR: Final = 21 * CENTURY

YEAR_ENDPOINTS: Final = frozenset({(1, 1), (12, 31)})

LEAP_DAY_SHIFT: Final = (2, 28)

"""Where a year's shift lands the day after a 29 February: the calendar, not a due date."""

MONTH_TUPLE_LENGTH: Final = 3

MONTHS_OF_A_YEAR: Final = 12

DAYS_OF_A_YEAR: Final = frozenset({365, 366})

COLLECTION_CALLS: Final = frozenset({"frozenset", "list", "set", "tuple"})

"""Wrapping members in one of these keeps them under the name that holds the collection."""

ADDRESS_KEYWORDS: Final = frozenset({"modelo", "period", "modelo_id", "source_modelo", "registry_token"})

PERIOD_ENUM: Final = "StandardPeriodCode"

COMMAND_ROOTS: Final = frozenset({"app", "config"})


def modelo_ids() -> frozenset[str]:
    return frozenset(path.name for path in (SRC / "_data" / "registry" / "aeat" / "modelos").iterdir() if path.is_dir())


def period_codes() -> frozenset[str]:
    sys.path.insert(0, str(_ROOT / "src"))
    from cadrumo.core.period import StandardPeriodCode

    return frozenset(code.value for code in StandardPeriodCode)


def called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else ""


def expression_names(node: ast.AST) -> str:
    return " ".join(
        item.id if isinstance(item, ast.Name) else item.attr
        for item in ast.walk(node)
        if isinstance(item, (ast.Name, ast.Attribute))
    )


def docstrings(tree: ast.AST) -> set[ast.AST]:
    found: set[ast.AST] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for statement in body:
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                    found.add(statement.value)
    return found


def machine_capacity(value: float) -> bool:
    """A power of two sizes a buffer or payload; no tax limit is written that way."""
    return isinstance(value, int) and value >= _SMALLEST_CAPACITY and value & (value - 1) == 0


def wire_capacity(value: float) -> bool:
    """A round thousand is a capacity only where its use proves it: the longest a wire value may be."""
    return machine_capacity(value) or (
        isinstance(value, int) and value >= THOUSAND and str(value).strip("0") in {"1", "2", "4", "5"}
    )


def _collection_capacity(value: float) -> bool:
    """A collection's capacity is a power of two or a round ten thousand: no form holds that many rows of its own."""
    return machine_capacity(value) or (wire_capacity(value) and value >= _COLLECTION_WIRE_FLOOR)


def single_code_letter(value: object) -> bool:
    return isinstance(value, str) and _SINGLE_CODE_LETTER.fullmatch(value) is not None


def name_words(name: str) -> frozenset[str]:
    """Return the whole words of a name, so that ``ARITY`` is not read inside ``SOLIDARITY``."""
    return frozenset(str(word).upper() for word in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", name) if word)


def tax_name(name: str) -> bool:
    return bool(name_words(_NON_TAX_PHRASE.sub("_", name)) & _TAX_WORDS)


def bare_limit(name: str) -> bool:
    """A name that is only a limit word says nothing of what it limits."""
    return _limit_name(name) and name_words(name) <= _LIMIT_WORDS


def _limit_name(name: str) -> bool:
    return bool(name_words(name) & _LIMIT_WORDS)


def machine_unit_name(name: str) -> bool:
    """A unit speaks for a name unless the name also says tax, or a limit under a unit that can mean anything."""
    if not _MACHINE_UNIT_NAME.search(name) or tax_name(name):
        return False
    return not (_limit_name(name) and name_words(name) & _AMBIGUOUS_UNIT_WORDS)


def mechanic_name(name: str) -> bool:
    """A mechanic word or a lexical phrase speaks for a name unless the name also says tax."""
    if tax_name(name):
        return False
    words = re.split(r"[^A-Za-z0-9]+", name.strip("_"))
    return bool(name_words(name) & _PRODUCT_MECHANIC_WORDS) or (
        bool(_LEXICAL_NAME.search(name)) and words[-1].upper() not in _LIMIT_WORDS
    )


def terminal_name(node: ast.AST) -> str:
    """Return the name a side of a comparison ends in: ``casilla`` of ``period.casilla``."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return called_name(node) if isinstance(node, ast.Call) else ""


def lawful_range(low: float | None, high: float | None, name: str = "") -> bool:
    """Return whether a ``Field``'s numeric bounds state arithmetic, a calendar range or a capacity.

    A name spoken of a fact keeps only arithmetic bounds: ``rate`` from one to twelve is not a month.
    """
    if tax_name(name) or "clave" in name.lower():
        return all(bound is None or bound in ARITHMETIC_BOUNDS for bound in (low, high))
    if (low, high) in CALENDAR_RANGES:
        return True
    return all(bound is None or bound in ARITHMETIC_BOUNDS or machine_capacity(bound) for bound in (low, high))


def lawful_length(low: float | None, high: float | None, pattern: str | None) -> bool:
    """Return whether ``Field`` lengths state a digest, a payload guard or nothing at all."""
    if (
        pattern is not None
        and all(group[0] in HEX_CLASSES for group in WIDTH_QUANTIFIER.findall(pattern))
        and (WIDTH_QUANTIFIER.search(pattern))
    ):
        return True
    if low == high and low == SHA256_HEX:
        return True
    if low is not None and low not in ARITHMETIC_BOUNDS:
        return False
    return high is None or high in ARITHMETIC_BOUNDS or _collection_capacity(high)


def lawful_decimal(text: str) -> bool:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return True
    if not value.is_finite():
        return True
    return value in {Decimal(0), Decimal(1), Decimal(100), Decimal(-1)} or _cent_or_finer(value)


def cent_or_finer_text(text: str) -> bool:
    try:
        return _cent_or_finer(Decimal(text))
    except InvalidOperation:
        return False


def _cent_or_finer(value: Decimal) -> bool:
    """A cent or finer power of ten states a precision; a tenth can just as well be a ten per cent rate."""
    return 0 < value <= _CENT and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


def rounding_quantum(value: Decimal) -> bool:
    return 0 < value < 1 and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


def constant_number(node: ast.AST | None) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = constant_number(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    return None


def is_hundred(node: ast.AST) -> bool:
    """Return whether ``node`` spells the per cent scale, as a number or a ``Decimal``."""
    if constant_number(node) == ARITHMETIC_PERCENT:
        return True
    return (
        isinstance(node, ast.Call)
        and called_name(node) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and str(node.args[0].value) == str(ARITHMETIC_PERCENT)
    )


@cache
def _module_tree(module: str) -> ast.Module | None:
    """Inspect canonical project scalar definitions without importing application code."""
    if not module.startswith(("cadrumo.", "cadrumo_client.")):
        return None
    path = _ROOT / "src" / Path(*module.split(".")).with_suffix(".py")
    return ast.parse(path.read_text(encoding="utf-8")) if path.is_file() else None


@cache
def imports_for(tree: ast.AST, module: str) -> dict[str, tuple[str, str]]:
    imports = {}
    package = module.split(".")[:-1]
    for node in scope_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*prefix, *(node.module or "").split(".")]).strip(".")
            imports.update({alias.asname or alias.name: (target, alias.name) for alias in node.names})
    return imports


def annotation_kind(
    node: ast.AST | None, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]] = frozenset()
) -> str:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        kinds = {annotation_kind(part, tree, module, seen) for part in (node.left, node.right)} - {"unknown"}
        return kinds.pop() if len(kinds) == 1 else "unknown"
    if isinstance(node, ast.Subscript):
        kind = _subscript_annotation_kind(node, tree, module, seen)
        if kind is not None:
            return kind
    if not isinstance(node, ast.Name):
        return "unknown"
    if node.id in {"str", "bytes", "StrEnum"}:
        return "text"
    key = (module, node.id)
    if key in seen:
        return "unknown"
    seen = seen | {key}
    imported = imports_for(tree, module).get(node.id)
    if imported is not None:
        target, symbol = imported
        if (target, symbol) == ("cadrumo.domain.calculations.registry.schema_formula", "FormulaExpression"):
            return "expression"
        if (target, symbol) == ("urllib.parse", "SplitResult"):
            return "url"
        imported_tree = _module_tree(target)
        if imported_tree is not None:
            return annotation_kind(ast.Name(id=symbol, ctx=ast.Load()), imported_tree, target, seen)
    return _declared_annotation_kind(node, tree, module, seen)


def _subscript_annotation_kind(
    node: ast.Subscript, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]]
) -> str | None:
    name = reader_name(node.value)
    first = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
    if name in {"Annotated", "Optional"}:
        return annotation_kind(first, tree, module, seen)
    if (
        name in {"dict", "Mapping"}
        and isinstance(node.slice, ast.Tuple)
        and all(annotation_kind(part, tree, module, seen) == "text" for part in node.slice.elts)
    ):
        return "text_mapping"
    if name in {"tuple", "list", "set", "frozenset", "dict", "Mapping", "Sequence"}:
        return "collection"
    return None


def _declared_annotation_kind(node: ast.Name, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]]) -> str:
    for declaration in getattr(tree, "body", []):
        if isinstance(declaration, ast.ClassDef) and declaration.name == node.id:
            if any(annotation_kind(base, tree, module, seen) == "text" for base in declaration.bases):
                return "text"
        elif isinstance(declaration, ast.TypeAlias):
            if declaration.name.id == node.id:
                return annotation_kind(declaration.value, tree, module, seen)
        elif isinstance(declaration, (ast.Assign, ast.AnnAssign)):
            targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
            if any(isinstance(target, ast.Name) and target.id == node.id for target in targets):
                return annotation_kind(declaration.value, tree, module, seen)
    return "unknown"


def folded_number(node: ast.AST) -> float | None:
    """Return the number a literal or an arithmetic of literals states."""
    number = constant_number(node)
    if number is not None or not isinstance(node, ast.BinOp):
        return number
    left, right = folded_number(node.left), folded_number(node.right)
    if left is None or right is None:
        return None
    if isinstance(node.op, ast.Mult):
        return left * right
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Pow) and isinstance(left, int) and isinstance(right, int) and right >= 0:
        return int(left**right)
    if isinstance(node.op, ast.LShift) and isinstance(left, int) and isinstance(right, int):
        return left << right
    return None


def scope_nodes(scope: ast.AST) -> list[ast.AST]:
    nodes = [scope]
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        nodes.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return nodes


def dom_cell_call(node: ast.Call) -> bool:
    if called_name(node) != "find_all":
        return False
    if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in {"td", "th"}:
        return True
    return any(
        keyword.arg == "class_"
        and isinstance(keyword.value, ast.Call)
        and keyword.value.args
        and isinstance(keyword.value.args[0], ast.Constant)
        and keyword.value.args[0].value == "z-listcell"
        for keyword in node.keywords
    )


def fixed_pattern_members(pattern: str) -> tuple[str, ...]:
    """Recognize complete literal alternatives, leaving digit widths as lexical grammar."""
    text = pattern.removeprefix("^").removesuffix("$").removesuffix(r"\Z")
    if text.startswith("(?:") and text.endswith(")"):
        text = text[3:-1]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    members = tuple(text.split("|"))
    return members if all(re.fullmatch(r"[0-9A-Z]+", member) for member in members) else ()


def reader_name(node: ast.AST) -> str:
    return str(getattr(node, "id", getattr(node, "attr", "")))

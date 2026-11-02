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

_ROOT: Final = Path(__file__).resolve().parents[3]

_SRC: Final = _ROOT / "src" / "cadrumo"

_SCANNED: Final = (
    _SRC / "domain",
    _SRC / "application",
    _SRC / "core",
    _SRC / "adapters",
    _SRC / "entrypoints",
    _ROOT / "src" / "cadrumo_client",
)

_MACHINE_OWNERS: Final = ("cadrumo_client/", "adapters/persistence/storage/", "core/redaction/")

"""These read operating system answers, framing and byte sizes; no tax value reaches them."""

_MECHANICS_OWNERS: Final = (
    "adapters/inbound/declaracion/bbox_extraction.py",
    "adapters/inbound/pdf/",
    "adapters/outbound/aeat/browser/",
    "adapters/outbound/calculation_summary_pdf/",
    "adapters/outbound/google/_calc_sheets_apply_formatting.py",
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
    "domain/calculations/registry/_formula_operator_contracts.py",
    "entrypoints/tui/",
)

"""Terminal cells, page and sheet coordinates, search ranking, wire codecs, an identifier's lexical shape, Unicode
folding, platform codes, an operator's argument count and the calendar range of a period: these lay out, rank or
transport a value and hold none of their own."""

_RECORD_DESIGN_OWNERS: Final = (
    "domain/calculations/registry/export_",
    "domain/calculations/registry/fixed_width_",
    "domain/calculations/registry/schema_exports.py",
)

_RECORD_DESIGN_LETTERS: Final = frozenset({"A", "N"})

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

_FILE_PERMISSION_NAME: Final = re.compile(r"(?:^|_)MODE$", re.IGNORECASE)

_FILE_PERMISSIONS: Final = frozenset({0o600, 0o640, 0o644, 0o700, 0o750, 0o755})

_YEAR_NAME: Final = re.compile(r"year|ejercicio", re.IGNORECASE)

_CENTURY: Final = 100

_FORM_HANDING_MODULE: Final = re.compile(r"^producer_snapshot|_bindings|(?:^|_)rows?(?:_|$)|row_models")

_FORM_HANDING_OWNERS: Final = (
    "application/filing/",
    "application/modelo/edit_apply_row_contracts.py",
    "domain/filing/",
    "domain/modelos/",
)

"""Where a value is on its way to a form's field: a width written here restates the record design."""

_TEXT_WIDTH_CALLS: Final = frozenset({"ljust", "rjust", "center", "zfill"})

_YEAR_WIDTH: Final = "4"

_NUMERIC_BOUNDS: Final = frozenset({"ge", "gt", "le", "lt"})

_ARITHMETIC_BOUNDS: Final = frozenset({0, 1})

_CODE_SHAPED: Final = re.compile(r"^\d{2,4}[A-Z]?$")

_LETTER_CLAVE: Final = re.compile(r"^[A-Z]{1,2}$")

_CLAVE_NAME: Final = re.compile(r"clave|subclave|tipo_|_code$|^code$|codigo", re.IGNORECASE)

_MODELO_ADDRESS_CALLS: Final = frozenset(
    {"Modelo", "modelo_directory", "revision", "revision_for_context", "select_revision_metadata", "snapshot"},
)

_FORM_NAMED_MODULE: Final = re.compile(r"(?:^|_)m(\d{3})(?:_|$)")

_MONTH_NAME: Final = re.compile(r"month", re.IGNORECASE)

_DAY_NAME: Final = re.compile(r"days?(?:_|$)|dias", re.IGNORECASE)

_COUNTRY_NAME: Final = re.compile(r"countr|iso", re.IGNORECASE)

_LENGTH_BOUNDS: Final = frozenset({"min_length", "max_length"})

_SHA256_HEX: Final = 64

_SMALLEST_CAPACITY: Final = 16

_THOUSAND: Final = 1000

_COLLECTION_WIRE_FLOOR: Final = 10_000

_LAST_FOUR_DIGIT_YEAR: Final = 9999

_CENT: Final = Decimal("0.01")

_DATE_CALLS: Final = frozenset({"date", "datetime"})

_ISO_DATE: Final = re.compile(r"^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?:$|T)")

_SINGLE_CODE_LETTER: Final = re.compile(r"^[A-Z]$")

_CHECKBOX_MARK: Final = "X"

"""The record designs' affirmative mark on a flag; a name meaning clave still brings the same letter in."""

_YES_NO_LETTERS: Final = frozenset({"S", "N"})

_ARITHMETIC_OPERANDS: Final = frozenset({-1, 0, 1, 2, 10, 100})

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

_FACT_WORDS: Final = _TAX_WORDS | _LIMIT_WORDS

"""A number held under one of these words is what it says, however small."""

_AMBIGUOUS_UNIT_WORDS: Final = frozenset({"S", "POINTS", "VERSION"})

"""Units too short or too general to speak for a limit word: ``LIMIT_S`` says nothing about seconds."""

_NON_TAX_PHRASE: Final = re.compile(
    r"(?:^|_)(?:fx_rate|exchange_rate|rate_limit|(?:diagnostic|run|runs|record|records|cache|usage|settled|log|logs)_retention)",
    re.IGNORECASE,
)

"""Phrases that hold a tax word in another sense: an exchange rate read as data, a request rate, a log kept so long."""

_SHEET_GEOMETRY_OWNERS: Final = ("application/storage/calc_sheets/", "application/modelo/reconciliation_export.py")

_SHEET_GEOMETRY_WORDS: Final = frozenset(
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

_SHEET_MEASURES: Final = frozenset(
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

_FORM_SHAPE_WORDS: Final = frozenset(
    {"BOX", "BOXES", "CASILLA", "CASILLAS", "FORM", "RECORD", "RECORDS", "ROW", "ROWS"}
)

"""A name counting a form's own parts: cutting a sequence short at this number is the form's limit, not a view."""

_IDENTITY_NUMBERS: Final = frozenset({-1, 0, 1})

_VALUE_KEYWORDS: Final = frozenset({"base", "count", "default", "offset", "position", "start", "step", "limit_rows"})

"""These keywords take a position or a count, and a fiscal value just as well: they speak only for a small number."""

_SMALL_COUNT: Final = 13

"""Below this a bare integer is more often a position, a count or a width than a fact: the stated limit of the sweep."""

_KEYWORD_MECHANICS: Final = frozenset(
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

_YEAR_ARITHMETIC_CALLS: Final = frozenset({"range"})

_DECIMAL_MODULE_NAMES: Final = frozenset({"Decimal"})

_TEXT_NUMBER: Final = re.compile(r"^-?\d+(?:[.,]\d+)?$")

_NUMBER_CALLS: Final = frozenset({"float", "int"})

_DATE_TEXTS: Final = (
    re.compile(r"^(?:0[1-9]|[12]\d|3[01])[/-](?:0[1-9]|1[0-2])[/-](?:19|20)\d{2}$"),
    re.compile(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$"),
    re.compile(r"^(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$"),
)

_SPELLED_BOX: Final = re.compile(r"(?i)^(?:[a-z_]*_)?casilla[_ -]?\d{2,4}$")

_SPELLED_FORM: Final = re.compile(r"^(?:M|MODELO[_ -]?)(\d{3})$")

_CODE_LIST: Final = re.compile(r"^\d{2,4}[A-Z]?(?:[,;\s]+\d{2,4}[A-Z]?)+$")

_CODE_LETTERS: Final = re.compile(r"^[A-Z]{2,}$")

_MODELO_TAIL: Final = re.compile(r"(?:^|_)(?:modelos?(?:_ids?|_codes?)?|models?)$", re.IGNORECASE)

_PERIOD_TAIL: Final = re.compile(r"(?:^|_)(?:periods?(?:_codes?|_tokens?)?|quarters?|registry_token)$", re.IGNORECASE)

_EDITION_TAIL: Final = re.compile(r"(?:^|_)(?:revision_id|design_epoch)$", re.IGNORECASE)

_POSITIONAL_MECHANICS: Final = frozenset(
    {"ElidedProse", "_percentile", "chr", "divmod", "getattr", "int", "open", "sleep", "wait_for_timeout"}
)

"""These take a delay, a code point, a numeric base, a mode, a sentinel or a text bound as a bare argument."""

_RECORD_DESIGN_READERS: Final = ("application/filing/_export_xml_dictionary",)

"""These parse the printed dictionary of a published design; its grammar is what they read, not a width they restate."""

_MODELO_ID_DECLARATION: Final = re.compile(r"ModeloCode")

_EPOCHS: Final = frozenset({(1899, 12, 30), (1970, 1, 1)})

_UNIT_CONVERSIONS: Final = frozenset({60, 1000, 3600, 86400})

"""Scaling by a time or metric unit converts a quantity; adding one of these is still a finding."""

_CLOCK_CALLS: Final = frozenset({"monotonic", "perf_counter", "time"})

_STANDARD_SHAPE_FUNCTION: Final = re.compile(
    r"(?:^|_|\.)(?:yyyymmdd|ddmmyyyy|territory_definition|jurisdictions|modelo_code|selector_address)(?:_|\.|s?$)",
    re.IGNORECASE,
)

_STANDARD_SHAPE_WIDTHS: Final = {
    "yyyymmdd": 8,
    "ddmmyyyy": 8,
    "territory_definition": 5,
    "jurisdictions": 2,
    "modelo_code": 3,
    "selector_address": 16,
}

"""A standard shape states one width: a function so named is excused for that width and no other."""

_PATTERN_CALLS: Final = frozenset({"Field", "StringConstraints", "constr"})

_REGEX_CALLS: Final = frozenset(
    {"compile", "match", "fullmatch", "search", "sub", "subn", "findall", "finditer", "split"}
)

_WIDTH_QUANTIFIER: Final = re.compile(r"(\[[^\]]*\]|\\[A-Za-z]|\.|\))\{(\d+)(?:,(\d*))?\}")

_HEX_CLASSES: Final = frozenset({"[0-9a-f]", "[a-f0-9]", "[0-9A-Fa-f]", "[A-Fa-f0-9]", "[0-9a-fA-F]", "[a-fA-F0-9]"})

_CALENDAR_RANGES: Final = frozenset({(1, 12), (1, 31), (1, 53), (1, 366), (365, 366), (1, 7), (1900, 9999)})

_CALENDAR_VALUES: Final = frozenset({7, 12, 24, 28, 29, 30, 31, 52, 53, 60, 365, 366, 1900, 9999})

_DAY_WORDS: Final = frozenset({"DAY", "DAYS", "DIA", "DIAS"})

_CALENDAR_UNITS: Final = {
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

_ARITHMETIC_COMPARE: Final = frozenset({-1, 0, 1, 2, 100})

_ARITHMETIC_PERCENT: Final = 100

_FIRST_YEAR: Final = 1900

_LAST_YEAR: Final = 2100

_YEAR_ENDPOINTS: Final = frozenset({(1, 1), (12, 31)})

_LEAP_DAY_SHIFT: Final = (2, 28)

"""Where a year's shift lands the day after a 29 February: the calendar, not a due date."""

_MONTH_TUPLE_LENGTH: Final = 3

_MONTHS_OF_A_YEAR: Final = 12

_DAYS_OF_A_YEAR: Final = frozenset({365, 366})

_COLLECTION_CALLS: Final = frozenset({"frozenset", "list", "set", "tuple"})

"""Wrapping members in one of these keeps them under the name that holds the collection."""

_ADDRESS_KEYWORDS: Final = frozenset({"modelo", "period", "modelo_id", "source_modelo", "registry_token"})

_PERIOD_ENUM: Final = "StandardPeriodCode"

_COMMAND_ROOTS: Final = frozenset({"app", "config"})


def _modelo_ids() -> frozenset[str]:
    return frozenset(
        path.name for path in (_SRC / "_data" / "registry" / "aeat" / "modelos").iterdir() if path.is_dir()
    )


def _period_codes() -> frozenset[str]:
    sys.path.insert(0, str(_ROOT / "src"))
    from cadrumo.core.period import StandardPeriodCode

    return frozenset(code.value for code in StandardPeriodCode)


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else ""


def _expression_names(node: ast.AST) -> str:
    return " ".join(
        item.id if isinstance(item, ast.Name) else item.attr
        for item in ast.walk(node)
        if isinstance(item, (ast.Name, ast.Attribute))
    )


def _docstrings(tree: ast.AST) -> set[ast.AST]:
    found: set[ast.AST] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for statement in body:
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                    found.add(statement.value)
    return found


def _machine_capacity(value: float) -> bool:
    """A power of two sizes a buffer or payload; no tax limit is written that way."""
    return isinstance(value, int) and value >= _SMALLEST_CAPACITY and value & (value - 1) == 0


def _wire_capacity(value: float) -> bool:
    """A round thousand is a capacity only where its use proves it: the longest a wire value may be."""
    return _machine_capacity(value) or (
        isinstance(value, int) and value >= _THOUSAND and str(value).strip("0") in {"1", "2", "4", "5"}
    )


def _collection_capacity(value: float) -> bool:
    """A collection's capacity is a power of two or a round ten thousand: no form holds that many rows of its own."""
    return _machine_capacity(value) or (_wire_capacity(value) and value >= _COLLECTION_WIRE_FLOOR)


def _single_code_letter(value: object) -> bool:
    return isinstance(value, str) and _SINGLE_CODE_LETTER.fullmatch(value) is not None


def _name_words(name: str) -> frozenset[str]:
    """Return the whole words of a name, so that ``ARITY`` is not read inside ``SOLIDARITY``."""
    return frozenset(str(word).upper() for word in re.split(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])", name) if word)


def _tax_name(name: str) -> bool:
    return bool(_name_words(_NON_TAX_PHRASE.sub("_", name)) & _TAX_WORDS)


def _bare_limit(name: str) -> bool:
    """A name that is only a limit word says nothing of what it limits."""
    return _limit_name(name) and _name_words(name) <= _LIMIT_WORDS


def _limit_name(name: str) -> bool:
    return bool(_name_words(name) & _LIMIT_WORDS)


def _machine_unit_name(name: str) -> bool:
    """A unit speaks for a name unless the name also says tax, or a limit under a unit that can mean anything."""
    if not _MACHINE_UNIT_NAME.search(name) or _tax_name(name):
        return False
    return not (_limit_name(name) and _name_words(name) & _AMBIGUOUS_UNIT_WORDS)


def _mechanic_name(name: str) -> bool:
    """A mechanic word or a lexical phrase speaks for a name unless the name also says tax."""
    if _tax_name(name):
        return False
    words = re.split(r"[^A-Za-z0-9]+", name.strip("_"))
    return bool(_name_words(name) & _PRODUCT_MECHANIC_WORDS) or (
        bool(_LEXICAL_NAME.search(name)) and words[-1].upper() not in _LIMIT_WORDS
    )


def _terminal_name(node: ast.AST) -> str:
    """Return the name a side of a comparison ends in: ``casilla`` of ``period.casilla``."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return _called_name(node) if isinstance(node, ast.Call) else ""


def _lawful_range(low: float | None, high: float | None, name: str = "") -> bool:
    """Return whether a ``Field``'s numeric bounds state arithmetic, a calendar range or a capacity.

    A name spoken of a fact keeps only arithmetic bounds: ``rate`` from one to twelve is not a month.
    """
    if _tax_name(name) or "clave" in name.lower():
        return all(bound is None or bound in _ARITHMETIC_BOUNDS for bound in (low, high))
    if (low, high) in _CALENDAR_RANGES:
        return True
    return all(bound is None or bound in _ARITHMETIC_BOUNDS or _machine_capacity(bound) for bound in (low, high))


def _lawful_length(low: float | None, high: float | None, pattern: str | None) -> bool:
    """Return whether ``Field`` lengths state a digest, a payload guard or nothing at all."""
    if (
        pattern is not None
        and all(group[0] in _HEX_CLASSES for group in _WIDTH_QUANTIFIER.findall(pattern))
        and (_WIDTH_QUANTIFIER.search(pattern))
    ):
        return True
    if low == high and low == _SHA256_HEX:
        return True
    if low is not None and low not in _ARITHMETIC_BOUNDS:
        return False
    return high is None or high in _ARITHMETIC_BOUNDS or _collection_capacity(high)


def _lawful_decimal(text: str) -> bool:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return True
    if not value.is_finite():
        return True
    return value in {Decimal(0), Decimal(1), Decimal(100), Decimal(-1)} or _cent_or_finer(value)


def _cent_or_finer_text(text: str) -> bool:
    try:
        return _cent_or_finer(Decimal(text))
    except InvalidOperation:
        return False


def _cent_or_finer(value: Decimal) -> bool:
    """A cent or finer power of ten states a precision; a tenth can just as well be a ten per cent rate."""
    return 0 < value <= _CENT and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


def _rounding_quantum(value: Decimal) -> bool:
    return 0 < value < 1 and value.as_tuple().digits[0] == 1 and sum(value.as_tuple().digits) == 1


def _constant_number(node: ast.AST | None) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _constant_number(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    return None


def _is_hundred(node: ast.AST) -> bool:
    """Return whether ``node`` spells the per cent scale, as a number or a ``Decimal``."""
    if _constant_number(node) == _ARITHMETIC_PERCENT:
        return True
    return (
        isinstance(node, ast.Call)
        and _called_name(node) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and str(node.args[0].value) == str(_ARITHMETIC_PERCENT)
    )


@cache
def _module_tree(module: str) -> ast.Module | None:
    """Inspect canonical project scalar definitions without importing application code."""
    if not module.startswith(("cadrumo.", "cadrumo_client.")):
        return None
    path = _ROOT / "src" / Path(*module.split(".")).with_suffix(".py")
    return ast.parse(path.read_text(encoding="utf-8")) if path.is_file() else None


@cache
def _imports_for(tree: ast.AST, module: str) -> dict[str, tuple[str, str]]:
    imports = {}
    package = module.split(".")[:-1]
    for node in _scope_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            prefix = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*prefix, *(node.module or "").split(".")]).strip(".")
            imports.update({alias.asname or alias.name: (target, alias.name) for alias in node.names})
    return imports


def _annotation_kind(
    node: ast.AST | None, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]] = frozenset()
) -> str:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        kinds = {_annotation_kind(part, tree, module, seen) for part in (node.left, node.right)} - {"unknown"}
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
    imported = _imports_for(tree, module).get(node.id)
    if imported is not None:
        target, symbol = imported
        if (target, symbol) == ("cadrumo.domain.calculations.registry.schema_formula", "FormulaExpression"):
            return "expression"
        if (target, symbol) == ("urllib.parse", "SplitResult"):
            return "url"
        imported_tree = _module_tree(target)
        if imported_tree is not None:
            return _annotation_kind(ast.Name(id=symbol, ctx=ast.Load()), imported_tree, target, seen)
    return _declared_annotation_kind(node, tree, module, seen)


def _subscript_annotation_kind(
    node: ast.Subscript, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]]
) -> str | None:
    name = _reader_name(node.value)
    first = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
    if name in {"Annotated", "Optional"}:
        return _annotation_kind(first, tree, module, seen)
    if (
        name in {"dict", "Mapping"}
        and isinstance(node.slice, ast.Tuple)
        and all(_annotation_kind(part, tree, module, seen) == "text" for part in node.slice.elts)
    ):
        return "text_mapping"
    if name in {"tuple", "list", "set", "frozenset", "dict", "Mapping", "Sequence"}:
        return "collection"
    return None


def _declared_annotation_kind(node: ast.Name, tree: ast.AST, module: str, seen: frozenset[tuple[str, str]]) -> str:
    for declaration in getattr(tree, "body", []):
        if isinstance(declaration, ast.ClassDef) and declaration.name == node.id:
            if any(_annotation_kind(base, tree, module, seen) == "text" for base in declaration.bases):
                return "text"
        elif isinstance(declaration, ast.TypeAlias):
            if declaration.name.id == node.id:
                return _annotation_kind(declaration.value, tree, module, seen)
        elif isinstance(declaration, (ast.Assign, ast.AnnAssign)):
            targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
            if any(isinstance(target, ast.Name) and target.id == node.id for target in targets):
                return _annotation_kind(declaration.value, tree, module, seen)
    return "unknown"


def _folded_number(node: ast.AST) -> float | None:
    """Return the number a literal or an arithmetic of literals states."""
    number = _constant_number(node)
    if number is not None or not isinstance(node, ast.BinOp):
        return number
    left, right = _folded_number(node.left), _folded_number(node.right)
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


def _scope_nodes(scope: ast.AST) -> list[ast.AST]:
    nodes = [scope]
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        nodes.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return nodes


def _dom_cell_call(node: ast.Call) -> bool:
    if _called_name(node) != "find_all":
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


def _fixed_pattern_members(pattern: str) -> tuple[str, ...]:
    """Recognize complete literal alternatives, leaving digit widths as lexical grammar."""
    text = pattern.removeprefix("^").removesuffix("$").removesuffix(r"\Z")
    if text.startswith("(?:") and text.endswith(")"):
        text = text[3:-1]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    members = tuple(text.split("|"))
    return members if all(re.fullmatch(r"[0-9A-Z]+", member) for member in members) else ()


def _reader_name(node: ast.AST) -> str:
    return str(getattr(node, "id", getattr(node, "attr", "")))

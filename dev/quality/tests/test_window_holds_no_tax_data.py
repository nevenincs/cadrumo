"""Gate: the desktop window holds no tax data and does no tax arithmetic.

The backend is the only tax engine. The window shows what the ledger serves and
sends what the person typed; a category list, a rate, a figure worked out from
other figures or a rule about which class takes which field belongs to the
backend, and a copy in the window goes stale the day the registry changes.

This is a tripwire for copies, not a proof. It reads every TypeScript or
JavaScript source under the frontend's ``src`` as tokens (stories, specs and
``src/dev`` excluded) and fires on the shapes a copy is usually written in.
Every list it compares against is read from an owner at run time: the
vocabularies, dated rates, modelo numbers and filing years from the pinned
registry, the figure names from the fields of the invoice request and result
contracts, the classifications from their enum. Ten rules:

``vocabulary``
    Two or more distinct tokens of one served vocabulary appear as string
    literals in one file. One token alone is a remap of a code and passes. A
    token shorter than three characters (a prorrata sector letter, a premises
    code) counts only when two of one vocabulary sit in one array literal.
``rates``
    Dated IVA rates, as points or as a fraction, gathered in one place: two or
    more distinct in a list or table literal that is mostly rates (or three in
    a list of nothing but numbers, however many other numbers it holds), in the
    arguments of one call, in the labels of one ``switch``, or as numeric
    constants of one file (two named after the registry's rate vocabulary, or
    three of any name).
``multiplication``
    A product chain with an exact (bigint) factor and two or more factors that
    are not a power of ten: ``a.units * b.units``, ``a.cents * b.cents``,
    ``b * r / 100n`` with ``r`` a bigint, ``u * 100n * 21n``. Scaling by one
    power of ten is how a decimal is aligned, not a calculation, and is the only
    multiplication allowed. A named multiplying helper (``timesToCent``) or
    method (``.times(``, ``.mul(``) also fires.
``figures``
    A decimal field of the invoice contracts set from a computation, in a
    request literal (``{ subtotal: a * b }``, a template that computes, a
    computed local) or by assignment to a member (``o.grand_total = a * b``). A
    value taken from the preview's answer or the text the person typed passes.
``classification``
    A stored classification the person decides compared (``===``, ``!==``,
    ``==``, ``!=``), switched on, looked up (``includes``, ``has``, a ``Set``, a
    record index), used as a record key, or two of them listed together.
``modelo_branch``
    A registry modelo number compared, switched on or looked up as a string.
``year_window``
    A year inside the registry's filing-year envelope used as a bound or label,
    or two of them in one literal or as constants.
``field_route``
    A ``new Set([...])`` holding three or more of the fields a movement's id is
    worked out from, or of the fields a stored invoice's correction waits on, or
    a record sending two or more readiness reasons to a field named as a string.
    A list of readiness reasons counts under ``vocabulary``; a record from a
    reason to the window's own layout passes.
``direction_rule``
    A movement direction chosen by a condition (``k ? "INCOMING" : "OUTGOING"``),
    or tested inside a ``filter``, ``find``, ``some`` or ``every``: which way
    money goes for what is the ledger's. A direction told apart to draw it passes.
``text_limit``
    A number given as the limit of ``parseLine`` or ``textField``: how long an entry may be is its
    writer's, and a field states a limit it was served.
``moved_rule``
    A name of a rule the backend now answers (``checkSplit``), or a staged split
    whose ``children`` are not read from the backend's ``answer``: whether parts
    make a split is the split writer's. Likewise the names of the matching rules
    (``EARLY_DAYS``, ``PICK_WINDOW_DAYS``, ``TOLERANCE_UNITS``, ``LEGAL_FORMS``) and a call or
    declaration of ``settlement``, ``partyName``, ``party``, ``sameParty``, ``reconcile``,
    ``linkPicker`` or ``movementPicker``: which invoice a payment settles, how
    candidates rank and which movements are offered are the ledger's. A function
    assigned to ``party`` or ``partyName`` (``const party = (text) => ...``) is a declaration, and
    so is a pattern that alternates three or more of the legal forms the backend reads as
    naming no party (read from its list at run time, under any name): which names are one
    party, and what link differences a pair has, are the ledger's. Also, in a ``filter``, ``find``, ``some``
    or ``every``, a ``counterparty_tax_id`` compared, or an ``invoice_number``
    folded through a call and compared: whether two invoices are one is the
    backend's. Finding the exact number just sent, to tell whether a write landed,
    passes.

Limits. The scan is lexical and per file. It does not follow a value across
files or through a renamed import, does not see arithmetic on plain numbers
(``Number(a) * Number(b)`` outside a figure's literal), cannot judge an
eligibility rule written as ordinary conditionals (which lifecycle or direction
takes which action), and a copy that is spelled in none of the shapes above, or
that is assembled at run time, passes. Locals are matched by name, blind to
scope. A generated file is excluded only when its path is one a generator driver
under ``scripts`` declares as its output and it opens with the exact header of
that driver's producer; two outputs of one producer are not told apart by
header. The gate fails closed only on what it can read, so a pass is
absence of the known shapes and no more.

The copies still awaiting removal are named in ``_PENDING``. An entry that no
longer hits fails the test, so the list can only shrink.
"""

from __future__ import annotations

import ast
import inspect
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.invoices.catalogue_add_contracts import InvoiceAddLine, InvoiceAddRequest
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from cadrumo.application.invoices.catalogue_update_operation import InvoiceUpdateValues
from cadrumo.application.invoices.figures_preview_contracts import (
    INVOICE_CORRECTION_JUDGED_FIELDS,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewRequest,
)
from cadrumo.application.ledger.entry_options_operation import ledger_entry_options
from cadrumo.application.ledger.readiness_routes import READINESS_REASON_FIELDS
from cadrumo.application.ledger.staged_identity import TRANSACTION_IDENTITY_FIELDS
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.enums import iva_rate_percentage, iva_rate_slots_on
from cadrumo.domain.invoices.service import BARE_LEGAL_FORMS
from cadrumo.domain.iva.errors import IvaRateNotFoundError
from cadrumo.domain.transactions.enums import CLASSIFIED_STATES, TransactionDirection
from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRONTEND: Final[Path] = REPO_ROOT / "native/desktop/frontend"
_SOURCE: Final[Path] = _FRONTEND / "src"
_GENERATORS: Final[Path] = _FRONTEND / "scripts"
_EXTENSIONS: Final = frozenset({".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"})
_EXCLUDED_NAME: Final = re.compile(r"\.(?:stories|spec)\.[^.]+$")

_MIN_TOKEN: Final = 3
_RULES: Final = (
    "vocabulary",
    "rates",
    "multiplication",
    "figures",
    "classification",
    "modelo_branch",
    "year_window",
    "field_route",
    "direction_rule",
    "text_limit",
    "moved_rule",
)
#: The names of rules the backend now answers, so a copy kept or brought back fails by name.
_MOVED_RULE_NAMES: Final = frozenset(
    {
        "checkSplit",
        "splitRemainder",
        "centsOf",
        "duplicateOf",
        "EARLY_DAYS",
        "LATE_RANK",
        "PICK_WINDOW_DAYS",
        "TOLERANCE_UNITS",
        "numberInDescription",
        "LEGAL_FORMS",
    }
)
#: Rules the backend answers that a window might name as ordinary words, so they fail only when called or declared.
_MOVED_RULE_CALLS: Final = frozenset(
    {"settlement", "partyName", "party", "sameParty", "reconcile", "linkPicker", "movementPicker"}
)
#: The names a counterparty-name fold goes by; a function assigned to one is a copy of it.
_MOVED_FOLD_NAMES: Final = frozenset({"party", "partyName"})
#: Invoice facts a duplicate rests on; the window asks and never compares them.
_DUPLICATE_FACTS: Final = frozenset({"invoice_number", "counterparty_tax_id"})
#: The request and result contracts of an invoice whose decimal fields are the figures a form could compute.
_INVOICE_CONTRACTS: Final[tuple[type[BaseModel], ...]] = (
    InvoiceAddLine,
    InvoiceAddRequest,
    InvoiceUpdateValues,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewRequest,
    CatalogueInvoiceSnapshot,
    InvoiceLineSnapshot,
)
_CLASSIFICATIONS: Final = frozenset(state.value for state in CLASSIFIED_STATES)

#: Copies awaiting removal, keyed by file (relative to ``src``) and rule.
_PENDING: Final[dict[tuple[str, str], str]] = {}


# ---------------------------------------------------------------------------
# What the registry serves
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Facts:
    """What the registry and the invoice contracts serve, which the window must not hold."""

    vocabularies: dict[str, frozenset[str]]
    rates: frozenset[Decimal]
    figure_keys: frozenset[str]
    modelos: frozenset[str]
    years: frozenset[int]
    rate_words: frozenset[str]
    identity_tokens: frozenset[str]
    judged_fields: frozenset[str]
    directions: frozenset[str]
    legal_forms: frozenset[str]


def _year_days(years: list[int]) -> Iterator[date]:
    for year in years:
        for month, day in ((1, 1), (7, 1), (12, 31)):
            yield date(year, month, day)


def _identity_tokens() -> frozenset[str]:
    """The identity fields, and the words a column of one is commonly named by (``date``, ``account``)."""
    return frozenset(TRANSACTION_IDENTITY_FIELDS) | frozenset(
        word for field in TRANSACTION_IDENTITY_FIELDS for word in _words(field) - {"own", "value", "booked"}
    )


def invoice_figure_keys() -> frozenset[str]:
    """The decimal fields of the invoice request and result contracts, read from the models themselves."""
    return frozenset(
        name
        for model in _INVOICE_CONTRACTS
        if inspect.isclass(model)
        for name, info in model.model_fields.items()
        if "PublicDecimal" in repr(info.annotation)
    )


def read_facts() -> Facts:
    """Read every vocabulary, rate, modelo and year from the pinned authority, on each supported year."""
    vocabularies: dict[str, set[str]] = {"readiness_reason": {str(reason.value) for reason in READINESS_REASON_FIELDS}}
    rates: set[Decimal] = set()
    with bundled_indexed_authority().operation() as operation:
        years = sorted(operation.supported_filing_years().years)
        modelos = frozenset(operation.modelo_ids())
        for day in _year_days(years):
            for family in ledger_entry_options(uuid4(), operation=operation, on_date=day).families:
                if family.family in {"country", "currency"}:
                    continue
                vocabularies.setdefault(family.family, set()).update(option.value for option in family.options)
            for slot in iva_rate_slots_on(day):
                vocabularies.setdefault("iva_rate_slot", set()).add(str(slot))
                try:
                    fraction = iva_rate_percentage(slot, day)
                except IvaRateNotFoundError:  # a slot not in force on this day has no rate to read
                    fraction = None
                if fraction is not None and fraction != 0:
                    rates.update({fraction.normalize(), (fraction * 100).normalize()})
    return Facts(
        {name: frozenset(tokens) for name, tokens in vocabularies.items()},
        frozenset(rates),
        invoice_figure_keys(),
        modelos,
        frozenset(years),
        frozenset(
            word
            for family in ("iva_category", "iva_rate_slot")
            for token in vocabularies.get(family, ())
            for word in _words(token.replace(".", "_"))
        ),
        _identity_tokens(),
        INVOICE_CORRECTION_JUDGED_FIELDS,
        frozenset(direction.value for direction in TransactionDirection),
        BARE_LEGAL_FORMS,
    )


# ---------------------------------------------------------------------------
# A lexer just exact enough to find literals, brackets and operators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    """One token, with the bracket it sits directly in (``-1`` at the top level)."""

    kind: str  # "str", "tmpl", "num", "id", "op"
    text: str
    line: int
    parent: int


_OPERATORS: Final = (
    "?.",
    "??",
    "**",
    "=>",
    "===",
    "!==",
    "==",
    "!=",
    "<=",
    ">=",
    "&&",
    "||",
    "++",
    "--",
    "...",
)
_REGEX_AFTER: Final = frozenset({"(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "=>", "&&", "||", "??"})
_NUMBER: Final = re.compile(r"(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+)n?")
_IDENT: Final = re.compile(r"[A-Za-z_$][\w$]*")
_OPEN: Final = {"(": ")", "[": "]", "{": "}"}


def _skip_template(text: str, start: int) -> int:
    """Return the index after the template that opens at ``start``."""
    i = start + 1
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
        elif char == "`":
            return i + 1
        elif char == "$" and text[i + 1 : i + 2] == "{":
            depth, i = 1, i + 2
            while i < len(text) and depth:
                inner = text[i]
                if inner == "`":
                    i = _skip_template(text, i)
                    continue
                if inner in "'\"":
                    i = _skip_quoted(text, i)
                    continue
                depth += (inner == "{") - (inner == "}")
                i += 1
        else:
            i += 1
    return len(text)


def _skip_quoted(text: str, start: int) -> int:
    """Return the index after the quoted string at ``start``; an unterminated one ends at its line."""
    quote, i = text[start], start + 1
    while i < len(text) and text[i] not in (quote, "\n"):
        i += 2 if text[i] == "\\" else 1
    return i + 1 if i < len(text) and text[i] == quote else i


def _skip_regex(text: str, start: int) -> int:
    i, in_class = start + 1, False
    while i < len(text) and text[i] != "\n":
        char = text[i]
        if char == "\\":
            i += 2
            continue
        in_class = (char == "[") or (in_class and char != "]")
        if char == "/" and not in_class:
            i += 1
            while i < len(text) and text[i].isalpha():
                i += 1
            return i
        i += 1
    return start + 1


def lex(source: str) -> list[Token]:
    """Split TypeScript or JSX source into tokens, dropping comments and whitespace."""
    tokens: list[Token] = []
    stack: list[int] = []
    i, line = 0, 1

    def push(kind: str, text: str, at: int) -> None:
        tokens.append(Token(kind, text, line, stack[-1] if stack else -1))
        if kind == "op" and text in _OPEN:
            stack.append(len(tokens) - 1)
        elif kind == "op" and text in ")]}" and stack:
            stack.pop()
            tokens[-1] = Token(kind, text, line, stack[-1] if stack else -1)

    while i < len(source):
        char = source[i]
        if char == "\n":
            line += 1
            i += 1
        elif char.isspace():
            i += 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end < 0 else end + 2
            line += source.count("\n", i, end)
            i = end
        elif char in "'\"":
            end = _skip_quoted(source, i)
            push("str", source[i + 1 : end - 1].replace("\\", ""), i)
            i = end
        elif char == "`":
            end = _skip_template(source, i)
            body = source[i + 1 : end - 1]
            push("tmpl" if "${" in body else "str", body, i)
            line += body.count("\n")
            i = end
        elif char == "/" and (not tokens or tokens[-1].text in _REGEX_AFTER or tokens[-1].text == "return"):
            end = _skip_regex(source, i)
            push("regex", source[i:end], i)
            i = max(end, i + 1)
        elif (match := _NUMBER.match(source, i)) and (char.isdigit() or (char == "." and match.group())):
            push("num", match.group(), i)
            i = match.end()
        elif match := _IDENT.match(source, i):
            push("id", match.group(), i)
            i = match.end()
        else:
            operator = next((op for op in sorted(_OPERATORS, key=len, reverse=True) if source.startswith(op, i)), char)
            push("op", operator, i)
            i += len(operator)
    return tokens


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    """One finding: the rule that fired, the line, and what was seen."""

    rule: str
    line: int
    detail: str


def _literal_like(tokens: list[Token], index: int) -> bool:
    """Whether the bracket at ``index`` opens an array or object literal rather than a body or call."""
    if tokens[index].text not in {"[", "{"}:
        return False
    if index == 0:
        return True
    before = tokens[index - 1]
    return before.text in {"[", ",", ":", "=", "(", "return", "?", "||", "??", "&&"} and before.kind != "str"


def _literal_chain(tokens: list[Token], token: Token) -> Iterator[int]:
    """Yield the literal brackets enclosing ``token``, innermost first, stopping at the first body or call."""
    parent: int = token.parent
    while parent >= 0 and _literal_like(tokens, parent):
        yield parent
        enclosing: Token = tokens[parent]
        parent = enclosing.parent


def _closer(tokens: list[Token], opener: int) -> int:
    """The index of the bracket that closes ``opener``, or the last token where the source ends first."""
    wanted = _OPEN[tokens[opener].text]
    for index in range(opener + 1, len(tokens)):
        found = tokens[index]
        if found.text == wanted and found.kind == "op" and found.parent == tokens[opener].parent:
            return index
    return len(tokens) - 1


_NOT_A_CALL: Final = frozenset({"if", "for", "while", "switch", "catch", "return", "typeof", "function"})


def _call_paren(tokens: list[Token], index: int) -> bool:
    """Whether the bracket at ``index`` opens the arguments of a call."""
    return (
        index > 0
        and tokens[index].text == "("
        and tokens[index - 1].kind == "id"
        and tokens[index - 1].text not in _NOT_A_CALL
    )


def _value(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace("_", "")).normalize()
    except InvalidOperation:
        return None


def _number(token: Token) -> Decimal | None:
    """A plain number's value, from a numeric literal or a numeric string; a bigint is not one."""
    if token.kind not in {"num", "str"} or token.text.endswith("n") or not token.text:
        return None
    return _value(token.text)


def vocabulary_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """Two or more distinct tokens of one vocabulary as string literals in one file."""
    long_seen: dict[str, dict[str, int]] = {}
    short_seen: dict[tuple[str, int], dict[str, int]] = {}
    for token in tokens:
        if token.kind != "str" or not token.text:
            continue
        for name, members in facts.vocabularies.items():
            if token.text not in members:
                continue
            if len(token.text) >= _MIN_TOKEN:
                long_seen.setdefault(name, {}).setdefault(token.text, token.line)
            elif not token.text.isdigit() and token.parent >= 0 and tokens[token.parent].text == "[":
                short_seen.setdefault((name, token.parent), {}).setdefault(token.text, token.line)
    hits = [
        Hit("vocabulary", min(seen.values()), f"{name}: {', '.join(sorted(seen))}")
        for name, seen in long_seen.items()
        if len(seen) >= 2
    ]
    hits += [
        Hit("vocabulary", min(seen.values()), f"{name} (short tokens in one list): {', '.join(sorted(seen))}")
        for (name, _bracket), seen in short_seen.items()
        if len(seen) >= 2
    ]
    return hits


_DILUTED_RATE_LIST: Final = 3


def _scalar_constants(tokens: list[Token]) -> Iterator[tuple[Token, Decimal, str]]:
    """Each ``const NAME = 21;`` whose whole value is one plain number, with the name."""
    for index, token in enumerate(tokens):
        if token.kind != "id" or token.text not in {"const", "let", "var"} or index + 3 >= len(tokens):
            continue
        cursor = index + 2
        if tokens[cursor].text == ":":  # skip a type annotation up to the "="
            while cursor < len(tokens) and tokens[cursor].text != "=" and tokens[cursor].line == token.line:
                cursor += 1
        if cursor + 1 >= len(tokens) or tokens[cursor].text != "=":
            continue
        value_token = tokens[cursor + 1]
        value = _number(value_token)
        after = tokens[cursor + 2] if cursor + 2 < len(tokens) else None
        if value is not None and (after is None or after.text in {";", ","} or after.line > value_token.line):
            yield value_token, value, tokens[index + 1].text


_WORD: Final = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")


def _words(name: str) -> frozenset[str]:
    """The lower-case words of an identifier written in camelCase or SNAKE_CASE."""
    return frozenset(str(word).lower() for word in _WORD.findall(name) if len(str(word)) >= _MIN_TOKEN)


def _spell(values: Mapping[Decimal, int] | Mapping[int, int]) -> str:
    return ", ".join(sorted(format(v, "f") for v in values))


def rate_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """Dated rate values gathered in one place, however the place is spelled.

    A list or table literal made mostly of rate values, two or more distinct. A small number
    such as 2 or 10 also turns up in a table of widths, so the rate values must be at least
    half of the numbers the literal holds, unless the literal is nothing but numbers and holds
    three or more distinct rates. The same count is made over the arguments of one call, over
    the labels of one ``switch``, and over the numeric constants a file declares: two named
    after the registry's rate vocabulary, or three of any name.
    """
    rates: dict[int, dict[Decimal, int]] = {}
    numbers: dict[int, int] = {}
    members: dict[int, int] = {}
    foreign: set[int] = set()  # a literal holding anything but numbers
    for token in tokens:
        value = _number(token)
        if token.parent >= 0 and value is None and token.text not in {",", "-"}:
            foreign.add(token.parent)
        if value is None:
            continue
        for bracket in _literal_chain(tokens, token):
            numbers[bracket] = numbers.get(bracket, 0) + 1
            if value in facts.rates:
                members[bracket] = members.get(bracket, 0) + 1
                rates.setdefault(bracket, {}).setdefault(value, token.line)
    hits: list[Hit] = []
    for bracket, seen in rates.items():
        pure = tokens[bracket].text == "[" and bracket not in foreign
        mostly = 2 * members[bracket] >= numbers[bracket]
        if len(seen) >= 2 and (mostly or (pure and len(seen) >= _DILUTED_RATE_LIST)):
            hits.append(Hit("rates", min(seen.values()), "rate values " + _spell(seen)))
    # The arguments of one call.
    call_rates: dict[int, dict[Decimal, int]] = {}
    call_numbers: dict[int, int] = {}
    for index, token in enumerate(tokens):
        value = _number(token)
        if value is None or token.parent < 0 or not _call_paren(tokens, token.parent):
            continue
        if tokens[index - 1].text not in {"(", ","} or tokens[index + 1].text not in {",", ")"}:
            continue  # part of a larger expression, not an argument of its own
        call_numbers[token.parent] = call_numbers.get(token.parent, 0) + 1
        if value in facts.rates:
            call_rates.setdefault(token.parent, {}).setdefault(value, token.line)
    hits += [
        Hit("rates", min(seen.values()), "rate values as call arguments " + _spell(seen))
        for bracket, seen in call_rates.items()
        if len(seen) >= 2 and 2 * len(seen) >= call_numbers[bracket]
    ]
    # The labels of one switch.
    labels: dict[Decimal, int] = {}
    for index, token in enumerate(tokens[:-1]):
        value = _number(tokens[index + 1])
        if token.text == "case" and token.kind == "id" and value is not None and value in facts.rates:
            labels.setdefault(value, token.line)
    if len(labels) >= 2:
        hits.append(Hit("rates", min(labels.values()), "rate values as case labels " + _spell(labels)))
    # Separate constants of one file.
    constants: dict[Decimal, int] = {}
    named: dict[Decimal, int] = {}
    for token, value, name in _scalar_constants(tokens):
        if value in facts.rates:
            constants.setdefault(value, token.line)
            if _words(name) & facts.rate_words:
                named.setdefault(value, token.line)
    if len(named) >= 2 or len(constants) >= _DILUTED_RATE_LIST:
        seen = constants if len(constants) >= _DILUTED_RATE_LIST else named
        hits.append(Hit("rates", min(seen.values()), "rate values as constants " + _spell(seen)))
    # An enclosing literal repeats its members' hit; one report per line and detail is enough.
    return list({(hit.line, hit.detail): hit for hit in hits}.values())


_STOP: Final = frozenset(
    {
        *("+", "-", "*", "/", "%", ",", ";", ")", "]", "}", "?", ":", "=", "==", "===", "!=", "!==", "<", ">"),
        *("<=", ">=", "&&", "||", "??", "=>", "(", "[", "{"),
    }
)
_PRODUCT: Final = frozenset({"*", "/", "%"})
_HELPER: Final = re.compile(r"^(?:timesTo\w*|multiplyBy\w*|mulDecimal\w*|\w+ToCent)$")
_METHOD: Final = frozenset({"times", "mul", "multiply", "multipliedBy"})
_POWER_OF_TEN: Final = re.compile(r"^10*n$")
_EXACT_MEMBERS: Final = frozenset({"units", "cents"})


def _chain(tokens: list[Token], star: int) -> list[list[Token]]:
    """The factors of the product chain around the ``*`` at ``star``, split on ``*``, ``/`` and ``%``."""
    left: list[Token] = []
    depth = 0
    for token in reversed(tokens[:star]):
        if token.kind == "op" and token.text in {")", "]", "}"}:
            depth += 1
        elif token.kind == "op" and token.text in {"(", "[", "{"}:
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and token.kind == "op" and token.text in _STOP and token.text not in _PRODUCT:
            break
        left.append(token)
    right: list[Token] = []
    depth = 0
    for token in tokens[star + 1 :]:
        if token.kind == "op" and token.text in {"(", "[", "{"}:
            depth += 1
        elif token.kind == "op" and token.text in {")", "]", "}"}:
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and token.kind == "op" and token.text in _STOP and token.text not in _PRODUCT:
            if not right:
                continue  # a unary sign before the operand
            break
        right.append(token)
    factors: list[list[Token]] = [[]]
    depth = 0
    for token in [*left[::-1], tokens[star], *right]:
        if token.kind == "op" and token.text in {"(", "[", "{"}:
            depth += 1
        elif token.kind == "op" and token.text in {")", "]", "}"}:
            depth -= 1
        if depth == 0 and token.kind == "op" and token.text in _PRODUCT:
            factors.append([])
        else:
            factors[-1].append(token)
    return [factor for factor in factors if factor]


def _is_power_of_ten(operand: list[Token], scales: set[str]) -> bool:
    """A power-of-ten literal, alone or as the base of ``**``, or a local name defined as one."""
    if not operand:
        return False
    head = operand[0]
    if head.kind == "num" and _POWER_OF_TEN.match(head.text):
        return len(operand) == 1 or operand[1].text == "**"
    return len(operand) == 1 and head.kind == "id" and head.text in scales


def _bigint_like(operand: list[Token], bigints: set[str]) -> bool:
    texts = [t.text for t in operand]
    return (
        any(t.kind == "num" and t.text.endswith("n") for t in operand)
        or "BigInt" in texts
        or any(a in {".", "?."} and b in _EXACT_MEMBERS for a, b in pairwise(texts))
        or any(t.kind == "id" and t.text in bigints for t in operand)
    )


def _scale_names(tokens: list[Token]) -> set[str]:
    """Local names defined only from powers of ten, such as ``const scale = 10n ** BigInt(places)``."""
    scales: set[str] = set()
    for name, span in _declared_spans(tokens):
        literals = [t.text for t in span if t.kind == "num" and t.text.endswith("n")]
        if literals and all(_POWER_OF_TEN.match(text) for text in literals) and not any(t.text == "*" for t in span):
            scales.add(name)
    return scales


def _bigint_names(tokens: list[Token], scales: set[str]) -> set[str]:
    """Local names the file declares as a bigint, by annotation or by what they are set from."""
    names = {
        tokens[i].text
        for i in range(len(tokens) - 2)
        if tokens[i].kind == "id" and tokens[i + 1].text == ":" and tokens[i + 2].text == "bigint"
    }
    for name, span in _declared_spans(tokens):
        if any((t.kind == "num" and t.text.endswith("n")) or t.text == "BigInt" for t in span):
            names.add(name)
    return names - scales


def multiplication_hits(tokens: list[Token]) -> list[Hit]:
    """Exact-decimal products and named multiplying helpers.

    A product chain counts when it holds an exact (bigint) factor and two or more factors that
    are not a power of ten: ``a.units * b.units``, ``b * r / 100n`` with ``r`` a bigint, and
    ``u * 100n * 21n``. Scaling by one power of ten is how a decimal is aligned.
    """
    hits: list[Hit] = []
    scales = _scale_names(tokens)
    bigints = _bigint_names(tokens, scales)
    for index, token in enumerate(tokens):
        if token.kind == "id" and _HELPER.match(token.text):
            hits.append(Hit("multiplication", token.line, f"helper {token.text}"))
        if (
            token.kind == "id"
            and token.text in _METHOD
            and index > 0
            and tokens[index - 1].text in {".", "?."}
            and index + 1 < len(tokens)
            and tokens[index + 1].text == "("
        ):
            hits.append(Hit("multiplication", token.line, f"method {token.text}"))
        if token.kind != "op" or token.text != "*":
            continue
        factors = _chain(tokens, index)
        if not any(_bigint_like(factor, bigints) for factor in factors):
            continue
        if sum(not _is_power_of_ten(factor, scales) for factor in factors) < 2:
            continue
        hits.append(Hit("multiplication", token.line, "product of exact decimals"))
    return list({(hit.line, hit.detail): hit for hit in hits}.values())


_COMPUTING_ANYWHERE: Final = frozenset({"toFixed", "units", "cents"})
_COMPUTING_GLOBAL: Final = frozenset({"BigInt", "Number", "parseFloat", "parseInt", "Math"})


def _template_expressions(body: str) -> Iterator[str]:
    """The ``${...}`` expressions of a template literal's body."""
    i = 0
    while (i := body.find("${", i)) >= 0:
        depth, j = 1, i + 2
        while j < len(body) and depth:
            depth += (body[j] == "{") - (body[j] == "}")
            j += 1
        yield body[i + 2 : j - 1]
        i = j


def _computes(span: list[Token], computed: set[str]) -> bool:
    """Whether the tokens work something out: arithmetic, a conversion to a number, or a computed name."""
    for index, token in enumerate(span):
        member = index > 0 and span[index - 1].text in {".", "?."}
        if token.kind == "tmpl" and any(
            _computes(lex(expression), computed) for expression in _template_expressions(token.text)
        ):
            return True
        if token.kind == "id":
            if token.text in _COMPUTING_ANYWHERE or _HELPER.match(token.text):
                return True
            if member and token.text in _METHOD and index + 1 < len(span) and span[index + 1].text == "(":
                return True
            if not member and (token.text in _COMPUTING_GLOBAL or token.text in computed):
                return True
        if token.kind == "op" and token.text in {"*", "**"}:
            return True
        if token.kind == "op" and token.text in {"+", "-", "/", "%"} and 0 < index < len(span) - 1:
            before, after = span[index - 1], span[index + 1]
            if (before.kind in {"id", "num"} or before.text in {")", "]"}) and (
                after.kind in {"id", "num"} or after.text == "("
            ):
                return True
    return False


def _declared_spans(tokens: list[Token]) -> Iterator[tuple[str, list[Token]]]:
    """Yield each ``const/let/var NAME = ...;`` initialiser that is a value and not a function."""
    for index, token in enumerate(tokens):
        name_at = index + 1
        if token.kind != "id" or token.text not in {"const", "let", "var"} or name_at + 1 >= len(tokens):
            continue
        name = tokens[name_at]
        if name.kind != "id" or tokens[name_at + 1].text not in {"=", ":"}:
            continue
        end = name_at + 2
        while (
            end < len(tokens)
            and tokens[end].parent >= token.parent
            and not (tokens[end].text == ";" and tokens[end].parent == token.parent)
        ):
            end += 1
        span = tokens[name_at + 2 : end]
        is_function = any(t.text == "=>" and t.parent == token.parent for t in span) or any(
            t.text == "function" for t in span
        )
        if not is_function:
            yield name.text, span


def computed_names(tokens: list[Token]) -> set[str]:
    """Names, local to the file, whose definition works a figure out."""
    declared: dict[str, list[list[Token]]] = {}
    for name, span in _declared_spans(tokens):
        declared.setdefault(name, []).append(span)
    computed: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, spans in declared.items():
            # The scan is blind to scope, so a name counts only when every declaration of it computes.
            if name not in computed and all(_computes(span, computed) for span in spans):
                computed.add(name)
                changed = True
    return computed


_OPERATING: Final = frozenset(
    {*("+", "-", "*", "/", "%", "**", "?", ":", "=", "&&", "||", "??", "(", "[", "{", ",", "=>", "."), "<", ">"}
)


def _assigned_value(tokens: list[Token], equals: int) -> list[Token]:
    """The tokens of the right-hand side of the assignment at ``equals``."""
    owner = tokens[equals].parent
    value: list[Token] = []
    for index in range(equals + 1, len(tokens)):
        follower = tokens[index]
        if follower.parent < owner or (follower.parent == owner and follower.text in {";", ","}):
            break
        if (
            follower.parent == owner
            and follower.line > tokens[index - 1].line
            and tokens[index - 1].text not in _OPERATING
            and follower.text not in _OPERATING
        ):
            break  # the next statement, with no semicolon between
        value.append(follower)
    return value


def _member_assignment(tokens: list[Token], index: int) -> int | None:
    """The index of the ``=`` when the token at ``index`` is assigned as ``o.name`` or ``o["name"]``."""
    token = tokens[index]
    if index == 0 or index + 1 >= len(tokens):
        return None
    before, after = tokens[index - 1], tokens[index + 1]
    if token.kind == "id" and before.text in {".", "?."} and after.text == "=":
        return index + 1
    if (
        token.kind == "str"
        and before.text == "["
        and after.text == "]"
        and index + 2 < len(tokens)
        and tokens[index + 2].text == "="
    ):
        return index + 2
    return None


def figure_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A request literal, or an assignment to a wire member, that sets a figure from a computation."""
    computed = computed_names(tokens)
    hits: list[Hit] = []
    for index, token in enumerate(tokens):
        if token.text not in facts.figure_keys or token.kind not in {"id", "str"}:
            continue
        equals = _member_assignment(tokens, index)
        if equals is not None:
            assigned = _assigned_value(tokens, equals)
            if assigned and (_computes(assigned, computed) or (len(assigned) == 1 and assigned[0].kind == "num")):
                hits.append(Hit("figures", token.line, f"{token.text} is assigned a computation"))
            continue
        if token.parent < 0 or tokens[token.parent].text != "{":
            continue
        after = tokens[index + 1] if index + 1 < len(tokens) else None
        before = tokens[index - 1]
        if after is not None and after.text == ":":
            value: list[Token] = []
            for follower in tokens[index + 2 :]:
                if follower.parent == token.parent and follower.text in {",", ";"}:
                    break
                if follower.parent < token.parent or (
                    follower.text == "}" and follower.parent == tokens[token.parent].parent
                ):
                    break
                value.append(follower)
            if value and value[-1].text == "}" and value[-1].parent == tokens[token.parent].parent:
                value.pop()
            terminated_by_semicolon = (
                index + 2 + len(value) < len(tokens) and tokens[index + 2 + len(value)].text == ";"
            )
            if terminated_by_semicolon:
                continue  # a member of a type, not a request literal
            if any(t.text in {"=>", "function"} for t in value):
                continue  # a renderer or accessor, not a figure
            if value and (_computes(value, computed) or (len(value) == 1 and value[0].kind == "num")):
                hits.append(Hit("figures", token.line, f"{token.text} is computed"))
        elif (
            token.kind == "id"
            and before.text in {",", "{"}
            and after is not None
            and after.text in {",", "}"}
            and token.text in computed
        ):
            hits.append(Hit("figures", token.line, f"{token.text} is computed"))
    return hits


_COMPARISONS: Final = frozenset({"===", "!==", "==", "!="})
_MEMBERSHIP: Final = frozenset({"includes", "has", "indexOf", "lastIndexOf", "some", "find", "findIndex"})
_NOT_A_LOOKUP: Final = frozenset({"return", "case", "typeof", "in", "of", "yield", "await", "void", "delete"})


def _compared(tokens: list[Token], index: int) -> bool:
    """Whether the literal at ``index`` is an operand of an equality test or a ``case`` label."""
    before = tokens[index - 1].text if index > 0 else ""
    after = tokens[index + 1].text if index + 1 < len(tokens) else ""
    return before in _COMPARISONS or after in _COMPARISONS or before == "case"


def _looked_up(tokens: list[Token], index: int) -> bool:
    """Whether the literal at ``index`` is looked up in a collection or is a member of one that is.

    ``["A", "B"].includes(x)``, ``new Set(["A"])``, ``x.includes("A")``, ``set.has("A")``, ``rule["A"]``.
    """
    parent = tokens[index].parent
    if parent < 0:
        return False
    opener = tokens[parent]
    before = tokens[parent - 1] if parent > 0 else None
    if opener.text == "(":
        return before is not None and before.text in _MEMBERSHIP
    if opener.text != "[":
        return False
    if before is not None and (before.kind == "id" or before.text in {")", "]"}):
        return before.text not in _NOT_A_LOOKUP  # an index: a lookup by key
    closer = _closer(tokens, parent)
    if closer + 2 < len(tokens) and tokens[closer + 1].text == "." and tokens[closer + 2].text in _MEMBERSHIP:
        return True
    return before is not None and before.text == "(" and parent > 1 and tokens[parent - 2].text == "Set"


def _record_key(tokens: list[Token], index: int) -> bool:
    """Whether the token is a key of an object literal."""
    token = tokens[index]
    if index == 0 or token.parent < 0 or tokens[token.parent].text != "{":
        return False
    before = tokens[index - 1]
    after = tokens[index + 1] if index + 1 < len(tokens) else None
    return before.text in {"{", ","} and after is not None and after.text == ":"


def classification_hits(tokens: list[Token]) -> list[Hit]:
    """A decided classification tested, listed, switched on or used as a key, by whatever spelling."""
    hits: list[Hit] = []
    lists: dict[int, dict[str, int]] = {}
    for index, token in enumerate(tokens):
        if token.kind not in {"str", "id"} or token.text not in _CLASSIFICATIONS:
            continue
        if token.kind == "str" and (_compared(tokens, index) or _looked_up(tokens, index)):
            hits.append(Hit("classification", token.line, token.text))
        elif _record_key(tokens, index):
            hits.append(Hit("classification", token.line, f"{token.text} as a key"))
        if (
            token.kind == "str"
            and token.parent >= 0
            and _literal_like(tokens, token.parent)
            and tokens[token.parent].text == "["
        ):
            lists.setdefault(token.parent, {}).setdefault(token.text, token.line)
    # Two or more in one list are a copy of the vocabulary, whether or not the list is asked.
    hits += [
        Hit("classification", min(seen.values()), "listed " + ", ".join(sorted(seen)))
        for seen in lists.values()
        if len(seen) >= 2
    ]
    return list({(hit.line, hit.detail): hit for hit in hits}.values())


def modelo_branch_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A registry modelo number tested or switched on: which modelo takes a path is the registry's."""
    return [
        Hit("modelo_branch", token.line, token.text)
        for index, token in enumerate(tokens)
        if token.kind == "str"
        and token.text in facts.modelos
        and (_compared(tokens, index) or _looked_up(tokens, index))
    ]


_ORDERING: Final = frozenset({"<", "<=", ">", ">="})


def year_window_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A year inside the registry's filing-year envelope used as a bound, a label, or two in one literal."""
    if not facts.years:
        return []
    low, high = min(facts.years), max(facts.years)

    def in_window(value: Decimal | None) -> bool:
        return value is not None and value == value.to_integral_value() and low <= int(value) <= high

    hits: list[Hit] = []
    literals: dict[int, dict[int, int]] = {}
    for index, token in enumerate(tokens):
        value = _number(token)
        if not in_window(value) or value is None or (token.kind == "str" and not token.text.isdigit()):
            continue
        before = tokens[index - 1].text if index > 0 else ""
        after = tokens[index + 1].text if index + 1 < len(tokens) else ""
        if _compared(tokens, index) or before in _ORDERING or after in _ORDERING:
            hits.append(Hit("year_window", token.line, f"year {int(value)} compared"))
        for bracket in _literal_chain(tokens, token):
            literals.setdefault(bracket, {}).setdefault(int(value), token.line)
    hits += [
        Hit("year_window", min(seen.values()), "years " + ", ".join(str(y) for y in sorted(seen)))
        for seen in literals.values()
        if len(seen) >= 2
    ]
    standing: dict[int, int] = {}
    for token, value, _name in _scalar_constants(tokens):
        if in_window(value):
            standing.setdefault(int(value), token.line)
    if len(standing) >= 2:
        hits.append(
            Hit(
                "year_window",
                min(standing.values()),
                "years as constants " + ", ".join(str(y) for y in sorted(standing)),
            )
        )
    return list({(hit.line, hit.detail): hit for hit in hits}.values())


_ROUTE_MINIMUM: Final = 3
_ROUTED_REASONS: Final = 2
_PREDICATES: Final = frozenset({"filter", "find", "some", "every", "findIndex"})


def field_route_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A hand-kept set of identity fields or of the fields a correction waits on."""
    held: dict[tuple[str, int], dict[str, int]] = {}
    for token in tokens:
        if token.kind != "str" or token.parent < 1 or tokens[token.parent].text != "[":
            continue
        opening = token.parent
        if tokens[opening - 1].text != "(" or opening < 2 or tokens[opening - 2].text != "Set":
            continue
        if token.text in facts.identity_tokens:
            held.setdefault(("identity", opening), {}).setdefault(token.text, token.line)
        if token.text in facts.judged_fields:
            held.setdefault(("judged", opening), {}).setdefault(token.text, token.line)
    reasons = facts.vocabularies["readiness_reason"]
    routed: dict[int, dict[str, int]] = {}
    for index, token in enumerate(tokens[:-2]):
        if token.text in reasons and _record_key(tokens, index) and tokens[index + 2].kind == "str":
            routed.setdefault(token.parent, {}).setdefault(token.text, token.line)
    routes = [
        Hit("field_route", min(seen.values()), f"readiness reasons routed: {', '.join(sorted(seen))}")
        for seen in routed.values()
        if len(seen) >= _ROUTED_REASONS
    ]
    return routes + [
        Hit("field_route", min(seen.values()), f"{name} fields: {', '.join(sorted(seen))}")
        for (name, _bracket), seen in held.items()
        if len(seen) >= _ROUTE_MINIMUM
    ]


def _inside_predicate(tokens: list[Token], token: Token) -> bool:
    """Whether the token sits in the arguments of a collection predicate."""
    parent = token.parent
    while parent >= 1:
        if tokens[parent].text == "(" and tokens[parent - 1].text in _PREDICATES:
            return True
        parent = tokens[parent].parent
    return False


def direction_rule_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A direction chosen by a condition, or tested to choose which rows a rule takes."""
    hits: list[Hit] = []
    for index, token in enumerate(tokens):
        if token.kind != "str" or token.text not in facts.directions:
            continue
        before = tokens[index - 1].text if index > 0 else ""
        after = tokens[index + 1].text if index + 1 < len(tokens) else ""
        if before == "?" and after == ":":
            hits.append(Hit("direction_rule", token.line, f"{token.text} chosen by a condition"))
        elif _compared(tokens, index) and _inside_predicate(tokens, token):
            hits.append(Hit("direction_rule", token.line, f"{token.text} tested in a predicate"))
    return hits


def text_limit_hits(tokens: list[Token]) -> list[Hit]:
    """A number given as the limit ``parseLine`` or ``textField`` holds typed text to."""
    return [
        Hit("text_limit", token.line, f"{token.text} given a number as its limit")
        for index, token in enumerate(tokens)
        if token.text in {"parseLine", "textField"}
        and any(
            tokens[at].text == "," and tokens[at + 1].kind == "num"
            for at in range(index + 2, min(index + 8, len(tokens) - 1))
        )
    ]


#: How many of the backend's bare legal forms one pattern must alternate to be a copy of the list.
_LEGAL_FORMS_IN_PATTERN: Final = 3
_PATTERN_NOISE: Final = re.compile(r"\\[bB]|[\\^$()?.*+\s]")


def _legal_form_alternatives(literal: str, facts: Facts) -> int:
    """How many alternatives of a regex literal are a legal form the backend reads as naming no party."""
    body = literal[1 : literal.rfind("/")].lower()
    return sum(1 for part in body.split("|") if _PATTERN_NOISE.sub("", part) in facts.legal_forms)


def _arrow_declared(tokens: list[Token], index: int) -> bool:
    """Whether the name at ``index`` is assigned a function: ``name = (..) =>``, ``name = x =>`` or ``function``."""
    if index + 2 >= len(tokens) or tokens[index + 1].text != "=":
        return False
    follow = tokens[index + 2]
    if follow.text in {"function", "async"}:
        return True
    if follow.kind == "id":
        return index + 3 < len(tokens) and tokens[index + 3].text == "=>"
    if follow.text != "(":
        return False
    depth = 0
    for at in range(index + 2, len(tokens)):
        depth += (tokens[at].text == "(") - (tokens[at].text == ")")
        if depth == 0:
            return at + 1 < len(tokens) and tokens[at + 1].text == "=>"
    return False


def moved_rule_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A moved rule's name, or a staged split's children that are not the backend's answer."""
    hits = [
        Hit("moved_rule", token.line, f"{token.text} is answered by the backend")
        for token in tokens
        if token.kind != "str" and token.text in _MOVED_RULE_NAMES
    ]
    hits += [
        Hit("moved_rule", token.line, f"{token.text} is answered by the backend")
        for index, token in enumerate(tokens)
        if token.kind != "str"
        and token.text in _MOVED_RULE_CALLS
        and index + 1 < len(tokens)
        and tokens[index + 1].text == "("
    ]
    hits += [
        Hit("moved_rule", token.line, f"{token.text} is declared as a function, and is answered by the backend")
        for index, token in enumerate(tokens)
        if token.kind != "str" and token.text in _MOVED_FOLD_NAMES and _arrow_declared(tokens, index)
    ]
    hits += [
        Hit("moved_rule", token.line, "a pattern of legal forms: which names are one party is the backend's")
        for token in tokens
        if token.kind == "regex" and _legal_form_alternatives(token.text, facts) >= _LEGAL_FORMS_IN_PATTERN
    ]
    for index, token in enumerate(tokens):
        if token.kind != "str" and token.text in _DUPLICATE_FACTS and _inside_predicate(tokens, token):
            window = tokens[max(index - 6, 0) : index + 5]
            folded = tokens[index + 1].text == ")" if index + 1 < len(tokens) else False
            if any(near.text in {"===", "!=="} for near in window) and (folded or token.text != "invoice_number"):
                hits.append(Hit("moved_rule", token.line, f"{token.text} compared in the window"))
        if token.kind != "str" or token.text != "split" or tokens[index - 1].text != ":":
            continue
        for at in range(index + 1, min(index + 16, len(tokens) - 2)):
            if (
                tokens[at].text == "children"
                and tokens[at + 1].text == ":"
                and tokens[at + 2].text not in {"answer", "{"}
            ):
                hits.append(Hit("moved_rule", tokens[at].line, "a split's children are not the backend's answer"))
    return hits


def scan_source(source: str, facts: Facts) -> list[Hit]:
    """Run every rule over one file's source."""
    tokens = lex(source)
    return [
        *vocabulary_hits(tokens, facts),
        *rate_hits(tokens, facts),
        *multiplication_hits(tokens),
        *figure_hits(tokens, facts),
        *classification_hits(tokens),
        *modelo_branch_hits(tokens, facts),
        *year_window_hits(tokens, facts),
        *field_route_hits(tokens, facts),
        *direction_rule_hits(tokens, facts),
        *text_limit_hits(tokens),
        *moved_rule_hits(tokens, facts),
    ]


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------


_DRIVER_SCRIPT: Final = re.compile(r"""["']scripts/(\w+\.py)["']""")
_DRIVER_OUTPUT: Final = re.compile(r"""["']src/([\w./-]+\.[cm]?tsx?)["']""")


def _script_headers(script: Path) -> tuple[str, ...]:
    """The opening comment block a generator script writes, read from its own header constants."""
    headers: list[str] = []
    for node in ast.parse(script.read_text(encoding="utf-8")).body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and any(isinstance(target, ast.Name) and target.id.endswith("HEADER") for target in node.targets)
        ):
            headers.append("\n".join(node.value.value.splitlines()[:3]))
    return tuple(headers)


def generated_outputs(scripts: Path = _GENERATORS) -> dict[str, tuple[str, ...]]:
    """Each generated file, by path under ``src``, with the headers its generator may write.

    A driver (``scripts/*.mjs``) names the Python producer it runs and the files it writes; a
    file is generated only where a driver declares it as an output, and only the headers of
    that driver's producer open it.
    """
    outputs: dict[str, tuple[str, ...]] = {}
    for driver in sorted(scripts.glob("*.mjs")):
        text = driver.read_text(encoding="utf-8")
        producers = [scripts / name for name in _DRIVER_SCRIPT.findall(text) if (scripts / name).is_file()]
        headers = tuple(header for producer in producers for header in _script_headers(producer))
        if not headers:
            continue
        for path in _DRIVER_OUTPUT.findall(text):
            outputs[path] = tuple(dict.fromkeys((*outputs.get(path, ()), *headers)))
    return outputs


def is_generated(source: str, relative: str, outputs: Mapping[str, tuple[str, ...]]) -> bool:
    """Whether the file is a declared generator output and opens with exactly that generator's header."""
    opening = "\n".join(source.replace("\r\n", "\n").splitlines()[:3])
    return opening in outputs.get(relative, ())


def window_sources(root: Path = _SOURCE) -> Iterator[Path]:
    """Yield the production sources under ``root``, by the filesystem and not by Git."""
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            path.is_file()
            and path.suffix in _EXTENSIONS
            and not _EXCLUDED_NAME.search(path.name)
            and relative.parts[0] != "dev"
            and "node_modules" not in relative.parts
        ):
            yield path


def scan_tree(root: Path, facts: Facts, outputs: Mapping[str, tuple[str, ...]]) -> dict[str, list[Hit]]:
    """Return the hits of each non-generated source, by path relative to ``root``."""
    found: dict[str, list[Hit]] = {}
    for path in window_sources(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        if is_generated(source, relative, outputs):
            continue
        hits = scan_source(source, facts)
        if hits:
            found[relative] = hits
    return found


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def facts() -> Facts:
    return read_facts()


@pytest.fixture(scope="module")
def outputs() -> dict[str, tuple[str, ...]]:
    return generated_outputs()


def _fired(source: str, facts: Facts) -> set[str]:
    return {hit.rule for hit in scan_source(source, facts)}


def _two_categories(facts: Facts) -> tuple[str, str]:
    first, second = sorted(token for token in facts.vocabularies["iva_category"] if len(token) >= _MIN_TOKEN)[:2]
    return first, second


def _points(facts: Facts) -> list[Decimal]:
    return sorted(rate for rate in facts.rates if rate >= 1)


def _whole_rates(facts: Facts) -> list[int]:
    return [int(rate) for rate in _points(facts) if rate == rate.to_integral_value()]


def test_the_facts_are_read_from_the_registry_not_listed_here(facts: Facts) -> None:
    assert {"iva_category", "irpf_category", "spending_category", "iva_rate_slot"} <= set(facts.vocabularies)
    assert all(len(members) >= 2 for members in facts.vocabularies.values() if members)
    assert len(facts.rates) >= 4
    assert len(facts.modelos) >= 4
    assert len(facts.years) >= 2


def test_the_figure_keys_come_from_the_invoice_contracts(facts: Facts) -> None:
    assert {"subtotal", "iva_amount", "retention_amount", "recargo_amount", "grand_total", "taxable_base"} <= (
        facts.figure_keys
    )
    assert not {"description", "invoice_number", "counterparty_name"} & facts.figure_keys


# -- rates -------------------------------------------------------------------


def test_a_renamed_rate_table_fails_the_rates_rule(facts: Facts) -> None:
    points = _points(facts)[:2]
    source = f"export const SOMETHING_ELSE = {{ general: {points[0]}, reduced: {points[1]} }};\n"
    assert "rates" in _fired(source, facts)


def test_a_list_of_rates_among_other_numbers_fails_the_rates_rule(facts: Facts) -> None:
    rates = _whole_rates(facts)[:4]
    fillers = [n for n in range(1, 40) if Decimal(n) not in facts.rates][:6]
    assert len(rates) == 4
    assert 2 * len(rates) < len(rates) + len(fillers)
    source = f"export const STEPS = [{', '.join(str(n) for n in [*rates, *fillers])}];\n"
    assert "rates" in _fired(source, facts)


def test_a_few_rate_like_numbers_among_many_widths_pass(facts: Facts) -> None:
    rate = _whole_rates(facts)[-1]
    fillers = [n for n in range(1, 60) if Decimal(n) not in facts.rates][:8]
    source = f"export const WIDTHS = [{rate}, {', '.join(str(n) for n in fillers)}];\n"
    assert "rates" not in _fired(source, facts)


def test_rates_declared_as_separate_constants_fail_the_rates_rule(facts: Facts) -> None:
    first, second = _whole_rates(facts)[-2:]
    assert "rates" in _fired(f"const GENERAL = {first};\nconst REDUCED = {second};\n", facts)
    assert "rates" not in _fired(f"const GENERAL = {first};\nconst PAGE = 7000;\n", facts)


def test_rates_in_a_switch_fail_the_rates_rule(facts: Facts) -> None:
    first, second = _whole_rates(facts)[-2:]
    source = f"function f(x: number) {{ switch (x) {{ case {first}: return 1; case {second}: return 2; }} }}\n"
    assert "rates" in _fired(source, facts)


def test_rates_in_the_arguments_of_a_call_fail_the_rates_rule(facts: Facts) -> None:
    first, second = _whole_rates(facts)[-2:]
    assert "rates" in _fired(f"const x = taxFor(amount, {first}, {second});\n", facts)
    assert "rates" not in _fired(f"const x = taxFor(amount, {first}, 3, 1, 8);\n", facts)


# -- multiplication ----------------------------------------------------------


def test_a_product_of_exact_decimals_fails_the_multiplication_rule(facts: Facts) -> None:
    source = "export const total = (left: Amount, right: Amount) => left.units * right.units;\n"
    assert "multiplication" in _fired(source, facts)


def test_a_bigint_product_without_a_power_of_ten_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const x = BigInt(a) * BigInt(b);\n", facts)
    assert "multiplication" in _fired("const x = timesToCent(a, b);\n", facts)


def test_a_product_with_a_named_bigint_constant_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const r = 21n;\nconst tax = (b: bigint) => b * r / 100n;\n", facts)
    assert "multiplication" in _fired("const tax = (a: bigint, b: bigint) => a * b;\n", facts)


def test_a_rate_beside_a_power_of_ten_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const tax = (u: bigint) => u * 100n * 21n / 10000n;\n", facts)


def test_a_product_of_minor_unit_members_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const x = a.cents * b.cents;\n", facts)


def test_a_multiplying_method_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const x = a.times(b);\n", facts)
    assert "multiplication" in _fired("const x = a.multipliedBy(b);\n", facts)
    assert "multiplication" not in _fired("const times = 3;\nconst y = { times: 2 };\n", facts)


def test_aligning_a_decimal_by_one_power_of_ten_passes(facts: Facts) -> None:
    source = (
        "const scale = (units: bigint, places: number) => units * 10n ** BigInt(places);\n"
        "const cents = (units: bigint) => units * 100n;\n"
        "const whole = (units: bigint) => (units * 100n) / 100n;\n"
    )
    assert "multiplication" not in _fired(source, facts)


# -- figures -----------------------------------------------------------------


def test_a_figure_built_from_a_local_computation_fails_the_figures_rule(facts: Facts) -> None:
    source = (
        "function build(quantity: string, price: string) {\n"
        "  const base = Number(quantity) * Number(price);\n"
        "  return { subtotal: String(base), description: 'x' };\n"
        "}\n"
    )
    assert "figures" in _fired(source, facts)


def test_a_shorthand_figure_that_is_computed_fails_the_figures_rule(facts: Facts) -> None:
    source = "function build(a: number, b: number) { const subtotal = a * b; return { subtotal, note: '' }; }"
    assert "figures" in _fired(source, facts)


def test_every_contract_figure_computed_in_a_request_fails_the_figures_rule(facts: Facts) -> None:
    missed = sorted(
        key for key in facts.figure_keys if "figures" not in _fired(f"const r = {{ {key}: a * b }};\n", facts)
    )
    assert missed == []


def test_a_figure_in_a_template_fails_the_figures_rule(facts: Facts) -> None:
    assert "figures" in _fired("const r = { iva_amount: `${a * b}` };\n", facts)
    assert "figures" in _fired("const a = x * y;\nconst r = { iva_amount: `${a}` };\n", facts)
    assert "figures" not in _fired("const r = { iva_amount: `${typed.iva}` };\n", facts)


def test_a_figure_assigned_to_a_member_fails_the_figures_rule(facts: Facts) -> None:
    assert "figures" in _fired("function f(o: Wire) {\n  o.subtotal = a * b;\n  return o;\n}\n", facts)
    assert "figures" in _fired('function f(o: Wire) {\n  o["subtotal"] = a * b;\n  return o;\n}\n', facts)
    assert "figures" in _fired("function f(o: Wire) {\n  o.grand_total = Number(a)\n  return o;\n}\n", facts)
    assert "figures" not in _fired("function f(o: Wire, p: P) {\n  o.subtotal = p.subtotal;\n  return o;\n}\n", facts)


def test_a_figure_from_a_multiplying_method_fails_the_figures_rule(facts: Facts) -> None:
    assert "figures" in _fired("const r = { subtotal: a.times(b) };\n", facts)


# -- vocabulary --------------------------------------------------------------


def test_a_list_of_two_iva_categories_fails_the_vocabulary_rule(facts: Facts) -> None:
    first, second = _two_categories(facts)
    source = f'export const OFFERED = ["{first}", "{second}"];\n'
    assert "vocabulary" in _fired(source, facts)


def test_two_short_tokens_count_only_inside_one_list(facts: Facts) -> None:
    letters = sorted(token for token in facts.vocabularies["prorrata_sector_letter"] if len(token) < _MIN_TOKEN)[:2]
    listed = f'const a = ["{letters[0]}", "{letters[1]}"];\n'
    apart = f'const a = "{letters[0]}";\nfunction f() {{ return "{letters[1]}"; }}\n'
    assert "vocabulary" in _fired(listed, facts)
    assert "vocabulary" not in _fired(apart, facts)


# -- classification ----------------------------------------------------------


def test_comparing_a_decided_classification_fails_the_classification_rule(facts: Facts) -> None:
    token = sorted(_CLASSIFICATIONS)[0]
    assert "classification" in _fired(f'const share = code === "{token}";\n', facts)
    assert "classification" in _fired(f'const share = "{token}" !== code;\n', facts)
    assert "classification" in _fired(f'const share = code == "{token}";\n', facts)
    assert "classification" in _fired(f'const share = code != "{token}";\n', facts)
    assert "classification" not in _fired(f'const named = {{ mixed: "{token}" }};\n', facts)
    assert "classification" not in _fired('const refused = code === "NOT_YET_PROCESSED";\n', facts)


@pytest.mark.parametrize(
    "template",
    [
        'const takes = ["{a}"].includes(code);\n',
        'const takes = code.includes("{a}");\n',
        'const takes = new Set(["{a}"]).has(code);\n',
        'const takes = group.has("{a}");\n',
        'function f(code: string) {{ switch (code) {{ case "{a}": return 1; default: return 0; }} }}\n',
        "const allows = {{ {a}: true, other: false }};\n",
        'const allows = {{ "{a}": true }};\n',
        'const word = labels["{a}"];\n',
        'const set = new Set(["{a}", "{b}"]);\n',
        'const both = ["{a}", "{b}"];\n',
    ],
)
def test_a_decided_classification_looked_up_or_listed_fails_the_classification_rule(
    template: str, facts: Facts
) -> None:
    a, b = sorted(_CLASSIFICATIONS)[:2]
    assert "classification" in _fired(template.format(a=a, b=b), facts)


# -- modelo and year branches ------------------------------------------------


def test_branching_on_a_modelo_fails_the_modelo_branch_rule(facts: Facts) -> None:
    modelo = sorted(facts.modelos)[0]
    assert "modelo_branch" in _fired(f'const annual = m === "{modelo}";\n', facts)
    assert "modelo_branch" in _fired(f'const annual = "{modelo}" !== m;\n', facts)
    assert "modelo_branch" in _fired(
        f'function f(m: string) {{ switch (m) {{ case "{modelo}": return 1; }} }}\n', facts
    )
    assert "modelo_branch" in _fired(f'const annual = ["{modelo}"].includes(m);\n', facts)
    assert "modelo_branch" not in _fired(f'const id = "{modelo}";\nconst label = names[m];\n', facts)
    assert "modelo_branch" not in _fired('const status = code === "OK";\n', facts)


def test_a_year_bound_in_the_support_window_fails_the_year_window_rule(facts: Facts) -> None:
    low, high = min(facts.years), max(facts.years)
    assert "year_window" in _fired(f"const supported = year >= {low};\n", facts)
    assert "year_window" in _fired(f"const supported = year === {high};\n", facts)
    assert "year_window" in _fired(f"const supported = {high} > year;\n", facts)
    assert "year_window" in _fired(f"const YEARS = [{low}, {low + 1}];\n", facts)
    assert "year_window" in _fired(f"const FIRST = {low};\nconst LAST = {high};\n", facts)
    assert "year_window" in _fired(f"function f(y: number) {{ switch (y) {{ case {low}: return 1; }} }}\n", facts)
    assert "year_window" not in _fired(f"const day = new Date({low}, 0, 1);\n", facts)
    assert "year_window" not in _fired("const wide = width >= 1000;\n", facts)


# -- rules moved to the backend ----------------------------------------------


def test_the_moved_rules_are_read_from_their_owners(facts: Facts) -> None:
    assert {"amount", "description", "date", "account"} <= facts.identity_tokens
    assert {"iva_category", "retention_rate"} <= facts.judged_fields
    assert {"INCOMING", "OUTGOING"} <= facts.directions
    assert "missing_iva_rate" in facts.vocabularies["readiness_reason"]


def test_a_set_of_identity_columns_fails_the_field_route_rule(facts: Facts) -> None:
    source = 'const IDENTITY = new Set(["date", "description", "amount", "account"]);\n'
    assert "field_route" in _fired(source, facts)
    assert "field_route" not in _fired('const WIDE = new Set(["amount", "notes"]);\n', facts)
    assert "field_route" not in _fired('const ORDER = ["date", "description", "amount", "account"];\n', facts)


def test_a_set_of_judged_correction_fields_fails_the_field_route_rule(facts: Facts) -> None:
    first, second, third = sorted(facts.judged_fields)[:3]
    assert "field_route" in _fired(f'const JUDGED = new Set(["{first}", "{second}", "{third}"]);\n', facts)


def test_a_table_of_readiness_reasons_fails_the_vocabulary_rule(facts: Facts) -> None:
    first, second = sorted(facts.vocabularies["readiness_reason"])[:2]
    assert "vocabulary" in _fired(f'const ROUTE = {{ "{first}": "a", "{second}": "b" }};\n', facts)
    assert "vocabulary" in _fired(f'const DERIVES = ["{first}", "{second}"];\n', facts)
    assert "vocabulary" not in _fired(f'const lead = "{first}";\n', facts)


def test_a_record_routing_reasons_to_fields_fails_the_field_route_rule(facts: Facts) -> None:
    first, second = sorted(facts.vocabularies["readiness_reason"])[:2]
    assert "field_route" in _fired(f'const ROUTE = {{ {first}: "a", {second}: "b" }};\n', facts)
    layout = f'const FIX = {{ {first}: {{ preset: "p" }}, {second}: {{ preset: "q" }} }};\n'
    assert "field_route" not in _fired(layout, facts)


def test_a_direction_chosen_by_a_condition_fails_the_direction_rule(facts: Facts) -> None:
    source = 'const flow = (i: Invoice) => i.kind === "issued" ? "INCOMING" : "OUTGOING";\n'
    assert "direction_rule" in _fired(source, facts)


def test_a_direction_tested_in_a_predicate_fails_the_direction_rule(facts: Facts) -> None:
    source = 'const picks = rows.filter((row) => row.direction === "OUTGOING" && !used.has(row.id));\n'
    assert "direction_rule" in _fired(source, facts)
    assert "direction_rule" in _fired('const one = rows.find((r) => "INCOMING" === r.direction);\n', facts)


def test_a_direction_told_apart_to_draw_it_passes(facts: Facts) -> None:
    source = 'const icon = (d: string) => { if (d === "INTERNAL_TRANSFER") return "swap"; return "arrow"; };\n'
    assert "direction_rule" not in _fired(source, facts)
    assert "direction_rule" not in _fired('const word = { IN: "INCOMING" };\n', facts)


def test_a_number_as_a_line_limit_fails_the_text_limit_rule(facts: Facts) -> None:
    assert "text_limit" in _fired("const parsed = parseLine(raw, 64);\n", facts)
    assert "text_limit" in _fired("const name = textField(draft.counterpartyName, 512);\n", facts)
    assert "text_limit" not in _fired("const parsed = parseLine(raw, LINE_LIMIT);\n", facts)
    assert "text_limit" not in _fired('const name = textField(raw, textLimit("name"));\n', facts)
    assert "text_limit" not in _fired("const parsed = parseLine(raw, field.maxLength);\n", facts)


def test_a_moved_rule_brought_back_fails_the_moved_rule_rule(facts: Facts) -> None:
    assert "moved_rule" in _fired("const remainder = splitRemainder(total, others);\n", facts)
    assert "moved_rule" in _fired("export function checkSplit(total, parts) { return parts; }\n", facts)
    assert "moved_rule" not in _fired('const said = "checkSplit";\n', facts)


def test_the_matching_rules_brought_back_fail_the_moved_rule_rule(facts: Facts) -> None:
    assert "moved_rule" in _fired("const owed = settlement(invoice);\n", facts)
    assert "moved_rule" in _fired("export function settlement(invoice) { return invoice.grand_total; }\n", facts)
    assert "moved_rule" in _fired("export function partyName(text) { return text.toLowerCase(); }\n", facts)
    assert "moved_rule" in _fired("const same = sameParty(row.counterparty, invoice.counterparty_name);\n", facts)
    assert "moved_rule" in _fired("const found = reconcile(rows, invoices, actions);\n", facts)
    assert "moved_rule" in _fired("const offered = movementPicker(invoice, rows);\n", facts)
    assert "moved_rule" in _fired("const early = gap >= -EARLY_DAYS;\n", facts)
    assert "moved_rule" in _fired("export const PICK_WINDOW_DAYS = 10;\n", facts)
    assert "moved_rule" in _fired("const near = distance <= TOLERANCE_UNITS;\n", facts)
    assert "moved_rule" in _fired("const named = numberInDescription(row, invoice);\n", facts)


_PLANTED_LEGAL_FORMS = (
    r"const LEGAL_FORMS = /\b(s\.?l\.?u?|s\.?a\.?|s\.?coop|sll|slp|cb|scp)\b\.?/g;"
    "\n"
    'const party = (text: string) => fold(text).replace(LEGAL_FORMS, " ").trim();\n'
    "const differs = party(row.counterparty) !== party(invoice.counterparty_name);\n"
)


def _moved_messages(source: str, facts: Facts) -> str:
    return "\n".join(hit.detail for hit in scan_source(source, facts) if hit.rule == "moved_rule")


def test_a_copy_of_the_legal_form_fold_fails_the_moved_rule_rule_however_it_is_spelled(facts: Facts) -> None:
    assert "moved_rule" in _fired(_PLANTED_LEGAL_FORMS, facts)
    # Each part alone is enough: the name, the fold and its call, and the pattern under any name.
    assert "LEGAL_FORMS" in _moved_messages("const forms = LEGAL_FORMS;\n", facts)
    assert "declared as a function" in _moved_messages("const party = (text: string) => text.trim();\n", facts)
    assert "declared as a function" in _moved_messages("const party = text => text.trim();\n", facts)
    assert "declared as a function" in _moved_messages("const party = function (text) { return text; };\n", facts)
    assert "party is answered" in _moved_messages("const same = party(row.counterparty);\n", facts)
    renamed = r"const FORMS = /\b(sl|sa|slu|cb)\b/gi;" "\n"
    assert "pattern of legal forms" in _moved_messages(renamed, facts)
    spelled = r"const ENDINGS = /(s\.?l\.?u?|s\.?a\.?|s\.?coop)$/;" "\n"
    assert "pattern of legal forms" in _moved_messages(spelled, facts)


def test_a_name_called_party_and_a_pattern_of_other_words_do_not_fail_the_moved_rule_rule(facts: Facts) -> None:
    for source in (
        'const party = correctable("counterparty_name");\n',
        "const party = (picked ? picked.fills : null);\n",
        "const party = row.counterparty || row.description;\n",
        "const sizes = /(sl|sa)/;\n",
        "const words = /(red|green|blue|sl)/;\n",
        r"const digits = /\d+|\s+|\w+/g;" "\n",
    ):
        assert "moved_rule" not in _fired(source, facts), source


def test_the_legal_forms_are_read_from_the_backend(facts: Facts) -> None:
    assert {"sl", "sa", "slu", "scoop", "cb", "scp"} <= facts.legal_forms


def test_the_words_the_matching_rules_share_with_other_names_do_not_fail_the_moved_rule_rule(facts: Facts) -> None:
    served = "const owed = invoice.settlement_amount.decimal;\n"
    member = "type Revision = { settlement: ModeloSettlementSnapshot | null };\n"
    local = 'const partyName = party.typed ?? party.read ?? "";\n'
    said = 'const call = "settlement(";\n'
    for source in (served, member, local, said):
        assert "moved_rule" not in _fired(source, facts), source


def test_invoice_identity_compared_in_the_window_fails_the_moved_rule_rule(facts: Facts) -> None:
    planted = "const same = invoices.find((i) => folded(i.invoice_number) === number);\n"
    assert "moved_rule" in _fired(planted, facts)
    planted = "const same = invoices.find((i) => taxId === i.counterparty_tax_id);\n"
    assert "moved_rule" in _fired(planted, facts)
    assert "moved_rule" in _fired("const copy = duplicateOf(draft, kind, invoices);\n", facts)
    assert "moved_rule" not in _fired("const number = invoice.invoice_number;\n", facts)
    landed = "const saved = invoices.some((i) => i.invoice_number === sent.number);\n"
    assert "moved_rule" not in _fired(landed, facts)


def test_a_split_staged_from_the_windows_own_parts_fails_the_moved_rule_rule(facts: Facts) -> None:
    held = 'const a = { id: x, kind: "split", transactionId: y, children: parts.map(toChild), reason: r };\n'
    read = 'const a = { id: x, kind: "split", transactionId: y, children: answer.children.map(toChild), reason: r };\n'
    assert "moved_rule" in _fired(held, facts)
    assert "moved_rule" not in _fired(read, facts)


# -- clean files and exclusions ----------------------------------------------


def test_a_clean_file_with_one_token_and_a_power_of_ten_passes(facts: Facts) -> None:
    token = sorted(facts.vocabularies["iva_category"])[0]
    source = (
        f'const remap = (code: string) => (code === "{token}" ? "other" : code);\n'
        "const scale = (units: bigint, places: number) => units * 10n ** BigInt(places);\n"
        "const cents = (units: bigint) => units * 100n;\n"
        "export function request(preview: Answer, typed: Typed) {\n"
        "  return { subtotal: preview.line.subtotal.submitted, recargo_amount: typed.recargo.value };\n"
        "}\n"
    )
    assert scan_source(source, facts) == []


def test_comments_and_a_type_member_do_not_fire(facts: Facts) -> None:
    first, second = _two_categories(facts)
    source = (
        f"// {first} and {second} and left.units * right.units\n"
        "interface Wire {\n  subtotal: Decimal;\n  iva_amount: Decimal;\n  grand_total: Decimal;\n}\n"
    )
    assert scan_source(source, facts) == []


def test_a_generated_file_is_excluded_only_at_its_declared_path_with_its_header(
    tmp_path: Path, facts: Facts, outputs: dict[str, tuple[str, ...]]
) -> None:
    assert outputs, "no generator output was read"
    path, headers = sorted(outputs.items())[0]
    first, second = _two_categories(facts)
    body = f'export const ALL = ["{first}", "{second}"];\n'
    genuine = tmp_path / path
    genuine.parent.mkdir(parents=True, exist_ok=True)
    genuine.write_text(headers[0] + "\n\n" + body, encoding="utf-8")
    # The generator's own header, pasted into a handwritten file that is no declared output.
    (tmp_path / "pasted.ts").write_text(headers[0] + "\n\n" + body, encoding="utf-8")
    # A declared output whose opening is no generator's header.
    other = sorted(outputs)[-1]
    assert other != path
    (tmp_path / other).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / other).write_text("// Generated by hand; do not edit.\n\n" + body, encoding="utf-8")
    assert set(scan_tree(tmp_path, facts, outputs)) == {"pasted.ts", other}


def test_the_generated_outputs_are_read_from_the_drivers_that_write_them(outputs: dict[str, tuple[str, ...]]) -> None:
    assert {"shell/ledgerContract.ts", "shell/modeloContract/contracts.ts"} <= set(outputs)
    assert all(path.endswith((".ts", ".tsx", ".mts", ".cts")) for path in outputs)


def test_scan_skips_stories_specs_and_the_dev_tree(
    tmp_path: Path, facts: Facts, outputs: dict[str, tuple[str, ...]]
) -> None:
    body = "export const t = (a: Amount, b: Amount) => a.units * b.units;\n"
    for name in ("a.stories.tsx", "a.spec.ts", "dev/a.ts", "ok/a.ts"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    assert sorted(scan_tree(tmp_path, facts, outputs)) == ["ok/a.ts"]


@pytest.mark.parametrize("suffix", [".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"])
def test_every_module_spelling_is_scanned(
    tmp_path: Path, facts: Facts, outputs: dict[str, tuple[str, ...]], suffix: str
) -> None:
    (tmp_path / f"a{suffix}").write_text("export const t = (a, b) => a.units * b.units;\n", encoding="utf-8")
    assert list(scan_tree(tmp_path, facts, outputs)) == [f"a{suffix}"]


def reached_sources(root: Path) -> list[Path]:
    """The sources the scan reaches under ``root``, refusing a scan that reaches none or reads none."""
    reached = list(window_sources(root))
    assert reached, f"the scan reaches no source under {root}: it would pass without reading the window"
    unread = [path for path in reached if not lex(path.read_text(encoding="utf-8"))]
    assert unread == [], "a source the scan reaches yields no tokens, so no rule can see it"
    return reached


def _eligible_by_walk(root: Path) -> set[str]:
    """Every module source outside ``dev``, stories and specs, found by walking directories."""
    found: set[str] = set()
    for directory, names, files in os.walk(root):
        names[:] = [name for name in names if name != "node_modules"]
        for name in files:
            relative = (Path(directory) / name).relative_to(root)
            if relative.suffix in _EXTENSIONS and relative.parts[0] != "dev" and not _EXCLUDED_NAME.search(name):
                found.add(relative.as_posix())
    return found


def test_the_scan_reaches_every_window_source() -> None:
    reached = {path.relative_to(_SOURCE).as_posix() for path in reached_sources(_SOURCE)}
    assert reached == _eligible_by_walk(_SOURCE)


def test_a_scan_that_reaches_no_source_fails(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("export const t = 1;\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="reaches no source"):
        reached_sources(tmp_path)


def test_a_source_that_yields_no_tokens_fails(tmp_path: Path) -> None:
    (tmp_path / "blank.ts").write_text("", encoding="utf-8")
    with pytest.raises(AssertionError, match="yields no tokens"):
        reached_sources(tmp_path)


def test_the_window_holds_no_tax_data(facts: Facts, outputs: dict[str, tuple[str, ...]]) -> None:
    reached_sources(_SOURCE)
    found = scan_tree(_SOURCE, facts, outputs)
    hit_keys = {(path, hit.rule) for path, hits in found.items() for hit in hits}
    unlisted = sorted(
        f"{path}:{hit.line} [{hit.rule}] {hit.detail}"
        for path, hits in found.items()
        for hit in hits
        if (path, hit.rule) not in _PENDING
    )
    cleared = sorted(
        f"{path} [{rule}]: {reason}" for (path, rule), reason in _PENDING.items() if (path, rule) not in hit_keys
    )
    assert unlisted == [], "tax data or arithmetic in the window"
    assert cleared == [], "a pending entry no longer hits; remove it from _PENDING"

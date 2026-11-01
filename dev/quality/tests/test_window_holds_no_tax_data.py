"""Gate: the desktop window holds no tax data and does no tax arithmetic.

The backend is the only tax engine. The window shows what the ledger serves and
sends what the person typed; a category list, a rate, a figure worked out from
other figures or a rule about which class takes which field belongs to the
backend, and a copy in the window goes stale the day the registry changes.

Four rules scan every TypeScript source under the frontend's ``src`` (stories,
specs and ``src/dev`` excluded; a generated file is excluded only when it opens
with the exact header its generator writes):

``vocabulary``
    Two or more distinct tokens of one served vocabulary appear as string
    literals in one file. One token alone is a remap of a code and passes. The
    vocabularies are read from the owners the ledger's entry-options operation
    reads, on every supported year, plus the rate slots; nothing is listed here.
    A token shorter than three characters (a prorrata sector letter, a premises
    code) is indistinguishable from any short string, so it counts only when two
    of one vocabulary sit in one array literal.
``rates``
    Two or more distinct values from the registry's dated IVA rates, as points
    or as a fraction, sit in one list or table literal, whatever it is named.
``multiplication``
    A product of exact decimals (``a.units * b.units``), a ``BigInt`` product
    where neither factor is a power of ten, or a named multiplying helper such
    as ``timesToCent``. Scaling by a power of ten is how a decimal is aligned,
    not a calculation.
``figures``
    A request literal that sets ``subtotal``, ``iva_amount``, ``retention_amount``
    or ``recargo_amount`` from a computation: arithmetic, a numeric literal, a
    conversion to a number, or a local name that is itself computed. A value
    taken from the preview's answer or the text the person typed passes.

Limits. The scan is lexical. It cannot judge an eligibility rule written as
ordinary conditionals (which class takes which field, which category applies to
which kind), and it does not see arithmetic on plain numbers or a figure
computed in another file. Those are reviewed by hand; the gate does not prove
their absence.

The copies still awaiting removal are named in ``_PENDING``. An entry that no
longer hits fails the test, so the list can only shrink.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest

from cadrumo.application.ledger.entry_options_operation import ledger_entry_options
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.enums import iva_rate_percentage, iva_rate_slots_on
from cadrumo.domain.iva.errors import IvaRateNotFoundError
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRONTEND: Final[Path] = REPO_ROOT / "native/desktop/frontend"
_SOURCE: Final[Path] = _FRONTEND / "src"
_GENERATORS: Final[Path] = _FRONTEND / "scripts"
_EXTENSIONS: Final = frozenset({".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs"})
_EXCLUDED_NAME: Final = re.compile(r"\.(?:stories|spec)\.[^.]+$")

_MIN_TOKEN: Final = 3
_FIGURE_KEYS: Final = frozenset({"subtotal", "iva_amount", "retention_amount", "recargo_amount"})
_RULES: Final = ("vocabulary", "rates", "multiplication", "figures")

#: Copies awaiting removal, keyed by file (relative to ``src``) and rule.
_PENDING: Final[dict[tuple[str, str], str]] = {}


# ---------------------------------------------------------------------------
# What the registry serves
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Facts:
    """The served vocabularies and dated rate values the window must not hold."""

    vocabularies: dict[str, frozenset[str]]
    rates: frozenset[Decimal]


def _year_days(years: list[int]) -> Iterator[date]:
    for year in years:
        for month, day in ((1, 1), (7, 1), (12, 31)):
            yield date(year, month, day)


def read_facts() -> Facts:
    """Read every vocabulary and rate from the pinned authority, on each supported year."""
    vocabularies: dict[str, set[str]] = {}
    rates: set[Decimal] = set()
    with bundled_indexed_authority().operation() as operation:
        days = list(_year_days(sorted(operation.supported_filing_years().years)))
        for day in days:
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
                if fraction:
                    rates.update({fraction.normalize(), (fraction * 100).normalize()})
    return Facts({name: frozenset(tokens) for name, tokens in vocabularies.items()}, frozenset(rates))


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
            push("regex", "/regex/", i)
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
    parent = token.parent
    while parent >= 0 and _literal_like(tokens, parent):
        yield parent
        parent = tokens[parent].parent


def _value(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace("_", "")).normalize()
    except InvalidOperation:
        return None


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


def rate_hits(tokens: list[Token], facts: Facts) -> list[Hit]:
    """A list or table literal made mostly of dated rate values, two or more of them distinct.

    A small number such as 2 or 10 also turns up in a table of widths or levels, so
    the rate values must be at least half of the numbers the literal holds.
    """
    rates: dict[int, dict[Decimal, int]] = {}
    numbers: dict[int, int] = {}
    members: dict[int, int] = {}
    for token in tokens:
        if token.kind not in {"num", "str"} or token.text.endswith("n"):
            continue
        value = _value(token.text)
        if value is None:
            continue
        for bracket in _literal_chain(tokens, token):
            numbers[bracket] = numbers.get(bracket, 0) + 1
            if value in facts.rates:
                members[bracket] = members.get(bracket, 0) + 1
                rates.setdefault(bracket, {}).setdefault(value, token.line)
    hits = [
        Hit("rates", min(seen.values()), "rate values " + ", ".join(sorted(format(v, "f") for v in seen)))
        for bracket, seen in rates.items()
        if len(seen) >= 2 and 2 * members[bracket] >= numbers[bracket]
    ]
    # An enclosing literal repeats its members' hit; one report per line is enough.
    return list({hit.line: hit for hit in hits}.values())


_STOP: Final = frozenset(
    {"+", "-", "*", "/", "%", ",", ";", ")", "]", "}", "?", ":", "=", "==", "===", "!=", "!==", "<", ">"}
)
_STOP |= {"<=", ">=", "&&", "||", "??", "=>", "(", "[", "{"}
_HELPER: Final = re.compile(r"^(?:timesTo\w*|multiplyBy\w*|mulDecimal\w*|\w+ToCent)$")
_POWER_OF_TEN: Final = re.compile(r"^10*n$")


def _right_operand(tokens: list[Token], star: int) -> list[Token]:
    out: list[Token] = []
    depth = 0
    for token in tokens[star + 1 :]:
        if token.text in {"(", "[", "{"} and token.kind == "op":
            depth += 1
        elif token.text in {")", "]", "}"} and token.kind == "op":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and token.kind == "op" and token.text in _STOP:
            if out:
                break
            continue  # a unary sign before the operand
        out.append(token)
    return out


def _left_operand(tokens: list[Token], star: int) -> list[Token]:
    out: list[Token] = []
    depth = 0
    for token in reversed(tokens[:star]):
        if token.kind == "op" and token.text in {")", "]", "}"}:
            depth += 1
        elif token.kind == "op" and token.text in {"(", "[", "{"}:
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and token.kind == "op" and token.text in _STOP and token.text not in {"(", "[", "{"}:
            break
        out.append(token)
    return out[::-1]


def _is_power_of_ten(operand: list[Token], scales: set[str]) -> bool:
    """A power-of-ten literal, alone or as the base of ``**``, or a local name defined as one."""
    if not operand:
        return False
    head = operand[0]
    if head.kind == "num" and _POWER_OF_TEN.match(head.text):
        return len(operand) == 1 or operand[1].text == "**"
    return len(operand) == 1 and head.kind == "id" and head.text in scales


def _bigint_like(operand: list[Token]) -> bool:
    texts = [t.text for t in operand]
    return (
        any(t.kind == "num" and t.text.endswith("n") for t in operand)
        or "BigInt" in texts
        or any(a == "." and b == "units" for a, b in pairwise(texts))
    )


def _scale_names(tokens: list[Token]) -> set[str]:
    """Local names defined only from powers of ten, such as ``const scale = 10n ** BigInt(places)``."""
    scales: set[str] = set()
    for name, span in _declared_spans(tokens):
        literals = [t.text for t in span if t.kind == "num" and t.text.endswith("n")]
        if literals and all(_POWER_OF_TEN.match(text) for text in literals) and not any(t.text == "*" for t in span):
            scales.add(name)
    return scales


def multiplication_hits(tokens: list[Token]) -> list[Hit]:
    """Exact-decimal products and named multiplying helpers."""
    hits: list[Hit] = []
    scales = _scale_names(tokens)
    for index, token in enumerate(tokens):
        if token.kind == "id" and _HELPER.match(token.text):
            hits.append(Hit("multiplication", token.line, f"helper {token.text}"))
        if token.kind != "op" or token.text != "*":
            continue
        left, right = _left_operand(tokens, index), _right_operand(tokens, index)
        if not (_bigint_like(left) or _bigint_like(right)):
            continue
        if _is_power_of_ten(left, scales) or _is_power_of_ten(right, scales):
            continue
        hits.append(Hit("multiplication", token.line, "product of exact decimals"))
    return hits


_COMPUTING_ANYWHERE: Final = frozenset({"toFixed", "units"})
_COMPUTING_GLOBAL: Final = frozenset({"BigInt", "Number", "parseFloat", "parseInt", "Math"})


def _computes(span: list[Token], computed: set[str]) -> bool:
    """Whether the tokens work something out: arithmetic, a conversion to a number, or a computed name."""
    for index, token in enumerate(span):
        member = index > 0 and span[index - 1].text in {".", "?."}
        if token.kind == "id":
            if token.text in _COMPUTING_ANYWHERE or _HELPER.match(token.text):
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


def figure_hits(tokens: list[Token]) -> list[Hit]:
    """A request literal that sets a wire figure from a computation."""
    computed = computed_names(tokens)
    hits: list[Hit] = []
    for index, token in enumerate(tokens):
        if token.text not in _FIGURE_KEYS or token.kind not in {"id", "str"}:
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


def scan_source(source: str, facts: Facts) -> list[Hit]:
    """Run every rule over one file's source."""
    tokens = lex(source)
    return [
        *vocabulary_hits(tokens, facts),
        *rate_hits(tokens, facts),
        *multiplication_hits(tokens),
        *figure_hits(tokens),
    ]


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------


def generated_headers(scripts: Path = _GENERATORS) -> tuple[str, ...]:
    """The opening comment block each generator writes, read from its own header constants."""
    headers: list[str] = []
    for script in sorted(scripts.glob("*.py")):
        for node in ast.parse(script.read_text(encoding="utf-8")).body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and any(isinstance(target, ast.Name) and target.id.endswith("HEADER") for target in node.targets)
            ):
                lines = node.value.value.splitlines()
                headers.append("\n".join(lines[:3]))
    return tuple(headers)


def is_generated(source: str, headers: tuple[str, ...]) -> bool:
    """Whether the file opens with exactly a generator's header."""
    opening = "\n".join(source.replace("\r\n", "\n").splitlines()[:3])
    return opening in headers


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


def scan_tree(root: Path, facts: Facts, headers: tuple[str, ...]) -> dict[str, list[Hit]]:
    """Return the hits of each non-generated source, by path relative to ``root``."""
    found: dict[str, list[Hit]] = {}
    for path in window_sources(root):
        source = path.read_text(encoding="utf-8")
        if is_generated(source, headers):
            continue
        hits = scan_source(source, facts)
        if hits:
            found[path.relative_to(root).as_posix()] = hits
    return found


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def facts() -> Facts:
    return read_facts()


@pytest.fixture(scope="module")
def headers() -> tuple[str, ...]:
    return generated_headers()


def _fired(source: str, facts: Facts) -> set[str]:
    return {hit.rule for hit in scan_source(source, facts)}


def test_the_facts_are_read_from_the_registry_not_listed_here(facts: Facts) -> None:
    assert {"iva_category", "irpf_category", "spending_category", "iva_rate_slot"} <= set(facts.vocabularies)
    assert all(len(members) >= 2 for members in facts.vocabularies.values() if members)
    assert len(facts.rates) >= 4


def test_a_renamed_rate_table_fails_the_rates_rule(facts: Facts) -> None:
    points = sorted(rate for rate in facts.rates if rate >= 1)[:2]
    source = f"export const SOMETHING_ELSE = {{ general: {points[0]}, reduced: {points[1]} }};\n"
    assert "rates" in _fired(source, facts)


def test_a_product_of_exact_decimals_fails_the_multiplication_rule(facts: Facts) -> None:
    source = "export const total = (left: Amount, right: Amount) => left.units * right.units;\n"
    assert "multiplication" in _fired(source, facts)


def test_a_bigint_product_without_a_power_of_ten_fails_the_multiplication_rule(facts: Facts) -> None:
    assert "multiplication" in _fired("const x = BigInt(a) * BigInt(b);\n", facts)
    assert "multiplication" in _fired("const x = timesToCent(a, b);\n", facts)


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


def test_a_list_of_two_iva_categories_fails_the_vocabulary_rule(facts: Facts) -> None:
    first, second = sorted(token for token in facts.vocabularies["iva_category"] if len(token) >= _MIN_TOKEN)[:2]
    source = f'export const OFFERED = ["{first}", "{second}"];\n'
    assert "vocabulary" in _fired(source, facts)


def test_two_short_tokens_count_only_inside_one_list(facts: Facts) -> None:
    letters = sorted(token for token in facts.vocabularies["prorrata_sector_letter"] if len(token) < _MIN_TOKEN)[:2]
    listed = f'const a = ["{letters[0]}", "{letters[1]}"];\n'
    apart = f'const a = "{letters[0]}";\nfunction f() {{ return "{letters[1]}"; }}\n'
    assert "vocabulary" in _fired(listed, facts)
    assert "vocabulary" not in _fired(apart, facts)


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
    first, second = sorted(token for token in facts.vocabularies["iva_category"] if len(token) >= _MIN_TOKEN)[:2]
    source = (
        f"// {first} and {second} and left.units * right.units\n"
        "interface Wire {\n  subtotal: Decimal;\n  iva_amount: Decimal;\n}\n"
    )
    assert scan_source(source, facts) == []


def test_a_generated_file_is_excluded_only_by_its_exact_header(
    tmp_path: Path, facts: Facts, headers: tuple[str, ...]
) -> None:
    assert headers, "no generator header was read"
    first, second = sorted(token for token in facts.vocabularies["iva_category"] if len(token) >= _MIN_TOKEN)[:2]
    body = f'export const ALL = ["{first}", "{second}"];\n'
    (tmp_path / "genuine.ts").write_text(headers[0] + "\n\n" + body, encoding="utf-8")
    (tmp_path / "forged.ts").write_text("// Generated by hand; do not edit.\n\n" + body, encoding="utf-8")
    assert sorted(scan_tree(tmp_path, facts, headers)) == ["forged.ts"]


def test_scan_skips_stories_specs_and_the_dev_tree(tmp_path: Path, facts: Facts, headers: tuple[str, ...]) -> None:
    body = "export const t = (a: Amount, b: Amount) => a.units * b.units;\n"
    for name in ("a.stories.tsx", "a.spec.ts", "dev/a.ts", "ok/a.ts"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    assert sorted(scan_tree(tmp_path, facts, headers)) == ["ok/a.ts"]


def test_the_window_holds_no_tax_data(facts: Facts, headers: tuple[str, ...]) -> None:
    found = scan_tree(_SOURCE, facts, headers)
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

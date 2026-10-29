"""No shipped Cadrumo source defines an AI model.

The agent's provider catalogue is the only source of providers and models.
Cadrumo carries the person's selection and the local program's pins, but no
model name, no model digest, no table of models, no model's size and no
model's licence. This gate reads the shipped sources and refuses each way a
file could define a model again. Every row, in every kind of file, is first
shown to catch a representative defect in an isolated fixture and to pass a
representative clean one, then run against the real tree. No file is excused:
there is no allowance list, and a file that defines a model is repaired or its
definition routed to the agent's catalogue.

Scanned, by kind of file:

- Python: every ``.py`` file under ``src/cadrumo``, ``src/cadrumo_runtime``,
  ``src/cadrumo_mcp``, ``src/cadrumo_client`` and ``src/cadrumo_agent_service``,
  except test directories and the shared test support in ``src/cadrumo/tests``.
- TOML: every ``.toml`` file under ``native/component-pins``.
- Rust: every ``.rs`` file under ``native/application`` and ``native/desktop``,
  tests included, so a fixture names a synthetic model such as
  ``synthetic-text:test`` and never a real one.
- TypeScript: every ``.ts``, ``.tsx``, ``.mts``, ``.mjs`` and ``.js`` file under
  ``native/desktop``, tests and fixtures included.
- Environment template: ``env/.env.example``.

Build output and installed packages (``target``, ``node_modules``, ``dist``,
``build``, ``test-results``) are not source. The bundled corpora, the
documentation and the locale catalogues are not scanned.

Where each row stops:

- Model name. A string constant, not a docstring or comment, that contains a
  model family followed by a version or size (``claude-sonnet``, ``gpt-4``,
  ``gemini-2``, ``qwen3``, ``gemma3``, ``llama3`` ...), the family names
  ``moondream`` and ``llava``, or that is exactly an Ollama tag
  (``name:1.7b``); in a TOML file, the same test on every string value and key;
  in the environment template, on every value. A model named only in a
  docstring or comment passes, and so does a name built at run time from
  parts. The bare provider names ``claude``, ``gemini`` and ``ollama`` are not
  model names and pass.
- Model digest. A string constant containing ``sha256:`` and 64 hexadecimal
  digits, the form of an Ollama manifest digest; in a TOML file, also a
  64-digit hexadecimal value under a key whose name contains ``digest``. A
  bare 64-digit hexadecimal string is not a model digest on its own: the
  registry and filing code spell many content hashes, so it passes.
- Model table. A collection literal with at least two entries that name a
  model: in Python, calls or dicts carrying a string-literal keyword or key
  named ``model_id``, ``model_name``, ``runtime_id`` or ``manifest_digest``; in
  Rust and TypeScript, an array of struct or object literals with such a field
  bound to a string literal; in TOML, an array of tables named ``models``; in
  the environment template, two or more variables whose names end in
  ``MODEL_ID``, ``MODEL_NAME``, ``RUNTIME_ID`` or ``MANIFEST_DIGEST`` and carry
  a value. A single entry, a table whose model names are read from elsewhere,
  and a Rust or TypeScript entry built by a call are not seen.
- Model size. An entry that names a model by one of those keys and also binds
  ``size_bytes``, ``model_size``, ``model_size_bytes``, ``download_size`` or
  ``download_bytes`` to a number literal, even as a single entry; in the
  environment template, a variable whose name has ``MODEL`` in it and ends in
  ``_SIZE``, ``_SIZE_BYTES`` or ``_DOWNLOAD_BYTES`` and carries a number. A size
  read from the catalogue and a size beside a key that names no model are not
  seen.
- Model licence. An entry that names a model by one of those keys and also
  binds ``licence``, ``license``, ``licence_name``, ``license_name``,
  ``licence_spdx``, ``license_spdx`` or ``spdx`` to a string literal; in the
  environment template, a variable with ``MODEL`` and ``LICENCE`` or
  ``LICENSE`` in its name and a value; and, in every kind, a string that names
  a model family beside its licence or terms of use (``Gemma Terms of Use``).
  A licence read from the catalogue, or named only in a comment, is not seen.

Rust and TypeScript are read by a small lexer, not a parser. It takes strings,
raw strings, template literals and numbers, skips comments, character literals
and regular-expression literals, and ends a TypeScript quote that does not
close on its line as a stray apostrophe. Text a parser would call something
other than a string, such as the words of a JSX element, or a slash the lexer
takes for division where a regular expression starts, can hide or invent a
literal on its own line; a field bound through a helper call instead of a
literal is not seen.
"""

from __future__ import annotations

import ast
import os
import re
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Final, cast, override

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class Kind(StrEnum):
    """The kinds of shipped file the gate reads."""

    PYTHON = "python"
    TOML = "toml"
    RUST = "rust"
    TYPESCRIPT = "typescript"
    ENV = "env"


class Row(StrEnum):
    """The ways a file can define a model."""

    NAME = "names a model"
    DIGEST = "spells a model manifest digest"
    TABLE = "defines a table of models"
    SIZE = "states a model's size"
    LICENCE = "states a model's licence"


@dataclass(frozen=True, order=True, slots=True)
class Finding:
    """One place a file defines a model."""

    label: str
    line: int
    row: Row
    detail: str = ""

    @override
    def __str__(self) -> str:
        """Render the finding as ``label:line: what, detail``."""
        where = self.label if self.line == 0 else f"{self.label}:{self.line}"
        return f"{where}: {self.row.value}" + (f" ({self.detail})" if self.detail else "")


_PRODUCT_ROOTS: Final = (
    REPO_ROOT / "src" / "cadrumo",
    REPO_ROOT / "src" / "cadrumo_runtime",
    REPO_ROOT / "src" / "cadrumo_mcp",
    REPO_ROOT / "src" / "cadrumo_client",
    REPO_ROOT / "src" / "cadrumo_agent_service",
)
_TEST_SUPPORT: Final = REPO_ROOT / "src" / "cadrumo" / "tests"
_DATA_ROOT: Final = REPO_ROOT / "native" / "component-pins"
_RUST_ROOTS: Final = (REPO_ROOT / "native" / "application", REPO_ROOT / "native" / "desktop")
_TYPESCRIPT_ROOTS: Final = (REPO_ROOT / "native" / "desktop",)
_TYPESCRIPT_SUFFIXES: Final = frozenset({".ts", ".tsx", ".mts", ".mjs", ".js"})
_ENVIRONMENT_TEMPLATE: Final = REPO_ROOT / "env" / ".env.example"
_NOT_SOURCE: Final = frozenset({"target", "node_modules", "dist", "build", "test-results", "__pycache__"})

_FAMILY_VERSIONED: Final = re.compile(
    r"(?<![a-z0-9])(?:claude-(?:haiku|sonnet|opus|\d)|gpt-?\d|gemini-(?:\d|pro|flash)|qwen-?\d|gemma-?\d|llama-?\d"
    r"|mistral-|mixtral|phi-?\d|deepseek-|smollm|granite-?\d|minicpm|moondream|llava)",
    re.IGNORECASE,
)
_OLLAMA_TAG: Final = re.compile(r"[a-z][a-z0-9._-]*:\d+(?:\.\d+)?[bm]", re.IGNORECASE)
_MANIFEST_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}", re.IGNORECASE)
_BARE_DIGEST: Final = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)
_LICENCE_TEXT: Final = re.compile(
    r"(?<![a-z0-9])(?:llama|gemma|qwen|mistral|mixtral|deepseek|phi|falcon|granite|smollm|minicpm|moondream|llava)"
    r"(?![a-z])[\w .-]{0,24}?\b(?:community licen[cs]e|licen[cs]e|terms of use)\b",
    re.IGNORECASE,
)

_MODEL_KEYS: Final = frozenset({"model_id", "model_name", "runtime_id", "manifest_digest"})
_SIZE_KEYS: Final = frozenset({"size_bytes", "model_size", "model_size_bytes", "download_size", "download_bytes"})
_LICENCE_KEYS: Final = frozenset(
    {"licence", "license", "licence_name", "license_name", "licence_spdx", "license_spdx", "spdx"}
)

type _Binding = str | float
"""What an entry binds a key to when the value is a string or number literal."""


def _is_model_name(text: str) -> bool:
    return bool(_FAMILY_VERSIONED.search(text)) or _OLLAMA_TAG.fullmatch(text.strip()) is not None


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _as_binding(value: object) -> _Binding | None:
    """Return ``value`` when it is a string or number literal, else ``None``."""
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    return None


def _literal_findings(label: str, line: int, text: str) -> list[Finding]:
    """The rows one string literal answers: a name, a digest, a licence."""
    found: list[Finding] = []
    if _is_model_name(text):
        found.append(Finding(label, line, Row.NAME, text[:60]))
    if _MANIFEST_DIGEST.search(text):
        found.append(Finding(label, line, Row.DIGEST))
    if _LICENCE_TEXT.search(text):
        found.append(Finding(label, line, Row.LICENCE, text[:60]))
    return found


def _names_a_model(bindings: Mapping[str, _Binding]) -> bool:
    return any(isinstance(bindings.get(key), str) for key in _MODEL_KEYS)


def _entry_findings(label: str, line: int, bindings: Mapping[str, _Binding]) -> list[Finding]:
    """The size and licence rows of one entry that names a model."""
    if not _names_a_model(bindings):
        return []
    found: list[Finding] = []
    if any(_is_number(bindings.get(key)) for key in _SIZE_KEYS):
        found.append(Finding(label, line, Row.SIZE))
    if any(isinstance(bindings.get(key), str) for key in _LICENCE_KEYS):
        found.append(Finding(label, line, Row.LICENCE))
    return found


def _table_findings(label: str, line: int, naming_entries: int) -> list[Finding]:
    return [Finding(label, line, Row.TABLE)] if naming_entries >= 2 else []


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------


def _docstring_ids(tree: ast.Module) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                found.add(id(first.value))
    return found


def _python_bindings(entry: ast.expr) -> dict[str, _Binding]:
    """The string and number literals a call's keywords or a dict's keys bind."""
    pairs: list[tuple[str, ast.expr]] = []
    if isinstance(entry, ast.Call):
        pairs = [(keyword.arg, keyword.value) for keyword in entry.keywords if keyword.arg is not None]
    elif isinstance(entry, ast.Dict):
        pairs = [
            (key.value, value)
            for key, value in zip(entry.keys, entry.values, strict=True)
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
    bindings: dict[str, _Binding] = {}
    for key, value in pairs:
        literal = _as_binding(value.value) if isinstance(value, ast.Constant) else None
        if literal is not None:
            bindings[key] = literal
    return bindings


def python_findings(label: str, text: str) -> list[Finding]:
    """Name each way one Python module defines a model."""
    tree = ast.parse(text)
    documented = _docstring_ids(tree)
    found: list[Finding] = []
    bound: dict[int, dict[str, _Binding]] = {}

    def bindings_of(entry: ast.expr) -> dict[str, _Binding]:
        if id(entry) not in bound:
            bound[id(entry)] = _python_bindings(entry)
        return bound[id(entry)]

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in documented:
            found.extend(_literal_findings(label, node.lineno, node.value))
        if isinstance(node, ast.Call | ast.Dict):
            found.extend(_entry_findings(label, node.lineno, bindings_of(node)))
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            entries = list(node.elts)
        elif isinstance(node, ast.Dict):
            entries = list(node.values)
        else:
            continue
        found.extend(_table_findings(label, node.lineno, sum(_names_a_model(bindings_of(entry)) for entry in entries)))
    return found


# --------------------------------------------------------------------------
# TOML
# --------------------------------------------------------------------------


def _toml_strings(value: object, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield key, value
    elif isinstance(value, Mapping):
        for child_key, child in value.items():
            yield from _toml_strings(str(child_key), "")
            yield from _toml_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _toml_strings(child, key)


def _toml_tables(value: object) -> Iterator[Mapping[str, object]]:
    if isinstance(value, Mapping):
        # tomllib produces tables with string keys throughout the parsed tree.
        yield cast(Mapping[str, object], value)
        for child in value.values():
            yield from _toml_tables(child)
    elif isinstance(value, list):
        for child in value:
            yield from _toml_tables(child)


def toml_findings(label: str, text: str) -> list[Finding]:
    """Name each way one TOML file defines a model."""
    document = tomllib.loads(text)
    found: list[Finding] = []
    for key, value in _toml_strings(document):
        found.extend(_literal_findings(label, 0, value))
        if "digest" in key.lower() and _BARE_DIGEST.fullmatch(value):
            found.append(Finding(label, 0, Row.DIGEST, key))
    for table in _toml_tables(document):
        bindings = {str(key): literal for key, value in table.items() if (literal := _as_binding(value)) is not None}
        found.extend(_entry_findings(label, 0, bindings))
    models = document.get("models")
    if isinstance(models, list):
        found.extend(_table_findings(label, 0, len(models)))
    return found


# --------------------------------------------------------------------------
# Rust and TypeScript
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Token:
    """One lexical item of a Rust or TypeScript file."""

    kind: str
    text: str
    line: int


_NUMBER: Final = re.compile(r"0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*(?:\.\d[\d_]*)?")
_NAME: Final = re.compile(r"[A-Za-z_$][\w$]*")
_RUST_STRING_START: Final = re.compile(r'(?:b|c)?(?:r(#*))?"')


def _end_of_quoted(text: str, start: int, quote: str, *, multiline: bool) -> int | None:
    """Return the index of the quote that closes the one at ``start``, or ``None`` when none does."""
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index
        if char == "\n" and not multiline:
            return None
        index += 1
    return None


def _end_of_template(text: str, start: int) -> int:
    """Return the index of the backtick that closes the template literal at ``start``."""
    depth = 0
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if depth == 0:
            if char == "`":
                return index
            if text.startswith("${", index):
                depth = 1
                index += 2
                continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "`":
            index = _end_of_template(text, index)
        index += 1
    return len(text)


def _end_of_block_comment(text: str, start: int, *, nested: bool) -> int:
    depth = 1
    index = start + 2
    while index < len(text) and depth:
        if nested and text.startswith("/*", index):
            depth += 1
            index += 2
        elif text.startswith("*/", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


_REGEX_AFTER_NAMES: Final = frozenset(
    {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "await", "yield"}
)
_REGEX_AFTER_PUNCTUATION: Final = "(,=:[!&|?{};+-*%^~"


def _regex_may_start(before: Sequence[Token]) -> bool:
    """Whether a ``/`` after the tokens ``before`` opens a regular expression rather than dividing."""
    if not before:
        return True
    previous = before[-1]
    if previous.kind == "punct":
        arrow = previous.text == ">" and len(before) > 1 and before[-2].text == "="
        return arrow or previous.text in _REGEX_AFTER_PUNCTUATION
    return previous.kind == "name" and previous.text in _REGEX_AFTER_NAMES


def _end_of_regex(text: str, start: int) -> int | None:
    """Return the index after the regular expression at ``start`` and its flags, or ``None`` if its line ends first."""
    index = start + 1
    in_class = False
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "\n":
            return None
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            index += 1
            while index < len(text) and text[index].isalpha():
                index += 1
            return index
        index += 1
    return None


def tokens(text: str, *, rust: bool) -> list[Token]:
    """Lex Rust (``rust`` true) or TypeScript, skipping comments, character literals and regular expressions."""
    found: list[Token] = []
    index, line, size = 0, 1, len(text)
    while index < size:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
        elif char.isspace():
            index += 1
        elif text.startswith("//", index):
            end = text.find("\n", index)
            index = size if end < 0 else end
        elif text.startswith("/*", index):
            end = _end_of_block_comment(text, index, nested=rust)
            line += text.count("\n", index, end)
            index = end
        elif rust and (start := _RUST_STRING_START.match(text, index)):
            hashes = start.group(1)
            if hashes is None:
                end = _end_of_quoted(text, start.end() - 1, '"', multiline=True)
                body_end = size if end is None else end
            else:
                terminator = '"' + hashes
                closing = text.find(terminator, start.end())
                body_end = size if closing < 0 else closing
                end = body_end + len(terminator) - 1
            content = text[start.end() : body_end]
            found.append(Token("string", content, line))
            line += content.count("\n")
            index = size if end is None else end + 1
        elif char == "'" and rust:
            if text.startswith("\\", index + 1):
                closing = text.find("'", index + 3)
                index = size if closing < 0 else closing + 1
            elif text.startswith("'", index + 2):
                index += 3
            else:
                found.append(Token("punct", char, line))
                index += 1
        elif char in "\"'" and not rust:
            end = _end_of_quoted(text, index, char, multiline=False)
            if end is None:
                found.append(Token("punct", char, line))
                index += 1
            else:
                found.append(Token("string", text[index + 1 : end], line))
                index = end + 1
        elif char == "`" and not rust:
            end = _end_of_template(text, index)
            found.append(Token("string", text[index + 1 : end], line))
            line += text.count("\n", index, end)
            index = end + 1
        elif char == "/" and not rust and _regex_may_start(found):
            after = _end_of_regex(text, index)
            if after is None:
                found.append(Token("punct", char, line))
                index += 1
            else:
                index = after
        elif char.isdigit() and (number := _NUMBER.match(text, index)):
            found.append(Token("number", number.group().replace("_", ""), line))
            index = number.end()
        elif name := _NAME.match(text, index):
            found.append(Token("name", name.group(), line))
            index = name.end()
        else:
            found.append(Token("punct", char, line))
            index += 1
    return found


def _matching_brackets(items: Sequence[Token]) -> dict[int, int]:
    """Map each opening bracket's index to the index of its closer."""
    open_at: list[int] = []
    closer: dict[int, int] = {}
    for index, item in enumerate(items):
        if item.kind != "punct":
            continue
        if item.text in "([{":
            open_at.append(index)
        elif item.text in ")]}" and open_at:
            closer[open_at.pop()] = index
    return closer


def _direct(items: Sequence[Token], closer: Mapping[int, int], start: int, end: int) -> list[int]:
    """The indexes strictly inside ``start``..``end`` that are not inside a nested bracket pair."""
    found: list[int] = []
    index = start + 1
    while index < end:
        found.append(index)
        index = closer[index] + 1 if index in closer else index + 1
    return found


def _bound(items: Sequence[Token], direct: Sequence[int]) -> dict[str, _Binding]:
    """The string and number literals a group binds as ``key: literal`` at its own level."""
    bindings: dict[str, _Binding] = {}
    for position in range(len(direct) - 2):
        key, colon, value = (items[direct[position + offset]] for offset in range(3))
        if key.kind not in {"name", "string"} or colon.kind != "punct" or colon.text != ":":
            continue
        if value.kind == "string":
            bindings[key.text] = value.text
        elif value.kind == "number":
            bindings[key.text] = float(value.text) if value.text.replace(".", "", 1).isdigit() else 0.0
    return bindings


def _split_at_commas(items: Sequence[Token], direct: Sequence[int]) -> list[list[int]]:
    parts: list[list[int]] = [[]]
    for index in direct:
        if items[index].kind == "punct" and items[index].text == ",":
            parts.append([])
        else:
            parts[-1].append(index)
    return parts


def source_findings(label: str, text: str, *, rust: bool) -> list[Finding]:
    """Name each way one Rust or TypeScript file defines a model."""
    items = tokens(text, rust=rust)
    closer = _matching_brackets(items)
    found: list[Finding] = []
    for item in items:
        if item.kind == "string":
            found.extend(_literal_findings(label, item.line, item.text))
    for opener, end in closer.items():
        direct = _direct(items, closer, opener, end)
        if items[opener].text == "{":
            found.extend(_entry_findings(label, items[opener].line, _bound(items, direct)))
        elif items[opener].text == "[":
            naming = 0
            for part in _split_at_commas(items, direct):
                body = next((index for index in part if index in closer and items[index].text == "{"), None)
                if body is not None:
                    naming += _names_a_model(_bound(items, _direct(items, closer, body, closer[body])))
            found.extend(_table_findings(label, items[opener].line, naming))
    return found


# --------------------------------------------------------------------------
# Environment template
# --------------------------------------------------------------------------

_ENV_LINE: Final = re.compile(r"^\s*(?:#\s*)?([A-Z][A-Z0-9_]*)=(.*)$")
_ENV_TABLE_NAME: Final = re.compile(r"(?:MODEL_ID|MODEL_NAME|RUNTIME_ID|MANIFEST_DIGEST)$")
_ENV_SIZE_NAME: Final = re.compile(r"MODEL\w*_(?:SIZE|SIZE_BYTES|DOWNLOAD_BYTES)$")
_ENV_LICENCE_NAME: Final = re.compile(r"MODEL\w*LICEN[CS]E|LICEN[CS]E\w*MODEL")


def env_findings(label: str, text: str) -> list[Finding]:
    """Name each way one environment template defines a model."""
    found: list[Finding] = []
    naming = 0
    first_table_line = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        match = _ENV_LINE.match(raw)
        if match is None:
            continue
        name, value = match.group(1), match.group(2).strip().strip("\"'")
        if not value:
            continue
        found.extend(_literal_findings(label, number, value))
        if _ENV_TABLE_NAME.search(name):
            naming += 1
            first_table_line = first_table_line or number
        if _ENV_SIZE_NAME.search(name) and _NUMBER.fullmatch(value):
            found.append(Finding(label, number, Row.SIZE, name))
        if _ENV_LICENCE_NAME.search(name):
            found.append(Finding(label, number, Row.LICENCE, name))
    found.extend(_table_findings(label, first_table_line, naming))
    return found


def findings(kind: Kind, label: str, text: str) -> list[Finding]:
    """Name each way one file of ``kind`` defines a model."""
    match kind:
        case Kind.PYTHON:
            return python_findings(label, text)
        case Kind.TOML:
            return toml_findings(label, text)
        case Kind.RUST:
            return source_findings(label, text, rust=True)
        case Kind.TYPESCRIPT:
            return source_findings(label, text, rust=False)
        case Kind.ENV:
            return env_findings(label, text)


# --------------------------------------------------------------------------
# The real tree
# --------------------------------------------------------------------------


def _product_python_files() -> Iterator[Path]:
    for root in _PRODUCT_ROOTS:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT)
            if "tests" in relative.parts or "__pycache__" in relative.parts or path.is_relative_to(_TEST_SUPPORT):
                continue
            yield path


def _native_files(roots: Sequence[Path], suffixes: frozenset[str]) -> Iterator[Path]:
    for root in roots:
        for directory, subdirectories, names in os.walk(root):
            subdirectories[:] = sorted(name for name in subdirectories if name not in _NOT_SOURCE)
            for name in sorted(names):
                if Path(name).suffix in suffixes:
                    yield Path(directory) / name


def _shipped_files() -> Iterator[tuple[Kind, Path]]:
    for path in _product_python_files():
        yield Kind.PYTHON, path
    for path in sorted(_DATA_ROOT.glob("*.toml")):
        yield Kind.TOML, path
    for path in _native_files(_RUST_ROOTS, frozenset({".rs"})):
        yield Kind.RUST, path
    for path in _native_files(_TYPESCRIPT_ROOTS, _TYPESCRIPT_SUFFIXES):
        yield Kind.TYPESCRIPT, path
    yield Kind.ENV, _ENVIRONMENT_TEMPLATE


@cache
def _census() -> tuple[Mapping[Kind, int], tuple[Finding, ...]]:
    scanned = dict.fromkeys(Kind, 0)
    offenders: list[Finding] = []
    for kind, path in _shipped_files():
        scanned[kind] += 1
        relative = path.relative_to(REPO_ROOT).as_posix()
        offenders.extend(findings(kind, relative, path.read_text(encoding="utf-8")))
    return scanned, tuple(offenders)


# --------------------------------------------------------------------------
# Each row catches a representative defect and passes a clean file, in every kind
# --------------------------------------------------------------------------

_DIGEST: Final = "ab" * 32
_HASH: Final = "cd" * 32

_FIXTURES: Final[Mapping[tuple[Kind, Row], tuple[str, str]]] = {
    # name: (defect, clean)
    (Kind.PYTHON, Row.NAME): (
        'DEFAULT = "claude-sonnet-99"\nLOCAL = "qwen99-vl:2b"\nTAG = "widget:7b"\n',
        '"""Reads claude-sonnet-99 and qwen99-vl:2b from the catalogue."""\n\n'
        'PROVIDER = "claude"\nRUNTIME = "ollama"\nSPEED = "10:30"\nSELECTED = lookup(role)\n',
    ),
    (Kind.TOML, Row.NAME): (
        '[roles]\nvision = "gemma99:4b"\n',
        '[program]\nname = "ollama"\nversion = "0.40.10"\n',
    ),
    (Kind.RUST, Row.NAME): (
        'const DEFAULT: &str = "qwen99-vl:2b";\nfn raw() -> &\'static str { r#"widget:7b"# }\n',
        '/// Reads claude-sonnet-99 from the catalogue.\n// and qwen99-vl:2b\nconst P: &str = "ollama";\n'
        'const MODEL: &str = "synthetic-text:test";\nfn quote() -> char { \'"\' }\n',
    ),
    (Kind.TYPESCRIPT, Row.NAME): (
        'export const DEFAULT = "gemma99:4b";\nexport const LOCAL = `llama99.2:3b`;\n',
        '// claude-sonnet-99 and qwen99-vl:2b\n/* gpt-99 */\nexport const P = "claude";\n'
        'export const MODEL = "synthetic-text:test";\nconst note = "it\'s";\n',
    ),
    (Kind.ENV, Row.NAME): (
        "CADRUMO_READER=qwen99-vl:2b\n# CADRUMO_TEXT=widget:7b\n",
        "# The reader is chosen in the desktop app, for example qwen99-vl:2b.\n"
        "CADRUMO_PROVIDER=ollama\nCADRUMO_READER=\n",
    ),
    # digest
    (Kind.PYTHON, Row.DIGEST): (f'PIN = "sha256:{_DIGEST}"\n', f'CONTENT_HASH = "{_HASH}"\n'),
    (Kind.TOML, Row.DIGEST): (
        f'[pin]\nmanifest_digest = "{_DIGEST}"\n',
        f'[source]\nchecksum = "{_HASH}"\n',
    ),
    (Kind.RUST, Row.DIGEST): (
        f'const PIN: &str = "sha256:{_DIGEST}";\n',
        f'const CONTENT_HASH: &str = "{_HASH}";\n// sha256:{_DIGEST}\n',
    ),
    (Kind.TYPESCRIPT, Row.DIGEST): (
        f'export const PIN = "sha256:{_DIGEST}";\n',
        f'export const CONTENT_HASH = "{_HASH}";\n// sha256:{_DIGEST}\n',
    ),
    (Kind.ENV, Row.DIGEST): (f"CADRUMO_PIN=sha256:{_DIGEST}\n", f"CADRUMO_CHECKSUM={_HASH}\n"),
    # table
    (Kind.PYTHON, Row.TABLE): (
        'TABLE = (\n    Entry(model_id="alpha", tier=1),\n    Entry(model_id="beta", tier=2),\n)\n'
        'ROWS = [{"runtime_id": "alpha", "tier": 1}, {"runtime_id": "beta", "tier": 2}]\n',
        'ONE = (Entry(model_id="alpha"),)\n'
        "COMPUTED = tuple(Entry(model_id=name) for name in names)\n"
        "OTHER = (Entry(model_id=a), Entry(model_id=b))\n",
    ),
    (Kind.TOML, Row.TABLE): ("[[models]]\ntier = 1\n\n[[models]]\ntier = 2\n", "[[models]]\ntier = 1\n"),
    (Kind.RUST, Row.TABLE): (
        'const TABLE: [Entry; 2] = [Entry { model_id: "alpha", tier: 1 }, Entry { model_id: "beta", tier: 2 }];\n',
        'const ONE: [Entry; 1] = [Entry { model_id: "alpha", tier: 1 }];\n'
        "const BUILT: [Entry; 2] = [Entry::new(a), Entry::new(b)];\n"
        'const UNNAMED: [Entry; 2] = [Entry { id: "alpha" }, Entry { id: "beta" }];\n',
    ),
    (Kind.TYPESCRIPT, Row.TABLE): (
        'export const TABLE = [{ model_id: "alpha", tier: 1 }, { "runtime_id": "beta", tier: 2 }];\n'
        'export const MORE = [{ model_name: "a" }, { manifest_digest: "b" }];\n',
        'export const ONE = [{ model_id: "alpha" }];\n'
        "export const READ = [{ model_id: first }, { model_id: second }];\n",
    ),
    (Kind.ENV, Row.TABLE): (
        "CADRUMO_ONE_MODEL_ID=alpha\nCADRUMO_TWO_MODEL_ID=beta\n",
        "CADRUMO_ONE_MODEL_ID=alpha\nCADRUMO_TWO_MODEL_ID=\nCADRUMO_OLLAMA_MODELS_DIR=models\n",
    ),
    # size
    (Kind.PYTHON, Row.SIZE): (
        'ENTRY = Entry(model_id="alpha", size_bytes=123)\nRAW = {"model_name": "beta", "download_bytes": 4.5}\n',
        'ENTRY = Entry(model_id="alpha", size_bytes=size)\nOTHER = Entry(name="alpha", size_bytes=123)\n'
        'FLAG = Entry(model_id="alpha", size_bytes=True)\n',
    ),
    (Kind.TOML, Row.SIZE): (
        '[model]\nmodel_id = "alpha"\nsize_bytes = 123\n',
        '[model]\nname = "alpha"\nsize_bytes = 123\n\n[floor]\nsize_bytes = 5\n',
    ),
    (Kind.RUST, Row.SIZE): (
        'const ENTRY: Entry = Entry { model_name: "alpha", size_bytes: 1_234 };\n',
        'const ENTRY: Entry = Entry { model_name: "alpha", size_bytes };\n'
        'const OTHER: Entry = Entry { name: "alpha", size_bytes: 1_234 };\n',
    ),
    (Kind.TYPESCRIPT, Row.SIZE): (
        'export const ENTRY = { model_id: "alpha", size_bytes: 1234 };\n',
        'export const ENTRY = { model_id: "alpha", size_bytes: size };\n'
        'export const OTHER = { name: "alpha", size_bytes: 1234 };\n',
    ),
    (Kind.ENV, Row.SIZE): (
        "CADRUMO_LLM_MODEL_SIZE_BYTES=1234\n# CADRUMO_READER_MODEL_SIZE=5\n",
        "CADRUMO_LOG_FILE_MAX_BYTES=10485760\nCADRUMO_LLM_MODEL_SIZE_BYTES=\n",
    ),
    # licence
    (Kind.PYTHON, Row.LICENCE): (
        'ENTRY = Entry(model_id="alpha", licence="acme-open")\nTERMS = "Gemma Terms of Use"\n',
        '"""Shows the Gemma Terms of Use the catalogue states."""\n\n'
        'ENTRY = Entry(name="alpha", licence="acme-open")\nOWN = Entry(model_id="alpha", licence=chosen)\n',
    ),
    (Kind.TOML, Row.LICENCE): (
        '[model]\nmodel_id = "alpha"\nlicence = "acme-open"\n\n[terms]\ntext = "Llama 3 Community License"\n',
        '[dependency]\nname = "alpha"\nlicence = "acme-open"\n',
    ),
    (Kind.RUST, Row.LICENCE): (
        'const ENTRY: Entry = Entry { model_id: "alpha", spdx: "acme-open" };\n'
        'const TERMS: &str = "Qwen License Agreement";\n',
        'const ENTRY: Entry = Entry { name: "alpha", spdx: "acme-open" };\n// Gemma Terms of Use\n',
    ),
    (Kind.TYPESCRIPT, Row.LICENCE): (
        'export const ENTRY = { model_id: "alpha", license: "acme-open" };\n'
        'export const TERMS = "Gemma Terms of Use";\n',
        'export const ENTRY = { name: "alpha", license: "acme-open" };\n// Gemma Terms of Use\n',
    ),
    (Kind.ENV, Row.LICENCE): (
        "CADRUMO_READER_MODEL_LICENCE=acme-open\n# CADRUMO_MODEL_LICENSE=acme-open\n",
        "CADRUMO_READER_MODEL_LICENCE=\nCADRUMO_PROGRAM_LICENCE=acme-open\n",
    ),
}


def test_every_row_has_a_fixture_in_every_kind() -> None:
    assert set(_FIXTURES) == {(kind, row) for kind in Kind for row in Row}


@pytest.mark.parametrize(("kind", "row"), sorted(_FIXTURES), ids=lambda item: item.value)
def test_each_row_catches_its_defect_and_nothing_else(kind: Kind, row: Row) -> None:
    defect, _ = _FIXTURES[kind, row]
    found = findings(kind, "fixture", defect)
    assert found, f"the {row.value} row of the {kind.value} scan missed its defect"
    assert {item.row for item in found} == {row}, [str(item) for item in found]


@pytest.mark.parametrize(("kind", "row"), sorted(_FIXTURES), ids=lambda item: item.value)
def test_each_row_passes_its_clean_file(kind: Kind, row: Row) -> None:
    _, clean = _FIXTURES[kind, row]
    assert findings(kind, "fixture", clean) == []


def test_each_defect_is_reported_where_it_is() -> None:
    assert [item.line for item in findings(Kind.PYTHON, "fixture", 'ONE = 1\nPIN = "sha256:' + _DIGEST + '"\n')] == [2]
    assert [
        item.line for item in findings(Kind.RUST, "fixture", '// one\n/* two\nthree */\nconst PIN: &str = "gpt-99";\n')
    ] == [4]
    assert [item.line for item in findings(Kind.TYPESCRIPT, "fixture", 'const a = `x\ny`;\nconst b = "gpt-99";\n')] == [
        3
    ]
    assert [item.line for item in findings(Kind.ENV, "fixture", "A=1\nCADRUMO_X=gpt-99\n")] == [2]


def test_the_lexer_keeps_a_quote_in_prose_from_hiding_the_next_literal() -> None:
    typescript = "const prose = `it's`;\nconst jsx = <p>Don't</p>;\nconst name = \"gpt-99\";\n"
    rust = "fn f<'a>(x: &'a str) -> char { 'x' }\nconst NAME: &str = \"gpt-99\";\n"
    expression = (
        'const cell = /[",\\r\\n]/.test(text) ? `"${text.replace(/"/g, \'""\')}"` : text;\n'
        'const share = total / count;\nconst name = "gpt-99";\n'
    )
    assert [item.line for item in findings(Kind.TYPESCRIPT, "fixture", typescript)] == [3]
    assert [item.line for item in findings(Kind.TYPESCRIPT, "fixture", expression)] == [3]
    assert [item.line for item in findings(Kind.RUST, "fixture", rust)] == [2]


def test_a_python_licence_text_in_a_docstring_passes_but_the_same_literal_does_not() -> None:
    assert findings(Kind.PYTHON, "fixture", '"""Gemma Terms of Use."""\n') == []
    assert [item.row for item in findings(Kind.PYTHON, "fixture", 'TERMS = "Gemma Terms of Use"\n')] == [Row.LICENCE]


# --------------------------------------------------------------------------
# The real shipped sources
# --------------------------------------------------------------------------


def test_the_census_reads_every_kind_of_shipped_source() -> None:
    scanned, _ = _census()
    assert scanned[Kind.PYTHON] > 2000, f"the census read only {scanned[Kind.PYTHON]} Python files"
    assert (_DATA_ROOT / "local_ai_program.toml").is_file(), "the census missed the program pin data"
    assert scanned[Kind.TOML] >= 1
    assert scanned[Kind.RUST] > 100, f"the census read only {scanned[Kind.RUST]} Rust files"
    assert scanned[Kind.TYPESCRIPT] > 300, f"the census read only {scanned[Kind.TYPESCRIPT]} TypeScript files"
    assert _ENVIRONMENT_TEMPLATE.is_file()
    assert scanned[Kind.ENV] == 1


def test_no_shipped_source_defines_a_model() -> None:
    _, offenders = _census()
    assert not offenders, "shipped files define a model; delete it or route it to the agent's catalogue:\n" + "\n".join(
        str(item) for item in offenders
    )

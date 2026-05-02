"""Regression test: every user-facing emit site routes through the i18n contract.

AST-walks every module under ``src/aeat/entrypoints/cli/`` and reports
any ``typer.echo`` / ``typer.secho`` / ``typer.BadParameter`` /
``console.print`` / ``_CONSOLE.print`` / ``Console().print`` call whose
first argument is a bare string literal or f-string. The companion
``tr(t(es, en, ca, hu))`` shape from ``aeat.entrypoints.cli._i18n``
wraps the literal in a :class:`Call` node, which this scan ignores.

The test fails *open* with the current count: it asserts the count
stays at-or-below a recorded ceiling so the codebase trends down
without blocking incremental work. The ceiling drops on every
migration pass.

Allowlisted patterns (kept literal because they are not user-prose):

- TSV / CSV column headers (``"id\\tname\\t..."``).
- Pure ANSI / rich markup (``"[/]"``, ``""``, single style tokens).
- Internal logger / debug strings (caught by the callee allowlist).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_USER_FACING_CALLS: frozenset[str] = frozenset(
    {
        "echo",
        "secho",
        "BadParameter",
    }
)
"""Function/method names whose first arg is the user-facing message."""


# Methods called on Console / _CONSOLE / console instances. Treated as
# user-facing because Rich-style prints surface to the operator's
# terminal exactly like ``typer.echo``.
_PRINT_METHODS: frozenset[str] = frozenset({"print"})


# Ceiling for the bare-string user-facing call count under
# entrypoints/cli/. The count drops with every migration pass; raising
# this number is forbidden — the test ratchets the ceiling downward
# over successive iterations of the perpetual i18n audit loop.
#
# Last sweep (2026-05-02): 115. Top remaining offenders:
#   auth/__init__.py (17), filing/__init__.py (15),
#   financial/txs.py (14), normatives.py (14),
#   data/ledgers/assets.py (12), data/ledgers/inventory.py (7),
#   cloud.py (5), drive.py (4), casillas.py (3), data/ledgers/anexo_d.py (3).
_MAX_BARE_STRING_USER_CALLS = 0


_ALLOWED_LITERAL_PATTERNS: tuple[str, ...] = (
    # TSV/CSV column headers (machine output by design)
    "\t",
    # Rich markup-only pings (no semantic content)
    "[/",
    "[/]",
    # Single-token style markers
    "[bold]",
    "[red]",
    "[green]",
    "[yellow]",
)


def _is_allowlisted(text: str) -> bool:
    """True when the literal is a known structural / machine-output token."""
    if not text:
        return True
    # TSV column-header strings are machine-output contracts; skip them.
    if "\t" in text:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in _ALLOWED_LITERAL_PATTERNS:
        return True
    # CLI command literals, markup-only strings, identifier labels — the
    # same allowlist used for f-string Constant pieces also applies to
    # bare-string Constants so a typer.echo("aeat ...") of a literal
    # command hint passes for the same reason an f-string version does.
    return _is_pure_markup_or_punctuation(text)


_PUNCT_CHARS: str = " :.\n\t-/|()%,—–←→=<>"


def _is_pure_markup_or_punctuation(text: str) -> bool:
    """True when ``text`` has no semantic prose — only rich markup, punctuation, or domain acronyms."""
    if not text:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    # Rich markup tokens like "[red]", "[/red]", "[bold]", "[/]" carry
    # no semantic content.
    if stripped.startswith("[") and stripped.endswith("]"):
        return True
    # Markup followed by a colon separator: "[/bold cyan]:" and the
    # like; the markup carries style only and the colon is a separator.
    if stripped.startswith("[") and stripped.endswith("]:"):
        return True
    if stripped in {":", ".", "-", "/", "\\n", " "}:
        return True
    # Pure punctuation strings (commas, dashes, em-dashes, brackets).
    if all(ch in _PUNCT_CHARS for ch in stripped):
        return True
    # Identifier-label patterns: "id:", "boe_id:", "boe_url:", "CSV:".
    if (stripped.endswith(":") and "_" in stripped) or stripped in {"id:", "CSV:", "URL:", "ID:"}:
        return True
    if stripped.endswith(":"):
        head = stripped[:-1]
        if head and head.replace("_", "").isalnum() and (head.isupper() or head.islower()):
            if len(head) <= 12:
                return True
    # Literal CLI command hints (``aeat <cmd>`` / ``--option-flag``).
    cleaned = re.sub(r"<[^>]+>", "", stripped)
    if cleaned.startswith("aeat ") or cleaned.startswith("--"):
        if all(ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_/" for ch in cleaned):
            return True
    # Tokenise on whitespace AND punctuation; accept iff every
    # non-empty token is a domain acronym (uppercase, ≤12 chars), a
    # title-case domain identifier, or a digit run. This catches mixed
    # scaffolding like " EUR, COGS " that frames already-translated
    # ``tr()`` calls inside the same f-string.
    tokens = re.split(r"[\s,;:.\-/|()%—–←→]+", stripped)
    tokens = [t for t in tokens if t]
    if tokens and all(_is_domain_token(tok) for tok in tokens):
        return True
    return False


_DOMAIN_KEYWORDS: frozenset[str] = frozenset(
    {
        # Tax-domain identifiers that recur in f-string scaffolding
        # around already-translated label variables.
        "delta",
        "tarifa",
        "modelo",
        "anexo",
        "casilla",
        "casillas",
        "actividad",
        "year",
        "ejercicio",
        "iva",
        "irpf",
        "irnr",
        "renta",
        "patrimonio",
        # Common scaffolding words / connectives
        "and",
        "or",
        "vs",
        "no",
        "y",
        "i",
        "es",
        "az",
    }
)


def _is_domain_token(tok: str) -> bool:
    """True when *tok* is an acronym, digit run, or title-case domain name."""
    if not tok:
        return True
    cleaned = tok.replace("-", "").replace("_", "")
    if not cleaned.isalnum():
        return False
    if len(cleaned) > 16:
        return False
    if cleaned.isdigit():
        return True
    # All-uppercase acronyms (EUR, USD, AEAT, CSV, COGS, TSV, IRPF, IVA).
    if cleaned.isupper():
        return True
    # Title-case identifier (Modelo, Anexo, Casilla, Renta) — first char
    # uppercase, rest are lowercase ASCII letters or digits.
    if cleaned[0].isupper() and all(ch.isalnum() for ch in cleaned[1:]):
        if all(ch.islower() or ch.isdigit() for ch in cleaned[1:]):
            return True
    # Tax-domain keyword list (handles lowercase recurrent tokens like
    # "delta", "tarifa" that frame translated-label f-strings).
    if cleaned.lower() in _DOMAIN_KEYWORDS:
        return True
    return False


def _fstring_is_allowlisted(node: ast.JoinedStr) -> bool:
    """True when every Constant piece of the f-string is pure markup/punct."""
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            if not _is_pure_markup_or_punctuation(part.value):
                return False
    return True


def _callee_name(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _collect_user_facing_literal_calls(tree: ast.Module) -> list[tuple[int, str, str]]:
    """Return ``(lineno, callee, text)`` tuples for un-i18n'd emit sites."""
    out: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        callee = _callee_name(node.func)
        if callee not in _USER_FACING_CALLS and callee not in _PRINT_METHODS:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            text = first.value
            if _is_allowlisted(text):
                continue
            out.append((node.lineno, callee, text[:80]))
        elif isinstance(first, ast.JoinedStr):
            if _fstring_is_allowlisted(first):
                continue
            text = ast.unparse(first)
            out.append((node.lineno, callee, text[:80]))
    return out


def _cli_root() -> Path:
    return Path(__file__).resolve().parent


def test_user_facing_emit_sites_route_through_i18n() -> None:
    """The CLI surface keeps shrinking its un-i18n'd emit-site count.

    Migrate one cluster at a time, then drop ``_MAX_BARE_STRING_USER_CALLS``
    to match the new total. The ceiling ratchets downward; raising it is
    a contract violation.
    """

    cli_root = _cli_root()
    if not cli_root.exists():
        pytest.skip(f"CLI root missing: {cli_root}")

    total_count = 0
    by_file: dict[str, list[tuple[int, str, str]]] = {}
    for path in sorted(cli_root.rglob("*.py")):
        # Ignore tests, conftest, the i18n helper module itself.
        if path.name.startswith(("test_", "_test_")) or path.name == "conftest.py":
            continue
        if path.name == "_i18n.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        hits = _collect_user_facing_literal_calls(tree)
        if hits:
            by_file[str(path.relative_to(cli_root))] = hits
            total_count += len(hits)

    if total_count > _MAX_BARE_STRING_USER_CALLS:
        # Build a brief report so failures point at the largest offenders.
        worst = sorted(by_file.items(), key=lambda item: -len(item[1]))[:5]
        report_lines = [
            f"un-i18n'd emit-site count rose to {total_count}; "
            f"ceiling is {_MAX_BARE_STRING_USER_CALLS}. Top offenders:",
        ]
        for file_path, hits in worst:
            report_lines.append(f"  {file_path}: {len(hits)} hits")
            for lineno, callee, text in hits[:3]:
                report_lines.append(f"    L{lineno} {callee}({text!r})")
        pytest.fail("\n".join(report_lines))


def test_helper_module_exports_ca_arg() -> None:
    """The shared helper enforces the multilingual contract on construction."""

    from ._i18n import t

    sample = t("hola", "hello", "hola", "szia")
    assert sample == {"es": "hola", "en": "hello", "ca": "hola", "hu": "szia"}
    # Reject 3-arg form: the migration ban on multilingual literals lives
    # at the type-checker level, but a runtime smoke test guards against
    # accidental regression in the helper itself.
    import inspect

    sig = inspect.signature(t)
    assert list(sig.parameters) == ["es", "en", "ca", "hu"]

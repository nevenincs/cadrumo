"""Project-wide i18n placeholder parity validator.

Walks every ``tr(literal_key, kwarg=...)`` call site in the production
source tree via AST and cross-checks the supplied kwargs against the
``%{name}`` and ``{name}`` placeholder tokens present in the canonical
Spanish locale value for that key.

Three failure axes are checked:

ORPHAN
    The locale value declares a placeholder token (``%{foo}`` or
    ``{foo}``) but no ``tr()`` call site for that key ever supplies a
    matching kwarg. The placeholder will survive interpolation and the
    operator will read a half-rendered string.

SURPLUS
    A ``tr()`` call site supplies a kwarg that has no corresponding
    placeholder in the locale value. The kwarg is silently ignored by
    ``_interpolate``; the call site author probably misnamed a kwarg or
    the locale value lost a placeholder without the call site being
    updated.

SHADOW
    Multiple call sites for the same key supply *different* non-empty
    kwarg sets. One rendering path produces the intended output; the
    other(s) silently drop or over-supply tokens. All call sites for a
    given key must supply an identical kwarg set (or all supply no
    kwargs).

Dynamic call sites (keys built from f-strings or concatenation) are
skipped; only call sites where the first argument is a string literal
are checked.

The test is expected to fail on first landing. Each failure entry names
the key, axis, and offending token/kwarg so follow-up remediation can
target exactly the right locale values and call sites to fix.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from ... import scan_directory
from .. import extract_placeholders

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = Path(__file__).parent.parent.parent.parent  # src/cadrumo
_LOCALES_DIR = _SRC_ROOT / "locales"
_CANONICAL_LOCALE = _LOCALES_DIR / "es"

# There is no skip list. The one that existed was keyed by bare file STEM, so
# it matched by name anywhere in the tree: "conftest" silently exempted 23
# modules, and "manager" would have pre-authorised any future manager.py in any
# package -- the inheriting-exemption hole, in a list instead of a class
# hierarchy. It was also entirely redundant: none of the modules it skipped
# carried a literal tr() call at all, and one entry ("test_parity") duplicated
# the startswith("test_") filter below. Removing it left the collected call-site
# count identical.

# (key, token) pairs whose ``{name}`` tokens are intentionally passed THROUGH
# tr() to a downstream formatter rather than supplied by the tr() call site,
# so they are NOT orphans. ``_interpolate`` fails closed on an unsupplied
# ``{name}`` (its ``str.format`` pass raises ``KeyError`` and returns the
# pre-format string), leaving the token intact for the downstream formatter.
# ``cli.help.try_for_help`` routes Typer's RICH_HELP through tr() for
# localisation while preserving Typer's own ``{command_path}`` /
# ``{help_option}`` positional tokens, which Typer ``.format()``s itself when
# it renders the help footer. Verified: the footer renders fully at runtime
# with both tokens filled by Typer. These are localised-prose surfaces
# with a downstream ``.format()`` owner, not half-rendered operator strings.
_DOWNSTREAM_FORMAT_PASSTHROUGH: frozenset[tuple[str, str]] = frozenset(
    {
        ("cli.help.try_for_help", "command_path"),
        ("cli.help.try_for_help", "help_option"),
    }
)


def _flatten_locale(data: object, prefix: str = "") -> dict[str, str]:
    """Recursively flatten a nested locale YAML dict to dotted-key → value."""
    if not isinstance(data, dict):
        return {}
    result: dict[str, str] = {}
    for k, v in data.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            result.update(_flatten_locale(v, path))
        else:
            result[path] = str(v)
    return result


def _collect_tr_call_sites(src_root: Path) -> dict[str, list[frozenset[str]]]:
    """Walk ``src_root`` for ``tr(literal_key, **literal_kwargs)`` call sites.

    Returns a mapping of locale key → list of kwarg-name sets, one entry
    per call site. Only call sites whose first argument is a string
    literal are collected; dynamic keys (f-strings, concatenations) are
    silently skipped because they cannot be resolved statically.

    The ``locale`` and ``default`` meta-kwargs are excluded from the
    kwarg set; they are not interpolation placeholders.
    """
    calls: dict[str, list[frozenset[str]]] = defaultdict(list)
    for module_path in scan_directory(src_root, pattern="*.py", recursive=True):
        if module_path.stem.startswith("test_"):
            continue
        try:
            source = module_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(module_path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name) or func.id != "tr":
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            key = node.args[0].value
            if not isinstance(key, str):
                continue
            kws = frozenset(
                kw.arg for kw in node.keywords if kw.arg not in {"locale", "default"} and kw.arg is not None
            )
            calls[key].append(kws)
    return dict(calls)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def canonical_locale() -> dict[str, str]:
    """Flat dotted-key → value mapping from the canonical Spanish locale."""
    result: dict[str, str] = {}
    if _CANONICAL_LOCALE.is_dir():
        for shard in _CANONICAL_LOCALE.rglob("*.yml"):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8"))
            result.update(_flatten_locale(raw or {}))
    elif _CANONICAL_LOCALE.is_file():
        raw = yaml.safe_load(_CANONICAL_LOCALE.read_text(encoding="utf-8"))
        result.update(_flatten_locale(raw or {}))
    return result


@pytest.fixture(scope="module")
def tr_call_sites() -> dict[str, list[frozenset[str]]]:
    """All statically-resolvable ``tr()`` call sites in the production tree."""
    return _collect_tr_call_sites(_SRC_ROOT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_orphan_placeholder_tokens(
    canonical_locale: dict[str, str],
    tr_call_sites: dict[str, list[frozenset[str]]],
) -> None:
    """Every placeholder token in a locale value is supplied by every call site.

    An ORPHAN token means the operator will see a half-rendered string:
    the template declares ``%{name}`` or ``{name}`` but no call site ever
    fills it in.  Fix by either:
    - updating the locale value to remove the unused placeholder, or
    - updating the call site(s) to supply the missing kwarg.
    """
    findings: list[str] = []
    for key, call_kwargs_list in sorted(tr_call_sites.items()):
        if key not in canonical_locale:
            continue
        locale_val = canonical_locale[key]
        required = extract_placeholders(locale_val)
        if not required:
            continue
        all_supplied = frozenset().union(*call_kwargs_list)
        for token in sorted(required - all_supplied):
            if (key, token) in _DOWNSTREAM_FORMAT_PASSTHROUGH:
                continue
            findings.append(f"ORPHAN  key={key!r}  token={token!r}  locale={locale_val[:80]!r}")
    if findings:
        formatted = "\n  ".join(findings)
        pytest.fail(
            f"{len(findings)} ORPHAN placeholder(s) detected — "
            f"locale tokens never supplied by any tr() call site:\n  {formatted}",
        )


def test_no_surplus_kwargs(
    canonical_locale: dict[str, str],
    tr_call_sites: dict[str, list[frozenset[str]]],
) -> None:
    """No call site supplies a kwarg that the locale value does not declare.

    A SURPLUS kwarg is silently dropped by ``_interpolate``; the call
    site author either misnamed the kwarg or the locale template lost
    the matching ``%{name}`` token without the call site being updated.
    Fix by either:
    - adding the missing ``%{name}`` token to the locale value, or
    - removing the stale kwarg from the call site.
    """
    findings: list[str] = []
    for key, call_kwargs_list in sorted(tr_call_sites.items()):
        if key not in canonical_locale:
            continue
        locale_val = canonical_locale[key]
        required = extract_placeholders(locale_val)
        all_supplied = frozenset().union(*call_kwargs_list)
        for kwarg in sorted(all_supplied - required):
            findings.append(f"SURPLUS  key={key!r}  kwarg={kwarg!r}  locale={locale_val[:80]!r}")
    if findings:
        formatted = "\n  ".join(findings)
        pytest.fail(
            f"{len(findings)} SURPLUS kwarg(s) detected — "
            f"call site kwargs not matched by any locale placeholder:\n  {formatted}",
        )


def test_no_shadow_kwarg_variants(
    canonical_locale: dict[str, str],
    tr_call_sites: dict[str, list[frozenset[str]]],
) -> None:
    """All call sites for a given key supply the same kwarg set.

    A SHADOW arises when two call sites for the same key supply
    *different* non-empty kwarg sets.  One rendering path will produce
    the correct output; the other silently renders a partial string.
    Fix by aligning all call sites for the key to supply identical
    kwargs matching the locale placeholders.
    """
    findings: list[str] = []
    for key, call_kwargs_list in sorted(tr_call_sites.items()):
        if key not in canonical_locale:
            continue
        non_empty = [s for s in call_kwargs_list if s]
        distinct = {frozenset(s) for s in non_empty}
        if len(distinct) > 1:
            variants = [sorted(s) for s in sorted(distinct, key=sorted)]
            findings.append(f"SHADOW  key={key!r}  variants={variants!r}")
    if findings:
        formatted = "\n  ".join(findings)
        pytest.fail(
            f"{len(findings)} SHADOW kwarg variant(s) detected — "
            f"inconsistent kwarg sets across call sites for the same key:\n  {formatted}",
        )

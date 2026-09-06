"""Structural gate: every ``tr(CONSTANT)`` call site's constant is scanner-visible.

The fourth concealment-layer class the honesty themes named: a
``tr(CONSTANT)`` call site where ``CONSTANT`` is a bare, ALL-CAPS module- or
class-level constant reference escapes both AST resolvers in
:mod:`locales._ast_scanner` — it is not a literal string (so
``_dotted_literal_value`` finds nothing at the call site), and if the
constant's own name does not end in ``_LOCALE_KEY``/``_LOCALE_KEYS`` it is
also invisible to ``_extract_locale_constant_keys`` (which only resolves
declarations matching that suffix). The key becomes entirely invisible to
the coverage/parity audit: a missing catalogue entry, a typo, or an orphaned
key on that call site raises nothing, because the scanner never knew the key
existed.

This gate closes the loop by holding the CALL SITE to the exact naming
contract the DECLARATION side already enforces
(:func:`locales._ast_scanner._declares_locale_key_constant`): any
``tr(...)``/``t(...)`` argument that looks like a constant reference by its
ALL-CAPS shape must carry a ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix.
"""

from __future__ import annotations

import ast

import pytest

from .._ast_scanner import find_tr_constant_naming_violations, tr_constant_naming_violations_in_tree
from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The source tree the scanner walks. The tooling sits outside the package it
# maintains, so the root is resolved from the checkout by the shared derivation
# rather than counted from this file's own parents.
_SRC_ROOT = SRC_DIR


def test_no_tr_constant_naming_violations_repo_wide() -> None:
    """Every production ``tr(CONSTANT)``/``t(CONSTANT)`` call site is scanner-visible.

    Real-behavior gate: walks the actual ``src/cadrumo`` tree (not a fixture)
    and fails loudly, naming every offending ``path:line: 'CONSTANT'`` site,
    the moment a constant reference without the required suffix is passed to
    the translator. The one currently compliant production site
    (``application/wizard/format_hints.py``'s
    ``REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY``, referenced from
    ``application/wizard/_registered_values.py``) is proof this is not a
    vacuous "nothing calls tr() with a constant" pass — the naming
    convention is genuinely exercised at HEAD, not merely absent.
    """
    violations = find_tr_constant_naming_violations(_SRC_ROOT)

    assert violations == [], (
        "tr()/t() call site(s) reference a constant without the required "
        "_LOCALE_KEY/_LOCALE_KEYS suffix, making the key invisible to the "
        "locale coverage/parity scanners:\n" + "\n".join(violations)
    )


def test_rule_fires_on_an_unsuffixed_constant_reference() -> None:
    """Non-tautology proof: an unsuffixed constant reference is caught.

    ``SOME_MESSAGE`` is a plausible module constant by its ALL-CAPS shape,
    carries no ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix, and is fed straight
    into ``tr(...)`` — precisely the shape that made the concealed key
    invisible to the declaration-side scanner. The detector must fire.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "SOME_MESSAGE = 'cli.app.some.message'\n"
        "\n"
        "def render() -> str:\n"
        "    return tr(SOME_MESSAGE)\n",
    )

    violations = list(tr_constant_naming_violations_in_tree(tree))

    assert violations == [(6, "SOME_MESSAGE")]


def test_rule_passes_on_a_correctly_suffixed_constant_reference() -> None:
    """Anti-false-positive proof: the compliant shape stays green.

    A constant whose name ends in the required suffix is exactly the shape
    the declaration-side scanner (``_extract_locale_constant_keys``) already
    resolves, so referencing it from a ``tr(...)`` call site must NOT trip
    this gate.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "SOME_MESSAGE_LOCALE_KEY = 'cli.app.some.message'\n"
        "\n"
        "def render() -> str:\n"
        "    return tr(SOME_MESSAGE_LOCALE_KEY)\n",
    )

    assert list(tr_constant_naming_violations_in_tree(tree)) == []


def test_rule_fires_through_the_aliased_translator_import() -> None:
    """The rule resolves the same ``tr as _tr`` alias convention the other scanners honor.

    An unsuffixed constant must not escape detection merely because the call
    site uses the project's underscore-aliased translator import.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr as _tr\n"
        "\n"
        "BANNER = 'cli.app.banner'\n"
        "\n"
        "def render() -> str:\n"
        "    return _tr(BANNER)\n",
    )

    violations = list(tr_constant_naming_violations_in_tree(tree))

    assert violations == [(6, "BANNER")]


def test_rule_ignores_a_lowercase_or_mixed_case_argument() -> None:
    """A lowercase/mixed-case name is a genuinely dynamic value, not a constant.

    A local variable, function parameter, or loop variable does not follow
    the ALL-CAPS constant-naming shape the declaration-side rule itself uses
    to identify a locale-key registry, so it is out of scope for this check —
    flagging it would be a false positive against ordinary dynamic
    dispatch, not the concealment class this gate targets.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n\ndef render(dynamic_key: str) -> str:\n    return tr(dynamic_key)\n",
    )

    assert list(tr_constant_naming_violations_in_tree(tree)) == []


def test_rule_ignores_a_literal_string_argument() -> None:
    """A literal ``tr("...")`` call site is already fully scanner-visible.

    This gate targets only the bare-Name constant-reference shape; a literal
    string argument is out of scope (and already handled by the
    declaration-side literal scanner), so it must not be flagged here.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n\ndef render() -> str:\n    return tr('cli.app.literal.key')\n",
    )

    assert list(tr_constant_naming_violations_in_tree(tree)) == []


def test_rule_ignores_an_unrelated_uppercase_call_argument() -> None:
    """An unsuffixed constant passed to an unrelated function is not a violation.

    The gate is scoped to ``tr()``/``t()`` call sites specifically (resolved
    through the alias set every other scanner in this module shares); an
    ALL-CAPS constant passed to a different callee carries no locale-key
    contract at all.
    """
    tree = ast.parse(
        "def other_call() -> None:\n"
        "    return None\n"
        "\n"
        "SOME_MESSAGE = 'not-a-locale-key'\n"
        "\n"
        "def render() -> None:\n"
        "    other_call(SOME_MESSAGE)\n",
    )

    assert list(tr_constant_naming_violations_in_tree(tree)) == []

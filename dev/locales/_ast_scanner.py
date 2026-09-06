"""AST-based locale-key discovery for sites the regex scanner misses.

The regex scanner under :class:`locales.manager.LocaleManager`
captures `tr("…")` and `t("…")` literal call sites. Two surfaces slip
past that contract:

* Programmatic errors that pass a translation key to an exception
  constructor through a ``message_key=`` / ``translation_key=`` kwarg rather than a
  :func:`tr` call (for example
  ``WizardValidationError("wizard.errors.select_unknown")``).
* f-string call sites whose JoinedStr starts with a literal
  dot-notation prefix matching the translation-key shape (for example
  ``tr(f"cli.registry.metrics.{key}")``) — the regex sees the prefix
  but cannot tell what follows. The scanner emits a
  ``<prefix>.*`` marker that the parity check treats as a namespace
  declaration rather than a single key.
* Bounded locale-key registries exposed as module constants whose names
  end in ``_LOCALE_KEY`` or ``_LOCALE_KEYS``. These constants centralize
  key selection for application policies that return translation keys
  to a later caller instead of calling :func:`tr` locally.
* Dict literals SHAPED as a locale-key registry (every value a
  dotted-key string) AND actually read into a translator sink, regardless
  of what their assignment target is named — a status/enum-token-to-key
  mapping read through a lowercase local (``SOME_DICT.get(token)``) into
  :func:`tr`. Recognized by shape plus real usage
  (:func:`_flow_confirmed_locale_key_dicts`), not by the naming convention
  the previous bullet depends on; shape alone is deliberately NOT
  sufficient, because this codebase also carries same-shaped dicts (a
  casilla-to-casilla reconciliation map, a ``Notice.code`` machine-routing
  table) that never reach the translator.

These findings feed into
:meth:`locales.manager.LocaleManager.get_codebase_keys` so the
parity audit covers programmatic emissions and dynamic namespaces.

Two further surfaces are structural HAZARDS rather than discovery gaps:

* ``tr(SOME_CONSTANT)`` where ``SOME_CONSTANT`` is a bare, ALL-CAPS
  constant reference that does NOT carry the ``_LOCALE_KEY``/``_LOCALE_KEYS``
  suffix. Neither the literal-argument resolver nor the constant-declaration
  resolver above finds it, so the key is invisible to every downstream
  audit — a missing catalogue entry, a typo, or an orphaned key on that
  site raises nothing. :func:`find_tr_constant_naming_violations` is a
  repo-wide structural gate (not a key-discovery feed) that holds every
  call site to the same naming contract the declaration side already
  enforces.
* A dict literal shaped as a locale-key registry (the discovery bullet
  above) but named without the required suffix. Key discovery no longer
  depends on the rename, but the un-suffixed declaration is exactly the
  concealed form that let a production dict orphan invisibly — neither
  the declaration-side suffix check nor the call-site naming gate (which
  explicitly excludes the lowercase local it is read through) could see
  it. :func:`find_dict_constant_naming_violations` surfaces the hazard so
  a human renames it into the same contract the call-site gate already
  enforces.

Both hazard gates hold different HALVES of the same naming contract
(:data:`_LOCALE_KEY_CONSTANT_SUFFIXES`) to account: the call-site gate
holds the USE to the DECLARATION's contract; the dict gate holds a
SHAPE-MATCHED DECLARATION to its OWN contract.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.logging import get_logger

from .._paths import UTF_8
from ..quality.unread_inputs import report_unread

_log = get_logger(__name__)
_UTF_8: Final[str] = UTF_8

_KEY_PATTERN_PREFIX_MIN_PARTS = 2
"""A discovered f-string key prefix must carry at least two dotted
segments before the dynamic tail (e.g. ``cli.registry.metrics``)."""

_KEY_LITERAL_RE = re.compile(r"^[\w-]+(?:\.[\w-]+)+$", re.UNICODE)
"""A literal that qualifies as a translation-key prefix: word chars,
hyphens, and dots only, at least two dotted segments, no whitespace,
slashes, operators, or other punctuation. Hyphens are first-class key
characters — the wizard page catalogue keys segments by hyphenated page
ids (``wizard.setup.format.tax-id``), and a hyphen-blind shape check
leaves every such key invisible to the scanner even when it is declared
in a ``*_LOCALE_KEY`` constant."""

_DYNAMIC_TRANSLATION_ROOTS = frozenset(
    {
        "application",
        "cli",
        "errors",
        "flows",
        "profile",
        "sheets",
        "topic",
        "wizard",
    },
)
"""Top-level roots that can legitimately identify dynamic i18n namespaces.

Documented dynamic-dispatch survivors
--------------------------------------
The following f-string patterns in :mod:`application.wizard.catalogue`
produce dynamic translation keys. They are bounded (not open-ended) because
the tail is always an enum member value or a flow-registered question ID —
the set of runtime keys is fully enumerable from the domain model. They are
intentional survivors of the static-key constraint and are covered here by
the ``"wizard"`` root entry:

* ``tr(f"wizard.setup.{suffix}.{qid}.prompt")`` — ``suffix`` is drawn from
  the wizard flow's registered section ID (e.g. ``"taxpayer-type"``,
  ``"obligations"``, ``"residence"``); ``qid`` is a flow-registered question
  ID. Every concrete key exists in all locale files.

* ``tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value...}.label")``
  and equivalent patterns for ``LegalEntityForm``, ``IrpfIncomeCategory``,
  ``IrpfEstimationRegime``, ``IrpfSpecialRegime``, ``FiscalResidency``,
  ``CCAA``, and ``SUPPORTED_OUTPUT_LANGUAGES`` — the tail segment is an enum
  member value (snake_case with underscores replaced by hyphens). The full
  key space is bounded by the enum definition.

These patterns are picked up by :func:`_extract_fstring_prefixes` and emitted
as ``wizard.setup.*`` namespace markers, which the parity check validates
against concrete locale entries. No additional static registration is needed.
"""


#: Keyword arguments whose dotted-literal value IS a translation key. The
#: finding constructors use ``message_locale_key``; the error registry and the
#: wizard verifiers use the other three; the CLI command-spec tables use
#: ``help_key`` for every command, group and option help string they declare.
#:
#: ``help_key`` currently recovers NOTHING on its own: all 893 sites wrap their
#: value, so the wrapper rule below already reaches every one, and removing this
#: entry leaves the scanner's output unchanged. It is kept because an unwrapped
#: ``help_key="cli..."`` is the form a new spec would most naturally reach for and
#: would otherwise be silently invisible. Stated rather than left implied, so nobody
#: later reads it as evidence that bare help kwargs exist.
_TRANSLATION_KEY_KWARGS: frozenset[str] = frozenset(
    {"translated_message", "message_key", "translation_key", "message_locale_key", "help_key"},
)

#: Single-argument constructors and helpers that WRAP a translation key without
#: changing it. Note ``_key`` is NOT unique to this purpose -- the AEAT session
#: store defines its own ``_key(path)`` returning a posix path -- so a wrapper is
#: only ever read as a key when its argument is a catalogue-rooted dotted literal.
#: The name alone is not the signal; the name plus the shape of what it wraps is.
#:
#: The CLI command specs never pass a bare string: every help key is
#: written ``help_key=TranslationKey("cli...")`` or ``help_key=_key("cli...")``, so
#: reading only ``ast.Constant`` values made 690 live keys invisible to this scanner
#: and reported them as catalogue-only extras — one strip away from deleting the
#: entire ledger and live CLI help surface.
_KEY_WRAPPER_CALLS: frozenset[str] = frozenset({"TranslationKey", "_key"})

#: CLI command-spec factories that take their translation key as a POSITIONAL
#: argument. The command-spec tables under ``entrypoints/cli/*_command_specs.py``
#: build every verb, group, option and argument through these few helpers, passing
#: the help key positionally rather than as ``help_key=``. Read as a declared table
#: rather than by generalising to "any positional dotted literal", which would let a
#: module path or a dotted identifier become a phantom catalogue key.
#:
#: Collection is additionally guarded by :func:`_is_dynamic_translation_prefix`, so
#: only literals rooted in a real catalogue namespace are taken.
_COMMAND_SPEC_KEY_FACTORIES: frozenset[str] = frozenset(
    {
        "_option",
        "_leaf",
        "_required",
        "_group",
        "ArgumentSpec",
        # Two more option factories, added because the keys they carry were
        # invisible: thirteen catalogue entries the source writes and this
        # scanner did not see, which the coverage and parity scanners would
        # therefore report as unused and which are one strip away from
        # deletion. Both were derived from the keys the owning gate reported
        # rather than guessed, and both are named here rather than reached by
        # widening the rule to any positional dotted literal - which the note
        # above rejects, because a module path would then become a phantom key.
        "_boolean_flag_option",
        "_repeatable_text_option",
        "_optional_text_option",
        "state_free_group_spec",
    },
)


def _is_dotted_literal(value: str) -> bool:
    """Return True when ``value`` matches the dot-notation key shape."""
    return bool(_KEY_LITERAL_RE.match(value))


def _is_dynamic_translation_prefix(prefix: str) -> bool:
    """Return True when a dynamic dotted prefix belongs to the i18n catalogue."""
    root = prefix.split(".", 1)[0]
    return root in _DYNAMIC_TRANSLATION_ROOTS


def _extract_error_constructor_keys(tree: ast.AST) -> set[str]:
    """Find translation keys declared anywhere in the module.

    Collects positional translation keys passed to classes whose name
    ends with ``Error``/``Exception``, ``message_key=``/
    ``translation_key=`` / ``translated_message=`` dotted-literal kwargs on any callee
    (exception constructors, ``ErrorCode`` registry rows,
    ``WizardCheckFinding`` verifier findings), direct
    ``tr("dotted.key")``/``t("dotted.key")`` calls, ``build_entry``
    portal-catalogue keys, and dotted-literal defaults for kw-only
    ``translated_message``/``message_key``/``translation_key`` parameters.
    """
    findings: set[str] = set()
    tr_names = _translation_call_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            _collect_kwonly_default_keys(node, findings)
        elif isinstance(node, ast.Call):
            _collect_call_site_keys(node, findings, tr_names)
    return findings


def _translation_call_names(tree: ast.AST) -> frozenset[str]:
    """Return every local name that resolves to the ``tr`` / ``t`` translator.

    Always includes the canonical ``tr`` / ``t`` names, plus any module-local
    alias introduced by an aliased import (``from ...core.i18n import tr as
    _tr`` - the underscore-aliased module-level import convention). Without
    alias resolution an aliased call site like ``_tr("cli.root.verbose_help")``
    is invisible to the scanner, so its genuinely-live locale keys are wrongly
    reported as orphans and pruned.
    """
    names = {"tr", "t"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in {"tr", "t"} and alias.asname:
                    names.add(alias.asname)
    return frozenset(names)


def _extract_locale_constant_keys(tree: ast.AST) -> set[str]:
    """Find dotted locale keys declared in explicit locale-key constants.

    Recognizes two independent declaration shapes: a constant NAMED as a
    locale-key registry (:func:`_declares_locale_key_constant`, suffix-based,
    which then trusts every dotted literal nested under its value), and a
    dict literal SHAPED as one AND actually read into a translator sink
    (:func:`_flow_confirmed_locale_key_dicts`) regardless of what its target
    is named. The second shape is what let a status-token-to-key mapping
    orphan invisibly when it carried neither a suffixed name nor a literal
    ``tr()`` call site — see :func:`dict_constant_naming_violations_in_tree`
    for the companion naming HAZARD this shape also earns. Flow confirmation
    (not shape alone) keeps a same-shaped unrelated lookup table — mapping
    one dotted identifier to another without ever reaching the translator —
    from being misread as a locale-key declaration.
    """
    findings: set[str] = set()
    flow_confirmed = _flow_confirmed_locale_key_dicts(tree) | _flow_confirmed_locale_key_row_tables(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            named = any(_declares_locale_key_constant(target) for target in node.targets)
            shaped = any(
                isinstance(target, ast.Name) and flow_confirmed.get(target.id) is node.value for target in node.targets
            )
            if named or shaped:
                _collect_declared_locale_keys(node.value, findings)
        elif isinstance(node, ast.AnnAssign):
            named = _declares_locale_key_constant(node.target)
            shaped = isinstance(node.target, ast.Name) and flow_confirmed.get(node.target.id) is node.value
            if named or shaped:
                _collect_declared_locale_keys(node.value, findings)
    return findings


def _collect_declared_locale_keys(value: ast.expr, findings: set[str]) -> None:
    """Collect the locale keys a declared registry holds, and not its lookup tokens.

    A locale-key MAPPING is keyed by whatever the runtime selects on -- an enum
    value, a route identity, an action id -- and only its VALUES are locale
    keys. Sweeping the whole literal in claims those tokens as keys too, and
    they are dotted often enough to look the part: `workbench.home` and
    `operator.profile.edit` are a TUI route and a catalogue action, and the
    parity gate reported all of them as missing translations that no catalogue
    should ever have carried.

    Every other shape -- a tuple, list or set of keys, or a bare string -- has
    no such distinction, so it is collected whole as before.
    """
    if isinstance(value, ast.Dict):
        for item in value.values:
            _collect_dotted_literals(item, findings)
        return
    _collect_dotted_literals(value, findings)


_LOCALE_KEY_CONSTANT_SUFFIXES: tuple[str, str] = ("_LOCALE_KEY", "_LOCALE_KEYS")
"""Naming convention every module-level locale-key constant must carry.

Shared by :func:`_declares_locale_key_constant` (does this ASSIGNMENT declare
a locale-key registry?) and :func:`find_tr_constant_naming_violations` (does
this ``tr(CONSTANT)`` CALL SITE reference one?) so the two halves of the
contract — the declaration and the use — are held to one naming rule rather
than two independently-maintained copies that could drift apart."""


def _declares_locale_key_constant(target: ast.expr) -> bool:
    """Return True when ``target`` names an explicit locale-key registry."""
    if not isinstance(target, ast.Name):
        return False
    return target.id.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES)


def _is_locale_key_dict_literal(node: ast.expr | None) -> bool:
    """Return True when ``node`` is a dict literal shaped as a locale-key registry.

    Structural, not name-based: a dict literal mapping arbitrary keys (often
    short status/enum tokens resolved only at runtime) to translation keys is
    unambiguously a locale-key registry BY SHAPE alone, independent of what
    its assignment target is named. Requires at least one entry and EVERY
    value to be a dotted-key-shaped string constant — a dict with even one
    non-matching value is not treated as a locale-key mapping, which keeps
    the false-positive rate low against an ordinary lookup table that merely
    happens to carry one dotted-looking string.

    This is the exact shape that orphaned invisibly in production: a dict
    constant named without the ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix,
    read through a lowercase local variable (``SOME_DICT.get(token)``) into
    ``tr(...)``. Neither the declaration-side suffix check nor the call-site
    naming gate (which explicitly excludes lowercase/mixed-case arguments as
    genuinely dynamic values) can see it; recognizing the dict BY SHAPE closes
    the discovery gap without requiring any rename.
    """
    if not isinstance(node, ast.Dict) or not node.values:
        return False
    return all(_dotted_literal_value(value) is not None for value in node.values)


def _shape_candidate_locale_key_dicts(tree: ast.AST) -> dict[str, ast.expr]:
    """Return every ``Name -> dict-literal-value`` pair shaped as a locale-key registry.

    Shape alone (:func:`_is_locale_key_dict_literal`) is necessary but not
    sufficient: many dicts in this codebase map one dotted-namespaced
    identifier to another WITHOUT either side being a translation key (a
    casilla-to-casilla reconciliation map, a ``Notice.code`` machine-routing
    table). :func:`_flow_confirmed_locale_key_dicts` narrows this candidate
    set down to the ones actually read into a recognized locale-key sink.
    """
    candidates: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and _is_locale_key_dict_literal(value):
            candidates[target.id] = value
    return candidates


def _dict_access_source(value: ast.expr | None) -> str | None:
    """Return the dict-constant ``Name`` a ``.get(...)``/subscript access reads.

    Recognizes ``SOME_DICT.get(...)`` and ``SOME_DICT[...]`` where
    ``SOME_DICT`` is a bare name — the two lookup shapes both real incidents
    and every judged-legitimate lookup table in this codebase use.
    """
    if value is None:
        return None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "get":
        base = value.func.value
        return base.id if isinstance(base, ast.Name) else None
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
        return value.value.id
    return None


def _call_site_key_argument_exprs(node: ast.Call, tr_names: frozenset[str]) -> list[ast.expr]:
    """Return ``node``'s argument expressions that are recognized locale-key sinks.

    Mirrors the sink taxonomy :func:`_collect_call_site_keys` already
    recognizes for LITERAL keys (``tr``/``t`` calls, ``build_entry``,
    ``ValidationVerdict.failed``, ``*Error``/``*Exception`` constructors, and
    the translation-key kwargs), so flow confirmation asks exactly the same
    question that already governs whether a literal value is a genuine
    locale key — never a narrower or looser one invented for this check
    alone.
    """
    name = _callee_name(node.func)
    exprs: list[ast.expr] = []
    if name is not None:
        is_first_arg_sink = name in tr_names or name == "failed" or name.endswith(("Error", "Exception"))
        if is_first_arg_sink and node.args:
            exprs.append(node.args[0])
        elif name == "build_entry":
            for kw in node.keywords:
                if kw.arg in {"label", "purpose"}:
                    exprs.append(kw.value)
                elif kw.arg == "notes" and isinstance(kw.value, ast.Tuple | ast.List):
                    exprs.extend(kw.value.elts)
    for kw in node.keywords:
        if kw.arg in _TRANSLATION_KEY_KWARGS:
            exprs.append(kw.value)
    return exprs


def _locale_key_dict_names_read_into_a_sink(tree: ast.AST, candidate_names: frozenset[str]) -> frozenset[str]:
    """Return the candidate dict names actually read into a recognized locale-key sink.

    Tracks the ``local = SOME_DICT.get(...)`` / ``local = SOME_DICT[...]``
    indirection one hop per function/method body — the exact shape the
    concealed incident used (``setup_state_key =
    _PROFILE_SETUP_STATE_KEYS.get(...)``; ``tr(setup_state_key)``) — plus the
    direct ``tr(SOME_DICT.get(...))``/``tr(SOME_DICT[...])`` shape. This is
    what tells a dict that is genuinely a locale-key source apart from a
    same-shaped lookup table for an unrelated domain that never reaches a
    translation-key sink: a casilla-to-casilla reconciliation map or a
    ``Notice.code`` machine-routing table both use the identical
    dict-of-dotted-strings SHAPE without ever being read by ``tr()``.

    Each function/method body is walked in two passes so confirmation never
    depends on AST traversal order (``ast.walk`` is breadth-first, not
    textual order): the first pass fully populates the local-to-dict map,
    the second checks every call against it.
    """
    tr_names = _translation_call_names(tree)
    confirmed: set[str] = set()
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        local_to_dict: dict[str, str] = {}
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                source = _dict_access_source(node.value)
                if source in candidate_names:
                    local_to_dict[node.targets[0].id] = source
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            for argument in _call_site_key_argument_exprs(node, tr_names):
                direct = _dict_access_source(argument)
                if direct in candidate_names:
                    confirmed.add(direct)
                elif isinstance(argument, ast.Name) and argument.id in local_to_dict:
                    confirmed.add(local_to_dict[argument.id])
    return frozenset(confirmed)


def _flow_confirmed_locale_key_dicts(tree: ast.AST) -> dict[str, ast.expr]:
    """Return shape-candidate locale-key dicts actually read into a translator sink.

    Combines :func:`_shape_candidate_locale_key_dicts` (structural
    candidacy) with :func:`_locale_key_dict_names_read_into_a_sink` (real
    usage confirmation) so neither signal alone decides: shape alone
    over-fires on same-shaped unrelated lookup tables, and usage alone
    cannot be checked without first knowing which names are dict-shaped
    candidates.
    """
    candidates = _shape_candidate_locale_key_dicts(tree)
    confirmed_names = _locale_key_dict_names_read_into_a_sink(tree, frozenset(candidates))
    return {name: value for name, value in candidates.items() if name in confirmed_names}


def _is_locale_key_row_table_literal(node: ast.expr | None) -> bool:
    """Return True when ``node`` is a table of string ROWS carrying a key column.

    The dict shape above covers ``{token: "some.key"}``. A second table shape
    ships in this codebase and the dict test cannot see it: a tuple of
    equal-width tuples where one COLUMN holds the translation key and the
    others hold the framework's English source strings and defaults, iterated
    as ``for prefix, key, default, _ in TABLE`` and reaching ``tr(key)``.
    Requiring every value to be a dotted key -- as the dict shape does -- is
    exactly wrong here, because the sibling columns are prose by design.

    The signal is POSITIONAL instead: every row is all-string, every row has
    the same width, and there is at least one index where EVERY row carries a
    dotted-key-shaped string. A column that is a key in one row and prose in
    the next is not a key column, so an ordinary table of English pairs cannot
    qualify. Prose does not collide with the key shape in any case, since
    :data:`_KEY_LITERAL_RE` admits no spaces.
    """
    if not isinstance(node, ast.Tuple | ast.List) or not node.elts:
        return False
    rows: list[list[str]] = []
    for element in node.elts:
        if not isinstance(element, ast.Tuple | ast.List) or not element.elts:
            return False
        values = [item.value for item in element.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if len(values) != len(element.elts):
            return False
        rows.append(values)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        return False
    return any(all(_is_dotted_literal(row[index]) for row in rows) for index in range(width))


def _row_table_key_columns(node: ast.expr | None) -> frozenset[int]:
    """Return the column indices where EVERY row carries a dotted key.

    The shape test asks whether such a column exists; confirmation needs to
    know WHICH, because the sibling columns are prose by design and a name
    bound to one of those reaching a sink says nothing about the table.
    """
    if not isinstance(node, ast.Tuple | ast.List) or not node.elts:
        return frozenset()
    rows: list[list[str]] = []
    for element in node.elts:
        if not isinstance(element, ast.Tuple | ast.List) or not element.elts:
            return frozenset()
        values = [item.value for item in element.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if len(values) != len(element.elts):
            return frozenset()
        rows.append(values)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        return frozenset()
    return frozenset(index for index in range(width) if all(_is_dotted_literal(row[index]) for row in rows))


def _shape_candidate_locale_key_row_tables(tree: ast.AST) -> dict[str, ast.expr]:
    """Return every ``Name -> row-table-literal`` pair shaped as a locale-key registry."""
    candidates: dict[str, ast.expr] = {}
    for node in ast.walk(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and _is_locale_key_row_table_literal(value):
            candidates[target.id] = value
    return candidates


def _row_table_names_iterated_into_a_sink(tree: ast.AST, candidates: dict[str, ast.expr]) -> frozenset[str]:
    """Return the candidate row-table names whose loop variable reaches a translator.

    The dict sink tracks ``.get(...)``/subscript access. A row table is not
    read that way -- it is ITERATED, and the key arrives at ``tr`` as one of
    the loop's unpacked target names. Confirming through that binding is what
    separates a genuine locale-key table from a same-shaped table of unrelated
    string tuples that never reaches the translator.
    """
    tr_names = _translation_call_names(tree)
    key_columns = {name: _row_table_key_columns(value) for name, value in candidates.items()}
    bound_to_table: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.For | ast.AsyncFor):
            continue
        if not (isinstance(node.iter, ast.Name) and node.iter.id in candidates):
            continue
        columns = key_columns[node.iter.id]
        if isinstance(node.target, ast.Name):
            # A whole-row binding cannot say which column reaches the sink, so
            # it stays confirmable as before.
            bound_to_table[node.target.id] = node.iter.id
            continue
        # Unpacked: only the KEY column binding confirms. A name bound to a
        # prose column reaching a sink is the framework passing its English
        # source string, which says nothing about whether the table holds keys.
        for index, target in enumerate(getattr(node.target, "elts", [])):
            if isinstance(target, ast.Name) and index in columns:
                bound_to_table[target.id] = node.iter.id
    confirmed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for argument in _call_site_key_argument_exprs(node, tr_names):
            if isinstance(argument, ast.Name) and argument.id in bound_to_table:
                confirmed.add(bound_to_table[argument.id])
    return frozenset(confirmed)


def _flow_confirmed_locale_key_row_tables(tree: ast.AST) -> dict[str, ast.expr]:
    """Return shape-candidate row tables actually iterated into a translator sink."""
    candidates = _shape_candidate_locale_key_row_tables(tree)
    confirmed_names = _row_table_names_iterated_into_a_sink(tree, candidates)
    return {name: value for name, value in candidates.items() if name in confirmed_names}


def _collect_dotted_literals(node: ast.expr | None, findings: set[str]) -> None:
    """Collect dotted string literals nested under ``node``."""
    if node is None:
        return
    value = _dotted_literal_value(node)
    if value is not None:
        findings.add(value)
        return
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            _collect_dotted_literals(child, findings)


def _collect_kwonly_default_keys(node: ast.FunctionDef, findings: set[str]) -> None:
    """Pick up dotted-literal defaults for translation-key kwonly args."""
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False):
        if default is None or arg.arg not in _TRANSLATION_KEY_KWARGS:
            continue
        value = _dotted_literal_value(default)
        if value is not None:
            findings.add(value)


def _collect_call_site_keys(node: ast.Call, findings: set[str], tr_names: frozenset[str]) -> None:
    """Pick up translation keys from call sites across multiple call patterns.

    Handles ``tr(...)`` / ``t(...)`` direct calls, ``*Error``/``*Exception``
    constructor translation keys, ``build_entry(...)`` portal-catalogue
    translation keys, ``ValidationVerdict.failed(...)`` flow-verdict
    factory keys, and ``message_key=`` / ``translation_key=`` /
    ``translated_message=`` dotted-literal kwargs on any callee.

    The translation-key kwargs (``message_key=`` / ``translation_key=`` / ``translated_message=``)
    are collected callee-agnostically: any call that names one of those
    kwargs with a dotted-literal value declares a live operator-facing
    translation key. This covers the ``ErrorCode(message_key=...)``
    registry rows and ``WizardCheckFinding(message_key=...)`` verifier
    findings, neither of which carries an ``*Error`` callee name.
    """
    name = _callee_name(node.func)
    if name is None:
        return
    _collect_translation_key_kwargs(node, findings)
    _collect_wrapped_key_arguments(node, findings)
    if name in _COMMAND_SPEC_KEY_FACTORIES:
        _collect_command_spec_positional_keys(node, findings)
    if name in tr_names:
        _add_first_dotted_arg(node, findings)
        return
    if name == "build_entry":
        _collect_build_entry_keys(node, findings)
        return
    if name == "failed":
        # ValidationVerdict.failed("dotted.message.key", ...) — the flow
        # substrate's verdict factory declares its operator-facing message
        # key as the first positional argument, not a tr() call site or a
        # message_key kwarg, so it needs first-class collection or the
        # scaffold prunes the authored leaves as orphans.
        _add_first_dotted_arg(node, findings)
        return
    if name.endswith("Error") or name.endswith("Exception"):
        _add_first_dotted_arg(node, findings)


def _collect_wrapped_key_arguments(node: ast.Call, findings: set[str]) -> None:
    """Collect wrapped translation keys from ANY argument of ANY call.

    Callee-agnostic on purpose. A key written ``TranslationKey("cli...")`` denotes
    that key wherever it appears, and the CLI spec tables pass it positionally into
    a long tail of local factories -- enumerating those factories chased the same
    defect one helper at a time, while the wrapper is the thing that actually marks
    the string.

    Safety comes from the argument, not the callee: the wrapper must hold a lone
    dotted literal ROOTED IN A CATALOGUE NAMESPACE, so an overloaded helper such as
    the session store's ``_key(path)`` cannot contribute a phantom key.
    """
    for argument in (*node.args, *(kw.value for kw in node.keywords)):
        value = _unwrapped_key_literal(argument)
        if value is not None and _is_dynamic_translation_prefix(value):
            findings.add(value)


def _collect_command_spec_positional_keys(node: ast.Call, findings: set[str]) -> None:
    """Collect catalogue-rooted dotted literals passed positionally to a spec factory.

    Every positional argument is considered, because the key's index differs between
    these helpers, and a spec's other positional arguments are handler names, result
    model names and permission constants -- none of which are dotted, so none of which
    can be mistaken for a key. The catalogue-root guard is what makes that safe rather
    than merely true today.
    """
    for argument in node.args:
        value = _dotted_literal_value(argument)
        if value is not None and _is_dynamic_translation_prefix(value):
            findings.add(value)


def _collect_translation_key_kwargs(node: ast.Call, findings: set[str]) -> None:
    """Collect translation-key dotted-literal kwargs.

    The kwarg name alone identifies a translation key, so this is
    callee-agnostic: it covers exception constructors,
    ``super().__init__(...)`` delegations, ``ErrorCode(...)`` registry
    declarations, and ``WizardCheckFinding(...)`` verifier findings
    alike.
    """
    for kw in node.keywords:
        if kw.arg not in _TRANSLATION_KEY_KWARGS:
            continue
        value = _dotted_literal_value(kw.value)
        if value is not None:
            findings.add(value)


def _collect_build_entry_keys(node: ast.Call, findings: set[str]) -> None:
    """Pick up portal-catalogue translation keys passed to ``build_entry``.

    :mod:`domain.portals._entries` modules construct each portal entry
    through :func:`domain.portals._entries._common.build_entry`, passing the
    multilingual ``label`` and
    ``purpose`` keys (and an optional ``notes`` tuple of keys) as keyword
    arguments rather than through a ``tr(...)`` call. The regex scanner
    and the ``tr``/``t`` call-site path both miss them, so resolve those
    keyword arguments explicitly here.
    """
    for kw in node.keywords:
        if kw.arg in {"label", "purpose"}:
            value = _dotted_literal_value(kw.value)
            if value is not None:
                findings.add(value)
        elif kw.arg == "notes" and isinstance(kw.value, ast.Tuple | ast.List):
            for element in kw.value.elts:
                element_value = _dotted_literal_value(element)
                if element_value is not None:
                    findings.add(element_value)


def _callee_name(callee: ast.expr) -> str | None:
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _dotted_literal_value(node: ast.expr | None) -> str | None:
    """Return the dotted-literal key string ``node`` carries, else ``None``.

    Returns the resolved ``str`` directly so callers obtain a typed
    value without a separate ``node.value`` access — ``ast.Constant.value``
    is a broad ``str | bytes | int | ...`` union the type system cannot
    narrow through a predicate. The runtime check is unchanged: the node
    must be a Constant, its value must be a string, and the string must
    match the dotted-literal shape.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_dotted_literal(node.value):
        return node.value
    return _unwrapped_key_literal(node)


def _unwrapped_key_literal(node: ast.expr | None) -> str | None:
    """Return the key inside a single-argument key wrapper, else ``None``.

    ``TranslationKey("cli.app.ledger.x_help")`` and ``_key("cli.app.live.y_help")``
    denote exactly the string they wrap; the wrapper is a typing newtype and a local
    shorthand, not a transformation. Restricted to a known callee set and to a lone
    positional Constant argument, so a call that COMPUTES a key is still correctly
    left to the dynamic-prefix machinery rather than being read as a literal.
    """
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 1:
        return None
    if _callee_name(node.func) not in _KEY_WRAPPER_CALLS:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and _is_dotted_literal(argument.value):
        return argument.value
    return None


def _add_first_dotted_arg(node: ast.Call, findings: set[str]) -> None:
    """Collect the dotted-literal key(s) carried by a call's first argument.

    A ternary first argument (``tr(branch_a if cond else branch_b)`` where each
    branch is a dotted-literal key) is walked into both branches -- possibly
    nested -- so every literal key an operator
    can actually observe at runtime is discovered, not only whichever branch
    happens to sit as a plain ``Constant``. Without this, only the branch the
    regex/AST scanner happens to see first is ever enrolled, and the other
    branch's key is invisible to every downstream parity/coverage audit.
    """
    if not node.args:
        return
    _collect_conditional_dotted_literal(node.args[0], findings)


def _collect_conditional_dotted_literal(node: ast.expr, findings: set[str]) -> None:
    """Recursively collect dotted-literal keys from a (possibly ternary) expression."""
    if isinstance(node, ast.IfExp):
        _collect_conditional_dotted_literal(node.body, findings)
        _collect_conditional_dotted_literal(node.orelse, findings)
        return
    value = _dotted_literal_value(node)
    if value is not None:
        findings.add(value)


_KEY_PREFIX_RE = re.compile(r"^\w+(?:\.\w+)*\.$", re.UNICODE)
"""An f-string literal head qualifies as a key prefix when it ends in a
dot and carries at least one word segment before it (e.g. ``topic.``,
``cli.registry.metrics.``)."""


def _extract_fstring_prefixes(tree: ast.AST) -> set[str]:
    """Walk f-string literals and emit ``<prefix>.*`` namespace markers.

    Walks every f-string literal whose leading segment matches the
    dotted-key shape and emits ``<prefix>.*`` namespace markers.

    Covers both inline call sites (``tr(f"cli.registry.metrics.{x}")``)
    and the assignment form (``key = f"wizard.errors.{reason}"``)
    that the runtime then passes to a downstream call.

    The head literal must end in a dot — that's the explicit
    key-segment marker. ``f"topic.{slug}.title"`` qualifies because
    the head ``topic.`` ends in a dot; ``f"plain text {value}"``
    does not.
    """
    findings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        if not node.values:
            continue
        head = node.values[0]
        if not isinstance(head, ast.Constant) or not isinstance(head.value, str):
            continue
        if not _KEY_PREFIX_RE.match(head.value):
            continue
        prefix = head.value.rstrip(".")
        if not _is_dynamic_translation_prefix(prefix):
            continue
        findings.add(f"{prefix}.*")
    return findings


def _extract_concat_prefixes(tree: ast.AST) -> set[str]:
    """Walk string-concatenation call sites and emit literal-prefix ``.*`` markers.

    Walks ``tr(<literal> + <expr>)`` and ``t(<literal> + <expr>)``
    concatenations and emits the literal-prefix ``.*`` marker.

    Matches the dynamic-key pattern ``tr("cli.registry.metrics." + key)``
    where the literal carries the registered key prefix.
    """
    findings: set[str] = set()
    tr_names = _translation_call_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in tr_names:
            continue
        for argument in node.args:
            prefix = _concat_prefix_marker(argument)
            if prefix is not None:
                findings.add(prefix)
    return findings


def _concat_prefix_marker(argument: ast.expr) -> str | None:
    """Return the ``<prefix>.*`` marker for a ``"<literal>" + <expr>`` arg, or None."""
    if not isinstance(argument, ast.BinOp) or not isinstance(argument.op, ast.Add):
        return None
    left = argument.left
    if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
        return None
    literal = left.value.rstrip(".")
    if not _is_dotted_literal(literal):
        return None
    if len(literal.split(".")) < _KEY_PATTERN_PREFIX_MIN_PARTS:
        return None
    if not _is_dynamic_translation_prefix(literal):
        return None
    return f"{literal}.*"


_UNSCANNED_MODULE_NAMES: frozenset[str] = frozenset({"test_parity.py", "manager.py", "_ast_scanner.py"})
"""Modules whose dotted string literals describe the scan itself, not call sites."""


def declares_locale_keys(module: Path) -> bool:
    """Return True when ``module`` is a source file the key scan reads.

    Shared by the tree walk below and by the change-scoped scan, so a module the
    tree ignores can never be judged as an added or orphaned call site by the
    other. Two independent copies of this predicate would let one scanner see a
    key the other cannot.
    """
    if module.name in _UNSCANNED_MODULE_NAMES:
        return False
    return not (module.name.startswith("test_") or module.name.startswith("_test_") or "/tests/" in module.as_posix())


def _parse_module_source(source: str, filename: str) -> ast.Module | None:
    """Parse ``source``, debug-logging and swallowing a syntax failure."""
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as exc:
        _log.debug("locale ast scan: parse failure %s (%s)", filename, exc)
        return None


def scan_source_text(source: str, *, filename: str) -> set[str]:
    """Emit the concrete dotted locale keys one module's source text declares.

    The text form of :func:`scan_source_tree`, for callers holding a revision's
    content rather than a working-tree file: comparing a module's key set before
    and after a change is what makes a co-landing check possible at all.
    Unparseable source yields an empty set, exactly as the tree walk skips it.
    """
    tree = _parse_module_source(source, filename)
    if tree is None:
        return set()
    return _extract_error_constructor_keys(tree) | _extract_locale_constant_keys(tree)


def scan_namespace_markers_in_text(source: str, *, filename: str) -> set[str]:
    """Emit the dynamic-namespace markers one module's source text declares."""
    tree = _parse_module_source(source, filename)
    if tree is None:
        return set()
    return _extract_fstring_prefixes(tree) | _extract_concat_prefixes(tree)


def _iter_parseable_python_modules(root: Path) -> Iterator[tuple[Path, ast.Module]]:
    """Yield ``(path, tree)`` pairs of parseable Python ASTs under ``root``.

    Every module this cannot read is ANNOUNCED. Three silences stacked here: a
    lenient decode dropped undecodable bytes so the text scanned was not the
    file, a read failure was logged at debug level, and a parse failure was
    swallowed the same way. All three shrink the set of DECLARED keys, and a
    key that is never seen declared looks unused - which is how a cleanup sweep
    deletes a live translation.

    That is not hypothetical for this scanner: four unknown key factories once
    put seventy-seven catalogue entries on the deletion path. Measured now:
    2119 modules declare locale keys, none undecodable and none unparsable.
    """
    skipped: list[str] = []
    for module in iter_directory(root, pattern="*.py", recursive=True):
        if not declares_locale_keys(module):
            continue
        try:
            source = module.read_text(encoding=_UTF_8)
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append(f"{module}: {type(exc).__name__}: {exc}")
            continue
        tree = _parse_module_source(source, str(module))
        if tree is None:
            skipped.append(f"{module}: does not parse")
            continue
        yield module, tree
    report_unread(
        "locale ast scan",
        "the keys they declare are absent from this scan and would look unused to a cleanup sweep",
        skipped,
    )


def scan_source_tree(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit concrete dotted locale keys.

    Concrete keys are literal translation keys passed to error
    constructors (positional first argument or ``message_key=`` kwarg).
    Dynamic namespaces (f-string and concatenation patterns) are
    returned by :func:`scan_namespace_markers` and routed through a
    separate parity check that asserts at least one concrete locale
    entry exists under each declared namespace prefix.
    """
    findings: set[str] = set()
    for _module, tree in _iter_parseable_python_modules(root):
        findings.update(_extract_error_constructor_keys(tree))
        findings.update(_extract_locale_constant_keys(tree))
    return findings


def scan_namespace_markers(root: Path) -> set[str]:
    """Walk ``root`` for `.py` files and emit dynamic-namespace markers.

    A namespace marker is a ``<prefix>.*`` string identifying a
    family of keys whose tail is computed at runtime (f-string
    interpolation or string concatenation). Each marker passes the
    parity check when at least one concrete locale key starts with
    its prefix.
    """
    findings: set[str] = set()
    for _module, tree in _iter_parseable_python_modules(root):
        findings.update(_extract_fstring_prefixes(tree))
        findings.update(_extract_concat_prefixes(tree))
    return findings


_UPPER_CONSTANT_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""Python constant-naming shape: all-uppercase letters, digits, underscores."""


def tr_constant_naming_violations_in_tree(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, constant_name)`` for a scanner-invisible ``tr(CONSTANT)`` site.

    The regex/AST scanners above resolve a ``tr(...)``/``t(...)`` call site's
    key two ways: a literal string argument (:func:`_dotted_literal_value`), or
    a bare reference to a module-level constant whose OWN NAME ends in
    ``_LOCALE_KEY``/``_LOCALE_KEYS`` (:func:`_extract_locale_constant_keys`,
    keyed on :func:`_declares_locale_key_constant`). A third shape slips past
    both: ``tr(SOME_CONSTANT)`` where ``SOME_CONSTANT`` is plainly a
    module/class-level constant by its ALL-CAPS shape, but its name carries
    none of the required suffixes. Neither resolver finds it — the call site
    is not a literal, and the constant's declaration is invisible to
    :func:`_declares_locale_key_constant` because its name does not match.
    The key becomes entirely invisible to the coverage/parity audit: a typo,
    an orphaned removal, or a missing catalogue entry on that key raises
    nothing, because the scanner never knew the key existed.

    This closes the gap by holding the CALL SITE to the same naming contract
    the DECLARATION side already enforces: any argument that looks like a
    constant reference (``^[A-Z][A-Z0-9_]*$``) must carry a
    :data:`_LOCALE_KEY_CONSTANT_SUFFIXES` suffix. A lowercase or mixed-case
    name (a local variable, loop variable, or function parameter) is a
    genuinely dynamic runtime value, not a static constant, and is out of
    scope for this check — the same distinction the naming-convention rule
    itself draws.

    Scope boundary (deliberate, not an oversight): this check is about the
    KEY EXPRESSION at the Python call site — whether ``tr()``'s argument is a
    literal the scanner can see, or a named constant whose OWN IDENTIFIER
    hides the key from every literal-key scan. It never inspects, resolves,
    or has any opinion about the STRING VALUE a locale catalogue stores under
    that key. Whether a translated value is legitimately identical across
    locales (a bare regulatory acronym such as ``IVA``/``IRPF``, a Spanish
    product noun, a bare interpolation placeholder, a literal CLI command) is
    a distinct concern owned entirely by the ``_intentional_identical.json``
    allowlist and its honesty gate — this function does not read locale
    catalogue files at all, so the two mechanisms cannot collide.
    """
    tr_names = _translation_call_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in tr_names:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Name):
            continue
        if not _UPPER_CONSTANT_NAME_RE.match(first.id):
            continue
        if first.id.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES):
            continue
        yield node.lineno, first.id


def find_tr_constant_naming_violations(root: Path) -> list[str]:
    """Walk ``root`` for `.py` files and return formatted naming violations.

    Each returned entry is a ``path:line: 'CONSTANT_NAME'`` string naming a
    ``tr(CONSTANT_NAME)``/``t(CONSTANT_NAME)`` call site whose constant does
    not carry the ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix required for the
    declaration-side scanner to resolve it. See
    :func:`tr_constant_naming_violations_in_tree` for the full rationale.
    """
    violations: list[str] = []
    for module, tree in _iter_parseable_python_modules(root):
        for lineno, name in tr_constant_naming_violations_in_tree(tree):
            violations.append(f"{module}:{lineno}: {name!r}")
    return violations


def dict_constant_naming_violations_in_tree(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, constant_name)`` for an un-suffixed locale-key dict.

    The DECLARATION-side counterpart to
    :func:`tr_constant_naming_violations_in_tree`. That function holds a
    ``tr(CONSTANT)`` CALL SITE to the naming contract the declaration side
    already enforces; this one holds the DECLARATION itself to the same
    contract when it is a dict literal shaped as a locale-key registry AND
    actually read into a translator sink
    (:func:`_flow_confirmed_locale_key_dicts`) but named without the
    required suffix.

    Key DISCOVERY already resolves such a dict's values structurally —
    :func:`_extract_locale_constant_keys` matches the same flow-confirmed
    set, not only by name — so this is a naming HAZARD gate, not a discovery
    feed: an un-suffixed but confirmed dict is exactly the concealed form
    that let a status-token-to-key mapping orphan invisibly in production
    (the constant carried neither the suffix nor a literal ``tr()`` call
    site, so every downstream coverage/parity audit had no signal at all).
    Flagging the declaration surfaces the hazard to a human even though
    discovery no longer depends on the rename.

    Only a MODULE-LEVEL bare ``Name`` target is considered (a direct child
    of the tree's top-level ``body``, matching :func:`ast.Module`'s own
    statement list) — a dict-literal local variable declared and consumed a
    few lines apart inside one function is visibly connected to its own use
    at a glance and is not the "invisible at a distance" hazard class a
    module constant referenced from elsewhere in the file represents; a
    tuple-unpacking or attribute target likewise cannot be a module-level
    locale-key registry by this project's convention (matching
    :func:`_declares_locale_key_constant`).
    """
    flow_confirmed = _flow_confirmed_locale_key_dicts(tree)
    body = getattr(tree, "body", ())
    for node in body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if not isinstance(target, ast.Name) or flow_confirmed.get(target.id) is not value:
            continue
        if target.id.endswith(_LOCALE_KEY_CONSTANT_SUFFIXES):
            continue
        yield node.lineno, target.id


def find_dict_constant_naming_violations(root: Path) -> list[str]:
    """Walk ``root`` for `.py` files and return formatted dict-naming violations.

    Each returned entry is a ``path:line: 'CONSTANT_NAME'`` string naming a
    dict-literal locale-key registry whose declared name does not carry the
    ``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix. See
    :func:`dict_constant_naming_violations_in_tree` for the full rationale.
    """
    violations: list[str] = []
    for module, tree in _iter_parseable_python_modules(root):
        for lineno, name in dict_constant_naming_violations_in_tree(tree):
            violations.append(f"{module}:{lineno}: {name!r}")
    return violations


__all__ = [
    "declares_locale_keys",
    "find_dict_constant_naming_violations",
    "find_tr_constant_naming_violations",
    "scan_namespace_markers",
    "scan_namespace_markers_in_text",
    "scan_source_text",
    "scan_source_tree",
]

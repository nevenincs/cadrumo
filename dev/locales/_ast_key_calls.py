"""Collect locale keys declared by translator and typed constructor call sites."""

from __future__ import annotations

import ast

from ._ast_key_policy import _COMMAND_SPEC_KEY_FACTORIES, _TRANSLATION_KEY_KWARGS
from ._ast_key_syntax import (
    _callee_name,
    _collect_dotted_literals,
    _dotted_literal_value,
    _is_dynamic_translation_prefix,
    _unwrapped_key_literal,
    _walk_nodes,
)


def _extract_error_constructor_keys(tree: ast.AST, extra_translators: frozenset[str] = frozenset()) -> set[str]:
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
    tr_names = _translation_call_names(tree) | extra_translators
    for node in _walk_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            _collect_kwonly_default_keys(node, findings)
        elif isinstance(node, ast.Call):
            _collect_call_site_keys(node, findings, tr_names)
    return findings


def _translation_call_names(tree: ast.AST) -> frozenset[str]:
    """Return every local name that resolves to the ``tr`` / ``t`` translator.

    Always includes the canonical ``tr`` / ``t`` names, plus any module-local
    alias introduced by an aliased import (``from ...core.i18n.render import tr as
    _tr`` - the underscore-aliased module-level import convention). Without
    alias resolution an aliased call site like ``_tr("cli.root.verbose_help")``
    is invisible to the scanner, so its genuinely-live locale keys are wrongly
    reported as orphans and pruned.
    """
    names = {"tr", "t"}
    for node in _walk_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in {"tr", "t"} and alias.asname:
                    names.add(alias.asname)
    return frozenset(names)


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
                collect_build_entry_argument(kw, exprs)
    for kw in node.keywords:
        if kw.arg in _TRANSLATION_KEY_KWARGS:
            exprs.append(kw.value)
    return exprs


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
        # Recurse rather than reading one literal: a key is routinely
        # supplied conditionally -- `empty_key="..." if not rows else None` --
        # and the parameter is DECLARED to take a key, so any dotted literal
        # that can reach it is one.
        _collect_dotted_literals(kw.value, findings)


def _collect_build_entry_keys(node: ast.Call, findings: set[str]) -> None:
    """Pick up portal-catalogue translation keys passed to ``build_entry``.

    :mod:`domain.portals._entries` modules construct each portal entry
    through :func:`domain.portals._entries .common.build_entry`, passing the
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


def collect_build_entry_argument(kw: ast.keyword, exprs: list[ast.expr]) -> None:
    """Collect build entry argument."""
    if kw.arg in {"label", "purpose"}:
        exprs.append(kw.value)
    elif kw.arg == "notes" and isinstance(kw.value, ast.Tuple | ast.List):
        exprs.extend(kw.value.elts)

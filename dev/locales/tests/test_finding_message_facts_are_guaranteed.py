"""Every finding template interpolates only facts its producer always supplies.

``tr()`` does not raise on a missing fact. It leaves the placeholder in place,
so a template naming a fact the producer supplies only on some branches hands
the operator a literal ``%{binding_id}`` in exactly the case where there is no
binding. The data and the call path each look fine alone; only rendering them
together shows the defect, which is why this gate renders rather than reading
the catalogue.

The guaranteed fact set is derived from the LIVE producers by walking the
source, never from an inventory declared here: a list would go stale the moment
someone adds a branch, and a stale list is what lets the next such key ship. A
fact assigned conditionally (``facts["binding_id"] = ...`` under an ``if``) is
NOT guaranteed, and neither is one supplied at some call sites of a shared
finding factory but not others -- those two shapes are where every instance of
this defect has hidden.

The gate refuses to pass vacuously: a construction whose facts cannot be
resolved statically fails here rather than being skipped, because a skipped
construction is indistinguishable from a clean one.
"""

from __future__ import annotations

import ast

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n import tr

from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The domain model whose constructions carry a locale key plus its typed facts.
_FINDING_CLASS = "ModeloVerificationFinding"

#: Rendered in place of every guaranteed fact. Distinctive so a template that
#: accidentally matches it is visible, and short so a bounded field cannot trip.
_FACT_VALUE = "FACTVALUE"

#: What an unrendered placeholder looks like once it reaches the operator.
_PLACEHOLDER_OPEN = "%{"


class _UnresolvedFactsError(Exception):
    """Raised when a construction's fact set cannot be read from the source."""


def _dict_literal_keys(node: ast.expr) -> tuple[set[str], list[str]]:
    """Return (literal string keys, names splatted in) for a dict literal."""
    if not isinstance(node, ast.Dict):
        raise _UnresolvedFactsError("message_facts is not a dict literal")
    keys: set[str] = set()
    splats: list[str] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            if not isinstance(value, ast.Name):
                raise _UnresolvedFactsError("splat of a non-name expression")
            splats.append(value.id)
        elif isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        else:
            raise _UnresolvedFactsError("non-literal fact key")
    return keys, splats


def _enclosing_function(module: ast.Module, target: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(
            child is target for child in ast.walk(node)
        ):
            return node
    raise _UnresolvedFactsError("construction sits outside any function")


def _conditionally_assigned(function: ast.AST, name: str) -> set[str]:
    """Return keys assigned as ``name["k"] = ...`` inside a conditional branch."""
    conditional: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.If | ast.Try | ast.For | ast.While):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Assign)
                and len(inner.targets) == 1
                and isinstance(target := inner.targets[0], ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == name
                and isinstance(target.slice, ast.Constant)
                and isinstance(target.slice.value, str)
            ):
                conditional.add(target.slice.value)
    return conditional


def _local_dict_keys(function: ast.AST, name: str) -> set[str]:
    """Return the literal keys of the dict ``name`` is bound to in ``function``."""
    for node in ast.walk(function):
        value = getattr(node, "value", None)
        if not isinstance(node, ast.Assign | ast.AnnAssign) or not isinstance(value, ast.Dict):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                keys, splats = _dict_literal_keys(value)
                if splats:
                    raise _UnresolvedFactsError(f"local dict {name} splats {splats}")
                return keys
    raise _UnresolvedFactsError(f"no dict literal bound to {name}")


def _facts_at_call_sites(module: ast.Module, function_name: str) -> set[str]:
    """Return facts present at EVERY call site of a shared finding factory.

    Intersected, not unioned: a fact supplied by only some callers is exactly
    the ``country_code`` shape, guaranteed nowhere and safe to interpolate
    nowhere.
    """
    per_call: list[set[str]] = []
    for node in ast.walk(module):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function_name):
            continue
        for keyword in node.keywords:
            if keyword.arg == "message_facts":
                keys, splats = _dict_literal_keys(keyword.value)
                if splats:
                    raise _UnresolvedFactsError(f"call site of {function_name} splats {splats}")
                per_call.append(keys)
    if not per_call:
        raise _UnresolvedFactsError(f"no resolvable call site of {function_name}")
    return set.intersection(*per_call)


def _guaranteed_facts(module: ast.Module, call: ast.Call, facts: ast.expr) -> set[str]:
    """Resolve the facts this construction supplies on EVERY path that reaches it."""
    if isinstance(facts, ast.Name):
        function = _enclosing_function(module, call)
        return _local_dict_keys(function, facts.id) - _conditionally_assigned(function, facts.id)
    keys, splats = _dict_literal_keys(facts)
    for splat in splats:
        function = _enclosing_function(module, call)
        parameters = {argument.arg for argument in [*function.args.args, *function.args.kwonlyargs]}
        if splat not in parameters:
            raise _UnresolvedFactsError(f"splat {splat} is not a parameter")
        keys |= _facts_at_call_sites(module, function.name)
    return keys


def _producer_sites() -> list[tuple[str, set[str], str]]:
    """Return (locale_key, guaranteed_facts, source_locator) for every producer."""
    sites: list[tuple[str, set[str], str]] = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        if "tests" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == _FINDING_CLASS
            ):
                continue
            locale_key: str | None = None
            facts: ast.expr | None = None
            for keyword in node.keywords:
                if keyword.arg == "message_locale_key" and isinstance(keyword.value, ast.Constant):
                    locale_key = keyword.value.value
                if keyword.arg == "message_facts":
                    facts = keyword.value
            locator = f"{path.relative_to(SRC_DIR).as_posix()}:{node.lineno}"
            if locale_key is None:
                pytest.fail(f"{locator}: {_FINDING_CLASS} built without a literal message_locale_key")
            if facts is None:
                sites.append((locale_key, set(), locator))
                continue
            try:
                sites.append((locale_key, _guaranteed_facts(module, node, facts), locator))
            except _UnresolvedFactsError as exc:
                pytest.fail(
                    f"{locator}: cannot resolve the facts guaranteed for {locale_key!r} ({exc}). "
                    "This gate must not skip a construction it cannot read: an unreadable one is "
                    "indistinguishable from a clean one.",
                )
    return sites


def test_the_gate_reaches_the_live_producers() -> None:
    """Anti-vacuity: a walk that found nothing would pass every assertion below."""
    sites = _producer_sites()

    assert sites, f"no {_FINDING_CLASS} construction found under {SRC_DIR}"
    assert len({key for key, _, _ in sites}) > 1, "expected several distinct finding locale keys"


def _render_failures(locale_key: str, guaranteed: set[str], locator: str) -> list[str]:
    """Render one key in every language, returning a failure line per leak."""
    supplied = dict.fromkeys(guaranteed, _FACT_VALUE)
    failures: list[str] = []
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=str(language)):
            rendered = tr(locale_key, **supplied)
        if _PLACEHOLDER_OPEN in rendered:
            leaked = rendered[rendered.index(_PLACEHOLDER_OPEN) :].split("}")[0] + "}"
            failures.append(
                f"{locator} [{language}] {locale_key}: template interpolates {leaked}, "
                f"which the producer does not always supply. Guaranteed facts: "
                f"{sorted(guaranteed) or 'none'}. Rendered: {rendered}",
            )
    return failures


def test_the_check_bites_when_a_producer_stops_supplying_a_fact() -> None:
    """Anti-vacuity: drop one real fact and the real catalogue must leak it.

    Perturbs the GUARANTEED SET rather than a tracked producer: the shipped
    catalogue and the shipped renderer stay untouched, so this proves the
    assertion fires against real data rather than against a synthetic string,
    and no source edit can be left behind in a shared tree.
    """
    sites = [(key, facts, loc) for key, facts, loc in _producer_sites() if facts]
    assert sites, "no finding supplies any fact, so this proof would be vacuous"

    proved = False
    for locale_key, guaranteed, locator in sites:
        for dropped in sorted(guaranteed):
            failures = _render_failures(locale_key, guaranteed - {dropped}, locator)
            if failures:
                assert f"%{{{dropped}}}" in failures[0], failures[0]
                proved = True
                break
        if proved:
            break

    assert proved, (
        "dropping a guaranteed fact from every finding still rendered clean, so no template "
        "interpolates any fact and this gate cannot fail for a real defect"
    )


def test_no_finding_message_renders_an_unsupplied_placeholder() -> None:
    """A template may name only facts its producer supplies on every path.

    Rendered through the real ``tr()`` in every shipped language, because the
    catalogues are translated independently and a placeholder can survive in one
    locale while the others are clean.
    """
    failures: list[str] = []
    for locale_key, guaranteed, locator in _producer_sites():
        failures.extend(_render_failures(locale_key, guaranteed, locator))
    assert not failures, "\n".join(failures)

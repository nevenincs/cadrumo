"""The wallet execute read must pass a landing rule on EVERY exit, not one.

The enrollment gate next door asks whether a driving module is wired to a
landing rule at all. It walks each ``async`` function and returns true on
the first refusal call found anywhere inside it -- which is the right
question for "is this module enrolled" and one notch short of "does every
path through it run a rule". Its own docstring names the principle: a
module can carry a perfectly good landing rule that nothing on the live
path ever calls, and that module is exactly as unguarded as one with no
rule at all. A call nested in a branch satisfies that scan while leaving
its sibling branches unguarded.

That is what this gate adds, for the one function where it mattered.
``_submit_wallet_execute_gate_if_present`` is the funnel both wallet
traversals reach, and its landing rule used to sit inside the
``wallet-execute-submit-present`` arm. ``wallet_execute_gate_status``
returns four values, so the other three -- ``no-wallet-form`` above all,
what a page carrying no wallet form yields, including AEAT's
acting-capacity gate -- returned having run no landing rule. The parser
refused those pages anyway for want of a wallet table, so nothing was read
that should not have been; but it reported a changed external shape where
the truth was an undeclared landing.

WHAT THIS GATE DOES NOT PROVE, twice over. It asserts CALL-SITE POSITION,
never runtime reachability: a call at statement level is unconditional by
construction, but this scan cannot show the function was entered, nor that
Playwright served what the rule then read. The driver proofs and the live
capture are the primary wall; this is the weaker, cheaper half. And it is
the mirror of the enrollment gate's own admitted blind spot -- that scan
cannot see a control drive hidden inside a ``page.evaluate`` JS string, as
``_walker.py`` does, while this one cannot see whether a well-placed call
is reached. Two views of one weakness. A reader who knows both is better
placed than one who trusts either.

A structural assertion also fails vacuously the moment its subject is
renamed: "no refusal call is nested in a branch" is trivially true of a
function that calls no refusal at all. So the presence of the call is
pinned FIRST, and the position asserted only after.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_WALLET_MODULE = Path(__file__).resolve().parent.parent / "iva_compensation_wallet.py"
_GUARDED_FUNCTION = "_submit_wallet_execute_gate_if_present"
_LANDING_REFUSAL = "_assert_read_landing"


def _guarded_function() -> ast.AsyncFunctionDef:
    tree = ast.parse(_WALLET_MODULE.read_text(encoding="utf-8"), filename=str(_WALLET_MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == _GUARDED_FUNCTION:
            return node
    message = f"{_GUARDED_FUNCTION} is not an async function in {_WALLET_MODULE.name}"
    raise AssertionError(message)


def _landing_refusal_calls(node: ast.AST) -> list[ast.Call]:
    return [
        inner
        for inner in ast.walk(node)
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == _LANDING_REFUSAL
    ]


def _statement_level_calls(function: ast.AsyncFunctionDef) -> list[ast.Call]:
    """Return the refusal calls that are direct statements of the function body.

    A call in this list runs on every path that enters the function, because
    nothing in the body precedes it conditionally. A refusal reached only
    inside an ``if`` / ``try`` / loop body is excluded by construction, which
    is exactly the shape this gate exists to reject.
    """
    calls: list[ast.Call] = []
    for statement in function.body:
        if not isinstance(statement, ast.Expr):
            continue
        calls.extend(_landing_refusal_calls(statement))
    return calls


class TestTheSubjectIsStillThere:
    """Pinned first, so the position assertion below cannot pass vacuously."""

    def test_the_wallet_module_exists(self) -> None:
        assert _WALLET_MODULE.is_file(), _WALLET_MODULE

    def test_the_guarded_function_is_found(self) -> None:
        assert _guarded_function().name == _GUARDED_FUNCTION

    def test_the_function_calls_a_landing_refusal_at_all(self) -> None:
        """Renaming the refusal must red this gate, not silently satisfy it."""
        assert _landing_refusal_calls(_guarded_function()), (
            f"{_GUARDED_FUNCTION} calls no {_LANDING_REFUSAL}; the position assertion "
            f"below would pass vacuously. If the refusal was renamed, update "
            f"_LANDING_REFUSAL; if it was removed, this gate is the reason not to."
        )

    def test_the_detector_can_tell_nested_from_statement_level(self) -> None:
        """The instrument must distinguish the two shapes, or it decides nothing."""
        nested = ast.parse("async def f():\n    if x:\n        _assert_read_landing(page)\n")
        flat = ast.parse("async def f():\n    _assert_read_landing(page)\n")
        nested_fn = next(n for n in ast.walk(nested) if isinstance(n, ast.AsyncFunctionDef))
        flat_fn = next(n for n in ast.walk(flat) if isinstance(n, ast.AsyncFunctionDef))
        assert _landing_refusal_calls(nested_fn), "the call detector must see a nested call"
        assert not _statement_level_calls(nested_fn), "a nested call must NOT count as statement level"
        assert _statement_level_calls(flat_fn), "a statement-level call must count"


class TestEveryExitPassesALandingRule:
    def test_a_landing_refusal_runs_unconditionally(self) -> None:
        """At least one refusal is a direct statement of the function body.

        Before this was enforced the only refusal sat inside the
        ``wallet-execute-submit-present`` branch, so a page carrying no
        wallet form returned with none run.
        """
        assert _statement_level_calls(_guarded_function()), (
            f"{_GUARDED_FUNCTION} reaches {_LANDING_REFUSAL} only inside a branch, so at "
            f"least one exit returns without a landing rule. Hoist a call to statement "
            f"level; do NOT instead admit the landing to the read-path allow-list."
        )

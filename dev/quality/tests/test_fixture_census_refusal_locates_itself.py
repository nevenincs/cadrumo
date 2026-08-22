"""A census refusal names the module it is refusing.

The fixture census refuses a fixture whose effective name it cannot state
statically, which is the right call -- inventing a value would make the
ownership manifest a guess. It reported that refusal as:

    fixture name at line 87 is dynamic; static census cannot state its
    effective value

A line number with no file does not locate anything in the 5,773 modules the
census scans. Establishing that empirically took six probes and still failed:
a text scan of line 87 across every scanned root found nothing, because the
census reports the FUNCTION's line while the decorator sits a line above it;
and a subtree bisect reported nothing at all, because the census refuses a root
carrying no ``conftest.py`` and the probe's filter swallowed that refusal as
"not the error I am looking for". The instrument observed nothing and said so
in exactly the way a clean result does.

With the module named, the same run answers immediately:

    src/cadrumo/tests/seeded_isolated_backend_fixture.py:87: fixture name is
    dynamic; static census cannot state its effective value

That fixture factory derives its name -- ``origin_name = f"{name}_origin"`` --
from its own parameter, so the value genuinely is a call-site fact. Whether the
census should DEFER such a derived name the way it already defers a bare
parameter is a separate question about the census's model, and this module does
not answer it. It only requires that the refusal say where to look.
"""

from __future__ import annotations

import ast

import pytest

from ..fixture_census import FixtureCensusError, _literal_bool, _literal_string

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WHERE = "src/cadrumo/tests/some_fixture_factory.py"


def _dynamic_expression() -> ast.expr:
    """An expression the census cannot reduce to a literal."""
    return ast.parse('f"{name}_origin"', mode="eval").body


def test_a_dynamic_name_refusal_names_its_module() -> None:
    """DISCRIMINATING: a line number alone does not locate anything."""
    with pytest.raises(FixtureCensusError) as caught:
        _literal_string(_dynamic_expression(), field="name", line=87, where=_WHERE)

    assert _WHERE in str(caught.value)
    assert "87" in str(caught.value)


def test_a_dynamic_autouse_refusal_names_its_module() -> None:
    """The sibling helper refuses the same way, so neither is the unlocatable one."""
    with pytest.raises(FixtureCensusError) as caught:
        _literal_bool(_dynamic_expression(), field="autouse", line=12, default=False, where=_WHERE)

    assert _WHERE in str(caught.value)


def test_a_literal_value_is_still_returned_unchanged() -> None:
    """ANTI-TAUTOLOGY: locating the refusal must not make everything refuse.

    A helper that raised regardless would satisfy both assertions above while
    failing the census on every fixture in the tree.
    """
    literal = ast.parse('"_isolated_backend"', mode="eval").body

    assert _literal_string(literal, field="name", line=1, where=_WHERE) == "_isolated_backend"
    assert _literal_bool(ast.parse("True", mode="eval").body, field="autouse", line=1, default=False, where=_WHERE)


def test_a_bare_parameter_is_still_deferred_to_the_call_site() -> None:
    """The factory carve-out must survive: a parameter name is not-yet-known, not dynamic.

    Refusing it would report every correctly-written fixture factory as
    unmeasurable, which is the failure the deferral exists to prevent.
    """
    deferred = frozenset({"name"})
    parameter = ast.parse("name", mode="eval").body

    assert _literal_string(parameter, field="name", line=1, where=_WHERE, deferred_names=deferred) is None

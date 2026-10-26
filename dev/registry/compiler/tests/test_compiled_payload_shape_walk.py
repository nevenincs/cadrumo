"""Detector teeth for the compiled-cache structural shape walk.

The walk is what keeps a pickle written against an older model shape from being
served as the compiled authority. Its correctness is entirely about REACH: a
stale object hidden one container deeper than the walk descends is served
silently, and the defect surfaces much later as an ``AttributeError`` inside a
calculation. These cases pin the reach at each container kind the compiled
payload actually uses, and pin the scalar bail-out that makes the walk cheap to
being unable to skip a container.
"""

from __future__ import annotations

import datetime
import decimal
from collections.abc import Callable, Mapping

import pytest
from pydantic import BaseModel

from cadrumo.core.frozen_mapping import FrozenMapping

from .._compiled_cache import _INERT_LEAF_TYPES, _has_current_pydantic_shape

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Leaf(BaseModel):
    """A model with one required field, standing in for any nested registry model."""

    identifier: str


class _Branch(BaseModel):
    """A model that holds another, so the walk has somewhere to descend."""

    label: str
    leaf: _Leaf


def _stale_leaf() -> _Leaf:
    """Return a ``_Leaf`` whose stored state omits a field today's schema requires.

    This is what an old pickle restores: the class resolves and ``isinstance``
    passes, but the instance never ran today's validators, so the field is simply
    absent from ``__dict__``.
    """
    leaf = _Leaf(identifier="present").model_copy()
    leaf.__dict__.pop("identifier")
    return leaf


def test_a_current_graph_of_every_container_kind_is_accepted() -> None:
    """The normal path: nothing is missing, through every container the walk knows."""
    leaf = _Leaf(identifier="present")
    assert _has_current_pydantic_shape(
        (
            _Branch(label="b", leaf=leaf),
            {"key": leaf},
            FrozenMapping({"key": leaf}),
            (leaf,),
            [leaf],
            frozenset({leaf.identifier}),
            "text",
            7,
            7.5,
            True,
            None,
            b"bytes",
            decimal.Decimal("1.5"),
            datetime.date(2026, 1, 1),
            datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC),
            datetime.time(12, 0),
        ),
    )


@pytest.mark.parametrize(
    "container",
    [
        pytest.param(lambda stale: (stale,), id="tuple"),
        pytest.param(lambda stale: [stale], id="list"),
        pytest.param(lambda stale: {"key": stale}, id="dict-value"),
        pytest.param(lambda stale: FrozenMapping({"key": stale}), id="frozen-mapping-value"),
        pytest.param(lambda stale: _Branch(label="b", leaf=stale), id="model-field"),
        pytest.param(lambda stale: ({"key": (FrozenMapping({"deep": [stale]}),)},), id="nested-through-every-kind"),
    ],
)
def test_a_stale_model_is_reached_behind_each_container(container: Callable[[_Leaf], object]) -> None:
    """Teeth: the walk must refuse wherever the stale object is hidden.

    A walk that stopped at any one of these container kinds would report the
    payload current and serve it.

    Mapping KEYS are walked by the implementation but are not a case here: a key
    must be hashable, and hashing a frozen model whose stored state is missing a
    field raises rather than producing a key, so no stale model can reach a
    mapping key to begin with. Asserting a reach that cannot be constructed would
    be a test of the plant, not of the walk.
    """
    stale = _stale_leaf()
    assert "identifier" not in stale.__dict__, "sanity: the plant must actually omit the field"
    assert _has_current_pydantic_shape((container(stale),)) is False


def test_every_exempt_type_is_one_the_walk_would_treat_as_a_leaf_anyway() -> None:
    """The bail-out may only name types the walk already descends into nothing.

    This is what keeps the fast path equivalent rather than merely faster. The
    walk descends exactly three shapes -- a Pydantic model, a mapping, and a
    tuple/list/set/frozenset -- so exempting any type that is one of those would
    silently stop the walk at it and serve a stale object nested below. Adding
    ``tuple`` to the exempt set, for instance, reds here rather than in a
    calculation months later.
    """
    descended = (BaseModel, Mapping, tuple, list, set, frozenset)
    wrongly_exempt = [exempt_type.__name__ for exempt_type in _INERT_LEAF_TYPES if issubclass(exempt_type, descended)]
    assert not wrongly_exempt, f"these exempt types are containers the walk must open: {wrongly_exempt}"


def test_the_bail_out_keys_on_the_exact_class_so_a_subclass_keeps_the_full_path() -> None:
    """A subclass of an exempt type must not be retired by the bail-out.

    The exemption is sound only for the exact types listed, whose instances hold
    no nested model. A subclass can hold anything, so it must reach the walk's
    normal dispatch; keying on ``value.__class__`` rather than ``isinstance`` is
    what secures that, and this pins it.
    """

    class _Labels(tuple[object, ...]):
        """A ``tuple`` subclass: a container whose exact class is not ``tuple``."""

    assert _Labels not in _INERT_LEAF_TYPES
    assert _has_current_pydantic_shape((_Labels((_stale_leaf(),)),)) is False

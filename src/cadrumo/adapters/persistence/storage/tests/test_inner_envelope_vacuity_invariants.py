"""Pin the two structural facts the inner-envelope equality argument rests on.

Tightening the inner-envelope check from an ordering comparison to an equality
was behaviour-identical only because the below-current region is empty, and that
emptiness is not self-evident. It is the conjunction of two facts: the envelope's
``schema_version`` carries a positive lower bound, and that bound REACHES the
lowest version any registered namespace declares. Neither is pinned anywhere
else, so a future change to either would silently turn a proven no-op into a real
behaviour change against filed taxpayer data.

The direction of the second fact matters and is easy to get backwards. Asserting
that no namespace sits below the bound is unfalsifiable — the namespace
definition's own field carries ``ge=1``, so the comparison is unsatisfiable by
construction and would report green forever. What can genuinely regress is the
bound being loosened out from under the inventory, so that is what is pinned.

Both are pinned here as RELATIONS rather than as the literal ``1``. That
distinction is load-bearing. A per-namespace version bump is a legitimate,
expected change — the durability machinery exists to support it — and a gate
written as "every namespace equals 1" would go red on a correct change, for the
wrong reason, training its reader to edit the gate rather than read it. The
inventory also does not sit on one shared constant: 66 namespaces declare the
shared secure-object constant and a 67th declares its own blob-manifest constant,
so the proof holds today on a coincidence of VALUE rather than a shared
authority. A relation survives that; an equality against a literal does not.
"""

from __future__ import annotations

import annotated_types
import pytest
from pydantic import BaseModel, Field

from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..envelope import Envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _NoLowerBound(BaseModel):
    """Stand-in whose version field carries no lower bound at all."""

    schema_version: int


class _LooseLowerBound(BaseModel):
    """Stand-in whose version field admits zero and below."""

    schema_version: int = Field(ge=-5)


def _declared_lower_bound(model: type[BaseModel], field: str) -> int:
    """Return the field's declared lower bound, refusing to invent one.

    Raising rather than defaulting is the point: a helper that fell back to a
    literal would keep reporting a healthy floor after the real constraint was
    removed, which is the failure mode this module exists to catch.
    """
    for constraint in model.model_fields[field].metadata:
        if isinstance(constraint, annotated_types.Ge):
            return int(constraint.ge)
    raise AssertionError(
        f"{model.__name__}.{field} declares no lower bound; the inner-envelope "
        "equality argument depends on one, so this is a real regression rather "
        "than a missing test fixture",
    )


def test_the_envelope_version_carries_a_positive_lower_bound() -> None:
    """Leg one: a below-current stamp must be unrepresentable, not merely unseen."""
    assert _declared_lower_bound(Envelope, "schema_version") >= 1


def test_the_envelope_bound_reaches_the_lowest_declared_namespace_version() -> None:
    """Leg two, stated so it can actually fail.

    The naive form of this test — "no namespace declares a version below the
    envelope bound" — cannot fail and is worthless: the namespace definition's
    own ``schema_version`` field carries ``ge=1``, so with the envelope bound at
    1 the comparison is unsatisfiable by construction. It would report green
    forever while proving nothing.

    The direction that can fail is the opposite one. The below-current region is
    empty because the envelope's lower bound REACHES the lowest version any
    namespace declares. Loosening that bound — to zero, to a negative, or by
    deleting the constraint — makes a below-current stamp representable, and the
    equality check then refuses payloads the old ordering comparison silently
    accepted. That is the regression this pins.
    """
    floor = _declared_lower_bound(Envelope, "schema_version")
    lowest_declared = min(definition.schema_version for definition in STORAGE_NAMESPACE_REGISTRY.namespaces)
    assert floor >= lowest_declared, (
        f"the envelope's lower bound ({floor}) no longer reaches the lowest declared "
        f"namespace schema_version ({lowest_declared}), so a below-current inner "
        "stamp is now representable; the inner-envelope equality check will refuse "
        "payloads the previous ordering comparison accepted"
    )


def test_the_namespace_inventory_is_not_empty() -> None:
    """Anti-vacuity: an empty registry would pass the relation above trivially."""
    assert len(STORAGE_NAMESPACE_REGISTRY.namespaces) > 0


def test_the_bound_is_read_from_the_model_and_not_assumed() -> None:
    """Anti-tautology: prove the helper fails when the constraint is absent.

    Without this, a helper that quietly defaulted to 1 would keep both tests
    above green after someone removed the real constraint — the gate would be
    asserting its own assumption rather than the model's contract.
    """
    with pytest.raises(AssertionError, match="declares no lower bound"):
        _declared_lower_bound(_NoLowerBound, "schema_version")


def test_a_loosened_bound_is_reported_as_loosened() -> None:
    """The helper reports what the model says, including a bound that admits zero."""
    assert _declared_lower_bound(_LooseLowerBound, "schema_version") == -5


def test_a_loosened_envelope_bound_would_fail_the_reach_relation() -> None:
    """Prove the reach relation bites, by driving it with a loosened stand-in.

    Without this the relation could be silently unsatisfiable — the failure mode
    the naive form of it had. Here the real namespace inventory is compared
    against a model whose bound has been loosened, and the relation must break.
    """
    loosened = _declared_lower_bound(_LooseLowerBound, "schema_version")
    lowest_declared = min(definition.schema_version for definition in STORAGE_NAMESPACE_REGISTRY.namespaces)
    assert loosened < lowest_declared, (
        "the loosened stand-in no longer sits below the lowest declared namespace "
        "version, so this proof has stopped exercising the relation it guards"
    )

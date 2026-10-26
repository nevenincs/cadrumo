"""The reverse binding-to-casilla join, and the invariant its callers rest on.

``casillas_by_binding`` is the exact dual of ``bound_casilla_binding_ids``:
one answers "which bindings feed this casilla", the other "which casillas does
this binding feed". Defining the second in terms of the first is what makes
disagreement structurally impossible, so the corpus-wide transposition test
below is the load-bearing one - it would fail the moment either direction grew
a predicate the other did not.

A casilla that is not BOUND cannot carry a binding at all: the canonical schema
refuses it at construction, so the join never has to drop one.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....core.casilla_id import validated_casilla_id
from ..binding_targets import bound_casilla_binding_ids, casillas_by_binding
from ..schema import ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition
from .registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL = ("ley-37-1992:art-91",)
_SOURCE = ("aeat-dr-390-2025",)


def _casilla(
    casilla_id: str,
    *,
    number: str,
    input_kind: str,
    binding: str | None,
    alternate_bindings: tuple[str, ...] = (),
) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        localization_keys=(f"test.schema.casilla.{number}.label",),
        section=("iva", "anual"),
        input_kind=input_kind,
        binding=binding,
        alternate_bindings=alternate_bindings,
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _revision(casillas: tuple[CasillaDefinition, ...]) -> ModeloRevision:
    return ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
        casillas=casillas,
    )


def test_schema_refuses_a_bound_casilla_that_declares_no_binding() -> None:
    """The canonical schema refuses the invalid state before the join can run.

    A BOUND casilla with no binding is a registry declaration error. Keeping the
    proof at model construction exercises the real public boundary instead of
    bypassing Pydantic validation to manufacture an impossible join input.
    """
    with pytest.raises(ValidationError, match="must declare binding"):
        _casilla(
            validated_casilla_id("01", surface="test.dual.bound_without_binding"),
            number="01",
            input_kind="bound",
            binding=None,
        )


def test_schema_refuses_a_primary_binding_repeated_as_an_alternate() -> None:
    """The reverse join receives only canonical, non-duplicated binding axes."""
    with pytest.raises(ValidationError, match="must not repeat primary binding"):
        _casilla(
            validated_casilla_id("03", surface="test.dual.duplicate"),
            number="03",
            input_kind="bound",
            binding="m390-total",
            alternate_bindings=("m390-total",),
        )


def test_alternate_bindings_reach_the_mapping() -> None:
    """A casilla reached only through an alternate is still that binding's money."""
    casilla_id = validated_casilla_id("04", surface="test.dual.alternate")
    revision = _revision(
        (
            _casilla(
                casilla_id,
                number="04",
                input_kind="bound",
                binding="m390-primary",
                alternate_bindings=("m390-equivalent",),
            ),
        )
    )

    mapping = casillas_by_binding(revision)

    assert mapping == {"m390-primary": (casilla_id,), "m390-equivalent": (casilla_id,)}


def test_the_dual_transposes_the_forward_primitive_across_the_whole_corpus() -> None:
    """The two directions cannot disagree, checked against every bundled revision.

    This is the property the reverse join exists to guarantee, and it is checked
    against registry-authoritative data rather than a fixture, so a predicate
    added to either direction alone reds here.
    """
    checked_revisions = 0
    checked_pairs = 0

    for definition in bundled_registry_tree()[0]:
        modelo_id = definition.id
        for revision in definition.revisions.values():
            expected: dict[str, list[str]] = {}
            for casilla in revision.casillas:
                for binding_id in bound_casilla_binding_ids(casilla):
                    populated_by = expected.setdefault(binding_id, [])
                    if casilla.id not in populated_by:
                        populated_by.append(casilla.id)
                        checked_pairs += 1

            assert casillas_by_binding(revision) == {
                binding_id: tuple(casilla_ids) for binding_id, casilla_ids in expected.items()
            }, f"M{modelo_id}/{revision.id}: the dual disagrees with the forward primitive"
            checked_revisions += 1

    assert checked_revisions >= 90, (
        f"only {checked_revisions} revisions were compared; the corpus carries 94, so this "
        "assertion passed vacuously over a truncated corpus rather than proving the transposition"
    )
    assert checked_pairs > 0, "no bound casilla was reached at all, so the comparison proved nothing"

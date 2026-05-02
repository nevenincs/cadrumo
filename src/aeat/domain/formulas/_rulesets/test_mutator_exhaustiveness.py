"""Orphan-node defense for the mutation harness.

Every concrete subclass of :class:`aeat.domain.formulas._formula.Formula`
and every concrete operand subclass of
:class:`aeat.domain.formulas._formula.Operand` must appear in exactly
one of:

- :data:`aeat.domain.formulas._rulesets._mutators.MUTATOR_REGISTRY` —
  the type owns a mutator class.
- :data:`aeat.domain.formulas._rulesets._mutators.NOT_MUTABLE_NODE_TYPES`
  — the type is documented as intentionally not mutable, with a
  justifying reason.

If a future contributor adds a new ``Formula`` subclass to
:mod:`aeat.domain.formulas` without updating one of the two sets, the
exhaustiveness test fails loudly. This is the only mechanism preventing
silent gaps in the harness's coverage of the AST.
"""

from __future__ import annotations

import pytest

from .. import (
    AddFormula,
    BracketsFormula,
    ClampPositiveFormula,
    DivFormula,
    FormulaCasillaRef,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
)
from ._mutators import (
    MUTATOR_REGISTRY,
    NOT_MUTABLE_NODE_TYPES,
    all_concrete_formula_types,
    all_concrete_operand_types,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_PUBLIC_FORMULA_TYPES: frozenset[type] = frozenset(
    {
        AddFormula,
        SubFormula,
        MulFormula,
        DivFormula,
        MinFormula,
        MaxFormula,
        ClampPositiveFormula,
        PercentFormula,
        BracketsFormula,
        RoundFormula,
    }
)


_PUBLIC_OPERAND_TYPES: frozenset[type] = _PUBLIC_FORMULA_TYPES | frozenset({Literal, FormulaCasillaRef, ParamRef})


def test_concrete_formula_types_match_public_export() -> None:
    """Sanity check: ``all_concrete_formula_types`` matches ``aeat.domain.formulas.Formula``."""
    enumerated = frozenset(all_concrete_formula_types())
    assert enumerated == _PUBLIC_FORMULA_TYPES, (
        f"_mutators.all_concrete_formula_types is out of sync with "
        f"aeat.domain.formulas.Formula. Missing from registry: "
        f"{_PUBLIC_FORMULA_TYPES - enumerated!r}; extra: "
        f"{enumerated - _PUBLIC_FORMULA_TYPES!r}"
    )


def test_concrete_operand_types_match_public_export() -> None:
    """Sanity check: ``all_concrete_operand_types`` matches ``aeat.domain.formulas.Operand``."""
    enumerated = frozenset(all_concrete_operand_types())
    assert enumerated == _PUBLIC_OPERAND_TYPES


def test_every_concrete_operand_is_either_mutated_or_documented() -> None:
    """Every concrete Operand subclass appears in exactly one set."""
    registered = frozenset(MUTATOR_REGISTRY.keys())
    not_mutable = frozenset(NOT_MUTABLE_NODE_TYPES.keys())

    union = registered | not_mutable
    missing = _PUBLIC_OPERAND_TYPES - union
    extra = union - _PUBLIC_OPERAND_TYPES
    assert not missing, (
        f"orphan operand subclass(es) {missing!r}: add either a "
        f"mutator entry to MUTATOR_REGISTRY or a documented reason to "
        f"NOT_MUTABLE_NODE_TYPES in `_mutators.py`."
    )
    assert not extra, (
        f"unexpected entry/entries {extra!r} in MUTATOR_REGISTRY union "
        f"NOT_MUTABLE_NODE_TYPES; the type is not in aeat.domain.formulas.Operand."
    )

    overlap = registered & not_mutable
    assert not overlap, (
        f"type(s) {overlap!r} appear in both MUTATOR_REGISTRY and NOT_MUTABLE_NODE_TYPES; pick exactly one."
    )


def test_not_mutable_reasons_are_non_empty() -> None:
    """Every not-mutable entry must carry a non-empty justification."""
    for node_type, reason in NOT_MUTABLE_NODE_TYPES.items():
        assert reason.strip(), (
            f"NOT_MUTABLE_NODE_TYPES[{node_type.__name__}] has an empty reason; "
            f"document why this type is intentionally unmutable."
        )


def test_mutator_registry_entries_have_descriptive_classes() -> None:
    """Every registry entry's MutatorClass has slug + description set."""
    for node_type, mutator_class in MUTATOR_REGISTRY.items():
        assert mutator_class.slug, (
            f"MUTATOR_REGISTRY[{node_type.__name__}] has a blank slug; "
            f"the slug is used in test ids and in the exec summary."
        )
        assert mutator_class.description, f"MUTATOR_REGISTRY[{node_type.__name__}] has a blank description."

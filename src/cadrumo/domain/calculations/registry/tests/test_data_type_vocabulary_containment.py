"""The narrower ``data_type`` vocabularies must stay inside the scalar taxonomy.

Five surfaces in this package declare a closed vocabulary for a field named
``data_type``, and four of them are deliberate narrowings: a casilla may hold a
NIF or an IBAN, a manual input may not. That nesting is real and useful, and
collapsing the five into one would widen what several surfaces accept rather
than remove duplication.

What was missing is any check that the nesting holds. None of the narrower
vocabularies is derived from the canonical taxonomy, so a member added to one is
not checked against it, and a type added to the taxonomy does not reach them. The
relationship was maintained by hand and held only because nobody had broken it.

Each vocabulary here is read from the model that declares it rather than
restated. A test that listed the members would drift from the declarations the
moment either changed, and would then be asserting its own copy.

See Also:
    :class:`cadrumo.domain.calculations.registry.CasillaDefinition`
        Declares the canonical vocabulary the narrowings must stay inside.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import BaseModel

from .._binding_selector_utils import BindingExportDataType
from .._bindings import _ManualInputDataType
from .._schema_exports import ExportFieldDefinition
from .._schema_formula import ParameterDefinition
from .._schema_scalars import _REGISTRY_SCALAR_VALUE_TYPES, registry_scalar_value_type
from .._schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _declared_members(model: type[BaseModel]) -> frozenset[str]:
    """Return the closed ``data_type`` vocabulary a model declares."""
    return frozenset(typing.get_args(model.model_fields["data_type"].annotation))


#: The narrowings, each expected to stay inside the casilla vocabulary.
_SCALAR_NARROWINGS: dict[str, frozenset[str]] = {
    "ExportFieldDefinition.data_type": _declared_members(ExportFieldDefinition),
    "BindingExportDataType": frozenset(typing.get_args(BindingExportDataType)),
    "_ManualInputDataType": frozenset(typing.get_args(_ManualInputDataType)),
}


def test_the_casilla_vocabulary_is_exactly_the_runtime_scalar_taxonomy() -> None:
    """The canonical vocabulary and the classifier that reads it may not drift apart.

    Everything below is checked against the casilla vocabulary, so if that
    vocabulary stopped matching the classifier the containment checks would be
    measuring the wrong set and still pass.
    """
    assert _declared_members(CasillaDefinition) == frozenset(_REGISTRY_SCALAR_VALUE_TYPES), (
        "the casilla data_type vocabulary and the runtime scalar classifier disagree, so one of "
        "them admits a type the other cannot classify. Fix the disagreement rather than the "
        "assertion: every containment check in this module is measured against this set."
    )


@pytest.mark.parametrize("subject", sorted(_SCALAR_NARROWINGS))
def test_each_scalar_narrowing_stays_inside_the_canonical_vocabulary(subject: str) -> None:
    """A narrower surface may admit fewer types, never a type the taxonomy lacks."""
    outside = sorted(_SCALAR_NARROWINGS[subject] - _declared_members(CasillaDefinition))

    assert not outside, (
        f"{subject} admits {outside!r}, which the casilla vocabulary does not. A narrowing may "
        "drop types; it may not invent them. Either the taxonomy is missing the type, in which "
        "case add it there first, or this surface is admitting something the registry cannot "
        "classify at runtime."
    )


def test_the_parameter_vocabulary_is_deliberately_not_a_scalar_narrowing() -> None:
    """Parameters carry table shapes, so their vocabulary is a different axis.

    Asserted rather than commented, and asserted in BOTH directions, because this
    is the one exclusion in the module and an exclusion nobody checks is
    indistinguishable from an oversight.

    A parameter may be a bracket table -- an IRPF rate scale is not a scalar --
    so ``ParameterDefinition.data_type`` legitimately names shapes the scalar
    classifier refuses. That makes it a peer of the casilla vocabulary rather
    than a narrowing of it, and excluding it from the containment check above is
    correct.

    This fails if the exclusion stops being true: if the parameter vocabulary
    ever becomes a pure subset, it belongs in the check rather than out of it,
    and if someone folds its table members into the scalar taxonomy the
    classifier assertion here catches it.
    """
    parameter_members = _declared_members(ParameterDefinition)
    beyond_scalars = sorted(parameter_members - _declared_members(CasillaDefinition))

    assert beyond_scalars, (
        "the parameter data_type vocabulary is now a subset of the casilla vocabulary, so the "
        "reason it is excluded from the containment check no longer holds. Move it into "
        "_SCALAR_NARROWINGS rather than leaving it excluded on a stale justification."
    )
    for member in beyond_scalars:
        with pytest.raises(Exception, match="unsupported registry casilla data type"):
            registry_scalar_value_type(member)

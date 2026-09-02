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

import enum
import typing

import pytest
from pydantic import BaseModel

from ..binding_selector_utils import BindingExportDataType
from ..errors import RegistryValidationError
from ..manual_input_selector import ManualInputDataType
from ..schema_exports import ExportFieldDefinition
from ..schema_formula import ParameterDefinition
from ..schema_scalars import _REGISTRY_SCALAR_VALUE_TYPES, registry_scalar_value_type
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _vocabulary_of(annotation: object) -> frozenset[str]:
    """Return the closed vocabulary an annotation admits, in any of its forms.

    A vocabulary reaches this gate as an enum, as a literal over that enum's members,
    or as either wrapped in ``Annotated`` to carry a coercion hop. Reading only one
    form would make the gate silently measure nothing the first time a surface
    changed how it spells the same vocabulary.
    """
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return frozenset(str(member.value) for member in annotation)
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) is not typing.Literal and args:
        return _vocabulary_of(args[0])
    return frozenset(str(arg.value if isinstance(arg, enum.Enum) else arg) for arg in args)


def _declared_members(model: type[BaseModel]) -> frozenset[str]:
    """Return the closed ``data_type`` vocabulary a model declares."""
    return _vocabulary_of(model.model_fields["data_type"].annotation)


#: The narrowings, each expected to stay inside the casilla vocabulary.
_SCALAR_NARROWINGS: dict[str, frozenset[str]] = {
    "ExportFieldDefinition.data_type": _declared_members(ExportFieldDefinition),
    "BindingExportDataType": _vocabulary_of(BindingExportDataType),
    "ManualInputDataType": _vocabulary_of(ManualInputDataType),
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
        with pytest.raises(RegistryValidationError, match="unsupported registry casilla data type"):
            registry_scalar_value_type(member)


def test_parameter_and_casilla_share_identical_spelling_for_overlapping_scalar_tokens() -> None:
    """The tokens ``ParameterDefinition`` and ``CasillaDefinition`` DO share must be
    spelled identically; nothing above protects that.

    The exclusion proved above means ``ParameterDefinition`` sits outside every
    containment check in this module -- deliberately, since its table shapes are
    not scalars. But most of its members ARE the same scalar concept the casilla
    vocabulary also names (``decimal``, ``money``, ``integer``, ``ratio``, ...),
    and nothing checks that a shared concept is spelled the same on both surfaces.
    A rename on only one side -- ``"decimal"`` becoming ``"Decimal"`` on the
    parameter model, say -- raises no error anywhere: the two frozensets would
    simply stop intersecting on that token, and a silently smaller intersection is
    not an assertion failure.

    The check pins the implication rather than a literal list: casefold both
    vocabularies and compare the casefolded-matched pairing against the
    exact-spelling intersection. A token present in both once case is folded but
    absent from the exact intersection is exactly a spelling drift, and this is
    the one shape that catches it without hardcoding either vocabulary's members.
    """
    parameter_members = _declared_members(ParameterDefinition)
    casilla_members = _declared_members(CasillaDefinition)

    parameter_by_casefold = {member.casefold(): member for member in parameter_members}
    casilla_by_casefold = {member.casefold(): member for member in casilla_members}
    casefolded_overlap = frozenset(parameter_by_casefold) & frozenset(casilla_by_casefold)

    exact_overlap_casefolded = frozenset(member.casefold() for member in parameter_members & casilla_members)

    drifted = casefolded_overlap - exact_overlap_casefolded
    assert not drifted, (
        "a parameter data_type token and a casilla data_type token name the same scalar concept "
        "once case-folded but are spelled differently: "
        f"{sorted((parameter_by_casefold[fold], casilla_by_casefold[fold]) for fold in drifted)!r}. "
        "Correct the drifted surface to match the other's spelling rather than treating this as a "
        "new, deliberately different token."
    )

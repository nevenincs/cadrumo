"""Initial-value assembly for registry formula evaluation.

The :class:`ModeloRevision` declares the casilla and binding slots that seed
calculation; materialisation emits :class:`CasillaObservation` rows carrying
registry provenance.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ._binding_selector_utils import selector_as_dict as _binding_selector_as_dict
from ._bindings import CasillaObservation
from ._bindings_previous_filing import _PreviousModeloSelector
from ._casilla_membership import casillas_by_id
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId
from ._schema import CasillaDefinition, DataBindingDefinition, InputKind, ModeloRevision

_ZERO = Decimal("0")


def materialise_observations(
    *,
    values: Mapping[CasillaId, Decimal],
    computed_provenance: Mapping[CasillaId, CasillaObservation],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    absent_by_design_casilla_ids: frozenset[CasillaId] = frozenset(),
) -> tuple[CasillaObservation, ...]:
    """Project per-casilla runtime state into the canonical observation tuple.

    Each returned :class:`CasillaObservation` is either preserved from computed
    provenance or rebuilt from the registry casilla's legal/source references.
    """
    materialised: list[CasillaObservation] = []
    for casilla_id in sorted(values):
        computed = computed_provenance.get(casilla_id)
        if computed is not None:
            materialised.append(computed)
            continue
        registry_casilla = casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise RegistryValidationError(
                f"cannot materialise CasillaObservation for casilla {casilla_id!r}; "
                "missing registry casilla definition would erase legal_refs/source_refs provenance",
            )
        legal_refs = tuple(registry_casilla.legal_refs)
        source_refs = tuple(registry_casilla.source_refs)
        if not legal_refs or not source_refs:
            raise RegistryValidationError(
                f"cannot materialise CasillaObservation for casilla {casilla_id!r}; "
                "registry casilla definition is missing legal_refs/source_refs provenance",
            )
        materialised.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=values[casilla_id],
                legal_refs=legal_refs,
                source_refs=source_refs,
                absent_by_design=casilla_id in absent_by_design_casilla_ids,
            ),
        )
    return tuple(materialised)


def initial_values(
    revision: ModeloRevision,
    inputs: Mapping[CasillaId, Decimal],
    *,
    binding_values: Mapping[BindingId, Decimal],
    target_period: str,
) -> tuple[dict[CasillaId, Decimal], frozenset[CasillaId]]:
    """Build initial numeric casilla values and absent-by-design markers.

    The :class:`ModeloRevision` supplies casilla membership, formula targets,
    and bound slot declarations before formula evaluation starts.
    """
    casillas = casillas_by_id(revision)
    _reject_unknown_inputs(inputs, casillas)
    _reject_computed_inputs(inputs, casillas, {formula.target_casilla_id for formula in revision.formulas})

    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    _reject_smuggled_previous_filing_inputs(
        inputs,
        casillas=casillas,
        bindings_by_id=bindings_by_id,
        binding_values=binding_values,
    )
    _reject_inconsistent_previous_filing_projections(
        inputs,
        casillas=casillas,
        bindings_by_id=bindings_by_id,
        binding_values=binding_values,
    )

    return _initial_values_for_casillas(
        revision.casillas,
        inputs=inputs,
        bindings_by_id=bindings_by_id,
        binding_values=binding_values,
        target_period=target_period,
    )


def _reject_unknown_inputs(
    inputs: Mapping[CasillaId, Decimal],
    casillas: Mapping[CasillaId, CasillaDefinition],
) -> None:
    unknown = sorted(set(inputs).difference(casillas))
    if unknown:
        raise RegistryValidationError(
            f"unknown registry input casilla ids: {unknown!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(unknown)},
        )


def _reject_computed_inputs(
    inputs: Mapping[CasillaId, Decimal],
    casillas: Mapping[CasillaId, CasillaDefinition],
    formula_targets: set[CasillaId],
) -> None:
    computed = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == InputKind.COMPUTED or casilla_id in formula_targets
    )
    if computed:
        raise RegistryValidationError(
            f"computed registry casillas cannot be supplied as inputs: {computed!r}",
            translated_message="errors.calc.computed_supplied_as_input",
            context={"casilla_ids": ",".join(computed)},
        )


# Observation-backed slot sources: a bound casilla whose binding carries one of
# these sources materialises its value into ``binding_values`` (the
# previous-filing carry resolver or, since the relation became canonical for
# cross-modelo fold-ins, the relation prefill resolver). Both feed the bound
# casilla through the binding_values channel and obey the same
# source-of-truth / projection-consistency invariants below.
_OBSERVATION_BACKED_SLOT_SOURCES: frozenset[str] = frozenset({"previous_filing", "relation_prefill"})


def _previous_filing_binding_for_bound_casilla(
    casilla: CasillaDefinition,
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
) -> DataBindingDefinition | None:
    if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
        return None
    binding = bindings_by_id.get(casilla.binding)
    if binding is None or str(binding.source) not in _OBSERVATION_BACKED_SLOT_SOURCES:
        return None
    return binding


def _reject_smuggled_previous_filing_inputs(
    inputs: Mapping[CasillaId, Decimal],
    *,
    casillas: Mapping[CasillaId, CasillaDefinition],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    binding_values: Mapping[BindingId, Decimal],
) -> None:
    smuggled_previous_filing_bound = sorted(
        casilla_id
        for casilla_id in inputs
        if (binding := _previous_filing_binding_for_bound_casilla(casillas[casilla_id], bindings_by_id)) is not None
        and binding.id not in binding_values
    )
    if smuggled_previous_filing_bound:
        raise RegistryValidationError(
            "previous-filing bound registry casillas cannot be supplied via inputs "
            "without the matching binding_values entry; the projection from "
            "resolve_bound_inputs_by_casilla_id must include the binding value as the "
            f"source of truth: {smuggled_previous_filing_bound!r}",
            translated_message="errors.calc.bound_input_smuggled_without_binding_value",
            context={"casilla_ids": ",".join(smuggled_previous_filing_bound)},
        )


def _reject_inconsistent_previous_filing_projections(
    inputs: Mapping[CasillaId, Decimal],
    *,
    casillas: Mapping[CasillaId, CasillaDefinition],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    binding_values: Mapping[BindingId, Decimal],
) -> None:
    inconsistent: list[tuple[str, str]] = []
    for casilla_id, input_value in inputs.items():
        binding = _previous_filing_binding_for_bound_casilla(casillas[casilla_id], bindings_by_id)
        if binding is None:
            continue
        binding_value = binding_values.get(binding.id)
        if binding_value is None:
            continue
        if input_value != binding_value:
            inconsistent.append(
                (
                    casilla_id,
                    f"casilla {casilla_id!r}: inputs={input_value!r} vs "
                    f"binding_values[{binding.id!r}]={binding_value!r}",
                ),
            )
    if inconsistent:
        raise RegistryValidationError(
            "previous-filing bound casilla projection is inconsistent between "
            "inputs and binding_values; the binding_values entry is the source "
            "of truth and the inputs projection must match it: " + "; ".join(message for _, message in inconsistent),
            translated_message="errors.calc.bound_projection_inconsistent",
            context={"casilla_ids": ",".join(casilla_id for casilla_id, _ in inconsistent)},
        )


def _initial_values_for_casillas(
    casillas: tuple[CasillaDefinition, ...],
    *,
    inputs: Mapping[CasillaId, Decimal],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    binding_values: Mapping[BindingId, Decimal],
    target_period: str,
) -> tuple[dict[CasillaId, Decimal], frozenset[CasillaId]]:
    values: dict[CasillaId, Decimal] = {}
    absent_by_design: set[CasillaId] = set()
    for casilla in casillas:
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        value, absent = _initial_value_for_casilla(
            casilla,
            inputs=inputs,
            bindings_by_id=bindings_by_id,
            binding_values=binding_values,
            target_period=target_period,
        )
        values[casilla.id] = value
        if absent:
            absent_by_design.add(casilla.id)
    return values, frozenset(absent_by_design)


def _initial_value_for_casilla(
    casilla: CasillaDefinition,
    *,
    inputs: Mapping[CasillaId, Decimal],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    binding_values: Mapping[BindingId, Decimal],
    target_period: str,
) -> tuple[Decimal, bool]:
    binding = _previous_filing_binding_for_bound_casilla(casilla, bindings_by_id)
    if binding is None:
        return inputs.get(casilla.id, _ZERO), False
    if binding.id in binding_values:
        return binding_values[binding.id], False
    if _binding_is_absent_by_design(binding, target_period=target_period):
        return _ZERO, True
    raise RegistryValidationError(
        f"bound casilla {casilla.id!r} requires resolved binding {binding.id!r} value",
        translated_message="errors.calc.bound_casilla_binding_value_missing",
        context={"casilla_id": casilla.id, "binding_id": binding.id},
    )


def _binding_is_absent_by_design(binding: DataBindingDefinition, *, target_period: str) -> bool:
    # A relation_prefill slot legitimately blanks when no prior filing exists to
    # fold in (the relation resolver returns no value and the operator fills it
    # by hand). Treat an unresolved relation_prefill slot as absent-by-design
    # rather than raising — the same operator-manual fallback the relation
    # resolver documents.
    if str(binding.source) == "relation_prefill":
        return True
    if binding.source != "previous_filing":
        return False
    try:
        selector = _PreviousModeloSelector.model_validate(_binding_selector_as_dict(binding))
    except ValueError:
        return False
    if not _previous_filing_selector_has_period_anchor(selector):
        return False
    return selector.required_period_anchors_for_target(target_period) == ()


def _previous_filing_selector_has_period_anchor(selector: _PreviousModeloSelector) -> bool:
    return (
        selector.period is not None
        or bool(selector.source_periods)
        or selector.source_period_offset_from_target is not None
        or selector.prior_quarter_expanding_span
    )

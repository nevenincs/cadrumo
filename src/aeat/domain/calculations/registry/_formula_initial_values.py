"""Initial-value assembly for registry formula evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel

from ._bindings import CasillaObservation
from ._bindings_previous_filing import _PreviousModeloSelector
from ._errors import RegistryValidationError
from ._schema import CasillaDefinition, DataBindingDefinition, InputKind, ModeloRevision

_ZERO = Decimal("0")


def materialise_observations(
    *,
    values: Mapping[str, Decimal],
    computed_provenance: Mapping[str, CasillaObservation],
    casillas_by_id: Mapping[str, CasillaDefinition],
    absent_by_design_casillas: frozenset[str] = frozenset(),
) -> tuple[CasillaObservation, ...]:
    """Project per-casilla runtime state into the canonical observation tuple."""
    materialised: list[CasillaObservation] = []
    for casilla_id in sorted(values):
        computed = computed_provenance.get(casilla_id)
        if computed is not None:
            materialised.append(computed)
            continue
        registry_casilla = casillas_by_id.get(casilla_id)
        legal_refs = tuple(registry_casilla.legal_refs) if registry_casilla is not None else ()
        source_refs = tuple(registry_casilla.source_refs) if registry_casilla is not None else ()
        materialised.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=values[casilla_id],
                legal_refs=legal_refs,
                source_refs=source_refs,
                absent_by_design=casilla_id in absent_by_design_casillas,
            )
        )
    return tuple(materialised)


def initial_values(
    revision: ModeloRevision,
    inputs: Mapping[str, Decimal],
    *,
    binding_values: Mapping[str, Decimal],
    target_period: str,
) -> tuple[dict[str, Decimal], frozenset[str]]:
    """Build initial numeric casilla values and absent-by-design markers."""
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    unknown = sorted(set(inputs).difference(casillas))
    if unknown:
        raise RegistryValidationError(
            f"unknown registry input casilla ids: {unknown!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(unknown)},
        )
    formula_targets = {formula.target for formula in revision.formulas}
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

    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    smuggled_previous_filing_bound = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == InputKind.BOUND
        and casillas[casilla_id].binding is not None
        and (binding_def := bindings_by_id.get(casillas[casilla_id].binding or "")) is not None
        and binding_def.source == "previous_filing"
        and binding_def.id not in binding_values
    )
    if smuggled_previous_filing_bound:
        raise RegistryValidationError(
            "previous-filing bound registry casillas cannot be supplied via inputs "
            "without the matching binding_values entry; the projection from "
            "resolve_bound_casilla_inputs must include the binding value as the "
            f"source of truth: {smuggled_previous_filing_bound!r}",
            translated_message="errors.calc.bound_input_smuggled_without_binding_value",
            context={"casilla_ids": ",".join(smuggled_previous_filing_bound)},
        )

    inconsistent_previous_filing_projections: list[str] = []
    for casilla_id, input_value in inputs.items():
        casilla = casillas[casilla_id]
        if casilla.input_kind != InputKind.BOUND or casilla.binding is None:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None or binding.source != "previous_filing":
            continue
        binding_value = binding_values.get(binding.id)
        if binding_value is None:
            continue
        if input_value != binding_value:
            inconsistent_previous_filing_projections.append(
                f"casilla {casilla_id!r}: inputs={input_value!r} vs binding_values[{binding.id!r}]={binding_value!r}"
            )
    if inconsistent_previous_filing_projections:
        raise RegistryValidationError(
            "previous-filing bound casilla projection is inconsistent between "
            "inputs and binding_values; the binding_values entry is the source "
            "of truth and the inputs projection must match it: " + "; ".join(inconsistent_previous_filing_projections),
            translated_message="errors.calc.bound_projection_inconsistent",
            context={
                "casilla_ids": ",".join(c.split(":")[0].split("'")[1] for c in inconsistent_previous_filing_projections)
            },
        )

    values: dict[str, Decimal] = {}
    absent_by_design: set[str] = set()
    for casilla in revision.casillas:
        if casilla.input_kind == InputKind.COMPUTED:
            continue
        if casilla.input_kind == InputKind.BOUND:
            binding_id = casilla.binding
            binding = bindings_by_id.get(binding_id or "")
            if binding is not None and binding.source == "previous_filing":
                if binding_id in binding_values:
                    values[casilla.id] = binding_values[binding_id]
                    continue
                if _binding_is_absent_by_design(binding, target_period=target_period):
                    values[casilla.id] = _ZERO
                    absent_by_design.add(casilla.id)
                    continue
                raise RegistryValidationError(
                    f"bound casilla {casilla.id!r} requires resolved binding {binding_id!r} value",
                    translated_message="errors.calc.bound_casilla_binding_value_missing",
                    context={"casilla_id": casilla.id, "binding_id": binding_id or ""},
                )
        values[casilla.id] = inputs.get(casilla.id, _ZERO)
    return values, frozenset(absent_by_design)


def _binding_is_absent_by_design(binding: DataBindingDefinition, *, target_period: str) -> bool:
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
    )


def _binding_selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {k: v for k, v in selector.items() if k != "source"}

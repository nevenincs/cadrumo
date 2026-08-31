"""Initial-value assembly for registry formula evaluation.

The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` declares the
casilla and binding slots that seed
:func:`cadrumo.domain.calculations.registry.formula_runtime.calculate_registry_snapshot`;
materialisation emits
:class:`~cadrumo.domain.calculations.registry.CasillaObservation` rows carrying
registry provenance.

See Also:
    :mod:`cadrumo.domain.calculations.registry.formula_runtime`
        Runtime caller that consumes the initial values and materialised
        observations produced here.
    :mod:`cadrumo.domain.calculations.registry.bindings`
        Binding helpers that resolve bound casilla values and equivalent binding
        groups before provenance materialisation.
    :mod:`cadrumo.domain.calculations.registry.bindings_previous_filing`
        Previous-filing selector model used to decide whether a missing bound
        slot is absent by design for the target period.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ....core.aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS, BindingSourceKind
from ....core.casilla_id import CasillaId
from .binding_selector_utils import selector_as_dict as _binding_selector_as_dict
from .binding_targets import bound_casilla_binding_ids
from .bindings import CasillaObservation, resolve_bound_casilla_binding_value
from .bindings_previous_filing import PreviousModeloSelector
from .casilla_membership import casillas_by_id
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

_ZERO = Decimal("0")


def materialise_observations(
    *,
    values: Mapping[CasillaId, Decimal],
    text_values: Mapping[CasillaId, str] | None = None,
    computed_provenance: Mapping[CasillaId, CasillaObservation],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
    absent_by_design_casilla_ids: frozenset[CasillaId] = frozenset(),
) -> tuple[CasillaObservation, ...]:
    """Project per-casilla runtime state into the canonical observation tuple.

    Each returned
    :class:`~cadrumo.domain.calculations.registry.CasillaObservation` is either
    preserved from computed provenance or rebuilt from a
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` legal/source
    reference set.
    """
    resolved_text_values = text_values or {}
    materialised: list[CasillaObservation] = []
    for casilla_id in sorted(values.keys() | resolved_text_values.keys()):
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
                value_kind="text" if casilla_id in resolved_text_values else "decimal",
                value=(resolved_text_values[casilla_id] if casilla_id in resolved_text_values else values[casilla_id]),
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

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    :class:`~cadrumo.core.CasillaId` membership, formula
    targets, and :class:`~cadrumo.domain.calculations.registry.BindingId` slots
    before formula evaluation starts.
    """
    casillas = casillas_by_id(revision)
    _reject_unknown_inputs(inputs, casillas)
    _reject_non_input_kind_inputs(inputs, casillas, {formula.target_casilla_id for formula in revision.formulas})

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


def initial_value_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return casilla ids seeded before registry formula evaluation.

    Source-resolution preview passes can use this to distinguish declared or
    bound input slots from values that only exist after the formula engine runs.
    It is intentionally descriptive only; computed casillas still cannot be
    supplied through the input channel. ``revision`` is the compiled
    :class:`ModeloRevision` whose casillas are scanned for their declared
    ``input_kind``.
    """
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind not in {InputKind.COMPUTED, InputKind.PROJECTION_ONLY}
    )


def binding_values_with_absent_by_design_defaults(
    revision: ModeloRevision,
    binding_values: Mapping[BindingId, Decimal],
    *,
    target_period: str,
) -> dict[BindingId, Decimal]:
    """Add structural zeroes for absent-by-design binding slots.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` binding
    declarations are inspected through
    :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` so
    previous-filing and relation-prefill slots can default only when the
    selected target period has no required source period.
    """
    resolved = dict(binding_values)
    equivalent_groups_by_binding: dict[BindingId, tuple[BindingId, ...]] = {
        binding_id: group
        for casilla in revision.casillas
        if casilla.input_kind == InputKind.BOUND
        for group in (bound_casilla_binding_ids(casilla),)
        for binding_id in group
    }
    for binding in revision.bindings:
        if binding.id in resolved:
            continue
        equivalent_group = equivalent_groups_by_binding.get(binding.id, (binding.id,))
        if any(equivalent_id in resolved for equivalent_id in equivalent_group if equivalent_id != binding.id):
            continue
        if _binding_is_absent_by_design(binding, target_period=target_period):
            resolved[binding.id] = _ZERO
    return resolved


def _reject_unknown_inputs(
    inputs: Mapping[CasillaId, Decimal],
    casillas: Mapping[CasillaId, CasillaDefinition],
) -> None:
    """Reject supplied :class:`~cadrumo.core.CasillaId` keys."""
    unknown = sorted(set(inputs).difference(casillas))
    if unknown:
        raise RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=unknown)


def _reject_non_input_kind_inputs(
    inputs: Mapping[CasillaId, Decimal],
    casillas: Mapping[CasillaId, CasillaDefinition],
    formula_targets: set[CasillaId],
) -> None:
    """Reject caller values for computed and projection-only registry casillas."""
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
    projection_only = sorted(
        casilla_id for casilla_id in inputs if casillas[casilla_id].input_kind == InputKind.PROJECTION_ONLY
    )
    if projection_only:
        raise RegistryValidationError(
            "projection-only registry casillas cannot be supplied as inputs; "
            f"their canonical typed row projection owns the values: {projection_only!r}",
        )


# Observation-backed slot sources: a bound casilla whose binding carries one of
# these sources materialises its value into ``binding_values`` (the
# previous-filing carry resolver or, since the relation became canonical for
# cross-modelo fold-ins, the relation prefill resolver). Both feed the bound
# casilla through the binding_values channel and obey the same
# source-of-truth / projection-consistency invariants below.
#
# The set itself is the canonical one in ``core``. It was previously restated
# here as raw strings, which compared through a ``str()`` coercion and would
# have survived a token rename silently.
_OBSERVATION_BACKED_SLOT_SOURCES = OBSERVATION_BACKED_BINDING_SOURCE_KINDS


def _observation_backed_bindings_for_bound_casilla(
    casilla: CasillaDefinition,
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
) -> tuple[DataBindingDefinition, ...]:
    """Return bound :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` slots."""
    if casilla.input_kind != InputKind.BOUND:
        return ()
    return tuple(
        binding
        for binding_id in bound_casilla_binding_ids(casilla)
        if (binding := bindings_by_id.get(binding_id)) is not None
        and binding.source in _OBSERVATION_BACKED_SLOT_SOURCES
    )


def _reject_smuggled_previous_filing_inputs(
    inputs: Mapping[CasillaId, Decimal],
    *,
    casillas: Mapping[CasillaId, CasillaDefinition],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    binding_values: Mapping[BindingId, Decimal],
) -> None:
    """Require observation-backed bound casillas to enter through bindings."""
    smuggled_previous_filing_bound = sorted(
        casilla_id
        for casilla_id in inputs
        if _observation_backed_bindings_for_bound_casilla(casillas[casilla_id], bindings_by_id)
        and not any(binding_id in binding_values for binding_id in bound_casilla_binding_ids(casillas[casilla_id]))
    )
    if smuggled_previous_filing_bound:
        raise RegistryValidationError(
            "observation-backed bound registry casillas cannot be supplied via inputs "
            "without a matching binding_values entry; the available bound-input "
            "projection must include the binding value as the "
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
    """Reject mismatches between input projections and binding source values."""
    inconsistent: list[tuple[str, str]] = []
    for casilla_id, input_value in inputs.items():
        casilla = casillas[casilla_id]
        if not _observation_backed_bindings_for_bound_casilla(casilla, bindings_by_id):
            continue
        binding_value, present_binding_ids = resolve_bound_casilla_binding_value(casilla, binding_values)
        if binding_value is None:
            continue
        if input_value != binding_value:
            inconsistent.append(
                (
                    casilla_id,
                    f"casilla {casilla_id!r}: inputs={input_value!r} vs "
                    f"binding_values[{present_binding_ids!r}]={binding_value!r}",
                ),
            )
    if inconsistent:
        raise RegistryValidationError(
            "observation-backed bound casilla projection is inconsistent between "
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
    """Build initial values for non-computed registry casilla definitions."""
    values: dict[CasillaId, Decimal] = {}
    absent_by_design: set[CasillaId] = set()
    for casilla in casillas:
        if casilla.input_kind in {InputKind.COMPUTED, InputKind.PROJECTION_ONLY}:
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
    """Resolve one manual or observation-backed initial casilla value."""
    bindings = _observation_backed_bindings_for_bound_casilla(casilla, bindings_by_id)
    if not bindings:
        return inputs.get(casilla.id, _ZERO), False
    value, _present_binding_ids = resolve_bound_casilla_binding_value(casilla, binding_values)
    if value is not None:
        return value, False
    if any(_binding_is_absent_by_design(binding, target_period=target_period) for binding in bindings):
        return _ZERO, True
    binding_ids = bound_casilla_binding_ids(casilla)
    raise RegistryValidationError(
        f"bound casilla {casilla.id!r} requires resolved value for one of {binding_ids!r}",
        translated_message="errors.calc.bound_casilla_binding_value_missing",
        context={"casilla_id": casilla.id, "binding_id": ",".join(binding_ids)},
    )


def _binding_is_absent_by_design(binding: DataBindingDefinition, *, target_period: str) -> bool:
    """Decide whether a missing bound slot is structural for ``target_period``."""
    # A relation_prefill slot legitimately blanks when no prior filing exists to
    # fold in (the relation resolver returns no value and the operator fills it
    # by hand). Treat an unresolved relation_prefill slot as absent-by-design
    # rather than raising — the same operator-manual fallback the relation
    # resolver documents.
    if binding.source == BindingSourceKind.RELATION_PREFILL:
        return True
    if binding.source != BindingSourceKind.PREVIOUS_FILING:
        return False
    try:
        selector = PreviousModeloSelector.model_validate(_binding_selector_as_dict(binding))
    except ValueError:
        return False
    if not _previous_filing_selector_has_period_anchor(selector):
        return False
    return selector.required_period_anchors_for_target(target_period) == ()


def _previous_filing_selector_has_period_anchor(selector: PreviousModeloSelector) -> bool:
    """Check whether a previous-filing selector is anchored to target periods."""
    return (
        selector.period is not None
        or bool(selector.source_periods)
        or selector.source_period_offset_from_target is not None
        or selector.prior_quarter_expanding_span
    )

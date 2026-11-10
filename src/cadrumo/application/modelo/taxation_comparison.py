"""Conjunta vs. individual taxation comparison for Modelo 100 (IRPF).

Evaluates one declaration twice -- once as a joint return (tributación
conjunta, Art. 82-84 LIRPF) and once as an individual return -- and compares
the cuota diferencial so a family unit can pick the lower-tax mode.

Both runs are the work unit's own calculation, evaluated and never saved. They
replay the caller context of the current calculation head (the operator's
entered boxes and answers, detail rows and the borrador snapshot) through the
canonical source mesh, so imported, ledger-sourced and prior-period relation
evidence is resolved exactly as a calculation of this declaration resolves it.
The two runs differ only in the profile's declaration-type fact, which is
replaced in memory, so every resolver and derived fact that reads it sees the
mode it is evaluated for.

The comparison refuses only what it cannot answer honestly. A revision that
does not declare the declaration type and the two compared results cannot be
compared. A household that is not a family unit (Art. 82 LIRPF), judged from
the profile's family situation and the registry's family-situation vocabulary,
cannot file jointly. A result one of the runs leaves unresolved is refused,
naming the boxes the result formulas read that have no value, so an absent fact
is never compared as zero.

Scope honesty: the individual run reuses the single input set held for the
household and only changes the declaration type, so it faithfully models a
**single-earner** household. It does not compute two separate spouse returns;
a genuine two-earner individual comparison requires a per-spouse income axis
that does not yet exist. Every result therefore carries
``individual_branch_single_earner_only``, and the surfaces serve its caveat in
words so none presents the individual figure as authoritative for a two-earner
couple.

See Also:
    :func:`~cadrumo.application.modelo.calculation_bucket_actions.evaluate_modelo_revision_from_bucket_aggregation`:
        The canonical calculation, evaluated without publishing a revision.
    :mod:`~cadrumo.application.modelo.caller_context`:
        The caller context a calculation head was computed from.
    :mod:`~cadrumo.application.modelo.semantic_role_resolution`:
        The semantic-role-to-casilla resolver and its ambiguity refusal;
:class:`ModeloRevision`, the registry revision a modelo is calculated against;
:class:`RegistrySnapshot`, the pinned registry snapshot;
:class:`UserProfileRecord`, the stored taxpayer profile record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CoreError
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_targets import casillas_by_binding
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.runtime_graph import expression_binding_refs, expression_casilla_refs
from ...domain.calculations.registry.schema import FormulaDefinition, ModeloRevision, RegistrySnapshot
from ...domain.contribuyente.renta_codes import RentaDeclaracionType
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.work_unit import WorkUnit
    from .calculation_action_ports import CalculationActionPorts
    from .calculation_actions import TrustedMeshEvaluation
    from .caller_context import CalculationCallerContext, CallerContextCalculationInputs
    from .work_profile import ModeloWorkProfile

MATERIALITY_THRESHOLD: Final = Decimal(1)
"""The difference in euros below which either filing mode is acceptable; not a tax-law limit."""

_DECLARATION_TYPE_ROLE: Final = "irpf_declaracion_tipo_tributacion"
_CUOTA_RESULTANTE_ROLE: Final = "irpf_cuota_resultante_autoliquidacion"
_RESULTADO_ROLE: Final = "irpf_cuota_diferencial"
_SITUACION_FAMILIAR_PATH: Final = "renta_family.situacion_familiar"
_MINOR_CHILDREN_IN_UNIT_PATH: Final = "renta_family.minor_children_in_unit"
_SPOUSE_TAX_ID_PATH: Final = "renta_spouse.tax_id"
"""The profile rule that refuses a joint return whose spouse the profile does not identify."""


class TaxationRecommendation(StrEnum):
    """Recommended filing mode based on the computed cuota differential.

    The enum reports the lower-tax path after applying the materiality threshold,
    or ``INDIFFERENT`` when the two calculated results differ by less than one
    euro.
    """

    CONJUNTA = "conjunta"
    INDIVIDUAL = "individual"
    INDIFFERENT = "indifferent"


class TaxationRecommendationReason(StrEnum):
    """Why the comparison recommends what it does, as a closed token.

    The words for a reason, with the amounts it rests on, are served by
    :mod:`~cadrumo.application.modelo.taxation_comparison_words`.
    """

    CONJUNTA_LOWER_RESULT = "conjunta_lower_result"
    INDIVIDUAL_LOWER_RESULT = "individual_lower_result"
    BELOW_MATERIALITY = "below_materiality"


class TaxationComparisonRefusal(StrEnum):
    """Why a comparison could not be made, as a closed token with served words."""

    NOT_DECLARED = "not_declared"
    """The revision declares no declaration type or no unique compared result."""
    REVISION_OUTDATED = "revision_outdated"
    """The work unit was created on a revision the authority no longer selects."""
    NOT_CALCULATED = "not_calculated"
    """The declaration has no calculation whose held values the runs could replay."""
    ENTRIES_UNKNOWN = "entries_unknown"
    """The calculation predates recorded operator entries, so what was entered is unknown."""
    SPOUSE_UNSTATED = "spouse_unstated"
    """The profile does not identify the spouse a joint return declares."""
    FAMILY_SITUATION_UNSTATED = "family_situation_unstated"
    """The profile does not state the facts that decide whether the household is a family unit."""
    NO_FAMILY_UNIT = "no_family_unit"
    """The household is not a family unit, so it cannot file jointly."""
    UNRESOLVED_BOXES = "unresolved_boxes"
    """A box the compared results read has no value in one of the runs."""


_REFUSAL_LOCALE_KEYS: Final[Mapping[TaxationComparisonRefusal, str]] = MappingProxyType(
    {
        TaxationComparisonRefusal.NOT_DECLARED: "application.modelo.taxation_comparison_words.refusal.not_declared",
        TaxationComparisonRefusal.REVISION_OUTDATED: (
            "application.modelo.taxation_comparison_words.refusal.revision_outdated"
        ),
        TaxationComparisonRefusal.NOT_CALCULATED: "application.modelo.taxation_comparison_words.refusal.not_calculated",
        TaxationComparisonRefusal.ENTRIES_UNKNOWN: (
            "application.modelo.taxation_comparison_words.refusal.entries_unknown"
        ),
        TaxationComparisonRefusal.SPOUSE_UNSTATED: (
            "application.modelo.taxation_comparison_words.refusal.spouse_unstated"
        ),
        TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED: (
            "application.modelo.taxation_comparison_words.refusal.family_situation_unstated"
        ),
        TaxationComparisonRefusal.NO_FAMILY_UNIT: "application.modelo.taxation_comparison_words.refusal.no_family_unit",
        TaxationComparisonRefusal.UNRESOLVED_BOXES: (
            "application.modelo.taxation_comparison_words.refusal.unresolved_boxes"
        ),
    }
)
"""The catalogue sentence of each refusal; every refusal has one."""


class TaxationComparisonError(CoreError):
    """Raised when a conjunta-vs-individual comparison cannot be performed.

    ``refusal`` is the closed reason; ``casilla_ids`` names the unresolved
    boxes of an :attr:`TaxationComparisonRefusal.UNRESOLVED_BOXES` refusal.
    The served words name the boxes and never an amount.
    """

    def __init__(self, refusal: TaxationComparisonRefusal, *, casilla_ids: tuple[CasillaId, ...] = ()) -> None:
        """Carry the refusal token and, for unresolved boxes, the boxes it names."""
        self.refusal = refusal
        self.casilla_ids = casilla_ids
        context: dict[str, object] = {"refusal": refusal.value}
        if casilla_ids:
            context["casilla_ids"] = ", ".join(casilla_ids)
        super().__init__(
            f"taxation comparison refused: {refusal.value}",
            translated_message=_REFUSAL_LOCALE_KEYS[refusal],
            context=context,
        )


class TaxationComparisonResult(BaseModel):
    """Typed result of a conjunta-vs-individual comparison run.

    All cuota amounts are in euros (``Decimal`` rounded to 2dp by
    the registry formula engine).  Positive values are amounts
    to pay (a ingresar); negative values are amounts to refund
    (a devolver).

    ``*_cuota_resultante`` carries the Modelo 100 cuota resultante de la
    autoliquidación semantic role, while ``*_resultado`` carries the cuota
    diferencial/result role used to compute ``delta_resultado`` and the
    recommendation.
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int
    modelo: str
    revision: str

    conjunta_cuota_resultante: Decimal
    individual_cuota_resultante: Decimal

    conjunta_resultado: Decimal
    individual_resultado: Decimal

    # individual - conjunta: positive -> conjunta is cheaper.
    delta_resultado: Decimal

    recommendation: TaxationRecommendation
    recommendation_reason: TaxationRecommendationReason

    # Honesty scope: the individual branch reuses the household's single input
    # set, so it is faithful only for a single-earner household. The words of
    # this disclosure are served by
    # :func:`~cadrumo.application.modelo.taxation_comparison_words.individual_branch_caveat_words`.
    individual_branch_single_earner_only: bool = True


@dataclass(frozen=True, slots=True)
class TaxationComparisonBasis:
    """What a revision declares that a joint-versus-individual comparison reads.

    ``declaration_binding`` is the binding of the revision's declaration-type
    box, and ``declaration_profile_key`` the profile fact it is sourced from;
    the comparison replaces that fact for each run. ``cuota_casilla`` and
    ``resultado_casilla`` are the compared results.
    """

    declaration_binding: BindingId
    declaration_profile_key: str
    declaration_casilla: CasillaId
    cuota_casilla: CasillaId
    resultado_casilla: CasillaId

    @property
    def result_casillas(self) -> tuple[CasillaId, CasillaId]:
        """The two compared boxes, cuota resultante first."""
        return (self.cuota_casilla, self.resultado_casilla)


def _unique_role(snapshot: RegistrySnapshot, role: str) -> CasillaId | None:
    try:
        return casilla_id_for_unique_semantic_role(snapshot, role)
    except AmbiguousSemanticRoleCasillaError:
        return None


def _declaration_binding(snapshot: RegistrySnapshot, declaration_casilla: CasillaId) -> tuple[BindingId, str] | None:
    """The profile-sourced binding behind the declaration-type box and the profile key it reads."""
    declaration = next(casilla for casilla in snapshot.revision.casillas if casilla.id == declaration_casilla)
    binding = next((item for item in snapshot.revision.bindings if item.id == declaration.binding), None)
    if binding is None:
        return None
    profile_key = selector_as_dict(binding).get("profile_key")
    if not isinstance(profile_key, str) or not profile_key:
        return None
    return binding.id, profile_key


def taxation_comparison_basis(snapshot: RegistrySnapshot) -> TaxationComparisonBasis | None:
    """Return what ``snapshot`` declares for the comparison, or ``None`` when it cannot be compared.

    A revision can be compared when one box carries the declaration-type role
    and is bound to a profile-sourced binding, and one box each carries the
    cuota resultante and the cuota diferencial roles. An ambiguous role is
    not a basis: the comparison never picks among duplicated boxes.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    declaration_casilla = _unique_role(snapshot, _DECLARATION_TYPE_ROLE)
    cuota_casilla = _unique_role(snapshot, _CUOTA_RESULTANTE_ROLE)
    resultado_casilla = _unique_role(snapshot, _RESULTADO_ROLE)
    if declaration_casilla is None or cuota_casilla is None or resultado_casilla is None:
        return None
    declared = _declaration_binding(snapshot, declaration_casilla)
    if declared is None:
        return None
    binding_id, profile_key = declared
    return TaxationComparisonBasis(
        declaration_binding=binding_id,
        declaration_profile_key=profile_key,
        declaration_casilla=declaration_casilla,
        cuota_casilla=cuota_casilla,
        resultado_casilla=resultado_casilla,
    )


def revision_compares_taxation(snapshot: RegistrySnapshot) -> bool:
    """Whether ``snapshot`` declares what a joint-versus-individual comparison reads.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    return taxation_comparison_basis(snapshot) is not None


def compare_taxation_results(
    basis: TaxationComparisonBasis,
    *,
    snapshot: RegistrySnapshot,
    conjunta: Mapping[CasillaId, Decimal],
    individual: Mapping[CasillaId, Decimal],
) -> TaxationComparisonResult:
    """Compare the joint and individual results of two settled runs.

    Both runs must hold both compared boxes; a missing one is refused rather
    than read as zero. The recommendation applies the one-euro materiality
    threshold to ``individual - conjunta``.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    missing = tuple(
        casilla_id for casilla_id in basis.result_casillas if casilla_id not in conjunta or casilla_id not in individual
    )
    if missing:
        raise TaxationComparisonError(TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=missing)
    delta = individual[basis.resultado_casilla] - conjunta[basis.resultado_casilla]
    if delta > MATERIALITY_THRESHOLD:
        recommendation = TaxationRecommendation.CONJUNTA
        reason = TaxationRecommendationReason.CONJUNTA_LOWER_RESULT
    elif delta < -MATERIALITY_THRESHOLD:
        recommendation = TaxationRecommendation.INDIVIDUAL
        reason = TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT
    else:
        recommendation = TaxationRecommendation.INDIFFERENT
        reason = TaxationRecommendationReason.BELOW_MATERIALITY
    return TaxationComparisonResult(
        filing_year=snapshot.filing_year,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        conjunta_cuota_resultante=conjunta[basis.cuota_casilla],
        individual_cuota_resultante=individual[basis.cuota_casilla],
        conjunta_resultado=conjunta[basis.resultado_casilla],
        individual_resultado=individual[basis.resultado_casilla],
        delta_resultado=delta,
        recommendation=recommendation,
        recommendation_reason=reason,
    )


def _boxes_reading_binding(revision: ModeloRevision, binding_id: BindingId) -> tuple[CasillaId, ...]:
    """The boxes a binding fills, or else the formula boxes that read it directly."""
    bound = casillas_by_binding(revision).get(binding_id, ())
    if bound:
        return bound
    return tuple(
        formula.target_casilla_id
        for formula in revision.formulas
        if binding_id in expression_binding_refs(formula.expression)
    )


def _formula_box_gaps(
    revision: ModeloRevision,
    casilla_id: CasillaId,
    formula: FormulaDefinition,
    values: Mapping[CasillaId, Decimal],
    unresolved_binding_ids: frozenset[BindingId],
) -> tuple[set[CasillaId], list[CasillaId]]:
    """The boxes one formula box names, and the operand boxes without a value the walk descends into.

    Boxes filled by an unresolved binding the formula reads are named; the formula box itself is named when
    nothing else explains why it has no value.
    """
    operand_boxes = [ref for ref in expression_casilla_refs(formula.expression) if ref not in values]
    gaps = [ref for ref in expression_binding_refs(formula.expression) if ref in unresolved_binding_ids]
    named: set[CasillaId] = set()
    for binding_id in gaps:
        named.update(_boxes_reading_binding(revision, binding_id))
    if not operand_boxes and not gaps:
        named.add(casilla_id)
    return named, operand_boxes


def unresolved_result_boxes(
    revision: ModeloRevision,
    *,
    results: tuple[CasillaId, ...],
    values: Mapping[CasillaId, Decimal],
    unresolved_binding_ids: frozenset[BindingId],
) -> tuple[CasillaId, ...]:
    """Name the boxes without a value that the formulas of ``results`` read, in box order.

    The walk follows the formula dependency graph down from each result that
    has no value. A box with no value and no formula is an unresolved input; a
    formula box whose own operands all hold values could not be evaluated
    itself, so it is named; an unresolved binding a formula reads names the
    boxes it fills. A result that holds a value is never descended into, so a
    gap the compared results do not read is never blamed.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    formulas = {formula.target_casilla_id: formula for formula in revision.formulas}
    named: set[CasillaId] = set()
    seen: set[CasillaId] = set()
    pending = [casilla_id for casilla_id in results if casilla_id not in values]
    while pending:
        casilla_id = pending.pop()
        if casilla_id in seen or casilla_id in values:
            continue
        seen.add(casilla_id)
        formula = formulas.get(casilla_id)
        if formula is None:
            named.add(casilla_id)
            continue
        names, operand_boxes = _formula_box_gaps(revision, casilla_id, formula, values, unresolved_binding_ids)
        named.update(names)
        pending.extend(operand_boxes)
    return tuple(sorted(named))


def _with_declaration_type(
    profile: ModeloWorkProfile, *, profile_key: str, declaration_type: RentaDeclaracionType
) -> ModeloWorkProfile:
    """The same profile with its declaration-type fact replaced, held in memory only."""
    from dataclasses import replace

    from ...domain.user_profile.values import UserProfileFact, UserProfileRecord

    record = profile.record
    facts = (
        *(fact for fact in record.facts if fact.path != profile_key),
        UserProfileFact(path=profile_key, value=declaration_type.code),
    )
    payload = record.model_dump(mode="python") | {"facts": facts, "content_digest": ""}
    return replace(
        profile,
        record=UserProfileRecord.model_validate(payload, context=profile.profile_decode_context),
    )


def _require_family_unit(
    profile: ModeloWorkProfile, *, filing_period: date, operation: PinnedAuthorityOperation
) -> None:
    """Refuse a household that is not a family unit (Art. 82 LIRPF) or does not say whether it is.

    The profile states the family situation; the registry's family-situation
    vocabulary says whether that situation forms a unit only with children
    (the single-parent modality), and the profile states whether minor
    children belong to the unit. The married unit must name the spouse.
    """
    from ...domain.calculations.registry.errors import RegistryValidationError
    from ...domain.calculations.registry.situacion_familiar_catalogue import situacion_familiar_monoparental_required
    from ..user_profile.projections import profile_fact_index

    facts = profile_fact_index(profile.record, profile.profile_decode_context.schema)
    situacion = facts.get(_SITUACION_FAMILIAR_PATH)
    if not isinstance(situacion, str) or not situacion.strip():
        raise TaxationComparisonError(TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED)
    try:
        needs_children = situacion_familiar_monoparental_required(
            situacion.strip(), effective_date=filing_period, authority=operation
        )
    except RegistryValidationError as exc:
        raise TaxationComparisonError(TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED) from exc
    if not needs_children:
        # The married unit (Art. 82.1.1ª) files jointly with the spouse it names.
        spouse = facts.get(_SPOUSE_TAX_ID_PATH)
        if not isinstance(spouse, str) or not spouse.strip():
            raise TaxationComparisonError(TaxationComparisonRefusal.SPOUSE_UNSTATED)
        return
    children = facts.get(_MINOR_CHILDREN_IN_UNIT_PATH)
    if not isinstance(children, bool):
        raise TaxationComparisonError(TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED)
    if not children:
        raise TaxationComparisonError(TaxationComparisonRefusal.NO_FAMILY_UNIT)


def _without[Key, Value](mapping: Mapping[Key, Value], excluded: object) -> dict[Key, Value]:
    """The mapping without ``excluded``."""
    return {key: value for key, value in mapping.items() if key != excluded}


def _evaluate_mode(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    revision: ModeloRevision,
    basis: TaxationComparisonBasis,
    profile: ModeloWorkProfile,
    declaration_type: RentaDeclaracionType,
    replay: CallerContextCalculationInputs,
) -> TrustedMeshEvaluation:
    """Evaluate the declaration under one declaration type through the canonical calculation.

    The replayed caller context never carries the declaration type itself:
    an entered declaration-type box or answer would otherwise override the
    mode this run is for.
    """
    from .calculation_bucket_actions import evaluate_modelo_revision_from_bucket_aggregation
    from .work_missing_input import ModeloWorkMissingInputError

    try:
        return evaluate_modelo_revision_from_bucket_aggregation(
            work_unit_id,
            ports=ports,
            casilla_inputs=_without(replay.casilla_inputs, basis.declaration_casilla),
            text_casilla_inputs=_without(replay.text_casilla_inputs, basis.declaration_casilla),
            cleared_casilla_ids=tuple(
                casilla_id for casilla_id in replay.cleared_casilla_ids if casilla_id != basis.declaration_casilla
            ),
            m210_official_tipo_renta_code=replay.m210_official_tipo_renta_code,
            m210_gross_income_source_mode=replay.m210_gross_income_source_mode,
            binding_values=_without(replay.binding_values, basis.declaration_binding),
            enum_binding_values=_without(replay.enum_binding_values, basis.declaration_binding),
            borrador_snapshot_id=replay.borrador_snapshot_id,
            detail_rows=replay.detail_rows,
            filing_instance_evidence=replay.filing_instance_evidence,
            profile=_with_declaration_type(
                profile, profile_key=basis.declaration_profile_key, declaration_type=declaration_type
            ),
        )
    except ModeloWorkMissingInputError as exc:
        raise TaxationComparisonError(
            TaxationComparisonRefusal.UNRESOLVED_BOXES,
            casilla_ids=tuple(sorted(_boxes_reading_binding(revision, exc.binding_id))),
        ) from exc


def _require_settled_results(
    revision: ModeloRevision, basis: TaxationComparisonBasis, evaluations: tuple[TrustedMeshEvaluation, ...]
) -> None:
    """Refuse when either run left a compared result unresolved, naming the boxes behind it."""
    named: set[CasillaId] = set()
    for evaluation in evaluations:
        named.update(
            unresolved_result_boxes(
                revision,
                results=basis.result_casillas,
                values=evaluation.casilla_values,
                unresolved_binding_ids=frozenset(
                    (*evaluation.unresolved_binding_ids, *evaluation.unresolved_relation_ids)
                ),
            )
        )
    if named:
        raise TaxationComparisonError(TaxationComparisonRefusal.UNRESOLVED_BOXES, casilla_ids=tuple(sorted(named)))


def _selected_work_unit(work_unit_id: str, *, bucket_id: str, ports: CalculationActionPorts) -> WorkUnit:
    """The work unit of ``bucket_id`` named by ``work_unit_id``; absent is refused."""
    from .action_errors import WorkUnitNotFoundError
    from .work_selection import ModeloWorkSelectorRequest, ModeloWorkSelectorState, select_modelo_work_resolution

    selection = select_modelo_work_resolution(
        ModeloWorkSelectorRequest(work_unit_id=work_unit_id, bucket_id=bucket_id),
        catalogue=ports.work_unit_repository.load(),
        bucket_id=bucket_id,
    )
    if selection.state is ModeloWorkSelectorState.ABSENT or selection.work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    return selection.work_unit


def _comparable_snapshot(
    work_unit: WorkUnit, *, operation: PinnedAuthorityOperation
) -> tuple[RegistrySnapshot, TaxationComparisonBasis]:
    """The work unit's pinned snapshot and its comparison basis; an undeclared or outdated revision is refused."""
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    try:
        snapshot = operation.reading_snapshot(
            str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period.registry_token
        )
    except (FileNotFoundError, RegistrySnapshotError) as exc:
        raise TaxationComparisonError(TaxationComparisonRefusal.NOT_DECLARED) from exc
    basis = taxation_comparison_basis(snapshot)
    if basis is None:
        raise TaxationComparisonError(TaxationComparisonRefusal.NOT_DECLARED)
    if snapshot.revision.id != work_unit.revision_id:
        raise TaxationComparisonError(TaxationComparisonRefusal.REVISION_OUTDATED)
    return snapshot, basis


def _head_caller_context(work_unit: WorkUnit, *, ports: CalculationActionPorts) -> CalculationCallerContext:
    """The caller context of the work unit's current calculation head; no head or unknown entries are refused."""
    from .caller_context import caller_context_of

    head_id = work_unit.current_calculation_revision_id
    head = None if head_id is None else ports.calculation_repository.load(operation=ports.operation).get(head_id)
    if head is None:
        raise TaxationComparisonError(TaxationComparisonRefusal.NOT_CALCULATED)
    context = caller_context_of(head)
    if not context.operator_layer_known:
        raise TaxationComparisonError(TaxationComparisonRefusal.ENTRIES_UNKNOWN)
    return context


def compare_taxation_for_work_unit(
    work_unit_id: str,
    *,
    bucket_id: str,
    ports: CalculationActionPorts,
) -> TaxationComparisonResult:
    """Compare joint and individual filing for one work unit of the authenticated profile.

    Both runs evaluate the work unit's current calculation through the
    canonical source mesh and publish nothing; see the module docstring for
    what each run holds and what is refused.

    Raises :class:`TaxationComparisonError` with a closed refusal, and
    :class:`~cadrumo.application.modelo.action_errors.WorkUnitNotFoundError`
    when ``work_unit_id`` is not a work unit of ``bucket_id``.
    """
    from ...domain.period import calculation_filing_date
    from .caller_context import caller_context_calculation_inputs
    from .profile_readiness_gate import load_modelo_work_profile

    operation = ports.operation
    work_unit = _selected_work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    snapshot, basis = _comparable_snapshot(work_unit, operation=operation)
    context = _head_caller_context(work_unit, ports=ports)
    profile = load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context())
    if profile is None:
        raise TaxationComparisonError(TaxationComparisonRefusal.FAMILY_SITUATION_UNSTATED)
    _require_family_unit(profile, filing_period=calculation_filing_date(work_unit.period), operation=operation)
    replay = caller_context_calculation_inputs(context, revision=snapshot.revision)
    conjunta, individual = (
        _evaluate_mode(
            work_unit_id,
            ports=ports,
            revision=snapshot.revision,
            basis=basis,
            profile=profile,
            declaration_type=declaration_type,
            replay=replay,
        )
        for declaration_type in (RentaDeclaracionType.JOINT, RentaDeclaracionType.INDIVIDUAL)
    )
    _require_settled_results(snapshot.revision, basis, (conjunta, individual))
    return compare_taxation_results(
        basis, snapshot=snapshot, conjunta=conjunta.casilla_values, individual=individual.casilla_values
    )


__all__ = [
    "MATERIALITY_THRESHOLD",
    "TaxationComparisonBasis",
    "TaxationComparisonError",
    "TaxationComparisonRefusal",
    "TaxationComparisonResult",
    "TaxationRecommendation",
    "TaxationRecommendationReason",
    "compare_taxation_for_work_unit",
    "compare_taxation_results",
    "revision_compares_taxation",
    "taxation_comparison_basis",
    "unresolved_result_boxes",
]

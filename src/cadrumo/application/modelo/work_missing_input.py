"""Typed missing-input refusal from a Modelo calculation before publication.

It works with :class:`RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Final, Self

from pydantic import TypeAdapter, ValidationError

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.binding_targets import sole_bound_casilla
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.work_unit import WorkUnit
from ..operations.next_step import OperationNextStepErrorMixin, OperationNextStepWording
from .preconditions import build_modelo_precondition_failure_for_scenario
from .printed_boxes import PrintedBoxes, first_printed_dependent
from .projection_next_steps import open_work_step
from .reconciliation_sources import ReconciliationSourceNeed

_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_MISSING_BINDING_MESSAGES = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
    }
)


class ModeloWorkMissingInputError(RegistryValidationError):
    """A promptable binding refused an engine calculation before publication.

    Only the calculation action's engine-call boundary may raise this error.
    It says that no new calculation revision was published; earlier preparation
    may already have changed other state.
    """

    _binding_id: BindingId

    def __init__(
        self,
        source: RegistryValidationError,
        *,
        binding_id: BindingId,
        translated_message: str | None = None,
        context: Mapping[str, object] | None = None,
        precondition_verdict: object | None = None,
    ) -> None:
        """Retain the original refusal and its renderer-facing metadata.

        A subclass that words the refusal itself passes its own message key,
        context and verdict; otherwise the engine's are kept.
        """
        self._binding_id = binding_id
        super().__init__(
            str(source),
            context=source.context if context is None else context,
            translated_message=source.translated_message if translated_message is None else translated_message,
            registry_failure=source.registry_failure,
            precondition_verdict=(
                source.terminal_precondition_verdict if precondition_verdict is None else precondition_verdict
            ),
        )
        self.args = source.args
        self.__cause__ = source

    @property
    def binding_id(self) -> BindingId:
        """The binding the engine found without a value.

        Held privately so the registered error context, which folds public
        attributes in, never names a registry binding to the filer.
        """
        return self._binding_id

    @classmethod
    def from_registry_error(cls, source: RegistryValidationError) -> Self | None:
        """Classify only supported engine tags with one canonical binding ID."""
        if isinstance(source, cls) or source.translated_message not in _MISSING_BINDING_MESSAGES:
            return None
        value = (source.context or {}).get("binding_id")
        try:
            binding_id = _BINDING_ID_ADAPTER.validate_python(value, strict=True)
        except ValidationError:
            return None
        return cls(source, binding_id=binding_id)


_PRIOR_CARRY_SUBJECT_LEAF_KEY: Final[str] = "modelo.work.calculate"
_PRIOR_CARRY_SCENARIO_PREFIX: Final[str] = "modelo.work.calculate.prior_carries"
_PRIOR_CARRY_MESSAGE_LOCALE_KEYS: Final[Mapping[AbsenceAttestationFamily, str]] = {
    AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (
        "application.modelo.errors.prior_carries_unstated.renta_negative_general_bases_pending"
    ),
}


class ModeloPriorCarryAbsenceUnstatedError(OperationNextStepErrorMixin, ModeloWorkMissingInputError):
    """Carries from earlier ejercicios hold no value and the filer has not stated that none is pending.

    A carry the registry declares a statement of absence for is unknown, never
    zero, while no earlier return supplies it. The refusal names every carry of
    the family still open, by the boxes the form prints, so the filer answers
    them together; it is raised before any revision is published.
    """

    _family: AbsenceAttestationFamily
    _open_carry_ids: tuple[BindingId, ...]

    def __init__(
        self,
        source: RegistryValidationError,
        *,
        binding_id: BindingId,
        family: AbsenceAttestationFamily,
        open_carry_ids: tuple[BindingId, ...],
        translated_message: str,
        context: Mapping[str, object],
        precondition_verdict: object,
        next_step: OperationNextStepWording | None,
    ) -> None:
        """Keep the engine refusal as the cause and the open carries as typed facts."""
        self._family = family
        self._open_carry_ids = open_carry_ids
        super().__init__(
            source,
            binding_id=binding_id,
            translated_message=translated_message,
            context=context,
            precondition_verdict=precondition_verdict,
            next_step=next_step,
        )

    @property
    def family(self) -> AbsenceAttestationFamily:
        """The statement-of-absence family the open carries belong to."""
        return self._family

    @property
    def open_carry_ids(self) -> tuple[BindingId, ...]:
        """Every carry of the family still open, as typed facts kept out of the rendered context."""
        return self._open_carry_ids


def _carry_box(snapshot: RegistrySnapshot, boxes: PrintedBoxes, binding_id: BindingId) -> str | None:
    casilla_id = sole_bound_casilla(snapshot.revision, binding_id)
    if casilla_id is None:
        casilla_id = first_printed_dependent(snapshot, binding_id)
    return boxes.number(casilla_id)


def prior_carry_absence_unstated(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    boxes: PrintedBoxes,
    unresolved_binding_ids: Collection[BindingId],
) -> ModeloPriorCarryAbsenceUnstatedError | None:
    """The refusal for ``missing`` when its binding is a carry the filer can state holds nothing.

    Every carry of the same family that no source resolved and the caller did
    not answer is named, the refused one included. ``None`` when the binding
    declares no statement of absence, so the engine refusal stands unchanged.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    refused = bindings.get(missing.binding_id)
    family = None if refused is None else refused.absence_attestation
    if family is None:
        return None
    unresolved = frozenset(unresolved_binding_ids) | {missing.binding_id}
    open_carry_ids = tuple(
        sorted(
            binding_id
            for binding_id, binding in bindings.items()
            if binding.absence_attestation is family and binding_id in unresolved
        )
    )
    box_numbers = tuple(
        sorted(
            {box for binding_id in open_carry_ids if (box := _carry_box(snapshot, boxes, binding_id)) is not None},
            key=lambda box: (len(box), box),
        )
    )
    scenario_id = f"{_PRIOR_CARRY_SCENARIO_PREFIX}.{family.value}_unstated"
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_PRIOR_CARRY_SUBJECT_LEAF_KEY,
        scenario_id=scenario_id,
        evidence_id=f"{scenario_id}.observation",
        evidence_values={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "work_unit_id": work_unit.work_unit_id,
            "family": family.value,
            "open_carries": ",".join(open_carry_ids),
            "boxes": ",".join(box_numbers),
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values={"work_unit_id": work_unit.work_unit_id},
    )
    return ModeloPriorCarryAbsenceUnstatedError(
        missing,
        binding_id=missing.binding_id,
        family=family,
        open_carry_ids=open_carry_ids,
        translated_message=_PRIOR_CARRY_MESSAGE_LOCALE_KEYS[family],
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "boxes": ", ".join(box_numbers),
        },
        precondition_verdict=failure.verdict,
        next_step=open_work_step(work_unit),
    )


class ModeloPriorPeriodUnfiledError(OperationNextStepErrorMixin, ModeloWorkMissingInputError):
    """An earlier period of the same ejercicio this one carries from has no return the carry can read.

    The carry is read from the filed earlier return, so it is unknown, never
    zero, until that return is filed; the refusal names the earliest such
    period and serves the work its standing calls for: create, calculate,
    verify or file its declaration. It is raised before any revision is
    published.
    """

    _source_needs: tuple[ReconciliationSourceNeed, ...]

    def __init__(
        self,
        source: RegistryValidationError,
        *,
        binding_id: BindingId,
        source_needs: tuple[ReconciliationSourceNeed, ...],
        translated_message: str,
        context: Mapping[str, object],
        precondition_verdict: object,
        next_step: OperationNextStepWording | None,
    ) -> None:
        """Keep the engine refusal as the cause and each unfiled earlier period as a typed fact."""
        self._source_needs = source_needs
        super().__init__(
            source,
            binding_id=binding_id,
            translated_message=translated_message,
            context=context,
            precondition_verdict=precondition_verdict,
            next_step=next_step,
        )

    @property
    def source_needs(self) -> tuple[ReconciliationSourceNeed, ...]:
        """Each earlier period the carry reads that is not filed, and where it stands, in period order."""
        return self._source_needs

    @property
    def unfiled_period(self) -> Period:
        """The earliest earlier period whose filed return the carry needs."""
        return self._source_needs[0].period


_PRIOR_FILING_SCENARIO_PREFIX: Final[str] = "modelo.work.calculate.prior_filing"
_PRIOR_PERIOD_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.prior_period_unfiled"
type SourcePeriodNeeds = Callable[[tuple[tuple[str, Period], ...]], tuple[ReconciliationSourceNeed, ...]]
"""Where each (source modelo, period) stands, for the periods that owe a return."""


def _same_ejercicio_periods_read(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
) -> tuple[tuple[str, Period], ...]:
    """Every (modelo, period) the refused carry reads, when all are of this modelo and ejercicio; otherwise none."""
    requirements = tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        if missing.binding_id in requirement.binding_ids
    )
    if any(
        requirement.source_modelo != str(work_unit.modelo) or requirement.filing_year != work_unit.filing_year
        for requirement in requirements
    ):
        return ()
    return tuple(
        (str(requirement.source_modelo), Period.from_year_and_code(requirement.filing_year, code))
        for requirement in requirements
        for code in requirement.periods
    )


def prior_period_unfiled(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    source_needs: SourcePeriodNeeds,
) -> ModeloPriorPeriodUnfiledError | None:
    """The refusal for ``missing`` when its carry waits on an earlier period of this ejercicio that is not filed.

    ``source_needs`` says where each period the carry reads stands, as the
    fold reads it, leaving out periods that owe no return. ``None`` when the
    carry reads another modelo or ejercicio, or no period it reads needs work,
    so the engine refusal stands unchanged.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    periods = _same_ejercicio_periods_read(missing, work_unit=work_unit, snapshot=snapshot)
    needs = source_needs(periods) if periods else ()
    if not needs:
        return None
    first = needs[0]
    scenario, action_argument_values = first.door()
    scenario_id = f"{_PRIOR_FILING_SCENARIO_PREFIX}.{scenario}"
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_PRIOR_CARRY_SUBJECT_LEAF_KEY,
        scenario_id=scenario_id,
        evidence_id=f"{_PRIOR_FILING_SCENARIO_PREFIX}.observation",
        evidence_values={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "work_unit_id": work_unit.work_unit_id,
            "source_periods": "|".join(f"{need.period.registry_token}:{need.standing.value}" for need in needs),
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=action_argument_values,
    )
    return ModeloPriorPeriodUnfiledError(
        missing,
        binding_id=missing.binding_id,
        source_needs=needs,
        translated_message=_PRIOR_PERIOD_MESSAGE_LOCALE_KEY,
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "unfiled_period": first.period.registry_token,
        },
        precondition_verdict=failure.verdict,
        next_step=first.next_step(),
    )


__all__ = [
    "ModeloPriorCarryAbsenceUnstatedError",
    "ModeloPriorPeriodUnfiledError",
    "ModeloWorkMissingInputError",
    "prior_carry_absence_unstated",
    "prior_period_unfiled",
]

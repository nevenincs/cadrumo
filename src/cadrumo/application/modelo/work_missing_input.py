"""Typed missing-input refusal from a Modelo calculation before publication.

It works with :class:`RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
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
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
from ..operations.next_step import OperationNextStepErrorMixin, OperationNextStepWording
from .preconditions import build_modelo_precondition_failure_for_scenario
from .printed_boxes import PrintedBoxes, first_printed_dependent
from .projection_next_steps import create_work_step, open_work_step

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
    """An earlier period of the same ejercicio this one carries from has no filed return.

    The carry is read from the filed earlier return, so it is unknown, never
    zero, until that return is filed; the refusal names the earliest such
    period and opens its declaration, or offers to create it when none exists.
    It is raised before any revision is published.
    """

    _unfiled_period: Period
    _unfiled_work_unit_id: str | None

    def __init__(
        self,
        source: RegistryValidationError,
        *,
        binding_id: BindingId,
        unfiled_period: Period,
        unfiled_work_unit_id: str | None,
        translated_message: str,
        context: Mapping[str, object],
        precondition_verdict: object,
        next_step: OperationNextStepWording | None,
    ) -> None:
        """Keep the engine refusal as the cause and the unfiled period as a typed fact."""
        self._unfiled_period = unfiled_period
        self._unfiled_work_unit_id = unfiled_work_unit_id
        super().__init__(
            source,
            binding_id=binding_id,
            translated_message=translated_message,
            context=context,
            precondition_verdict=precondition_verdict,
            next_step=next_step,
        )

    @property
    def unfiled_period(self) -> Period:
        """The earliest earlier period whose filed return the carry needs."""
        return self._unfiled_period

    @property
    def unfiled_work_unit_id(self) -> str | None:
        """The declaration that period already has, or ``None`` when it has none yet."""
        return self._unfiled_work_unit_id


_PRIOR_PERIOD_SCENARIO_PREFIX: Final[str] = "modelo.work.calculate.prior_period"
_PRIOR_PERIOD_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.prior_period_unfiled"


def _same_ejercicio_periods_read(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
) -> frozenset[Period]:
    """Every period the refused carry reads, when all are of this modelo and ejercicio; otherwise none."""
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
        return frozenset[Period]()
    return frozenset(
        Period.from_year_and_code(requirement.filing_year, code)
        for requirement in requirements
        for code in requirement.periods
    )


def _earliest_unfiled_prior_period(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    observations: CalculationObservationRepositoryProtocol,
) -> Period | None:
    """The earliest same-ejercicio period of this modelo the refused carry reads and no filed return covers.

    ``None`` unless every period the carry reads is an earlier period of the
    same modelo and ejercicio: a carry from another modelo or ejercicio is
    filed elsewhere, and its refusal stays the engine's.
    """
    read_periods = _same_ejercicio_periods_read(missing, work_unit=work_unit, snapshot=snapshot)
    unfiled = sorted(
        (period for period in read_periods if observations.load_observation(str(work_unit.modelo), period) is None),
        key=lambda period: period.quarter_ordinal or 0,
    )
    return unfiled[0] if unfiled else None


def prior_period_unfiled(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    observations: CalculationObservationRepositoryProtocol,
    work_units: Iterable[WorkUnit],
) -> ModeloPriorPeriodUnfiledError | None:
    """The refusal for ``missing`` when its carry waits on an earlier period of this ejercicio that is not filed.

    The door files that period's declaration when it exists and creates it
    otherwise. ``None`` when the carry reads elsewhere or every period it
    reads is filed, so the engine refusal stands unchanged.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    unfiled_period = _earliest_unfiled_prior_period(
        missing, work_unit=work_unit, snapshot=snapshot, observations=observations
    )
    if unfiled_period is None:
        return None
    modelo = str(work_unit.modelo)
    unfiled_unit = next(
        (
            unit
            for unit in work_units
            if str(unit.modelo) == modelo
            and unit.period == unfiled_period
            and unit.state is WorkUnitState.BORRADOR
            and unit.bucket_id == work_unit.bucket_id
        ),
        None,
    )
    evidence_values: dict[str, str | int | bool] = {
        "modelo": modelo,
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "work_unit_id": work_unit.work_unit_id,
        "unfiled_period": unfiled_period.registry_token,
        "unfiled_work_unit_present": unfiled_unit is not None,
    }
    if unfiled_unit is None:
        failure = build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=_PRIOR_CARRY_SUBJECT_LEAF_KEY,
            scenario_id=f"{_PRIOR_PERIOD_SCENARIO_PREFIX}.unfiled_without_work",
            evidence_id=f"{_PRIOR_PERIOD_SCENARIO_PREFIX}.observation",
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            action_argument_values={
                "modelo": modelo,
                "period": unfiled_period.registry_token,
                "year": unfiled_period.filing_year,
            },
        )
        next_step = create_work_step(modelo=modelo, period=unfiled_period)
    else:
        failure = build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=_PRIOR_CARRY_SUBJECT_LEAF_KEY,
            scenario_id=f"{_PRIOR_PERIOD_SCENARIO_PREFIX}.unfiled",
            evidence_id=f"{_PRIOR_PERIOD_SCENARIO_PREFIX}.observation",
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            action_argument_values={"work_unit_id": unfiled_unit.work_unit_id},
        )
        next_step = open_work_step(unfiled_unit)
    return ModeloPriorPeriodUnfiledError(
        missing,
        binding_id=missing.binding_id,
        unfiled_period=unfiled_period,
        unfiled_work_unit_id=None if unfiled_unit is None else unfiled_unit.work_unit_id,
        translated_message=_PRIOR_PERIOD_MESSAGE_LOCALE_KEY,
        context={
            "modelo": modelo,
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "unfiled_period": unfiled_period.registry_token,
        },
        precondition_verdict=failure.verdict,
        next_step=next_step,
    )


__all__ = [
    "ModeloPriorCarryAbsenceUnstatedError",
    "ModeloPriorPeriodUnfiledError",
    "ModeloWorkMissingInputError",
    "prior_carry_absence_unstated",
    "prior_period_unfiled",
]

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
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from ...domain.modelos.work_unit import WorkUnit
from ..operations.next_step import OperationNextStepErrorMixin, OperationNextStepWording
from .calculation_input_refusal_doors import missing_input_listing_verdict
from .edit_admission import permitted_binding_entry
from .edit_models import ModeloEditBindingIntentKind, ModeloEditWritableBindingOverrideSurfaceEntryV1
from .preconditions import build_modelo_precondition_failure_for_scenario
from .printed_boxes import PrintedBoxes, first_printed_dependent
from .projection_next_steps import open_work_step
from .reconciliation_sources import ReconciliationSourceNeed
from .row_filled_bindings import row_filled_binding_ids

_BINDING_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BindingId)
_UNOBSERVED_PREVIOUS_FILING_MESSAGE: Final[str] = "errors.calc.previous_filing_casillas_unobserved"
_MISSING_BINDING_MESSAGES = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.date_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
    }
)


class ModeloWorkMissingInputError(OperationNextStepErrorMixin, RegistryValidationError):
    """A promptable binding refused an engine calculation before publication.

    Only the calculation action's engine-call boundary may raise this error.
    It says that no new calculation revision was published; earlier preparation
    may already have changed other state. The operator supplies the input, so
    the refusal built by :func:`input_required` names it and serves the door.
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
        next_step: OperationNextStepWording | None = None,
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
            next_step=next_step,
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
    def from_registry_error(
        cls, source: RegistryValidationError, *, precondition_verdict: object | None = None
    ) -> Self | None:
        """Classify only supported engine tags with one canonical binding ID."""
        if isinstance(source, cls) or source.translated_message not in _MISSING_BINDING_MESSAGES:
            return None
        value = (source.context or {}).get("binding_id")
        try:
            binding_id = _BINDING_ID_ADAPTER.validate_python(value, strict=True)
        except ValidationError:
            return None
        return cls(source, binding_id=binding_id, precondition_verdict=precondition_verdict)

    @classmethod
    def from_unobserved_previous_filing(
        cls, source: RegistryValidationError, *, precondition_verdict: object | None = None
    ) -> Self | None:
        """Classify a stored earlier return that does not show the boxes a carry reads, by its first carry.

        The engine names every carry of that return it could not read; the
        first, in identifier order, is the one the refusal addresses.
        """
        if isinstance(source, cls) or source.translated_message != _UNOBSERVED_PREVIOUS_FILING_MESSAGE:
            return None
        raw = (source.context or {}).get("binding_ids")
        if not isinstance(raw, str) or not raw:
            return None
        try:
            binding_id = _BINDING_ID_ADAPTER.validate_python(sorted(raw.split(","))[0], strict=True)
        except ValidationError:
            return None
        return cls(source, binding_id=binding_id, precondition_verdict=precondition_verdict)

    @property
    def previous_filing_unobserved(self) -> bool:
        """Whether the engine refused because a stored earlier return does not show the boxes the carry reads."""
        cause = self.__cause__
        return isinstance(cause, RegistryValidationError) and (
            cause.translated_message == _UNOBSERVED_PREVIOUS_FILING_MESSAGE
        )


_PRIOR_CARRY_SUBJECT_LEAF_KEY: Final[str] = "modelo.work.calculate"
_PRIOR_CARRY_SCENARIO_PREFIX: Final[str] = "modelo.work.calculate.prior_carries"
PRIOR_CARRY_MESSAGE_LOCALE_KEYS: Final[Mapping[AbsenceAttestationFamily, str]] = {
    AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (
        "application.modelo.errors.prior_carries_unstated.renta_negative_general_bases_pending"
    ),
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING: (
        "application.modelo.errors.prior_carries_unstated.renta_negative_savings_capital_income_pending"
    ),
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING: (
        "application.modelo.errors.prior_carries_unstated.renta_negative_savings_gains_losses_pending"
    ),
}


class ModeloPriorCarryAbsenceUnstatedError(ModeloWorkMissingInputError):
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
        translated_message=PRIOR_CARRY_MESSAGE_LOCALE_KEYS[family],
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "boxes": ", ".join(box_numbers),
        },
        precondition_verdict=failure.verdict,
        next_step=open_work_step(work_unit),
    )


class ModeloPriorPeriodUnfiledError(ModeloWorkMissingInputError):
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


_INPUT_REQUIRED_SCENARIO_ID: Final[str] = "modelo.work.calculate.input.binding_unanswered"
_OVERRIDE_REQUIRED_SCENARIO_ID: Final[str] = "modelo.work.calculate.input.override_unanswered"
_INPUT_REQUIRED_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.input_required"
_INPUT_REQUIRED_UNPRINTED_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.input_required_unprinted"
_UNOBSERVED_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.previous_filing_unobserved"
_UNOBSERVED_UNPRINTED_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.previous_filing_unobserved_unprinted"


def override_admitted(
    snapshot: RegistrySnapshot, binding_id: BindingId, *, period: str, layout: FormLayoutDefinition | None
) -> bool:
    """Whether the edit admission lets the operator state ``binding_id``'s value for ``period``.

    The same classification the edit baseline publishes: a manual input or a
    carry of the caller-override precedence ladder, read by the calculation
    for the period, not filled row by row, with a value channel. ``layout`` is
    the revision's declared form layout.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    binding = next((item for item in snapshot.revision.bindings if item.id == binding_id), None)
    if binding is None:
        return False
    entry = permitted_binding_entry(
        binding,
        revision=snapshot.revision,
        period=period,
        row_filled=row_filled_binding_ids(snapshot.revision, layout),
    )
    return (
        isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in entry.allowed_intents
    )


def _input_words(
    missing: ModeloWorkMissingInputError, *, work_unit: WorkUnit, box: str | None
) -> tuple[str, dict[str, object]]:
    """The message key and context that say which input has no value and why."""
    context: dict[str, object] = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "binding": missing.binding_id,
    }
    if box is not None:
        context["boxes"] = box
    cause = missing.__cause__
    if not (missing.previous_filing_unobserved and isinstance(cause, RegistryValidationError)):
        return (
            _INPUT_REQUIRED_MESSAGE_LOCALE_KEY if box is not None else _INPUT_REQUIRED_UNPRINTED_MESSAGE_LOCALE_KEY
        ), context
    source = cause.context or {}
    context |= {
        "source_modelo": source.get("source_modelo", ""),
        "source_filing_year": source.get("source_filing_year", ""),
        "source_period": source.get("source_period", ""),
        "source_boxes": str(source.get("casilla_ids", "")).replace(",", ", "),
    }
    return (_UNOBSERVED_MESSAGE_LOCALE_KEY if box is not None else _UNOBSERVED_UNPRINTED_MESSAGE_LOCALE_KEY), context


def input_required(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    boxes: PrintedBoxes,
    overridable: bool = False,
) -> ModeloWorkMissingInputError:
    """The refusal for ``missing`` naming the input the operator supplies and the doors that lead to it.

    The words name the binding and the box it feeds when the form prints one;
    for a stored earlier return that does not show the boxes the carry reads,
    they name that return and its boxes too, and the evidence carries the
    earlier return's modelo, year and period. When the operator may state the
    input's value (``overridable``, from :func:`override_admitted`), the door
    is the override bound to this work unit and input, and the value is the
    operator's to give; otherwise it is the declared binding listing for this
    modelo, year and period. The next step opens the work unit whose form
    takes the value.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    box = _carry_box(snapshot, boxes, missing.binding_id)
    message_key, context = _input_words(missing, work_unit=work_unit, box=box)
    source_coordinates = {
        key: str(value)
        for key in ("source_modelo", "source_filing_year", "source_period")
        if (value := context.get(key)) is not None
    }
    scenario_id = _OVERRIDE_REQUIRED_SCENARIO_ID if overridable else _INPUT_REQUIRED_SCENARIO_ID
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_PRIOR_CARRY_SUBJECT_LEAF_KEY,
        scenario_id=scenario_id,
        evidence_id=f"{scenario_id}.observation",
        evidence_values={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "binding_id": missing.binding_id,
            "box": "" if box is None else box,
            **source_coordinates,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=(
            {"work_unit_id": work_unit.work_unit_id, "binding_id": missing.binding_id}
            if overridable
            else {
                "modelo": str(work_unit.modelo),
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            }
        ),
        # The value is the operator's to state; the door never supplies one.
        missing_action_arguments=("value",) if overridable else (),
    )
    return ModeloWorkMissingInputError(
        missing,
        binding_id=missing.binding_id,
        translated_message=message_key,
        context=context,
        precondition_verdict=failure.verdict,
        next_step=open_work_step(work_unit),
    )


def previous_filing_unobserved(
    error: RegistryValidationError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    boxes: PrintedBoxes,
    layout: FormLayoutDefinition | None,
) -> ModeloWorkMissingInputError | None:
    """The refusal for a stored earlier return that does not show the boxes a carry reads, with its door.

    ``None`` when ``error`` is another refusal, or when the operator may not
    state the carry on this work unit, so the source refusal stands unchanged.
    ``layout`` is the revision's declared form layout.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    unobserved = ModeloWorkMissingInputError.from_unobserved_previous_filing(
        error, precondition_verdict=missing_input_listing_verdict(work_unit)
    )
    if unobserved is None or not override_admitted(
        snapshot, unobserved.binding_id, period=work_unit.period.registry_token, layout=layout
    ):
        return None
    return input_required(unobserved, work_unit=work_unit, snapshot=snapshot, boxes=boxes, overridable=True)


__all__ = [
    "PRIOR_CARRY_MESSAGE_LOCALE_KEYS",
    "ModeloPriorCarryAbsenceUnstatedError",
    "ModeloPriorPeriodUnfiledError",
    "ModeloWorkMissingInputError",
    "input_required",
    "override_admitted",
    "previous_filing_unobserved",
    "prior_carry_absence_unstated",
    "prior_period_unfiled",
]

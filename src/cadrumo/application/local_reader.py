"""The local document reader: the local AI program and the model the person picked to read with.

Cadrumo defines no model, and nothing here asks the local AI server anything.
Each role reads with the one model the person picked in the agent's model
picker, as the agent service answers it; the running operation asks it through its model-run port
(:func:`read_role_lanes`). A lane whose catalogue entry says it reads off this
computer needs nothing local. A lane that stays on this computer reads through
the local AI program: the components role's status row for the local AI says
whether the program is set up and which version it is, and the lane carries
whether the program's server holds the picked model, as the agent's live
catalogue states it.

An on-host role is judged in a fixed order: a program the status row does not
report usable refuses with the row's own recovery; then a model the server does
not hold refuses with the local AI setup; then a model whose presence nobody
stated refuses as unknown, never as missing. No judgement is made here about
this computer's hardware or memory: the native setup owns the hardware floor,
and whether a model loads is the agent's answer when it loads it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, model_validator

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.model_roles import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .dependency_contracts import DependencyState, DependencyStatusRow
from .operations.model_runs import current_model_run_port
from .operator_actions.models import PreconditionVerdict
from .provisioning import DependencyStatus
from .provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    provisioning_setup_verdict,
    require_provisioning_verdict,
)

__all__ = [
    "EXTRACTION_READER_ROLES",
    "LOCAL_AI_PROGRAM_SERVICE",
    "LocalAiProgram",
    "LocalReaderDocumentReadiness",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "ProgramRow",
    "RoleLane",
    "judge_local_ai_program",
    "probe_local_ai_program",
    "read_local_reader_status",
    "read_role_lanes",
]

#: The roles invoice evidence extraction reads with, text layer first.
EXTRACTION_READER_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION)

#: The doctor row id for the local AI program.
LOCAL_AI_PROGRAM_SERVICE = "local-ai:program"

#: The states in which the components role reports an item usable.
_USABLE_STATES = frozenset({DependencyState.READY, DependencyState.STALE})

type RoleLane = ModelRunLane | ModelRunRefusal
"""The lane the agent service resolved for one role, or why it resolves none."""

type ProgramRow = DependencyStatusRow | None
"""The components role's status row for the local AI, or ``None`` when the role reported none."""


class LocalReaderDocumentReadiness(StrEnum):
    """Which invoice documents this machine can turn into drafts.

    Text-layer documents are read by label rules that need no model, so they
    are always readable; the model only fills fields the labels do not print.
    Every document is readable only when :attr:`LocalReaderStatus.extraction_ready`.
    """

    ALL_DOCUMENTS = "all_documents"
    TEXT_LAYER_ONLY = "text_layer_only"


async def read_role_lanes(roles: Iterable[ModelRole]) -> dict[ModelRole, RoleLane]:
    """Return the lane the agent service resolves for each of ``roles``, as the running operation sees it.

    Outside an operation there is no model-run port, so every role reads as
    the service being unavailable rather than as having no selection.
    """
    port = current_model_run_port()
    if port is None:
        return {role: ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE) for role in roles}
    return {role: await port.lookup(role) for role in roles}


class LocalAiProgram(ProvisioningOutcome):
    """The local AI program as the components role's status row reports it.

    ``state`` is ``None`` when the role reported no row; that is unknown, never
    absent. ``available`` is true for a ready or stale program, and ``version``
    is the version of a program that is there; an absent program's row names
    the version setup would install, which is not reported here.
    """

    state: DependencyState | None = None
    version: str | None = None
    available: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_program_outcome(self) -> LocalAiProgram:
        require_provisioning_verdict(failed=not self.available, verdict=self.precondition_verdict)
        return self


def _state_fact(row: ProgramRow) -> str:
    return "unknown" if row is None else row.state.value


def _program_verdict(row: ProgramRow, facts: Mapping[str, ProvisioningFactValue]) -> PreconditionVerdict:
    """Return the refusal for a program the row does not report usable, naming the row's own recovery."""
    condition = ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    if row is not None and row.recovery_action_id is not None:
        return provisioning_setup_verdict(condition, facts=facts, action_id=row.recovery_action_id)
    return provisioning_no_recovery_verdict(condition, facts=facts)


def judge_local_ai_program(row: ProgramRow) -> LocalAiProgram:
    """Judge the local AI program from its status row alone; nothing is asked of the program."""
    available = row is not None and row.state in _USABLE_STATES
    version = row.version if row is not None and available else None
    facts: dict[str, ProvisioningFactValue] = {"local_ai_state": _state_fact(row)}
    if version is not None:
        facts["local_ai_version"] = version
    return LocalAiProgram(
        state=None if row is None else row.state,
        version=version,
        available=available,
        facts=facts,
        precondition_verdict=None if available else _program_verdict(row, facts),
    )


def probe_local_ai_program(row: ProgramRow) -> DependencyStatus:
    """Report the local AI program's row for a configuration check, from the components role's status row.

    The program's health only. Every role reads with the model the person
    picked, which the agent service answers; this row judges no model.

    Returns:
        A :class:`DependencyStatus` on the ``local-ai:program`` row. Never raises.
    """
    program = judge_local_ai_program(row)
    return DependencyStatus(
        service=LOCAL_AI_PROGRAM_SERVICE,
        available=program.available,
        facts=program.facts,
        precondition_verdict=program.precondition_verdict,
    )


class LocalReaderRoleStatus(BaseModel):
    """One role's reader: the model its on-host lane loads, and whether the program's server holds it.

    ``model`` is the selected model of a lane that stays on this computer, and
    ``None`` for a lane that reads off it or a role with no usable lane.
    ``installed`` is ``None`` when nobody stated it or it does not apply -- an
    off-host lane loads nothing here -- and ``None`` must not render as "not
    installed".
    """

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    installed: bool | None = None
    ready: bool
    failed_condition_id: str | None = None
    #: The operator action the judgement named for the failed condition, or
    #: ``None`` when it named none -- a role with no selection, a program whose
    #: state is unknown, or a ready role.
    recovery_action_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area.

    ``extraction_ready`` is true only when both invoice-extraction roles can
    read: each has a lane, and an on-host lane's model is held by a usable
    program. It is the single claim a surface may use to say every document
    can be read. ``document_readiness`` says which documents can be read
    either way, and ``text_layer_model_fill_available`` whether text-layer
    fields the labels do not print can be filled by the text role.
    """

    model_config = STRICT_FROZEN_CONFIG

    program: LocalAiProgram
    roles: tuple[LocalReaderRoleStatus, ...]
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _readiness_agrees(self) -> LocalReaderStatus:
        expected = (
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if self.extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        )
        if self.document_readiness is not expected:
            raise ValueError("document readiness must follow extraction readiness")
        if self.extraction_ready and not self.text_layer_model_fill_available:
            raise ValueError("an extraction-ready reader can fill text-layer fields")
        return self


@dataclass(frozen=True, slots=True)
class _Judgement:
    ready: bool
    verdict: PreconditionVerdict | None = None


def selected_model_condition(code: ModelRunRefusalCode) -> ProvisioningPreconditionCondition:
    """Return the failed condition a refused role reports: a model that cannot read images, or no usable model."""
    if code is ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES:
        return ProvisioningPreconditionCondition.SELECTED_MODEL_READS_IMAGES
    return ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE


def _refusal_judgement(role: ModelRole, refusal: ModelRunRefusal) -> _Judgement:
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "model_run_refusal": refusal.code.value,
        "role_selection_required": refusal.code is ModelRunRefusalCode.NO_SELECTION,
    }
    return _Judgement(
        ready=False,
        verdict=provisioning_no_recovery_verdict(selected_model_condition(refusal.code), facts=facts),
    )


def _on_host_judgement(role: ModelRole, lane: ModelRunLane, row: ProgramRow) -> _Judgement:
    """Judge an on-host lane in the fixed order: the program, then the model itself."""
    model = lane.model
    if row is None or row.state not in _USABLE_STATES:
        return _Judgement(
            ready=False, verdict=_program_verdict(row, {"role": role.value, "local_ai_state": _state_fact(row)})
        )
    if lane.installed is False:
        return _Judgement(
            ready=False,
            verdict=provisioning_setup_verdict(
                ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
                facts={"role": role.value, "model": model, "role_model_installed": False},
                action_id=LOCAL_AI_PROVISION_ACTION_ID,
            ),
        )
    if lane.installed is None:
        return _Judgement(
            ready=False,
            verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                facts={"role": role.value, "model": model, "role_model_installed_known": False},
            ),
        )
    return _Judgement(ready=True)


def _role_status(role: ModelRole, answer: RoleLane, row: ProgramRow) -> LocalReaderRoleStatus:
    if isinstance(answer, ModelRunRefusal):
        return _status_row(role, _refusal_judgement(role, answer))
    if answer.reads_off_host:
        return LocalReaderRoleStatus(role=role, ready=True)
    judgement = _on_host_judgement(role, answer, row)
    return _status_row(role, judgement, model=answer.model, installed=answer.installed)


def _status_row(
    role: ModelRole,
    judgement: _Judgement,
    *,
    model: str | None = None,
    installed: bool | None = None,
) -> LocalReaderRoleStatus:
    verdict = judgement.verdict
    return LocalReaderRoleStatus(
        role=role,
        model=model,
        installed=installed,
        ready=judgement.ready,
        failed_condition_id=None if verdict is None else verdict.failed_condition_id,
        recovery_action_id=None if verdict is None or verdict.action is None else verdict.action.action_id,
    )


def _selected_roles(roles: Iterable[ModelRole] | None) -> tuple[ModelRole, ...]:
    return tuple(ModelRole) if roles is None else tuple(roles)


def _answer(lanes: Mapping[ModelRole, RoleLane], role: ModelRole) -> RoleLane:
    # A role the caller did not look up has no lane this read can judge.
    return lanes.get(role, ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE))


def read_local_reader_status(
    lanes: Mapping[ModelRole, RoleLane],
    program: ProgramRow,
    *,
    roles: Iterable[ModelRole] | None = None,
) -> LocalReaderStatus:
    """Judge the program's row and every role's selected lane into one projection.

    ``lanes`` is what :func:`read_role_lanes` resolved for each role and
    ``program`` the components role's status row for the local AI. Reads
    nothing from the local AI or from this computer: nothing is started,
    pulled, loaded or measured.
    """
    role_rows = tuple(_role_status(role, _answer(lanes, role), program) for role in _selected_roles(roles))
    by_role = {row.role: row for row in role_rows}
    for role in EXTRACTION_READER_ROLES:
        if role not in by_role:
            by_role[role] = _role_status(role, _answer(lanes, role), program)
    extraction_ready = all(by_role[role].ready for role in EXTRACTION_READER_ROLES)
    return LocalReaderStatus(
        program=judge_local_ai_program(program),
        roles=role_rows,
        extraction_ready=extraction_ready,
        document_readiness=(
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        ),
        text_layer_model_fill_available=by_role[ModelRole.TEXT_EXTRACTION].ready,
    )

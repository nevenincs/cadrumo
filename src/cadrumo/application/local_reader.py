"""The local document reader: the local AI program and the models the person selected for it.

Cadrumo defines no model. Each role reads with the lane and model the person
selected, which the agent service resolves; the running operation asks it
through its model-run port (:func:`read_role_lanes`). A lane whose catalogue
entry says it reads off this computer needs nothing local. A lane that stays on
this computer reads through the local AI program, so its model must be one the
program's server holds, and this computer must be able to hold it.

The native component engine installs the local AI and the runtime manager runs
its one server; the engine's local AI record says where the program and the
models are and which fixed address the server answers on. This module locates
the local AI from that record alone, aims every reading at the recorded
address, and turns what the server answers into the projections a status
surface renders. An operator who configured an endpoint of their own runs that
server themselves, and it is used as written.

An on-host role is judged in a fixed order: a model this computer's installed
memory cannot hold refuses first and offers nothing, because setup cannot
change it; then a local AI the record does not locate, or a server that does
not answer at its address, refuses with the local AI setup; then a missing
model does too. Free memory is never judged here: whether a load fits at that
moment is decided at the load by
:func:`.provisioning_runtime.assess_model_load_contention`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, model_validator

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ..core.component_records import (
    LocatedLocalAi,
    component_records_root,
    locate_local_ai,
    uses_managed_local_ai,
)
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hardware import ContentionCause
from ..core.model_roles import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .operations.model_runs import current_model_run_port
from .operator_actions.models import PreconditionVerdict
from .provisioning import DependencyStatus, HardwareProfile, below_capacity_floor, probe_hardware_profile
from .provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    provisioning_setup_verdict,
)
from .provisioning_host import ExecutableLookup, RuntimeHostStatus, probe_runtime_host
from .provisioning_runtime import (
    InstalledModel,
    RuntimeResident,
    assess_model_load_contention,
    read_installed_models,
    read_runtime_residents,
    runtime_model_names_match,
)

__all__ = [
    "EXTRACTION_READER_ROLES",
    "LOCAL_AI_PROGRAM_SERVICE",
    "LocalReaderDocumentReadiness",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "RoleLane",
    "lane_requirement_bytes",
    "probe_local_ai_program",
    "read_local_reader_status",
    "read_role_lanes",
]

#: The roles invoice evidence extraction reads with, text layer first.
EXTRACTION_READER_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION)

#: The doctor row id for the local AI program.
LOCAL_AI_PROGRAM_SERVICE = "local-ai:program"

type RoleLane = ModelRunLane | ModelRunRefusal
"""The lane the agent service resolved for one role, or why it resolves none."""


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


def local_ai_settings(settings: Settings) -> tuple[Settings, LocatedLocalAi | None]:
    """Return ``settings`` aimed at the server the local AI record names, and that location.

    An operator's own endpoint keeps ``settings`` as they are and has no
    location. Without a record that locates the local AI, ``settings`` are
    returned unchanged beside the location that says why.
    """
    if not uses_managed_local_ai(settings):
        return settings, None
    located = locate_local_ai(records_root=component_records_root(settings))
    url = located.chat_url
    if located.located and url is not None and url != settings.cadrumo_llm_ollama_chat_url:
        return settings.model_copy(update={"cadrumo_llm_ollama_chat_url": url}), located
    return settings, located


def _locates(located: LocatedLocalAi | None) -> bool:
    """Whether there is a server to ask: an operator's own endpoint, or a located local AI."""
    return located is None or located.located


def _setup_verdict(
    condition: ProvisioningPreconditionCondition, facts: Mapping[str, ProvisioningFactValue]
) -> PreconditionVerdict:
    return provisioning_setup_verdict(condition, facts=facts, action_id=LOCAL_AI_PROVISION_ACTION_ID)


def probe_local_ai_program(settings: Settings | None = None) -> DependencyStatus:
    """Report whether the local AI program is located and its server answers.

    The program's health only. Which model each role reads with is the
    person's selection, which the agent's catalogue and the setup surfaces
    report; this row judges no model.

    Returns:
        A :class:`DependencyStatus` on the ``local-ai:program`` row. Never raises.
    """
    resolved, located = local_ai_settings(settings if settings is not None else load_settings())
    if located is not None and not located.located:
        facts: dict[str, ProvisioningFactValue] = {
            "local_ai_located": False,
            "record": located.component.outcome.value,
        }
        return DependencyStatus(
            service=LOCAL_AI_PROGRAM_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=_setup_verdict(ProvisioningPreconditionCondition.RUNTIME_INSTALLED, facts),
        )
    if read_installed_models(resolved) is None:
        # Whether the server is the managed one, never its address: an
        # operator's own endpoint can name a host or carry credentials.
        facts = {"runtime_reachable": False, "operator_endpoint": located is None}
        return DependencyStatus(
            service=LOCAL_AI_PROGRAM_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=_setup_verdict(ProvisioningPreconditionCondition.RUNTIME_REACHABLE, facts),
        )
    return DependencyStatus(
        service=LOCAL_AI_PROGRAM_SERVICE,
        available=True,
        facts={"runtime_reachable": True, "operator_endpoint": located is None},
    )


class LocalReaderRoleStatus(BaseModel):
    """One role's reader: the model its on-host lane loads, and what the program says about it.

    ``model`` is the selected model of a lane that stays on this computer, and
    ``None`` for a lane that reads off it or a role with no usable lane.
    ``installed``, ``resident`` and ``load_admitted`` are ``None`` when the
    answer could not be measured or does not apply -- an off-host lane loads
    nothing here, and an unreachable program has no inventory -- and ``None``
    must not render as "not installed".
    """

    model_config = STRICT_FROZEN_CONFIG

    role: ModelRole
    model: str | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: tuple[ContentionCause, ...] = ()
    ready: bool
    failed_condition_id: str | None = None
    #: The operator action the judgement named for the failed condition, or
    #: ``None`` when it named none -- a role with no selection, a model this
    #: computer cannot hold, or a ready role.
    recovery_action_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area.

    ``extraction_ready`` is true only when both invoice-extraction roles can
    read: each has a lane, and an on-host lane's model is held by an answering
    program. It is the single claim a surface may use to say every document can
    be read. ``document_readiness`` says which documents can be read either
    way, and ``text_layer_model_fill_available`` whether text-layer fields the
    labels do not print can be filled by the text role.
    """

    model_config = STRICT_FROZEN_CONFIG

    host: RuntimeHostStatus
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
class _Measured:
    """What one status read measured once and every role row is judged against."""

    settings: Settings
    located: LocatedLocalAi | None
    inventory: tuple[InstalledModel, ...] | None
    residents: tuple[RuntimeResident, ...] | None
    hardware: HardwareProfile


@dataclass(frozen=True, slots=True)
class _Judgement:
    ready: bool
    verdict: PreconditionVerdict | None = None


def _names(entries: Iterable[InstalledModel | RuntimeResident] | None) -> tuple[str, ...] | None:
    return None if entries is None else tuple(entry.name for entry in entries)


def _present(model: str, names: tuple[str, ...] | None) -> bool | None:
    if names is None:
        return None
    return any(runtime_model_names_match(model, name) for name in names)


def lane_requirement_bytes(lane: ModelRunLane) -> int | None:
    """Return the memory an on-host lane's model needs, or ``None`` when its catalogue entry states none.

    The catalogue states ``0`` for an unknown size; neither it nor an absent
    size is a requirement, and inventing one would admit or refuse on
    evidence nobody has.
    """
    return lane.size_bytes or None


def _refusal_judgement(role: ModelRole, refusal: ModelRunRefusal) -> _Judgement:
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "model_run_refusal": refusal.code.value,
        "role_selection_required": refusal.code is ModelRunRefusalCode.NO_SELECTION,
    }
    return _Judgement(
        ready=False,
        verdict=provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE, facts=facts
        ),
    )


def _on_host_judgement(role: ModelRole, lane: ModelRunLane, measured: _Measured) -> _Judgement:
    """Judge an on-host lane in the fixed order: capacity, program, then the model itself."""
    model = lane.model
    requirement = lane_requirement_bytes(lane)
    if requirement is not None and below_capacity_floor(measured.hardware, requirement):
        floor_facts: dict[str, ProvisioningFactValue] = {
            "role": role.value,
            "model": model,
            "required_bytes": requirement,
        }
        if measured.hardware.memory.total_bytes is not None:
            floor_facts["total_memory_bytes"] = measured.hardware.memory.total_bytes
        return _Judgement(
            ready=False,
            verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET, facts=floor_facts
            ),
        )
    located = measured.located
    if located is not None and not located.located:
        return _Judgement(
            ready=False,
            verdict=_setup_verdict(
                ProvisioningPreconditionCondition.RUNTIME_INSTALLED,
                {"role": role.value, "local_ai_located": False, "record": located.component.outcome.value},
            ),
        )
    if measured.inventory is None:
        return _Judgement(
            ready=False,
            verdict=_setup_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                {"role": role.value, "runtime_reachable": False, "operator_endpoint": located is None},
            ),
        )
    if _present(model, _names(measured.inventory)) is not True:
        return _Judgement(
            ready=False,
            verdict=_setup_verdict(
                ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
                {"role": role.value, "runtime_reachable": True, "model": model, "role_model_installed": False},
            ),
        )
    return _Judgement(ready=True)


def _load_admission(
    lane: ModelRunLane,
    installed: bool | None,
    resident: bool | None,
    measured: _Measured,
) -> tuple[bool | None, tuple[ContentionCause, ...]]:
    requirement = lane_requirement_bytes(lane)
    if requirement is None or installed is not True or resident is True:
        return None, ()
    snapshot = assess_model_load_contention(
        lane.model,
        requirement,
        profile=measured.hardware,
        residents=measured.residents,
        residents_measured=measured.residents is not None,
        settings=measured.settings,
    )
    return snapshot.admitted, snapshot.causes


def _role_status(role: ModelRole, answer: RoleLane, measured: _Measured, *, assess_load: bool) -> LocalReaderRoleStatus:
    if isinstance(answer, ModelRunRefusal):
        judgement = _refusal_judgement(role, answer)
        return _status_row(role, judgement)
    if answer.reads_off_host:
        return LocalReaderRoleStatus(role=role, ready=True)
    judgement = _on_host_judgement(role, answer, measured)
    installed = _present(answer.model, _names(measured.inventory))
    resident = _present(answer.model, _names(measured.residents))
    admitted, causes = _load_admission(answer, installed, resident, measured) if assess_load else (None, ())
    return _status_row(
        role,
        judgement,
        model=answer.model,
        installed=installed,
        resident=resident,
        load_admitted=admitted,
        contention_causes=causes,
    )


def _status_row(
    role: ModelRole,
    judgement: _Judgement,
    *,
    model: str | None = None,
    installed: bool | None = None,
    resident: bool | None = None,
    load_admitted: bool | None = None,
    contention_causes: tuple[ContentionCause, ...] = (),
) -> LocalReaderRoleStatus:
    verdict = judgement.verdict
    return LocalReaderRoleStatus(
        role=role,
        model=model,
        installed=installed,
        resident=resident,
        load_admitted=load_admitted,
        contention_causes=contention_causes,
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
    settings: Settings | None = None,
    *,
    roles: Iterable[ModelRole] | None = None,
    assess_load: bool = True,
    which: ExecutableLookup | None = None,
    hardware: HardwareProfile | None = None,
) -> LocalReaderStatus:
    """Measure the program and judge every role's selected lane into one projection.

    ``lanes`` is what :func:`read_role_lanes` resolved for each role. Reads
    only: nothing is started, pulled or loaded. ``assess_load`` adds the
    admission check for installed on-host models that are not yet resident,
    which reads hardware counters and can be skipped by a surface that
    refreshes often. ``hardware`` is this computer's measured hardware,
    measured here when omitted. Every reading is aimed at the server the local
    AI record names.
    """
    resolved = settings if settings is not None else load_settings()
    host = probe_runtime_host(resolved) if which is None else probe_runtime_host(resolved, which=which)
    aimed, located = local_ai_settings(resolved)
    reachable = host.reachable and _locates(located)
    measured = _Measured(
        settings=aimed,
        located=located,
        inventory=read_installed_models(aimed) if reachable else None,
        residents=read_runtime_residents(aimed) if reachable else None,
        hardware=hardware if hardware is not None else probe_hardware_profile(),
    )
    role_rows = tuple(
        _role_status(role, _answer(lanes, role), measured, assess_load=assess_load) for role in _selected_roles(roles)
    )
    by_role = {row.role: row for row in role_rows}
    for role in EXTRACTION_READER_ROLES:
        if role not in by_role:
            by_role[role] = _role_status(role, _answer(lanes, role), measured, assess_load=False)
    extraction_ready = all(by_role[role].ready for role in EXTRACTION_READER_ROLES)
    return LocalReaderStatus(
        host=host,
        roles=role_rows,
        extraction_ready=extraction_ready,
        document_readiness=(
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        ),
        text_layer_model_fill_available=by_role[ModelRole.TEXT_EXTRACTION].ready,
    )

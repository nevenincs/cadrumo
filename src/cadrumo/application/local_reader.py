"""The local document reader as one provisioned unit: runtime, role models, readiness.

Invoice extraction reads a text-layer document with the TEXT_EXTRACTION model
and a scanned one with the VISION_TRANSCRIPTION model; column mapping and the
supply-nature proposal use their own roles. Each reader loads one model for
its role, so provisioning, status and the reader itself must resolve the same
identifier -- :func:`select_role_model` is that single resolution.

The native component engine installs the local AI and the runtime manager runs
its one server; the engine's local AI record says where the program and the
models are and which fixed address the server answers on. This module locates
the local AI from that record alone, aims every reading at the recorded
address, and turns what the server answers into the projections a status
surface renders and the per-role probe a status surface consults. An operator who configured an
endpoint of their own runs that server themselves, and it is used as written.

The per-role probe judges in a fixed order: a role the catalogue cannot serve,
or whose model this computer's installed memory cannot hold, refuses first and
offers nothing, because setup cannot change either; then a local AI the record
does not locate, or a server that does not answer at its address, refuses with
the local AI setup; then a missing model does too. The probe never judges free
memory: a model already resident, or another program's load, lowers it for a
while, and whether a load fits at that moment is decided at the load by
:func:`.provisioning_runtime.assess_model_load_contention`, whose refusal says
memory is busy and is retried rather than read as this computer's limit.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ..core.component_records import (
    LocatedLocalAi,
    component_records_root,
    locate_local_ai,
    uses_managed_local_ai,
)
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hardware import ContentionCause
from ..core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ..core.models import STRICT_FROZEN_CONFIG
from .operator_actions.models import PreconditionVerdict
from .provisioning import (
    DependencyStatus,
    HardwareProfile,
    ModelSelection,
    below_capacity_floor,
    probe_hardware_profile,
    select_model_for_role,
)
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
    ReadinessOutcome,
    RuntimeResident,
    assess_model_load_contention,
    load_and_verify_model,
    read_installed_models,
    read_runtime_residents,
    runtime_model_names_match,
)

__all__ = [
    "EXTRACTION_READER_ROLES",
    "LocalReaderDocumentReadiness",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "RoleModelTarget",
    "local_ai_settings",
    "local_reader_service",
    "probe_local_reader",
    "read_local_reader_status",
    "role_model_targets",
    "select_role_model",
    "verify_role_target",
]

#: The roles invoice evidence extraction reads with, text layer first.
EXTRACTION_READER_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION)


class LocalReaderDocumentReadiness(StrEnum):
    """Which invoice documents this machine can turn into drafts.

    Text-layer documents are read by label rules that need no runtime and no
    model, so they are always readable; the model only fills fields the labels
    do not print. Every document is readable only when :attr:`LocalReaderStatus.extraction_ready`.
    """

    ALL_DOCUMENTS = "all_documents"
    TEXT_LAYER_ONLY = "text_layer_only"


def verify_role_target(target: RoleModelTarget, *, settings: Settings | None = None) -> ReadinessOutcome:
    """Verify a provisioning target is loaded and answering, through :func:`load_and_verify_model`.

    Raises:
        ValueError: When ``target`` carries no model (a refused selection).
    """
    if target.model is None:
        raise ValueError("a refused selection has no model to verify")
    resolved, _ = local_ai_settings(settings if settings is not None else load_settings())
    return load_and_verify_model(target.model, settings=resolved)


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


def local_reader_service(role: ModelRole) -> str:
    """Return the stable diagnostic row id for one role's local reader."""
    return f"local-reader:{role.value}"


def _role_setting(role: ModelRole, settings: Settings) -> str:
    """Return the model setting an operator can set for ``role``; every role has one."""
    if role is ModelRole.VISION_TRANSCRIPTION:
        return settings.cadrumo_llm_ollama_vision_model
    if role is ModelRole.TEXT_EXTRACTION:
        return settings.cadrumo_llm_ollama_text_model
    if role is ModelRole.COLUMN_ROLE_MAPPING:
        return settings.cadrumo_llm_ollama_mapping_model
    return settings.cadrumo_llm_ollama_supply_nature_model


def _role_model(role: ModelRole, settings: Settings, selection: ModelSelection) -> str | None:
    """Return the model ``role``'s reader sends, which momentary headroom never changes."""
    if role in EXTRACTION_READER_ROLES:
        return _role_setting(role, settings)
    return selection.capacity_runtime_id


class RoleModelTarget(BaseModel):
    """One distinct model to provision with every role it serves, or one role's refusal.

    ``model`` is ``None`` exactly when catalogue selection refused the role;
    the selection's facts and verdict are then carried so the caller reports
    why nothing will be fetched for it.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = None
    roles: tuple[ModelRole, ...] = Field(min_length=1)
    requirement_bytes: int | None = Field(default=None, ge=0)
    selection_facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    selection_verdict: PreconditionVerdict | None = None
    licence_advisories: tuple[str, ...] = ()


def _requirement_for(role: ModelRole, model: str, settings: Settings) -> int | None:
    candidate = model_candidate(model)
    if candidate is not None:
        return candidate.memory_requirement_bytes
    # An uncatalogued override declares no requirement; the role's selected
    # candidate is the closest measured claim, and the admission check runs
    # against it rather than against an invented figure.
    assessable = select_model_for_role(role, settings=settings).assessable_load
    return None if assessable is None else assessable[1]


def select_role_model(
    role: ModelRole,
    settings: Settings,
    *,
    explicit: str | None = None,
    profile: HardwareProfile | None = None,
) -> ModelSelection:
    """Resolve ``role`` through catalogue selection, honouring an operator-set model.

    The configured setting is passed as an override only when it differs from
    the catalogue default, so a default configuration keeps every selection
    bar -- context window, licence, headroom -- and an operator's choice is
    honoured with its advisories. ``explicit`` outranks both. ``profile`` is
    this computer's measured hardware, measured here when omitted.
    """
    configured = explicit
    if configured is None:
        setting = _role_setting(role, settings)
        configured = setting if setting != default_model_runtime_id(role) else None
    return select_model_for_role(role, profile=profile, settings=settings, override=configured)


def _role_selection_target(
    role: ModelRole,
    selection: ModelSelection,
    settings: Settings,
    served: dict[str, list[ModelRole]],
    requirements: dict[str, int | None],
    refusals: list[RoleModelTarget],
    advisories: dict[str, list[str]],
) -> None:
    model = selection.runtime_id
    if not selection.selected or model is None:
        refusals.append(
            RoleModelTarget(
                roles=(role,),
                selection_facts=selection.facts,
                selection_verdict=selection.precondition_verdict,
            )
        )
        return
    key = next((known for known in served if runtime_model_names_match(known, model)), model)
    served.setdefault(key, []).append(role)
    advisory = selection.licence_advisory
    if advisory and advisory not in advisories.setdefault(key, []):
        advisories[key].append(advisory)
    if requirements.get(key) is None:
        assessable = selection.assessable_load
        requirements[key] = assessable[1] if assessable is not None else _requirement_for(role, model, settings)


def _selected_roles(roles: Iterable[ModelRole] | None) -> tuple[ModelRole, ...]:
    return tuple(ModelRole) if roles is None else tuple(roles)


def role_model_targets(
    roles: Iterable[ModelRole] | None = None,
    settings: Settings | None = None,
    *,
    explicit_model: str | None = None,
) -> tuple[RoleModelTarget, ...]:
    """Return the distinct models to provision for ``roles`` (every role by default).

    Roles sharing one model yield one target, so provisioning every role pulls
    each model once. A role whose selection refuses yields its own target with
    no model and the refusal attached.
    """
    resolved = settings if settings is not None else load_settings()
    served: dict[str, list[ModelRole]] = {}
    requirements: dict[str, int | None] = {}
    refusals: list[RoleModelTarget] = []
    advisories: dict[str, list[str]] = {}
    for role in _selected_roles(roles):
        selection = select_role_model(role, resolved, explicit=explicit_model)
        _role_selection_target(role, selection, resolved, served, requirements, refusals, advisories)
    targets = tuple(
        RoleModelTarget(
            model=model,
            roles=tuple(roles_served),
            requirement_bytes=requirements.get(model),
            licence_advisories=tuple(advisories.get(model, ())),
        )
        for model, roles_served in served.items()
    )
    return (*refusals, *targets)


def _names(entries: Iterable[InstalledModel | RuntimeResident]) -> tuple[str, ...]:
    return tuple(entry.name for entry in entries)


def _present(model: str, names: tuple[str, ...] | None) -> bool | None:
    if names is None:
        return None
    return any(runtime_model_names_match(model, name) for name in names)


def probe_local_reader(
    role: ModelRole,
    settings: Settings | None = None,
    *,
    installed: tuple[InstalledModel, ...] | None = None,
    model: str | None = None,
    hardware: HardwareProfile | None = None,
) -> DependencyStatus:
    """Report whether the on-host reader for ``role`` can run right now.

    A consumer consults this per role before its first request, so a missing
    vision model never stops text-layer reads and a missing text model is not
    hidden behind an installed vision model. The judgement runs in a fixed
    order, each step only when the one before passed:

    * A role the catalogue cannot serve, or whose model needs more memory than
      this computer has installed, refuses and names no action, because setup
      cannot change either.
    * A local AI its record does not locate, a server that does not answer at
      the recorded address, or a model it does not hold refuses with the local
      AI setup.

    Free memory decides nothing here. It changes with every resident model and
    every other program, so whether a load fits now is judged at the load by
    :func:`.provisioning_runtime.assess_model_load_contention`, as busy memory
    to retry rather than as this computer's limit.

    Args:
        role: The reader role a document needs.
        settings: Settings carrying the endpoint and role models.
        installed: An inventory already read; read from the runtime when omitted.
        model: The role model a reader already resolved and will send; resolved
            through :func:`select_role_model` when omitted. A reader that
            passes the id it sends cannot be checked against another model.
        hardware: This computer's measured hardware; measured when omitted.

    Returns:
        A :class:`DependencyStatus` on the ``local-reader:<role>`` row. Never raises.
    """
    resolved, located = local_ai_settings(settings if settings is not None else load_settings())
    measured = hardware if hardware is not None else probe_hardware_profile()
    selection = select_role_model(role, resolved, profile=measured)
    if model is None:
        model = _role_model(role, resolved, selection)
    inventory = installed
    floor = _floor_refusal(role, selection, model=model, hardware=measured)
    if inventory is None and floor is None and _locates(located):
        inventory = read_installed_models(resolved)
    return _reader_status_from_inventory(
        role, resolved, model=model, inventory=inventory, selection=selection, hardware=measured, located=located
    )


def _locates(located: LocatedLocalAi | None) -> bool:
    """Whether the readers have a server to ask: an operator's own endpoint, or a located local AI."""
    return located is None or located.located


def _floor_refusal(
    role: ModelRole,
    selection: ModelSelection,
    *,
    model: str | None,
    hardware: HardwareProfile,
) -> DependencyStatus | None:
    """Return the refusal for a role this computer cannot serve at all, which no setup changes.

    Either the catalogue has no model the role may use, or the role's model
    needs more memory than this computer has installed. A selection refused only
    because free memory is short this moment is neither: its model still reads
    here once memory frees up.
    """
    if selection.capacity_runtime_id is None:
        failed = selection.precondition_verdict
        facts: dict[str, ProvisioningFactValue] = {"role": role.value, "role_model_selected": False}
        if failed is not None:
            facts["selection_condition"] = failed.failed_condition_id
        return DependencyStatus(
            service=local_reader_service(role),
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE, facts=facts
            ),
        )
    candidate = None if model is None else model_candidate(model)
    requirement = None if candidate is None else candidate.memory_requirement_bytes
    if model is None or requirement is None or not below_capacity_floor(hardware, requirement):
        return None
    floor_facts: dict[str, ProvisioningFactValue] = {"role": role.value, "model": model, "required_bytes": requirement}
    if hardware.memory.total_bytes is not None:
        floor_facts["total_memory_bytes"] = hardware.memory.total_bytes
    return DependencyStatus(
        service=local_reader_service(role),
        available=False,
        facts=floor_facts,
        precondition_verdict=provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET, facts=floor_facts
        ),
    )


def _setup_refusal(
    role: ModelRole,
    condition: ProvisioningPreconditionCondition,
    facts: dict[str, ProvisioningFactValue],
) -> DependencyStatus:
    return DependencyStatus(
        service=local_reader_service(role),
        available=False,
        facts=facts,
        precondition_verdict=provisioning_setup_verdict(condition, facts=facts, action_id=LOCAL_AI_PROVISION_ACTION_ID),
    )


def _reader_status_from_inventory(
    role: ModelRole,
    resolved: Settings,
    *,
    model: str | None,
    inventory: tuple[InstalledModel, ...] | None,
    selection: ModelSelection,
    hardware: HardwareProfile,
    located: LocatedLocalAi | None,
) -> DependencyStatus:
    """Judge ``role``'s reader in the probe's order; ``inventory`` ``None`` means the server did not answer."""
    refused = _floor_refusal(role, selection, model=model, hardware=hardware)
    if refused is not None:
        return refused
    if located is not None and not located.located:
        return _setup_refusal(
            role,
            ProvisioningPreconditionCondition.RUNTIME_INSTALLED,
            {"role": role.value, "local_ai_located": False, "record": located.component.outcome.value},
        )
    if inventory is None:
        return _setup_refusal(
            role,
            ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
            # Whether the server is the managed one, never its address: an
            # operator's own endpoint can name a host or carry credentials.
            {"role": role.value, "runtime_reachable": False, "operator_endpoint": located is None},
        )
    if model is None:
        facts: dict[str, ProvisioningFactValue] = {"role": role.value, "runtime_reachable": True}
        facts["role_model_selected"] = False
        return DependencyStatus(
            service=local_reader_service(role),
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE, facts=facts
            ),
        )
    if not bool(_present(model, _names(inventory))):
        return _setup_refusal(
            role,
            ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
            {"role": role.value, "runtime_reachable": True, "model": model, "role_model_installed": False},
        )
    return DependencyStatus(
        service=local_reader_service(role),
        available=True,
        facts={"role": role.value, "runtime_reachable": True, "model": model, "role_model_installed": True},
    )


class LocalReaderRoleStatus(BaseModel):
    """One role's reader: which model it loads, and what the runtime says about it.

    ``installed``, ``resident`` and ``load_admitted`` are ``None`` when the
    answer could not be measured -- an unreachable runtime has no inventory,
    and ``None`` must not render as "not installed".
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
    #: The operator action the reader probe named for the failed condition, or
    #: ``None`` when it named none -- a role this computer cannot run, or a
    #: ready role.
    recovery_action_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area or doctor row.

    ``extraction_ready`` is true only when the runtime answers and both
    invoice-extraction roles have their models installed; it is the single
    claim a surface may use to say every document can be read on this machine.
    ``document_readiness`` says which documents can be read either way, and
    ``text_layer_model_fill_available`` whether text-layer fields the labels do
    not print can be filled by the text model.
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
class _RoleRuntimeStatus:
    model: str | None
    installed: bool | None
    resident: bool | None
    load_admitted: bool | None
    contention_causes: tuple[ContentionCause, ...]
    failed_condition_id: str | None
    recovery_action_id: str | None
    ready: bool


def _role_load_admission(
    role: ModelRole,
    model: str | None,
    installed: bool | None,
    resident: bool | None,
    *,
    settings: Settings,
    residents: tuple[RuntimeResident, ...] | None,
    assess_load: bool,
) -> tuple[bool | None, tuple[ContentionCause, ...]]:
    if (
        not assess_load
        or model is None
        or not (installed is not None and installed)
        or (resident is not None and resident)
    ):
        return None, ()
    requirement = _requirement_for(role, model, settings)
    if requirement is None:
        return None, ()
    snapshot = assess_model_load_contention(
        model,
        requirement,
        residents=residents,
        residents_measured=residents is not None,
        settings=settings,
    )
    return snapshot.admitted, snapshot.causes


@dataclass(frozen=True, slots=True)
class _Measured:
    """What one status read measured once and every role row is judged against."""

    settings: Settings
    located: LocatedLocalAi | None
    inventory: tuple[InstalledModel, ...] | None
    residents: tuple[RuntimeResident, ...] | None
    hardware: HardwareProfile


def _role_runtime_status(role: ModelRole, measured: _Measured, *, assess_load: bool) -> _RoleRuntimeStatus:
    settings, inventory, residents = measured.settings, measured.inventory, measured.residents
    selection = select_role_model(role, settings, profile=measured.hardware)
    model = _role_model(role, settings, selection)
    # Judged by the probe's own verdicts even when the runtime did not answer,
    # so the row names the same setup action a refused read would.
    probe = _reader_status_from_inventory(
        role,
        settings,
        model=model,
        inventory=inventory,
        selection=selection,
        hardware=measured.hardware,
        located=measured.located,
    )
    verdict = probe.precondition_verdict
    installed = None if model is None else _present(model, None if inventory is None else _names(inventory))
    resident = None if model is None else _present(model, None if residents is None else _names(residents))
    admitted, causes = _role_load_admission(
        role,
        model,
        installed,
        resident,
        settings=settings,
        residents=residents,
        assess_load=assess_load,
    )
    return _RoleRuntimeStatus(
        model=model,
        installed=installed,
        resident=resident,
        load_admitted=admitted,
        contention_causes=causes,
        failed_condition_id=None if verdict is None else verdict.failed_condition_id,
        recovery_action_id=None if verdict is None or verdict.action is None else verdict.action.action_id,
        ready=probe.available,
    )


def _role_status(role: ModelRole, measured: _Measured, *, assess_load: bool) -> LocalReaderRoleStatus:
    runtime = _role_runtime_status(role, measured, assess_load=assess_load)
    return LocalReaderRoleStatus(
        role=role,
        model=runtime.model,
        installed=runtime.installed,
        resident=runtime.resident,
        load_admitted=runtime.load_admitted,
        contention_causes=runtime.contention_causes,
        ready=runtime.ready,
        failed_condition_id=runtime.failed_condition_id,
        recovery_action_id=runtime.recovery_action_id,
    )


def _runtime_models(
    settings: Settings,
    *,
    reachable: bool,
) -> tuple[tuple[InstalledModel, ...] | None, tuple[RuntimeResident, ...] | None]:
    if not reachable:
        return None, None
    return read_installed_models(settings), read_runtime_residents(settings)


def _include_extraction_roles(by_role: dict[ModelRole, LocalReaderRoleStatus], measured: _Measured) -> None:
    for role in EXTRACTION_READER_ROLES:
        if role in by_role:
            continue
        by_role[role] = _role_status(role, measured, assess_load=False)


def read_local_reader_status(
    settings: Settings | None = None,
    *,
    roles: Iterable[ModelRole] | None = None,
    assess_load: bool = True,
    which: ExecutableLookup | None = None,
) -> LocalReaderStatus:
    """Measure the runtime host and every role's model into one projection.

    Reads only: nothing is started, pulled or loaded. ``assess_load`` adds the
    admission check for installed models that are not yet resident, which
    reads hardware counters and can be skipped by a surface that refreshes
    often. Every reading is aimed at the server the local AI record names.
    """
    resolved = settings if settings is not None else load_settings()
    host = probe_runtime_host(resolved) if which is None else probe_runtime_host(resolved, which=which)
    aimed, located = local_ai_settings(resolved)
    inventory, residents = _runtime_models(aimed, reachable=host.reachable)
    measured = _Measured(
        settings=aimed,
        located=located,
        inventory=inventory,
        residents=residents,
        hardware=probe_hardware_profile(),
    )
    role_rows = tuple(_role_status(role, measured, assess_load=assess_load) for role in _selected_roles(roles))
    by_role = {row.role: row for row in role_rows}
    _include_extraction_roles(by_role, measured)
    extraction_ready = host.reachable and all(by_role[role].ready for role in EXTRACTION_READER_ROLES)
    text_row = by_role[ModelRole.TEXT_EXTRACTION]
    return LocalReaderStatus(
        host=host,
        roles=role_rows,
        extraction_ready=extraction_ready,
        document_readiness=(
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        ),
        text_layer_model_fill_available=host.reachable and text_row.ready,
    )

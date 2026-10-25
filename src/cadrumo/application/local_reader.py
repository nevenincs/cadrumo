"""The local document reader as one provisioned unit: runtime, role models, readiness.

Invoice extraction reads a text-layer document with the TEXT_EXTRACTION model
and a scanned one with the VISION_TRANSCRIPTION model; column mapping and the
supply-nature proposal use their own roles. Each reader loads one model for
its role, so provisioning, status and the reader itself must resolve the same
identifier -- :func:`configured_role_model` is that single resolution.

The native component engine installs the local AI and the runtime manager runs
its one server; the engine's local AI record says where the program and the
models are and which fixed address the server answers on. This module locates
the local AI from that record alone, aims every reading at the recorded
address, and turns what the server answers into the projections a status
surface renders and the per-role probe a consumer consults before spending a
document. An operator who configured an endpoint of their own runs that server
themselves, and it is used as written.

The per-role probe judges in a fixed order: a role the catalogue cannot serve,
or whose model this computer's installed memory cannot hold, refuses first and
offers nothing, because setup cannot change either; then a local AI the record
does not locate, or a server that does not answer at its address, refuses with
the local AI setup; then a missing model does too. The probe never judges free
memory: a model already resident, or another program's load, lowers it for a
while, and whether a load fits at that moment is decided at the load by
:func:`.provisioning_runtime.assess_model_load_contention`, whose refusal says
memory is busy and is retried rather than read as this computer's limit. Role
fitness, the answer quality of the text model, is
the consumer's admission and not part of the component's state. A consumer
admits its read through :func:`admit_local_reader`, which measures the model's
fitness at the first use of its current weights and records the verdict in
:mod:`.provisioning_fitness`; a verdict that found the weights unfit or too
slow refuses its consumer and offers nothing. Status, and the plain
:func:`probe_local_reader`, read that record and never probe unless asked, so a
model nobody has read with yet is not verified there rather than unfit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

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
from ..core.locks_errors import LockAcquisitionError
from ..core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.clock import now
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
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    provisioning_setup_verdict,
    require_provisioning_verdict,
)
from .provisioning_fitness import (
    RecordedFitnessVerdict,
    RoleFitnessVerdict,
    fitness_measurement_lock,
    read_fitness_verdict,
    record_fitness_verdict,
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
    "FITNESS_PROBED_ROLES",
    "LocalReaderDocumentReadiness",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "RoleFitnessOutcome",
    "RoleFitnessState",
    "RoleModelTarget",
    "TextExtractionFitnessProbe",
    "admit_local_reader",
    "configured_role_model",
    "local_ai_settings",
    "local_reader_service",
    "probe_local_reader",
    "probe_role_fitness",
    "read_local_reader_status",
    "recorded_role_fitness",
    "role_model_targets",
    "select_role_model",
    "verify_role_target",
]

#: The roles invoice evidence extraction reads with, text layer first.
EXTRACTION_READER_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION)


#: Roles whose readiness includes a fitness probe. Presence answers "is the
#: model there"; only the text reader has shown that a model can be present,
#: loaded and answering, and still never produce a parseable extraction -- a
#: vision model configured in the text role spends its whole answer budget and
#: returns nothing the parser can read.
FITNESS_PROBED_ROLES: tuple[ModelRole, ...] = (ModelRole.TEXT_EXTRACTION,)

#: How many reader timeouts a consumer waits while another one measures the
#: same record: the holder's probe bounds its connect, send and answer phases
#: by the reader's own timeout each, and one more covers rendering the probe
#: document and writing the verdict.
_MEASUREMENT_WAIT_BOUNDS: Final[int] = 4


def _measurement_wait_s(settings: Settings) -> float:
    return float(_MEASUREMENT_WAIT_BOUNDS * settings.cadrumo_llm_default_timeout_s)


class RoleFitnessOutcome(ProvisioningOutcome):
    """Whether a model produced a usable answer to its role's real request shape.

    ``fit`` is the decision. ``answer_parseable`` and ``grounded`` say which
    half failed: a reply the parser could not read at all, or a readable reply
    whose values did not match the probe document. ``timed_out`` marks a model
    that did not finish its answer within the probe's bound -- a verdict about
    the model on this host, recorded like any other. ``transport_failed`` marks
    a probe that never got an answer for any other reason, which says nothing
    about the model and is therefore never recorded.
    """

    role: ModelRole
    model: str = Field(min_length=1)
    fit: bool
    answer_parseable: bool = False
    grounded: bool = False
    timed_out: bool = False
    transport_failed: bool = False
    output_tokens: int | None = Field(default=None, ge=0)
    answer_budget_tokens: int = Field(gt=0)
    elapsed_ms: int = Field(ge=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_fitness_outcome(self) -> RoleFitnessOutcome:
        require_provisioning_verdict(failed=not self.fit, verdict=self.precondition_verdict)
        if self.fit and (self.timed_out or self.transport_failed):
            raise ValueError("a fit outcome cannot have timed out or lost its transport")
        if self.timed_out and self.transport_failed:
            raise ValueError("a timed-out probe got a transport answer; it is not a transport failure")
        return self

    @property
    def settled(self) -> bool:
        """Return whether this outcome is a verdict about the model rather than about the transport."""
        return not self.transport_failed

    @property
    def verdict(self) -> RoleFitnessVerdict:
        """Return the recorded verdict kind for a settled outcome."""
        if self.fit:
            return RoleFitnessVerdict.FIT
        return RoleFitnessVerdict.TIMED_OUT if self.timed_out else RoleFitnessVerdict.UNFIT


type TextExtractionFitnessProbe = Callable[[str, Settings], RoleFitnessOutcome]
"""Runs the text reader's real request shape and budget against a model; supplied by composition."""


class RoleFitnessState(StrEnum):
    """What a status surface knows about a probed role's fitness.

    ``NOT_VERIFIED`` is its own state: no verdict is recorded for the model's
    current weights, which is not evidence that the model is unfit.
    """

    FIT = "fit"
    UNFIT = "unfit"
    TIMED_OUT = "timed_out"
    NOT_VERIFIED = "not_verified"


class LocalReaderDocumentReadiness(StrEnum):
    """Which invoice documents this machine can turn into drafts.

    Text-layer documents are read by label rules that need no runtime and no
    model, so they are always readable; the model only fills fields the labels
    do not print. Every document is readable only when :attr:`LocalReaderStatus.extraction_ready`.
    """

    ALL_DOCUMENTS = "all_documents"
    TEXT_LAYER_ONLY = "text_layer_only"


def _installed_digest(model: str, settings: Settings) -> str | None:
    return _inventory_digest(model, read_installed_models(settings))


def _record(outcome: RoleFitnessOutcome, *, digest: str, settings: Settings) -> None:
    verdict = outcome.precondition_verdict
    record_fitness_verdict(
        RecordedFitnessVerdict(
            endpoint=settings.cadrumo_llm_ollama_chat_url,
            model=outcome.model,
            digest=digest,
            role=outcome.role,
            verdict=outcome.verdict,
            failed_condition_id=verdict.failed_condition_id if verdict is not None else None,
            elapsed_ms=outcome.elapsed_ms,
            recorded_at=now(),
        ),
        settings,
    )


def probe_role_fitness(
    role: ModelRole,
    model: str,
    settings: Settings,
    *,
    text_probe: TextExtractionFitnessProbe,
) -> RoleFitnessOutcome | None:
    """Run ``role``'s fitness probe against ``model`` now, or return ``None`` when the role is not probed.

    Records nothing; the callers that record a verdict hold
    :func:`.provisioning_fitness.fitness_measurement_lock` while they do.
    """
    if role not in FITNESS_PROBED_ROLES:
        return None
    return text_probe(model, settings)


def recorded_role_fitness(
    role: ModelRole,
    model: str,
    digest: str | None,
    settings: Settings,
) -> RoleFitnessState | None:
    """Return the recorded fitness of ``model``'s current weights, or ``None`` when the role is not probed."""
    if role not in FITNESS_PROBED_ROLES:
        return None
    if digest is None:
        return RoleFitnessState.NOT_VERIFIED
    recorded = read_fitness_verdict(
        endpoint=settings.cadrumo_llm_ollama_chat_url,
        model=model,
        digest=digest,
        role=role,
        settings=settings,
    )
    if recorded is None:
        return RoleFitnessState.NOT_VERIFIED
    return RoleFitnessState(recorded.verdict.value)


def verify_role_target(
    target: RoleModelTarget,
    *,
    settings: Settings | None = None,
    text_probe: TextExtractionFitnessProbe | None = None,
) -> ReadinessOutcome:
    """Verify a provisioning target is loaded, answering and fit for every role it serves.

    Readiness first, through :func:`load_and_verify_model`, then -- for a role in
    :data:`FITNESS_PROBED_ROLES` and when a probe is supplied -- the role's
    real request shape. An unfit or too-slow model is reported not ready with
    its own condition, so ``verify`` cannot pass a model the reader will never
    get an answer from. Every settled probe is recorded against the model's
    current digest; status reads that record instead of probing.

    Raises:
        ValueError: When ``target`` carries no model (a refused selection).
    """
    if target.model is None:
        raise ValueError("a refused selection has no model to verify")
    resolved, _ = local_ai_settings(settings if settings is not None else load_settings())
    ready = load_and_verify_model(target.model, settings=resolved)
    if not ready.ready or text_probe is None:
        return ready
    digest = _installed_digest(target.model, resolved)
    for role in target.roles:
        fitness = probe_role_fitness(role, target.model, resolved, text_probe=text_probe)
        if fitness is None:
            continue
        if fitness.settled and digest is not None:
            with fitness_measurement_lock(resolved, timeout=_measurement_wait_s(resolved)):
                _record(fitness, digest=digest, settings=resolved)
        if fitness.fit:
            continue
        facts = dict(fitness.facts)
        return ReadinessOutcome(
            model=target.model,
            ready=False,
            resident=ready.resident,
            answered=ready.answered,
            elapsed_ms=fitness.elapsed_ms,
            facts=facts,
            precondition_verdict=fitness.precondition_verdict,
        )
    return ready


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


def configured_role_model(role: ModelRole, settings: Settings | None = None) -> str | None:
    """Return the runtime model id the on-host reader for ``role`` actually loads.

    The two document readers load their settings as written. The column mapper
    and the supply-nature proposer resolve through :func:`select_role_model`,
    so this returns whatever that selection names -- the operator's setting
    when it differs from the shipped default, otherwise the catalogue's pick
    for this machine, whatever its free memory says this moment -- or ``None``
    when no catalogued model can serve the role.
    """
    resolved = settings if settings is not None else load_settings()
    return _role_model(role, resolved, select_role_model(role, resolved))


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
    * A fitness verdict recorded against the text model's current weights that
      found it unfit or too slow refuses and names no action.

    Free memory decides nothing here. It changes with every resident model and
    every other program, so whether a load fits now is judged at the load by
    :func:`.provisioning_runtime.assess_model_load_contention`, as busy memory
    to retry rather than as this computer's limit.

    It never measures fitness, so a model with no verdict is admitted here; a
    consumer about to read admits through :func:`admit_local_reader`, which
    measures it first.

    Args:
        role: The reader role a document needs.
        settings: Settings carrying the endpoint and role models.
        installed: An inventory already read; read from the runtime when omitted.
        model: The role model a reader already resolved and will send; resolved
            through :func:`configured_role_model` when omitted. A reader that
            passes the id it sends cannot be checked against another model.
        hardware: This computer's measured hardware; measured when omitted.

    Returns:
        A :class:`DependencyStatus` on the ``local-reader:<role>`` row. Never raises.
    """
    return _judge_reader(role, settings, installed=installed, model=model, hardware=hardware).status


@dataclass(frozen=True, slots=True)
class _ReaderJudgement:
    """One reader probe's verdict with what it was judged on, so admission can continue from it."""

    settings: Settings
    located: LocatedLocalAi | None
    selection: ModelSelection
    hardware: HardwareProfile
    model: str | None
    inventory: tuple[InstalledModel, ...] | None
    status: DependencyStatus


def _judge_reader(
    role: ModelRole,
    settings: Settings | None,
    *,
    installed: tuple[InstalledModel, ...] | None,
    model: str | None,
    hardware: HardwareProfile | None,
) -> _ReaderJudgement:
    resolved, located = local_ai_settings(settings if settings is not None else load_settings())
    measured = hardware if hardware is not None else probe_hardware_profile()
    selection = select_role_model(role, resolved, profile=measured)
    if model is None:
        model = _role_model(role, resolved, selection)
    inventory = installed
    floor = _floor_refusal(role, selection, model=model, hardware=measured)
    if inventory is None and floor is None and _locates(located):
        inventory = read_installed_models(resolved)
    status = _reader_status_from_inventory(
        role, resolved, model=model, inventory=inventory, selection=selection, hardware=measured, located=located
    )
    return _ReaderJudgement(
        settings=resolved,
        located=located,
        selection=selection,
        hardware=measured,
        model=model,
        inventory=inventory,
        status=status,
    )


def admit_local_reader(
    role: ModelRole,
    settings: Settings | None = None,
    *,
    text_probe: TextExtractionFitnessProbe,
    model: str | None = None,
) -> DependencyStatus:
    """Admit a consumer's read with ``role``'s reader, measuring its fitness at first use.

    The reader probe judges first, in :func:`probe_local_reader`'s order. A
    role in :data:`FITNESS_PROBED_ROLES` whose installed model carries no
    verdict for its current digest is then measured with ``text_probe`` before
    the read, and the verdict is recorded against that digest and the endpoint
    the reading is aimed at. The measurement runs under
    :func:`.provisioning_fitness.fitness_measurement_lock`, which re-reads the
    record once held, so concurrent first uses of the same weights measure
    once; every later admission reads the record. A model the runtime lists
    without a digest cannot be keyed to its weights and is admitted unmeasured.

    Refusals stay typed:

    * A recorded or freshly measured unfit or too-slow verdict refuses and names
      no action, because setup cannot change a model's answers.
    * A probe that got no answer is judged again from a fresh inventory, so a
      server that stopped reads as the local AI setup verdict; one still
      answering refuses with the probe's own verdict, which records nothing.
    * Another measurement holding the record longer than its bound refuses as
      not yet verified, naming no action.

    Nothing is downloaded, started or installed: the probe is one inference
    request to the server the reader would read from.

    Args:
        role: The reader role the consumer reads with.
        settings: Settings carrying the endpoint and role models.
        text_probe: The text reader's fitness probe, supplied by composition.
        model: The role model the consumer already resolved and will send;
            resolved through :func:`configured_role_model` when omitted.

    Returns:
        A :class:`DependencyStatus` on the ``local-reader:<role>`` row.
    """
    judged = _judge_reader(role, settings, installed=None, model=model, hardware=None)
    reader_model = judged.model
    if not judged.status.available or role not in FITNESS_PROBED_ROLES or reader_model is None:
        return judged.status
    digest = _inventory_digest(reader_model, judged.inventory)
    if digest is None:
        return judged.status
    try:
        outcome = _measure_at_first_use(role, reader_model, digest, judged.settings, text_probe=text_probe)
    except LockAcquisitionError:
        return _measurement_pending(role, reader_model, judged.settings)
    if outcome is not None and not outcome.settled:
        again = _judge_reader(role, settings, installed=None, model=model, hardware=None)
        if not again.status.available:
            return again.status
        return _unanswered_probe(role, outcome)
    return _reader_status_from_inventory(
        role,
        judged.settings,
        model=reader_model,
        inventory=judged.inventory,
        selection=judged.selection,
        hardware=judged.hardware,
        located=judged.located,
    )


def _inventory_digest(model: str, inventory: tuple[InstalledModel, ...] | None) -> str | None:
    return next(
        (entry.digest for entry in inventory or () if runtime_model_names_match(model, entry.name)),
        None,
    )


def _measure_at_first_use(
    role: ModelRole,
    model: str,
    digest: str,
    settings: Settings,
    *,
    text_probe: TextExtractionFitnessProbe,
) -> RoleFitnessOutcome | None:
    """Measure and record ``model``'s fitness unless its weights carry a verdict; ``None`` when they do.

    Raises:
        LockAcquisitionError: When another measurement holds the record past the wait.
    """
    with fitness_measurement_lock(settings, timeout=_measurement_wait_s(settings)):
        if recorded_role_fitness(role, model, digest, settings) is not RoleFitnessState.NOT_VERIFIED:
            return None
        outcome = probe_role_fitness(role, model, settings, text_probe=text_probe)
        if outcome is not None and outcome.settled:
            _record(outcome, digest=digest, settings=settings)
        return outcome


def _measurement_pending(role: ModelRole, model: str, settings: Settings) -> DependencyStatus:
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "runtime_reachable": True,
        "model": model,
        "role_model_installed": True,
        "fitness": RoleFitnessState.NOT_VERIFIED.value,
        "fitness_measurement_wait_s": int(_measurement_wait_s(settings)),
    }
    return DependencyStatus(
        service=local_reader_service(role),
        available=False,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED, facts=facts
        ),
    )


def _unanswered_probe(role: ModelRole, outcome: RoleFitnessOutcome) -> DependencyStatus:
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "runtime_reachable": True,
        "role_model_installed": True,
        **outcome.facts,
        "fitness": RoleFitnessState.NOT_VERIFIED.value,
    }
    return DependencyStatus(
        service=local_reader_service(role),
        available=False,
        facts=facts,
        precondition_verdict=outcome.precondition_verdict,
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


def _fitness_refusal(
    role: ModelRole,
    model: str,
    inventory: tuple[InstalledModel, ...],
    settings: Settings,
) -> DependencyStatus | None:
    """Return the admission refusal for a model whose current weights were found unfit or too slow."""
    state = recorded_role_fitness(role, model, _inventory_digest(model, inventory), settings)
    if state is not RoleFitnessState.UNFIT and state is not RoleFitnessState.TIMED_OUT:
        return None
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "runtime_reachable": True,
        "model": model,
        "role_model_installed": True,
        "fitness": state.value,
    }
    return DependencyStatus(
        service=local_reader_service(role),
        available=False,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(_FITNESS_FAILURE[state], facts=facts),
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
    unfit = _fitness_refusal(role, model, inventory, resolved)
    if unfit is not None:
        return unfit
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
    fitness: RoleFitnessState | None = None
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: str | None = None
    #: The operator action the reader probe named for the failed condition, or
    #: ``None`` when it named none -- a role this computer cannot run, a fitness
    #: verdict, or a ready role.
    recovery_action_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area or doctor row.

    ``extraction_ready`` is true only when the runtime answers, both
    invoice-extraction roles have their models installed and no fitness verdict
    found the text model's current weights unfit or too slow; it is the single
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


_FITNESS_FAILURE: Mapping[RoleFitnessState, ProvisioningPreconditionCondition] = {
    RoleFitnessState.NOT_VERIFIED: ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED,
    RoleFitnessState.TIMED_OUT: ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT,
    RoleFitnessState.UNFIT: ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE,
}


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


def _fresh_fitness_state(outcome: RoleFitnessOutcome) -> tuple[RoleFitnessState, str | None]:
    verdict = outcome.precondition_verdict
    failed = verdict.failed_condition_id if verdict is not None else None
    if not outcome.settled:
        return RoleFitnessState.NOT_VERIFIED, failed
    return RoleFitnessState(outcome.verdict.value), failed


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


def _current_role_fitness(
    role: ModelRole,
    model: str,
    *,
    settings: Settings,
    inventory: tuple[InstalledModel, ...] | None,
    text_probe: TextExtractionFitnessProbe | None,
) -> tuple[RoleFitnessState | None, str | None] | None:
    if text_probe is not None:
        outcome = probe_role_fitness(role, model, settings, text_probe=text_probe)
        return None if outcome is None else _fresh_fitness_state(outcome)
    state = recorded_role_fitness(role, model, _inventory_digest(model, inventory), settings)
    failed = _FITNESS_FAILURE[state].value if state is not None and state is not RoleFitnessState.FIT else None
    return state, failed


_NEGATIVE_FITNESS = frozenset({RoleFitnessState.UNFIT, RoleFitnessState.TIMED_OUT})
_FITNESS_CONDITIONS = frozenset(condition.value for condition in _FITNESS_FAILURE.values())


def _role_status(
    role: ModelRole,
    measured: _Measured,
    *,
    assess_load: bool,
    text_probe: TextExtractionFitnessProbe | None,
) -> LocalReaderRoleStatus:
    runtime = _role_runtime_status(role, measured, assess_load=assess_load)
    state: RoleFitnessState | None = None
    failure = runtime.failed_condition_id
    ready = runtime.ready
    if runtime.installed is True and runtime.model is not None and role in FITNESS_PROBED_ROLES:
        fitness = _current_role_fitness(
            role,
            runtime.model,
            settings=measured.settings,
            inventory=measured.inventory,
            text_probe=text_probe,
        )
        state, fitness_failure = (None, None) if fitness is None else fitness
        # Fitness is the consumer's admission: only a verdict that found the
        # weights unfit or too slow closes the role, never a missing one. A
        # check run now replaces what was recorded, and one that got no answer
        # at all closes the role on its own condition.
        admitted_but_for_fitness = ready or failure in _FITNESS_CONDITIONS
        if text_probe is not None and admitted_but_for_fitness:
            ready = state not in _NEGATIVE_FITNESS and fitness_failure is None
            failure = None if ready else fitness_failure
    fit = None if state is None or state is RoleFitnessState.NOT_VERIFIED else state is RoleFitnessState.FIT
    return LocalReaderRoleStatus(
        role=role,
        model=runtime.model,
        installed=runtime.installed,
        resident=runtime.resident,
        load_admitted=runtime.load_admitted,
        contention_causes=runtime.contention_causes,
        fitness=state,
        fit_for_role=fit,
        ready=ready,
        failed_condition_id=failure,
        # A fitness refusal names no action, as the probe's own does not.
        recovery_action_id=runtime.recovery_action_id if failure == runtime.failed_condition_id else None,
    )


def _runtime_models(
    settings: Settings,
    *,
    reachable: bool,
) -> tuple[tuple[InstalledModel, ...] | None, tuple[RuntimeResident, ...] | None]:
    if not reachable:
        return None, None
    return read_installed_models(settings), read_runtime_residents(settings)


def _include_extraction_roles(
    by_role: dict[ModelRole, LocalReaderRoleStatus],
    measured: _Measured,
    *,
    text_probe: TextExtractionFitnessProbe | None,
) -> None:
    for role in EXTRACTION_READER_ROLES:
        if role in by_role:
            continue
        by_role[role] = _role_status(role, measured, assess_load=False, text_probe=text_probe)


def read_local_reader_status(
    settings: Settings | None = None,
    *,
    roles: Iterable[ModelRole] | None = None,
    assess_load: bool = True,
    which: ExecutableLookup | None = None,
    text_probe: TextExtractionFitnessProbe | None = None,
) -> LocalReaderStatus:
    """Measure the runtime host and every role's model into one projection.

    Reads only: nothing is started, pulled or loaded. ``assess_load`` adds the
    admission check for installed models that are not yet resident, which
    reads hardware counters and can be skipped by a surface that refreshes
    often. Without ``text_probe`` the text model's fitness is the verdict
    recorded for its current digest at a consumer's first use, and a model with
    no recorded verdict is not verified rather than unfit, and is admitted. With
    ``text_probe`` the check runs now and its answer is reported without being
    recorded. Every reading is aimed at the server the local AI record names.
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
    role_rows = tuple(
        _role_status(role, measured, assess_load=assess_load, text_probe=text_probe) for role in _selected_roles(roles)
    )
    by_role = {row.role: row for row in role_rows}
    _include_extraction_roles(by_role, measured, text_probe=text_probe)
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

"""The local document reader as one provisioned unit: runtime, role models, readiness.

Invoice extraction reads a text-layer document with the TEXT_EXTRACTION model
and a scanned one with the VISION_TRANSCRIPTION model; column mapping and the
supply-nature proposal use their own roles. Each role reads the model its
setting names, so provisioning, status and the reader itself must resolve the
same identifier -- :func:`configured_role_model` is that single resolution.

Starting, installing and pulling live in :mod:`.provisioning_host` and
:mod:`.provisioning_runtime`; this module turns their measurements into the
projections a status surface renders and the per-role probe an ingestion lane
consults before spending a document. Its one write is the fitness verdict
:func:`verify_role_target` records in :mod:`.provisioning_fitness`; status
reads that record and never probes unless asked.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hardware import ContentionCause
from ..core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.clock import now
from .operator_actions.models import PreconditionVerdict
from .provisioning import DependencyStatus, ModelSelection, select_model_for_role
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)
from .provisioning_fitness import (
    RecordedFitnessVerdict,
    RoleFitnessVerdict,
    read_fitness_verdict,
    record_fitness_verdict,
)
from .provisioning_host import ExecutableLookup, RuntimeHostStatus, probe_runtime_host
from .provisioning_runtime import (
    InstalledModel,
    ReadinessOutcome,
    RuntimePullRecord,
    RuntimeResident,
    assess_model_load_contention,
    last_runtime_pull,
    read_installed_models,
    read_runtime_residents,
    runtime_model_names_match,
    verify_model_ready,
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
    "configured_role_model",
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
    inventory = read_installed_models(settings)
    if inventory is None:
        return None
    return next(
        (entry.digest for entry in inventory if runtime_model_names_match(model, entry.name)),
        None,
    )


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

    Records nothing; :func:`verify_role_target` is the only writer of the
    recorded verdict.
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

    Readiness first, through :func:`verify_model_ready`, then -- for a role in
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
    resolved = settings if settings is not None else load_settings()
    ready = verify_model_ready(target.model, settings=resolved)
    if not ready.ready or text_probe is None:
        return ready
    digest = _installed_digest(target.model, resolved)
    for role in target.roles:
        fitness = probe_role_fitness(role, target.model, resolved, text_probe=text_probe)
        if fitness is None:
            continue
        if fitness.settled and digest is not None:
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


def local_reader_service(role: ModelRole) -> str:
    """Return the stable diagnostic row id for one role's local reader."""
    return f"local-reader:{role.value}"


def configured_role_model(role: ModelRole, settings: Settings | None = None) -> str | None:
    """Return the runtime model id the on-host reader for ``role`` actually loads.

    The three document and table roles read their own settings; the
    supply-nature proposer resolves through catalogue selection, so it returns
    whatever that selection names, or ``None`` when nothing is selectable.
    """
    resolved = settings if settings is not None else load_settings()
    if role is ModelRole.VISION_TRANSCRIPTION:
        return resolved.cadrumo_llm_ollama_vision_model
    if role is ModelRole.TEXT_EXTRACTION:
        return resolved.cadrumo_llm_ollama_text_model
    if role is ModelRole.COLUMN_ROLE_MAPPING:
        return resolved.cadrumo_llm_ollama_mapping_model
    return select_model_for_role(role, settings=resolved).runtime_id


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


def _requirement_for(role: ModelRole, model: str, settings: Settings) -> int | None:
    candidate = model_candidate(model)
    if candidate is not None:
        return candidate.memory_requirement_bytes
    # An uncatalogued override declares no requirement; the role's selected
    # candidate is the closest measured claim, and the admission check runs
    # against it rather than against an invented figure.
    assessable = select_model_for_role(role, settings=settings).assessable_load
    return None if assessable is None else assessable[1]


def select_role_model(role: ModelRole, settings: Settings, *, explicit: str | None = None) -> ModelSelection:
    """Resolve ``role`` through catalogue selection, honouring an operator-set model.

    The configured setting is passed as an override only when it differs from
    the catalogue default, so a default configuration keeps every selection
    bar -- context window, licence, headroom -- and an operator's choice is
    honoured with its advisories. ``explicit`` outranks both.
    """
    configured = explicit
    if configured is None and role is not ModelRole.SUPPLY_NATURE_PROPOSAL:
        setting = configured_role_model(role, settings)
        configured = setting if setting != default_model_runtime_id(role) else None
    return select_model_for_role(role, settings=settings, override=configured)


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
    for role in tuple(ModelRole) if roles is None else tuple(roles):
        selection = select_role_model(role, resolved, explicit=explicit_model)
        model = selection.runtime_id
        if not selection.selected or model is None:
            refusals.append(
                RoleModelTarget(
                    roles=(role,),
                    selection_facts=selection.facts,
                    selection_verdict=selection.precondition_verdict,
                )
            )
            continue
        key = next((known for known in served if runtime_model_names_match(known, model)), model)
        served.setdefault(key, []).append(role)
        if requirements.get(key) is None:
            assessable = selection.assessable_load
            requirements[key] = assessable[1] if assessable is not None else _requirement_for(role, model, resolved)
    targets = tuple(
        RoleModelTarget(model=model, roles=tuple(roles_served), requirement_bytes=requirements.get(model))
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
) -> DependencyStatus:
    """Report whether the on-host reader for ``role`` can run right now.

    Unavailable when the runtime does not answer, or when it answers without
    the model this role's reader loads. An ingestion lane consults this per
    role, so a missing vision model never stops text-layer reads and a missing
    text model is not hidden behind an installed vision model.

    Args:
        role: The reader role a document needs.
        settings: Settings carrying the endpoint and role models.
        installed: An inventory already read; read from the runtime when omitted.

    Returns:
        A :class:`DependencyStatus` on the ``local-reader:<role>`` row. Never raises.
    """
    resolved = settings if settings is not None else load_settings()
    service = local_reader_service(role)
    model = configured_role_model(role, resolved)
    inventory = installed if installed is not None else read_installed_models(resolved)
    if inventory is None:
        facts: dict[str, ProvisioningFactValue] = {
            "role": role.value,
            "runtime_reachable": False,
            "runtime_url": resolved.cadrumo_llm_ollama_chat_url,
        }
        return DependencyStatus(
            service=service,
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE, facts=facts
            ),
        )
    if model is None:
        facts = {"role": role.value, "runtime_reachable": True, "role_model_selected": False}
        return DependencyStatus(
            service=service,
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE, facts=facts
            ),
        )
    if not _present(model, _names(inventory)):
        facts = {"role": role.value, "runtime_reachable": True, "model": model, "role_model_installed": False}
        return DependencyStatus(
            service=service,
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED, facts=facts
            ),
        )
    return DependencyStatus(
        service=service,
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


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area or doctor row.

    ``extraction_ready`` is true only when the runtime answers, both
    invoice-extraction roles have their models installed and the text model's
    current weights carry a recorded fit verdict; it is the single claim a
    surface may use to say every document can be read on this machine.
    ``document_readiness`` says which documents can be read either way, and
    ``text_layer_model_fill_available`` whether text-layer fields the labels do
    not print can be filled by the text model.
    """

    model_config = STRICT_FROZEN_CONFIG

    host: RuntimeHostStatus
    roles: tuple[LocalReaderRoleStatus, ...]
    last_pull: RuntimePullRecord | None = None
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


def _fresh_fitness_state(outcome: RoleFitnessOutcome) -> tuple[RoleFitnessState, str | None]:
    verdict = outcome.precondition_verdict
    failed = verdict.failed_condition_id if verdict is not None else None
    if not outcome.settled:
        return RoleFitnessState.NOT_VERIFIED, failed
    return RoleFitnessState(outcome.verdict.value), failed


def _role_status(
    role: ModelRole,
    *,
    settings: Settings,
    inventory: tuple[InstalledModel, ...] | None,
    residents: tuple[RuntimeResident, ...] | None,
    assess_load: bool,
    text_probe: TextExtractionFitnessProbe | None,
) -> LocalReaderRoleStatus:
    probe = probe_local_reader(role, settings, installed=inventory) if inventory is not None else None
    model = configured_role_model(role, settings)
    installed = None if model is None else _present(model, None if inventory is None else _names(inventory))
    resident = None if model is None else _present(model, None if residents is None else _names(residents))
    admitted: bool | None = None
    causes: tuple[ContentionCause, ...] = ()
    if assess_load and model is not None and installed and not resident:
        requirement = _requirement_for(role, model, settings)
        if requirement is not None:
            snapshot = assess_model_load_contention(
                model,
                requirement,
                residents=residents,
                residents_measured=residents is not None,
                settings=settings,
            )
            admitted = snapshot.admitted
            causes = snapshot.causes
    failed = None
    if probe is not None and probe.precondition_verdict is not None:
        failed = probe.precondition_verdict.failed_condition_id
    elif probe is None:
        failed = ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
    ready = probe is not None and probe.available
    state: RoleFitnessState | None = None
    if ready and model is not None and role in FITNESS_PROBED_ROLES:
        if text_probe is not None:
            outcome = probe_role_fitness(role, model, settings, text_probe=text_probe)
            if outcome is not None:
                state, fresh_failure = _fresh_fitness_state(outcome)
                failed = fresh_failure
        else:
            digest = next(
                (entry.digest for entry in inventory or () if runtime_model_names_match(model, entry.name)),
                None,
            )
            state = recorded_role_fitness(role, model, digest, settings)
            if state is not None and state is not RoleFitnessState.FIT:
                failed = _FITNESS_FAILURE[state].value
        if state is not None and state is not RoleFitnessState.FIT:
            ready = False
    fit = None if state is None or state is RoleFitnessState.NOT_VERIFIED else state is RoleFitnessState.FIT
    return LocalReaderRoleStatus(
        role=role,
        model=model,
        installed=installed,
        resident=resident,
        load_admitted=admitted,
        contention_causes=causes,
        fitness=state,
        fit_for_role=fit,
        ready=ready,
        failed_condition_id=failed,
    )


def read_local_reader_status(
    settings: Settings | None = None,
    *,
    roles: Iterable[ModelRole] | None = None,
    assess_load: bool = True,
    which: ExecutableLookup | None = None,
    pull_record: Callable[[], RuntimePullRecord | None] = last_runtime_pull,
    text_probe: TextExtractionFitnessProbe | None = None,
) -> LocalReaderStatus:
    """Measure the runtime host and every role's model into one projection.

    Reads only: nothing is started, pulled or loaded. ``assess_load`` adds the
    admission check for installed models that are not yet resident, which
    reads hardware counters and can be skipped by a surface that refreshes
    often. Without ``text_probe`` the text model's fitness is the verdict
    ``verify`` recorded for its current digest, and a model with no recorded
    verdict is not verified rather than unfit. With ``text_probe`` the check runs
    now and its answer is reported without being recorded.
    """
    resolved = settings if settings is not None else load_settings()
    host = probe_runtime_host(resolved) if which is None else probe_runtime_host(resolved, which=which)
    inventory = read_installed_models(resolved) if host.reachable else None
    residents = read_runtime_residents(resolved) if host.reachable else None
    selected_roles = tuple(ModelRole) if roles is None else tuple(roles)
    role_rows = tuple(
        _role_status(
            role,
            settings=resolved,
            inventory=inventory,
            residents=residents,
            assess_load=assess_load,
            text_probe=text_probe,
        )
        for role in selected_roles
    )
    by_role = {row.role: row for row in role_rows}
    for role in EXTRACTION_READER_ROLES:
        if role not in by_role:
            by_role[role] = _role_status(
                role,
                settings=resolved,
                inventory=inventory,
                residents=residents,
                assess_load=False,
                text_probe=text_probe,
            )
    extraction_ready = host.reachable and all(by_role[role].ready for role in EXTRACTION_READER_ROLES)
    text_row = by_role[ModelRole.TEXT_EXTRACTION]
    return LocalReaderStatus(
        host=host,
        roles=role_rows,
        last_pull=pull_record(),
        extraction_ready=extraction_ready,
        document_readiness=(
            LocalReaderDocumentReadiness.ALL_DOCUMENTS
            if extraction_ready
            else LocalReaderDocumentReadiness.TEXT_LAYER_ONLY
        ),
        text_layer_model_fill_available=host.reachable and text_row.ready,
    )

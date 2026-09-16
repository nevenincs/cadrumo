"""The local document reader as one provisioned unit: runtime, role models, readiness.

Invoice extraction reads a text-layer document with the TEXT_EXTRACTION model
and a scanned one with the VISION_TRANSCRIPTION model; column mapping and the
supply-nature proposal use their own roles. Each role reads the model its
setting names, so provisioning, status and the reader itself must resolve the
same identifier -- :func:`configured_role_model` is that single resolution.

Everything here reads. Starting, installing and pulling live in
:mod:`.provisioning_host` and :mod:`.provisioning_runtime`; this module turns
their measurements into the projections a status surface renders and the
per-role probe an ingestion lane consults before spending a document.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from pydantic import BaseModel, Field, model_validator

from ..core.config import Settings, load_settings
from ..core.hardware import ContentionCause
from ..core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ..core.models import STRICT_FROZEN_CONFIG
from .operator_actions.models import PreconditionVerdict
from .provisioning import DependencyStatus, ModelSelection, select_model_for_role
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
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
    verify_model_ready,
)

__all__ = [
    "EXTRACTION_READER_ROLES",
    "FITNESS_PROBED_ROLES",
    "LocalReaderRoleStatus",
    "LocalReaderStatus",
    "RoleFitnessOutcome",
    "RoleModelTarget",
    "TextExtractionFitnessProbe",
    "assess_role_fitness",
    "configured_role_model",
    "forget_role_fitness",
    "local_reader_service",
    "probe_local_reader",
    "read_local_reader_status",
    "role_model_targets",
    "runtime_model_names_match",
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
    whose values did not match the probe document. ``transport_failed`` marks a
    probe that never got an answer, which says nothing about the model and is
    therefore never remembered.
    """

    role: ModelRole
    model: str = Field(min_length=1)
    fit: bool
    answer_parseable: bool = False
    grounded: bool = False
    transport_failed: bool = False
    output_tokens: int | None = Field(default=None, ge=0)
    answer_budget_tokens: int = Field(gt=0)
    elapsed_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _require_fitness_outcome(self) -> RoleFitnessOutcome:
        require_provisioning_verdict(failed=not self.fit, verdict=self.precondition_verdict)
        return self


type TextExtractionFitnessProbe = Callable[[str, Settings], RoleFitnessOutcome]
"""Runs the text reader's real request shape and budget against a model; supplied by composition."""

#: Settled verdicts by ``(endpoint, model)``. A model's fitness for a request
#: shape does not change while it stays pulled, and the probe costs a model
#: load plus a full answer budget, so a status surface refreshing often asks
#: once. Transport failures are never stored.
_FITNESS_VERDICTS: dict[tuple[str, str], RoleFitnessOutcome] = {}


def forget_role_fitness() -> None:
    """Drop every remembered fitness verdict, after a pull or removal changes a model."""
    _FITNESS_VERDICTS.clear()


def assess_role_fitness(
    role: ModelRole,
    model: str,
    settings: Settings,
    *,
    text_probe: TextExtractionFitnessProbe,
) -> RoleFitnessOutcome | None:
    """Return ``model``'s fitness for ``role``, or ``None`` when the role is not probed.

    Remembered per endpoint and model, so a repeated status read does not
    re-run a probe whose answer cannot have changed.
    """
    if role not in FITNESS_PROBED_ROLES:
        return None
    key = (settings.cadrumo_llm_ollama_chat_url, model)
    known = _FITNESS_VERDICTS.get(key)
    if known is not None:
        return known
    outcome = text_probe(model, settings)
    if not outcome.transport_failed:
        _FITNESS_VERDICTS[key] = outcome
    return outcome


def verify_role_target(
    target: RoleModelTarget,
    *,
    settings: Settings | None = None,
    text_probe: TextExtractionFitnessProbe | None = None,
) -> ReadinessOutcome:
    """Verify a provisioning target is loaded, answering and fit for every role it serves.

    Readiness first, through :func:`verify_model_ready`, then -- for a role in
    :data:`FITNESS_PROBED_ROLES` and when a probe is supplied -- the role's
    real request shape. An unfit model is reported not ready with the
    ``fit_for_role`` condition, so ``verify`` cannot pass a model the reader
    will never get an answer from.

    Raises:
        ValueError: When ``target`` carries no model (a refused selection).
    """
    if target.model is None:
        raise ValueError("a refused selection has no model to verify")
    resolved = settings if settings is not None else load_settings()
    ready = verify_model_ready(target.model, settings=resolved)
    if not ready.ready or text_probe is None:
        return ready
    for role in target.roles:
        fitness = assess_role_fitness(role, target.model, resolved, text_probe=text_probe)
        if fitness is None or fitness.fit:
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


def runtime_model_names_match(left: str, right: str) -> bool:
    """Return whether two runtime model names denote the same tagged model.

    An untagged name means ``:latest`` to the runtime, so ``qwen3`` and
    ``qwen3:latest`` match while ``qwen3:1.7b`` and ``qwen3:8b`` do not -- a
    different size is a different download and a different memory claim.
    """

    def normalised(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return normalised(left) == normalised(right)


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
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: str | None = None


class LocalReaderStatus(BaseModel):
    """The whole local reader at one moment, for a status area or doctor row.

    ``extraction_ready`` is true only when the runtime answers and both
    invoice-extraction roles have their models installed; it is the single
    claim a surface may use to say documents can be read on this machine.
    """

    model_config = STRICT_FROZEN_CONFIG

    host: RuntimeHostStatus
    roles: tuple[LocalReaderRoleStatus, ...]
    last_pull: RuntimePullRecord | None = None
    extraction_ready: bool


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
    fit: bool | None = None
    if ready and model is not None and text_probe is not None:
        fitness = assess_role_fitness(role, model, settings, text_probe=text_probe)
        if fitness is not None:
            fit = fitness.fit
            if not fitness.fit and fitness.precondition_verdict is not None:
                ready = False
                failed = fitness.precondition_verdict.failed_condition_id
    return LocalReaderRoleStatus(
        role=role,
        model=model,
        installed=installed,
        resident=resident,
        load_admitted=admitted,
        contention_causes=causes,
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
    often. ``text_probe`` adds the text reader's fitness check to an installed
    text model, so ``extraction_ready`` is false for a model that is present but
    cannot answer the extraction request; its verdict is remembered per model.
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
    extraction_ready = host.reachable and all(
        (
            by_role[role]
            if role in by_role
            else _role_status(
                role,
                settings=resolved,
                inventory=inventory,
                residents=residents,
                assess_load=False,
                text_probe=text_probe,
            )
        ).ready
        for role in EXTRACTION_READER_ROLES
    )
    return LocalReaderStatus(
        host=host,
        roles=role_rows,
        last_pull=pull_record(),
        extraction_ready=extraction_ready,
    )

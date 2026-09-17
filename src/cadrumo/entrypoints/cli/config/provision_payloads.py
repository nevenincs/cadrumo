"""Typed ``--json`` payload schemas for the ``aeat config provision`` verbs.

Each class is a strict :class:`~core.json_contract.OutputSchema` referenced by
production-authored CommandSpec as deferred public schema targets, so the JSON-contract gate enumerates
the surface. Diagnostics ride the shared envelope's typed ``notices`` channel;
nothing here declares a bespoke ``advisory``, ``next`` or ``suggestion`` field,
which the envelope contract forbids.

The contention block is carried as structured fields rather than a rendered
sentence. Its condition, evidence, and closed outcome are projected through the
shared action resolver; this schema does not own an instruction.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, NonNegativeInt

from ....application.local_reader import LocalReaderDocumentReadiness, RoleFitnessState
from ....core.hardware import ContentionCause
from ....core.json_contract import OutputSchema, ResolvedPreconditionAction
from ....core.text_bounds import NonEmptyStr

ProvisioningFactPayload = Mapping[str, str | int | bool]
"""Locale-neutral scalar facts projected from a provisioning outcome."""


class ProvisionContentionPayload(OutputSchema):
    """The measured admission verdict for one model load.

    ``causes`` is the :class:`~core.ContentionCause` set the application layer
    attributed the shortfall to. The application outcome's facts and resolved
    verdict preserve the remaining explanation without prose parsing.
    """

    model: NonEmptyStr
    admitted: bool
    causes: list[ContentionCause] = []
    required_bytes: NonNegativeInt
    free_vram_bytes: int | None = None
    free_system_memory_bytes: int | None = None
    shortfall_bytes: int | None = None
    unloadable_models: list[str] = []
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionModelPayload(OutputSchema):
    """One role's resolved model and whether it is present in the runtime."""

    role: NonEmptyStr
    model: str | None = None
    selected: bool
    resident: bool = False
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionReportResult(OutputSchema):
    """JSON envelope for ``aeat config provision report``.

    The doctor rows for local inference in one place: what the machine measures,
    which model each role resolves to, and whether that model could be loaded
    right now. Read-only -- it pulls nothing and loads nothing.
    """

    accelerator: str
    total_vram_bytes: int | None = None
    free_vram_bytes: int | None = None
    total_system_memory_bytes: int | None = None
    free_system_memory_bytes: int | None = None
    runtime_reachable: bool
    residents: list[str] = []
    models: list[ProvisionModelPayload] = []
    contention: ProvisionContentionPayload | None = None


class ProvisionPullItemPayload(OutputSchema):
    """One model fetch, or one role whose selection refused before any fetch.

    ``pulled`` false with ``contention`` populated means the fetch was refused
    BEFORE any bytes moved -- the admission check runs first precisely so a
    multi-gigabyte download does not complete only to arrive at a refusal that
    was knowable at the start.
    """

    model: NonEmptyStr | None = None
    roles: list[str] = []
    pulled: bool
    bytes_fetched: int | None = None
    contention: ProvisionContentionPayload | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionPullResult(OutputSchema):
    """JSON envelope for ``aeat config provision pull``; ``pulled`` is true only when every item pulled."""

    pulled: bool
    models: list[ProvisionPullItemPayload] = []


class ProvisionVerifyItemPayload(OutputSchema):
    """One model's readiness observation, or one role whose selection refused.

    ``resident`` and ``answered`` are separate claims: a model can be present
    and not loaded, or loaded and too slow to be useful, and an operator
    debugging a stalled read needs to know which they have.
    """

    model: NonEmptyStr | None = None
    roles: list[str] = []
    ready: bool
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config provision verify``; ``ready`` is true only when every item is."""

    ready: bool
    models: list[ProvisionVerifyItemPayload] = []


class ProvisionRuntimePayload(OutputSchema):
    """Whether the local runtime is installed on this host and whether it answers."""

    platform: NonEmptyStr
    endpoint_url: NonEmptyStr
    endpoint_local: bool
    executable_located: bool
    reachable: bool
    version: str | None = None
    installer: NonEmptyStr
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionRoleStatusPayload(OutputSchema):
    """One reader role's model and what the runtime reports about it.

    ``installed``, ``resident`` and ``load_admitted`` are null when they could
    not be measured, which is distinct from false. ``fitness`` is null for a
    role without a fitness probe or a model not ready to probe; otherwise it is
    ``fit``, ``unfit``, ``timed_out`` or ``not_verified`` -- the last meaning no
    verdict is recorded for the model's current weights, which is not unfitness.
    ``fit_for_role`` is null unless a verdict exists.
    """

    role: NonEmptyStr
    model: str | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: list[ContentionCause] = []
    fitness: RoleFitnessState | None = None
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: str | None = None


class ProvisionLastPullPayload(OutputSchema):
    """The most recent fetch this process attempted."""

    model: NonEmptyStr
    pulled: bool
    attempted_at: NonEmptyStr
    bytes_fetched: int | None = None
    failed_condition_id: str | None = None


class ProvisionStatusResult(OutputSchema):
    """JSON envelope for ``aeat config provision status``. Reads only.

    ``probed`` says whether the text model's fitness was checked now
    (``--probe``) rather than read from the verdict ``verify`` recorded.
    """

    runtime: ProvisionRuntimePayload
    roles: list[ProvisionRoleStatusPayload] = []
    last_pull: ProvisionLastPullPayload | None = None
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool
    probed: bool


class ProvisionInstallResult(OutputSchema):
    """JSON envelope for ``aeat config provision install``."""

    installed: bool
    already_installed: bool = False
    installer: NonEmptyStr
    consented: bool
    installer_exit_code: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionBrowserResult(OutputSchema):
    """JSON envelope for ``aeat config provision browser``."""

    installed: bool
    already_installed: bool = False
    installer_exit_code: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionStartResult(OutputSchema):
    """JSON envelope for ``aeat config provision start``."""

    running: bool
    already_running: bool = False
    started_pid: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionRemoveItemPayload(OutputSchema):
    """One model removal; ``freed_bytes`` is reported only when the removal was confirmed."""

    model: NonEmptyStr | None = None
    roles: list[str] = []
    removed: bool
    was_installed: bool = False
    freed_bytes: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config provision remove``; ``removed`` is true only when every item was."""

    removed: bool
    models: list[ProvisionRemoveItemPayload] = []


class ProvisionLoadItemPayload(OutputSchema):
    """One model load, or one role whose selection refused before any load.

    ``already_loaded`` marks a model that was resident before the request, so
    nothing was sent to the runtime.
    """

    model: NonEmptyStr | None = None
    roles: list[str] = []
    loaded: bool
    already_loaded: bool = False
    elapsed_ms: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionLoadResult(OutputSchema):
    """JSON envelope for ``aeat config provision load``; ``loaded`` is true only when every item loaded."""

    loaded: bool
    models: list[ProvisionLoadItemPayload] = []


class ProvisionSetupStepPayload(OutputSchema):
    """One setup step: ``unchanged``, ``changed``, ``failed`` or ``not_reached``."""

    step: NonEmptyStr
    state: NonEmptyStr
    failed_condition_id: str | None = None


class ProvisionSetupModelPayload(OutputSchema):
    """What one setup step did to one model, or one role whose selection refused."""

    step: NonEmptyStr
    model: NonEmptyStr | None = None
    roles: list[str] = []
    succeeded: bool
    already_satisfied: bool = False
    bytes_fetched: int | None = None
    elapsed_ms: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionSetupResult(OutputSchema):
    """JSON envelope for ``aeat config provision setup``.

    ``stopped_step`` names the step that failed; every later step is
    ``not_reached``. ``precondition_action`` resolves the install or start
    refusal when one of those steps stopped the run.
    """

    succeeded: bool
    stopped_step: str | None = None
    steps: list[ProvisionSetupStepPayload] = []
    runtime_started: bool = False
    install_consented: bool
    models: list[ProvisionSetupModelPayload] = []
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


__all__ = [
    "ProvisionBrowserResult",
    "ProvisionContentionPayload",
    "ProvisionInstallResult",
    "ProvisionLastPullPayload",
    "ProvisionLoadItemPayload",
    "ProvisionLoadResult",
    "ProvisionModelPayload",
    "ProvisionPullItemPayload",
    "ProvisionPullResult",
    "ProvisionRemoveItemPayload",
    "ProvisionRemoveResult",
    "ProvisionReportResult",
    "ProvisionRoleStatusPayload",
    "ProvisionRuntimePayload",
    "ProvisionSetupModelPayload",
    "ProvisionSetupResult",
    "ProvisionSetupStepPayload",
    "ProvisionStartResult",
    "ProvisionStatusResult",
    "ProvisionVerifyItemPayload",
    "ProvisionVerifyResult",
]

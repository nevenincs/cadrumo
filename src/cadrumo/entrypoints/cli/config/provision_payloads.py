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
    not be measured, which is distinct from false.
    """

    role: NonEmptyStr
    model: str | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: list[ContentionCause] = []
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
    """JSON envelope for ``aeat config provision status``. Reads only."""

    runtime: ProvisionRuntimePayload
    roles: list[ProvisionRoleStatusPayload] = []
    last_pull: ProvisionLastPullPayload | None = None
    extraction_ready: bool


class ProvisionInstallResult(OutputSchema):
    """JSON envelope for ``aeat config provision install``."""

    installed: bool
    already_installed: bool = False
    installer: NonEmptyStr
    consented: bool
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


__all__ = [
    "ProvisionContentionPayload",
    "ProvisionInstallResult",
    "ProvisionLastPullPayload",
    "ProvisionModelPayload",
    "ProvisionPullItemPayload",
    "ProvisionPullResult",
    "ProvisionRemoveItemPayload",
    "ProvisionRemoveResult",
    "ProvisionReportResult",
    "ProvisionRoleStatusPayload",
    "ProvisionRuntimePayload",
    "ProvisionStartResult",
    "ProvisionStatusResult",
    "ProvisionVerifyItemPayload",
    "ProvisionVerifyResult",
]

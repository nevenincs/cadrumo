"""Typed ``--json`` payload schemas for the ``aeat config provision`` verbs.

Each class is a strict :class:`~core.json_contract.OutputSchema` registered with
CommandSpec schema authority, so the JSON-contract gate enumerates
the surface. Diagnostics ride the shared envelope's typed ``notices`` channel;
nothing here declares a bespoke ``advisory``, ``next`` or ``suggestion`` field,
which the envelope contract forbids.

The contention block is carried as structured fields rather than a rendered
sentence. Its condition, evidence, and closed outcome are projected through the
shared action resolver; this schema does not own an instruction.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from ....core import ContentionCause
from ....core.json_contract import OutputSchema, ResolvedPreconditionAction

ProvisioningFactPayload = Mapping[str, str | int | bool]
"""Locale-neutral scalar facts projected from a provisioning outcome."""


class ProvisionContentionPayload(OutputSchema):
    """The measured admission verdict for one model load.

    ``causes`` is the :class:`~core.ContentionCause` set the application layer
    attributed the shortfall to. The application outcome's facts and resolved
    verdict preserve the remaining explanation without prose parsing.
    """

    model: str = Field(min_length=1)
    admitted: bool
    causes: list[ContentionCause] = []
    required_bytes: int = Field(ge=0)
    free_vram_bytes: int | None = None
    free_system_memory_bytes: int | None = None
    shortfall_bytes: int | None = None
    unloadable_models: list[str] = []
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionModelPayload(OutputSchema):
    """One role's resolved model and whether it is present in the runtime."""

    role: str = Field(min_length=1)
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


class ProvisionPullResult(OutputSchema):
    """JSON envelope for ``aeat config provision pull``.

    ``pulled`` false with ``contention`` populated means the fetch was refused
    BEFORE any bytes moved -- the admission check runs first precisely so a
    multi-gigabyte download does not complete only to arrive at a refusal that
    was knowable at the start.
    """

    model: str | None = Field(default=None, min_length=1)
    pulled: bool
    bytes_fetched: int | None = None
    contention: ProvisionContentionPayload | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionVerifyResult(OutputSchema):
    """JSON envelope for ``aeat config provision verify``.

    ``resident`` and ``answered`` are separate claims: a model can be present
    and not loaded, or loaded and too slow to be useful, and an operator
    debugging a stalled read needs to know which they have.
    """

    model: str | None = Field(default=None, min_length=1)
    ready: bool
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = None
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


__all__ = [
    "ProvisionContentionPayload",
    "ProvisionModelPayload",
    "ProvisionPullResult",
    "ProvisionReportResult",
    "ProvisionVerifyResult",
]

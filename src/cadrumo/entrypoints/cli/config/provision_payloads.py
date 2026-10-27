"""Typed ``--json`` payload schemas for the ``aeat config provision`` verbs.

Each class is a strict :class:`~core.json_contract.OutputSchema` referenced by
production-authored CommandSpec as deferred public schema targets, so the JSON-contract gate enumerates
the surface. Diagnostics ride the shared envelope's typed ``notices`` channel;
nothing here declares a bespoke ``advisory``, ``next`` or ``suggestion`` field,
which the envelope contract forbids.

A refusal is carried as structured fields rather than a rendered sentence. Its
condition, evidence, and closed outcome are projected through the shared action
resolver; this schema does not own an instruction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, NonNegativeInt

from ....application.operations.models import OperationId
from ....core.json_contract import OutputSchema, ResolvedPreconditionAction
from ....core.text_bounds import NonEmptyStr

ProvisioningFactPayload = Mapping[str, str | int | bool]
"""Locale-neutral scalar facts projected from a provisioning outcome."""


class ProvisionModelPayload(OutputSchema):
    """One role's selected lane and the model it loads on this computer."""

    role: NonEmptyStr
    model: str | None = None
    selected: bool
    facts: ProvisioningFactPayload = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction | None = None


class ProvisionReportResult(OutputSchema):
    """JSON envelope for ``aeat config provision report``.

    The doctor rows for local inference in one place: what the machine measures
    and the lane the person selected for each role. Read-only -- it pulls
    nothing, loads nothing and asks the local AI server nothing.
    """

    accelerator: str
    total_vram_bytes: int | None = None
    free_vram_bytes: int | None = None
    total_system_memory_bytes: int | None = None
    free_system_memory_bytes: int | None = None
    models: list[ProvisionModelPayload] = []


class ProvisionItemPayload(OutputSchema):
    """One setup item's derived row, exactly as every surface reads it.

    ``state`` and its one reason are closed values; the text output turns
    them into a plain sentence. ``command`` is the exact command that offers
    the row's recovery, present exactly when ``recovery_action_id`` is.
    """

    item_id: NonEmptyStr
    state: NonEmptyStr
    stale_reason: str | None = None
    blocked_reason: str | None = None
    failure_category: str | None = None
    version: str | None = None
    size_estimate_bytes: int | None = None
    recovery: str | None = None
    recovery_action_id: str | None = None
    command: str | None = None


class ProvisionStatusResult(OutputSchema):
    """JSON envelope for ``aeat config provision status``: every item's quick check.

    ``complete`` is true when every item is ready or usable; ``hardware_limited``
    names a computer below the model floor, which no setup can fix.
    ``failure_category`` is the category the engine refused the check itself
    under, such as a proxy setting it cannot use; it then reports no item.
    """

    mode: NonEmptyStr
    complete: bool
    hardware_limited: bool
    failure_category: str | None = None
    items: list[ProvisionItemPayload] = []


class ProvisionProbeResult(ProvisionStatusResult):
    """JSON envelope for ``aeat config provision probe``: every item's full check."""


class ProvisionVerifyResult(ProvisionStatusResult):
    """JSON envelope for ``aeat config provision verify``: the full check of the named items."""


class ProvisionSpacePayload(OutputSchema):
    """Free space on the storage volume against what the plan needs; unknown free space is never enough."""

    free_bytes: int | None = None
    required_bytes: NonNegativeInt
    sufficient: bool


class ProvisionSetupResult(OutputSchema):
    """JSON envelope for ``aeat config provision setup``.

    ``outcome`` is the component engine's closed outcome. ``approved`` records
    whether the printed plan was approved; nothing moves without it.
    ``item_id`` and ``failure_category`` name the item and the category a
    refusal or failure is for. ``items`` is every item's row after the setup.
    """

    outcome: NonEmptyStr
    approved: bool
    plan_digest: str | None = None
    space: ProvisionSpacePayload | None = None
    item_id: str | None = None
    failure_category: str | None = None
    complete: bool
    items: list[ProvisionItemPayload] = []


class ProvisionRemoveResult(OutputSchema):
    """JSON envelope for ``aeat config provision remove``.

    ``item`` is the component asked for and ``confirmed`` whether the person
    confirmed its removal; nothing is removed without it. ``outcome`` is the
    component engine's closed outcome, absent when nothing was asked of it, and
    ``removed`` the items it removed. ``item_id`` and ``failure_category`` name
    the item and the category of a refusal or failure. ``items`` is every
    item's row after the removal.
    """

    item: NonEmptyStr
    confirmed: bool
    outcome: str | None = None
    removed: list[str] = []
    item_id: str | None = None
    failure_category: str | None = None
    items: list[ProvisionItemPayload] = []


class ProvisionBrowserResult(ProvisionSetupResult):
    """JSON envelope for ``aeat config provision browser``: the setup of the browser alone."""


class ProvisionReviewResult(OutputSchema):
    """A response accepted for the current setup review; settlement may still be pending."""

    operation_id: OperationId
    decision: Literal["apply", "reject"]


__all__ = [
    "ProvisionBrowserResult",
    "ProvisionItemPayload",
    "ProvisionModelPayload",
    "ProvisionProbeResult",
    "ProvisionRemoveResult",
    "ProvisionReportResult",
    "ProvisionReviewResult",
    "ProvisionSetupResult",
    "ProvisionSpacePayload",
    "ProvisionStatusResult",
    "ProvisionVerifyResult",
]

"""Public, credential-free CLI projection of installed runtime management facts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from ...application.runtime.management import RuntimeManagerInspection
from ...application.runtime.management_status import RuntimeListenerState, RuntimeManagerAvailability
from ...core.json_contract import OutputSchema


class RuntimeStatusResult(OutputSchema):
    """Keep listener readiness separate from manager and autostart observations."""

    listener: RuntimeListenerState
    manager_availability: RuntimeManagerAvailability
    manager: RuntimeManagerInspection | None = None


class RuntimeManagerConfigResult(OutputSchema):
    """Observed native task configuration after an explicit operator change."""

    manager: RuntimeManagerInspection


class RuntimeStopResult(OutputSchema):
    """Accepted global stop request, without a settlement claim."""

    runtime_boot_id: UUID
    scope: Literal["all_profiles_and_work"]


__all__ = ["RuntimeManagerConfigResult", "RuntimeStatusResult", "RuntimeStopResult"]

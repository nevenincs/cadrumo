"""User-session manager facts, separate from runtime readiness and authorization."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, Field

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class RuntimeManagerKind(StrEnum):
    """Supported per-user launch facilities; none implies unattended authority."""

    WINDOWS_TASK = "windows_task"
    MACOS_AGENT = "macos_agent"
    LINUX_USER_SERVICE = "linux_user_service"


class RuntimeManagerProcessState(StrEnum):
    """Manager observations, which do not establish authenticated readiness."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    UNKNOWN = "unknown"


class RuntimeServiceBinding(BaseModel):
    """Nonsecret installed executable, owner, root and expected cohort binding.

    Trusted composition supplies canonical native paths and physical storage
    identity. The launched runtime must independently revalidate them before
    private admission. Manager configuration is not authentication proof.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    executable: Annotated[str, Field(min_length=1, max_length=4096)]
    storage_root: Annotated[str, Field(min_length=1, max_length=4096)]
    storage_identity: ContentDigest
    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    product_version: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$")]


class RuntimeManagerInspection(BaseModel):
    """Keep manager reachability, provisioning and login startup independent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: RuntimeManagerKind
    available: bool
    provisioned: bool
    binding_matches: bool
    login_autostart: bool
    process_state: RuntimeManagerProcessState


class RuntimeUserManager(Protocol):
    """Native deployment port consumed by authorized runtime management only.

    Start uses existing provisioning and never enables login autostart. Stop
    follows application fencing/draining; the manager cannot certify committed
    effects, application settlement, or profile custody release.
    """

    async def inspect(self) -> RuntimeManagerInspection:
        """Read exact binding and manager state without changing deployment."""
        ...

    async def start(self) -> None:
        """Request existing bound deployment start without changing its policy."""
        ...

    async def stop(self) -> None:
        """Stop only the bound deployment after its application's drain phase."""
        ...

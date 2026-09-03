"""One real installed-workbench composition, shared by the workbench gates.

The composition under test is the production one: a real encrypted profile is
created and unlocked through the canonical registration and login doors, and
the root is then composed exactly the way ``aeat --tui`` composes it. Nothing
here substitutes a projection, a repository, or an operation service — a gate
built on a stand-in would prove only that the stand-in agrees with itself.

The profile is genuinely empty of tax data, which is the point: a fresh
operator is the state every workbench surface has to remain truthful in, and
"no work yet" must not render as a missing or broken destination.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from ....application.user_profile.login_interaction import profile_login_choices
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....tests.secure_sql import isolated_profile_storage_root
from ..installed_session import compose_authenticated_root_inputs_provider
from ..launcher import InstalledWorkbenchRootCompositionV1, compose_installed_workbench_root, operation_services_scope

WORKBENCH_PROFILE_LABEL: Final[str] = "Workbench subject"
"""A synthetic operator label; it identifies nobody and holds no tax data."""

_WORKBENCH_PASSWORD: Final[str] = "correct horse battery staple 42!"  # noqa: S105 - synthetic test credential


@asynccontextmanager
async def installed_workbench_root(tmp_path: Path) -> AsyncGenerator[InstalledWorkbenchRootCompositionV1]:
    """Compose one authenticated installed workbench root over real storage."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            label=WORKBENCH_PROFILE_LABEL,
            passphrase=_WORKBENCH_PASSWORD,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        # Registration closes its own session and leaves the capsule sealed, so
        # the workbench generation below needs a real login to read anything.
        login_profile(name=WORKBENCH_PROFILE_LABEL, passphrase_callback=lambda: _WORKBENCH_PASSWORD)
        provider = compose_authenticated_root_inputs_provider(
            profile_id=require_active_bucket_id(),
            profile_label=WORKBENCH_PROFILE_LABEL,
            login_choices=profile_login_choices(),
        )
        async with operation_services_scope() as operation_runtime:
            yield compose_installed_workbench_root(provider(operation_runtime))


__all__ = ["WORKBENCH_PROFILE_LABEL", "installed_workbench_root"]

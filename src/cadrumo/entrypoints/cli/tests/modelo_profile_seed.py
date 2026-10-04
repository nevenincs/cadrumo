"""Own the registered human profile and joined runtime for Modelo CLI scenarios."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Unpack
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .cli_runner import ClickInvokeKwargs, invoke_cached_cli

if TYPE_CHECKING:
    from .portable_human_cli_runtime import PortableHumanCliRuntime

__all__ = ["ProfileSeeder", "invoke_seeded_profile_cli", "seed_profile"]

type ProfileSeeder = Callable[..., PortableHumanCliRuntime]

_CURRENT_RUNTIME: ContextVar[PortableHumanCliRuntime | None] = ContextVar("modelo-seeded-human-runtime", default=None)


def invoke_seeded_profile_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Use the seeded human's credential transport, retaining public calls without a seed."""
    runtime = _CURRENT_RUNTIME.get()
    return invoke_cached_cli(args, **kwargs) if runtime is None else runtime.invoke(args, **kwargs)


@pytest.fixture
def seed_profile(tmp_path: Path) -> Iterator[ProfileSeeder]:
    """Register one fresh profile and keep its runtime and local setup oracle owned.

    Each profile has genuine password custody material. The joined human runtime
    owns admitted CLI requests while preserving the parent encrypted session used
    for controlled test setup. Neither an active pointer nor that setup session is
    treated as frontend admission. The per-test storage root and runtime binding
    are retired together, including exceptional exits.
    """
    with ExitStack() as stack:
        storage_root = stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        seeded: list[str] = []

        def seed(*, label: str, facts: Mapping[str, str]) -> PortableHumanCliRuntime:
            assert not seeded, f"a profile was already seeded in this test: {seeded}"
            seeded.append(label)
            from .portable_human_cli_runtime import portable_human_cli_runtime

            profile_id = register_cli_profile(label=label, facts=facts, log_in=False)
            runtime = stack.enter_context(
                portable_human_cli_runtime(storage_root=storage_root, profile_id=UUID(profile_id), label=label)
            )
            token = _CURRENT_RUNTIME.set(runtime)
            stack.callback(_CURRENT_RUNTIME.reset, token)
            return runtime

        yield seed

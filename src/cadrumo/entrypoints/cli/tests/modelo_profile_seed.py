"""Own the registered human profile and joined runtime for Modelo CLI scenarios."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .cli_runner import bind_profile_cli

if TYPE_CHECKING:
    from .portable_human_cli_runtime import PortableHumanCliRuntime

__all__ = ["ProfileSeeder", "seed_profile", "seed_test_profile"]

type ProfileSeeder = Callable[..., PortableHumanCliRuntime]


_CURRENT_SEEDER: ContextVar[ProfileSeeder | None] = ContextVar("modelo-profile-seeder", default=None)


def seed_test_profile(
    *, label: str, facts: Mapping[str, str] | None = None, complete: bool = True
) -> PortableHumanCliRuntime:
    """Register and join one profile through the test's active :func:`seed_profile` fixture.

    Shared setup helpers that are plain functions reach the same seeder the
    fixture owns, so the profile they register is served by a joined runtime.
    """
    seeder = _CURRENT_SEEDER.get()
    if seeder is None:
        raise AssertionError("request the seed_profile fixture before registering a profile for CLI commands")
    return seeder(label=label, facts=facts, complete=complete)


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

        def seed(
            *, label: str, facts: Mapping[str, str] | None = None, complete: bool = True
        ) -> PortableHumanCliRuntime:
            assert not seeded, f"a profile was already seeded in this test: {seeded}"
            seeded.append(label)
            from .portable_human_cli_runtime import portable_human_cli_runtime

            profile_id = register_cli_profile(label=label, facts=facts, complete=complete, log_in=False)
            runtime = stack.enter_context(
                portable_human_cli_runtime(storage_root=storage_root, profile_id=UUID(profile_id), label=label)
            )
            stack.enter_context(bind_profile_cli(runtime))
            return runtime

        token = _CURRENT_SEEDER.set(seed)
        stack.callback(_CURRENT_SEEDER.reset, token)
        yield seed

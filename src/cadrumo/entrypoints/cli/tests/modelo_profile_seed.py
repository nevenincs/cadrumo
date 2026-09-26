"""Seed the active profile a modelo CLI scenario runs against.

The modelo suites need a complete, selected profile as a precondition; the
credential ceremony that creates one is not their subject. Registering through
the credential door costs two supervised Argon2id derivations plus the login
handover per test (measured at 3.6s of real work), while publishing the same
facts through the minimal capsule door and opening a test bucket session costs
under a second. Each test still gets its own profile in its own storage root.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import pytest

from ....adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root

__all__ = ["ProfileSeeder", "seed_profile"]

type ProfileSeeder = Callable[..., None]


@pytest.fixture
def seed_profile(tmp_path: Path) -> Iterator[ProfileSeeder]:
    """Return a callable that publishes and selects one complete profile.

    The bucket session stays open until the test ends, so every CLI
    invocation after the call sees the profile as active. One call per test.

    The profile identity is fresh per test, as it is through the credential
    door: content-addressed ids downstream derive from it, and a pinned
    identity would make every run render the same ids, turning any
    value-dependent output defect into a constant result for these suites.

    The fixture owns the storage root it publishes into. Seeding selects the
    profile in that root's active pointer, so a root shared with later tests
    in the same worker would leave them resolving a profile whose session
    this fixture has already closed. Entering the per-test root here keeps
    that true whether or not the requesting module also isolates its backend;
    when it does, both resolve to the same ``tmp_path`` root.
    """
    with ExitStack() as stack:
        stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        seeded: list[str] = []

        def seed(*, label: str, facts: Mapping[str, str]) -> None:
            assert not seeded, f"a profile was already seeded in this test: {seeded}"
            seeded.append(label)
            profile_id = str(uuid4())
            stack.enter_context(open_test_profile_session(profile_id))
            register_minimal_profile(profile_id=profile_id, display_name=label, overrides=facts)

        yield seed

"""The shared profile fixtures seal the session they bound once a test ends.

``open_test_profile_session`` unbinds its session on exit without closing it,
which leaves unwrapped key material alive until the garbage collector reaches
the object. Both fixture homes -- the per-test seeded world and the
seed-once-copy-per-test world -- now seal what they bound. The first two cases
capture the session each fixture handed them; the last checks, after both of
those fixtures have been torn down, that each captured session is sealed.

The cases depend on file order, which pytest keeps within a module and which
the suite's ``--dist=loadfile`` keeps on one worker.
"""

from __future__ import annotations

import pytest

from ..master_key.active_session import current_active_bucket_session
from ..master_key.bucket_session import BucketSession
from .active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from .seeded_isolated_backend_fixture import seeded_isolated_backend_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_captured: dict[str, BucketSession] = {}


def _seed_nothing() -> None:
    return None


_active_backend = active_profile_isolated_backend_fixture(autouse=False, name="_active_backend")
_seeded_origin, _seeded_backend = seeded_isolated_backend_fixture(
    seed=_seed_nothing,
    autouse=False,
    name="_seeded_backend",
    origin_name="_seeded_origin",
)
__all__ = ["_active_backend", "_seeded_backend", "_seeded_origin"]


def _capture(label: str) -> None:
    session = current_active_bucket_session()
    assert session is not None, f"the {label} fixture bound no session"
    assert not session.sealed, f"the {label} fixture handed the test a sealed session"
    _captured[label] = session


@pytest.mark.usefixtures("_active_backend")
def test_the_per_test_seeded_world_binds_a_live_session() -> None:
    _capture("per-test")


@pytest.mark.usefixtures("_seeded_backend")
def test_the_copied_seeded_world_binds_a_live_session() -> None:
    _capture("copied")


def test_both_fixtures_sealed_the_session_they_bound() -> None:
    assert set(_captured) == {"per-test", "copied"}, (
        f"the capturing cases did not both run first in this module: {sorted(_captured)}"
    )
    unsealed = sorted(label for label, session in _captured.items() if not session.sealed)
    assert unsealed == [], f"these fixtures left their session unsealed after teardown: {unsealed}"
    assert current_active_bucket_session() is None

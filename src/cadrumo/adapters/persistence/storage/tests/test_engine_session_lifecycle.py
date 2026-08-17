"""Engine lifecycle is owned by the bucket session.

The bucket-session manager is the single owner of the SQLAlchemy engine
lifecycle for bucket-routed storage: the engine is acquired lazily on
first storage access within a session, keyed on bucket identity, and
disposed when the session closes (on idle expiry, profile switch, or
explicit close). These two regressions pin that contract with real
adapters — real bucket provisioning, real SQLite, real sessions, no mocks:

* An in-process profile switch cannot observe the prior bucket's engine:
  re-resolving the earlier bucket after a switch yields a fresh engine,
  never the disposed handle from before the switch.
* Closing a session disposes its engine, observable by pool inspection —
  ``Engine.dispose`` replaces the connection pool, so the pool object the
  session held is no longer the engine's live pool after close.

A regression that unbinds disposal from the session boundary (a stale
engine surviving a switch, or a session close that leaves the engine's
pool live) fails these assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from .....tests.secure_sql import isolated_runtime_profile
from ..master_key import current_active_bucket_session
from ..sql.engine import get_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_A_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_BUCKET_B_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_profile_switch_cannot_observe_prior_bucket_engine(tmp_path: Path) -> None:
    """After a switch, re-resolving the prior bucket yields a fresh engine.

    Opening bucket A acquires an engine on A's session. Exiting A's
    context closes A's session, which disposes and evicts A's engine.
    Opening bucket B is the second half of the in-process switch. Once B
    is active, resolving A's route again must NOT return the engine handle
    from before the switch — that handle was disposed at A's close, so a
    fresh engine is created. The stale-engine window the audit found
    (``persistence-global-engine-lifecycle``) is closed at the boundary.
    """
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"

    with isolated_runtime_profile(tmp_path=root_a, bucket_id=_BUCKET_A_ID) as profile_a:
        engine_a = get_engine(profile_a.settings)
        settings_a = profile_a.settings

    with isolated_runtime_profile(tmp_path=root_b, bucket_id=_BUCKET_B_ID) as profile_b:
        engine_b = get_engine(profile_b.settings)
        # The switch disposed A's engine, so re-resolving A's route builds a
        # fresh engine — the prior handle is unobservable.
        engine_a_after_switch = get_engine(settings_a)
        assert engine_a_after_switch is not engine_a
        # A and B never share an engine handle across the switch.
        assert engine_b is not engine_a


def test_closing_a_session_disposes_its_engine(tmp_path: Path) -> None:
    """Closing the active session disposes the engine it acquired.

    Building the runtime repository acquires the bucket engine on the
    active session and registers the handle there. After a real connection
    is opened against that engine, closing the session disposes it;
    ``Engine.dispose`` replaces the connection pool, so the pool the engine
    held before close is no longer its live pool afterwards.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A_ID) as profile:
        engine = get_engine(profile.settings)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        pool_before_close = engine.pool

        active = current_active_bucket_session()
        assert active is not None
        active.close()

        # Disposal replaces the pool: the pre-close pool is no longer the
        # engine's live pool, the observable signal that close disposed it.
        assert engine.pool is not pool_before_close

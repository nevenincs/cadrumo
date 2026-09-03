"""What the installed workbench is not allowed to do, proven on the real path.

Four invariants, each stated because breaking it would be invisible from the
surface: the shell must hold no repository or service locator, an initial load
must reach no AEAT endpoint, protected taxpayer values must not ride the search
snapshot the palette queries, and a session that stops being live must refuse
rather than keep serving the profile it was bound to.

The composition is the production one over a real encrypted profile. A gate
built on a stand-in projection would prove only that the stand-in behaves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....application.aeat_sync.workspace import AeatSyncWorkspaceAvailability, AeatSyncWorkspaceSource
from ..account import AccountSessionExpiredError
from .workbench_session import WORKBENCH_PROFILE_LABEL, installed_workbench_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_AEAT_SOURCES = frozenset(
    {
        AeatSyncWorkspaceSource.AEAT_CENSUS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
    }
)


@pytest.mark.asyncio
async def test_the_composed_root_holds_no_repository_or_service_locator(tmp_path: Path) -> None:
    """The shell receives projections and factories, never a way to read storage.

    A repository reaching the root is how a frontend quietly acquires
    persistence authority: nothing fails, and every later screen can then read
    whatever it likes. The check is on the composed value's own attributes,
    which is where such a handle would have to sit.
    """
    async with installed_workbench_root(tmp_path) as root:
        for name in root.__dataclass_fields__:
            value = getattr(root, name)
            assert not hasattr(value, "load"), f"{name} exposes a repository-shaped read door to the shell"
            assert not hasattr(value, "save"), f"{name} exposes a repository-shaped write door to the shell"


@pytest.mark.asyncio
async def test_an_initial_load_observes_no_aeat_source(tmp_path: Path) -> None:
    """Opening the workbench must not reach the AEAT.

    Every AEAT authority is NEVER CAPTURED until an explicit pull, which is
    both the decision and the only honest description of a local-only load.
    Reporting one of them as observed would mean the session went to the
    network without the operator asking.
    """
    async with installed_workbench_root(tmp_path) as root:
        inputs = root.search_inputs
        assert inputs is not None
        for zone in inputs.aeat_sync.zones:
            for source in zone.sources:
                if source.source in _AEAT_SOURCES:
                    assert source.availability is AeatSyncWorkspaceAvailability.NEVER_CAPTURED, (
                        f"{zone.zone} claims {source.source} was observed on a local-only load"
                    )
                    assert source.refusal is not None


@pytest.mark.asyncio
async def test_a_never_captured_aeat_source_is_not_reported_as_an_observed_zero(tmp_path: Path) -> None:
    """Never captured and a proven zero must stay distinguishable.

    An item count is what a caller reads to decide there is nothing to act on.
    An unobserved source that reported zero would look exactly like a clean
    reconciliation, which is the under-declaration this product refuses.
    """
    async with installed_workbench_root(tmp_path) as root:
        inputs = root.search_inputs
        assert inputs is not None
        for zone in inputs.aeat_sync.zones:
            for source in zone.sources:
                if source.source in _AEAT_SOURCES:
                    assert source.item_count is None, f"{source.source} reports a count it never observed"
                    assert source.observed_at is None


@pytest.mark.asyncio
async def test_the_search_snapshot_carries_no_profile_identity(tmp_path: Path) -> None:
    """The palette indexes addresses and statuses, never the taxpayer.

    The snapshot is held in memory for the whole session and queried on every
    keystroke, so a protected value reaching it would be exposed far more
    widely than the surface that owns it.
    """
    async with installed_workbench_root(tmp_path) as root:
        inputs = root.search_inputs
        assert inputs is not None
        rendered = repr(inputs.snapshot().documents)

        assert WORKBENCH_PROFILE_LABEL not in rendered, "the search snapshot carries the profile label"


@pytest.mark.asyncio
async def test_a_closed_secure_session_refuses_to_refresh_rather_than_serving_stale_facts(
    tmp_path: Path,
) -> None:
    """Losing the live session must fail closed, not keep answering from before.

    The Home refresh door is the boundary every returning journey crosses, so
    it is where an expired or closed custody session has to be noticed.
    """
    from ....application.user_profile.login_session import logout_active_profile

    async with installed_workbench_root(tmp_path) as root:
        assert root.refresh_home().account.profile_label == WORKBENCH_PROFILE_LABEL
        logout_active_profile()

        with pytest.raises((AccountSessionExpiredError, RuntimeError)):
            root.refresh_home()

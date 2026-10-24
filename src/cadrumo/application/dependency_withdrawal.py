"""Setup items whose acquisition Python no longer performs.

The native component engine owns acquiring, checking and removing the browser
and the local AI. Until a build carries it, each item here only reads what is
already on this computer through its quick check: an item that is not usable
reads ``blocked`` for ``not_in_this_build``, so no surface offers a setup, and
planning or provisioning refuses before any byte moves or any program runs.
Exercising an item (launching the browser, generating with a model,
preflighting hosts) is the engine's, so a registry of these items runs no full
check: it answers a full request with its quick check, and the rows say quick.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, NoReturn

from .dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyFailureCategory,
    DependencyItemChecker,
    DependencyItemDeclaration,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencySetupEvents,
)
from .dependency_transfer import DependencyTransferError
from .provisioning_browser import BrowserInstallerExit, BrowserInstallerRequest, BrowserInstallObserver
from .provisioning_host import RuntimeInstaller

__all__ = [
    "WithdrawnSetupItem",
    "refused_browser_install",
    "refused_browser_launch",
    "refused_build_removal",
    "refused_runtime_install",
    "refused_runtime_spawn",
]


def _refuse() -> NoReturn:
    raise DependencyTransferError(DependencyFailureCategory.NOT_IN_THIS_BUILD, transient=False)


def refused_browser_install(
    request: BrowserInstallerRequest, observer: BrowserInstallObserver, /
) -> BrowserInstallerExit:
    """Stand in for the vendor browser installer, which this build never runs."""
    del request, observer
    _refuse()


async def refused_browser_launch(executable: Path, /, *, timeout_s: float) -> NoReturn:
    """Stand in for the headless browser launch, which only the component engine performs."""
    del executable, timeout_s
    _refuse()


def refused_build_removal(root: Path, directory_names: Sequence[str], /) -> tuple[str, ...]:
    """Stand in for removing browser builds, which only the component engine performs."""
    del root, directory_names
    _refuse()


def refused_runtime_install(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    """Stand in for the local AI program's package-manager install, which this build never runs."""
    del installer, executable, timeout_s
    _refuse()


def refused_runtime_spawn(executable: Path, environment: Mapping[str, str]) -> int:
    """Stand in for starting the local AI program, which only the component engine performs."""
    del executable, environment
    _refuse()


_KEPT: Final = frozenset(
    {DependencyProbeOutcome.PRESENT, DependencyProbeOutcome.DIFFERS, DependencyProbeOutcome.UNREADABLE}
)


class WithdrawnSetupItem:
    """One setup item reduced to its quick check; its setup refuses as not in this build."""

    def __init__(self, item: DependencyItemChecker) -> None:
        """Wrap ``item``, of which only the quick check is ever called."""
        self._item = item

    @property
    def declaration(self) -> DependencyItemDeclaration:
        """The wrapped item's registry declaration."""
        return self._item.declaration

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Read local facts, holding back anything not usable; a full check cannot run and reads unknown."""
        if mode is not DependencyCheckMode.QUICK:
            return DependencyProbeReading(
                item_id=self.declaration.item_id, mode=mode, outcome=DependencyProbeOutcome.UNREADABLE
            )
        reading = await self._item.check(DependencyCheckMode.QUICK)
        if reading.outcome in _KEPT or reading.blocked_reason is DependencyBlockedReason.HARDWARE:
            return reading
        return DependencyProbeReading(
            item_id=reading.item_id,
            mode=mode,
            outcome=DependencyProbeOutcome.BLOCKED,
            blocked_reason=DependencyBlockedReason.NOT_IN_THIS_BUILD,
            facts=reading.facts,
        )

    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        """Refuse: there is nothing this build can set up."""
        del model_name
        _refuse()

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Refuse without writing anything, even for a plan approved before this build."""
        del events
        return DependencyProvisionResult(
            item_id=entry.item_id, changed=False, failure_category=DependencyFailureCategory.NOT_IN_THIS_BUILD
        )

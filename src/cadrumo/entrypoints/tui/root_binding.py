"""Immutable presentation and doors for one authenticated TUI root."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ...application.overview.home import HomeAccountSession, HomeProjectionV1
from .account import AccountFactoriesV1, AccountSessionReaderV1
from .navigation import TuiDestinationCatalogueV1, TuiNavigationTargetV1
from .search import WorkbenchSearchDoorV1


@dataclass(frozen=True, slots=True)
class RootPresentationV1:
    """One captured Home and its matching destination, search, and account doors."""

    home: HomeProjectionV1
    destination_catalogue: TuiDestinationCatalogueV1
    workbench_search_service: WorkbenchSearchDoorV1 | None
    account_factories: AccountFactoriesV1


type HomeRefreshDoorV1 = Callable[[], HomeProjectionV1 | RootPresentationV1]
type WorkbenchSearchRefreshDoorV1 = Callable[[], WorkbenchSearchDoorV1]
type DestinationCatalogueRefreshDoorV1 = Callable[[], TuiDestinationCatalogueV1]


@dataclass(frozen=True, slots=True)
class RootBindingV1:
    """Every door the root needs for one authenticated session, built off the loop."""

    destination_catalogue: TuiDestinationCatalogueV1
    refresh_home: HomeRefreshDoorV1
    workbench_search_service: WorkbenchSearchDoorV1 | None
    refresh_workbench_search: WorkbenchSearchRefreshDoorV1 | None
    refresh_destination_catalogue: DestinationCatalogueRefreshDoorV1 | None
    account_factories: AccountFactoriesV1
    read_account_session: AccountSessionReaderV1 | None
    initial_destination: TuiNavigationTargetV1 | None = None
    initial_account_session: HomeAccountSession | None = None
    note_activity: Callable[[], Awaitable[None]] | None = None


type RootLoaderV1 = Callable[[], RootBindingV1]

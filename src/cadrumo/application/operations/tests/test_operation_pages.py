"""Each registered operation names the workspace page where the person sees its records."""

from __future__ import annotations

from typing import get_args

import pytest

from cadrumo_client.contracts.presentation import PresentationDestination

from ..contract_manifest import load_operation_contract_manifest
from ..operation_pages import operation_destination

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FAMILY_PAGES = {
    "ledger": "ledger",
    "live": "aeat_sync",
    "user-profile": "profile",
    "auth": "aeat_auth",
    "overview": "home",
    "export": "declarations",
    "dependencies": "setup",
    "local-reader": "setup",
}
_EXCEPTIONS = {
    "modelo.aggregate.capture_received_invoice_retencion": "withholding",
    "modelo.reconcile.pull": "aeat_sync",
    "modelo.reconcile.import": "aeat_sync",
}


def _registered() -> tuple[str, ...]:
    return tuple(entry.contract.definition_id for entry in load_operation_contract_manifest().operations)


def test_every_registered_family_has_a_decided_page() -> None:
    # A new family must be given a page, or be named here as one no page shows.
    pageless = {"app", "config", "diagnostics", "profile", "workbench", "workflow"}
    pages = set(get_args(PresentationDestination.__value__))
    for definition_id in _registered():
        family = definition_id.split(".", 1)[0]
        assert family in _FAMILY_PAGES or family == "modelo" or family in pageless, definition_id
        page = operation_destination(definition_id)
        if family in pageless:
            assert page is None, definition_id
        elif family != "modelo":
            assert page == _FAMILY_PAGES[family], definition_id
        assert page is None or page in pages, definition_id


def test_bookkeeping_profile_and_declaration_writes_open_their_pages() -> None:
    registered = set(_registered())
    for definition_id, page in {
        "ledger.add": "ledger",
        "ledger.classify.bulk": "ledger",
        "user-profile.patch": "profile",
        "modelo.work.calculate": "declarations",
        "modelo.export": "declarations",
        "live.notifications.capture": "aeat_sync",
        **_EXCEPTIONS,
    }.items():
        assert definition_id in registered, definition_id
        assert operation_destination(definition_id) == page, definition_id


def test_operations_no_page_shows_name_none() -> None:
    for definition_id in ("workflow.run.read", "diagnostics.read", "config.google.status", "app.review.queue"):
        assert operation_destination(definition_id) is None, definition_id

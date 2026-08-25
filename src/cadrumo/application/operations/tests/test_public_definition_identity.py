"""Canonical-definition receipts for public operation contracts."""

from __future__ import annotations

from types import ModuleType

import pytest

from .. import (
    capabilities,
    composition,
    errors,
    event_replay,
    events,
    frontend_contracts,
    interactions,
    models,
    observation,
    owner,
    projection_services,
    registry,
    secret_submission,
    supervisor,
)
from ..persistence import events as persistence_events
from ..persistence import idempotency as persistence_idempotency
from ..persistence import journal as persistence_journal
from ..persistence import leases as persistence_leases
from ..persistence import replay as persistence_replay

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = (
    capabilities,
    composition,
    errors,
    event_replay,
    events,
    frontend_contracts,
    interactions,
    models,
    observation,
    owner,
    persistence_events,
    persistence_idempotency,
    persistence_journal,
    persistence_leases,
    persistence_replay,
    registry,
    secret_submission,
    projection_services,
    supervisor,
)


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_operation_export_has_runtime_identity_at_its_defining_module(module: ModuleType) -> None:
    assert module.__all__
    foreign_exports = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in module.__all__
        if getattr(getattr(module, name), "__module__", None) != module.__name__
    }
    assert foreign_exports == {}

"""Canonical-definition receipts for public operation contracts."""

from __future__ import annotations

from types import ModuleType

import pytest

import cadrumo.application.operations.capabilities as capabilities
import cadrumo.application.operations.composition as composition
import cadrumo.application.operations.errors as errors
import cadrumo.application.operations.event_replay as event_replay
import cadrumo.application.operations.events as events
import cadrumo.application.operations.frontend_contracts as frontend_contracts
import cadrumo.application.operations.interactions as interactions
import cadrumo.application.operations.models as models
import cadrumo.application.operations.observation as observation
import cadrumo.application.operations.owner as owner
import cadrumo.application.operations.persistence.events as persistence_events
import cadrumo.application.operations.persistence.idempotency as persistence_idempotency
import cadrumo.application.operations.persistence.journal as persistence_journal
import cadrumo.application.operations.persistence.leases as persistence_leases
import cadrumo.application.operations.persistence.replay as persistence_replay
import cadrumo.application.operations.projection_services as projection_services
import cadrumo.application.operations.registry as registry
import cadrumo.application.operations.secret_submission as secret_submission
import cadrumo.application.operations.supervisor as supervisor

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

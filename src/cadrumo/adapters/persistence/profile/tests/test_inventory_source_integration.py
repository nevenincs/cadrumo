"""Encrypted inventory integration for the application source resolver."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from .....application.aggregation.inventory import InventorySourceResolver
from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.aggregation.tests.test_inventory_source import inventory_ledger
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.casilla_membership import casillas_by_id
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ...storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ...storage.sql.engine import get_engine
from ...storage.sql.orm import SecureObjectRow
from ...storage.tests.secure_sql import (
    TestRuntimeProfile,
    mutate_encrypted_secure_object_json,
)
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..inventory import InventoryLedgerRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "00000000-0000-4000-8000-000000000176"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _revision() -> ModeloRevision:
    return published_authority_operation().snapshot("100", filing_year=2025, period="0A").revision


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=revision,
    )


def test_real_encrypted_multi_activity_success_absence_conflict_and_corruption(
    runtime_profile: TestRuntimeProfile,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = InventoryLedgerRepository(objects=runtime_profile.repository)
    revision = _revision()
    absent = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision))
    alpha = inventory_ledger("alpha", physical_closing=Decimal("250.00"))
    zeta = inventory_ledger("zeta")
    repository.save(InventoryLedgerDocument(ledgers=(zeta, alpha)))
    complete = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision))

    statement = select(SecureObjectRow).where(
        SecureObjectRow.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
        SecureObjectRow.object_key == PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
    )

    def orphan_authority(document: dict[str, Any]) -> None:
        ledgers = document["ledgers"]
        assert isinstance(ledgers, list) and isinstance(ledgers[0], dict)
        assert "zeta" in repr(ledgers)
        ledgers[0]["closing_authority_record"]["decision"]["actividad_id"] = "other"

    mutate_encrypted_secure_object_json(
        get_engine(runtime_profile.settings),
        row_statement=statement,
        mutate=orphan_authority,
    )
    corrupted = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision))

    assert absent.row_binding_values == {}
    assert absent.diagnostics[0].reason == "source_domain_not_ready"
    # Casilla 0181 names the binding it is fed through; the test reads that
    # declaration rather than restating the binding's identifier.
    acquisition_binding = casillas_by_id(revision)[validated_casilla_id("0181")].binding
    assert acquisition_binding is not None
    assert complete.row_binding_values[(acquisition_binding, 1)] == Decimal("100.00")
    assert complete.row_source_identities[(acquisition_binding, 1)].source_row_identity == "alpha"
    assert complete.diagnostics[0].reason == "source_issue"
    assert corrupted.row_binding_values == {}
    assert corrupted.diagnostics[0].reason == "storage_degraded"
    rendered = f"{corrupted!r} {corrupted.model_dump()!r} {caplog.text}"
    for canary in ("alpha", "zeta", "250.00", "reviewer-secret", "inventory-secret-command", "a" * 64):
        assert canary not in rendered

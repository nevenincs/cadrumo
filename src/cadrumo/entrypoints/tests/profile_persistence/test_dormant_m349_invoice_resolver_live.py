"""Live M349 invoice resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports
from cadrumo.entrypoints.tests.modelo_349_invoice_facts import (
    M349_EXPECTED_IMPORTE,
    M349_EXPECTED_OPERADORES,
    M349_INVOICES,
    intra_community_invoice,
)
from cadrumo.entrypoints.tests.profile_persistence._dormant_resolver_live_support import (
    _T0,
    _T1,
    _revision,
    _seed_ready_profile,
)

pytestmark = [pytest.mark.hex_entrypoint]

# Chain 3 — M349 invoices (m349_intracommunity_operation): PROVEN LIVE
# ---------------------------------------------------------------------------

_M349_BUCKET = "34900000-0000-4000-8000-000000000013"
_M349_REVISION = "2020-y-siguientes"
_M349_YEAR = 2026
_M349_IMPORTE_CASILLA: CasillaId = validated_casilla_id("decl.importe-operaciones")
_M349_IMPORTE_BINDING = "iva-349-declarante-importe-operaciones"
_M349_OPERADORES_CASILLA: CasillaId = validated_casilla_id("decl.numero-operadores")


@pytest.fixture
def m349_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M349_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M349_BUCKET)
        yield profile.repository


@pytest.fixture
def m349_calculated(
    m349_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> tuple[WorkUnit, CalculationRevision]:
    """E2E: real seeded intra-community invoices fold into M349 on the live path.

    Seeds three DISTINCT ISSUED INTRA_COMMUNITY_SUPPLY invoices (clave E) in 1T,
    then runs the live bucket-aggregation calculate. casilla
    decl.importe-operaciones must equal the summed bases and
    decl.numero-operadores must count the three distinct operators — proving the
    enrolled InvoiceCatalogueSourceResolver folds the real encrypted invoice
    catalogue through to the bound casillas.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=m349_objects)
    CalculationRevisionCatalogueRepository(objects=m349_objects)
    TransactionCatalogueRepository(bucket_id=_M349_BUCKET, objects=m349_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m349_objects)

    invoices = tuple(
        intra_community_invoice(
            bucket_id=_M349_BUCKET,
            invoice_number=number,
            counterparty_country=country,
            counterparty_tax_id=tax_id,
            issued_at=issued_at,
            base_total=base_total,
        )
        for number, country, tax_id, issued_at, base_total in M349_INVOICES
    )
    invoice_repo.save(build_invoice_catalogue(invoices))

    # Non-vacuity: the casilla under test binds the invoice source, and the seeded
    # bases are distinct so a copy/contamination cannot satisfy the sum.
    revision = _revision("349", _M349_REVISION)
    importe_casilla = next(c for c in revision.casillas if c.id == _M349_IMPORTE_CASILLA)
    assert importe_casilla.binding == _M349_IMPORTE_BINDING
    assert any(
        str(b.source) == "m349_intracommunity_operation" and b.id == _M349_IMPORTE_BINDING for b in revision.bindings
    )
    assert len({base for *_, base in M349_INVOICES}) == 3

    work_unit = create_work_unit(
        bucket_id=_M349_BUCKET,
        modelo="349",
        filing_year=_M349_YEAR,
        period=Period.from_year_and_code(_M349_YEAR, "1T"),
        revision_id=_M349_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m349_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_M349_BUCKET, operation=operation),
            clock=_T1,
        )

    assert isinstance(result, BucketAggregationCalculationResult)
    folded_importe = Decimal(result.revision.casilla_values[_M349_IMPORTE_CASILLA])
    assert folded_importe == M349_EXPECTED_IMPORTE, (
        f"M349 {_M349_IMPORTE_CASILLA} must fold the three seeded invoice bases "
        f"(sum {M349_EXPECTED_IMPORTE}); got {folded_importe}"
    )
    folded_operadores = Decimal(result.revision.casilla_values[_M349_OPERADORES_CASILLA])
    assert folded_operadores == M349_EXPECTED_OPERADORES, (
        f"M349 {_M349_OPERADORES_CASILLA} must count the three distinct operators; got {folded_operadores}"
    )
    # The invoice source is CLAIMED (resolver enrolled): no unhandled advisory.
    assert not any(
        diag.source_kind in {"collectible_invoice", "payable_invoice", "m349_intracommunity_operation"}
        and diag.reason in {"unhandled_binding_source", "terminal_origin_mismatch"}
        for diag in result.source_diagnostics
    )
    return work_unit, result.revision


@pytest.mark.unit
def test_m349_importe_operaciones_folds_seeded_invoices_on_live_calculate(
    m349_calculated: tuple[WorkUnit, CalculationRevision],
) -> None:
    _, revision = m349_calculated
    assert revision.casilla_values[_M349_IMPORTE_CASILLA] == M349_EXPECTED_IMPORTE
    assert len(revision.detail_rows) == 3

"""The calculate service keeps its caller's registry lease through publication."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_modelo_ready_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo import calculation_actions
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.calculation_advisory_projection import ModeloCalculationAdvisories
from cadrumo.application.modelo.calculation_projection import ModeloCalculationSnapshot
from cadrumo.application.modelo.calculation_publication import CalculationRevisionPublication
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority, bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.cross_period_seeding import resolved_revision

from ..adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "91df36b5-544e-45eb-835a-7ec1112988e1"
_FIRST_QUARTER_BINDINGS = {
    "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    "modelo-130-resultados-negativos-anteriores": Decimal("0"),
    "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
}


def test_bucket_calculation_reuses_caller_authority_and_returns_writer_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness, source, advisory, and result phases keep one authority lease."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile_record(_PROFILE_ID, clock=datetime(2026, 8, 24, tzinfo=UTC))
        with bundled_indexed_authority().operation() as operation:
            revision = resolved_revision(modelo="130", filing_year=2025, period="1T")
            unit = create_work_unit(
                bucket_id=_PROFILE_ID,
                modelo="130",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "1T"),
                revision_id=revision.id,
                actor="authority-binding-test",
                ports=build_work_lifecycle_ports(bucket_id=_PROFILE_ID),
                operation=operation,
            )
            ports = build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation)
            inputs = WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values=_FIRST_QUARTER_BINDINGS,
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            )

            def unexpected_authority(_authority: IndexedRegistryAuthority) -> None:
                raise AssertionError("calculation opened another registry authority")

            def unexpected_post_write_load(_repository: object) -> None:
                raise AssertionError("calculation reloaded its publication after the writer returned")

            persisted = calculation_actions.persist_calculation_revision

            with monkeypatch.context() as patch:

                def persist_then_close_catalogues(*args: Any, **kwargs: Any) -> CalculationRevisionPublication:
                    publication = persisted(*args, **kwargs)
                    patch.setattr(WorkUnitCatalogueRepository, "load", unexpected_post_write_load)
                    patch.setattr(CalculationRevisionCatalogueRepository, "load", unexpected_post_write_load)
                    return publication

                patch.setattr(IndexedRegistryAuthority, "operation", unexpected_authority)
                patch.setattr(calculation_actions, "persist_calculation_revision", persist_then_close_catalogues)
                result = calculate_modelo_work_revision(
                    work_unit_id=unit.work_unit_id,
                    ports=ports,
                    actor="authority-binding-test",
                    inputs=inputs,
                )
                snapshot = ModeloCalculationSnapshot.from_revision(
                    result.revision, work_unit=result.work_unit, operation=operation
                )
                advisories = ModeloCalculationAdvisories.from_result(result, operation=operation)

            assert result.revision.calculation_revision_id == snapshot.calculation_revision_id
            assert result.work_unit.work_unit_id == unit.work_unit_id
            assert result.revision_published
            assert advisories.to_diagnostics() == result.source_diagnostics

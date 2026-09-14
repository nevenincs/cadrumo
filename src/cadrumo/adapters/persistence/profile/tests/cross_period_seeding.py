"""Persistence-backed cross-period source seeding for outer integration tests.

The source chain is intentionally materialised through the application
workflow and encrypted profile repositories.  Registry-derived grouping and
values are owned by the domain test support; this module owns only the writes
and their adapter bindings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.external_import_actions import import_external_filing_evidence
from cadrumo.adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.cross_period_seeding import (
    cross_period_source_groups,
    resolved_revision,
    source_casilla_values,
)
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind

if TYPE_CHECKING:
    from cadrumo.domain.modelos.work_unit import WorkUnit


SEED_CLOCK = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
"""The fixed instant every seeded source is stamped with.

Clock-free identity is a contract elsewhere, so a seeded chain must not vary
run to run: a wall-clock stamp would make two identical seedings produce
different records and turn an idempotency proof into a coin flip.
"""

SEEDED_SOURCE_TAX_ID: Final = "X1234567L"
"""The taxpayer identity every seeded cross-period source is filed under.

The clean-state gate compares the seeded evidence's ``authenticated_identity``
against the active profile tax id.  A caller aligns its profile to this value
so a seeding test exercises the cross-period behavior instead of an unrelated
identity mismatch.
"""


def seed_clean_cross_period_sources(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
) -> None:
    """Materialise every declared cross-period source through real adapters.

    Each source is filed through the real external-import door and then
    recorded as an ``aeat_sede_justificante`` observation, which is what the
    cross-period clean-state gate requires: a locally-produced source kind
    would not satisfy it, and stamping one that does without the filing behind
    it would prove the gate passes on evidence no operator has.
    """
    groups = cross_period_source_groups(work_unit)
    if not groups:
        return
    observation_repository = CalculationObservationRepository()
    filing_catalogue = filing_repository.load()
    lifecycle_ports = WorkLifecyclePorts(
        work_unit_repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
    )
    for (source_modelo, filing_year, period), source_casilla_ids in sorted(groups.items()):
        source_period = Period.from_year_and_code(filing_year, period)
        source_revision = resolved_revision(modelo=source_modelo, filing_year=filing_year, period=period)
        values = source_casilla_values(source_casilla_ids)
        current = filing_catalogue.current_for(
            bucket_id=work_unit.bucket_id,
            modelo=source_modelo,
            filing_year=filing_year,
            period=source_period,
        )
        evidence_reference_id = f"CSV{source_modelo}{filing_year}{period}".upper()
        if current is None:
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                captured_at=SEED_CLOCK,
            )
            source_work_unit = create_work_unit(
                bucket_id=work_unit.bucket_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=source_period,
                revision_id=source_revision.id,
                ports=lifecycle_ports,
                clock=SEED_CLOCK,
            )
            import_external_filing_evidence(
                work_unit_id=source_work_unit.work_unit_id,
                casilla_values=values,
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id=evidence_reference_id,
                actor="aeat-import-test",
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
                bucket_event_repository=bucket_event_repository,
                observation_repository=observation_repository,
                expected_tax_id=SEEDED_SOURCE_TAX_ID,
                clock=SEED_CLOCK,
            )
            filing_catalogue = filing_repository.load()
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo=source_modelo,
                    filing_year=filing_year,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo=source_modelo,
                        filing_year=filing_year,
                        period=period,
                        casilla_values=values,
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=SEED_CLOCK,
                stamped_revision_id=source_revision.id,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": f"EXP-{source_modelo}-{filing_year}-{period}",
                    "aeat_justificante_csv": evidence_reference_id,
                    "authenticated_identity": SEEDED_SOURCE_TAX_ID,
                },
            ),
        )


__all__ = ["SEED_CLOCK", "SEEDED_SOURCE_TAX_ID", "seed_clean_cross_period_sources"]

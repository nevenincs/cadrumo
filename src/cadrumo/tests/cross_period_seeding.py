"""Seed the clean cross-period source chain a target work unit depends on.

A modelo whose revision declares previous-filing or relation sources cannot
reach a clean cross-period state until those sources exist as filed,
officially-evidenced observations. Building that chain by hand is the same
forty lines in every suite that needs it, so it lives here once.

This is shared test support rather than package-internal support: the
conformance surfaces under :mod:`cadrumo.entrypoints` need the same chain
as the application-layer suites, and reaching into another package's
``tests`` directory for it is the cross-package private import the
architecture rules reject.

Everything here writes through real production doors -- ``create_work_unit``,
``import_external_filing_evidence`` and the observation repository -- so a
seeded chain is indistinguishable from one an operator produced. Nothing is
faked, because a fixture that fabricates the chain would prove the consumer
works against a state no filing can reach.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..application.calculations import CalculationObservationRepository
from ..application.modelo.external_import_actions import import_external_filing_evidence
from ..application.modelo.tests.justificante_metadata import persist_justificante_metadata
from ..application.modelo.work_lifecycle import create_work_unit
from ..core import CasillaId, Period
from ..domain.calculations.registry.bindings import RegistryModeloObservation
from ..domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ..domain.calculations.registry.relations import relation_source_requirements
from ..domain.calculations.registry.temporal import select_revision
from ..domain.modelos.filing_record import ExternalEvidenceKind
from .registry_observations import registry_grounded_observations
from .registry_tree import bundled_registry_tree

if TYPE_CHECKING:
    from ..domain.calculations.registry.schema import ModeloRevision
    from ..domain.modelos.work_unit import WorkUnit

SEED_CLOCK = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
"""The fixed instant every seeded source is stamped with.

Clock-free identity is a contract elsewhere, so a seeded chain must not vary
run to run: a wall-clock stamp would make two identical seedings produce
different records and turn an idempotency proof into a coin flip.
"""


def resolved_revision(*, modelo: str, filing_year: int, period: str) -> ModeloRevision:
    """Resolve a law-determined revision without touching the tree-wide authority.

    ``load_registry_tree`` compiles the tree without validating it, and
    ``select_revision`` is a pure function with no validation of its own -- this
    works for any modelo, layout-bearing or not, unlike
    ``bundled_authority()``, whose ``.load()`` validates the entire
    registry tree and currently refuses unconditionally as a result.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return select_revision(modelo_definition, filing_year=filing_year, period=period)


def cross_period_source_groups(work_unit: WorkUnit) -> dict[tuple[str, int, str], set[CasillaId]]:
    """Group every declared cross-period source by its own filing coordinates."""
    revision = resolved_revision(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    groups: dict[tuple[str, int, str], set[CasillaId]] = {}
    for requirement in previous_filing_observation_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        groups.setdefault(
            (requirement.source_modelo, requirement.filing_year, requirement.periods[0]),
            set(),
        ).update(requirement.source_casilla_ids)
    for requirement in relation_source_requirements(
        revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ):
        for period in requirement.periods:
            groups.setdefault(
                (requirement.source_modelo, requirement.filing_year, period),
                set(),
            ).update(requirement.source_casilla_ids)
    return groups


def source_casilla_values(source_casilla_ids: set[CasillaId]) -> dict[CasillaId, Decimal]:
    """Give each source casilla a distinct, deterministic non-zero value."""
    return {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casilla_ids))}


def seed_clean_cross_period_sources(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
) -> None:
    """Materialise every cross-period source the work unit's revision declares.

    Each source is filed through the real external-import door and then
    recorded as an ``aeat_sede_justificante`` observation, which is what the
    cross-period clean-state gate requires: a locally-produced source kind
    would not satisfy it, and stamping one that does without the filing
    behind it would prove the gate passes on evidence no operator has.
    """
    groups = cross_period_source_groups(work_unit)
    if not groups:
        return
    observation_repository = CalculationObservationRepository()
    filing_catalogue = filing_repository.load()
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
                repository=work_unit_repository,
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
                expected_tax_id="X1234567L",
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
                    "authenticated_identity": "X1234567L",
                },
            )
        )

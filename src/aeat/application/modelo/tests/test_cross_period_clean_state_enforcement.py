"""Filing-grade Modelo gates for cross-period clean-state proof."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.deadlines import CrossPeriodGroupMemberRoster, IVARegime, TaxpayerProfile
from ....domain.filing import ModeloDraftError
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    ExternalEvidenceKind,
    ModeloVerificationFindingKind,
    derive_calculation_revision_id,
    upsert_calculation_revision,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
    cross_period_dependency_requirements,
)
from .. import (
    ModeloCrossPeriodCleanStateError,
    ModeloExportCommand,
    create_work_unit,
    export_modelo_revision,
    file_modelo_revision,
    import_external_filing_evidence,
    verify_modelo_revision,
)
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _seed_verified_revision(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
) -> str:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=snapshot.revision.id,
        clock=_CLOCK,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="operator-test",
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision_id


def _seed_draft_revision(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
) -> str:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=snapshot.revision.id,
        clock=_CLOCK,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision_id


def test_export_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-export") as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision_id,
                    output_path=tmp_path / "modelo-390.txt",
                    actor="operator-test",
                ),
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_file_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-file") as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    (
        ("390", 2025, "0A"),
        ("180", 2026, "0A"),
        ("190", 2026, "0A"),
        ("193", 2026, "0A"),
        ("100", 2025, "0A"),
        ("202", 2026, "2P"),
        ("200", 2026, "0A"),
    ),
)
def test_file_refuses_declared_cross_period_modelos_without_clean_sources(
    tmp_path: Path,
    modelo: str,
    filing_year: int,
    period: str,
) -> None:
    bucket_id = f"cross-period-{modelo}-{period}".lower()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_verify_modelo_303_reports_clean_state_blocker_for_carry_forward_dependency(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-303") as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="303",
            filing_year=2026,
            period="2T",
        )

        report = verify_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(),
            clock=_CLOCK,
        )

    assert any(
        finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        and "modelo=303" in finding.message
        for finding in report.findings
    )


def test_export_modelo_390_passes_clean_state_with_imported_bound_justificantes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-390-imported") as profile:
        target_snapshot = resources().modelos.authority.snapshot("390", filing_year=2025, period="0A")
        observations = CalculationObservationRepository()
        requirements_by_source: dict[tuple[str, int, str], set[str]] = {}
        for requirement in cross_period_dependency_requirements(target_snapshot):
            requirements_by_source.setdefault(
                (requirement.source_modelo, requirement.filing_year, requirement.period),
                set(),
            ).update(requirement.source_casillas)

        for (source_modelo, filing_year, period), source_casillas in sorted(requirements_by_source.items()):
            source_snapshot = resources().modelos.authority.snapshot(
                source_modelo,
                filing_year=filing_year,
                period=period,
            )
            source_work_unit = create_work_unit(
                bucket_id=profile.bucket_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=Period.from_year_and_code(filing_year, period),
                revision_id=source_snapshot.revision.id,
                clock=_CLOCK,
            )
            casilla_values = {
                casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casillas))
            }
            evidence_reference_id = f"JUST-{source_modelo}-{filing_year}-{period}"
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=source_modelo,
                filing_year=filing_year,
                period=period,
                captured_at=_CLOCK,
            )
            import_external_filing_evidence(
                work_unit_id=source_work_unit.work_unit_id,
                casilla_values=casilla_values,
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id=evidence_reference_id,
                actor="aeat-import-test",
                expected_tax_id="X1234567L",
                clock=_CLOCK,
            )
            observations.save_observation(
                RegistryModeloObservation(
                    modelo=source_modelo,
                    filing_year=filing_year,
                    period=period,
                    observations=tuple(
                        CasillaObservation(casilla_id=casilla_id, value=value)
                        for casilla_id, value in casilla_values.items()
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_CLOCK,
            )

        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloDraftError):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision_id,
                    output_path=tmp_path / "modelo-390.txt",
                    actor="operator-test",
                ),
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )


def test_file_refuses_modelo_353_when_expected_member_roster_is_incomplete(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-353") as profile:
        snapshot = resources().modelos.authority.snapshot("353", filing_year=2026, period="12")
        requirement = next(
            item for item in cross_period_dependency_requirements(snapshot) if item.requires_member_fan_in
        )
        CalculationObservationRepository().save_observation(
            RegistryModeloObservation(
                modelo="322",
                filing_year=2026,
                period="12",
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=Decimal(index + 1))
                    for index, casilla_id in enumerate(requirement.source_casillas)
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            member_nif="A00000000",
        )
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="353",
            filing_year=2026,
            period="12",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                cross_period_expected_member_sets=(
                    CrossPeriodExpectedMemberSet(
                        source_modelo="322",
                        filing_year=2026,
                        period="12",
                        member_nifs=("A00000000", "B00000001"),
                    ),
                ),
                clock=_CLOCK,
            )

    message = str(exc_info.value)
    assert "incomplete_group_member_coverage" in message
    assert "missing_expected_group_member_roster" not in message


def test_file_uses_profile_group_roster_for_modelo_353_member_fan_in(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-353-profile-roster") as profile:
        snapshot = resources().modelos.authority.snapshot("353", filing_year=2026, period="12")
        requirement = next(
            item for item in cross_period_dependency_requirements(snapshot) if item.requires_member_fan_in
        )
        CalculationObservationRepository().save_observation(
            RegistryModeloObservation(
                modelo="322",
                filing_year=2026,
                period="12",
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=Decimal(index + 1))
                    for index, casilla_id in enumerate(requirement.source_casillas)
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CLOCK,
            member_nif="A00000000",
        )
        revision_id = _seed_verified_revision(
            bucket_id=profile.bucket_id,
            modelo="353",
            filing_year=2026,
            period="12",
        )
        workflow_profile = _workflow_profile().model_copy(
            update={
                "cross_period_group_member_rosters": (
                    CrossPeriodGroupMemberRoster(
                        source_modelo="322",
                        filing_year=2026,
                        period="12",
                        member_nifs=("A00000000", "B00000001"),
                    ),
                ),
            },
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                clock=_CLOCK,
            )

    message = str(exc_info.value)
    assert "incomplete_group_member_coverage" in message
    assert "missing_expected_group_member_roster" not in message

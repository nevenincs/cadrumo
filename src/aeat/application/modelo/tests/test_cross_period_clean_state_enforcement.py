"""Filing-grade Modelo gates for cross-period clean-state proof."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, Period
from ....core.resources import resources
from ....domain.calculations.registry import RegistryModeloObservation
from ....domain.deadlines import CrossPeriodGroupMemberRoster, IrpfIncomeCategory, IVARegime, TaxpayerProfile
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
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
    NoPriorObligationProvenanceKind,
    cross_period_dependency_requirements,
)
from ...calculations._cross_period_clean_state import _OFFICIAL_SOURCE_KINDS
from .. import (
    APP_FILING_SOURCE_KIND,
    ModeloCrossPeriodCleanStateError,
    ModeloExportCommand,
    create_work_unit,
    export_modelo_revision,
    file_modelo_revision,
    import_external_filing_evidence,
    mark_revision_verificado_completo,
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
        input_values_by_casilla_id={},
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
        input_values_by_casilla_id={},
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


def test_direct_mark_verified_refuses_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-mark") as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="390",
            filing_year=2025,
            period="0A",
        )

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            mark_revision_verificado_completo(
                revision_id,
                actor="operator-test",
                clock=_CLOCK,
            )

        stored = CalculationRevisionCatalogueRepository().load().revisions[revision_id]

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
    assert stored.state is CalculationRevisionState.BORRADOR
    assert stored.verified_at is None
    assert stored.verified_by is None


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


def test_verify_salaried_taxpayer_m100_has_no_cross_period_withholding_block(tmp_path: Path) -> None:
    """C3 end-to-end: a declared employee's Modelo 100 verify reports NO cross-period dependency block.

    The empty-profile [100, 2025, 0A] file case above raises ModeloCrossPeriodCleanStateError
    (130/131 fail-closed enforced). A profile declaring TRABAJO income (no actividad económica)
    scopes every withholding/pagos dependency (111/115/123/130/131/180/184/190/193) out as
    not-applicable, so the salaried filer's M100 carries no CROSS_PERIOD_DEPENDENCY_UNCLEAN finding.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="c3-salaried-m100") as profile:
        revision_id = _seed_draft_revision(
            bucket_id=profile.bucket_id,
            modelo="100",
            filing_year=2025,
            period="0A",
        )
        salaried = _workflow_profile().model_copy(
            update={"irpf_income_categories": frozenset({IrpfIncomeCategory.TRABAJO})},
        )
        report = verify_modelo_revision(
            revision_id,
            actor="operator-test",
            workflow_profile=salaried,
            clock=_CLOCK,
        )

    withholding_pagos = {"111", "115", "123", "130", "131", "180", "184", "190", "193"}
    blocked = {
        modelo
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        for modelo in withholding_pagos
        if f"modelo={modelo}" in finding.message
    }
    # The M100->M100 prior-year self-carry is a separate first-filer concern, not a withholding dep.
    assert not blocked, f"salaried M100 must not be cross-period-blocked on withholding/pagos deps, got {blocked}"


def test_export_modelo_390_passes_clean_state_with_imported_bound_justificantes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-390-imported") as profile:
        target_snapshot = resources().modelos.authority.snapshot("390", filing_year=2025, period="0A")
        observations = CalculationObservationRepository()
        requirements_by_source: dict[tuple[str, int, str], set[CasillaId]] = {}
        for requirement in cross_period_dependency_requirements(target_snapshot):
            requirements_by_source.setdefault(
                (requirement.source_modelo, requirement.filing_year, requirement.period.registry_token),
                set(),
            ).update(requirement.source_casilla_ids)

        for (source_modelo, filing_year, period), source_casilla_ids in sorted(requirements_by_source.items()):
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
                casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(sorted(source_casilla_ids))
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
                    observations=registry_grounded_observations(
                        modelo=source_modelo,
                        filing_year=filing_year,
                        period=period,
                        casilla_values=casilla_values,
                    ),
                ),
                source_kind="aeat_sede_justificante",
                captured_at=_CLOCK,
                stamped_revision_id=source_snapshot.revision.id,
                source_metadata={
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": f"EXP-{source_modelo}-{filing_year}-{period}",
                    "aeat_justificante_csv": evidence_reference_id,
                    "authenticated_identity": "X1234567L",
                },
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
                observations=registry_grounded_observations(
                    modelo="322",
                    filing_year=2026,
                    period="12",
                    casilla_values={
                        casilla_id: Decimal(index + 1)
                        for index, casilla_id in enumerate(requirement.source_casilla_ids)
                    },
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
                        period=Period.from_year_and_code(2026, "12"),
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
                observations=registry_grounded_observations(
                    modelo="322",
                    filing_year=2026,
                    period="12",
                    casilla_values={
                        casilla_id: Decimal(index + 1)
                        for index, casilla_id in enumerate(requirement.source_casilla_ids)
                    },
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
                        period=Period.from_year_and_code(2026, "12"),
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


def test_no_prior_obligation_provenance_never_enters_official_source_kinds() -> None:
    """Honesty: pre-activity suppression provenance is never official.

    The no-prior-obligation facet records a SUPPRESSION (no obligation existed),
    not a filing's AEAT evidence. None of its enum values - the facet
    discriminator, the operator-declared provenance, or the censo-corroborated
    provenance - may ever be a member of ``_OFFICIAL_SOURCE_KINDS``. Were any
    admitted, an unevidenced pre-activity scoping could masquerade as official
    AEAT evidence and launder a dependent filing past the evidence gate.
    """
    for kind in NoPriorObligationProvenanceKind:
        assert kind.value not in _OFFICIAL_SOURCE_KINDS
    assert (
        frozenset(
            {"aeat_sede_justificante", "aeat_sede_live_capture", "aeat_csv_register"},
        )
        == _OFFICIAL_SOURCE_KINDS
    )


def test_first_local_filing_still_persists_under_non_official_app_filing() -> None:
    """Honesty: the first local filing stays non-official ``app_filing``.

    The first-filer fix scopes a pre-activity DEMAND for evidence out of the graph;
    it never mints evidence. The local ``file`` flow still stamps its persisted
    observation as the non-official ``app_filing`` source kind, so a later dependent
    period still demands real AEAT evidence of that filing - the
    ``local-filed-observations-are-non-official-evidence`` invariant is unchanged.
    """
    assert APP_FILING_SOURCE_KIND == "app_filing"
    assert APP_FILING_SOURCE_KIND not in _OFFICIAL_SOURCE_KINDS

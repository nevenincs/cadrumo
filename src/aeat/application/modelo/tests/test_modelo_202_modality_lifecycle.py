"""Modelo 202 missing required bindings cannot produce filing-grade artifacts.

These tests exercise the real work-unit, calculation, verification, prior-filing
observation, and profile paths. An S.L. without the prior-12-month INCN or
relation-backed M202 facts must be refused before an all-zero draft, verified
revision, local filing, or export can be produced.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import RegistryModeloObservation
from ....domain.deadlines import EntityType, IVARegime, LegalEntityForm, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ExternalEvidenceKind,
)
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import derive_calculation_revision_id
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    CalculationRevisionStateError,
    ModeloExportCommand,
    ModeloRequiredBindingsMissingError,
    calculate_modelo_revision,
    create_work_unit,
    export_modelo_revision,
    file_modelo_revision,
    import_external_filing_evidence,
    verify_modelo_revision,
)
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True, scope="session")
def _register_wizard_catalogue() -> None:
    from ...wizard import _catalogue  # noqa: F401  (import for registration side effect)


_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
_BUCKET_ID = "69ba4fa8-427a-4853-8758-9ead443fb20c"
_TAX_ID = "B12345674"
_M202_RELATION_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M202_PRIOR_PAYMENTS_BINDING = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"
_M202_INCN_BINDING = "modelo-202-2025-y-siguientes-incn-prior-12-months"
_M200_CUOTA_LIQUIDA = "DP200014B:00592"
_ZERO_M202_CASILLA_VALUES = {
    "01": Decimal("0"),
    "03": Decimal("0"),
    "30": Decimal("0"),
    "34": Decimal("0"),
}


def _workflow_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        activity_start_date=date(2020, 1, 1),
        incn_prior_12_months=incn,
        new_entity_first_two_profit_periods=False,
    )


def _seed_profile(*, bucket_id: str, incn: Decimal | None) -> None:
    facts = [
        UserProfileFact(path="identity.tax_id", value=_TAX_ID),
        UserProfileFact(path="identity.name", value="Marta"),
        UserProfileFact(path="identity.surnames", value="Sociedad Limitada"),
        UserProfileFact(path="identity.legal_name", value="Taller Sol Sociedad Limitada"),
        UserProfileFact(path="activities.description", value="taller mecanico"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
        UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        UserProfileFact(path="filing_export.declaration_type", value="1"),
    ]
    if incn is not None:
        facts.append(UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=incn))
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test runtime profile",
            facts=tuple(facts),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def _seed_prior_m200_evidence(*, bucket_id: str) -> None:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2024, period="0A")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="200",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    evidence_reference_id = "JUST-M200-2024-0A"
    casilla_values = {_M200_CUOTA_LIQUIDA: Decimal("0")}
    persist_justificante_metadata(
        evidence_reference_id,
        modelo="200",
        filing_year=2024,
        period="0A",
        captured_at=_CLOCK,
        tax_id=_TAX_ID,
    )
    import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor="aeat-import-test",
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        filing_repository=filing_repo,
        expected_tax_id=_TAX_ID,
        clock=_CLOCK,
    )
    CalculationObservationRepository().save_observation(
        RegistryModeloObservation(
            modelo="200",
            filing_year=2024,
            period="0A",
            observations=registry_grounded_observations(
                modelo="200",
                filing_year=2024,
                period="0A",
                casilla_values=casilla_values,
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_CLOCK,
        stamped_revision_id=snapshot.revision.id,
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "EXP-M200-2024-0A",
            "aeat_justificante_csv": evidence_reference_id,
            "authenticated_identity": _TAX_ID,
        },
    )


def _calculate_m202(
    *,
    bucket_id: str,
) -> tuple[
    WorkUnit,
    CalculationRevision,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
]:
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    filing_repo = ModeloRecordCatalogueRepository()
    verification_repo = VerificationReportCatalogueRepository()
    snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period="1P")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="202",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1P"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_CLOCK,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-test",
        casilla_inputs={},
        binding_values={
            _M202_RELATION_BINDING: Decimal("0"),
            _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
        },
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        clock=_CLOCK,
    )
    refreshed_work_unit = work_repo.load().get(work_unit.work_unit_id)
    assert refreshed_work_unit is not None
    return refreshed_work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo


def _seed_legacy_zero_m202_revision(
    *,
    work_unit: WorkUnit,
    calculation_repository: CalculationRevisionCatalogueRepository,
    state: CalculationRevisionState,
) -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=_ZERO_M202_CASILLA_VALUES,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=state,
        casilla_values=_ZERO_M202_CASILLA_VALUES,
        observations=registry_grounded_observations(
            modelo="202",
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=_ZERO_M202_CASILLA_VALUES,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator-test" if state is not CalculationRevisionState.BORRADOR else None,
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    return revision


def test_m202_missing_required_bindings_refuses_before_persisting_zero_draft(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )

        with pytest.raises(ModeloRequiredBindingsMissingError) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator-test",
                casilla_inputs={},
                binding_values={},
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                clock=_CLOCK,
            )

        assert set(exc_info.value.context["missing_bindings"]) == {
            _M202_INCN_BINDING,
            _M202_RELATION_BINDING,
            _M202_PRIOR_PAYMENTS_BINDING,
        }
        assert calc_repo.load().revisions == {}
        stored_work_unit = work_repo.load().get(work_unit.work_unit_id)
        assert stored_work_unit is not None
        assert stored_work_unit.current_calculation_revision_id is None


def test_m202_legacy_zero_revision_cannot_verify_file_or_export(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        filing_repo = ModeloRecordCatalogueRepository()
        verification_repo = VerificationReportCatalogueRepository()
        snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )
        draft = _seed_legacy_zero_m202_revision(
            work_unit=work_unit,
            calculation_repository=calc_repo,
            state=CalculationRevisionState.BORRADOR,
        )
        workflow_profile = _workflow_profile(Decimal("500000"))

        with pytest.raises(ModeloRequiredBindingsMissingError, match=_M202_INCN_BINDING):
            verify_modelo_revision(
                draft.calculation_revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        stored = calc_repo.load().get(draft.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.BORRADOR

        verified = _seed_legacy_zero_m202_revision(
            work_unit=work_unit,
            calculation_repository=calc_repo,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
        )
        with pytest.raises(ModeloRequiredBindingsMissingError, match=_M202_PRIOR_PAYMENTS_BINDING):
            file_modelo_revision(
                verified.calculation_revision_id,
                actor="operator-test",
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        export_path = tmp_path / "m202-zero.txt"
        with pytest.raises(ModeloRequiredBindingsMissingError, match=_M202_RELATION_BINDING):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=verified.calculation_revision_id,
                    output_path=export_path,
                    actor="operator-test",
                ),
                workflow_profile=workflow_profile,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )
        assert export_path.exists() is False


def test_m202_wrong_state_still_refuses_file_before_required_binding_gate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=Decimal("500000"))
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )

        with pytest.raises(CalculationRevisionStateError, match="VERIFICADO_COMPLETO"):
            file_modelo_revision(
                revision.calculation_revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(Decimal("500000")),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                filing_repository=filing_repo,
                verification_repository=verification_repo,
                clock=_CLOCK,
            )


def test_m202_missing_incn_with_explicit_relation_values_refuses_calculate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=None)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        work_repo = WorkUnitCatalogueRepository()
        calc_repo = CalculationRevisionCatalogueRepository()
        snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period="1P")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1P"),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )

        with pytest.raises(ModeloRequiredBindingsMissingError) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator-test",
                casilla_inputs={},
                binding_values={
                    _M202_RELATION_BINDING: Decimal("0"),
                    _M202_PRIOR_PAYMENTS_BINDING: Decimal("0"),
                },
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                clock=_CLOCK,
            )

        assert tuple(exc_info.value.context["missing_bindings"]) == (_M202_INCN_BINDING,)


@pytest.mark.parametrize("incn", (Decimal("500000"), Decimal("7000000")))
def test_m202_declared_incn_below_or_above_threshold_can_verify(tmp_path: Path, incn: Decimal) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed_profile(bucket_id=_BUCKET_ID, incn=incn)
        _seed_prior_m200_evidence(bucket_id=_BUCKET_ID)
        _work_unit, revision, work_repo, calc_repo, filing_repo, verification_repo = _calculate_m202(
            bucket_id=_BUCKET_ID,
        )

        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator-test",
            workflow_profile=_workflow_profile(incn),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            verification_repository=verification_repo,
            clock=_CLOCK,
        )

        assert report.granted_verificado_completo is True
        stored = calc_repo.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored.state is CalculationRevisionState.VERIFICADO_COMPLETO

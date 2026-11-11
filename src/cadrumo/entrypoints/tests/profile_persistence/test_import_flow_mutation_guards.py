"""Work-unit and local-filing guard checks for external Modelo filing imports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from cadrumo.adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionScheme

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.action_errors import (
    AmendmentEvidenceMissingError,
    CalculationRevisionNotFoundError,
    ExternalModeloImportError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ....application.modelo.amendment_actions import amend_modelo_revision
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_revision_queries import get_calculation_revision
from ....application.modelo.external_import_actions import import_external_filing_evidence
from ....application.modelo.work_lifecycle import (
    create_work_unit,
    discard_work_unit,
)
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...adapter_composition_work_ports import build_amendment_action_ports, build_calculation_action_ports
from .file_flow_test_support import calculation_ports_for_test
from .import_flow_support import (
    IMPORT_INCOME_CASILLA,
    M111_AMENDMENT_CASILLA,
    PROFILE_ID,
    T0,
    T1,
    T2,
    T3,
    T4,
    Repos,
    import_external_filing,
    repos,
    seed_local_filing_record,
    seed_work_unit,
    withholding_payer_repos,
)

__all__ = ["repos", "withholding_payer_repos"]

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def test_import_refuses_discarded_work_unit(repos: Repos, *, operation: PinnedAuthorityOperation) -> None:
    """A discarded work unit cannot accept new imports."""

    wu_repo, _, _, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, bv_repo, operation=operation)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=T1,
    )

    with pytest.raises(WorkUnitMutationRefusedError):
        import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-LATE",
            clock=T2,
        )


def test_import_refuses_unknown_work_unit(repos: Repos) -> None:
    """A work_unit_id absent from the catalogue is rejected."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        import_external_filing_evidence(
            work_unit_id="0" * 64,
            casilla_values={IMPORT_INCOME_CASILLA: Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            observation_repository=CalculationObservationRepository(),
            clock=T1,
        )


def test_external_import_refuses_m303_without_complete_filing_evidence(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    period = Period.from_year_and_code(_YEAR, "1T")
    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period="1T")
    work_unit = create_work_unit(
        bucket_id=PROFILE_ID,
        modelo="303",
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=T0,
        operation=operation,
    )

    with pytest.raises(ExternalModeloImportError, match="external_import_m303_filing_evidence_required"):
        import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={validated_casilla_id("07"): Decimal("0")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="operator:m303:no-filing-evidence",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            observation_repository=CalculationObservationRepository(),
            clock=T1,
        )

    assert len(cr_repo.load()) == 0
    assert len(fr_repo.load()) == 0


def test_amend_locally_filed_still_refused_after_import_path_exists(
    withholding_payer_repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    """The import path does not loosen the local-filing amendment evidence gate."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = withholding_payer_repos
    work_unit = create_work_unit(
        bucket_id=PROFILE_ID,
        modelo="111",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=str(open_ended_revision("111").id),
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
        clock=T0,
        operation=operation,
    )
    # One professional retención paid in the quarter: the Modelo 111 boxes come from it.
    replace_retencion_observations(
        RetencionObservationRepositoryAdapter(objects=secure_object_repository_for_bucket(PROFILE_ID)),
        modelo="111",
        filing_year=_YEAR,
        period=work_unit.period,
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="professional-payment-001",
                perceptor_nif="12345678Z",
                perceptor_name="Profesional Ejemplo",
                scheme=RetencionScheme("actividades_profesionales"),
                taxable_base=Decimal("1000.00"),
                retencion_amount=Decimal("150.00"),
                accrued_on=date(_YEAR, 3, 15).isoformat(),
            )
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    with calculation_ports_for_test(
        bucket_id=PROFILE_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
    ) as _calculation_ports_180:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={},
            ports=_calculation_ports_180,
            clock=T1,
        ).revision
    verified_revision = revision.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": T2,
            "verified_by": "operator-A",
            "updated_at": T2,
        }
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), verified_revision))
    locally_filed = seed_local_filing_record(
        work_unit=work_unit,
        revision_id=verified_revision.calculation_revision_id,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        filed_at=T3,
        filed_by="operator-A",
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError), bundled_indexed_authority().operation() as operation:
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={M111_AMENDMENT_CASILLA: Decimal("1700")},
            amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
            reason="needed to amend",
            actor="operator-A",
            ports=build_amendment_action_ports(bucket_id=PROFILE_ID, operation=operation),
            clock=T4,
            operation=operation,
        )


def test_import_refuses_a_work_unit_outside_the_repository_bucket(tmp_path: Path) -> None:
    """A bucket-B work unit cannot be imported through A-bound repositories.

    ``import_external_filing_evidence`` loaded the WorkUnit by id from a
    caller-supplied repository and never checked that repository's bucket against
    ``work_unit.bucket_id``, then used separately supplied calculation, filing,
    work-unit, and event repositories for the whole mutation. A caller could
    persist a B-bucket filing through A-bound stores, advance B pointers, and
    emit a B event with no cross-bucket refusal.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        cr_repo = CalculationRevisionCatalogueRepository(objects=profile.repository)
        fr_repo = ModeloRecordCatalogueRepository(objects=profile.repository)
        bv_repo = BucketEventHistoryRepository(objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))
        # Provisioning the runtime profile records its own bucket event.
        events_before = bv_repo.load().events

        with pytest.raises(WorkUnitNotFoundError):
            import_external_filing_evidence(
                work_unit_id=foreign.work_unit_id,
                casilla_values={_GUARD_INCOME_CASILLA: Decimal("1500")},
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id="JUST-GUARD-FOREIGN",
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                filing_repository=fr_repo,
                bucket_event_repository=bv_repo,
                observation_repository=CalculationObservationRepository(),
                expected_tax_id="X0001500M",
                clock=_GUARD_CLOCK,
            )

        # Nothing advanced, nothing filed, nothing recorded for bucket B.
        assert wu_repo.load().get(foreign.work_unit_id) == foreign
        assert len(cr_repo.load()) == 0
        assert bv_repo.load().events == events_before


def test_calculate_refuses_a_work_unit_outside_the_repository_bucket(tmp_path: Path) -> None:
    """A work-unit repository claiming one bucket cannot calculate against a
    unit that actually belongs to another.

    The active session is bound to bucket B (the foreign unit's genuine
    owner, with a real ready profile) so the calculate path's own
    profile-readiness gate is not what refuses this -- ``wu_repo`` is
    constructed claiming bucket A while the loaded unit's own
    ``bucket_id`` is B, isolating exactly one check:
    ``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` compares
    ``work_unit_repository.bucket_id`` against the loaded unit's own
    ``bucket_id``, as ``import_external_filing_evidence`` and the
    calculation-revision addressing helpers in this same package do.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_B) as profile:
        seed_ready_profile(bucket_id=_GUARD_BUCKET_B, at=T0)
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        cr_repo = CalculationRevisionCatalogueRepository(objects=profile.repository)
        bv_repo = BucketEventHistoryRepository(objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))

        with (
            pytest.raises(WorkUnitNotFoundError),
            calculation_ports_for_test(
                bucket_id=_GUARD_BUCKET_B,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                bucket_event_repository=bv_repo,
            ) as _calculation_ports_295,
        ):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                foreign.work_unit_id,
                actor="operator-A",
                casilla_inputs={
                    _GUARD_WITHHELD_CASILLA: Decimal("0"),
                    _GUARD_PREVIOUS_PAYMENT_CASILLA: Decimal("0"),
                    _GUARD_HOME_DEDUCTION_CASILLA: Decimal("0"),
                    _GUARD_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
                },
                binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("0")},
                ports=_calculation_ports_295,
                clock=_GUARD_CLOCK,
            )

        assert wu_repo.load().get(foreign.work_unit_id) == foreign
        assert len(cr_repo.load()) == 0


_GUARD_EXPENSE_CASILLA = validated_casilla_id("02")
_GUARD_WITHHELD_CASILLA = validated_casilla_id("05")
_GUARD_PREVIOUS_PAYMENT_CASILLA = validated_casilla_id("06")
_GUARD_AGRARIAN_VOLUME_CASILLA = validated_casilla_id("08")
_GUARD_AGRARIAN_WITHHELD_CASILLA = validated_casilla_id("10")
_GUARD_HOME_DEDUCTION_CASILLA = validated_casilla_id("16")
_GUARD_PRIOR_RETURN_RESULT_CASILLA = validated_casilla_id("18")


def test_the_foreign_import_target_is_genuinely_present(tmp_path: Path) -> None:
    """Anti-tautology: the refusal above is bucket scope, not an absent unit."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))

        stored = wu_repo.load().get(foreign.work_unit_id)

    assert stored is not None
    assert stored.bucket_id == _GUARD_BUCKET_B


def test_calculation_revision_actions_refuse_a_foreign_work_unit(tmp_path: Path) -> None:
    """A foreign revision already present in A's stores is not addressable by A."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))
        revision = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=foreign.work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
                filing_instance_evidence=None,
                source_provenance=(),
            ),
            work_unit_id=foreign.work_unit_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo=foreign.modelo,
                revision_id=foreign.revision_id,
                modelo_year=foreign.filing_year,
                period=foreign.period.registry_token,
            ),
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            casilla_values={},
            created_at=_GUARD_CLOCK,
            updated_at=_GUARD_CLOCK,
            filing_instance_evidence=None,
            source_provenance=(),
        )
        cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

        with pytest.raises(CalculationRevisionNotFoundError), bundled_indexed_authority().operation() as operation:
            get_calculation_revision(
                revision.calculation_revision_id,
                ports=build_calculation_action_ports(bucket_id=_GUARD_BUCKET_A, operation=operation),
            )

        assert cr_repo.load().get(revision.calculation_revision_id) == revision


_GUARD_BUCKET_A = "6aa00000-0000-4000-8000-0000000000aa"
_GUARD_BUCKET_B = "6bb00000-0000-4000-8000-0000000000bb"
_GUARD_CLOCK = T1
_GUARD_INCOME_CASILLA = IMPORT_INCOME_CASILLA


def _guard_work_unit(bucket_id: str) -> WorkUnit:
    """Build a valid M130 work unit owned by ``bucket_id``."""
    period = Period.from_year_and_code(_YEAR, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=_YEAR,
            period=period,
            revision_id=str(open_ended_revision("130").id),
        ),
        bucket_id=bucket_id,
        name=f"130-{_YEAR}-1T",
        modelo="130",
        filing_year=_YEAR,
        period=period,
        revision_id=str(open_ended_revision("130").id),
        created_at=T0,
        updated_at=T0,
    )

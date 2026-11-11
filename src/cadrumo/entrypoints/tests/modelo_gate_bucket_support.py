"""Seeded profile, empty-input calculation and workflow profile shared by Modelo gate tests over one real bucket."""

from __future__ import annotations

from datetime import date, datetime

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope


def seed_ready_capital_payer_profile(*, bucket_id: str, at: datetime, tax_id: str = "12345678Z") -> None:
    """Store a complete natural-person profile, with an IVA general regime and no employees, that pays capital income.

    Paying capital income subject to retención is the payer fact the capital
    withholding modelos, the 123, 128 and 193 among them, are applicable on.
    """
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=tax_id),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="capital income payer"),
                    UserProfileFact(path="censo.activity_start_date", value=date(filing_year_envelope().floor, 1, 1)),
                    UserProfileFact(path="withholding.colegio_concertado", value=False),
                    UserProfileFact(path="withholding.pays_capital_income_with_retencion", value=True),
                )
            ),
            created_at=at,
            updated_at=at,
            context=profile_creation_context_for_test(),
        ),
    )


def calculate_without_inputs(
    *, bucket_id: str, objects: SecureObjectRepository, work_unit_id: str
) -> CalculationRevisionId:
    """Calculate one work unit with no operator inputs and return the persisted revision id."""
    with calculation_ports_for_test(
        bucket_id=bucket_id,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        invoice_repository=InvoiceCatalogueRepository(objects=objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
    ) as ports:
        result = calculate_modelo_work_revision(
            work_unit_id=work_unit_id,
            actor="test",
            inputs=WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values={},
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            ),
            ports=ports,
        )
    return result.revision.calculation_revision_id


def ready_workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(filing_year_envelope().floor, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )

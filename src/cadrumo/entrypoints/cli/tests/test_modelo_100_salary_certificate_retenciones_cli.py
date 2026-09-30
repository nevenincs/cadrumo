"""CLI reproduction for the M100 work-retention credit the payee keys."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from cadrumo.application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.operation_definitions import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition

from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# The newest Modelo 100 edition the registry authors; its prior-year carry reads the
# edition before it.
_REVIEWED_EDITION = newest_authored_edition("100")

_CAPTURED_AT = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


_M100_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ana"),
    UserProfileFact(path="identity.surnames", value="Retenciones"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(_REVIEWED_EDITION - 5, 1, 1)),
    UserProfileFact(path="renta_taxpayer.birth_date", value=date(_REVIEWED_EDITION - 45, 3, 15)),
    UserProfileFact(path="renta_taxpayer.sex", value="H"),
    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
    UserProfileFact(path="renta_filing.declaration_type", value="1"),
    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
    UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
)


def _scope(client_id: UUID) -> AccessScope:
    """Grant the registered work creation, addressing and calculation operations."""
    operation_ids = frozenset(
        {
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        }
    )
    return AccessScope(
        operations=operation_ids,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in operation_ids
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _prepare_m100_profile(profile_id: UUID, root: Path, authority_operation: PinnedAuthorityOperation) -> None:
    """Complete the enrolled taxpayer and persist canonical prior-year carry evidence."""
    facts = complete_profile_facts(authority_operation.profile_schema(), _M100_PROFILE_FACTS)
    populated = upsert_test_profile_facts(profile_id, facts, root=root)
    with bound_test_profile_record(profile_id, root=root) as repository:
        ready = repository.complete_setup(
            profile_id,
            expected_revision=populated.record_revision,
            expected_content_digest=populated.content_digest,
        )
    assert ready.setup_state is ProfileSetupState.COMPLETE
    _seed_prior_year_zero_carry(profile_id)


def _seed_prior_year_zero_carry(profile_id: UUID) -> None:
    repository = CalculationObservationRepository(bucket_id=str(profile_id))
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_REVIEWED_EDITION - 1,
                period="0A",
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_REVIEWED_EDITION - 1,
                    period="0A",
                    casilla_values={"1391": Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
            stamped_revision_id=str(
                published_snapshot("100", filing_year=_REVIEWED_EDITION - 1, period="0A").revision.id
            ),
        )
    )


def test_m100_cli_salary_certificate_retenciones_populates_0596(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Real CLI reproduction: the payee salary-certificate binding affects 0596."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope,
        prepare_profile=lambda profile_id, root: _prepare_m100_profile(profile_id, root, authority_operation),
    ) as session:
        created = session.invoke_password(
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            str(_REVIEWED_EDITION),
            "--period",
            "0A",
            "--revision",
            str(_REVIEWED_EDITION),
        )
        assert created.exit_code == 0, created.output
        work_unit_id = _payload(created.output)["work_unit_id"]
        assert isinstance(work_unit_id, str) and work_unit_id, created.output
        result = session.invoke_password(
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "0003=32000",
            "--casilla",
            "0102=9600",
            "--binding",
            "renta-modelo-100-estimacion-directa-es-normal=1",
            "--binding",
            "renta-modelo-184-atribucion-actividades-economicas=0",
            "--binding",
            "renta-certificado-trabajo-retenciones=4200",
            "--relation",
            "renta-modelo-130-pagos-fraccionados=0",
            "--relation",
            "renta-modelo-131-pagos-fraccionados=0",
        )

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert Decimal(payload["casilla_values"]["0596"]) == Decimal("4200")
    assert Decimal(payload["casilla_values"]["0609"]) == Decimal("4200")

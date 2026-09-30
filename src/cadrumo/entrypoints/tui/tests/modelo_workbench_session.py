"""Public real-storage construction support for the modelo workbench surfaces.

Entrypoint tests consume this defining test-support module directly.

A seeded, complete taxpayer and one real declaration, read through the
production workbench reader: the form builder, the published form layout, the
work review and the edit admission all run for real against the bundled
registry. The seeded taxpayer is deliberately complete, because an incomplete
one would exercise refusal paths in tests that mean to exercise a rendered
workbench, and a refusal renders a small surface that fits at any size.

The lifecycle door's operation services are the one stand-in: the surfaces
these tests mount read and stage, and never submit an operation, so nothing
reaches them. Every figure is synthetic.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.edit_admission import admit_modelo_edit_baseline
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports
from ...operation_composition import build_production_operation_registry
from ..modelo.lifecycle import ModeloWorkspaceLifecycleDoor
from ..modelo.workbench.installed import InstalledModeloWorkbench, WorkbenchRepositories

_BUCKET_ID = "13000000-0000-4000-8000-000000000451"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


@contextmanager
def real_workbench(
    tmp_path: Path,
    *,
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
) -> Generator[InstalledModeloWorkbench]:
    """Yield the production reader and actions of one seeded declaration.

    Held open as a context manager because the profile runtime must stay live
    while a mounted workbench reads through it. The address picks the SHAPE of
    the data -- a compact quarterly return or a dense annual one -- from the
    bundled registry rather than from padded fixture rows.
    """
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=operation.profile_create_context(),
            ),
        )
        period = Period.from_year_and_code(filing_year, period_code)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=str(
                operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token).id
            ),
            ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
            clock=_T0,
            operation=operation,
        )
        ports = build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation)
        contracts = build_production_operation_registry().public_contract_set

        def door(
            calculation_revision_id: str | None, verification_report_id: str | None
        ) -> ModeloWorkspaceLifecycleDoor:
            return ModeloWorkspaceLifecycleDoor(
                services=cast(Any, object()),
                work_unit_id=unit.work_unit_id,
                calculation_revision_id=calculation_revision_id,
                verification_report_id=verification_report_id,
                edit_admission=lambda: admit_modelo_edit_baseline(
                    work_unit_id=unit.work_unit_id,
                    work_catalogue=ports.work_unit_repository.load(),
                    calculation_catalogue=ports.calculation_repository.load(),
                    operation=operation,
                    operation_contracts=contracts,
                ),
            )

        yield InstalledModeloWorkbench(
            bucket_id=profile.bucket_id,
            declaration=DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=unit.work_unit_id,
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
                state=unit.state,
                has_current_calculation=False,
                has_current_filing=False,
            ),
            operation=operation,
            repositories=WorkbenchRepositories(
                work_units=ports.work_unit_repository,
                calculations=ports.calculation_repository,
                verifications=VerificationReportCatalogueRepository(bucket_id=profile.bucket_id),
            ),
            door=door,
        )


__all__ = ["real_workbench"]

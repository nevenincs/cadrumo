"""Live source-mesh enrollment for ``bienes_inversion_regularizacion``.

This test exercises the application mesh path, not the advisory projection in
isolation: the mesh materialises current-year registry prorrata values, calls
the real bienes-inversión resolver, and binds Modelo 303 casilla 43.

See Also:
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh result envelope whose owned sources, binding values, and
        diagnostics are asserted by this enrollment gate.
    :func:`~application.modelo.calculation_actions.resolve_bucket_source_mesh`
        Calculate-path mesh entry point that enrolls the bienes-inversión
        resolver.
    :mod:`~application.calculations._bienes_inversion_regularizacion`
        Projection and live resolver for the capital-goods IVA regularización
        source kind.
    :mod:`~application.modelo._bienes_inversion_advisory`
        Earlier advisory wiring that kept casilla 43 visible before hard
        source-mesh promotion.
        The M303 live enrollment policy.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests._relation_prefill_support import empty_profile_read_ports
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.percepciones_observations_repository import PercepcionObservationPorts
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
from cadrumo.application.modelo.action_errors import ModeloProfileReadinessError
from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts
from cadrumo.application.modelo.calculation_actions import resolve_bucket_source_mesh
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienInversionIvaRecord
from cadrumo.domain.bienes_inversion.vocabulary import BienInversionKind
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports

from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_FILING_YEAR = 2024
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_CREATED_AT = datetime(2025, 1, 20, 9, 0, tzinfo=UTC)
_BINDING_ID = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_CASILLA_43_ID: CasillaId = validated_casilla_id("43", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")


def _empty_usage_ratio_profile_loader(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> UsageRatioProfile:
    """Return the empty usage-ratio profile for this source-mesh seam."""
    del bucket_id, operation
    return UsageRatioProfile()


def _source_mesh_ports(
    *,
    bucket_id: str,
    objects: SecureObjectRepository,
    bienes_repository: BienesInversionIvaRegisterRepository,
    operation: PinnedAuthorityOperation,
) -> CalculationActionPorts:
    """Use the complete application composition with this test's isolated-store repositories."""
    transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=bucket_id, objects=objects)
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    return CalculationActionPorts(
        operation=operation,
        work_unit_repository=ports.work_unit_repository,
        work_lifecycle_ports=ports.work_lifecycle_ports,
        calculation_repository=ports.calculation_repository,
        bucket_event_repository=ports.bucket_event_repository,
        transaction_repository=transaction_repository,
        activity_asset_history_repository=ports.activity_asset_history_repository,
        usage_ratio_profile_loader=_empty_usage_ratio_profile_loader,
        profile_read_ports=empty_profile_read_ports(),
        invoice_repository=invoice_repository,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=invoice_repository,
            transaction_reader=transaction_repository,
        ),
        filing_repository=ports.filing_repository,
        invoice_source_ports=InvoiceSourceResolverPorts(catalogue_reader=invoice_repository),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=bucket_id, objects=objects),
        bienes_inversion_repository=bienes_repository,
        inventory_repository=ports.inventory_repository,
        observation_repository=CalculationObservationRepository(objects=objects),
        percepciones_observation_ports=PercepcionObservationPorts(
            repository=PercepcionObservationRepositoryAdapter(objects=objects),
        ),
        retencion_observation_ports=RetencionObservationPorts(
            repository=RetencionObservationRepositoryAdapter(objects=objects),
        ),
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
        iva_compensation_decision_repository=ports.iva_compensation_decision_repository,
        borrador_snapshot_repository=ports.borrador_snapshot_repository,
        relation_override_migration=ports.relation_override_migration,
    )


def _work_unit(*, revision_id: str) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision_id=revision_id,
        name=f"303-{_FILING_YEAR}-{_PERIOD.registry_token}",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _record() -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier="bi-2022-maquina",
        description="Maquina afecta a la actividad",
        acquisition_year=2022,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id="ledger-bi-2022-maquina",
    )


def _seed_taxpayer_profile(*, setup_state: ProfileSetupState) -> None:
    """Publish a canonical profile with explicit facts relevant to Modelo 303."""
    authority = published_authority_operation()
    context = authority.profile_create_context()
    explicit_facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="identity.name", value="Asset IVA Test"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="activities.description", value="investment-goods source-mesh acceptance"),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=context,
            setup_state=setup_state,
            profile_id=_BUCKET_ID,
            facts=complete_profile_facts(context.schema, explicit_facts),
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
        ),
    )


def test_source_mesh_resolves_bienes_inversion_regularizacion_binding(tmp_path: Path) -> None:
    """The live mesh projects the register value into Modelo 303 casilla 43."""
    authority = published_authority_operation()
    snapshot = authority.snapshot("303", filing_year=_FILING_YEAR, period="4T")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_taxpayer_profile(setup_state=ProfileSetupState.COMPLETE)
        bienes_repository = BienesInversionIvaRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        bienes_repository.add(_record())

        with bundled_indexed_authority().operation() as operation:
            resolution = resolve_bucket_source_mesh(
                snapshot,
                work_unit,
                ports=_source_mesh_ports(
                    bucket_id=_BUCKET_ID,
                    objects=profile.repository,
                    bienes_repository=bienes_repository,
                    operation=operation,
                ),
                foreign_asset_observations=(),
                foreign_asset_row_observations=(),
                casilla_inputs={
                    _VOLUMEN_CON_DERECHO_ID: Decimal("60000.00"),
                    _VOLUMEN_TOTAL_ID: Decimal("100000.00"),
                },
                filing_period_date=snapshot.filing_period.end_date,
            )

    bienes_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    )
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION in resolution.owned_sources
    assert resolution.binding_values[_BINDING_ID] == Decimal("200.00")
    assert resolution.bound_inputs_by_casilla_id[_CASILLA_43_ID] == Decimal("200.00")
    assert _BINDING_ID not in resolution.unresolved_binding_ids
    assert bienes_diagnostics == ()


def test_source_mesh_refuses_incomplete_taxpayer_profile(tmp_path: Path) -> None:
    """The real M303 resolver refuses setup-incomplete profile state."""
    authority = published_authority_operation()
    snapshot = authority.snapshot("303", filing_year=_FILING_YEAR, period="4T")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_taxpayer_profile(setup_state=ProfileSetupState.INCOMPLETE)
        bienes_repository = BienesInversionIvaRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        bienes_repository.add(_record())

        with bundled_indexed_authority().operation() as operation, pytest.raises(ModeloProfileReadinessError):
            resolve_bucket_source_mesh(
                snapshot,
                work_unit,
                ports=_source_mesh_ports(
                    bucket_id=_BUCKET_ID,
                    objects=profile.repository,
                    bienes_repository=bienes_repository,
                    operation=operation,
                ),
                foreign_asset_observations=(),
                foreign_asset_row_observations=(),
                casilla_inputs={
                    _VOLUMEN_CON_DERECHO_ID: Decimal("60000.00"),
                    _VOLUMEN_TOTAL_ID: Decimal("100000.00"),
                },
                filing_period_date=snapshot.filing_period.end_date,
            )

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

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests._relation_prefill_support import empty_profile_read_ports
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.percepciones_observations_repository import PercepcionObservationPorts
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
from cadrumo.application.modelo.calculation_action_ports import CalculationActionPorts
from cadrumo.application.modelo.calculation_actions import resolve_bucket_source_mesh
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienInversionIvaRecord
from cadrumo.domain.bienes_inversion.vocabulary import BienInversionKind
from cadrumo.domain.invoices.models import InvoiceCatalogue
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

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


class _EmptyInvoiceRepository:
    """Deterministic inward fake for the invoice authorities unused by this test."""

    @staticmethod
    def load() -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyPercepcionRepository:
    """Deterministic inward fake for the optional withholding source."""

    @staticmethod
    def load_observations(modelo: str, period: Period) -> tuple[object, ...]:
        del modelo, period
        return ()


class _EmptyRetencionRepository:
    """Deterministic inward fake for the optional retención source."""

    @staticmethod
    def load_observations(modelo: str, period: Period) -> tuple[object, ...]:
        del modelo, period
        return ()


def _source_mesh_ports(*, bucket_id: str, objects: object, bienes_repository: object) -> CalculationActionPorts:
    """Bind the real profile repositories while keeping unrelated authorities inward and deterministic."""
    transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    invoice_repository = _EmptyInvoiceRepository()
    work_unit_repository = Mock()
    bucket_event_repository = Mock()
    return CalculationActionPorts(
        work_unit_repository=work_unit_repository,
        work_lifecycle_ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
        ),
        calculation_repository=Mock(),
        bucket_event_repository=bucket_event_repository,
        transaction_repository=transaction_repository,
        usage_ratio_profile_loader=Mock(return_value={}),
        profile_read_ports=empty_profile_read_ports(),
        invoice_repository=invoice_repository,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=invoice_repository,
            transaction_reader=transaction_repository,
        ),
        filing_repository=Mock(),
        prorrata_register_repository=ProrrataRegisterRepository(objects=objects),
        bienes_inversion_repository=bienes_repository,
        inventory_repository=Mock(),
        observation_repository=CalculationObservationRepository(objects=objects),
        invoice_source_ports=InvoiceSourceResolverPorts(catalogue_reader=invoice_repository),
        percepciones_observation_ports=PercepcionObservationPorts(repository=_EmptyPercepcionRepository()),
        iva_compensation_history_repository=Mock(),
        iva_compensation_decision_repository=Mock(),
        borrador_snapshot_repository=Mock(),
        retencion_observation_ports=RetencionObservationPorts(repository=_EmptyRetencionRepository()),
        relation_override_migration=Mock(),
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
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id="ledger-bi-2022-maquina",
    )


def test_source_mesh_resolves_bienes_inversion_regularizacion_binding(tmp_path: Path) -> None:
    """The live mesh projects the register value into Modelo 303 casilla 43."""
    snapshot = compiled_bundled_authority().snapshot("303", filing_year=_FILING_YEAR, period="4T")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        bienes_repository = BienesInversionIvaRegisterRepository(objects=profile.repository)
        bienes_repository.add(_record())

        resolution = resolve_bucket_source_mesh(
            snapshot,
            work_unit,
            ports=_source_mesh_ports(
                bucket_id=_BUCKET_ID,
                objects=profile.repository,
                bienes_repository=bienes_repository,
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

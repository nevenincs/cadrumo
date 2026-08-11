"""Production value-arrival proof for M303 regimen-simplificado rows."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo, PaymentElection, Period, PriorDomiciliationElection, RefundElection, ResultDisposition
from ....domain.deadlines import ModeloIVAProfile
from ....domain.filing import FilingExportError
from ....domain.iva import (
    ActividadAgricolaSimplificado,
    ActividadOrdenAnual,
    HechoActividadSimplificado,
    RegimenSimplificadoFilingRows,
)
from ....domain.submission import ModeloDraftStatus
from .. import (
    FilingElectionFacts,
    M303RegimenSimplificadoValueArrival,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
    export_draft,
    project_m303_regimen_simplificado_value_arrival,
)
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACT_IDENTITIES = (
    "volumen-de-ingresos",
    "indice-de-cuota",
    "cuota-devengada",
    "1t-2t-3t-porcentaje-ingreso-a-cuenta",
    "1t-2t-3t-ingreso-a-cuenta-a",
    "4t-cuota-soportada-operaciones-corrientes",
    "4t-cuota-anual-derivada-del-regimen-simplificado-b",
    "cuotas-soportadas-4t",
    "compensaciones-satisfechas-a-sujetos-pasivos-en-r-e-a-g-p-4t",
)


def _provider() -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        modelos=("303",),
    )


def _arrival(*, applicable: bool, omit_last_fact: bool = False) -> M303RegimenSimplificadoValueArrival:
    facts = tuple(
        HechoActividadSimplificado(
            identity=identity,
            value=Decimal(index),
            evidence_reference=f"evidence:agri-1:{identity}",
        )
        for index, identity in enumerate(_FACT_IDENTITIES, start=1)
        if not (omit_last_fact and identity == _FACT_IDENTITIES[-1])
    )
    activities = (
        (
            ActividadAgricolaSimplificado(
                ejercicio=2025,
                activity_id="agri-1",
                activity_code="01",
                facts=facts,
                evidence_reference="censo:activity:agri-1",
            ),
        )
        if applicable
        else ()
    )
    return M303RegimenSimplificadoValueArrival(
        rows=RegimenSimplificadoFilingRows(ejercicio=2025, activities=activities),
        orden=(
            ActividadOrdenAnual(
                ejercicio=2025,
                kind="agricola",
                activity_code="01",
                applicable_fact_identities=_FACT_IDENTITIES,
                legal_refs=("orden-hac-1347-2024:art-4",),
                source_refs=("boe-a-2024-26340",),
            ),
        )
        if applicable
        else (),
        applicable=applicable,
        censo_iae_epigraphs=frozenset(),
        record_design_source_ref="aeat-dr-303-2025",
        design_epoch="2025",
    )


def _draft_and_snapshot(provider: RegistrySchemaAccessor):
    period = Period.from_year_and_code(2025, "4T")
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Regimen simplificado proof"),
        inputs={
            "07": Decimal("0"),
            "iva.soportado.interiores": Decimal("0"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=ModeloIVAProfile(
            roi_enrolled=False,
            oss_enrolled=False,
            group_member_enrolled=False,
            group_dominant_entity_enrolled=False,
            intracommunity_operations_exceed_50000_eur=False,
            sii_enrolled=False,
            redeme_enrolled=False,
        ),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
    )
    return draft, snapshot


def test_complete_rows_reach_exact_source_targets_before_unsupported_export(tmp_path: Path) -> None:
    provider = _provider()
    arrival = _arrival(applicable=True)
    projection = project_m303_regimen_simplificado_value_arrival(
        period=Period.from_year_and_code(2025, "4T"),
        schema_provider=provider,
        value_arrival=arrival,
    )

    assert len(projection) == 1
    assert len(projection[0].fields) == 142
    code = next(field for field in projection[0].fields if field.ordinal == 6)
    assert (code.offset, code.length, code.type_code, code.value) == (13, 2, "Num", "01")
    assert next(field for field in projection[0].fields if field.ordinal == 7).value == Decimal("1")

    draft, snapshot = _draft_and_snapshot(provider)
    output = tmp_path / "m303-regimen-simplificado.txt"
    with pytest.raises(FilingExportError, match="no complete export_layouts definition"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=snapshot,
            schema_provider=provider,
            regimen_simplificado=arrival,
        )
    assert not output.exists()


def test_missing_applicable_fact_refuses_before_unsupported_layout_or_target(tmp_path: Path) -> None:
    provider = _provider()
    draft, snapshot = _draft_and_snapshot(provider)
    output = tmp_path / "m303-regimen-simplificado-missing.txt"

    with pytest.raises(FilingExportError, match="applicable facts do not match the annual Orden"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=snapshot,
            schema_provider=provider,
            regimen_simplificado=_arrival(applicable=True, omit_last_fact=True),
        )
    assert not output.exists()


def test_proven_nonapplicable_rows_omit_projection_and_create_no_target(tmp_path: Path) -> None:
    provider = _provider()
    arrival = _arrival(applicable=False)
    assert (
        project_m303_regimen_simplificado_value_arrival(
            period=Period.from_year_and_code(2025, "4T"),
            schema_provider=provider,
            value_arrival=arrival,
        )
        == ()
    )

    draft, snapshot = _draft_and_snapshot(provider)
    output = tmp_path / "m303-regimen-simplificado-nonapplicable.txt"
    with pytest.raises(FilingExportError, match="no complete export_layouts definition"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=snapshot,
            schema_provider=provider,
            regimen_simplificado=arrival,
        )
    assert not output.exists()

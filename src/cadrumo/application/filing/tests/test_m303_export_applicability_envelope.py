"""Closed-shape and five-epoch proofs for exhaustive M303 applicability."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....application.aggregation import IvaDifferentiatedDeductionContribution
from ....core import (
    IvaDeductionFactKind,
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    ProrrataActivityRowType,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    RefundElection,
    ResultDisposition,
    SectorDiferenciadoLetra,
    validated_casilla_id,
)
from ....domain.bienes_inversion import BienesInversionIvaRegister, RegistroRegularizacionResult
from ....domain.deadlines import ModeloIVAProfile
from ....domain.filing import FilingExportError
from ....domain.iva import (
    ActividadAgricolaSimplificado,
    ActividadOrdenAnual,
    HechoActividadSimplificado,
    RegimenSimplificadoFilingRows,
)
from ....domain.prorrata_register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ....domain.submission import ModeloDraftStatus
from .. import (
    FilingElectionFacts,
    M303DifferentiatedSectorValueArrival,
    M303Exonerado390EndpointValue,
    M303Exonerado390ValueArrival,
    M303ExportApplicabilityEnvelope,
    M303RegimenSimplificadoValueArrival,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
    export_draft,
)
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _axes() -> dict[str, object]:
    return {
        "exonerado_390_applicable": False,
        "exonerado_390": None,
        "prorrata_activities_applicable": False,
        "prorrata_register": None,
        "differentiated_sectors_applicable": False,
        "differentiated_sectors": None,
        "regimen_simplificado_applicable": False,
        "regimen_simplificado": None,
    }


@pytest.mark.parametrize(
    "axis",
    (
        "exonerado_390_applicable",
        "prorrata_activities_applicable",
        "differentiated_sectors_applicable",
        "regimen_simplificado_applicable",
    ),
)
def test_every_applicability_axis_refuses_unknown(axis: str) -> None:
    values = _axes()
    values[axis] = None

    with pytest.raises(ValidationError, match="must be explicitly resolved"):
        M303ExportApplicabilityEnvelope.model_validate(values)


def test_applicable_unit_refuses_missing_payload() -> None:
    values = _axes()
    values["differentiated_sectors_applicable"] = True

    with pytest.raises(ValidationError, match="requires its authoritative payload"):
        M303ExportApplicabilityEnvelope.model_validate(values)


def test_nonapplicable_unit_refuses_payload() -> None:
    values = _axes()
    values["exonerado_390"] = M303Exonerado390ValueArrival(
        marker_reference="profile:exonerado",
        endpoints=(
            M303Exonerado390EndpointValue(
                casilla_id=validated_casilla_id("79", surface="S51 negative fixture"),
                value=Decimal("0"),
                producer_reference="annual:79",
            ),
        ),
    )

    with pytest.raises(ValidationError, match="must not carry a payload"):
        M303ExportApplicabilityEnvelope.model_validate(values)


def test_explicit_nonapplicability_is_the_only_blank_admission() -> None:
    envelope = M303ExportApplicabilityEnvelope.model_validate(_axes())

    assert envelope.exonerado_390 is None
    assert envelope.prorrata_register is None
    assert envelope.differentiated_sectors is None
    assert envelope.regimen_simplificado is None


_EXONERADO_IDS = (
    "79",
    "80",
    "81",
    "83",
    "84",
    "86",
    "88",
    "89",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
    "97",
    "98",
    "99",
    "107",
    "125",
    "126",
    "127",
    "128",
)
_BASE_FACTS = (
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
_LATE_2024_FACTS = (
    "si-en-el-ejercicio-realiza-la-actividad-en-municipios-afectados-por-la-dana-ver-anexo-del-rd-ley-6-2024-seleccione-lo-que-proceda",
    "reduccion-por-actividad-realizada-en-municipios-afectados-por-la-dana-ver-anexo-del-rd-ley-6-2024",
)


def _complete_envelope(year: int, source_ref: str, epoch: str) -> M303ExportApplicabilityEnvelope:
    definitions = (
        SectorDefinition(sector_id="a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",)),
        SectorDefinition(sector_id="b", letra=SectorDiferenciadoLetra.B, member_activity_codes=("6820",)),
    )
    register = ProrrataRegister(
        entries=tuple(
            ProrrataRegisterEntry(
                ejercicio=year,
                sector_id=sector_id,
                regime=ProrrataRegisterRegime.GENERAL,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            )
            for sector_id in ("a", "b")
        ),
        sector_definitions=definitions,
        activity_rows=tuple(
            ProrrataActivityRow(
                ejercicio=year,
                activity_id=f"activity-{slot}",
                slot=slot,
                cnae_code=f"{4700 + slot}",
                operaciones_total=Decimal("100"),
                operaciones_con_derecho=Decimal("80"),
                prorrata_type=ProrrataActivityRowType.GENERAL,
                percentage=Decimal("80"),
                evidence_reference=f"ledger:activity-{slot}",
            )
            for slot in range(1, 6)
        ),
    )
    kinds = tuple(
        kind for kind in IvaDeductionFactKind if kind is not IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    )
    contributions = tuple(
        IvaDifferentiatedDeductionContribution(
            sector_id=sector_id,
            deduction_fact_kind=kind,
            source_ledger_ids=(f"ledger-{sector_id}-{index}",),
            base_amount=Decimal("100"),
            deducible_iva_amount=Decimal("20"),
        )
        for sector_id in ("a", "b")
        for index, kind in enumerate(kinds, 1)
    )
    fact_ids = _BASE_FACTS + (_LATE_2024_FACTS if epoch == "2024-late" else ())
    simplified = M303RegimenSimplificadoValueArrival(
        rows=RegimenSimplificadoFilingRows(
            ejercicio=year,
            activities=(
                ActividadAgricolaSimplificado(
                    ejercicio=year,
                    activity_id="agri-1",
                    activity_code="01",
                    facts=tuple(
                        HechoActividadSimplificado(
                            identity=item, value=Decimal("1"), evidence_reference=f"evidence:{item}"
                        )
                        for item in fact_ids
                    ),
                    evidence_reference="censo:agri-1",
                ),
            ),
        ),
        orden=(
            ActividadOrdenAnual(
                ejercicio=year,
                kind="agricola",
                activity_code="01",
                applicable_fact_identities=fact_ids,
                legal_refs=("orden:regimen-simplificado",),
                source_refs=("boe:orden",),
            ),
        ),
        applicable=True,
        censo_iae_epigraphs=frozenset(),
        record_design_source_ref=source_ref,
        design_epoch=epoch,
    )
    regularisation = RegistroRegularizacionResult(
        regularizacion_year=year,
        rows=(),
        proposed_casilla_43=Decimal("0"),
        computed_count=0,
        pending_percentage_count=0,
        sector_contributions=(),
    )
    return M303ExportApplicabilityEnvelope(
        exonerado_390_applicable=True,
        exonerado_390=M303Exonerado390ValueArrival(
            marker_reference=f"profile:exonerado:{year}",
            endpoints=tuple(
                M303Exonerado390EndpointValue(
                    casilla_id=validated_casilla_id(item, surface="S51 exonerado fixture"),
                    value=Decimal("0"),
                    producer_reference=f"annual:{year}:{item}",
                )
                for item in _EXONERADO_IDS
            ),
        ),
        prorrata_activities_applicable=True,
        prorrata_register=register,
        differentiated_sectors_applicable=True,
        differentiated_sectors=M303DifferentiatedSectorValueArrival(
            prorrata_register=register,
            contributions=contributions,
            bienes_register=BienesInversionIvaRegister(),
            regularisation_result=regularisation,
        ),
        regimen_simplificado_applicable=True,
        regimen_simplificado=simplified,
    )


@pytest.mark.parametrize(
    ("year", "period_code", "source_ref", "epoch"),
    (
        (2023, "4T", "aeat-dr-303-2023", "2023"),
        (2024, "2T", "aeat-dr-303-2024-early", "2024-early"),
        (2024, "3T", "aeat-dr-303-2024-late", "2024-late"),
        (2025, "4T", "aeat-dr-303-2025", "2025"),
        (2026, "4T", "aeat-dr-303-2026", "2026"),
    ),
)
def test_all_units_complete_cross_the_public_boundary_for_every_epoch(
    year: int,
    period_code: str,
    source_ref: str,
    epoch: str,
    tmp_path: Path,
) -> None:
    period = Period.from_year_and_code(year, period_code)
    provider = build_runtime_schema_provider(filing_year=year, period=period, modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="S51 proof"),
        inputs={
            "07": Decimal("0"),
            "iva.soportado.interiores": Decimal("0"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    producer_snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoria Prueba"),
        model_profile=ModeloIVAProfile(),
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
    output_path = tmp_path / f"m303-{year}-{period_code}.txt"

    with pytest.raises(FilingExportError, match="no complete export_layouts definition"):
        export_draft(
            draft,
            output_path=output_path,
            producer_snapshot=producer_snapshot,
            schema_provider=provider,
            m303_applicability=_complete_envelope(year, source_ref, epoch),
        )

    assert not output_path.exists()

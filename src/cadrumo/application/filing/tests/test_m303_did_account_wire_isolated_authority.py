"""Isolated M303 DID account-wire proof against the official 2026 design."""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as _prov_date
from decimal import Decimal

import pytest

from ....core.filing_projection_ref import (
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFact,
)
from ....core.modelo import Modelo
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.product_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, RegistroRegularizacionResult
from ....domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionParameterProvenance,
    BienesInversionRegularizacionParameters,
)
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_base import CasillaDataType, ThresholdComparison
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
)
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    TaxpayerProfile,
)
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.schema import ModeloDraft
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_evidence import M303Exonerado390FilingEvidence
from ....domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoFilingEvidence
from ....domain.prorrata_register.register import ProrrataRegister
from ....domain.submission.models import ModeloDraftStatus
from ...aggregation.m303_arrivals import M303ProrrataTransitionArrival, M303SupplierRegimeArrival
from ...calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from ..export import render_filing_envelope
from ..export_envelope import FilingEnvelopeRenderRequest
from ..producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    M303FilingFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from ..runtime import RegistrySchemaAccessor, collection_from_snapshot, subview_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: Provenance stamped onto directly-constructed projections in this module. A
#: result must name the registry declaration its figures came from; these tests
#: build results by hand rather than by projection, so they state it explicitly.
_PROVENANCE = BienesInversionParameterProvenance(
    modelo_id="303",
    revision_id="2025",
    parameter_ids=(
        "m303-bien-inversion-ventana-anos-mueble",
        "m303-bien-inversion-ventana-anos-inmueble",
        "m303-bien-inversion-divisor-mueble",
        "m303-bien-inversion-divisor-inmueble",
        "m303-bien-inversion-regularizacion-umbral-puntos",
    ),
    resolved_on=_prov_date(2025, 6, 1),
)


#: The resolved bundle the regularisation result above was produced under. The
#: oracle compares the result's carried provenance against this, so the two must
#: name the same declaration.
_PARAMS = BienesInversionRegularizacionParameters(
    ventana_anos_mueble=4,
    ventana_anos_inmueble=9,
    divisor_mueble=Decimal("5"),
    divisor_inmueble=Decimal("10"),
    umbral_puntos=Decimal("10"),
    umbral_comparison=ThresholdComparison.EXCLUSIVE,
    provenance=_PROVENANCE,
)


def _params_for(year: int) -> BienesInversionRegularizacionParameters:
    """The bundle, resolved for ``year``.

    The projection refuses a bundle resolved for a different filing year, so a
    fixture cannot pin one year and be applied to another.
    """
    return _PARAMS.model_copy(
        update={"provenance": _PARAMS.provenance.model_copy(update={"resolved_on": _prov_date(year, 12, 31)})}
    )


_SOURCE_REF = "aeat-dr-303-2026"
_SOURCE_SHA256 = "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b"
_REVISION_ID = "2026-y-siguientes"
_TAXPAYER_TAX_ID = "12345678Z"
_REFUND_IBAN = "GB82WEST12345698765432"
_CHARGE_IBAN = "ES9121000418450200051332"
_LEGAL_REFS = '"ley-37-1992:art-88", "ley-37-1992:art-90", "ley-37-1992:art-91", "ley-37-1992:art-92", "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"'

#: ``ordinal`` is the PRINTED label the official design carries, preserved
#: verbatim as text rather than parsed into an arithmetic value.
_OFFICIAL_DID_ROWS = (
    ("1", 1, 2, "An", 'Constante "<T"'),
    ("2", 3, 3, "Num", 'Constante "303"'),
    ("3", 6, 5, "An", 'Constante "DID00"'),
    ("4", 11, 1, "An", 'Constante ">"'),
    ("5", 12, 11, "An", "Nota 3"),
    ("6", 23, 34, "An", "Nota 3"),
    ("7", 57, 70, "An", None),
    ("8", 127, 35, "An", None),
    ("9", 162, 30, "An", None),
    ("10", 192, 2, "An", None),
    ("11", 194, 1, "Num", '"0", "1", "2", "3" Nota 2, Nota 3'),
    ("12", 195, 617, "An", None),
    ("13", 812, 12, "An", 'Constante "</T303DID00>"'),
)

_DP30300_PREFIX_LENGTHS = (2, 3, 1, 4, 2, 5, 5, 70, 4, 4, 9, 213, 6)


def _required_iae_epigrafe(value: str | None) -> str:
    if value is None:
        raise AssertionError("non-agricultural activity must declare an IAE epigrafe")
    return value


def _m303_2026_snapshot() -> RegistrySnapshot:
    """Load the real 2026 revision from the published authority artifact."""
    return bundled_authority().snapshot(Modelo.M303.value, filing_year=2026, period="1T")


#: Modelo 303 prints the shared envelope grammar in its thirteen-row spelling:
#: every role except the composed opening tag, which is the ALTERNATIVE spelling
#: of the six rows this design prints separately.
_M303_PREFIX_ROLES: tuple[FilingEnvelopePrefixRole, ...] = tuple(
    role for role in FilingEnvelopePrefixRole if role is not FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
)


def _filing_envelope_layout(
    snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
) -> tuple[RegistrySnapshot, ExportLayoutDefinition]:
    """Attach only the reviewed static DP30300 grammar to the test-owned layout."""
    envelope = FilingEnvelopeDefinition(
        source_ref=_SOURCE_REF,
        source_sha256=_SOURCE_SHA256,
        record_identity="DP30300",
        prefix_extent=328,
        prefix_fields=tuple(
            FilingEnvelopePrefixFieldDeclaration(role=role, length=length)
            for role, length in zip(_M303_PREFIX_ROLES, _DP30300_PREFIX_LENGTHS, strict=True)
        ),
        body_record_ids=(layout.records[0].id,),
        product_identity_requirement="aeat-product-software-identity-v1",
        closer_derivation="relative-closer-v1",
        total_derivation="emitted-byte-total-v1",
    )
    envelope_layout = layout.model_copy(update={"filing_envelope": envelope})
    revision = snapshot.revision.model_copy(update={"export_layouts": (envelope_layout,)})
    return snapshot.model_copy(update={"revision": revision}), envelope_layout


def _projection_rows_envelope_layout(
    snapshot: RegistrySnapshot,
    *,
    required: bool,
) -> tuple[RegistrySnapshot, ExportLayoutDefinition]:
    """Attach one canonical regimen-simplificado repeated record to a real 2026 snapshot."""
    projection_ref = M303RegimenSimplificadoActivityProjectionRef(
        projection_kind="m303_regimen_simplificado_activity",
        cohort=M303RegimenSimplificadoCohort.NO_AGRICOLA,
        slot=1,
        field=M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
    )
    legal_ref = snapshot.revision.legal_refs[0]
    record = ExportRecordDefinition(
        id="test-owned-m303-projection-rows",
        record_type="REGIMEN_SIMPLIFICADO",
        order=1,
        encoding="iso-8859-1",
        line_ending="none",
        required=required,
        repeat="projection_rows",
        fields=(
            ExportFieldDefinition(
                id="test-owned-m303-projection-iae",
                offset=1,
                length=10,
                kind=CasillaFieldKind.PROJECTION,
                projection_ref=projection_ref,
                data_type=CasillaDataType.TEXT,
                required=True,
                padding="right_space",
                justification="left",
                signed=False,
                legal_refs=(legal_ref,),
                source_refs=(_SOURCE_REF,),
            ),
        ),
    )
    layout = ExportLayoutDefinition(
        id="test-owned-m303-projection-rows-envelope",
        format="fixed_width",
        records=(record,),
        legal_refs=(legal_ref,),
        source_refs=(_SOURCE_REF,),
    )
    return _filing_envelope_layout(snapshot, layout)


def _product_software_identity() -> AeatProductSoftwareIdentity:
    return AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:isolated-m303-envelope",
                digest="a" * 64,
            ),
        ),
    )


def _schema_provider_for_snapshot(snapshot: RegistrySnapshot) -> RegistrySchemaAccessor:
    """Project the test-owned validated snapshot through the real runtime accessor."""
    modelo_id = snapshot.modelo.id
    return RegistrySchemaAccessor(
        collections={modelo_id: collection_from_snapshot(snapshot)},
        subviews={modelo_id: subview_from_snapshot(snapshot)},
        snapshots={modelo_id: snapshot},
        sources=snapshot.sources,
    )


def _m303_did_producer_snapshot(
    disposition: ResultDisposition,
    *,
    registry_snapshot: RegistrySnapshot,
    non_agricultural_activity_count: int = 0,
) -> FilingProducerSnapshot:
    """Build real approved-draft producer authority for the isolated DID layout."""
    period = Period.from_year_and_code(2026, "1T")
    taxpayer = _taxpayer_profile()
    iva_profile = taxpayer.iva
    assert iva_profile is not None
    return build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=taxpayer.tax_id,
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="María",
            surnames="García López",
            full_name="María García López",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Ejemplo"),
        model_profile=iva_profile,
        elections=_elections(disposition),
        amendment_evidence=None,
        refund_account=iva_profile.refund_account,
        charge_account=iva_profile.charge_account,
        m303_filing_facts=_m303_filing_facts(
            period,
            registry_snapshot=registry_snapshot,
            non_agricultural_activity_count=non_agricultural_activity_count,
        ),
    )


def _taxpayer_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAXPAYER_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        iva={
            "tax_territory": M303TaxTerritory.COMMON_REGIME,
            "regime_composition": M303RegimeComposition.GENERAL,
            "redeme_enrolled": False,
            "cash_accounting_regime_enrolled": False,
            "voluntary_sii_enrolled": False,
            "hydrocarbon_deposit_advance_payment_deduction_entitled": False,
            "refund_account": {
                "iban": _REFUND_IBAN,
                "swift_bic": "DEUTDEFF",
                "bank_name": "Refund Bank",
                "bank_address": "Refund Street 1",
                "bank_city": "Berlin",
                "bank_country_code": "DE",
            },
            "charge_account": {"iban": _CHARGE_IBAN},
        },
    )


def _m303_filing_facts(
    period: Period,
    *,
    registry_snapshot: RegistrySnapshot,
    non_agricultural_activity_count: int = 0,
) -> M303FilingFacts:
    """Real M303 facts for the DID page and optional canonical repeated projection rows."""
    reference = FilingEvidenceReference(reference="test:did-wire:m303-facts")
    scope = M303RegimenSimplificadoScopeDecision(
        scope=(
            M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED
            if non_agricultural_activity_count
            else M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED
        ),
    )
    bienes_register = BienesInversionIvaRegister()
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    annual_activities = tuple(
        activity
        for activity in regimen_snapshot.orden.activities
        if activity.kind == "no_agricola" and activity.iae_epigrafe is not None
    )[:non_agricultural_activity_count]
    assert len(annual_activities) == non_agricultural_activity_count
    regimen_rows = RegimenSimplificadoFilingRows(
        ejercicio=period.filing_year,
        activities=tuple(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=period.filing_year,
                activity_id=activity.orden_id,
                iae_epigrafe=_required_iae_epigrafe(activity.iae_epigrafe),
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity,
                        declared_quantity=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=reference,
                    )
                    for _fact in activity.applicable_fact_identities
                ),
                evidence_reference=reference,
            )
            for activity in annual_activities
        ),
    )
    regimen_evidence = M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=regimen_rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=regimen_rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            authority=bundled_authority(),
        ),
    )
    return M303FilingFacts(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        insolvency=None,
        period=period,
        exonerado_390=M303Exonerado390FilingEvidence(
            applicable=False,
            applicability_reference=reference,
            endpoints=(),
            activity_rows=(),
            operaciones_terceros_declarables=None,
            operaciones_terceros_reference=None,
        ),
        regimen_simplificado=regimen_evidence,
        regimen_simplificado_result=regimen_evidence.calculation_result,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=False,
            source_ledger_ids=(),
        ),
        prorrata_transition=M303ProrrataTransitionArrival(
            period=period,
            transition=None,
            register_evidence=(),
        ),
        prorrata_register=ProrrataRegister(),
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=RegistroRegularizacionResult(
            regularizacion_year=period.filing_year,
            rows=(),
            proposed_casilla_43=Decimal("0"),
            computed_count=0,
            pending_percentage_count=0,
            sector_contributions=(),
            parameters_provenance=_params_for(period.filing_year).provenance,
        ),
        bienes_parameters=_params_for(period.filing_year),
    )


def _elections(disposition: ResultDisposition) -> FilingElectionFacts:
    return FilingElectionFacts(
        result_disposition=disposition,
        payment=(
            PaymentElection.DOMICILIACION if disposition is ResultDisposition.DOMICILIACION else PaymentElection.INGRESO
        ),
        refund=RefundElection.DEVOLVER if disposition is ResultDisposition.DEVOLUCION else RefundElection.COMPENSAR,
        prior_domiciliation=PriorDomiciliationElection.KEEP,
    )


def _draft() -> ModeloDraft:
    period = Period.from_year_and_code(2026, "1T")
    timestamp = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    return ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id=_TAXPAYER_TAX_ID,
        subject_tax_id=_TAXPAYER_TAX_ID,
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id=_REVISION_ID,
            modelo_year=period.filing_year,
            period=period.registry_token,
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=f"registry:303:{_REVISION_ID}",
    )


@pytest.mark.parametrize(
    ("non_agricultural_activity_count", "expected_occurrences"),
    (
        (0, ()),
        (1, (("test-owned-m303-projection-rows", 1),)),
        (
            3,
            (
                ("test-owned-m303-projection-rows", 1),
                ("test-owned-m303-projection-rows", 2),
            ),
        ),
    ),
)
def test_m303_envelope_preserves_canonical_zero_one_many_projection_row_occurrences(
    non_agricultural_activity_count: int,
    expected_occurrences: tuple[tuple[str, int], ...],
) -> None:
    registry_snapshot, layout = _projection_rows_envelope_layout(
        _m303_2026_snapshot(),
        required=False,
    )
    producer_snapshot = _m303_did_producer_snapshot(
        ResultDisposition.DEVOLUCION,
        registry_snapshot=registry_snapshot,
        non_agricultural_activity_count=non_agricultural_activity_count,
    )

    result = render_filing_envelope(
        FilingEnvelopeRenderRequest(
            registry_snapshot=registry_snapshot,
            layout=layout,
            draft=_draft(),
            producer_snapshot=producer_snapshot,
            prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            product_software_identity=_product_software_identity(),
        ),
    )

    assert tuple((item.record_id, item.occurrence) for item in result.occurrences) == expected_occurrences
    assert result.payload == result.prefix + b"".join(item.payload for item in result.occurrences) + result.closer


def test_m303_envelope_refuses_a_required_projection_record_without_an_applicable_occurrence() -> None:
    registry_snapshot, layout = _projection_rows_envelope_layout(
        _m303_2026_snapshot(),
        required=True,
    )
    producer_snapshot = _m303_did_producer_snapshot(
        ResultDisposition.DEVOLUCION,
        registry_snapshot=registry_snapshot,
    )

    with pytest.raises(FilingExportValidationError, match="required projection record"):
        render_filing_envelope(
            FilingEnvelopeRenderRequest(
                registry_snapshot=registry_snapshot,
                layout=layout,
                draft=_draft(),
                producer_snapshot=producer_snapshot,
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                product_software_identity=_product_software_identity(),
            ),
        )


def test_production_m303_generated_authority_is_visible_at_the_filing_boundary() -> None:
    """The filing boundary now receives the generated 2026 layout.

    This replaces the retired absence assertion.  The complete layout remains
    owned by the hash-pinned generated tree; this consumer only proves that the
    selected runtime snapshot exposes it unchanged.
    """
    registry_snapshot = _m303_2026_snapshot()
    (layout,) = registry_snapshot.revision.export_layouts
    assert layout.id == "generated-modelo-303-2026-y-siguientes-fichero"
    assert layout.filing_envelope is not None
    assert {field.kind for record in layout.records for field in record.fields} == {
        CasillaFieldKind.CASILLA,
        CasillaFieldKind.COMPUTED,
        CasillaFieldKind.DRAFT,
        CasillaFieldKind.FILLER,
        CasillaFieldKind.HEADER,
        CasillaFieldKind.LITERAL,
        CasillaFieldKind.PROJECTION,
    }
    assert tuple(record.id for record in layout.records) == (
        "m303-declaration",
        "m303-regimen-simplificado",
        "m303-resultados",
        "m303-exonerado-390",
        "m303-prorrata-deducciones",
        "m303-domiciliacion",
    )
    published_regimen_record = next(record for record in layout.records if record.id == "m303-regimen-simplificado")
    assert published_regimen_record.repeat == "projection_rows"
    regimen_indicator_field = next(
        field for field in published_regimen_record.fields if field.id == "m303-2026.dp30302.f023"
    )
    regimen_record = published_regimen_record.model_copy(update={"fields": (regimen_indicator_field,)})
    envelope = layout.filing_envelope
    assert envelope is not None

    # The other generated projection fields have independent value-arrival
    # contracts. Keep this public-render proof to the real no-agricultural
    # auxiliary-indicator field rather than manufacturing those unrelated facts.
    regimen_layout = layout.model_copy(
        update={
            "records": (regimen_record,),
            "filing_envelope": envelope.model_copy(update={"body_record_ids": (regimen_record.id,)}),
        },
    )
    regimen_snapshot = registry_snapshot.model_copy(
        update={
            "revision": registry_snapshot.revision.model_copy(update={"export_layouts": (regimen_layout,)}),
        },
    )

    producer_snapshot = _m303_did_producer_snapshot(
        ResultDisposition.DEVOLUCION,
        registry_snapshot=regimen_snapshot,
        non_agricultural_activity_count=1,
    )
    rendered = render_filing_envelope(
        FilingEnvelopeRenderRequest(
            registry_snapshot=regimen_snapshot,
            layout=regimen_layout,
            draft=_draft(),
            producer_snapshot=producer_snapshot,
            prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            product_software_identity=_product_software_identity(),
        ),
    )
    assert tuple((item.record_id, item.occurrence) for item in rendered.occurrences) == ((regimen_record.id, 1),)

    malformed_layout = regimen_layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(update={"repeat": None}) if record.id == regimen_record.id else record
                for record in regimen_layout.records
            ),
        },
    )
    malformed_snapshot = regimen_snapshot.model_copy(
        update={
            "revision": regimen_snapshot.revision.model_copy(update={"export_layouts": (malformed_layout,)}),
        },
    )
    with pytest.raises(
        FilingExportValidationError,
        match="regimen-simplificado projection record must repeat projection_rows",
    ):
        render_filing_envelope(
            FilingEnvelopeRenderRequest(
                registry_snapshot=malformed_snapshot,
                layout=malformed_layout,
                draft=_draft(),
                producer_snapshot=_m303_did_producer_snapshot(
                    ResultDisposition.DEVOLUCION,
                    registry_snapshot=malformed_snapshot,
                    non_agricultural_activity_count=1,
                ),
                prior_domiciliation_election=PriorDomiciliationElection.KEEP,
                product_software_identity=_product_software_identity(),
            ),
        )

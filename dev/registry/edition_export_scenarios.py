"""The filing scenarios the edition round-trip gate renders each modelo's export bytes from.

The round-trip gate compares the bytes one draft renders through a reference
tree and through a migrated tree. It needs, for every edition with an export
surface, a filing context that selects exactly that edition and a producer
snapshot the canonical export path accepts. This module is the one place those
scenarios are declared: the migration tool and the round-trip tests read them
from :func:`edition_export_scenarios`.

Every scenario is synthetic. The taxpayer, presenter, developer and account
identities are documentation placeholders, never a real person or account.

A scenario states filing inputs, never expected output. Its bytes are only ever
compared with the bytes the same scenario renders through the other tree, so
what it proves is that a migration left the export surface unchanged.

Modelo 303
----------
Modelo 303's export path, for the layouts from 2023 onwards, refuses an
envelope in which the regimen-simplificado or exonerado-390 record emits no
occurrence, or the prorrata/deducciones record leaves a declared projection
reference unemitted. So each scenario supplies facts that make every record
family emit one occurrence -- one non-agricultural
simplified-regime activity from the edition's own Orden, applicable
exonerado-390 evidence, a prorrata register with five activity slots and two
differentiated sectors, and a domiciliation charge account -- plus the
envelope's prior-domiciliation election and product/software identity. Facts
that depend on the edition are resolved from it: the Orden activity, the
capital-goods regularisation parameters (for the scenario period's last day,
which lies inside the edition's window) and the prior year's snapshot the
prorrata register carries forward.

Modelo 390
----------
The annual resumen anual files one period, ``0A``, so each edition is rendered
for its own year. Its repeated page rows are source-shaped arrivals the
producer snapshot owns rather than draft inputs, and none is supplied: every
repeated record is therefore empty, and the compared bytes judge the edition's
base layout and envelope. The 2023 edition names no predecessor, so the gate
does not require its bytes.

Modelos with no draft input
---------------------------
Modelos 714, 322, 490, 309, 308, 123, 604, 151, 165, 184, 202, 180, 185, 210,
270, 341, 353 and 576 route through one shared
builder, :func:`general_export_scenario`. None of them registers an envelope
policy -- Modelo 303 is the only modelo that does -- and none declares a
required repeated record, so an empty draft leaves no required occurrence
unemitted and the compared bytes judge each edition's base layout and envelope,
as Modelo 390's do. Each carries the full set of its export-bearing editions, so
no edition of a listed modelo reports missing while its siblings report clean.

Where it stops
--------------
- One quarterly period per edition. A period whose facts would change which
  records emit (a fourth quarter's final-period prorrata coverage, a monthly
  filer) is not rendered.
- Modelo 347 has no scenario: its layout declares a required repeated record,
  so an empty draft leaves a required occurrence unemitted and the export path
  refuses it. Supplying that occurrence needs source-shaped arrivals this module
  has no honest synthetic form for, so the modelo stays undeclared.
- Modelo 303's 2022 edition has no scenario: the export path refuses its layout,
  whose regimen-simplificado record does not repeat per projection row. It is
  the modelo's first edition and names no predecessor, so the gate does not
  require its bytes.
- Draft construction and these facts read the bundled registry, as the gate
  documents; they select the edition, and the bytes judge its export surface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from functools import cache, partial
from typing import Final

from cadrumo.application.aggregation.iva_ledger import (
    IvaDifferentiatedDeductionContribution,
)
from cadrumo.application.aggregation.m303_arrivals import (
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
)
from cadrumo.application.calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    M303FilingFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.filing_projection_ref import M303RegimenSimplificadoFact
from cadrumo.core.iva_deduction_fact import IvaDeductionFactKind
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.product_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from cadrumo.core.prorrata_register import (
    ProrrataActivityRowType,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister, RegistroRegularizacionResult
from cadrumo.domain.bienes_inversion.regularizacion_parameters import resolve_bienes_inversion_regularizacion_parameters
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.deadlines.models import ChargeAccount, M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from cadrumo.domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from cadrumo.domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoFilingEvidence
from cadrumo.domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)

from .compiler.authority import compiled_bundled_authority
from .edition_round_trip import SYNTHETIC_TAX_ID, EditionExportScenario

__all__ = [
    "M123_SCENARIO_PERIODS",
    "M131_SCENARIO_PERIODS",
    "M151_SCENARIO_PERIODS",
    "M165_SCENARIO_PERIODS",
    "M180_SCENARIO_PERIODS",
    "M184_SCENARIO_PERIODS",
    "M185_SCENARIO_PERIODS",
    "M202_SCENARIO_PERIODS",
    "M210_SCENARIO_PERIODS",
    "M270_SCENARIO_PERIODS",
    "M303_SCENARIO_PERIODS",
    "M308_SCENARIO_PERIODS",
    "M309_SCENARIO_PERIODS",
    "M322_SCENARIO_PERIODS",
    "M341_SCENARIO_PERIODS",
    "M353_SCENARIO_PERIODS",
    "M390_SCENARIO_PERIODS",
    "M490_SCENARIO_PERIODS",
    "M576_SCENARIO_PERIODS",
    "M604_SCENARIO_PERIODS",
    "M714_SCENARIO_PERIODS",
    "edition_export_scenarios",
    "general_export_scenario",
    "m131_export_scenario",
    "m303_export_scenario",
    "m390_export_scenario",
]

#: The quarter each Modelo 303 edition is rendered for; each selects exactly that edition.
M303_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2023": Period.from_year_and_code(2023, "1T"),
    "2024-hasta-08-y-2t": Period.from_year_and_code(2024, "1T"),
    "2024-desde-09-y-3t": Period.from_year_and_code(2024, "3T"),
    "2025": Period.from_year_and_code(2025, "1T"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "1T"),
}
#: The annual period each Modelo 390 edition is rendered for; 390 files only ``0A``.
M390_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The quarter each Modelo 131 edition is rendered for.
M131_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2023": Period.from_year_and_code(2023, "1T"),
    "2024": Period.from_year_and_code(2024, "1T"),
    "2025": Period.from_year_and_code(2025, "1T"),
    "2026": Period.from_year_and_code(2026, "1T"),
}
#: The annual period each Modelo 714 edition is rendered for; 714 files only ``0A``.
M714_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021": Period.from_year_and_code(2021, "0A"),
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The month each Modelo 322 edition is rendered for; 322 is a monthly group filer.
M322_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2008-2022": Period.from_year_and_code(2022, "01"),
    "2023": Period.from_year_and_code(2023, "01"),
    "2024-2025": Period.from_year_and_code(2024, "01"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "01"),
}
#: The quarter each Modelo 490 edition is rendered for; the 2022 editions split at 2T.
M490_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021": Period.from_year_and_code(2021, "1T"),
    "2022-1t": Period.from_year_and_code(2022, "1T"),
    "2022-2t-4t": Period.from_year_and_code(2022, "2T"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "1T"),
}
#: The ad-hoc period each Modelo 309 edition is rendered for; 309 is event-driven.
M309_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2004-2015": Period.from_year_and_code(2004, "AD-HOC"),
    "2016-2017": Period.from_year_and_code(2016, "AD-HOC"),
    "2018-2022": Period.from_year_and_code(2018, "AD-HOC"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "AD-HOC"),
}
#: The ad-hoc period Modelo 308's one export-bearing edition is rendered for.
M308_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-y-siguientes": Period.from_year_and_code(2019, "AD-HOC"),
}
#: The quarter each Modelo 123 edition is rendered for.
M123_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2023": Period.from_year_and_code(2019, "1T"),
    "2024-y-siguientes": Period.from_year_and_code(2024, "1T"),
}
#: The month each Modelo 604 edition is rendered for.
M604_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021-2023": Period.from_year_and_code(2021, "01"),
    "2024-y-siguientes": Period.from_year_and_code(2024, "01"),
}
#: The annual period each Modelo 151 edition is rendered for.
M151_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2015-2022": Period.from_year_and_code(2015, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 165 edition is rendered for.
M165_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2016-2022": Period.from_year_and_code(2016, "0A"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "0A"),
}
#: The annual period each Modelo 184 edition is rendered for.
M184_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2023-2024": Period.from_year_and_code(2023, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The payment period each Modelo 202 edition is rendered for; 202 files ``1P``-``3P``.
M202_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2022": Period.from_year_and_code(2019, "1P"),
    "2023-2024": Period.from_year_and_code(2023, "1P"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "1P"),
}
#: The annual period each Modelo 180 edition is rendered for.
M180_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2022": Period.from_year_and_code(2019, "0A"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "0A"),
}
#: The month Modelo 185's one export-bearing edition is rendered for.
M185_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2026, "01"),
}
#: The annual period each Modelo 210 edition is rendered for.
M210_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "0A"),
}
#: The annual period each Modelo 270 edition is rendered for.
M270_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2013-2022": Period.from_year_and_code(2013, "0A"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "0A"),
}
#: The quarter each Modelo 341 edition is rendered for.
M341_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2005-2015": Period.from_year_and_code(2005, "1T"),
    "2016-y-siguientes": Period.from_year_and_code(2016, "1T"),
}
#: The month each Modelo 353 edition is rendered for; the 2026 edition starts at ``02``.
M353_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021-2025": Period.from_year_and_code(2021, "01"),
    "2026-desde-02": Period.from_year_and_code(2026, "02"),
}
#: The annual period Modelo 576's one export-bearing edition is rendered for.
M576_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2008-y-siguientes": Period.from_year_and_code(2008, "0A"),
}


@cache
def _presenter() -> PresenterIdentity:
    """Build the example presenter on first use.

    PresenterIdentity validates its tax_id through the published authority, so
    constructing one at module scope makes importing this module — and every
    module that imports it, the edition migration tool included — fail outright
    whenever the published artifact is stale. Building it on demand keeps the
    dependency where it belongs, at the scenario that actually renders.
    """
    return PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba")


_TAXPAYER: Final = TaxpayerIdentityFacts(legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba")
#: The Spanish IBAN published as a format example; it identifies no real account.
_CHARGE_IBAN: Final = "ES9121000418450200051332"


@cache
def _m390_product_software_identity() -> AeatProductSoftwareIdentity:
    """Build Modelo 390's example software identity on first use; see :func:`_presenter`."""
    return AeatProductSoftwareIdentity(
        program_identifier="C390",
        developer_tax_id="Y0000001S",
        evidence=(AeatProductSoftwareEvidence(reference="edition-round-trip:m390-software", digest="b" * 64),),
    )


@cache
def _product_software_identity() -> AeatProductSoftwareIdentity:
    """Build Modelo 303's example software identity on first use; see :func:`_presenter`."""
    return AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(reference="aeat-software-registration:edition-round-trip", digest="a" * 64),
        ),
    )


_EVIDENCE: Final = FilingEvidenceReference(reference="edition-round-trip:m303-facts")
_M303_EXONERADO_ENDPOINT: Final = validated_casilla_id("79", surface="edition round-trip scenario")
_M303_EXONERADO_ACTIVITY_SLOTS: Final = range(1, 7)
_M303_PRORRATA_ACTIVITY_SLOTS: Final = range(1, 6)
_M303_DIFFERENTIATED_SECTORS: Final = (
    SectorDefinition(sector_id="a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",)),
    SectorDefinition(sector_id="b", letra=SectorDiferenciadoLetra.B, member_activity_codes=("6820",)),
)
_M303_NON_AGRICULTURAL: Final = "no_agricola"


def edition_export_scenarios(modelo_id: str) -> Mapping[str, EditionExportScenario]:
    """Every declared export scenario for ``modelo_id``, keyed by the edition it selects; empty when none is."""
    declared = _DECLARED_SCENARIOS.get(modelo_id)
    if declared is None:
        return dict[str, EditionExportScenario]()
    builder, periods = declared
    return {revision_id: builder(period) for revision_id, period in periods.items()}


# ── modelo 303 ──────────────────────────────────────────────────────────────


def m303_export_scenario(period: Period) -> EditionExportScenario:
    """A Modelo 303 quarterly scenario in which every record family emits one occurrence."""
    return EditionExportScenario(
        period=period,
        inputs={
            "iva.repercutido.general": Decimal("210.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        },
        producer_snapshot=partial(_m303_producer_snapshot, period),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=_product_software_identity(),
    )


def _m303_producer_snapshot(period: Period) -> FilingProducerSnapshot:
    authority = compiled_bundled_authority()
    registry_snapshot = authority.snapshot(
        str(Modelo("303")), filing_year=period.filing_year, period=period.registry_token
    )
    profile = ModeloIVAProfile(
        tax_territory=M303TaxTerritory.COMMON_REGIME,
        regime_composition=M303RegimeComposition.GENERAL,
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        charge_account=ChargeAccount(iban=_CHARGE_IBAN),
    )
    return build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=profile,
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.DOMICILIACION,
            payment=PaymentElection.DOMICILIACION,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=profile.charge_account,
        m303_filing_facts=_m303_filing_facts(period, authority=authority, registry_snapshot=registry_snapshot),
    )


def _m303_filing_facts(
    period: Period, *, authority: ValidatedRegistryAuthority, registry_snapshot: RegistrySnapshot
) -> M303FilingFacts:
    regimen = _m303_regimen_simplificado_evidence(period, authority=authority, registry_snapshot=registry_snapshot)
    parameters = resolve_bienes_inversion_regularizacion_parameters(
        registry_snapshot.revision, modelo_id=str(Modelo("303")), filing_period_date=period.end_date
    )
    return M303FilingFacts(
        joint_return_elected=False,
        annual_volume_nonzero=False,
        insolvency=None,
        period=period,
        exonerado_390=M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=_EVIDENCE,
            endpoints=(
                M303Exonerado390EndpointEvidence(
                    casilla_id=_M303_EXONERADO_ENDPOINT, value=Decimal("1.00"), evidence_reference=_EVIDENCE
                ),
            ),
            activity_rows=tuple(
                M303Exonerado390ActivityRowEvidence(
                    slot=slot, codigo_actividad="A01", epigrafe_iae=f"419{slot}", evidence_reference=_EVIDENCE
                )
                for slot in _M303_EXONERADO_ACTIVITY_SLOTS
            ),
            operaciones_terceros_declarables=False,
            operaciones_terceros_reference=_EVIDENCE,
        ),
        regimen_simplificado=regimen,
        regimen_simplificado_result=regimen.calculation_result,
        supplier_regime=M303SupplierRegimeArrival(
            period=period, recipient_of_cash_accounting_operations=False, source_ledger_ids=()
        ),
        prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
        prorrata_register=_m303_prorrata_register(period, authority=authority),
        differentiated_contributions=_m303_differentiated_contributions(),
        bienes_register=BienesInversionIvaRegister(),
        regularisation_result=RegistroRegularizacionResult(
            regularizacion_year=period.filing_year,
            rows=(),
            proposed_casilla_43=Decimal("0"),
            computed_count=0,
            pending_percentage_count=0,
            sector_contributions=(),
            parameters_provenance=parameters.provenance,
        ),
        bienes_parameters=parameters,
    )


def _m303_regimen_simplificado_evidence(
    period: Period, *, authority: ValidatedRegistryAuthority, registry_snapshot: RegistrySnapshot
) -> M303RegimenSimplificadoFilingEvidence:
    """One non-agricultural activity from the edition's own Orden, so the repeated record emits once."""
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot, scope_decision=scope
    )
    activity, epigrafe = next(
        (activity, activity.iae_epigrafe)
        for activity in regimen_snapshot.orden.activities
        if activity.kind == _M303_NON_AGRICULTURAL and activity.iae_epigrafe is not None
    )
    rows = RegimenSimplificadoFilingRows(
        ejercicio=period.filing_year,
        activities=(
            ActividadNoAgricolaSimplificado(
                orden_id=activity.orden_id,
                ejercicio=period.filing_year,
                activity_id=activity.orden_id,
                iae_epigrafe=epigrafe,
                auxiliary_activity_indicator=activity.auxiliary_activity_indicator,
                modulos=tuple(
                    EntradaModuloSimplificado(
                        module_identity=module.identity, declared_quantity=Decimal("1"), evidence_reference=_EVIDENCE
                    )
                    for module in activity.modulos
                ),
                facts=tuple(
                    HechoActividadSimplificado(
                        fact=M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
                        value=Decimal("1"),
                        evidence_reference=_EVIDENCE,
                    )
                    for _identity in activity.applicable_fact_identities
                ),
                evidence_reference=_EVIDENCE,
            ),
        ),
    )
    return M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_2024_eligibility=None,
            authority=authority,
        ),
    )


def _m303_prorrata_register(period: Period, *, authority: ValidatedRegistryAuthority) -> ProrrataRegister:
    """A general-regime register carrying the prior year's definitive percentage for the common and both sectors."""
    prior_snapshot_ref = authority.snapshot(
        str(Modelo("303")), filing_year=period.filing_year - 1, period="4T"
    ).snapshot_ref
    return ProrrataRegister(
        sector_definitions=_M303_DIFFERENTIATED_SECTORS,
        entries=tuple(
            ProrrataRegisterEntry(
                ejercicio=period.filing_year,
                sector_id=sector_id,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=Decimal("50"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_registry_snapshot_refs=(prior_snapshot_ref,),
            )
            for sector_id in (None, *(sector.sector_id for sector in _M303_DIFFERENTIATED_SECTORS))
        ),
        activity_rows=tuple(
            ProrrataActivityRow(
                ejercicio=period.filing_year,
                activity_id=f"edition-round-trip-prorrata-{slot}",
                slot=slot,
                cnae_code=f"47{slot}",
                operaciones_total=Decimal("100"),
                operaciones_con_derecho=Decimal("50"),
                prorrata_type=ProrrataActivityRowType.GENERAL,
                percentage=Decimal("50"),
                evidence_reference=f"edition-round-trip:prorrata:{slot}",
            )
            for slot in _M303_PRORRATA_ACTIVITY_SLOTS
        ),
    )


def _m303_differentiated_contributions() -> tuple[IvaDifferentiatedDeductionContribution, ...]:
    """One contribution per deduction kind the differentiated sectors declare, in each sector."""
    kinds = tuple(
        kind for kind in IvaDeductionFactKind if kind is not IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    )
    return tuple(
        IvaDifferentiatedDeductionContribution(
            sector_id=sector.sector_id,
            deduction_fact_kind=kind,
            source_ledger_ids=(f"edition-round-trip:{sector.sector_id}:{index}",),
            base_amount=Decimal("100"),
            deducible_iva_amount=Decimal("20"),
        )
        for sector in _M303_DIFFERENTIATED_SECTORS
        for index, kind in enumerate(kinds, start=1)
    )


# ── modelo 390 ───────────────────────────────────────────────────────────────


def m390_export_scenario(period: Period) -> EditionExportScenario:
    """A Modelo 390 annual scenario: the resumen anual's own declared figures.

    390 is the annual IVA summary. It carries no payment or refund, so the
    filing disposition is the neutral one and no account is selected; the
    repeated page rows are the source-shaped arrivals the producer snapshot
    owns, and none is supplied here, so every repeated record is empty and the
    bytes judge the edition's base layout.
    """
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=_m390_producer_snapshot,
        product_software_identity=_m390_product_software_identity(),
    )


def _m390_producer_snapshot() -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("390"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


# ── modelo 131 ──────────────────────────────────────────────────────────────


def m131_export_scenario(period: Period) -> EditionExportScenario:
    """A Modelo 131 quarterly scenario exporting from general filing facts."""
    return EditionExportScenario(
        period=period,
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "modelo-131.page1.actividad-1-epigrafe": "722",
            "modelo-131.page1.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.epigrafe-iae": ["722"],
            "modelo-131.dpa.vehiculos-afectos": {"1": "2"},
            "modelo-131.did.iban": _CHARGE_IBAN,
        },
        producer_snapshot=_m131_producer_snapshot,
    )


def _m131_producer_snapshot() -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("131"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


# ── modelos whose export path asks for no draft input ───────────────────────


def general_export_scenario(modelo_id: str, period: Period) -> EditionExportScenario:
    """A scenario carrying no draft input, for a modelo whose export path asks for none.

    These bytes exist to be comparable, never to be right: they are only ever
    compared with the bytes the same scenario renders through the other tree, so
    what the scenario must be is ACCEPTED by the export path. It states no
    taxpayer's real figures and is not an AEAT-correct declaration.

    No draft input is supplied, so every repeated record emits no occurrence and
    the compared bytes judge the edition's base layout and envelope -- the cheap
    end Modelo 390 already occupies. Modelo 303 is the demanding end and keeps
    its own builder: it is the one modelo registering an envelope policy, and
    its records refuse an envelope that leaves a required occurrence unemitted.
    The modelos routed here declare no required repeated record, so an empty
    draft satisfies their occurrence requirements.
    """
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=partial(_general_producer_snapshot, modelo_id),
    )


def _general_producer_snapshot(modelo_id: str) -> FilingProducerSnapshot:
    """The general-profile producer snapshot the no-input scenarios render through.

    The result disposition is the zero-result code every modelo here declares,
    which is what an empty draft computes; no account is selected, because no
    payment or refund is elected.
    """
    return build_filing_producer_snapshot(
        modelo=Modelo(modelo_id),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


#: Per modelo, the scenario builder and the period each edition is rendered for.
_DECLARED_SCENARIOS: Final[Mapping[str, tuple[Callable[[Period], EditionExportScenario], Mapping[str, Period]]]] = {
    str(Modelo("303")): (m303_export_scenario, M303_SCENARIO_PERIODS),
    str(Modelo("131")): (m131_export_scenario, M131_SCENARIO_PERIODS),
    str(Modelo("390")): (m390_export_scenario, M390_SCENARIO_PERIODS),
    str(Modelo("714")): (partial(general_export_scenario, "714"), M714_SCENARIO_PERIODS),
    str(Modelo("322")): (partial(general_export_scenario, "322"), M322_SCENARIO_PERIODS),
    str(Modelo("490")): (partial(general_export_scenario, "490"), M490_SCENARIO_PERIODS),
    str(Modelo("309")): (partial(general_export_scenario, "309"), M309_SCENARIO_PERIODS),
    str(Modelo("308")): (partial(general_export_scenario, "308"), M308_SCENARIO_PERIODS),
    str(Modelo("123")): (partial(general_export_scenario, "123"), M123_SCENARIO_PERIODS),
    str(Modelo("604")): (partial(general_export_scenario, "604"), M604_SCENARIO_PERIODS),
    str(Modelo("151")): (partial(general_export_scenario, "151"), M151_SCENARIO_PERIODS),
    str(Modelo("165")): (partial(general_export_scenario, "165"), M165_SCENARIO_PERIODS),
    str(Modelo("184")): (partial(general_export_scenario, "184"), M184_SCENARIO_PERIODS),
    str(Modelo("202")): (partial(general_export_scenario, "202"), M202_SCENARIO_PERIODS),
    str(Modelo("180")): (partial(general_export_scenario, "180"), M180_SCENARIO_PERIODS),
    str(Modelo("185")): (partial(general_export_scenario, "185"), M185_SCENARIO_PERIODS),
    str(Modelo("210")): (partial(general_export_scenario, "210"), M210_SCENARIO_PERIODS),
    str(Modelo("270")): (partial(general_export_scenario, "270"), M270_SCENARIO_PERIODS),
    str(Modelo("341")): (partial(general_export_scenario, "341"), M341_SCENARIO_PERIODS),
    str(Modelo("353")): (partial(general_export_scenario, "353"), M353_SCENARIO_PERIODS),
    str(Modelo("576")): (partial(general_export_scenario, "576"), M576_SCENARIO_PERIODS),
}

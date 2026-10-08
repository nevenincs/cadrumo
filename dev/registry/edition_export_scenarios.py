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
Modelos 714, 322, 490, 309, 123, 604, 151, 165, 184, 202, 180, 185, 210,
270, 341, 353 and 576 route through one shared
builder, :func:`general_export_scenario`. These scenarios need no extra
software-identity evidence and declare no required repeated record, so an empty draft leaves no required occurrence
unemitted and the compared bytes judge each edition's base layout and envelope,
as Modelo 390's do. Each carries the full set of its export-bearing editions, so
no edition of a listed modelo reports missing while its siblings report clean.
Modelo 308 shares that same empty draft but, like 200 and 322, needs its own
envelope software identity, so its own builder supplies it.

Where it stops
--------------
- One quarterly period per edition. A period whose facts would change which
  records emit (a fourth quarter's final-period prorrata coverage, a monthly
  filer) is not rendered.
- Only supported periods render. A period a table declares below the support
  floor is moved to the earliest supported period its edition serves, and an
  edition serving no supported period has no scenario, because nothing below
  the floor selects and so nothing there can render.
- Modelo 347 supplies purchase and sale rows from resolved fictional invoices,
  including a below-threshold exclusion control. Property records are not covered
  by this scenario.
- Modelo 303's 2022 edition has no scenario: the export path refuses its layout,
  whose regimen-simplificado record does not repeat per projection row. It is
  the modelo's first edition and names no predecessor, so the gate does not
  require its bytes.
- These facts read the published bundled generation, not the tree under
  comparison; the gate builds them once per scenario and renders the same
  facts through both trees, so the bytes judge the edition's export surface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from functools import cache, partial
from pathlib import Path
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
    AmendmentEvidence,
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    M303FilingFacts,
    Modelo222ProfileFacts,
    Modelo296AnexoCertificadoRow,
    Modelo296AnexoPagoRow,
    Modelo296PerceptorInteresesRow,
    Modelo296PerceptorRow,
    Modelo296ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.filing.producer_snapshot_m200 import (
    Modelo200AdministradorRow,
    Modelo200EntidadMenorDependienteRow,
    Modelo200EntidadParticipadaRow,
    Modelo200EstablecimientoPermanenteRow,
    Modelo200IncnEstablecimientoPermanenteRow,
    Modelo200IncnGrupoSociedadRow,
    Modelo200OperacionReestructuracionRow,
    Modelo200ParticipacionDirectaRow,
    Modelo200ParticipacionSocioRow,
    Modelo200ParticipeAieUteRow,
    Modelo200ProfileFacts,
    Modelo200ProjectionRows,
    Modelo200RepresentanteLegalRow,
    Modelo200SecretarioConsejoRow,
    Modelo200SocioSicavDisolucionRow,
    Modelo200TransparenciaFiscalInternacionalRow,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.filing_projection_ref import M303RegimenSimplificadoFact
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.prorrata_register import (
    ProrrataActivityRowType,
)
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister, RegistroRegularizacionResult
from cadrumo.domain.bienes_inversion.regularizacion_parameters import resolve_bienes_inversion_regularizacion_parameters
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.iva_deduction_catalogue import iva_deduction_fact_kinds
from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from cadrumo.domain.calculations.registry.m303_schema_vocabulary import (
    m303_regime_composition_simplified_scope,
)
from cadrumo.domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    general_prorrata_register_regime,
    prorrata_sector_letters,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    RegistrySnapshot,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.deadlines.models import ChargeAccount, M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from cadrumo.domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    LorcaActivityEligibility,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
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

from .compiler.loader import load_modelo_directory, load_shared_catalogues
from .edition_export_m347 import third_party_export_inputs
from .edition_round_trip import SYNTHETIC_TAX_ID, EditionExportScenario

__all__ = [
    "M123_SCENARIO_PERIODS",
    "M131_SCENARIO_PERIODS",
    "M151_SCENARIO_PERIODS",
    "M165_SCENARIO_PERIODS",
    "M180_SCENARIO_PERIODS",
    "M184_SCENARIO_PERIODS",
    "M185_SCENARIO_PERIODS",
    "M189_SCENARIO_PERIODS",
    "M190_SCENARIO_PERIODS",
    "M193_SCENARIO_PERIODS",
    "M200_SCENARIO_PERIODS",
    "M202_SCENARIO_PERIODS",
    "M210_SCENARIO_PERIODS",
    "M222_SCENARIO_PERIODS",
    "M232_SCENARIO_PERIODS",
    "M270_SCENARIO_PERIODS",
    "M296_SCENARIO_PERIODS",
    "M303_SCENARIO_PERIODS",
    "M308_SCENARIO_PERIODS",
    "M309_SCENARIO_PERIODS",
    "M322_SCENARIO_PERIODS",
    "M341_SCENARIO_PERIODS",
    "M345_SCENARIO_PERIODS",
    "M347_SCENARIO_PERIODS",
    "M353_SCENARIO_PERIODS",
    "M390_SCENARIO_PERIODS",
    "M490_SCENARIO_PERIODS",
    "M576_SCENARIO_PERIODS",
    "M604_SCENARIO_PERIODS",
    "M714_SCENARIO_PERIODS",
    "declared_row_total_inputs",
    "edition_export_scenarios",
    "general_export_scenario",
    "m131_export_scenario",
    "m190_export_scenario",
    "m193_export_scenario",
    "m200_export_scenario",
    "m222_export_scenario",
    "m296_export_scenario",
    "m303_export_scenario",
    "m308_export_scenario",
    "m322_export_scenario",
    "m347_export_scenario",
    "m390_export_scenario",
    "supported_scenario_periods",
]

#: The quarter each Modelo 303 edition is rendered for; each selects exactly that edition.
M303_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2023": Period.from_year_and_code(2023, "1T"),
    "2024-hasta-08-y-2t": Period.from_year_and_code(2024, "1T"),
    "2024-desde-09-y-3t": Period.from_year_and_code(2024, "3T"),
    "2025": Period.from_year_and_code(2025, "1T"),
    "2026-hasta-01-y-1t": Period.from_year_and_code(2026, "1T"),
    "2026-y-siguientes": Period.from_year_and_code(2026, "2T"),
}
#: The annual period each Modelo 189 edition is rendered for.
M189_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 190 edition is rendered for.
M190_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 193 edition is rendered for.
M193_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2022": Period.from_year_and_code(2022, "0A"),
    "2023": Period.from_year_and_code(2023, "0A"),
    "2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The annual period each Modelo 232 edition is rendered for.
M232_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    # 2016-2017 is deliberately absent. It was declared here and then withdrawn
    # on evidence: 140 of that edition's generated export fields reference
    # binding ids carrying an offset segment
    # (``modelo-232.page_02.2968-2968.paraiso-valor-12-tipo``) while every
    # binding it declares is offset-free. All 140 resolve once the segment is
    # stripped, and every embedded span agrees exactly with the binding's own
    # declared offset and length, so the segment is pure redundancy -- and the
    # sibling edition settles which spelling is canonical, carrying the same 140
    # fields with none of them. The edition therefore cannot compile, so it
    # cannot render, and its export tree is not regenerated because the edition
    # sits below the supported-filing-years floor. Declaring it would name a
    # render that will not happen.
    "2018-y-siguientes": Period.from_year_and_code(2018, "0A"),
}
#: The annual period each Modelo 345 edition is rendered for.
M345_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025": Period.from_year_and_code(2025, "0A"),
}
M347_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2011-2024": Period.from_year_and_code(2024, "0A"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
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
#: The first filing year of Modelo 322's BOE fichero layout, which stamps no
#: filing envelope where the editions before it do.
_M322_BOE_LAYOUT_FROM_YEAR: Final = 2026
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
    "2018-2022": Period.from_year_and_code(2022, "AD-HOC"),
    "2023-y-siguientes": Period.from_year_and_code(2023, "AD-HOC"),
}
#: The ad-hoc period Modelo 308's one export-bearing edition is rendered for.
M308_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-y-siguientes": Period.from_year_and_code(2022, "AD-HOC"),
}
#: The quarter each Modelo 123 edition is rendered for.
M123_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2023": Period.from_year_and_code(2022, "1T"),
    "2024-y-siguientes": Period.from_year_and_code(2024, "1T"),
}
#: The month each Modelo 604 edition is rendered for.
M604_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2021-2023": Period.from_year_and_code(2022, "01"),
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
#: The annual period of Modelo 200's export-bearing successor.
M200_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2025, "0A"),
}
#: The payment period each Modelo 202 edition is rendered for; 202 files ``1P``-``3P``.
M202_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2019-2022": Period.from_year_and_code(2019, "1P"),
    "2023-2024": Period.from_year_and_code(2023, "1P"),
    "2025-y-siguientes": Period.from_year_and_code(2025, "1P"),
}
#: The first payment period of Modelo 222's export-bearing edition.
M222_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2025-y-siguientes": Period.from_year_and_code(2025, "1P"),
}
#: The annual period of Modelo 296's five-record successor design.
M296_SCENARIO_PERIODS: Final[Mapping[str, Period]] = {
    "2024-2025": Period.from_year_and_code(2024, "0A"),
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
    "2021-hasta-2026-01": Period.from_year_and_code(2021, "01"),
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


def _m303_differentiated_sectors() -> tuple[SectorDefinition, ...]:
    """Modelo 303's two differentiated sectors, built on demand rather than at import.

    `SectorDiferenciadoLetra` is an opaque registry-projected token: it refuses
    construction outside the facts-registry projection path and exposes no class
    members. Building these at module scope therefore made the ENTIRE scenarios
    module unimportable the moment that refactor landed -- and with it every
    other modelo's scenario, none of which involves a differentiated sector.

    Deferring it does not fix 303, which still needs a projection entry point it
    can reach. It stops 303's dependency from deciding whether eight unrelated
    modelos can be read at all, and it keeps the failure loud at the point of
    use, where the token class raises with its own message. Module-scope
    construction of a projected token is the anti-pattern that has broken this
    import chain repeatedly; this is one instance of it removed.
    """
    letters = prorrata_sector_letters()
    return (
        SectorDefinition(sector_id="a", letra=letters[0], member_activity_codes=("4711",)),
        SectorDefinition(sector_id="b", letra=letters[1], member_activity_codes=("6820",)),
    )


_M303_NON_AGRICULTURAL: Final = "no_agricola"


def edition_export_scenarios(
    modelo_id: str,
    *,
    registry_root: Path | None = None,
) -> Mapping[str, EditionExportScenario]:
    """Every declared export scenario for ``modelo_id``, keyed by the edition it selects; empty when none is.

    Each edition renders at the period its table declares when the support
    envelope admits it, and otherwise at the earliest supported period it
    serves, as :func:`supported_scenario_periods` decides against
    ``registry_root`` (the bundled registry when omitted).
    """
    declared = _DECLARED_SCENARIOS.get(modelo_id)
    if declared is None:
        return dict[str, EditionExportScenario]()
    builder, periods = declared
    rendered = supported_scenario_periods(
        modelo_id,
        periods,
        registry_root=bundled_path("registry", "aeat") if registry_root is None else registry_root,
    )
    return {revision_id: builder(period) for revision_id, period in rendered.items()}


def supported_scenario_periods(
    modelo_id: str,
    periods: Mapping[str, Period],
    *,
    registry_root: Path,
) -> dict[str, Period]:
    """Return the period each edition renders at: its declared one, or the earliest supported one it serves.

    Nothing selects below the support floor, so a scenario declared there is
    refused before a byte renders and proves nothing about the edition. An
    edition whose span straddles the floor still files the supported years it
    covers, so it renders at the first of them, keeping its declared period
    code where that year serves it. The year and period are confirmed by the
    canonical revision selection rather than read off the edition's name. An
    edition that serves no supported year has no renderable export and gets no
    scenario.
    """
    support = load_shared_catalogues(registry_root).require_supported_filing_years()
    rendered: dict[str, Period] = {}
    modelo: ModeloDefinition | None = None
    for revision_id, period in periods.items():
        if support.admits_filing_year(period.filing_year):
            rendered[revision_id] = period
            continue
        if modelo is None:
            modelo = load_modelo_directory(registry_root / "modelos" / modelo_id)
        supported = _earliest_supported_period(modelo, revision_id, period, support)
        if supported is not None:
            rendered[revision_id] = supported
    return rendered


def _earliest_supported_period(
    modelo: ModeloDefinition,
    revision_id: str,
    declared: Period,
    support: SupportedFilingYearsCatalogue,
) -> Period | None:
    """The first supported ``(year, period)`` that canonically selects ``revision_id``, or ``None``."""
    revision = modelo.revisions.get(revision_id)
    if revision is None:
        return None
    for year in support.years:
        if year < declared.filing_year or not revision.period_selector.includes_year(year):
            continue
        served = tuple(str(token) for token in revision.period_selector.periods_for_year(year))
        tokens = _preferred_scenario_period_tokens(served, declared.registry_token)
        candidate = _supported_period_for_revision(modelo, year, revision_id, tokens, support)
        if candidate is not None:
            return candidate
    return None


def _preferred_scenario_period_tokens(served: tuple[str, ...], preferred: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*(item for item in served if item == preferred), *served)))


def _supported_period_for_revision(
    modelo: ModeloDefinition,
    year: int,
    revision_id: str,
    tokens: tuple[str, ...],
    support: SupportedFilingYearsCatalogue,
) -> Period | None:
    for token in tokens:
        try:
            selected = select_revision(modelo, filing_year=year, period=token, support=support)
            candidate = Period.from_year_and_code(year, token)
        except (RegistryError, ValueError):
            continue
        if str(selected.id) == revision_id:
            return candidate
    return None


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
        product_software_identity_factory=_product_software_identity,
    )


def _m303_producer_snapshot(period: Period) -> FilingProducerSnapshot:
    """Build the scenario's facts from one published bundled generation.

    The edition snapshot, the governed facts and the regimen calculation all
    read the same pinned operation, so the facts never mix a source compile
    with the published generation, and building them does not compile the
    whole bundled registry.
    """
    with bundled_indexed_authority().operation() as operation:
        registry_snapshot = operation.snapshot(
            str(Modelo("303")), filing_year=period.filing_year, period=period.registry_token
        )
        m303_filing_facts = _m303_filing_facts(
            period,
            registry_snapshot=registry_snapshot,
            operation=operation,
        )
    profile = ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
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
        charge_account=ChargeAccount(iban=_CHARGE_IBAN),
        m303_filing_facts=m303_filing_facts,
    )


def _m303_filing_facts(
    period: Period,
    *,
    registry_snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
) -> M303FilingFacts:
    regimen = _m303_regimen_simplificado_evidence(
        period,
        registry_snapshot=registry_snapshot,
        operation=operation,
    )
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
        prorrata_register=_m303_prorrata_register(period, operation=operation),
        differentiated_contributions=_m303_differentiated_contributions(period=period, operation=operation),
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
    period: Period,
    *,
    registry_snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
) -> M303RegimenSimplificadoFilingEvidence:
    """One non-agricultural activity from the edition's own Orden, so the repeated record emits once."""
    scope = M303RegimenSimplificadoScopeDecision(
        scope=m303_regime_composition_simplified_scope("simplified", authority=operation)
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
                lorca_eligibility=(
                    LorcaActivityEligibility(eligible=False, evidence_reference=_EVIDENCE)
                    if regimen_snapshot.orden.lorca_reduction is not None
                    else None
                ),
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
        dana_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_eligibility=None,
            operation=operation,
        ),
    )


def _m303_prorrata_register(period: Period, *, operation: PinnedAuthorityOperation) -> ProrrataRegister:
    """A general-regime register carrying the prior year's definitive percentage for the common and both sectors."""
    prior_snapshot_ref = operation.snapshot(
        str(Modelo("303")), filing_year=period.filing_year - 1, period="4T"
    ).snapshot_ref
    return ProrrataRegister(
        sector_definitions=_m303_differentiated_sectors(),
        entries=tuple(
            ProrrataRegisterEntry(
                ejercicio=period.filing_year,
                sector_id=sector_id,
                regime=general_prorrata_register_regime(),
                especial_transition=None,
                provisional_percentage=Decimal("50"),
                provisional_provenance=carried_prior_definitiva_prorrata_provenance(),
                source_registry_snapshot_refs=(prior_snapshot_ref,),
            )
            for sector_id in (None, *(sector.sector_id for sector in _m303_differentiated_sectors()))
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


def _m303_differentiated_contributions(
    *, period: Period, operation: PinnedAuthorityOperation
) -> tuple[IvaDifferentiatedDeductionContribution, ...]:
    """One contribution per deduction kind the differentiated sectors declare, in each sector."""
    kinds = iva_deduction_fact_kinds(
        effective_date=period.end_date,
        authority=operation,
    )
    return tuple(
        IvaDifferentiatedDeductionContribution(
            sector_id=sector.sector_id,
            deduction_fact_kind=kind,
            source_ledger_ids=(f"edition-round-trip:{sector.sector_id}:{index}",),
            base_amount=Decimal("100"),
            deducible_iva_amount=Decimal("20"),
        )
        for sector in _m303_differentiated_sectors()
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
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity_factory=_m390_product_software_identity,
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


# ── modelo 190 ──────────────────────────────────────────────────────────────

#: The eight ``provider.kind = "withholding"`` grouped-row-sum bindings an
#: edition's declarante summary formulas (percepciones-total, retenciones-total)
#: add over where they total the type-2 records. An edition that routes those
#: totals through the modelo 111 relation prefills does not declare them, and a
#: binding an edition does not declare must not be supplied.
_M190_PERCEPTOR_ROW_TOTAL_BINDINGS: Final = (
    "modelo-190-perceptor-rows-percepcion-dineraria-total",
    "modelo-190-perceptor-rows-percepcion-especie-total",
    "modelo-190-perceptor-rows-incapacidad-dineraria-total",
    "modelo-190-perceptor-rows-incapacidad-especie-total",
    "modelo-190-perceptor-rows-retencion-practicada-total",
    "modelo-190-perceptor-rows-ingreso-a-cuenta-total",
    "modelo-190-perceptor-rows-incapacidad-retencion-total",
    "modelo-190-perceptor-rows-incapacidad-ingreso-a-cuenta-total",
)


@cache
def _bundled_modelo(modelo_id: str) -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat") / "modelos" / modelo_id)


@cache
def _bundled_support() -> SupportedFilingYearsCatalogue:
    return load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()


def declared_row_total_inputs(
    modelo_id: str,
    period: Period,
    binding_ids: tuple[str, ...],
) -> dict[str, Decimal]:
    """Synthetic inputs for those of ``binding_ids`` the edition ``period`` selects declares.

    Which edition sums its own type-2 records and which routes its totals
    through a relation is the edition's declaration, so it is read from the
    selected revision rather than inferred from the filing year.
    """
    revision = select_revision(
        _bundled_modelo(modelo_id),
        filing_year=period.filing_year,
        period=period.registry_token,
        support=_bundled_support(),
    )
    declared = {str(binding.id) for binding in revision.bindings}
    return {binding_id: Decimal("1000.00") for binding_id in binding_ids if binding_id in declared}


def m190_export_scenario(period: Period) -> EditionExportScenario:
    """A Modelo 190 annual scenario supplying the withholding row totals its edition sums.

    An edition that totals its type-2 records binds its declarante summary
    casillas to formulas over eight withholding grouped-row-sum bindings -- the
    annual total each type-2 perceptor row family sums to -- so an empty draft
    leaves them unresolved.
    """
    inputs = declared_row_total_inputs("190", period, _M190_PERCEPTOR_ROW_TOTAL_BINDINGS)
    return EditionExportScenario(
        period=period,
        inputs=inputs,
        producer_snapshot=partial(_general_producer_snapshot, "190"),
    )


# ── modelo 193 ──────────────────────────────────────────────────────────────

#: The two ``provider.kind = "withholding"`` grouped-row-sum bindings an
#: edition's declarante summary formulas add over where they total the type-2
#: records. An edition that routes those totals through the modelo 123 relation
#: prefills does not declare them.
_M193_PERCEPTOR_ROW_TOTAL_BINDINGS: Final = (
    "modelo-193-perceptor-rows-base-total",
    "modelo-193-perceptor-rows-retenciones-total",
)


def m193_export_scenario(period: Period) -> EditionExportScenario:
    """A Modelo 193 annual scenario supplying its manual gastos total and the withholding row totals it sums.

    ``decl.gastos-total`` is a manual declarante casilla every edition declares
    required, so every edition needs it supplied directly. An edition that
    totals its type-2 records additionally binds its base-total and
    retenciones-total casillas to formulas over two withholding grouped-row-sum
    bindings; one that routes them through modelo 123 relation prefills does not.
    """
    inputs: dict[str, Decimal] = {"decl.gastos-total": Decimal("500.00")}
    inputs.update(declared_row_total_inputs("193", period, _M193_PERCEPTOR_ROW_TOTAL_BINDINGS))
    return EditionExportScenario(
        period=period,
        inputs=inputs,
        producer_snapshot=partial(_general_producer_snapshot, "193"),
    )


# ── modelos whose export path asks for no draft input ───────────────────────


def _scenario_software_identity(modelo_id: str) -> AeatProductSoftwareIdentity:
    """Validate synthetic software evidence inside the candidate fact scope."""
    return AeatProductSoftwareIdentity(
        program_identifier=f"C{modelo_id}",
        developer_tax_id="Y0000001S",
        evidence=(AeatProductSoftwareEvidence(reference=f"edition-round-trip:m{modelo_id}-software", digest="c" * 64),),
    )


def m200_export_scenario(
    period: Period, *, result_disposition: ResultDisposition = ResultDisposition.NEGATIVA
) -> EditionExportScenario:
    """A synthetic corporate draft with explicit envelope software evidence and its rate-dispatch profile bindings.

    The cuota-integra and tipo-gravamen formulas dispatch on the new-entity
    profile flag; both of its branches then look up the rate by legal entity
    form, and the cuota-ejercicio-a-ingresar formula unconditionally consumes
    the tributacion-estado-porcentaje profile binding. None of the three is a
    draft input the operator supplies through a casilla, so an empty draft
    leaves them unresolved.

    Six records of the layout -- pages 2, 2b, 21, 23, 24b and 25 -- are required
    and consist of projection fields alone, so each needs at least one row of
    every family it prints. The snapshot below supplies exactly one synthetic
    row per family, carrying the identity the row is about and leaving every
    monetary member absent, which is what AEAT's blancos rule prescribes for an
    unsupplied alphanumeric field.
    """
    return EditionExportScenario(
        period=period,
        inputs={
            "modelo-200-profile-new-entity-flag": True,
            "modelo-200-profile-legal-entity-form": "sl",
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            # DP200012 casilla 00501, "Resultado de la cuenta de pérdidas y
            # ganancias": the edition declares it required, and the base
            # determination starts from it, so no draft can omit it.
            "DP200012:00501": Decimal("0.00"),
        },
        producer_snapshot=partial(_m200_producer_snapshot, result_disposition=result_disposition),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity_factory=partial(_scenario_software_identity, "200"),
    )


#: The synthetic NIF every Modelo 200 projected party is identified by. Nine
#: characters, the width the diseño gives each of those NIF fields.
_M200_SYNTHETIC_NIF: Final = "B00000000"
#: The synthetic country/province code the two-character ``codigo`` members take.
_M200_SYNTHETIC_COUNTRY: Final = "ES"


def _m200_projection_rows() -> Modelo200ProjectionRows:
    """One synthetic row of every repeated family modelo 200's layout projects."""
    return Modelo200ProjectionRows(
        administrador=(Modelo200AdministradorRow(nif=_M200_SYNTHETIC_NIF, apellidos_nombre_razon_social="Ana Prueba"),),
        entidad_menor_dependiente=(
            Modelo200EntidadMenorDependienteRow(nif=_M200_SYNTHETIC_NIF, nombre_o_razon_social="Prueba SL"),
        ),
        entidad_participada=(
            Modelo200EntidadParticipadaRow(nif=_M200_SYNTHETIC_NIF, nombre_o_razon_social="Prueba SL"),
        ),
        establecimiento_permanente=(
            Modelo200EstablecimientoPermanenteRow(
                identificacion="Prueba EP",
                pais_residencia_fiscal=_M200_SYNTHETIC_COUNTRY,
            ),
        ),
        incn_establecimiento_permanente=(Modelo200IncnEstablecimientoPermanenteRow(nif=_M200_SYNTHETIC_NIF),),
        incn_grupo_sociedad=(
            Modelo200IncnGrupoSociedadRow(
                nif_entidad_grupo=_M200_SYNTHETIC_NIF,
                codigo_pais=_M200_SYNTHETIC_COUNTRY,
            ),
        ),
        operacion_reestructuracion=(
            Modelo200OperacionReestructuracionRow(
                transmitente_nif=_M200_SYNTHETIC_NIF,
                adquirente_nif=_M200_SYNTHETIC_NIF,
            ),
        ),
        participacion_directa=(
            Modelo200ParticipacionDirectaRow(nif=_M200_SYNTHETIC_NIF, nombre_o_razon_social="Prueba SL"),
        ),
        participacion_socio=(
            Modelo200ParticipacionSocioRow(nif=_M200_SYNTHETIC_NIF, apellidos_nombre_razon_social="Ana Prueba"),
        ),
        participe_aie_ute=(
            Modelo200ParticipeAieUteRow(nif=_M200_SYNTHETIC_NIF, apellidos_nombre_razon_social="Ana Prueba"),
        ),
        representante_legal=(Modelo200RepresentanteLegalRow(nif=_M200_SYNTHETIC_NIF, apellidos_y_nombre="Ana Prueba"),),
        secretario_consejo=(Modelo200SecretarioConsejoRow(nif=_M200_SYNTHETIC_NIF, apellidos_y_nombre="Ana Prueba"),),
        socio_sicav_disolucion=(
            Modelo200SocioSicavDisolucionRow(
                nif_sociedad_disuelta=_M200_SYNTHETIC_NIF,
                nif_iic_reinversion=_M200_SYNTHETIC_NIF,
            ),
        ),
        transparencia_fiscal_internacional=(
            Modelo200TransparenciaFiscalInternacionalRow(
                nombre_o_razon_social="Prueba SL",
                clave_pais_territorio=_M200_SYNTHETIC_COUNTRY,
            ),
        ),
    )


def _m200_producer_snapshot(*, result_disposition: ResultDisposition) -> FilingProducerSnapshot:
    """The Modelo 200 snapshot whose typed rows feed the layout's projection pages."""
    return build_filing_producer_snapshot(
        modelo=Modelo("200"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=Modelo200ProfileFacts(projection_rows=_m200_projection_rows()),
        elections=FilingElectionFacts(
            result_disposition=result_disposition,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def m222_export_scenario(period: Period) -> EditionExportScenario:
    """A synthetic fiscal group with the identity its filing requires."""
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=partial(_m222_producer_snapshot, period),
        product_software_identity_factory=partial(_scenario_software_identity, "222"),
    )


def _m222_producer_snapshot(period: Period) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("222"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=Modelo222ProfileFacts(
            numero_grupo="0001/25",
            entidad_dominante_identificacion="B00000000",
            entidad_dominante_razon_social="Grupo Prueba",
            representante_o_dominante="2",
            fecha_inicio_periodo_impositivo=f"0101{period.filing_year}",
        ),
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


def m296_export_scenario(period: Period) -> EditionExportScenario:
    """One synthetic occurrence of every required Modelo 296 detail family."""
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=partial(_m296_producer_snapshot, period),
    )


def _m296_producer_snapshot(period: Period) -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo("296"),
        taxpayer_tax_id=SYNTHETIC_TAX_ID,
        taxpayer_identity=_TAXPAYER,
        presenter=_presenter(),
        model_profile=Modelo296ProfileFacts(
            ejercicio=str(period.filing_year),
            nif_del_declarante=SYNTHETIC_TAX_ID,
            apellidos_y_nombre_o_razon_social_del="Ana Prueba",
            perceptor_rows=(Modelo296PerceptorRow(nif_del_perceptor="00000000T"),),
            perceptor_intereses_rows=(Modelo296PerceptorInteresesRow(nif_del_perceptor="00000000T"),),
            anexo_pago_rows=(Modelo296AnexoPagoRow(nif_del_contribuyente="00000000T"),),
            anexo_certificado_rows=(Modelo296AnexoCertificadoRow(nif_del_perceptor="00000000T"),),
        ),
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


def general_export_scenario(modelo_id: str, period: Period) -> EditionExportScenario:
    """A scenario carrying no draft input, for a modelo whose export path asks for none.

    These bytes exist to be comparable, never to be right: they are only ever
    compared with the bytes the same scenario renders through the other tree, so
    what the scenario must be is ACCEPTED by the export path. It states no
    taxpayer's real figures and is not an AEAT-correct declaration.

    No draft input is supplied, so every repeated record emits no occurrence and
    the compared bytes judge the edition's base layout and envelope -- the cheap
    end Modelo 390 already occupies. Modelos needing software-identity
    evidence, group identity or required detail occurrences use their own
    builders, which supply those facts explicitly.
    The modelos routed here declare no required repeated record and no other
    required casilla an empty draft leaves unresolved. A modelo whose required
    declarante total is bound to a formula over registry-sourced bindings the
    draft never supplies -- Modelo 190's and 193's percepciones/retenciones
    totals, for instance -- gets its own builder instead.
    """
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=partial(_general_producer_snapshot, modelo_id),
    )


def _general_producer_snapshot(
    modelo_id: str, *, amendment_evidence: AmendmentEvidence | None = None
) -> FilingProducerSnapshot:
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
        amendment_evidence=amendment_evidence,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def m322_export_scenario(period: Period) -> EditionExportScenario:
    """A synthetic complementaria carrying the envelope evidence only the editions that stamp one need.

    The 2008-2022, 2023 and 2024-2025 editions render a filing envelope, which
    the canonical export path refuses without BOTH an explicit
    product/software identity and an explicit prior-domiciliation election. The
    2026-y-siguientes edition replaces that layout with the BOE fichero, which
    declares no envelope prefix, and the same path refuses a product/software
    identity no layout stamps. The envelope facts therefore follow the layout,
    not the modelo.
    """
    stamps_envelope = period.filing_year < _M322_BOE_LAYOUT_FROM_YEAR
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=_m322_producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP if stamps_envelope else None,
        product_software_identity_factory=(partial(_scenario_software_identity, "322") if stamps_envelope else None),
    )


def _m322_producer_snapshot() -> FilingProducerSnapshot:
    return _general_producer_snapshot(
        "322",
        amendment_evidence=AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            m303_rectificativa_motive=None,
            original_aeat_receipt="3220000000000",
        ),
    )


def m308_export_scenario(period: Period) -> EditionExportScenario:
    """An empty synthetic draft with explicit envelope software evidence, as 200 and 322 supply.

    Modelo 308's export layout renders an envelope prefix, which the canonical
    export path refuses without explicit product/software identity authority
    and an explicit prior-domiciliation election, whichever the layout's own
    policy leaves defaulted.
    """
    return EditionExportScenario(
        period=period,
        inputs={},
        producer_snapshot=partial(_general_producer_snapshot, "308"),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity_factory=partial(_scenario_software_identity, "308"),
    )


def m347_export_scenario(period: Period) -> EditionExportScenario:
    """Supply required counterparty rows and their consistently resolved totals."""
    return EditionExportScenario(
        period=period,
        inputs=third_party_export_inputs(period),
        producer_snapshot=partial(_general_producer_snapshot, "347"),
    )


#: Per modelo, the scenario builder and the period each edition is rendered for.
_DECLARED_SCENARIOS: Final[Mapping[str, tuple[Callable[[Period], EditionExportScenario], Mapping[str, Period]]]] = {
    str(Modelo("189")): (partial(general_export_scenario, "189"), M189_SCENARIO_PERIODS),
    str(Modelo("190")): (m190_export_scenario, M190_SCENARIO_PERIODS),
    str(Modelo("193")): (m193_export_scenario, M193_SCENARIO_PERIODS),
    str(Modelo("232")): (partial(general_export_scenario, "232"), M232_SCENARIO_PERIODS),
    str(Modelo("345")): (partial(general_export_scenario, "345"), M345_SCENARIO_PERIODS),
    str(Modelo("347")): (m347_export_scenario, M347_SCENARIO_PERIODS),
    str(Modelo("303")): (m303_export_scenario, M303_SCENARIO_PERIODS),
    str(Modelo("131")): (m131_export_scenario, M131_SCENARIO_PERIODS),
    str(Modelo("390")): (m390_export_scenario, M390_SCENARIO_PERIODS),
    str(Modelo("714")): (partial(general_export_scenario, "714"), M714_SCENARIO_PERIODS),
    str(Modelo("322")): (m322_export_scenario, M322_SCENARIO_PERIODS),
    str(Modelo("490")): (partial(general_export_scenario, "490"), M490_SCENARIO_PERIODS),
    str(Modelo("309")): (partial(general_export_scenario, "309"), M309_SCENARIO_PERIODS),
    str(Modelo("308")): (m308_export_scenario, M308_SCENARIO_PERIODS),
    str(Modelo("123")): (partial(general_export_scenario, "123"), M123_SCENARIO_PERIODS),
    str(Modelo("604")): (partial(general_export_scenario, "604"), M604_SCENARIO_PERIODS),
    str(Modelo("151")): (partial(general_export_scenario, "151"), M151_SCENARIO_PERIODS),
    str(Modelo("165")): (partial(general_export_scenario, "165"), M165_SCENARIO_PERIODS),
    str(Modelo("184")): (partial(general_export_scenario, "184"), M184_SCENARIO_PERIODS),
    str(Modelo("202")): (partial(general_export_scenario, "202"), M202_SCENARIO_PERIODS),
    str(Modelo("200")): (m200_export_scenario, M200_SCENARIO_PERIODS),
    str(Modelo("222")): (m222_export_scenario, M222_SCENARIO_PERIODS),
    str(Modelo("296")): (m296_export_scenario, M296_SCENARIO_PERIODS),
    str(Modelo("180")): (partial(general_export_scenario, "180"), M180_SCENARIO_PERIODS),
    str(Modelo("185")): (partial(general_export_scenario, "185"), M185_SCENARIO_PERIODS),
    str(Modelo("210")): (partial(general_export_scenario, "210"), M210_SCENARIO_PERIODS),
    str(Modelo("270")): (partial(general_export_scenario, "270"), M270_SCENARIO_PERIODS),
    str(Modelo("341")): (partial(general_export_scenario, "341"), M341_SCENARIO_PERIODS),
    str(Modelo("353")): (partial(general_export_scenario, "353"), M353_SCENARIO_PERIODS),
    str(Modelo("576")): (partial(general_export_scenario, "576"), M576_SCENARIO_PERIODS),
}

"""Tests for the committed Modelo 390 (IVA Resumen Anual) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.resources import bundled_path
from ....iva.schema import IvaLedgerObservationRole
from .._validate import RegistryValidator
from ..binding_aggregation import binding_aggregation_op
from ..binding_selector_utils import selector_as_dict
from ..bindings import binding_source_casilla_ids, binding_source_modelo
from ..errors import RegistryValidationError
from ..runtime_graph import expression_casilla_refs
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..schema_input_kind import InputKind
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_COMPENSACION_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_POSTERIOR_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores"
)
_M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS: tuple[CasillaId, ...] = (
    validated_casilla_id("iva.cuota-deducible-total"),
    validated_casilla_id("iva.prorrata-volumen-con-derecho"),
    validated_casilla_id("iva.prorrata-volumen-total"),
    validated_casilla_id("iva.prorrata-porcentaje"),
)
_M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS = ("1T", "2T", "3T", "4T")
#: Modelo 390's four exact-year revisions. The revision-span split replaced the
#: single open-ended `2010-y-siguientes` revision with one revision per design
#: year, each claiming exactly one bundled diseño. Tests that assert a STRUCTURAL
#: property parametrise over all four rather than pinning one, so a property that
#: silently stops holding in a single year is caught.
#: Page-04 offsets for the two Regimen General regularizacion boxes, per revision.
#: The 2024 diseno inserted "Pag. 2 bis" and grew page 4 from 378 to 854
#: positions, so both boxes moved. Read from each year's own diseno -- the 2022
#: sheet prints the prorrata box at 166..182 and the 2024 sheet at 642..658 --
#: rather than pinned to one era, which is what made these cases fail for 2022
#: and 2023 after the revision-span split exposed them.
_M390_PAGE_04_REGULARIZACION_OFFSETS: dict[str, dict[str, int]] = {
    "2022": {"prorrata": 166, "bienes_inversion": 149},
    "2023": {"prorrata": 166, "bienes_inversion": 149},
    "2024": {"prorrata": 642, "bienes_inversion": 625},
    "2025": {"prorrata": 642, "bienes_inversion": 625},
}


_M390_REVISION_IDS: tuple[str, ...] = ("2022", "2023", "2024", "2025")

#: The most recent revision, for assertions that genuinely address one subject.
_M390_CURRENT_REVISION = "2025"


_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.resultado-regimen-general")
_M390_PRORRATA_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("iva.anual.regularizacion-prorrata-definitiva")
_M390_BIENES_INVERSION_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.regularizacion-bienes-inversion"
)
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97"
)
_M390_CONSTRUCT_ID = "modelo-390-iva-resumen-anual"
_M390_RECONCILIATION_PREDICATES = (
    (
        "modelo-390-cuota-devengada-total-equals-reconciliacion-303",
        _M390_CUOTA_DEVENGADA_TOTAL_CASILLA,
        _M390_RECONCILIACION_DEVENGADA_303_CASILLA,
        'equals(["iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"])',
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-90",
            "ley-37-1992:art-91",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
    (
        "modelo-390-cuota-deducible-total-equals-reconciliacion-303",
        _M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
        _M390_RECONCILIACION_DEDUCIBLE_303_CASILLA,
        'equals(["iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"])',
        {
            "ley-37-1992:art-17",
            "ley-37-1992:art-84",
            "ley-37-1992:art-92",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
    (
        "modelo-390-resultado-regimen-general-equals-reconciliacion-303",
        _M390_RESULTADO_REGIMEN_GENERAL_CASILLA,
        _M390_RECONCILIACION_RESULTADO_303_CASILLA,
        'equals(["iva.anual.resultado-regimen-general", "iva.anual.reconciliacion.resultado-303"])',
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-92",
            "rd-1624-1992:art-71",
            "orden-eha-3111-2009:art-1",
        },
    ),
)
_M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-13",
        "ley-37-1992:art-69",
        "ley-37-1992:art-70",
        "ley-37-1992:art-85",
        "ley-37-1992:art-88",
        "ley-37-1992:art-92",
        "ley-37-1992:art-99",
        "ley-37-1992:art-115",
        "ley-37-1992:art-116",
        "orden-eha-3111-2009:art-1",
        "rd-1624-1992:art-29",
        "rd-1624-1992:art-30",
        "rd-1624-1992:art-71",
    }
)


def _load_modelo_390() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("390")


def _replace_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(
        update={
            "revisions": {
                revision_id: revision if revision_id == revision.id else item
                for revision_id, item in modelo.revisions.items()
            },
        },
    )


def test_modelo_390_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_390()
    assert modelo.id == "390"
    assert modelo.revisions, "390 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "390 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_390_metadata_matches_orden_eha_3111_2009() -> None:
    modelo, _ = _load_modelo_390()
    assert modelo.title == "IVA. Declaración-resumen anual"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "annual"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3111-2009:art-1" in modelo.legal_refs
    assert "orden-eha-3111-2009:art-8" in modelo.legal_refs
    assert "aeat-dr-390-2025" in modelo.source_refs


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_revision_period_selector_claims_exactly_its_own_year(revision_id: str) -> None:
    """Each revision claims exactly the one filing year it is named for.

    This asserted a single open-ended span starting 2010-01-01. The
    revision-span split replaced that with one revision per bundled diseño year,
    so "starts at 2010" is no longer a property of any revision; what must hold
    now is that each one claims its own year and nothing else, which is what
    keeps a filing year from resolving under a neighbouring year's norms.
    """
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    year = int(revision_id)
    assert revision.valid_from == date(year, 1, 1)
    assert revision.valid_to == date(year, 12, 31)
    assert revision.period_selector.years == (year,)
    assert revision.period_selector.periods == ("0A",)
    assert revision.orden_aplicabilidad == ("orden-eha-3111-2009:art-1",)


def test_modelo_390_snapshot_builds_for_each_published_filing_year() -> None:
    """Each published filing year resolves to the revision that claims that year.

    This iterated 2020..2026 against a single open-ended revision. The
    revision-span split replaced it with one revision per bundled diseño year,
    so the published years are exactly those four: 2020 and 2021 have no
    bundled 390 design behind a revision, and 2026's diseño is not published
    yet. The resolved id is ASSERTED against the law-determined pick, never fed
    into resolution.
    """
    for filing_year in (2022, 2023, 2024, 2025):
        snapshot = _committed_snapshot("390", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)
        assert snapshot.revision.id == str(filing_year)


def test_modelo_390_snapshot_carries_legal_authority_and_record_design() -> None:
    _, catalogues = _load_modelo_390()
    snapshot = _committed_snapshot("390", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    assert "orden-eha-3111-2009:art-1" in snapshot.legal
    assert "orden-eha-3111-2009:art-8" in snapshot.legal
    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3111-2009:art-1",)
    assert snapshot.legal["orden-eha-3111-2009:art-8"].article == "8"
    assert "aeat-dr-390-2025" in snapshot.sources
    assert "aeat-modelo-390-procedure" in snapshot.sources
    assert "boe-modelo-390-2009-form" in snapshot.sources
    assert catalogues.sources["aeat-modelo-390-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-390-2009-form"].evidence_tier == "layout_authority"


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_extraction_profile_legal_refs_match_target_casillas(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    assert revision.extraction_profiles, revision.id
    profile = next(item for item in revision.extraction_profiles if item.id == "modelo-390-declaracion-pdf")
    target_refs = frozenset(
        legal_ref for target in profile.target_casillas for legal_ref in casillas_by_id[target.casilla_id].legal_refs
    )

    assert target_refs == _M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS
    assert set(profile.legal_refs) == _M390_EXTRACTION_PROFILE_TARGET_LEGAL_REFS


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_january_30_deadline_matches_orden_eha_3111_2009_art_8(revision_id: str) -> None:
    """Art 8: presentación en los treinta primeros días naturales del mes de enero siguiente."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    # One window per revision, for that revision's own filing year. This listed
    # all seven windows 2020..2026 on a single open-ended revision; after the
    # revision-span split each revision owns exactly its own, and 2020, 2021 and
    # 2026 have no revision to carry one.
    year = int(revision_id)
    windows = {w.id: w for w in revision.deadline_windows}
    assert set(windows) == {f"modelo-390-{year}-0a"}

    window = windows[f"modelo-390-{year}-0a"]
    assert window.filing_year == year
    # Art. 8: the thirty first natural days of the January FOLLOWING the ejercicio.
    assert window.opens_on == date(year + 1, 1, 1)
    assert window.closes_on == date(year + 1, 1, 30)


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_live_cross_references_are_read_only(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-390-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-390-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    forbidden = set(filed_ref.forbidden_actions)
    assert {"presentation", "signing", "amendment", "payment"}.issubset(forbidden)


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_construct_links_filing_workbook_parity(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    construct = next(c for c in revision.constructs if c.id == _M390_CONSTRUCT_ID)
    assert "modelo-390-filing" in construct.application_links
    assert "modelo-390-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-390-anual",)
    # Each revision carries ITS OWN year's workbook parity ref. Pinning
    # `modelo-390-dr-2025` asserted the newest revision's ref on all four, which
    # is the same era-pinning that the revision-span split exposed elsewhere in
    # this module.
    assert f"modelo-390-dr-{revision_id}" in construct.workbook_parity_refs
    assert "ley-37-1992:art-161" in construct.legal_refs
    assert "ley-37-1992:art-104" in construct.legal_refs
    assert "ley-37-1992:art-105" in construct.legal_refs
    assert "ley-37-1992:art-107" in construct.legal_refs
    assert "ley-37-1992:art-110" in construct.legal_refs


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_construct_requires_recargo_grounding(revision_id: str) -> None:
    modelo, catalogues = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    constructs = tuple(
        construct.model_copy(
            update={"legal_refs": tuple(ref for ref in construct.legal_refs if ref != "ley-37-1992:art-161")},
        )
        if construct.id == _M390_CONSTRUCT_ID
        else construct
        for construct in revision.constructs
    )
    mutated_revision = revision.model_copy(update={"constructs": constructs})
    mutated_modelo = _replace_revision(modelo, mutated_revision)

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"construct 'modelo-390-iva-resumen-anual' does not include legal refs "
            r"\['ley-37-1992:art-161'\] required by formula 'modelo-390-iva-anual-cuota-devengada-total'"
        ),
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_declares_iva_aggregation_bindings_for_annual_resumen(revision_id: str) -> None:
    """Modelo 390 declares the same IVA flow-direction binding pattern as
    Modelo 303 — the annual resumen aggregates the same flows over the
    full ejercicio rather than per quarter.

    The ``*-base`` entries are the base-imponible half of that pattern: the
    AEAT Diseño de Registros pairs a "Base imponible" box with every "Cuota"
    box of the Reg. ordinario block, and Modelo 303 already draws its base
    through the sibling ``modelo-303-iva-*-base`` bindings. They aggregate the
    ``base_amount`` of the very same observation sets their cuota siblings
    aggregate, and feed no annual total — the totals sum cuotas.

    The ``*-tipo-*`` entries are the rate-specific BOX layer: one binding per
    official rate box, each admitting a single ``applied_rate``. They complement
    the rate-blind tier bindings rather than replacing them -- the tier bindings
    keep feeding the annual total and therefore keep rows whose rate the ledger
    never recorded, which a rate-specific binding deliberately drops.
    """
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    iva_binding_ids = {binding.id for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert iva_binding_ids == {
        "modelo-390-iva-repercutido-general-cuota",
        "modelo-390-iva-repercutido-reducido-cuota",
        "modelo-390-iva-repercutido-super-reducido-cuota",
        "modelo-390-iva-repercutido-general-base",
        "modelo-390-iva-repercutido-reducido-base",
        "modelo-390-iva-repercutido-super-reducido-base",
        "modelo-390-iva-repercutido-zero-base",
        "modelo-390-iva-repercutido-tipo-21-base",
        "modelo-390-iva-repercutido-tipo-21-cuota",
        "modelo-390-iva-repercutido-tipo-10-base",
        "modelo-390-iva-repercutido-tipo-10-cuota",
        "modelo-390-iva-repercutido-tipo-7-5-base",
        "modelo-390-iva-repercutido-tipo-7-5-cuota",
        "modelo-390-iva-repercutido-tipo-5-base",
        "modelo-390-iva-repercutido-tipo-5-cuota",
        "modelo-390-iva-repercutido-tipo-4-base",
        "modelo-390-iva-repercutido-tipo-4-cuota",
        "modelo-390-iva-repercutido-tipo-2-base",
        "modelo-390-iva-repercutido-tipo-2-cuota",
        "modelo-390-iva-repercutido-tipo-0-base",
        "modelo-390-iva-repercutido-tipo-0-cuota",
        "modelo-390-iva-soportado-interiores-cuota",
        "modelo-390-iva-soportado-interiores-base",
        "modelo-390-iva-soportado-importaciones-cuota",
        "modelo-390-iva-autorepercutido-intracomunitaria-cuota",
        "modelo-390-iva-recargo-equivalencia-general-cuota",
        "modelo-390-iva-recargo-equivalencia-reducido-cuota",
        "modelo-390-iva-recargo-equivalencia-super-reducido-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-5-2-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-1-4-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-1-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-0-62-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-0-5-cuota",
        "modelo-390-iva-recargo-equivalencia-tipo-0-26-cuota",
        "modelo-390-volumen-entregas-intracomunitarias-base",
        "modelo-390-volumen-exportaciones-exentas-base",
        # AIC (adquisiciones intracomunitarias) rate-specific box layer -- see
        # civa.anual.aic.bienes.tipo-0.base__civa.anual.aic.servicios.tipo-21.cuota.toml.
        "modelo-390-iva-aic-bienes-tipo-0-base",
        "modelo-390-iva-aic-bienes-tipo-0-cuota",
        "modelo-390-iva-aic-bienes-tipo-2-base",
        "modelo-390-iva-aic-bienes-tipo-2-cuota",
        "modelo-390-iva-aic-bienes-tipo-4-base",
        "modelo-390-iva-aic-bienes-tipo-4-cuota",
        "modelo-390-iva-aic-bienes-tipo-5-base",
        "modelo-390-iva-aic-bienes-tipo-5-cuota",
        "modelo-390-iva-aic-bienes-tipo-7-5-base",
        "modelo-390-iva-aic-bienes-tipo-7-5-cuota",
        "modelo-390-iva-aic-bienes-tipo-10-base",
        "modelo-390-iva-aic-bienes-tipo-10-cuota",
        "modelo-390-iva-aic-bienes-tipo-21-base",
        "modelo-390-iva-aic-bienes-tipo-21-cuota",
        "modelo-390-iva-aic-servicios-tipo-0-base",
        "modelo-390-iva-aic-servicios-tipo-0-cuota",
        "modelo-390-iva-aic-servicios-tipo-2-base",
        "modelo-390-iva-aic-servicios-tipo-2-cuota",
        "modelo-390-iva-aic-servicios-tipo-4-base",
        "modelo-390-iva-aic-servicios-tipo-4-cuota",
        "modelo-390-iva-aic-servicios-tipo-5-base",
        "modelo-390-iva-aic-servicios-tipo-5-cuota",
        "modelo-390-iva-aic-servicios-tipo-7-5-base",
        "modelo-390-iva-aic-servicios-tipo-7-5-cuota",
        "modelo-390-iva-aic-servicios-tipo-10-base",
        "modelo-390-iva-aic-servicios-tipo-10-cuota",
        "modelo-390-iva-aic-servicios-tipo-21-base",
        "modelo-390-iva-aic-servicios-tipo-21-cuota",
        # AIC rate-blind per-tier base bindings (the total layer for the box
        # layer above, mirroring the domestic ordinario zero/general/reduced/
        # super_reduced blind bindings).
        "modelo-390-iva-aic-bienes-zero-blind-base",
        "modelo-390-iva-aic-bienes-super-reduced-blind-base",
        "modelo-390-iva-aic-bienes-reduced-blind-base",
        "modelo-390-iva-aic-bienes-general-blind-base",
        "modelo-390-iva-aic-servicios-zero-blind-base",
        "modelo-390-iva-aic-servicios-super-reduced-blind-base",
        "modelo-390-iva-aic-servicios-reduced-blind-base",
        "modelo-390-iva-aic-servicios-general-blind-base",
        # Domestic reverse-charge (ISP interior, LIVA art. 84.Uno.2) -- boxes
        # [27]/[28], previously fed in error by the AIC blind binding above.
        "modelo-390-iva-autorepercutido-interior-base",
        "modelo-390-iva-autorepercutido-interior-cuota",
    }


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_declares_annual_reconciliation_predicates(revision_id: str) -> None:
    """The annual result totals are blocked when they drift from the four 303s."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    predicates = {predicate.predicate_id: predicate for predicate in revision.verification_predicates}

    for predicate_id, computed_id, reconciliation_id, expression, legal_refs in _M390_RECONCILIATION_PREDICATES:
        predicate = predicates[predicate_id]
        assert computed_id in casilla_ids
        assert reconciliation_id in casilla_ids
        assert predicate.expression == expression
        assert predicate.finding_kind == "BLOCKING_RULE"
        assert set(str(ref) for ref in predicate.legal_refs) == legal_refs


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_declares_annual_compensation_result_fields(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    relations = {rel.id: rel for rel in revision.relations}
    compensation_source_ids = (
        _M303_COMPENSACION_GENERADA_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_COMPENSACION_DISPONIBLE_CASILLA,
        _M303_COMPENSACION_POSTERIOR_CASILLA,
    )

    assert casillas[_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA].number == "97"
    assert casillas[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA].number == "662"
    box_97_binding = bindings["modelo-390-prev-303-compensacion-ultimo-periodo"]
    box_662_binding = bindings["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"]
    assert box_97_binding.source == "iva_compensation_annual_partition"
    box_97_selector: Any = box_97_binding.selector
    assert box_97_selector.source_modelo == "303"
    assert binding_source_casilla_ids(box_97_binding) == compensation_source_ids
    assert box_97_selector.partition_output == "last_period_amount"
    assert box_662_binding.source == "iva_compensation_annual_partition"
    box_662_selector: Any = box_662_binding.selector
    assert box_662_selector.source_modelo == "303"
    assert binding_source_casilla_ids(box_662_binding) == compensation_source_ids
    assert box_662_selector.partition_output == "generated_not_in_last_amount"
    assert "modelo-390-rel-303-compensacion-ultimo-periodo" not in relations
    assert "modelo-390-rel-303-compensacion-generada-ejercicio-no-97" not in relations

    from ..bindings import iva_compensation_annual_partition_requirement

    requirement = iva_compensation_annual_partition_requirement(revision)
    assert requirement is not None
    assert requirement.binding_ids == tuple(sorted((box_97_binding.id, box_662_binding.id)))
    assert requirement.last_period_amount_binding_id == box_97_binding.id
    assert requirement.generated_not_in_last_amount_binding_id == box_662_binding.id
    assert requirement.dependency_treatment == "direct_annual_settlement"


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_declares_prorrata_regularizacion_annual_field(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    export_fields = {
        field.id: field for layout in revision.export_layouts for record in layout.records for field in record.fields
    }

    casilla = casillas[_M390_PRORRATA_REGULARIZACION_CASILLA]
    assert casilla.number == "522"
    assert casilla.input_kind is InputKind.MANUAL
    assert casilla.binding is None
    assert "ley-37-1992:art-104" in casilla.legal_refs
    assert "ley-37-1992:art-105" in casilla.legal_refs
    assert casilla.export_refs == ("modelo-390-page-04-casilla-regularizacion-prorrata-definitiva",)

    binding = bindings["modelo-390-prorrata-regularizacion-anual"]
    assert binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
        "source_periods": _M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS,
        "regularizacion_output": "modelo_390_regularizacion_anual",
    }
    assert binding_aggregation_op(binding) is BindingAggregationOp.SUM
    assert "ley-37-1992:art-104" in binding.legal_refs
    assert "ley-37-1992:art-105" in binding.legal_refs

    field = export_fields["modelo-390-page-04-casilla-regularizacion-prorrata-definitiva"]
    assert field.casilla_id == _M390_PRORRATA_REGULARIZACION_CASILLA
    assert field.offset == _M390_PAGE_04_REGULARIZACION_OFFSETS[revision_id]["prorrata"]
    assert field.length == 17
    assert field.signed is True


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_declares_bienes_inversion_regularizacion_annual_field(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    export_fields = {
        field.id: field for layout in revision.export_layouts for record in layout.records for field in record.fields
    }

    casilla = casillas[_M390_BIENES_INVERSION_REGULARIZACION_CASILLA]
    assert casilla.number == "63"
    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding == "modelo-390-bienes-inversion-regularizacion-casilla-63"
    assert "ley-37-1992:art-107" in casilla.legal_refs
    assert "ley-37-1992:art-110" in casilla.legal_refs
    assert casilla.export_refs == ("modelo-390-page-04-casilla-regularizacion-bienes-inversion",)
    assert casillas[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA].number == "662"

    binding = bindings["modelo-390-bienes-inversion-regularizacion-casilla-63"]
    assert binding.source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_390_casilla_63",
    }
    assert "ley-37-1992:art-107" in binding.legal_refs
    assert "ley-37-1992:art-110" in binding.legal_refs

    field = export_fields["modelo-390-page-04-casilla-regularizacion-bienes-inversion"]
    assert field.casilla_id == _M390_BIENES_INVERSION_REGULARIZACION_CASILLA
    assert field.offset == _M390_PAGE_04_REGULARIZACION_OFFSETS[revision_id]["bienes_inversion"]
    assert field.length == 17
    assert field.signed is True


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_prorrata_regularizacion_is_in_annual_deducible_formula(revision_id: str) -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    formula = next(item for item in revision.formulas if item.target_casilla_id == _M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA)

    assert _M390_PRORRATA_REGULARIZACION_CASILLA in set(expression_casilla_refs(formula.expression))
    assert _M390_BIENES_INVERSION_REGULARIZACION_CASILLA in set(expression_casilla_refs(formula.expression))


@pytest.mark.parametrize("revision_id", _M390_REVISION_IDS)
def test_modelo_390_iva_bindings_resolve_against_annual_substrate_observations(revision_id: str) -> None:
    from ....iva.flow import IvaFlowDirection
    from ....iva.schema import IvaCategory, IvaRateKind
    from ..ledger_bindings import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_390()
    revision = modelo.revisions[revision_id]
    # Simulate annual aggregation across four quarters
    quarterly_iva_amounts = [Decimal("210"), Decimal("315"), Decimal("420"), Decimal("525")]
    observations = [
        IvaLedgerObservation(
            ledger_id=f"q{idx}-rep",
            transaction_date=date(2025, idx * 3, 15),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1000") * idx,
            iva_amount=amount,
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        )
        for idx, amount in enumerate(quarterly_iva_amounts, start=1)
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)

    # Assert structural wiring: the expected binding key must be present.
    expected_binding_key = "modelo-390-iva-repercutido-general-cuota"
    assert expected_binding_key in result, f"{expected_binding_key!r} must be resolved by the annual IVA binding"

    # The binding aggregates iva_amount via sum — the resolved value must equal
    # the sum of iva_amounts from all observations provided to the resolver.
    # This is derived from the test's own input data list, not hand-computed.
    expected_total = sum((obs.iva_amount for obs in observations), Decimal("0"))
    assert result[expected_binding_key] == expected_total

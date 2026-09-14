"""Typed fixtures owned by artifact-runtime consumer tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import validated_casilla_id
from .....core.classification.policies import SensitivityClass
from .....core.tax_domain import TaxDomain
from ..facts.schema import GovernedFact, GovernedFactCatalogue
from ..runtime_catalogues import (
    ApoderamientoScopeRecord,
    CountryVocabularyRecord,
    PublishedIvaPlaceOfSupplyRule,
    PublishedIvaRegulation,
    PublishedRecargoBand,
    RuntimeRegistryCatalogues,
    SpanishPostalTerritory,
    TerritoryCarveOut,
)
from ..schema import (
    BindingDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
)
from ..schema_base import EvidenceTier
from ..schema_exports import ExportLayoutDefinition
from ..schema_input_kind import InputKind
from ..schema_references import LegalReference, PeriodSelector, SourceReference
from ..schema_revision_members import ApplicationLinkDefinition
from ..schema_surfaces import CasillaDefinition
from ..schema_verification import WorkbookParityReference

_LEGAL_ID = "ley-35-2006:art-1"
_SOURCE_ID = "aeat-dr-130-2019-v12"
_WORKBOOK_SOURCE_ID = "aeat-dr-130-2019-v12-layout"


def _minimal_source_ref() -> SourceReference:
    return SourceReference(
        id=_SOURCE_ID,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="registry/aeat/sources/aeat-dr-130-2019-v12.pdf",
        sha256="a" * 64,
        bytes=1024,
        retrieved_at=date(2024, 1, 1),
        source_url="https://www.aeat.es/",
        review_status="pending_review",
    )


def _minimal_catalogues() -> RegistryCatalogues:
    legal = LegalReference(
        id=_LEGAL_ID,
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="boe",
        kind="ley",
        corpus_ref="boe/lirpf#art-1",
        document_id="BOE-A-2006-20764",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        effective_from=date(2006, 11, 30),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 7, 1),
        reviewed_by="artifact runtime fixture",
        required_text=("art-1",),
    )
    source = _minimal_source_ref()
    workbook = source.model_copy(
        update={"id": _WORKBOOK_SOURCE_ID, "evidence_tier": "layout_authority", "kind": "record_design"}
    )
    tax_id_format = GovernedFact.model_validate(
        {
            "fact_id": "spanish-tax-identifier-format",
            "family": "mapping",
            "provider_id": "artifact-fixture",
            "variants": (
                {
                    "variant_id": "spanish-tax-identifier-format:fixture",
                    "date_axis": "filing_period",
                    "valid_from": date(2024, 1, 1),
                    "legal_refs": (_LEGAL_ID,),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                    "payload": {
                        "kind": "mapping",
                        "entries": (
                            {"key": "tax_id.width", "value": "9"},
                            {"key": "tax_id.country_prefix", "value": "ES"},
                            {"key": "tax_id.country_prefixed_width", "value": "11"},
                            {"key": "tax_id.country_prefix_strip_width", "value": "2"},
                            {"key": "tax_id.leaders.prefixed_nif", "value": "KLM"},
                            {"key": "tax_id.leaders.nie", "value": "XYZ"},
                            {"key": "tax_id.leaders.cif", "value": "ABCDEFGHJNPQRSUVW"},
                            {"key": "tax_id.check.nif_letters", "value": "TRWAGMYFPDXBNJZSQVHLCKE"},
                            {"key": "tax_id.check.nie_prefix.X", "value": "0"},
                            {"key": "tax_id.check.nie_prefix.Y", "value": "1"},
                            {"key": "tax_id.check.nie_prefix.Z", "value": "2"},
                            {"key": "tax_id.check.cif_digit_only_kinds", "value": "ABEH"},
                            {"key": "tax_id.check.cif_letter_only_kinds", "value": "PQRSNW"},
                            {"key": "tax_id.check.cif_letter_table", "value": "JABCDEFGHI"},
                        ),
                    },
                },
            ),
        }
    )
    runtime = RuntimeRegistryCatalogues(
        iva_regulations={
            "fixture-exempt": PublishedIvaRegulation(
                category="fixture-exempt",
                requires_reverse_charge=False,
                requires_supplier_iva_id=False,
                manual_references=(),
                citations=(),
                notes="No legal treatment is asserted by this fixture row.",
                legal_basis_exempt=True,
            )
        },
        iva_place_of_supply={
            "fixture-exempt": PublishedIvaPlaceOfSupplyRule(
                rule_id="fixture-exempt",
                notes="No placement is asserted by this fixture row.",
                legal_basis_exempt=True,
            )
        },
        countries={
            "ES": CountryVocabularyRecord(code="ES", alpha3="ESP", names=("Espana",)),
        },
        spanish_postal_territories={
            "28": SpanishPostalTerritory(
                postal_prefixes=("28",),
                scope="peninsula_baleares",
                name="Madrid",
                legal_refs=(_LEGAL_ID,),
            )
        },
        territory_carve_outs={
            "ES": TerritoryCarveOut(
                code="ES",
                name="Espana",
                establishes_nothing=True,
                legal_refs=(_LEGAL_ID,),
            )
        },
        recargo_bands={
            "all": PublishedRecargoBand(
                id="all",
                min_completed_months=0,
                surcharge_pct=Decimal("1"),
                legal_ref=_LEGAL_ID,
            )
        },
        apoderamientos_version="fixture-v1",
        apoderamientos_scopes={
            "GENERAL": ApoderamientoScopeRecord(
                code="GENERAL",
                name_es="General",
                name_en="General",
                name_ca="General",
                name_hu="Altalanos",
            )
        },
    ).require_complete()
    return RegistryCatalogues(
        legal={_LEGAL_ID: legal},
        sources={source.id: source, workbook.id: workbook},
        facts=GovernedFactCatalogue(facts={tax_id_format.fact_id: tax_id_format}),
        runtime=runtime,
    )


def _minimal_revision(
    *, bindings: tuple[BindingDefinition, ...] = (), export_layouts: tuple[ExportLayoutDefinition, ...] = ()
) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        review_status="agent_reviewed",
        reviewed_by="artifact runtime fixture",
        reviewed_at=date(2026, 7, 1),
        authority_grade=RegistryAuthorityGrade.FILING,
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=(_LEGAL_ID,),
        source_refs=(_SOURCE_ID,),
        orden_aplicabilidad=(_LEGAL_ID,),
        casillas=(
            CasillaDefinition(
                id=validated_casilla_id("01", surface="artifact_runtime_fixture"),
                number="01",
                localization_keys=("test.schema.casilla.label",),
                section=("test",),
                input_kind=InputKind.MANUAL,
                legal_refs=(_LEGAL_ID,),
                source_refs=(_SOURCE_ID,),
            ),
        ),
        workbook_parity_refs=(
            WorkbookParityReference(
                id="wp.test",
                workbook_source=_WORKBOOK_SOURCE_ID,
                fixture_id="test",
                formula_coverage="static_layout",
                runner_required=False,
                tolerance=0,
                legal_refs=(_LEGAL_ID,),
                source_refs=(_WORKBOOK_SOURCE_ID,),
            ),
        ),
        application_links=(
            ApplicationLinkDefinition(
                id="al.test",
                surface="filing",
                consumer="artifact-runtime-fixture",
                requires_snapshot=True,
                legal_refs=(_LEGAL_ID,),
                source_refs=(_SOURCE_ID,),
            ),
        ),
        bindings=bindings,
        export_layouts=export_layouts,
    )


def _minimal_modelo(revision: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition(
        id="130",
        title_localization_key="test.schema.modelo.130.title",
        official_name_localization_key="test.schema.modelo.130.official_name",
        tax_domain=TaxDomain("iva"),
        cadence="annual",
        jurisdiction="ES-AEAT",
        output_sensitivity=SensitivityClass.FINANCIAL,
        legal_refs=(_LEGAL_ID,),
        source_refs=(_SOURCE_ID,),
        revisions={revision.id: revision},
    )

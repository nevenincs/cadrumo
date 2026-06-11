"""Shared support for split calculation-registry tests."""


from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import ValidationError as ValidationError

from .....core import TaxDomain, freeze_toml
from .....core.classification import SensitivityClass
from .....core.config import Settings
from .....core.resources import bundled_path
from .. import InputKind, RegistryValidationError, ValidatedRegistryAuthority, load_registry_tree
from .._schema import (
    ApplicationLinkDefinition,
    CalculationCompletenessCasilla,
    CalculationCompletenessManifest,
    CasillaDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    FormulaDefinition,
    FormulaExpression,
    LegalReference,
    LiveCrossReferenceDecision,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    RegistryCatalogues,
    RegistrySnapshot,
    RelationDefinition,
    SourceReference,
    SupportRemovalDecisionDefinition,
    VerificationExpectationDefinition,
    WorkbookParityReference,
)
from .._validate_references import _check_all_id_references

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = [
    "ExportFieldDefinition",
    "ExportRecordDefinition",
    "ExtractionTargetDefinition",
    "FormulaExpression",
    "RegistryValidationError",
    "ValidatedRegistryAuthority",
    "ValidationError",
    "_check_all_id_references",
    "freeze_toml",
    "logging",
]


def _load_registry() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:

    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return modelos, catalogues


def _snapshot_for_revision(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    revision: ModeloRevision,
) -> RegistrySnapshot:
    """Build a minimal snapshot for a given revision without running integrity checks."""
    from .._snapshot import _build_validated_snapshot

    filing_year = revision.period_selector.year_from or 2024
    period = next(iter(revision.period_selector.periods))
    return _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
    )


_DUMMY_LEGAL_ID = "lirpf:art-1"

_DUMMY_SOURCE_ID = "aeat-dr-130-2019-v12"


def _minimal_legal_ref() -> LegalReference:
    return LegalReference(
        id=_DUMMY_LEGAL_ID,
        evidence_tier="legal_authority",
        authority="boe",
        kind="ley",
        corpus_ref="boe/lirpf#art-1",
        document_id="BOE-A-2006-20764",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        effective_from=date(2006, 11, 30),
        review_status="reviewed",
    )


def _minimal_source_ref() -> SourceReference:
    return SourceReference(
        id=_DUMMY_SOURCE_ID,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="registry/aeat/sources/aeat-dr-130-2019-v12.pdf",
        sha256="a" * 64,
        bytes=1024,
        retrieved_at=date(2024, 1, 1),
        source_url=f"{Settings.external_constants().aeat.domains.legacy_www}/",
        review_status="reviewed",
    )


def _minimal_catalogues() -> RegistryCatalogues:
    return RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref()},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref()},
    )


def _minimal_casilla(casilla_id: str = "01") -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        label=f"Casilla {casilla_id}",
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def _minimal_workbook_ref(source_ref: str = _DUMMY_SOURCE_ID) -> WorkbookParityReference:
    from .._schema import WorkbookParityReference

    return WorkbookParityReference(
        id="wp.test",
        workbook_source=source_ref,
        fixture_id="test",
        formula_coverage="static_layout",
        runner_required=False,
        tolerance=Decimal("0"),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(source_ref,),
    )


def _minimal_application_link(
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "export",
        "deadline",
        "portal",
        "extractor",
        "workflow",
        "communication",
        "payer_delivery",
    ] = "filing",
) -> ApplicationLinkDefinition:
    return ApplicationLinkDefinition(
        id="al.test",
        surface=surface,
        consumer="test",
        requires_snapshot=True,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def _minimal_revision(
    *,
    casillas: tuple[CasillaDefinition, ...] = (),
    extra_workbook_ref: WorkbookParityReference | None = None,
    application_links: tuple[ApplicationLinkDefinition, ...] | None = None,
    formulas: tuple[FormulaDefinition, ...] = (),
    parameters: tuple[ParameterDefinition, ...] = (),
    bindings: tuple[DataBindingDefinition, ...] = (),
    relations: tuple[RelationDefinition, ...] = (),
    extraction_profiles: tuple[ExtractionProfileDefinition, ...] = (),
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = (),
    verification_expectations: tuple[VerificationExpectationDefinition, ...] = (),
    support_removal_decisions: tuple[SupportRemovalDecisionDefinition, ...] = (),
    constructs: tuple[ConstructDefinition, ...] = (),
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = (),
    export_layouts: tuple[ExportLayoutDefinition, ...] = (),
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = (),
) -> ModeloRevision:
    from .._schema import PeriodSelector

    workbook_ref = extra_workbook_ref or _minimal_workbook_ref()
    casillas = casillas or (_minimal_casilla(),)
    app_links = application_links if application_links is not None else (_minimal_application_link("filing"),)
    return ModeloRevision(
        id="test-revision",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
        casillas=casillas,
        workbook_parity_refs=(workbook_ref,),
        application_links=app_links,
        formulas=formulas,
        parameters=parameters,
        bindings=bindings,
        relations=relations,
        extraction_profiles=extraction_profiles,
        live_cross_references=live_cross_references,
        verification_expectations=verification_expectations,
        support_removal_decisions=support_removal_decisions,
        constructs=constructs,
        dependency_classifications=dependency_classifications,
        export_layouts=export_layouts,
        deadline_windows=deadline_windows,
    )


def _minimal_modelo(revision: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition(
        id="130",
        title="Test",
        official_name="Test",
        tax_domain=TaxDomain.IVA,
        cadence="annual",
        jurisdiction="ES-AEAT",
        output_sensitivity=SensitivityClass.FINANCIAL,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
        revisions={"test-revision": revision},
    )


def _build_minimal_snapshot(revision: ModeloRevision) -> RegistrySnapshot:
    catalogues = _minimal_catalogues()
    modelo = _minimal_modelo(revision)
    return _snapshot_for_revision(modelo, catalogues, revision)


def _build_snapshot_with_missing_legal(revision: ModeloRevision, missing_legal_id: str) -> RegistrySnapshot:
    """Build a snapshot whose `legal` map omits a ref that the revision content references.

    This is the only way to surface a `_check_all_id_references` failure for legal_refs
    fields: the ref must be in the revision content but absent from the snapshot.legal map.
    We patch the snapshot object using model_copy after normal construction.
    """
    # First build a snapshot where the bad ID is in the catalogue so construction succeeds.
    extra_legal = _minimal_legal_ref().model_copy(update={"id": missing_legal_id})
    augmented_catalogues = RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref(), missing_legal_id: extra_legal},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref()},
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    # Now remove the ref from the snapshot's legal map to simulate the gap.
    patched_legal = {k: v for k, v in snapshot.legal.items() if k != missing_legal_id}
    return snapshot.model_copy(update={"legal": patched_legal})


def _build_snapshot_with_missing_source(revision: ModeloRevision, missing_source_id: str) -> RegistrySnapshot:
    """Build a snapshot whose `sources` map omits a ref that the revision content references."""
    extra_source = _minimal_source_ref().model_copy(update={"id": missing_source_id})
    augmented_catalogues = RegistryCatalogues(
        legal={_DUMMY_LEGAL_ID: _minimal_legal_ref()},
        sources={_DUMMY_SOURCE_ID: _minimal_source_ref(), missing_source_id: extra_source},
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != missing_source_id}
    return snapshot.model_copy(update={"sources": patched_sources})


def _segmented_casilla(
    casilla_id: str,
    number: str,
    segmento: str | None,
) -> CasillaDefinition:
    """A minimal manual casilla with an explicit number and segmento."""
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        segmento=segmento,
        label=f"Casilla {casilla_id}",
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def _single_segment_casilla() -> CasillaDefinition:
    """A real single-segment casilla, the shape every existing modelo authors."""
    return CasillaDefinition(
        id="00592",
        number="00592",
        label="Cuota liquida",
        section=("liquidacion",),
        data_type="money",
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )


def _completeness_manifest(
    casillas: tuple[CalculationCompletenessCasilla, ...],
) -> CalculationCompletenessManifest:
    """A minimal calculation-completeness manifest grounded on the dummy catalogues."""
    return CalculationCompletenessManifest(
        source_ref=_DUMMY_SOURCE_ID,
        casillas=casillas,
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )

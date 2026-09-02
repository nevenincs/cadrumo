"""Shared support for split calculation-registry tests."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import ValidationError as ValidationError

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.classification.policies import SensitivityClass
from .....core.config import Settings
from .....core.tax_domain import TaxDomain
from .....core.toml import freeze_toml
from .._snapshot_internals import _build_validated_snapshot as build_snapshot_at_grade
from ..authority import ValidatedRegistryAuthority
from ..errors import RegistryValidationError
from ..schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from ..schema_base import EvidenceTier
from ..schema_deadlines import DeadlineWindowDefinition
from ..schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ..schema_extraction import (
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
)
from ..schema_formula import FormulaExpression, ParameterDefinition
from ..schema_input_kind import InputKind
from ..schema_references import LegalReference, SourceReference
from ..schema_revision_members import (
    ApplicationLinkDefinition,
    ConstructDefinition,
    DependencyClassificationDefinition,
)
from ..schema_surfaces import (
    CalculationCompletenessCasilla,
    CalculationCompletenessManifest,
    CasillaDefinition,
    RelationDefinition,
)
from ..schema_verification import LiveCrossReferenceDecision, VerificationExpectationDefinition, WorkbookParityReference
from ..validate_references import check_all_id_references

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = [
    "REFERENCE_LEGAL_ID",
    "REFERENCE_SOURCE_ID",
    "ExportFieldDefinition",
    "ExportRecordDefinition",
    "ExtractionTargetDefinition",
    "FormulaExpression",
    "RegistryValidationError",
    "ValidatedRegistryAuthority",
    "ValidationError",
    "build_minimal_snapshot",
    "build_snapshot_with_missing_legal",
    "build_snapshot_with_missing_source",
    "check_all_id_references",
    "completeness_manifest",
    "freeze_toml",
    "logging",
    "minimal_application_link",
    "minimal_casilla",
    "minimal_catalogues",
    "minimal_legal_ref",
    "minimal_modelo",
    "minimal_revision",
    "minimal_source_ref",
    "minimal_workbook_ref",
    "segmented_casilla",
    "single_segment_casilla",
    "snapshot_for_revision",
]


def _snapshot_for_revision(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    revision: ModeloRevision,
) -> RegistrySnapshot:
    """Build a minimal snapshot for a given revision without running integrity checks."""

    selector = revision.period_selector
    filing_year = selector.years[0] if selector.years else selector.year_from
    assert filing_year is not None
    period = selector.periods[0]
    # APPLICABILITY grade, not the FILING default. These fixtures exist to
    # exercise REFERENTIAL integrity -- dangling ids, bound casillas with no
    # binding definition -- and carry no export layout, so a filing-grade
    # snapshot refuses on the missing filing capability before any reference is
    # ever checked. The integrity checks themselves are grade-independent.
    return build_snapshot_at_grade(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )


_REFERENCE_LEGAL_ID = "ley-35-2006:art-1"

_REFERENCE_SOURCE_ID = "aeat-dr-130-2019-v12"
_REFERENCE_WORKBOOK_SOURCE_ID = "aeat-dr-130-2019-v12-layout"
_DEFAULT_MINIMAL_CASILLA_ID: CasillaId = validated_casilla_id("01", surface="_DEFAULT_MINIMAL_CASILLA_ID")
_SINGLE_SEGMENT_CASILLA_ID: CasillaId = validated_casilla_id("00592", surface="_SINGLE_SEGMENT_CASILLA_ID")


def _minimal_legal_ref() -> LegalReference:
    return LegalReference(
        id=_REFERENCE_LEGAL_ID,
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="boe",
        kind="ley",
        corpus_ref="boe/lirpf#art-1",
        document_id="BOE-A-2006-20764",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        effective_from=date(2006, 11, 30),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 7, 1),
        reviewed_by="codex test fixture",
        required_text=("art-1",),
    )


def _minimal_source_ref() -> SourceReference:
    return SourceReference(
        id=_REFERENCE_SOURCE_ID,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="registry/aeat/sources/aeat-dr-130-2019-v12.pdf",
        sha256="a" * 64,
        bytes=1024,
        retrieved_at=date(2024, 1, 1),
        source_url=f"{Settings.external_constants().aeat.domains.legacy_www}/",
        review_status="pending_review",
    )


def _minimal_workbook_source_ref() -> SourceReference:
    return _minimal_source_ref().model_copy(
        update={
            "id": _REFERENCE_WORKBOOK_SOURCE_ID,
            "evidence_tier": "layout_authority",
            "kind": "record_design",
            "corpus_path": "registry/aeat/sources/aeat-dr-130-2019-v12.xls",
        },
    )


def _minimal_source_refs() -> dict[str, SourceReference]:
    return {
        _REFERENCE_SOURCE_ID: _minimal_source_ref(),
        _REFERENCE_WORKBOOK_SOURCE_ID: _minimal_workbook_source_ref(),
    }


def _minimal_catalogues() -> RegistryCatalogues:
    return RegistryCatalogues(
        legal={_REFERENCE_LEGAL_ID: _minimal_legal_ref()},
        sources=_minimal_source_refs(),
    )


def _minimal_casilla(casilla_id: CasillaId = _DEFAULT_MINIMAL_CASILLA_ID) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )


def _minimal_workbook_ref(source_ref: str = _REFERENCE_WORKBOOK_SOURCE_ID) -> WorkbookParityReference:
    from ..schema_verification import WorkbookParityReference

    return WorkbookParityReference(
        id="wp.test",
        workbook_source=source_ref,
        fixture_id="test",
        formula_coverage="static_layout",
        runner_required=False,
        tolerance=Decimal("0"),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(source_ref,),
    )


def _minimal_application_link(
    surface: Literal[
        "calculation",
        "filing",
        "review",
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
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
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
    constructs: tuple[ConstructDefinition, ...] = (),
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = (),
    export_layouts: tuple[ExportLayoutDefinition, ...] = (),
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = (),
) -> ModeloRevision:
    from ..schema_references import PeriodSelector

    workbook_ref = extra_workbook_ref or _minimal_workbook_ref()
    casillas = casillas or (_minimal_casilla(),)
    app_links = application_links if application_links is not None else (_minimal_application_link("filing"),)
    return ModeloRevision(
        id="test-revision",
        # These fixtures exercise REFERENTIAL integrity -- dangling casilla refs,
        # bound casillas with no binding. Without a review stamp the revision
        # defaults to pending_review, and a filing-grade snapshot refuses on that
        # first, so the assertions the tests exist for never run.
        review_status="agent_reviewed",
        reviewed_by="codex test fixture",
        reviewed_at=date(2026, 7, 1),
        # Same reasoning one rung further: an undeclared authority_grade is itself
        # a refusal now, and it lands before the referential assertions too. These
        # fixtures are built to carry casilla and binding REFERENCES, not to
        # compute amounts or back a filing, so applicability is the rung they are
        # intended to support rather than a reading of what they contain.
        authority_grade="applicability",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
        orden_aplicabilidad=(_REFERENCE_LEGAL_ID,),
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
        constructs=constructs,
        dependency_classifications=dependency_classifications,
        export_layouts=export_layouts,
        deadline_windows=deadline_windows,
    )


def _minimal_modelo(revision: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition(
        id="130",
        title_localization_key="test.schema.modelo.130.title",
        official_name_localization_key="test.schema.modelo.130.official_name",
        tax_domain=TaxDomain.IVA,
        cadence="annual",
        jurisdiction="ES-AEAT",
        output_sensitivity=SensitivityClass.FINANCIAL,
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
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
        legal={_REFERENCE_LEGAL_ID: _minimal_legal_ref(), missing_legal_id: extra_legal},
        sources=_minimal_source_refs(),
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    # Now remove the ref from the snapshot's legal map to simulate the gap.
    patched_legal = {k: v for k, v in snapshot.legal.items() if k != missing_legal_id}
    return snapshot.model_copy(update={"legal": patched_legal})


def _build_snapshot_with_missing_source(revision: ModeloRevision, missing_source_id: str) -> RegistrySnapshot:
    """Build a snapshot whose `sources` map omits a ref that the revision content references."""
    extra_source = _minimal_source_ref().model_copy(update={"id": missing_source_id})
    sources = _minimal_source_refs()
    sources[missing_source_id] = extra_source
    augmented_catalogues = RegistryCatalogues(
        legal={_REFERENCE_LEGAL_ID: _minimal_legal_ref()},
        sources=sources,
    )
    modelo = _minimal_modelo(revision)
    snapshot = _snapshot_for_revision(modelo, augmented_catalogues, revision)
    patched_sources = {k: v for k, v in snapshot.sources.items() if k != missing_source_id}
    return snapshot.model_copy(update={"sources": patched_sources})


def _segmented_casilla(
    casilla_id: CasillaId,
    number: str,
    segmento: str | None,
) -> CasillaDefinition:
    """A minimal manual casilla with an explicit number and segmento."""
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        segmento=segmento,
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )


def _single_segment_casilla() -> CasillaDefinition:
    """A real single-segment casilla, the shape every existing modelo authors."""
    return CasillaDefinition(
        id=_SINGLE_SEGMENT_CASILLA_ID,
        number="00592",
        localization_keys=("test.schema.casilla.label",),
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
        source_ref=_REFERENCE_SOURCE_ID,
        casillas=casillas,
        legal_refs=(_REFERENCE_LEGAL_ID,),
        source_refs=(_REFERENCE_SOURCE_ID,),
    )


REFERENCE_LEGAL_ID = _REFERENCE_LEGAL_ID
REFERENCE_SOURCE_ID = _REFERENCE_SOURCE_ID
build_minimal_snapshot = _build_minimal_snapshot
build_snapshot_with_missing_legal = _build_snapshot_with_missing_legal
build_snapshot_with_missing_source = _build_snapshot_with_missing_source
completeness_manifest = _completeness_manifest
minimal_application_link = _minimal_application_link
minimal_casilla = _minimal_casilla
minimal_catalogues = _minimal_catalogues
minimal_legal_ref = _minimal_legal_ref
minimal_modelo = _minimal_modelo
minimal_revision = _minimal_revision
minimal_source_ref = _minimal_source_ref
minimal_workbook_ref = _minimal_workbook_ref
segmented_casilla = _segmented_casilla
single_segment_casilla = _single_segment_casilla
snapshot_for_revision = _snapshot_for_revision

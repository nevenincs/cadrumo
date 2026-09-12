"""Typed fixtures owned by artifact-runtime consumer tests."""

from __future__ import annotations

from datetime import date

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import validated_casilla_id
from .....core.classification.policies import SensitivityClass
from .....core.tax_domain import TaxDomain
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
    return RegistryCatalogues(legal={_LEGAL_ID: legal}, sources={source.id: source, workbook.id: workbook})


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
        tax_domain=TaxDomain.IVA,
        cadence="annual",
        jurisdiction="ES-AEAT",
        output_sensitivity=SensitivityClass.FINANCIAL,
        legal_refs=(_LEGAL_ID,),
        source_refs=(_SOURCE_ID,),
        revisions={revision.id: revision},
    )

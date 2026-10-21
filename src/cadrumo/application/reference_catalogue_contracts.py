"""Typed answers to the bundled public reference reads.

Every frontend that reads the published tax authority, the category
vocabularies, the portal catalogue, the provider list or the representative
scopes receives these projections and no other. They are strict
:class:`~cadrumo.core.json_contract.OutputSchema` subclasses so that the
command line's result envelope, external clients and the terminal
interface carry one shape.

The domain reports and catalogues stay authoritative; these classes pin the
transport shape and hold no behaviour beyond building it from the report and
refusing a row that states one fact two ways.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import Field, NonNegativeInt, model_validator

from ..core.authority_grade import RegistryAuthorityGrade
from ..core.casilla_id import CasillaId
from ..core.filing_year import FilingYear
from ..core.identity.aeat_box import AeatBoxNumber
from ..core.json_contract import OutputSchema
from ..core.period import Period
from ..core.text_bounds import NonEmptyStr
from ..domain.auth.apoderamientos.catalogue import ApoderadoScope
from ..domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ..domain.calculations.registry.query_reports import ModeloDescribeReport
from ..domain.calculations.registry.schema_base import LegalRefs, SourceRefs


def printed_local_work_status(*, supported: bool) -> str:
    """Return the status a modelo row prints for whether local work can be created for the modelo."""
    return "supported-model-level" if supported else "unsupported-local-work"


class ModeloRowPayload(OutputSchema):
    """One modelo row in the list modelos output.

    Whether local work can be created for the modelo is stated once, by
    ``local_work_supported``. The status and the guidance say the same thing to
    a reader of the printed row, so a row whose three members disagree is
    refused rather than printed.
    """

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int
    local_work_supported: bool
    local_work_status: str
    local_work_guidance: str | None = None

    @model_validator(mode="after")
    def _status_and_guidance_follow_the_flag(self) -> Self:
        if self.local_work_status != printed_local_work_status(supported=self.local_work_supported):
            raise ValueError("a modelo row's local-work status restates its local_work_supported member")
        if self.local_work_supported != (self.local_work_guidance is None):
            raise ValueError("a modelo row carries local-work guidance exactly when local work is unsupported")
        return self


class ModeloListResult(OutputSchema):
    """List modelos result."""

    operation: str = "modelo.list"
    year_filter: int | None = None
    domain_filter: str | None = None
    modelo_count: int
    modelos: list[ModeloRowPayload]


class ModeloDescribeResult(OutputSchema):
    """Describe modelo result.

    Complete JSON projection of
    :class:`ModeloDescribeReport`. The
    payload carries every field of the canonical report -- including the
    declared ``authority_grade``, ``jurisdiction``, revision validity bounds,
    per-input-kind casilla counts, and ``legal_refs`` / ``source_refs``
    grounding -- because an operator justifying a revision selection needs the
    same evidence the domain report holds. Build instances through
    :meth:`from_report` rather than field-by-field, so a field added to the
    report cannot silently stop at this boundary.
    """

    operation: str = "modelo.describe"
    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    jurisdiction: str
    revision: str
    authority_grade: RegistryAuthorityGrade | None
    filing_year: FilingYear | None = None
    filing_period: Period | None = None
    period: str | None = None
    revision_ids: list[str]
    periods: list[str]
    valid_from: date
    valid_to: date | None = None
    casilla_count: NonNegativeInt
    manual_casilla_count: NonNegativeInt
    bound_casilla_count: NonNegativeInt
    computed_casilla_count: NonNegativeInt
    binding_count: NonNegativeInt
    formula_count: NonNegativeInt
    legal_refs: list[LegalRefId] = Field(default_factory=list)
    source_refs: list[SourceRefId] = Field(default_factory=list)

    @classmethod
    def from_report(cls, report: ModeloDescribeReport) -> ModeloDescribeResult:
        """Project every field of a canonical describe report.

        Args:
            report: The domain-layer describe report to render.

        Returns:
            The strict payload carrying the report's full field set.
        """
        return cls(
            code=report.code,
            title=report.title,
            official_name=report.official_name,
            tax_domain=report.tax_domain,
            cadence=report.cadence,
            jurisdiction=report.jurisdiction,
            revision=report.revision,
            authority_grade=report.authority_grade,
            filing_year=report.filing_year,
            filing_period=report.filing_period,
            period=report.period,
            revision_ids=list(report.revision_ids),
            periods=list(report.periods),
            valid_from=report.valid_from,
            valid_to=report.valid_to,
            casilla_count=report.casilla_count,
            manual_casilla_count=report.manual_casilla_count,
            bound_casilla_count=report.bound_casilla_count,
            computed_casilla_count=report.computed_casilla_count,
            binding_count=report.binding_count,
            formula_count=report.formula_count,
            legal_refs=list(report.legal_refs),
            source_refs=list(report.source_refs),
        )


class CasillaRowPayload(OutputSchema):
    """One casilla row in the casillas output."""

    casilla_id: CasillaId
    number: str
    input_kind: str
    required: bool
    label: str
    help_text: str | None = None
    section: tuple[str, ...] = ()
    data_type: str
    binding: BindingId | None = None
    formula: str | None = None
    form_number: AeatBoxNumber | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ModeloCasillasResult(OutputSchema):
    """Casillas listing result.

    ``code`` repeats ``modelo`` under the registry report's own name, so a reader
    that knows the report finds every field it carries.
    """

    operation: str = "modelo.casillas"
    code: str
    modelo: str
    revision: str
    filing_year: int | None = None
    filing_period: Period | None = None
    period: str | None = None
    casilla_count: int
    rows: list[CasillaRowPayload]


class ModeloCasillaResult(OutputSchema):
    """Single-casilla semantic detail.

    Projects
    :class:`ModeloCasillaDetailReport`
    into the result: an operator can look up one casilla's official
    label, legal / source grounding, input kind, and, when the casilla is
    computed, the resolved formula ``expression`` from the authoritative
    :class:`CasillaId` definition on the
    resolved registry snapshot, without running a calculation. ``legal_refs``
    and ``source_refs`` stay required so the grounding survives the boundary.
    """

    operation: str = "modelo.casilla"
    code: str
    modelo: str
    revision: str
    filing_year: int | None = None
    filing_period: Period | None = None
    period: str | None = None
    casilla_id: CasillaId
    number: str
    label: str
    help_text: str | None = None
    section: tuple[str, ...] = ()
    data_type: str
    input_kind: str
    required: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    binding: BindingId | None = None
    formula_id: FormulaId | None = None
    formula_expression: dict[str, object] | None = None


class FormulaPayload(OutputSchema):
    """One formula row in the formulas output."""

    formula_id: FormulaId
    target_casilla_id: CasillaId
    input_casilla_ids: tuple[CasillaId, ...]
    input_bindings: tuple[BindingId, ...]
    input_parameters: tuple[ParameterId, ...]
    input_relations: tuple[RelationId, ...]
    expression: dict[str, object]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class FormulasResult(OutputSchema):
    """Formulas listing result."""

    operation: str = "modelo.formulas"
    code: str
    revision: str
    filing_year: int | None = None
    filing_period: Period | None = None
    period: str | None = None
    formula_count: int
    rows: tuple[FormulaPayload, ...]


class ModeloRenamePayload(OutputSchema):
    """One declared per-ejercicio casilla continuity evolution."""

    continuidad_id: str
    from_revision: str
    to_revision: str
    evolution_kind: str


class ModeloPortalCompatibilityRefPayload(OutputSchema):
    """One declared AEAT-portal cross-reference."""

    id: str
    surface: str
    evidence_tier: str


class ModeloSupportMatrixEntryPayload(OutputSchema):
    """One modelo's support-matrix row."""

    modelo_id: str
    title: str
    calculation_class: str
    revision_count: int
    latest_revision_id: RevisionId
    latest_revision_valid_from: str
    supported_revision_ids: list[str]
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    extraction_profile_count: int
    renames: list[ModeloRenamePayload]
    portal_compatibility_refs: list[ModeloPortalCompatibilityRefPayload]


class ModeloSupportMatrixResult(OutputSchema):
    """Registry-wide per-modelo support/capability matrix result."""

    operation: str = "modelo.support_matrix"
    modelo_count: int
    entries: list[ModeloSupportMatrixEntryPayload]


class SpendingCategoryFamilyPayload(OutputSchema):
    """One spending category family entry in the categories catalogue."""

    family: str
    category_ids: list[str]


class LedgerIrpfCategoryPayload(OutputSchema):
    """One IRPF category value exposed by the categories catalogue."""

    id: str
    purpose: str
    directions: list[str]
    net_paid_invoice: bool
    related_category_ids: list[str]


class LedgerCategoriesResult(OutputSchema):
    """The spending and IRPF category vocabularies a ledger row may carry."""

    families: list[SpendingCategoryFamilyPayload]
    category_ids: list[str]
    irpf_categories: list[LedgerIrpfCategoryPayload]
    irpf_category_ids: list[str]
    net_paid_withholding_irpf_category_ids: list[str]
    income_requires_category: bool


class PortalEntryPayload(OutputSchema):
    """One local portal-registry catalogue entry.

    Projects :class:`PortalMetadata` from :data:`PORTAL_REGISTRY`, resolving
    translatable labels before the value leaves the application. Category,
    auth-method, and URL stability fields carry the domain enum values from
    :class:`PortalCategory`, :class:`AuthMethod`, and :class:`UrlStability`.
    """

    portal: str
    category: str
    subdomain: str
    url: str
    auth_methods: str
    url_stability: str
    label: str
    purpose: str
    active: bool


class PortalsListResult(OutputSchema):
    """Typed local-catalogue result for the portal listing.

    Rows are selected from :data:`PORTAL_REGISTRY` directly or through
    :func:`portals_by_category` / :func:`portals_for_modelo`, then projected as
    :class:`PortalEntryPayload`; reading the catalogue never opens a browser or
    contacts AEAT.
    """

    count: int
    rows: list[PortalEntryPayload]


class PortalsViewResult(PortalEntryPayload):
    """Typed local-catalogue result for one portal.

    The requested portal id resolves through :func:`get_portal` and yields the
    same :class:`PortalEntryPayload` projection as the listing.
    """


class ApoderadoScopesListResult(OutputSchema):
    """The apoderado scope catalogue.

    Projects the apoderado scope catalogue payload from its authoritative
    domain :class:`ApoderamientosCatalogue` records without restating their
    validation rules in the transport layer.
    """

    catalogue_version: NonEmptyStr
    scopes: list[ApoderadoScope]

"""Typed report contracts for registry query surfaces.

These frozen pydantic DTOs are emitted by
:class:`~domain.calculations.registry.RegistryQueryService` for read-only
registry introspection: modelo listings, revision descriptions, casilla
details, binding selector projections, formula dependency rows, support-matrix
summaries, and the registry-wide binding-source inventory.

The contracts stay in the domain layer and are deliberately not CLI payload
schemas. Application facades return these reports unchanged; CLI modules then
project them into strict ``--json`` envelopes. The source-inventory report is
also intentionally disposition-free: it records the committed
:class:`~core.BindingSourceKind` declarations and leaves enrolled/deferred/
reserved mesh classification to application-layer gates.

See Also:
    :class:`~domain.calculations.registry.RegistryQueryService`
        Builder of every report class defined here.
    :mod:`~application.modelo.registry_discovery`
        Application facade used by CLI discovery commands.
    :mod:`~entrypoints.cli._modelo_discovery_cli`
        Typer command group that renders these reports to text and JSON.
    :mod:`~entrypoints.cli._modelo_payloads`
        CLI-side ``OutputSchema`` projections for discovery command envelopes.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision record from which casilla, binding, and formula rows are
        projected.
    :class:`~domain.calculations.registry._support_matrix.ModeloEntry`
        Support-matrix row carried by :class:`ModeloSupportMatrixReport`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.identity import AeatBoxNumber
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period, RegistrySelectorPeriodCode
from ....core.text_bounds import PositiveCount
from .binding_selector_utils import BooleanBindingEncodedValue
from .ids import BindingId, FormulaId, LegalRefId, ParameterId, RelationId, RevisionId, SourceRefId
from .schema_input_kind import InputKind
from .support_matrix import ModeloEntry


class ModeloListRow(BaseModel):
    """One entry in a modelo catalogue listing."""

    model_config = STRICT_FROZEN_CONFIG

    code: str
    title: str
    cadence: str
    tax_domain: str
    revision_count: int


class ModeloListReport(BaseModel):
    """Complete result set for a modelo catalogue query."""

    model_config = STRICT_FROZEN_CONFIG

    modelos: tuple[ModeloListRow, ...]


class ModeloDescribeReport(BaseModel):
    """Full describe view for one resolved modelo revision.

    Every field here is regulatory grounding an operator may need to justify a
    revision selection, so the counts are bounded and ``filing_year`` shares the
    :class:`~core.Period` year range: a describe view is projected verbatim into
    the CLI ``--json`` envelope, and a negative count or an out-of-range year
    reaching that surface is a defect in the projection, not a legitimate value.
    """

    model_config = STRICT_FROZEN_CONFIG

    code: str
    title: str
    official_name: str
    tax_domain: str
    cadence: str
    jurisdiction: str
    revision: str
    revision_ids: tuple[str, ...]
    filing_year: FilingYear | None
    filing_period: Period | None = None
    period: RegistrySelectorPeriodCode | None
    valid_from: date
    valid_to: date | None
    periods: tuple[str, ...]
    casilla_count: NonNegativeInt
    manual_casilla_count: NonNegativeInt
    bound_casilla_count: NonNegativeInt
    computed_casilla_count: NonNegativeInt
    binding_count: NonNegativeInt
    formula_count: NonNegativeInt
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class CasillaGroundingReport(BaseModel):
    """Semantic identity and regulatory grounding of one casilla.

    The casilla *list* row and the casilla *detail* report describe the same
    casilla. Everything a reader needs to identify it and to justify its value
    -- its id, number, label, section path, value shape, input kind,
    requiredness, its bound binding, its localized label/help, and its
    ``legal_refs`` / ``source_refs`` grounding -- is declared once here, so the
    two projections cannot disagree about the same casilla.

    Before this base existed the list row typed its references as unconstrained
    ``tuple[str, ...]`` while the detail report used the canonical
    :data:`~domain.calculations.registry.LegalRefId` /
    :data:`~domain.calculations.registry.SourceRefId`, so a reference shape the
    detail projection refused passed silently through operator list JSON.

    Subclasses add only what genuinely differs: the resolved formula reference
    and form number for a listing row, the query context and full formula
    expression for a detail view.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    number: str
    label: str
    help_text: str | None = None
    section: tuple[str, ...]
    data_type: str
    input_kind: InputKind
    required: bool
    binding: BindingId | None
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class ModeloCasillaRow(CasillaGroundingReport):
    """One row in a casilla listing for a resolved modelo revision.

    Adds the listing-shaped formula reference and the official form number to
    the shared :class:`CasillaGroundingReport` identity and grounding.
    """

    formula: str | None
    form_number: AeatBoxNumber | None


class ModeloCasillasReport(BaseModel):
    """Full casilla listing for a resolved modelo revision."""

    model_config = STRICT_FROZEN_CONFIG

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: RegistrySelectorPeriodCode | None
    rows: tuple[ModeloCasillaRow, ...]


class ModeloCasillaDetailReport(CasillaGroundingReport):
    """Full semantic detail for one casilla on a resolved modelo revision.

    Adds the resolving query context and the full formula reference plus its
    expression to the shared :class:`CasillaGroundingReport` identity and
    grounding.
    """

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: RegistrySelectorPeriodCode | None
    formula_id: FormulaId | None
    formula_expression: Mapping[str, object] | None


BindingSelectorQueryValue = str | int | bool | tuple[str, ...]


class BindingSelectorQueryEntry(BaseModel):
    """One normalized binding-selector entry on the public query surface."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1)
    value: BindingSelectorQueryValue


class BindingSelectorQueryProjection(BaseModel):
    """Typed public projection of a binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    source: str
    keys: tuple[str, ...]
    entries: tuple[BindingSelectorQueryEntry, ...]


class ModeloBindingQueryRow(BaseModel):
    """One row in a binding listing for a resolved modelo revision."""

    model_config = STRICT_FROZEN_CONFIG

    binding_id: BindingId
    source: str
    typed_enum: str | None
    input_channel: Literal["decimal", "enum"]
    selector: BindingSelectorQueryProjection
    aggregation: Mapping[str, object] | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    borrador_capable: bool = False
    relation_inputs: tuple[RelationId, ...] = ()
    encoded_options: tuple[BooleanBindingEncodedValue, ...] = ()
    operator_input_required: bool = True


class ModeloBindingsReport(BaseModel):
    """Full binding listing for a single resolved modelo revision."""

    model_config = STRICT_FROZEN_CONFIG

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: RegistrySelectorPeriodCode | None
    rows: tuple[ModeloBindingQueryRow, ...]


class ModeloFormulaRow(BaseModel):
    """One row in a formula listing for a resolved modelo revision."""

    model_config = STRICT_FROZEN_CONFIG

    formula_id: FormulaId
    target_casilla_id: CasillaId
    input_casilla_ids: tuple[CasillaId, ...]
    input_bindings: tuple[BindingId, ...]
    input_parameters: tuple[ParameterId, ...]
    input_relations: tuple[RelationId, ...]
    expression: Mapping[str, object]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class ModeloFormulasReport(BaseModel):
    """Full formula listing for a single resolved modelo revision."""

    model_config = STRICT_FROZEN_CONFIG

    code: str
    revision: str
    filing_year: int | None
    filing_period: Period | None = None
    period: RegistrySelectorPeriodCode | None
    rows: tuple[ModeloFormulaRow, ...]


class RegistrySourceSite(BaseModel):
    """One committed modelo revision that declares a binding source kind."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    revision_id: RevisionId
    binding_count: PositiveCount


class RegistrySourceInventoryRow(BaseModel):
    """Every committed revision that declares one binding source kind."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    sites: tuple[RegistrySourceSite, ...]
    total_binding_count: PositiveCount


class RegistrySourceInventoryReport(BaseModel):
    """Registry-wide inventory of every declared binding source kind."""

    model_config = STRICT_FROZEN_CONFIG

    rows: tuple[RegistrySourceInventoryRow, ...]

    @property
    def declared_source_kinds(self) -> frozenset[BindingSourceKind]:
        """The set of binding source kinds the registry declares."""
        return frozenset(row.source_kind for row in self.rows)


class ModeloSupportMatrixReport(BaseModel):
    """Registry-wide support/capability matrix."""

    model_config = STRICT_FROZEN_CONFIG

    entries: tuple[ModeloEntry, ...]


__all__ = [
    "BindingSelectorQueryEntry",
    "BindingSelectorQueryProjection",
    "BindingSelectorQueryValue",
    "ModeloBindingQueryRow",
    "ModeloBindingsReport",
    "ModeloCasillaDetailReport",
    "ModeloCasillaRow",
    "ModeloCasillasReport",
    "ModeloDescribeReport",
    "ModeloFormulaRow",
    "ModeloFormulasReport",
    "ModeloListReport",
    "ModeloListRow",
    "ModeloSupportMatrixReport",
    "RegistrySourceInventoryReport",
    "RegistrySourceInventoryRow",
    "RegistrySourceSite",
]

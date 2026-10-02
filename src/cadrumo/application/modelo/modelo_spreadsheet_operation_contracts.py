"""Exact-profile spreadsheet operation wire contracts and canonical service ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self, override
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.country_code import CountryCodeAlpha2
from ...core.errors.hierarchy import CoreValidationError
from ...core.hex import HEX_PATTERN_64
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    RelatedPartyOperationObservation,
)
from ...domain.calculations.registry.donativo_bindings import DonativoDonorObservation
from ...domain.calculations.registry.gasto193_bindings import Gasto193Observation
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    ModeloId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.withholding296_bindings import Withholding296Observation
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..operations.public_period import PublicPeriod
from ..storage.calc_sheets.parity_harness import OperatorInputScenario
from ..storage.calc_sheets.records import SheetRelationProvenanceValue
from ..storage.calc_sheets.workbook_export import SheetWorkbookMaterializer, WorkbookPlanBuilder

MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID = "modelo.spreadsheet.export"
MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID = "modelo.spreadsheet.pull"
MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID = "modelo.spreadsheet.calculate"
MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID = "modelo.spreadsheet.verify"
MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE = "REFUSED_MODELO_SPREADSHEET_ROW_INGRESS"


class ModeloSpreadsheetRowIngressRefusedError(CoreValidationError):
    """Declared spreadsheet ingress refusal, separate from registry corruption."""


_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
_Hex64 = Annotated[str, Field(min_length=64, max_length=64, pattern=HEX_PATTERN_64)]
_Text = Annotated[str, Field(max_length=4096)]
_Handle = Annotated[str, Field(min_length=1, max_length=4096)]
_Count = Annotated[int, Field(ge=0)]
MAX_MODELO_SPREADSHEET_ROWS = 65_536


class SpreadsheetWithholdingObservation(BaseModel):
    """Closed wire fields of the canonical WithholdingObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    source_allocation_id: _Text
    perceptor_tax_id: _Text
    perceptor_legal_name: _Text
    country_code: CountryCodeAlpha2 | None
    transaction_date: _Text
    clave: _Text
    subclave: _Text
    percibido_dinerario: _Text
    percibido_especie: _Text
    retencion_practicada: _Text
    ingreso_a_cuenta: _Text
    province_code: _Text | None
    territorial_deduction_clave: int | None
    perceptor_birth_year: int | None
    perceptor_situacion_familiar: int | None
    representative_tax_id: _Text | None
    spouse_or_unit_titular_tax_id: _Text | None
    disability_clave: int | None
    contract_relation_clave: int | None
    unit_convivencia_titular_clave: int | None
    geographic_mobility_clave: int | None
    ingreso_a_cuenta_repercutido: _Text
    accrual_year: int | None
    reducciones_aplicables: _Text
    gastos_deducibles: _Text
    pension_compensatoria: _Text
    anualidades_alimentos: _Text
    descendants_under_3_total: int | None
    descendants_under_3_whole: int | None
    descendants_rest_total: int | None
    descendants_rest_whole: int | None
    descendants_disabled_33_65_total: int | None
    descendants_disabled_33_65_whole: int | None
    descendants_disabled_mobility_total: int | None
    descendants_disabled_mobility_whole: int | None
    descendants_disabled_65_plus_total: int | None
    descendants_disabled_65_plus_whole: int | None
    ascendants_under_75_total: int | None
    ascendants_under_75_whole: int | None
    ascendants_75_plus_total: int | None
    ascendants_75_plus_whole: int | None
    ascendants_disabled_33_65_total: int | None
    ascendants_disabled_33_65_whole: int | None
    ascendants_disabled_mobility_total: int | None
    ascendants_disabled_mobility_whole: int | None
    ascendants_disabled_65_plus_total: int | None
    ascendants_disabled_65_plus_whole: int | None
    first_child_compute: int | None
    second_child_compute: int | None
    third_child_compute: int | None
    housing_loan_communication_clave: int | None
    incapacity_cash_perception: _Text
    incapacity_cash_withholding: _Text
    incapacity_kind_value: _Text
    incapacity_kind_ingreso_a_cuenta: _Text
    incapacity_kind_repercutido: _Text
    complemento_infancia_clave: int | None
    foral_retention_estatal: _Text
    foral_retention_navarra: _Text
    foral_retention_araba: _Text
    foral_retention_gipuzkoa: _Text
    foral_retention_bizkaia: _Text
    emerging_stock_excess_clave: int | None
    startup_fund_rendimientos_clave: int | None
    pension_prestacion_jubilacion: int | None
    pension_prestacion_viudedad: int | None
    pension_prestacion_incapacidad: int | None
    pension_prestacion_no_contributiva: int | None
    pension_prestacion_resto: int | None
    perceptor_mediador_flag: _Text | None
    clave_codigo: int | None
    codigo_emisor: _Text | None
    naturaleza: _Text | None
    pago: int | None
    tipo_codigo: _Text | None
    codigo_cuenta: _Text | None
    pendiente_flag: _Text | None
    tipo_percepcion: int | None
    reducciones: _Text
    base_retenciones: _Text
    porcentaje_retencion: _Text
    penalizaciones: _Text
    isin_code: _Text | None
    naturaleza_declarante: _Text | None
    fecha_inicio_prestamo: _Text | None
    fecha_vencimiento_prestamo: _Text | None
    compensaciones: _Text
    garantias: _Text
    nif_pagador_anterior: _Text | None
    fecha_devengo: _Text | None
    clave_mercado: _Text | None
    numero_orden: int | None


class SpreadsheetRelatedPartyOperationObservation(BaseModel):
    """Closed wire fields of the canonical RelatedPartyOperationObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    counterparty_tax_id: _Text
    counterparty_legal_name: _Text
    country_code: CountryCodeAlpha2
    transaction_date: _Text
    operation_kind_code: _Text
    transfer_pricing_method_code: _Text
    amount: _Text


class SpreadsheetModelo720RowObservation(BaseModel):
    """Closed wire fields of the canonical Modelo720RowObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    asset_class_code: _Text
    country_code: CountryCodeAlpha2
    currency_code: _Text
    asset_identifier: _Text
    acquisition_date: _Text
    valuation_amount: _Text


class SpreadsheetAtributionMemberObservation(BaseModel):
    """Closed wire fields of the canonical AtributionMemberObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    member_tax_id: _Text
    member_legal_name: _Text
    country_code: CountryCodeAlpha2 | None
    transaction_date: _Text
    share_percentage: _Text
    base_imponible_assigned: _Text
    clave: _Text
    subclave: _Text | None
    codigo_provincia: _Text | None
    miembro_a_31_diciembre: _Text | None
    dias_miembro: int | None
    domicilio_fiscal: _Text | None
    naturaleza_inmueble: _Text | None
    situacion_inmueble: _Text | None
    referencia_catastral: _Text | None
    clave_declarado: _Text | None
    porcentaje_titularidad_inmueble: _Text | None
    dias_arrendamiento: int | None
    reduccion: _Text | None
    rendimiento_neto_previo_eo: _Text | None
    rendimiento_neto_minorado_agricola_eo: _Text | None


class SpreadsheetRefundOperationObservation(BaseModel):
    """Closed wire fields of the canonical RefundOperationObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    member_state_code: CountryCodeAlpha2
    operation_kind_code: _Text
    operation_date: _Text
    supplier_tax_id: _Text
    refund_amount: _Text


class SpreadsheetDonativoDonorObservation(BaseModel):
    """Closed wire fields of the canonical DonativoDonorObservation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    donor_tax_id: _Text
    donor_legal_name: _Text
    country_code: CountryCodeAlpha2
    transaction_date: _Text
    amount_donated: _Text
    deduction_percentage: _Text
    is_recurrent: bool


class SpreadsheetGasto193Observation(BaseModel):
    """Closed wire fields of the canonical Gasto193Observation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    contributor_tax_id: _Text
    contributor_legal_name: _Text
    representative_tax_id: _Text | None
    transaction_date: _Text
    importe_gastos: _Text


class SpreadsheetWithholding296Observation(BaseModel):
    """Closed wire fields of the canonical Withholding296Observation; no copied business policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_id: _Text
    perceptor_tax_id: _Text
    representative_tax_id: _Text | None
    persona_juridica_flag: _Text | None
    perceptor_legal_name: _Text
    codigo_bic: _Text | None
    fecha_devengo: _Text | None
    naturaleza: _Text
    clave: _Text
    subclave: _Text
    base_retenciones: _Text
    porcentaje_retencion: _Text
    retencion_practicada: _Text
    perceptor_mediador_flag: _Text | None
    codigo: _Text | None
    codigo_emisor: _Text | None
    pago: int | None
    tipo_codigo: _Text | None
    codigo_cuenta: _Text | None
    pendiente_flag: _Text | None
    accrual_year: int | None
    fecha_inicio_prestamo: _Text | None
    fecha_vencimiento_prestamo: _Text | None
    compensaciones: _Text
    garantias: _Text
    otros_importes: _Text
    direccion_perceptor: _Text | None
    ingreso_a_cuenta_repercutido: _Text
    nif_pagador_anterior: _Text | None
    procedimiento_especial_flag: _Text | None
    clave_mercado: _Text | None
    codigo_lei: _Text | None
    nif_pais_residencia: _Text | None
    fecha_nacimiento: _Text | None
    ciudad_nacimiento: _Text | None
    codigo_pais: CountryCodeAlpha2 | None
    pais_residencia_fiscal: CountryCodeAlpha2 | None
    transaction_date: _Text


type SpreadsheetAssembledObservation = (
    SpreadsheetWithholdingObservation
    | SpreadsheetRelatedPartyOperationObservation
    | SpreadsheetModelo720RowObservation
    | SpreadsheetAtributionMemberObservation
    | SpreadsheetRefundOperationObservation
    | SpreadsheetDonativoDonorObservation
    | SpreadsheetGasto193Observation
    | SpreadsheetWithholding296Observation
)

type CanonicalSpreadsheetAssembledObservation = (
    WithholdingObservation
    | RelatedPartyOperationObservation
    | Modelo720RowObservation
    | AtributionMemberObservation
    | RefundOperationObservation
    | DonativoDonorObservation
    | Gasto193Observation
    | Withholding296Observation
)


def project_modelo_spreadsheet_observation(
    observation: CanonicalSpreadsheetAssembledObservation,
) -> SpreadsheetAssembledObservation:
    """Losslessly project an already-validated canonical row into its closed wire type."""
    models = (
        (WithholdingObservation, SpreadsheetWithholdingObservation),
        (RelatedPartyOperationObservation, SpreadsheetRelatedPartyOperationObservation),
        (Modelo720RowObservation, SpreadsheetModelo720RowObservation),
        (AtributionMemberObservation, SpreadsheetAtributionMemberObservation),
        (RefundOperationObservation, SpreadsheetRefundOperationObservation),
        (DonativoDonorObservation, SpreadsheetDonativoDonorObservation),
        (Gasto193Observation, SpreadsheetGasto193Observation),
        (Withholding296Observation, SpreadsheetWithholding296Observation),
    )
    for canonical_type, wire_type in models:
        if type(observation) is canonical_type:
            return wire_type.model_validate(observation.model_dump(mode="json"), strict=True)
    raise TypeError("unsupported canonical spreadsheet observation")


class ModeloSpreadsheetRequest(BaseModel):
    """The admitted profile and canonical registry filing coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod


class ModeloSpreadsheetExportRequest(ModeloSpreadsheetRequest):
    """Explicit local export election; the supervisor stores its path securely."""

    output_path: _PathText
    replace_existing: bool = False
    prefill_relations: bool = False

    @model_validator(mode="after")
    def _absolute_output(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("spreadsheet output path must be absolute")
        return self


class ModeloSpreadsheetPullRequest(ModeloSpreadsheetRequest):
    """Read an existing remote workbook, optionally assembling its populated rows."""

    spreadsheet_id: _Handle
    assemble_observations: bool = False


class ModeloSpreadsheetCalculateRequest(ModeloSpreadsheetRequest):
    """Read a matching workbook and call its existing registry calculation service."""

    spreadsheet_id: _Handle


class ModeloSpreadsheetVerifyRequest(ModeloSpreadsheetRequest):
    """Optional immutable source reference for the existing parity scenario."""

    scenario_path: _PathText | None = None
    scenario_sha256: _Hex64 | None = None

    @model_validator(mode="after")
    def _scenario_reference(self) -> Self:
        if (self.scenario_path is None) != (self.scenario_sha256 is None):
            raise ValueError("scenario path and digest must be supplied together")
        if self.scenario_path is not None and not Path(self.scenario_path).is_absolute():
            raise ValueError("spreadsheet scenario path must be absolute")
        return self


class ModeloSpreadsheetProjection(BaseModel):
    """Encrypted renderer-neutral result with its owning profile coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: PublicPeriod


class ModeloSpreadsheetExportProjection(ModeloSpreadsheetProjection):
    """The same existing workbook publication receipt and coverage facts."""

    output_path: _PathText
    byte_size: _Count
    sha256: _Hex64
    tab_names: Annotated[tuple[_Text, ...], Field(min_length=1, max_length=128)]
    casilla_count: _Count
    prefill_relations: bool


class SpreadsheetPullMetadata(BaseModel):
    """Every identity stamp already exposed by the canonical pull surface."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo_id: _Text
    revision_id: RevisionId
    filing_year: int
    period: _Text
    engine_version: _Text
    registry_sha: _Text
    exported_at: _Text | None = None


class SpreadsheetOperatorEdit(BaseModel):
    """Populated casilla row, preserving the existing textual scalar projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    label: _Text
    value: _Text | None = None


class SpreadsheetBindingEdit(BaseModel):
    """One numeric or enum binding cell."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding: BindingId
    value: _Text | None = None


class SpreadsheetRelationEdit(BaseModel):
    """Preserve all existing relation provenance beside its textual value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    relation: RelationId
    value: _Text | None = None
    provenance: SheetRelationProvenanceValue | None = None
    source_modelo: ModeloId | None = None
    source_filing_year: int | None = None
    source_periods: tuple[str, ...] = ()
    source_casilla_ids: tuple[CasillaId, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    resolved_at: _Text | None = None


class SpreadsheetRowSetCell(SpreadsheetBindingEdit):
    """A populated row cell retaining its exact declared row coordinate."""

    row_index: Annotated[int, Field(ge=1)]


class SpreadsheetRowSet(BaseModel):
    """One populated canonical worksheet grouping."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grouping: _Handle
    cells: Annotated[tuple[SpreadsheetRowSetCell, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]


class SpreadsheetAssembledGrouping(BaseModel):
    """The canonical assembler's existing JSON observations, without persistence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grouping: _Handle
    source_kind: _Handle
    observation_count: _Count
    observations: Annotated[tuple[SpreadsheetAssembledObservation, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]

    @model_validator(mode="after")
    def _complete_observations(self) -> Self:
        if self.observation_count != len(self.observations):
            raise ValueError("assembled observation count disagrees with its rows")
        return self


class SpreadsheetReadFacts(BaseModel):
    """Read facts common to the existing pull and calculate projections."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    spreadsheet_id: _Handle
    cells_read: _Count
    operator_edits_populated: _Count
    binding_edits_populated: _Count
    relation_edits_populated: _Count


class SpreadsheetPullFacts(SpreadsheetReadFacts):
    """Normalized inbound facts, not an adapter object or a new ingress algorithm."""

    metadata_match: Literal["matches", "stale", "missing"]
    metadata: SpreadsheetPullMetadata
    operator_edits_total: _Count
    operator_edits: Annotated[tuple[SpreadsheetOperatorEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    binding_edits: Annotated[tuple[SpreadsheetBindingEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    relation_edits: Annotated[tuple[SpreadsheetRelationEdit, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    row_set_edits_populated: _Count
    row_set_cells_populated: _Count
    row_set_edits: Annotated[tuple[SpreadsheetRowSet, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]
    assembled_groupings: Annotated[
        tuple[SpreadsheetAssembledGrouping, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)
    ]
    assembled_observation_count: _Count

    @model_validator(mode="after")
    def _complete_counts(self) -> Self:
        if (
            self.operator_edits_populated != len(self.operator_edits)
            or self.operator_edits_total < self.operator_edits_populated
            or self.binding_edits_populated != len(self.binding_edits)
            or self.relation_edits_populated != len(self.relation_edits)
            or self.row_set_edits_populated != len(self.row_set_edits)
            or self.row_set_cells_populated != sum(len(row.cells) for row in self.row_set_edits)
            or self.assembled_observation_count != sum(row.observation_count for row in self.assembled_groupings)
        ):
            raise ValueError("spreadsheet pull counts disagree with their complete rows")
        return self


class SpreadsheetComputedCasilla(BaseModel):
    """Exactly the calculated value and grounding fields already disclosed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    value: _Text
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class SpreadsheetCalculateFacts(SpreadsheetReadFacts):
    """Canonical computation facts from a matching remote workbook."""

    metadata_match: Literal["matches"]
    computed: Annotated[tuple[SpreadsheetComputedCasilla, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]


class ModeloSpreadsheetPullProjection(ModeloSpreadsheetProjection, SpreadsheetPullFacts):
    """Complete current pull disclosure, bound to its registered profile."""


class ModeloSpreadsheetCalculateProjection(ModeloSpreadsheetProjection, SpreadsheetCalculateFacts):
    """Complete current calculation disclosure, with no local filing write."""


class SpreadsheetVerifyDivergence(BaseModel):
    """Existing three-way divergence row; absent oracle values stay absent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    label: _Text
    local: _Text | None = None
    sheets: _Text | None = None
    aeat: _Text | None = None


class SpreadsheetVerifyFacts(BaseModel):
    """Canonical report projection plus private transport write acknowledgement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    spreadsheet_id: _Handle
    spreadsheet_url: _Handle
    verdict: Literal["all_match", "divergence", "inconclusive"]
    aeat_oracle_present: bool
    computed_count: _Count
    divergence_count: _Count
    divergences: Annotated[tuple[SpreadsheetVerifyDivergence, ...], Field(max_length=MAX_MODELO_SPREADSHEET_ROWS)]

    @model_validator(mode="after")
    def _complete_divergences(self) -> Self:
        if self.divergence_count != len(self.divergences):
            raise ValueError("parity divergence count disagrees with its complete rows")
        return self


class ModeloSpreadsheetVerifyProjection(ModeloSpreadsheetProjection, SpreadsheetVerifyFacts):
    """Current parity result, without disclosing provider write counters."""


class SpreadsheetOutputPathRefusal(BaseModel):
    """Closed local publication facts; raw operating-system errors are excluded."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["output_path"] = "output_path"
    output_path: _PathText
    reason: Literal[
        "empty", "existing_directory", "existing_file", "missing_parent", "parent_not_directory", "publication_failed"
    ]


class SpreadsheetRowIngressRefusal(BaseModel):
    """Canonical row ownership coordinates without submitted cell values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["row_ingress"] = "row_ingress"
    reason: Literal[
        "undeclared_grouping",
        "caller_binding_substitution",
        "unknown_field",
        "duplicate_cell_coordinate",
        "row_ownership_collision",
    ]
    grouping: _Text
    row_index: Annotated[int, Field(ge=1)]
    binding_id: _Text | None = None
    declared_grouping: _Handle | None = None
    first_row_set_index: _Count | None = None
    second_row_set_index: _Count | None = None

    @model_validator(mode="after")
    def _complete_coordinates(self) -> Self:
        binding_required = self.reason in {"caller_binding_substitution", "unknown_field", "duplicate_cell_coordinate"}
        collision = self.reason == "row_ownership_collision"
        if (
            (self.binding_id is not None) != binding_required
            or (self.declared_grouping is not None) != (self.reason == "caller_binding_substitution")
            or (self.first_row_set_index is not None) != collision
            or (self.second_row_set_index is not None) != collision
            or (collision and self.first_row_set_index == self.second_row_set_index)
        ):
            raise ValueError("row ingress refusal coordinates are incomplete")
        return self


class SpreadsheetSnapshotMismatchRefusal(BaseModel):
    """Explicit workbook binding metadata; no worksheet values or authored error text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["snapshot_mismatch"] = "snapshot_mismatch"
    condition: Literal["google.calc_sheets.pull.snapshot_aligned"] = "google.calc_sheets.pull.snapshot_aligned"
    snapshot_aligned: Literal[False] = False
    spreadsheet_id: _Handle
    metadata_match: Literal["matches", "stale", "missing"]
    workbook_modelo: _Text
    snapshot_modelo: ModeloId
    workbook_revision: _Text
    snapshot_revision: RevisionId
    workbook_engine_version: _Text
    expected_engine_version: _Handle
    workbook_registry_sha: _Text
    snapshot_registry_sha: Annotated[str, Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")]


type SpreadsheetRefusal = (
    SpreadsheetOutputPathRefusal | SpreadsheetRowIngressRefusal | SpreadsheetSnapshotMismatchRefusal
)


class ModeloSpreadsheetOutcome(ModeloSpreadsheetProjection):
    """Receipt-correlated successful report or deliberately retained refusal facts."""

    outcome: Literal["succeeded", "refused"]
    refusal: SpreadsheetRefusal | None = None

    def report(self) -> ModeloSpreadsheetProjection | None:
        """Return the concrete family report for common coordinate validation."""
        raise NotImplementedError

    @model_validator(mode="after")
    def _complete_outcome(self) -> Self:
        result = self.report()
        if self.outcome == "succeeded":
            if (
                self.refusal is not None
                or result is None
                or (
                    result.profile_id != self.profile_id
                    or result.modelo != self.modelo
                    or result.revision != self.revision
                    or result.period != self.period
                )
            ):
                raise ValueError("spreadsheet success coordinates are inconsistent")
        elif self.refusal is None or result is not None:
            raise ValueError("spreadsheet refusal is incomplete")
        if isinstance(self.refusal, SpreadsheetSnapshotMismatchRefusal) and (
            self.refusal.snapshot_modelo != self.modelo or self.refusal.snapshot_revision != self.revision
        ):
            raise ValueError("spreadsheet refusal names another authority snapshot")
        return self


class ModeloSpreadsheetExportOutcome(ModeloSpreadsheetOutcome):
    """Local workbook publication outcome."""

    operation: Literal["export"] = "export"
    result: ModeloSpreadsheetExportProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetExportProjection | None:
        """Return the existing local workbook publication report."""
        return self.result


class ModeloSpreadsheetPullOutcome(ModeloSpreadsheetOutcome):
    """Remote workbook read and optional canonical ingress outcome."""

    operation: Literal["pull"] = "pull"
    result: ModeloSpreadsheetPullProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetPullProjection | None:
        """Return the complete normalized remote workbook read report."""
        return self.result


class ModeloSpreadsheetCalculateOutcome(ModeloSpreadsheetOutcome):
    """Remote matching-workbook calculation outcome."""

    operation: Literal["calculate"] = "calculate"
    result: ModeloSpreadsheetCalculateProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetCalculateProjection | None:
        """Return the matching-workbook canonical calculation report."""
        return self.result


class ModeloSpreadsheetVerifyOutcome(ModeloSpreadsheetOutcome):
    """Existing remote parity harness outcome."""

    operation: Literal["verify"] = "verify"
    result: ModeloSpreadsheetVerifyProjection | None = None

    @override
    def report(self) -> ModeloSpreadsheetVerifyProjection | None:
        """Return the existing canonical parity harness report."""
        return self.result


class ModeloSpreadsheetExecutionResult(BaseModel):
    """Private settled evidence, distinct from each registered public projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: (
        ModeloSpreadsheetExportOutcome
        | ModeloSpreadsheetPullOutcome
        | ModeloSpreadsheetCalculateOutcome
        | ModeloSpreadsheetVerifyOutcome
    )
    effect: Literal["none", "updated", "unknown"]


@dataclass(frozen=True, slots=True)
class SpreadsheetVerifyAcknowledgement:
    """Actual canonical adapter write confirmation; identity alone is insufficient."""

    facts: SpreadsheetVerifyFacts
    remote_write_confirmed: bool


type SpreadsheetProviderAdmission = Callable[[], None]
type SpreadsheetMutationHandoff = Callable[[], None]


class SpreadsheetPullPort(Protocol):
    """Lazy canonical remote pull and optional whole-pull assembly."""

    def __call__(
        self, request: ModeloSpreadsheetPullRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetPullFacts | SpreadsheetSnapshotMismatchRefusal:
        """Read the bound workbook after admission and retain its canonical facts."""
        ...


class SpreadsheetCalculatePort(Protocol):
    """Lazy canonical pull and existing guarded registry calculation."""

    def __call__(
        self, request: ModeloSpreadsheetCalculateRequest, *, admit_provider: SpreadsheetProviderAdmission
    ) -> SpreadsheetCalculateFacts | SpreadsheetSnapshotMismatchRefusal:
        """Calculate only through the canonical matching-workbook guard."""
        ...


class SpreadsheetVerifyPort(Protocol):
    """Lazy parity harness with separate provider admission and mutation handoff."""

    def __call__(
        self,
        request: ModeloSpreadsheetVerifyRequest,
        scenario: OperatorInputScenario,
        *,
        admit_provider: SpreadsheetProviderAdmission,
        before_mutation: SpreadsheetMutationHandoff,
    ) -> SpreadsheetVerifyAcknowledgement:
        """Run canonical parity after provider admission and explicit mutation handoff."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloSpreadsheetOperationPorts:
    """One worker's exact profile and retained authority, with lazy provider ports."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    materialize: SheetWorkbookMaterializer
    plan_builder: WorkbookPlanBuilder
    pull: SpreadsheetPullPort
    calculate: SpreadsheetCalculatePort
    verify: SpreadsheetVerifyPort


class ModeloSpreadsheetOperationPortsFactory(Protocol):
    """Compose ports without credential hydration, refresh or provider discovery."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloSpreadsheetOperationPorts:
        """Compose lazy ports retaining the owning profile and authority pin."""
        ...


__all__ = [
    "MAX_MODELO_SPREADSHEET_ROWS",
    "MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID",
    "MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE",
    "MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID",
    "CanonicalSpreadsheetAssembledObservation",
    "ModeloSpreadsheetCalculateOutcome",
    "ModeloSpreadsheetCalculateProjection",
    "ModeloSpreadsheetCalculateRequest",
    "ModeloSpreadsheetExecutionResult",
    "ModeloSpreadsheetExportOutcome",
    "ModeloSpreadsheetExportProjection",
    "ModeloSpreadsheetExportRequest",
    "ModeloSpreadsheetOperationPorts",
    "ModeloSpreadsheetOperationPortsFactory",
    "ModeloSpreadsheetOutcome",
    "ModeloSpreadsheetProjection",
    "ModeloSpreadsheetPullOutcome",
    "ModeloSpreadsheetPullProjection",
    "ModeloSpreadsheetPullRequest",
    "ModeloSpreadsheetRequest",
    "ModeloSpreadsheetRowIngressRefusedError",
    "ModeloSpreadsheetVerifyOutcome",
    "ModeloSpreadsheetVerifyProjection",
    "ModeloSpreadsheetVerifyRequest",
    "SpreadsheetAssembledGrouping",
    "SpreadsheetAssembledObservation",
    "SpreadsheetAtributionMemberObservation",
    "SpreadsheetBindingEdit",
    "SpreadsheetCalculateFacts",
    "SpreadsheetCalculatePort",
    "SpreadsheetComputedCasilla",
    "SpreadsheetDonativoDonorObservation",
    "SpreadsheetGasto193Observation",
    "SpreadsheetModelo720RowObservation",
    "SpreadsheetMutationHandoff",
    "SpreadsheetOperatorEdit",
    "SpreadsheetOutputPathRefusal",
    "SpreadsheetProviderAdmission",
    "SpreadsheetPullFacts",
    "SpreadsheetPullMetadata",
    "SpreadsheetPullPort",
    "SpreadsheetReadFacts",
    "SpreadsheetRefundOperationObservation",
    "SpreadsheetRefusal",
    "SpreadsheetRelatedPartyOperationObservation",
    "SpreadsheetRelationEdit",
    "SpreadsheetRowIngressRefusal",
    "SpreadsheetRowSet",
    "SpreadsheetRowSetCell",
    "SpreadsheetSnapshotMismatchRefusal",
    "SpreadsheetVerifyAcknowledgement",
    "SpreadsheetVerifyDivergence",
    "SpreadsheetVerifyFacts",
    "SpreadsheetVerifyPort",
    "SpreadsheetWithholding296Observation",
    "SpreadsheetWithholdingObservation",
    "project_modelo_spreadsheet_observation",
]

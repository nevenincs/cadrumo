"""Frozen revision evidence shared by review renderers and package assembly."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, TypeAdapter, model_serializer, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, SnapshotId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing.codes import IsoCurrencyCode
from ...core.period import Period
from ...domain.calculations.registry.ids import LegalRefId, ModeloId, SourceRefId
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.filing_record import AeatConfirmationState, ModeloRecordStatus
from ...domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow
from .review_form_data import ReviewSavedForm
from .review_snapshot_integrity import validate_review_snapshot_content


class CalculationReviewSelection(BaseModel):
    """Select a saved calculation explicitly; there is no implicit current revision."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["calculation"] = "calculation"
    profile_id: UUID
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: ModeloId
    filing_year: FilingYear
    period: str = Field(min_length=1)
    registry_snapshot_ref: RegistrySnapshotRef
    authority_generation: Hex64Str
    registry_digest: Hex64Str

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _matching_registry_coordinates(self) -> Self:
        Period.from_year_and_code(self.filing_year, self.period)
        reference = self.registry_snapshot_ref
        if (reference.modelo, reference.modelo_year, reference.period) != (self.modelo, self.filing_year, self.period):
            raise ValueError("selected calculation and registry coordinates must agree")
        return self


class LedgerReviewSelection(BaseModel):
    """An explicit ledger snapshot without an invented calculation identity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["ledger"] = "ledger"
    profile_id: UUID
    ledger_snapshot_id: SnapshotId


type ReviewSelection = Annotated[CalculationReviewSelection | LedgerReviewSelection, Field(discriminator="kind")]


class EvidenceDisposition(StrEnum):
    """Selection and availability are visible rather than silently omitted."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class EvidenceInventoryItem(BaseModel):
    """Immutable original-byte identity and explicit payload selection outcome."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    digest: Hex64Str | None = None
    media_type: str | None = Field(default=None, min_length=1)
    byte_length: int | None = Field(default=None, ge=0)
    disposition: EvidenceDisposition
    reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _complete_inventory(self) -> Self:
        if self.disposition is EvidenceDisposition.INCLUDED:
            if self.digest is None or self.media_type is None or self.byte_length is None:
                raise ValueError("included evidence requires its original byte identity")
        elif self.reason is None:
            raise ValueError("evidence omissions require an explicit reason")
        return self


class ReviewSourceKind(StrEnum):
    """The origin of an amount; a row's proximity never implies contribution."""

    LEDGER_ROW = "ledger_row"
    INVOICE = "invoice"
    MANUAL_INPUT = "manual_input"
    ADJUSTMENT = "adjustment"
    UNAVAILABLE = "unavailable"


class ReviewContribution(BaseModel):
    """Stable source attribution captured with the selected calculation."""

    model_config = STRICT_FROZEN_CONFIG

    contribution_id: str = Field(min_length=1)
    kind: ReviewSourceKind
    source_id: str = Field(min_length=1)
    source_revision: str | None = Field(default=None, min_length=1)
    source_digest: Hex64Str | None = None
    evidence_ids: tuple[str, ...] = ()
    detail: str = ""


class ReviewAmount(BaseModel):
    """A saved amount with display semantics and explicit contributing sources."""

    model_config = STRICT_FROZEN_CONFIG

    amount_id: str = Field(min_length=1)
    casilla_id: CasillaId
    row_id: str | None = Field(default=None, min_length=1)
    value: Decimal = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)
    currency: IsoCurrencyCode | None = None
    rounding: str = Field(min_length=1)
    contribution_ids: tuple[str, ...] = Field(min_length=1)
    formula_reference: str | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


class ReviewStatus(StrEnum):
    """Review quality does not confer filing or audit certification."""

    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"


class ReviewFinding(BaseModel):
    """A retained completeness or provenance limitation."""

    model_config = STRICT_FROZEN_CONFIG

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    related_ids: tuple[str, ...] = ()


class ReviewTextValue(BaseModel):
    """An exact retained text observation, with no numeric coercion."""

    model_config = STRICT_FROZEN_CONFIG
    value_id: str = Field(min_length=1)
    casilla_id: CasillaId
    value: str
    contribution_ids: tuple[str, ...] = Field(min_length=1)
    formula_reference: str | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


class ReviewCalculationLifecycle(BaseModel):
    """Saved local lifecycle and separately observed filing confirmation at export time."""

    model_config = STRICT_FROZEN_CONFIG

    state: CalculationRevisionState
    is_current_calculation: bool
    is_current_filing: bool
    filing_record_id: FilingRecordId | None = None
    filing_status: ModeloRecordStatus | None = None
    aeat_confirmation: AeatConfirmationState | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _filing_evidence_is_complete(self) -> Self:
        fields = (self.filing_record_id, self.filing_status, self.aeat_confirmation)
        if any(item is not None for item in fields) and any(item is None for item in fields):
            raise ValueError("review filing status requires the exact saved filing record")
        if self.is_current_filing and self.state is not CalculationRevisionState.PRESENTADO:
            raise ValueError("only a presented revision can be the current local filing")
        if self.filing_record_id is not None and self.state not in {
            CalculationRevisionState.PRESENTADO,
            CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
        }:
            raise ValueError("review filing evidence requires a filed calculation revision")
        return self


class ReviewSnapshotContent(BaseModel):
    """One immutable local baseline; construction and payload access have separate owners."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1, 2] = 1
    selection: ReviewSelection
    status: ReviewStatus
    calculation_lifecycle: ReviewCalculationLifecycle | None = None
    saved_form: ReviewSavedForm | None = None
    amounts: tuple[ReviewAmount, ...] = ()
    text_values: tuple[ReviewTextValue, ...] = ()
    ledger_rows: tuple[LedgerEvidenceRow, ...] = ()
    contributions: tuple[ReviewContribution, ...] = ()
    evidence: tuple[EvidenceInventoryItem, ...] = ()
    findings: tuple[ReviewFinding, ...] = ()

    @model_serializer(mode="wrap")
    def _preserve_v1_content(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        """Older retained snapshots keep their original canonical bytes and digest."""
        payload = TypeAdapter(dict[str, object]).validate_python(handler(self))
        if self.schema_version == 1:
            payload.pop("calculation_lifecycle", None)
            payload.pop("saved_form", None)
            payload.pop("text_values", None)
        return payload

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _reference_integrity(self) -> Self:
        validate_review_snapshot_content(self)
        return self


class ReviewSnapshot(ReviewSnapshotContent):
    """Digest-bound version of the exact snapshot content shared by all exporters."""

    snapshot_digest: Hex64Str

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _digest_matches(self) -> Self:
        payload = self.model_dump(mode="json", exclude={"snapshot_digest"})
        if sha256_hex(canonical_json_bytes(payload)) != self.snapshot_digest:
            raise ValueError("review snapshot digest does not match its content")
        return self


def seal_review_snapshot(content: ReviewSnapshotContent) -> ReviewSnapshot:
    """Bind canonical JSON bytes without reading or recalculating any source."""
    digest = sha256_hex(canonical_json_bytes(content.model_dump(mode="json")))
    return ReviewSnapshot(**content.model_dump(), snapshot_digest=digest)

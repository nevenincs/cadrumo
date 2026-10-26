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
        calculation = isinstance(self.selection, CalculationReviewSelection)
        if self.schema_version == 1 and (
            self.calculation_lifecycle is not None or self.saved_form is not None or self.text_values
        ):
            raise ValueError("v1 review snapshots cannot carry unbound lifecycle metadata")
        if self.schema_version == 2 and calculation and self.calculation_lifecycle is None:
            raise ValueError("v2 calculation review requires captured lifecycle metadata")
        if not calculation and self.calculation_lifecycle is not None:
            raise ValueError("ledger review cannot claim a calculation lifecycle")
        if self.saved_form is not None:
            if not isinstance(self.selection, CalculationReviewSelection):
                raise ValueError("saved form requires a calculation selection")
            rendering = self.saved_form.rendering
            if (
                rendering.registry_snapshot.snapshot_ref != self.selection.registry_snapshot_ref
                or rendering.registry_digest != self.selection.registry_digest
                or rendering.authority_generation != self.selection.authority_generation
            ):
                raise ValueError("saved form authority does not match the review selection")
            scalars = {value.id: value.value for value in self.saved_form.scalars}
            if any(amount.row_id is None and scalars.get(amount.casilla_id) != amount.value for amount in self.amounts):
                raise ValueError("saved form values do not match the baseline amounts")
            if any(scalars.get(item.casilla_id) != item.value for item in self.text_values):
                raise ValueError("saved form text values do not match the retained baseline")
        contribution_ids = {item.contribution_id for item in self.contributions}
        evidence_ids = {item.evidence_id for item in self.evidence}
        row_ids = {row.transaction_id for row in self.ledger_rows}
        if (
            len(contribution_ids) != len(self.contributions)
            or len(evidence_ids) != len(self.evidence)
            or len(row_ids) != len(self.ledger_rows)
            or len({amount.amount_id for amount in self.amounts}) != len(self.amounts)
            or len({item.value_id for item in self.text_values}) != len(self.text_values)
        ):
            raise ValueError("snapshot identities must be unique within each record family")
        if isinstance(self.selection, LedgerReviewSelection) and (self.amounts or self.text_values):
            raise ValueError("ledger-only review cannot invent calculated casilla values")
        for amount in self.amounts:
            if not set(amount.contribution_ids) <= contribution_ids:
                raise ValueError("amount attribution refers to a missing contribution")
        for item in self.text_values:
            if not set(item.contribution_ids) <= contribution_ids:
                raise ValueError("text attribution refers to a missing contribution")
        for source in self.contributions:
            if not set(source.evidence_ids) <= evidence_ids:
                raise ValueError("source attribution refers to missing inventory entries")
            if source.kind is ReviewSourceKind.LEDGER_ROW and source.source_id not in row_ids:
                raise ValueError("ledger contribution lacks its captured row")
        incomplete = any(
            item.disposition in {EvidenceDisposition.MISSING, EvidenceDisposition.UNAVAILABLE} for item in self.evidence
        ) or any(item.kind is ReviewSourceKind.UNAVAILABLE for item in self.contributions)
        if incomplete and self.status is ReviewStatus.VERIFIED:
            raise ValueError("unavailable evidence or provenance cannot be a verified complete review")
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

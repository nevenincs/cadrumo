"""Exact input evidence, caller intent and published result contracts for modelo calculation."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .calculation_advisory_projection import ModeloCalculationAdvisories
from .calculation_projection import ModeloCalculationSnapshot
from .calculation_request_fields import ModeloCalculationInputFieldsV1
from .edit_apply_row_contracts import ModeloDetailRowWireV1
from .metadata_projection import ModeloWorkMetadataSnapshot
from .work_change_contracts import ModeloWorkUnitSubjectId


class ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(BaseModel):
    """Operator-authored ordinary-M303 facts admitted only through secure request custody.

    The joint-return election is asked in every period. The Modelo 390
    attestation pair is supplied only for the last settlement period of the
    year and refused for any other; the executor applies that rule.
    """

    model_config = STRICT_FROZEN_CONFIG

    joint_return_elected: bool
    m303_exonerado_390_attachment_id: Hex64Str | None = None
    m303_exonerado_390_sha256: Hex64Str | None = None


class ModeloWorkCalculateCallerContext(StrEnum):
    """Where one calculation's caller-supplied inputs come from."""

    #: Replay the current head's caller context: the operator's own values,
    #: overrides and clears, detail rows, Modelo 303 filing evidence, Modelo 210
    #: selections and borrador snapshot. Recalculating keeps the operator's work.
    REPLAY_HEAD = "replay_head"
    #: Use exactly the inputs and detail rows this request carries, and nothing
    #: else: the full-specification semantics of ``modelo work calculate``.
    EXPLICIT = "explicit"


class ModeloWorkCalculateRequest(BaseModel):
    """Calculate the current ledger-backed revision for one work unit.

    The optional M303 branch remains absent for other modelos.  Its two filing
    facts are sensitive operator declarations, so the registered operation
    stores this complete request through the secure-reference boundary.

    ``caller_context`` defaults to replaying the head, so a recalculation that
    names no inputs never discards what the operator entered. A request that
    carries inputs or detail rows must say it is explicit; mixing the two is
    refused rather than silently resolved.

    ``actor`` is recorded as sent for a person's session. An agent's session is
    recorded under its own session label, whatever the request carries.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: ModeloWorkUnitSubjectId
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]
    ordinary_m303_filing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None = None
    caller_context: ModeloWorkCalculateCallerContext = ModeloWorkCalculateCallerContext.REPLAY_HEAD
    inputs: ModeloCalculationInputFieldsV1 = ModeloCalculationInputFieldsV1()
    detail_rows: tuple[ModeloDetailRowWireV1, ...] = Field(default=(), max_length=20_000)

    @model_validator(mode="after")
    def _replay_carries_no_inputs(self) -> Self:
        if self.caller_context is ModeloWorkCalculateCallerContext.REPLAY_HEAD and (
            self.inputs != ModeloCalculationInputFieldsV1() or self.detail_rows
        ):
            raise ValueError("a replaying calculation carries no explicit inputs; mark the request explicit")
        return self


class ModeloOperatorEntriesCarry(StrEnum):
    """What a calculation did with the entries the person made in the head it replaced."""

    #: The earlier head recorded the person's own entries and this calculation
    #: replayed them, so the new head holds them too.
    REPLAYED = "replayed"
    #: The earlier head did not record which of its values the person entered,
    #: so none was replayed: a value no source supplies is absent from the new
    #: head, and one a source supplies now reads as the source gives it.
    NOT_RECORDED = "not_recorded"
    #: The request carried its own inputs. They stand in the new head in place
    #: of whatever the person had entered in the earlier one.
    REPLACED_BY_REQUEST = "replaced_by_request"


class ModeloWorkCalculateReplacedHead(BaseModel):
    """The calculation head one calculation replaced as the declaration's current one.

    Calculating stores a new revision and removes none. The earlier revision,
    with every value it held, stays readable by its id; ``operator_entries``
    says whether the person's entries in it reached the new head.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    operator_entries: ModeloOperatorEntriesCarry


class ModeloWorkCalculatePublicResultV2(BaseModel):
    """Writer-returned calculation facts and advisories under the same authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[2] = 2
    work_unit_id: ModeloWorkUnitSubjectId
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    calculation: ModeloCalculationSnapshot
    advisories: ModeloCalculationAdvisories
    unit: ModeloWorkMetadataSnapshot
    revision_published: bool
    #: ``None`` when the work unit had no calculation before this one, or when
    #: this one left the same revision current.
    replaced_head: ModeloWorkCalculateReplacedHead | None = None

    @model_validator(mode="after")
    def _same_publication(self) -> Self:
        if (
            self.replaced_head is not None
            and self.replaced_head.calculation_revision_id == self.calculation_revision_id
        ):
            raise ValueError("a calculation does not replace the revision it returns")
        if (
            self.work_unit_id != self.calculation.work_unit_id
            or self.work_unit_id != self.unit.work_unit_id
            or self.calculation_revision_id != self.calculation.calculation_revision_id
            or self.calculation.bucket_id != self.unit.bucket_id
            or self.calculation.modelo != self.unit.modelo
            or self.calculation.filing_year != self.unit.filing_year
            or self.calculation.period != self.unit.period
            or self.calculation.registry_snapshot_ref.revision_id != self.unit.revision_id
        ):
            raise ValueError("calculation result does not match its writer-returned parent")
        return self

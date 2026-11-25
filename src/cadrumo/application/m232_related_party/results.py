"""Closed result schemas for the Modelo 232 related-party statements.

A projected operation names its counterparty by name and country only: the
counterparty's and the parent's identifiers stay in encrypted storage, as the
payer records' listing keeps a payer's.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.modelos.m232_obligation import (
    Modelo232Basis,
    Modelo232Ground,
    Modelo232GroundFinding,
    Modelo232GroundState,
    Modelo232Obligation,
    Modelo232ObligationFinding,
)
from ...domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232StatementState,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from ..aggregation.m232_related_party_obligation import M232_TURNOVER_SOURCE_LOCALE_KEYS, modelo_232_finding_note
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from ..operations.public_scalar import PublicDecimal
from .contracts import Modelo232RelatedPartyOperationId, Modelo232RelatedPartyOperationRefusalReason

__all__ = [
    "Modelo232GroundProjection",
    "Modelo232NoneStatementProjection",
    "Modelo232OperationProjection",
    "Modelo232RelatedPartyExecutionResult",
    "Modelo232RelatedPartyListProjection",
    "Modelo232RelatedPartyMutationProjection",
    "Modelo232RelatedPartyRefusalProjection",
    "Modelo232TurnoverStatementProjection",
    "Modelo232VerdictProjection",
    "Modelo232YearProjection",
]

_STATE_LOCALE_KEYS: Final[dict[Modelo232StatementState, str]] = {
    Modelo232StatementState.ACTIVE: "aggregation.modelo_232_related_party.state.active",
    Modelo232StatementState.WITHDRAWN: "aggregation.modelo_232_related_party.state.withdrawn",
}
_OPERATION_KIND_LOCALE_KEYS: Final[dict[Modelo232OperationKind, str]] = {
    Modelo232OperationKind.RELATED_PARTY: "aggregation.modelo_232_related_party.operation_kind.related_party",
    Modelo232OperationKind.INTANGIBLES_REDUCTION: (
        "aggregation.modelo_232_related_party.operation_kind.intangibles_reduction"
    ),
    Modelo232OperationKind.TAX_HAVEN_OPERATION: (
        "aggregation.modelo_232_related_party.operation_kind.tax_haven_operation"
    ),
    Modelo232OperationKind.TAX_HAVEN_HOLDING: "aggregation.modelo_232_related_party.operation_kind.tax_haven_holding",
}
_DIRECTION_LOCALE_KEYS: Final[dict[Modelo232Direction, str]] = {
    Modelo232Direction.INGRESO: "aggregation.modelo_232_related_party.direction.ingreso",
    Modelo232Direction.PAGO: "aggregation.modelo_232_related_party.direction.pago",
}
_EXCLUSION_LOCALE_KEYS: Final[dict[Modelo232Exclusion, str]] = {
    Modelo232Exclusion.CONSOLIDATION_GROUP: "aggregation.modelo_232_related_party.exclusion.consolidation_group",
    Modelo232Exclusion.AIE_OR_REGISTERED_UTE: "aggregation.modelo_232_related_party.exclusion.aie_or_registered_ute",
    Modelo232Exclusion.PUBLIC_OFFER: "aggregation.modelo_232_related_party.exclusion.public_offer",
}
_OBLIGATION_LOCALE_KEYS: Final[dict[Modelo232Obligation, str]] = {
    Modelo232Obligation.OWED: "aggregation.modelo_232_related_party.obligation.owed",
    Modelo232Obligation.NOT_OWED: "aggregation.modelo_232_related_party.obligation.not_owed",
    Modelo232Obligation.UNDECIDED: "aggregation.modelo_232_related_party.obligation.undecided",
}
_BASIS_LOCALE_KEYS: Final[dict[Modelo232Basis, str]] = {
    Modelo232Basis.NOTHING_STATED: "aggregation.modelo_232_related_party.basis.nothing_stated",
    Modelo232Basis.NONE_STATED: "aggregation.modelo_232_related_party.basis.none_stated",
    Modelo232Basis.OPERATIONS_STATED: "aggregation.modelo_232_related_party.basis.operations_stated",
    Modelo232Basis.CONTRADICTION: "aggregation.modelo_232_related_party.basis.contradiction",
}
_GROUND_LOCALE_KEYS: Final[dict[Modelo232Ground, str]] = {
    Modelo232Ground.SAME_RELATED_PARTY: "aggregation.modelo_232_related_party.ground.same_related_party",
    Modelo232Ground.SPECIFIC_OPERATION_TYPE: "aggregation.modelo_232_related_party.ground.specific_operation_type",
    Modelo232Ground.TURNOVER_SHARE: "aggregation.modelo_232_related_party.ground.turnover_share",
    Modelo232Ground.INTANGIBLES_REDUCTION: "aggregation.modelo_232_related_party.ground.intangibles_reduction",
    Modelo232Ground.TAX_HAVEN: "aggregation.modelo_232_related_party.ground.tax_haven",
}
_GROUND_STATE_LOCALE_KEYS: Final[dict[Modelo232GroundState, str]] = {
    Modelo232GroundState.MET: "aggregation.modelo_232_related_party.ground_state.met",
    Modelo232GroundState.NOT_MET: "aggregation.modelo_232_related_party.ground_state.not_met",
    Modelo232GroundState.UNDECIDED: "aggregation.modelo_232_related_party.ground_state.undecided",
}
"""Literal tables so the locale audit sees each served word reach the translator."""
for _table, _vocabulary in (
    (_STATE_LOCALE_KEYS, Modelo232StatementState),
    (_OPERATION_KIND_LOCALE_KEYS, Modelo232OperationKind),
    (_DIRECTION_LOCALE_KEYS, Modelo232Direction),
    (_EXCLUSION_LOCALE_KEYS, Modelo232Exclusion),
    (_OBLIGATION_LOCALE_KEYS, Modelo232Obligation),
    (_BASIS_LOCALE_KEYS, Modelo232Basis),
    (_GROUND_LOCALE_KEYS, Modelo232Ground),
    (_GROUND_STATE_LOCALE_KEYS, Modelo232GroundState),
    (M232_TURNOVER_SOURCE_LOCALE_KEYS, Modelo232TurnoverSource),
):
    if set(_table) != set(_vocabulary):
        raise InternalInvariantError("every Modelo 232 statement token needs its served word")


def _amount(value: object) -> PublicDecimal:
    return PublicDecimal(decimal=str(value))


class _StatedFields(BaseModel):
    """What every projected payload carries: its ejercicio, state and revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: FilingYear
    state: Modelo232StatementState
    state_label: str
    stated_at: datetime
    withdrawn_at: datetime | None
    revision_id: str

    @field_validator("stated_at", "withdrawn_at")
    @classmethod
    @pydantic_validation_boundary
    def _instants_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_utc_aware(value)


class Modelo232OperationProjection(_StatedFields):
    """One stated operation as the operator sees it, beside the revision it is stored at."""

    operation_id: str
    operation_kind: Modelo232OperationKind
    operation_kind_label: str
    counterparty_name: str
    counterparty_country: str
    tipo_vinculacion: str | None
    tipo_operacion: str | None
    valuation_method: str | None
    direction: Modelo232Direction | None
    direction_label: str | None
    specific_operation: bool
    amount_eur: PublicDecimal
    exclusion: Modelo232Exclusion | None
    exclusion_label: str | None
    description: str | None
    participation_percent: PublicDecimal | None
    parent_name: str | None

    @classmethod
    def from_operation(cls, operation: Modelo232Operation, *, revision_id: str) -> Modelo232OperationProjection:
        """Project every operator-visible field of ``operation`` and word its tokens."""
        return cls(
            ejercicio=operation.ejercicio,
            state=operation.state,
            state_label=tr(_STATE_LOCALE_KEYS[operation.state]),
            stated_at=operation.stated_at,
            withdrawn_at=operation.withdrawn_at,
            revision_id=revision_id,
            operation_id=operation.operation_id,
            operation_kind=operation.operation_kind,
            operation_kind_label=tr(_OPERATION_KIND_LOCALE_KEYS[operation.operation_kind]),
            counterparty_name=operation.counterparty_name,
            counterparty_country=operation.counterparty_country,
            tipo_vinculacion=operation.tipo_vinculacion,
            tipo_operacion=operation.tipo_operacion,
            valuation_method=operation.valuation_method,
            direction=operation.direction,
            direction_label=None if operation.direction is None else tr(_DIRECTION_LOCALE_KEYS[operation.direction]),
            specific_operation=operation.specific_operation,
            amount_eur=_amount(operation.amount_eur),
            exclusion=operation.exclusion,
            exclusion_label=None if operation.exclusion is None else tr(_EXCLUSION_LOCALE_KEYS[operation.exclusion]),
            description=operation.description,
            participation_percent=(
                None if operation.participation_percent is None else _amount(operation.participation_percent)
            ),
            parent_name=operation.parent_name,
        )


class Modelo232NoneStatementProjection(_StatedFields):
    """One "none" statement, active or withdrawn, beside the revision it is stored at."""

    statement_id: str
    note: str

    @classmethod
    def from_statement(cls, statement: Modelo232NoneStatement, *, revision_id: str) -> Modelo232NoneStatementProjection:
        """Project every operator-visible field of ``statement``."""
        return cls(
            ejercicio=statement.ejercicio,
            state=statement.state,
            state_label=tr(_STATE_LOCALE_KEYS[statement.state]),
            stated_at=statement.stated_at,
            withdrawn_at=statement.withdrawn_at,
            revision_id=revision_id,
            statement_id=statement.statement_id,
            note=statement.note,
        )


class Modelo232TurnoverStatementProjection(_StatedFields):
    """One turnover statement, active or withdrawn, beside the revision it is stored at."""

    statement_id: str
    turnover_eur: PublicDecimal
    source: Modelo232TurnoverSource
    source_label: str
    source_reference: str

    @classmethod
    def from_statement(
        cls, statement: Modelo232TurnoverStatement, *, revision_id: str
    ) -> Modelo232TurnoverStatementProjection:
        """Project every operator-visible field of ``statement`` and word its source."""
        return cls(
            ejercicio=statement.ejercicio,
            state=statement.state,
            state_label=tr(_STATE_LOCALE_KEYS[statement.state]),
            stated_at=statement.stated_at,
            withdrawn_at=statement.withdrawn_at,
            revision_id=revision_id,
            statement_id=statement.statement_id,
            turnover_eur=_amount(statement.turnover_eur),
            source=statement.source,
            source_label=tr(M232_TURNOVER_SOURCE_LOCALE_KEYS[statement.source]),
            source_reference=statement.source_reference,
        )


class Modelo232GroundProjection(BaseModel):
    """What one Orden HFP/816/2017 art. 2 ground shows, with the largest total tested and its limit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ground: Modelo232Ground
    ground_label: str
    state: Modelo232GroundState
    state_label: str
    largest_total_eur: PublicDecimal | None
    limit_eur: PublicDecimal | None

    @classmethod
    def from_finding(cls, finding: Modelo232GroundFinding) -> Modelo232GroundProjection:
        """Project one ground finding and word its ground and state."""
        return cls(
            ground=finding.ground,
            ground_label=tr(_GROUND_LOCALE_KEYS[finding.ground]),
            state=finding.state,
            state_label=tr(_GROUND_STATE_LOCALE_KEYS[finding.state]),
            largest_total_eur=None if finding.largest_total_eur is None else _amount(finding.largest_total_eur),
            limit_eur=None if finding.limit_eur is None else _amount(finding.limit_eur),
        )


class Modelo232VerdictProjection(BaseModel):
    """What the stated records decide about Modelo 232 for the ejercicio, and the counts behind it.

    It is the derivation of the stated records alone. ``note`` is the served
    detail behind a decided outcome: the turnover the art. 2.3 ground was tested
    against and its source, and the operations art. 2.2 left out.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    obligation: Modelo232Obligation
    obligation_label: str
    basis: Modelo232Basis
    basis_label: str
    grounds: tuple[Modelo232GroundProjection, ...]
    counted_operations: int
    excluded_operations: int
    excluded_total_eur: PublicDecimal
    turnover_eur: PublicDecimal | None
    turnover_source: Modelo232TurnoverSource | None
    note: str | None

    @classmethod
    def from_finding(cls, finding: Modelo232ObligationFinding) -> Modelo232VerdictProjection:
        """Project the obligation finding of one ejercicio and word its outcome."""
        obligation = finding.obligation
        return cls(
            obligation=obligation,
            obligation_label=tr(_OBLIGATION_LOCALE_KEYS[obligation]),
            basis=finding.basis,
            basis_label=tr(_BASIS_LOCALE_KEYS[finding.basis]),
            grounds=tuple(Modelo232GroundProjection.from_finding(ground) for ground in finding.grounds),
            counted_operations=finding.counted_operations,
            excluded_operations=finding.excluded_operations,
            excluded_total_eur=_amount(finding.excluded_total_eur),
            turnover_eur=None if finding.turnover_eur is None else _amount(finding.turnover_eur),
            turnover_source=finding.turnover_source,
            note=None if obligation is Modelo232Obligation.UNDECIDED else modelo_232_finding_note(finding),
        )


class Modelo232YearProjection(BaseModel):
    """Everything stated for one ejercicio, the guard revision a statement can assert, and its verdict.

    ``verdict`` is absent when the pinned authority supports no Modelo 232
    derivation for the ejercicio.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    guard_revision_id: str
    operations: tuple[Modelo232OperationProjection, ...]
    none_statements: tuple[Modelo232NoneStatementProjection, ...]
    turnover_statements: tuple[Modelo232TurnoverStatementProjection, ...]
    verdict: Modelo232VerdictProjection | None


class Modelo232RelatedPartyListProjection(BaseModel):
    """The public listing of one ejercicio."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear
    year: Modelo232YearProjection


class Modelo232RelatedPartyRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_MODELO_232_RELATED_PARTY", "REFUSED_MODELO_232_RELATED_PARTY_REVISION_CONFLICT"]
    reason: Modelo232RelatedPartyOperationRefusalReason
    ejercicio: FilingYear
    #: The finished sentence a frontend shows for the refusal and the language it is in, worded by the
    #: operation error detail's rules from a key written for frontends.
    refusal_words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> Modelo232RelatedPartyRefusalProjection:
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self


type _StatedPayload = (
    Modelo232OperationProjection | Modelo232NoneStatementProjection | Modelo232TurnoverStatementProjection
)


def _one_payload(
    operation: object | None, none_statement: object | None, turnover_statement: object | None
) -> object | None:
    stated = [item for item in (operation, none_statement, turnover_statement) if item is not None]
    if len(stated) > 1:
        raise ValueError("a Modelo 232 write carries at most one stated payload")
    return stated[0] if stated else None


class Modelo232RelatedPartyMutationProjection(BaseModel):
    """A stated or withdrawn payload, or the typed refusal that stored nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["stated", "withdrawn", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    operation: Modelo232OperationProjection | None = None
    none_statement: Modelo232NoneStatementProjection | None = None
    turnover_statement: Modelo232TurnoverStatementProjection | None = None
    refusal: Modelo232RelatedPartyRefusalProjection | None = None

    @property
    def payload(self) -> _StatedPayload | None:
        """Return the one stated or withdrawn payload, or ``None`` for a refusal."""
        return self.operation or self.none_statement or self.turnover_statement

    @model_validator(mode="after")
    def _arm_is_closed(self) -> Modelo232RelatedPartyMutationProjection:
        payload = _one_payload(self.operation, self.none_statement, self.turnover_statement)
        if (self.outcome == "refused") != (self.refusal is not None) or (self.refusal is None) == (payload is None):
            raise ValueError("Modelo 232 related-party projection has an incompatible payload")
        return self


class Modelo232RelatedPartyExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: Modelo232RelatedPartyOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    operation: Modelo232OperationProjection | None = None
    none_statement: Modelo232NoneStatementProjection | None = None
    turnover_statement: Modelo232TurnoverStatementProjection | None = None
    year: Modelo232YearProjection | None = None
    refusal: Modelo232RelatedPartyRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> Modelo232RelatedPartyExecutionResult:
        payload = _one_payload(self.operation, self.none_statement, self.turnover_statement)
        if self.operation_id == "list":
            closed = self.outcome == "success" and self.year is not None and payload is None and self.refusal is None
        else:
            closed = (
                self.year is None
                and (self.outcome == "refused") == (self.refusal is not None)
                and (self.refusal is None) != (payload is None)
                and _payload_matches(self.operation_id, payload)
            )
        if not closed:
            raise ValueError("Modelo 232 related-party execution result has an incompatible payload")
        return self


def _payload_matches(operation_id: Modelo232RelatedPartyOperationId, payload: object | None) -> bool:
    if payload is None:
        return True
    expected = {
        "state_operation": Modelo232OperationProjection,
        "withdraw_operation": Modelo232OperationProjection,
        "state_none": Modelo232NoneStatementProjection,
        "withdraw_none": Modelo232NoneStatementProjection,
        "state_turnover": Modelo232TurnoverStatementProjection,
        "withdraw_turnover": Modelo232TurnoverStatementProjection,
    }.get(operation_id)
    return expected is not None and type(payload) is expected

"""Closed result schemas for the suffered-withholding certificate operations.

No schema here carries a payer tax identifier: a record is named by its keyed
``payer_ref`` and the payer's legal name.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.retencion_soportada_label import retencion_soportada_clase_label
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from ..operations.public_scalar import PublicDecimal
from .contracts import (
    RetencionSoportadaCertificadoRefusalReason,
    RetencionSoportadaOperationId,
)


def _optional_amount(amount: Decimal | None) -> PublicDecimal | None:
    return None if amount is None else PublicDecimal(decimal=str(amount))


class RetencionSoportadaRowProjection(BaseModel):
    """One stored payer record as the operator sees it, without the payer's tax identifier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: FilingYear
    income_class: RetencionSoportadaClase
    income_class_label: str
    payer_ref: Hex64Str
    payer_legal_name: str | None
    importe_integro_dinerario: PublicDecimal
    valoracion_especie: PublicDecimal
    retencion: PublicDecimal
    ingreso_a_cuenta: PublicDecimal
    ingreso_a_cuenta_repercutido: PublicDecimal
    reducciones_aplicables: PublicDecimal | None
    gastos_deducibles: PublicDecimal | None
    pago_a_cuenta: PublicDecimal
    origin: RetencionSoportadaOrigen
    evidence_fingerprint: Hex64Str | None
    revision_id: str

    @classmethod
    def from_record(cls, record: RetencionSoportadaRecord, *, revision_id: str) -> RetencionSoportadaRowProjection:
        """Project every operator-visible field of ``record``."""
        return cls(
            ejercicio=record.ejercicio,
            income_class=record.income_class,
            income_class_label=retencion_soportada_clase_label(record.income_class),
            payer_ref=record.payer_ref,
            payer_legal_name=record.payer_legal_name,
            importe_integro_dinerario=PublicDecimal(decimal=str(record.importe_integro_dinerario)),
            valoracion_especie=PublicDecimal(decimal=str(record.valoracion_especie)),
            retencion=PublicDecimal(decimal=str(record.retencion)),
            ingreso_a_cuenta=PublicDecimal(decimal=str(record.ingreso_a_cuenta)),
            ingreso_a_cuenta_repercutido=PublicDecimal(decimal=str(record.ingreso_a_cuenta_repercutido)),
            reducciones_aplicables=_optional_amount(record.reducciones_aplicables),
            gastos_deducibles=_optional_amount(record.gastos_deducibles),
            pago_a_cuenta=PublicDecimal(decimal=str(record.pago_a_cuenta)),
            origin=record.origin,
            evidence_fingerprint=record.evidence_fingerprint,
            revision_id=revision_id,
        )


class RetencionSoportadaRefusalProjection(BaseModel):
    """Safe, closed context of a refusal made before anything was stored."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_RETENCION_SOPORTADA_WRITE", "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"]
    reason: RetencionSoportadaCertificadoRefusalReason
    ejercicio: FilingYear
    #: The finished sentence a frontend shows for the refusal and the language it is in, served for the
    #: certificate custody and file refusals, worded by the operation error detail's rules.
    refusal_words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> RetencionSoportadaRefusalProjection:
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self


class RetencionSoportadaListProjection(BaseModel):
    """Every stored payer record of one ejercicio."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear
    rows: tuple[RetencionSoportadaRowProjection, ...]


class RetencionSoportadaMutationProjection(BaseModel):
    """A recorded or removed payer record, or the typed refusal that stored nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["recorded", "removed", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    row: RetencionSoportadaRowProjection | None = None
    count: int | None = None
    refusal: RetencionSoportadaRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> RetencionSoportadaMutationProjection:
        if self.outcome == "refused":
            closed = self.row is None and self.count is None and self.refusal is not None
        else:
            closed = (
                self.refusal is None
                and self.count is not None
                and (self.outcome == "recorded") == (self.row is not None)
            )
        if not closed:
            raise ValueError("suffered-withholding mutation projection has an incompatible payload")
        return self


class RetencionSoportadaOperationExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: RetencionSoportadaOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    ejercicio: FilingYear
    rows: tuple[RetencionSoportadaRowProjection, ...] | None = None
    row: RetencionSoportadaRowProjection | None = None
    count: int | None = None
    refusal: RetencionSoportadaRefusalProjection | None = None

    @model_validator(mode="after")
    def _arm_is_closed(self) -> RetencionSoportadaOperationExecutionResult:
        if self.outcome == "refused":
            closed = self._refusal_arm_is_closed()
        elif self.refusal is not None:
            closed = False
        else:
            closed = self._success_arm_is_closed()
        if not closed:
            raise ValueError("suffered-withholding execution result has an incompatible payload")
        return self

    def _refusal_arm_is_closed(self) -> bool:
        return (
            self.operation_id != "list"
            and self.rows is None
            and self.row is None
            and self.count is None
            and self.refusal is not None
        )

    def _success_arm_is_closed(self) -> bool:
        if self.operation_id == "list":
            return self.rows is not None and self.row is None and self.count is None
        if self.operation_id == "record":
            return self.rows is None and self.row is not None and self.count is not None
        return self.rows is None and self.row is None and self.count is not None


__all__ = [
    "RetencionSoportadaListProjection",
    "RetencionSoportadaMutationProjection",
    "RetencionSoportadaOperationExecutionResult",
    "RetencionSoportadaRefusalProjection",
    "RetencionSoportadaRowProjection",
]

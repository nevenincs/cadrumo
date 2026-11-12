"""One payer's withholding suffered by the taxpayer, for one income class and ejercicio.

A record restates what a payer certificate (RIRPF art. 108.3) or the operator
declares about one payer: the income paid, the retención practised and the
ingreso a cuenta made on income in kind. It is the per-payer evidence behind the
credit casillas of the annual Renta.

The payer's identifier lives only inside the encrypted payload. Wherever the
record must be named outside it -- an object key, a provenance reference -- it is
named by :attr:`RetencionSoportadaRecord.payer_ref`, a keyed digest the storage
adapter computes under a profile-held key, because the space of Spanish tax
identifiers is small enough to recover from an unkeyed hash.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ...core.time.utc import UtcInstant
from .errors import RentaValidationError

__all__ = [
    "RetencionSoportadaIdentity",
    "RetencionSoportadaOrigen",
    "RetencionSoportadaRecord",
]

type _Importe = Annotated[Decimal, Field(ge=Decimal("0"), decimal_places=2)]
"""A non-negative euro amount with at most two decimals; a third decimal is refused, never rounded."""


class RetencionSoportadaOrigen(StrEnum):
    """Who states the figures on a record."""

    PAYER_CERTIFICATE = "payer_certificate"
    """The payer's certificate, held in attachment custody and fingerprinted."""
    OPERATOR_DECLARATION = "operator_declaration"
    """The operator's own declaration, with or without a supporting document."""


type RetencionSoportadaIdentity = tuple[int, RetencionSoportadaClase, str]
"""The ``(ejercicio, income class, payer_ref)`` a record is stored under, one row each."""


class RetencionSoportadaRecord(BaseModel):
    """One payer's figures for one income class and ejercicio (payload schema v2)."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    """The year the income is imputed to."""
    payer_tax_id: Annotated[TaxIdIdentityToken, Field(min_length=1, max_length=32)]
    payer_legal_name: str | None = Field(default=None, min_length=1, max_length=256)
    payer_ref: Hex64Str
    """The keyed digest of :attr:`payer_tax_id`, computed by the storage adapter."""
    income_class: RetencionSoportadaClase
    importe_integro_dinerario: _Importe
    valoracion_especie: _Importe
    retencion: _Importe
    ingreso_a_cuenta: _Importe
    ingreso_a_cuenta_repercutido: _Importe
    reducciones_aplicables: _Importe | None = None
    """The art. 18.2 and 18.3 reductions the payer applied; stated for class ``trabajo``, absent otherwise."""
    gastos_deducibles: _Importe | None = None
    """The art. 19.2 a), b) and c) deductible expenses the payer states; stated for ``trabajo``, absent otherwise."""
    origin: RetencionSoportadaOrigen
    evidence_fingerprint: ContentDigest | None = None
    """The sha256 of the certificate bytes; required for a payer certificate."""
    replaces_evidence_fingerprint: ContentDigest | None = None
    """The certificate this record's figures correct or replace, when they do.

    Equal to :attr:`evidence_fingerprint` when the figures correct a mistake made
    in reading the same certificate: the evidence is unchanged and the row is
    overwritten, so the record shows a correction against the same evidence.
    """
    captured_at: UtcInstant

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _repercutido_within_ingreso_a_cuenta(self) -> Self:
        if self.ingreso_a_cuenta_repercutido > self.ingreso_a_cuenta:
            raise RentaValidationError("the repercutido ingreso a cuenta exceeds the ingreso a cuenta it is part of")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _work_figures_belong_to_work_income(self) -> Self:
        """Refuse the two work-income figures on any other class, or one of them alone.

        A payload written before they existed states neither, and reads back as
        a ``trabajo`` record with both absent; :attr:`lacks_work_certificate_figures`
        names that state so a writer can refuse to create it afresh.
        """
        stated = (self.reducciones_aplicables is not None, self.gastos_deducibles is not None)
        if self.income_class is not RetencionSoportadaClase.TRABAJO:
            if any(stated):
                raise RentaValidationError("only a work-income record states reductions and deductible expenses")
        elif stated[0] != stated[1]:
            raise RentaValidationError(
                "a work-income record states both reductions and deductible expenses, or neither"
            )
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _certificate_is_fingerprinted(self) -> Self:
        if self.origin is RetencionSoportadaOrigen.PAYER_CERTIFICATE and self.evidence_fingerprint is None:
            raise RentaValidationError("a payer-certificate record names no certificate fingerprint")
        return self

    @property
    def identity(self) -> RetencionSoportadaIdentity:
        """Return the identity this record is stored under."""
        return (self.ejercicio, self.income_class, self.payer_ref)

    @property
    def lacks_work_certificate_figures(self) -> bool:
        """Return whether this is a work-income record that states neither figure a v2 payload requires."""
        return self.income_class is RetencionSoportadaClase.TRABAJO and self.reducciones_aplicables is None

    def states(self, cantidad: RetencionSoportadaCantidad) -> bool:
        """Return whether this record states the figure ``cantidad`` draws."""
        match cantidad:
            case RetencionSoportadaCantidad.REDUCCIONES_APLICABLES:
                return self.reducciones_aplicables is not None
            case RetencionSoportadaCantidad.GASTOS_DEDUCIBLES:
                return self.gastos_deducibles is not None
            case _:
                return True

    @property
    def pago_a_cuenta(self) -> Decimal:
        """Return the credit: the retención plus the whole ingreso a cuenta.

        A repercusión of the ingreso a cuenta to the taxpayer does not reduce
        it: LIRPF art. 99.6 lets repercusión decide only whether the ingreso a
        cuenta enters the base imponible, and art. 79.e deducts the ingresos a
        cuenta with no such condition.
        """
        return self.retencion + self.ingreso_a_cuenta

    @property
    def importe_integro(self) -> Decimal:
        """Return the gross income: money paid, the valuation in kind and the unrepercutido ingreso a cuenta.

        LIRPF art. 99.6 has the taxpayer include in the base the valuation of
        the payment in kind and the ingreso a cuenta, "salvo que le hubiera sido
        repercutido"; art. 43.2 states the same for the valuation.
        """
        return (
            self.importe_integro_dinerario
            + self.valoracion_especie
            + self.ingreso_a_cuenta
            - self.ingreso_a_cuenta_repercutido
        )

    def quantity(self, cantidad: RetencionSoportadaCantidad) -> Decimal:
        """Return the amount of this record a binding drawing ``cantidad`` reads.

        Raises:
            RentaValidationError: The record does not state the figure (see :meth:`states`).
        """
        match cantidad:
            case RetencionSoportadaCantidad.PAGO_A_CUENTA:
                return self.pago_a_cuenta
            case RetencionSoportadaCantidad.RETENCION:
                return self.retencion
            case RetencionSoportadaCantidad.INGRESO_A_CUENTA:
                return self.ingreso_a_cuenta
            case RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO:
                return self.ingreso_a_cuenta_repercutido
            case RetencionSoportadaCantidad.IMPORTE_INTEGRO:
                return self.importe_integro
            case RetencionSoportadaCantidad.IMPORTE_INTEGRO_DINERARIO:
                return self.importe_integro_dinerario
            case RetencionSoportadaCantidad.VALORACION_ESPECIE:
                return self.valoracion_especie
            case RetencionSoportadaCantidad.REDUCCIONES_APLICABLES:
                if self.reducciones_aplicables is None:
                    raise RentaValidationError("the record does not state the reductions the payer applied")
                return self.reducciones_aplicables
            case RetencionSoportadaCantidad.GASTOS_DEDUCIBLES:
                if self.gastos_deducibles is None:
                    raise RentaValidationError("the record does not state the deductible expenses")
                return self.gastos_deducibles

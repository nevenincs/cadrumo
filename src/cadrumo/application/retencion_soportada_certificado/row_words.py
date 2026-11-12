"""The words a frontend shows beside a stored payer record, rendered in the worker's output language.

Each table is a literal mapping so the locale audit sees every key reach the
translator; a member added to an enum without its word fails at import.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.retencion_soportada import RetencionSoportadaCantidad
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen

__all__ = [
    "RetencionSoportadaAmountColumnProjection",
    "amount_columns",
    "origin_label",
    "payer_display_name",
]

_ORIGIN_LOCALE_KEYS: Final[dict[RetencionSoportadaOrigen, str]] = {
    RetencionSoportadaOrigen.PAYER_CERTIFICATE: "aggregation.retencion_soportada.origen.payer_certificate",
    RetencionSoportadaOrigen.OPERATOR_DECLARATION: "aggregation.retencion_soportada.origen.operator_declaration",
}
if set(_ORIGIN_LOCALE_KEYS) != set(RetencionSoportadaOrigen):
    raise InternalInvariantError("every suffered-withholding origin needs its word")

_UNNAMED_PAYER_LOCALE_KEY: Final = "aggregation.retencion_soportada.payer_unnamed"

_AMOUNT_COLUMN_LOCALE_KEYS: Final[tuple[tuple[RetencionSoportadaCantidad, str], ...]] = (
    (
        RetencionSoportadaCantidad.IMPORTE_INTEGRO_DINERARIO,
        "application.ledger.entry_options.withholding_certificate_figure.importe_integro_dinerario",
    ),
    (
        RetencionSoportadaCantidad.VALORACION_ESPECIE,
        "application.ledger.entry_options.withholding_certificate_figure.valoracion_especie",
    ),
    (RetencionSoportadaCantidad.RETENCION, "application.ledger.entry_options.withholding_certificate_figure.retencion"),
    (
        RetencionSoportadaCantidad.INGRESO_A_CUENTA,
        "application.ledger.entry_options.withholding_certificate_figure.ingreso_a_cuenta",
    ),
    (
        RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO,
        "application.ledger.entry_options.withholding_certificate_figure.ingreso_a_cuenta_repercutido",
    ),
    (
        RetencionSoportadaCantidad.REDUCCIONES_APLICABLES,
        "application.ledger.entry_options.withholding_certificate_figure.reducciones_aplicables",
    ),
    (
        RetencionSoportadaCantidad.GASTOS_DEDUCIBLES,
        "application.ledger.entry_options.withholding_certificate_figure.gastos_deducibles",
    ),
    (RetencionSoportadaCantidad.PAGO_A_CUENTA, "aggregation.retencion_soportada.amount.pago_a_cuenta"),
)
"""Every amount a listed row carries, in row order; the stated figures share their words with the entry form."""


class RetencionSoportadaAmountColumnProjection(BaseModel):
    """One amount field of a listed row and the words naming it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: RetencionSoportadaCantidad
    label: str


def origin_label(origin: RetencionSoportadaOrigen) -> str:
    """Name who states a record's figures."""
    return tr(_ORIGIN_LOCALE_KEYS[origin])


def payer_display_name(payer_legal_name: str | None) -> str:
    """Name a payer by its legal name, or say that the record states none."""
    return payer_legal_name if payer_legal_name is not None else tr(_UNNAMED_PAYER_LOCALE_KEY)


def amount_columns() -> tuple[RetencionSoportadaAmountColumnProjection, ...]:
    """Name every amount a listed row carries, in row order."""
    return tuple(
        RetencionSoportadaAmountColumnProjection(field=field, label=tr(key))
        for field, key in _AMOUNT_COLUMN_LOCALE_KEYS
    )

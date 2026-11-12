"""The closed vocabularies of withholding a taxpayer suffered on income paid to them.

A payer that withholds on what it pays, or makes an ingreso a cuenta on a payment
in kind, issues a certificate of it (RIRPF art. 108.3), and the taxpayer credits
the amount against the annual Renta as a pago a cuenta (LIRPF arts. 79.e and
99.1). These tokens are persisted inside encrypted records and named by registry
bindings, so a value outside them is refused rather than carried as free text.

This is the perceptor's side only. Withholding the taxpayer practised on others,
as a withholding agent, is a different fact with its own stores and source kinds,
and none of these tokens may describe it.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RetencionSoportadaCantidad", "RetencionSoportadaClase"]


class RetencionSoportadaClase(StrEnum):
    """The income class one payer's withholding was practised on.

    The classes follow the official breakdown of the annual credit block (the
    2024 Renta manual's list of retenciones e ingresos a cuenta, and RIRPF art.
    75 for the income subject to withholding). Urban rentals take two tokens
    because the manual places their withholding in one class whether or not the
    rental constitutes an economic activity, and excludes it from the activity
    class, while the two arrive from different sources.

    Pagos fraccionados, cuotas of the non-residents' tax and the Directive
    2003/48 withholding are not per-payer income classes and have no token.
    """

    TRABAJO = "trabajo"
    CAPITAL_MOBILIARIO = "capital_mobiliario"
    ARRENDAMIENTO_INMUEBLE_URBANO = "arrendamiento_inmueble_urbano"
    """An urban rental that does not constitute an economic activity."""
    ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD = "arrendamiento_inmueble_urbano_actividad"
    """An urban rental that constitutes an economic activity."""
    ACTIVIDAD_ECONOMICA = "actividad_economica"
    """Economic-activity income other than an urban rental."""
    GANANCIA_PATRIMONIAL = "ganancia_patrimonial"
    """Capital gains, premios included."""
    ATRIBUCION_CAPITAL_MOBILIARIO = "atribucion_capital_mobiliario"
    ATRIBUCION_CAPITAL_INMOBILIARIO = "atribucion_capital_inmobiliario"
    ATRIBUCION_ACTIVIDAD_ECONOMICA = "atribucion_actividad_economica"
    ATRIBUCION_GANANCIA_PATRIMONIAL = "atribucion_ganancia_patrimonial"
    IMPUTACION_AIE_UTE = "imputacion_aie_ute"
    IMPUTACION_DERECHOS_IMAGEN = "imputacion_derechos_imagen"
    """The payer's ingreso a cuenta on image-rights imputation (LIRPF art. 92.8)."""


class RetencionSoportadaCantidad(StrEnum):
    """Which quantity of a payer's record a binding draws.

    ``PAGO_A_CUENTA`` is the credit: the retención plus the whole ingreso a
    cuenta. LIRPF art. 99.6 lets a repercusión of the ingreso a cuenta decide
    only whether it enters the base imponible; art. 79.e deducts the ingresos a
    cuenta with no such condition. So repercusión never reduces the credit.
    The other quantities serve income casillas and cross-checks.

    ``REDUCCIONES_APLICABLES`` and ``GASTOS_DEDUCIBLES`` are the two figures a
    work-income certificate states beyond the payment itself: the art. 18.2 and
    18.3 reductions the payer applied and the art. 19.2 a), b) and c) deductible
    expenses.
    """

    PAGO_A_CUENTA = "pago_a_cuenta"
    RETENCION = "retencion"
    INGRESO_A_CUENTA = "ingreso_a_cuenta"
    INGRESO_A_CUENTA_REPERCUTIDO = "ingreso_a_cuenta_repercutido"
    IMPORTE_INTEGRO = "importe_integro"
    IMPORTE_INTEGRO_DINERARIO = "importe_integro_dinerario"
    VALORACION_ESPECIE = "valoracion_especie"
    REDUCCIONES_APLICABLES = "reducciones_aplicables"
    GASTOS_DEDUCIBLES = "gastos_deducibles"

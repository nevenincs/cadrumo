"""Per-modelo result-disposition codes for the fichero "Tipo de declaración".

The AEAT fichero-BOE "Tipo de declaración" field encodes the *result disposition*
of an autoliquidación (a ingresar / a compensar / a devolver / negativa), NOT the
amendment type (ordinary vs complementaria, which is a separate "Rectificativa"
field). Hardcoding it to a constant ``"I"`` (ingreso) silently mis-files every
credit, refund, and nil return as a payment owed.

Each modelo declares its own closed code set in its AEAT Diseño de Registros
"Tipo de declaración" note. This module codifies those code sets and the
result→code derivation per modelo, so feature code (the export header composer)
emits a grounded, codified member instead of a hardcoded literal.

This module stops at the base sign-to-code mapping. The application resolver
:func:`application.modelo.result_disposition_resolution.resolve_modelo_result_disposition`
validates the full revision in its work-unit and registry context, then layers
:class:`~core.refund_election.RefundElection` and
:func:`~domain.iva.refund_eligibility.refund_disposition_available` for Modelo 303. Export
and cross-period carry read that single resolved fact through
:func:`result_disposition_is_refund`.

Grounded verbatim from the bundled official diseños
(``_data/corpus/aeat_official/disenos_registro/modelo_*``):

- M303: "C (solicitud de compensación) D (devolución) G (cuenta corriente-ingreso)
  I (ingreso) N (sin actividad/resultado cero) V (cuenta corriente-devolución)
  U (domiciliación) X (devolución por transferencia al extranjero)".
- M130 / M131: "I (ingreso), U (domiciliación), G (ingreso a anotar en CCT),
  N (negativa) y B (resultado al deducir)".
- M111 / M115 / M123: "I (ingreso), U (domiciliación), G (ingreso a anotar en CCT)
  y N (negativa)".
- M200: "I (Ingreso), U (Domiciliación), N (Negativa/Resultado cero),
  D (Solicitud de devolución), R (Renuncia a la devolución), G/V/X (CCT / extranjero)".
- M202: "I (ingreso), U (domiciliación), G (Ingreso en C.C.T.) y
  N (Negativa/Sin actividad/Resultado cero)".
- M210: casilla 31 "Resultado de la autoliquidación"; positive is ingreso,
  zero is cuota cero, and negative is solicitud de devolución.

The quarter decides a negative instalment result, per the bundled official
instructions (``_data/corpus/aeat_official/instructions/modelo_130`` and
``modelo_131``, sections "(5) A deducir" and "(6) Negativa"): a negative
result of the 1st, 2nd or 3rd quarter is "A deducir" (``B``) from later
instalments of the same year, while a negative result of the 4th quarter, like
a zero one, is "Negativa" (``N``). Modelo 130 reads its casilla 19, Modelo 131
its casilla 15.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from .errors.hierarchy import CoreValidationError
from .modelo import Modelo
from .period import Period, StandardPeriodCode


class ResultDisposition(StrEnum):
    """AEAT fichero "Tipo de declaración" result-disposition codes (all modelos).

    The member *value* is the single-character code the fichero expects. Not every
    modelo admits every code — the per-modelo derivation only selects codes that
    modelo's diseño declares.

    See Also:
        :class:`~core.refund_election.RefundElection`
            Operator input that can request a Modelo 303 ``C`` credit be filed
            as ``D`` after the application resolver applies the refund gate.
        :func:`result_disposition_is_refund`
            Classifier for the refund dispositions that suppress
            compensación carry-forward.
    """

    COMPENSACION = "C"
    """Solicitud de compensación — an IVA credit carried forward, ``a compensar``."""
    DEVOLUCION = "D"
    """Solicitud de devolución — refund requested."""
    CUENTA_CORRIENTE_INGRESO = "G"
    """Cuenta corriente tributaria — ingreso (operator payment-method election)."""
    INGRESO = "I"
    """Ingreso — a positive result the taxpayer pays (a ingresar)."""
    NEGATIVA = "N"
    """Negativa / sin actividad / resultado cero."""
    CUENTA_CORRIENTE_DEVOLUCION = "V"
    """Cuenta corriente tributaria — devolución."""
    DOMICILIACION = "U"
    """Domiciliación del ingreso en cuenta de cargo (payment-method election)."""
    DEVOLUCION_TRANSFERENCIA_EXTRANJERO = "X"
    """Devolución por transferencia al extranjero."""
    RESULTADO_A_DEDUCIR = "B"
    """Resultado a deducir (pago fraccionado IRPF M130/M131 negative carry)."""
    RENUNCIA_DEVOLUCION = "R"
    """Renuncia a la devolución (IS election)."""


@dataclass(frozen=True)
class _DispositionSpec:
    """The credit/zero disposition codes for one modelo.

    A positive result is always :attr:`ResultDisposition.INGRESO`. ``negative`` is
    the code for a sub-zero result (modelo-specific: C for IVA, B for IRPF pagos
    fraccionados, D for IS), and ``zero`` is the code for a zero result (N for all
    modelos here). ``U`` (domiciliación), ``G``/``V`` (cuenta corriente), ``X`` /
    ``R`` are operator elections layered on a base disposition, not derivable from
    the result amount alone; the caller records those explicitly.

    """

    negative: ResultDisposition
    zero: ResultDisposition
    declared: frozenset[ResultDisposition]
    """The closed code set the diseño's "Tipo de declaración" note declares.

    It decides which operator elections a modelo admits (``U`` is admissible
    only where it is declared here), and it must contain every code the spec
    can derive.
    """
    final_quarter_negative: ResultDisposition | None = None
    """The code for a negative result of the year's last quarter, where it differs from ``negative``."""

    def __post_init__(self) -> None:
        derivable = {ResultDisposition.INGRESO, self.negative, self.zero}
        if self.final_quarter_negative is not None:
            derivable.add(self.final_quarter_negative)
        undeclared = sorted(code.value for code in derivable - self.declared)
        if undeclared:
            raise CoreValidationError(
                f"result disposition spec derives undeclared codes {', '.join(undeclared)}",
                context={"undeclared_codes": ", ".join(undeclared)},
            )


#: Each modelo's closed "Tipo de declaración" code set, verbatim from the
#: diseño notes quoted in this module's docstring. Modelo 131 shares the 130
#: set; Modelos 115, 123 and 202 share the 111 set.
_M303_DECLARED: Final[frozenset[ResultDisposition]] = frozenset(
    {
        ResultDisposition.COMPENSACION,
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
        ResultDisposition.DOMICILIACION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    },
)
_M130_DECLARED: Final[frozenset[ResultDisposition]] = frozenset(
    {
        ResultDisposition.RESULTADO_A_DEDUCIR,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
        ResultDisposition.DOMICILIACION,
    },
)
_M111_DECLARED: Final[frozenset[ResultDisposition]] = frozenset(
    {
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
        ResultDisposition.DOMICILIACION,
    },
)
_M200_DECLARED: Final[frozenset[ResultDisposition]] = frozenset(
    {
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
        ResultDisposition.RENUNCIA_DEVOLUCION,
        ResultDisposition.DOMICILIACION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    },
)
_M210_DECLARED: Final[frozenset[ResultDisposition]] = frozenset(
    {
        ResultDisposition.DEVOLUCION,
        ResultDisposition.INGRESO,
        ResultDisposition.NEGATIVA,
    },
)


#: Per-modelo disposition spec, grounded in each bundled diseño's "Tipo de
#: declaración" note and the registry's result-casilla ``semantic_role``. Modelos
#: absent from this table and from :data:`_FIXED_DISPOSITION` derive ``None``; the
#: application resolver refuses one whose layout declares the header and records
#: no disposition for the rest.
_DISPOSITION_SPEC: dict[str, _DispositionSpec] = {
    # IVA: credit is a compensar (C). Result casilla 71 "Resultado final".
    Modelo("303"): _DispositionSpec(
        negative=ResultDisposition.COMPENSACION,
        zero=ResultDisposition.NEGATIVA,
        declared=_M303_DECLARED,
    ),
    # IRPF pago fraccionado: a negative result of quarters 1 to 3 is "a deducir"
    # (B), not C; in the 4th quarter it is "negativa" (N). Instructions of
    # Modelo 130, sections (5) A deducir and (6) Negativa, on casilla 19.
    Modelo("130"): _DispositionSpec(
        negative=ResultDisposition.RESULTADO_A_DEDUCIR,
        zero=ResultDisposition.NEGATIVA,
        final_quarter_negative=ResultDisposition.NEGATIVA,
        declared=_M130_DECLARED,
    ),
    # Instructions of Modelo 131, sections (5) A deducir and (6) Negativa, on casilla 15.
    Modelo("131"): _DispositionSpec(
        negative=ResultDisposition.RESULTADO_A_DEDUCIR,
        zero=ResultDisposition.NEGATIVA,
        final_quarter_negative=ResultDisposition.NEGATIVA,
        declared=_M130_DECLARED,
    ),
    # Retenciones: only I/N (no credit code). "Resultado a ingresar" casilla.
    Modelo("111"): _DispositionSpec(
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
        declared=_M111_DECLARED,
    ),
    Modelo("115"): _DispositionSpec(
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
        declared=_M111_DECLARED,
    ),
    Modelo("123"): _DispositionSpec(
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
        declared=_M111_DECLARED,
    ),
    # IS annual: credit is a devolución (D), not C. Result casilla
    # DP200014B:00599 (semantic_role is_resultado_ingresar_o_devolver, Estado),
    # signed. Renuncia R is an explicit election, not derived; default credit
    # disposition is D.
    Modelo("200"): _DispositionSpec(
        negative=ResultDisposition.DEVOLUCION,
        zero=ResultDisposition.NEGATIVA,
        declared=_M200_DECLARED,
    ),
    # IS pago fraccionado: only I/N. Result is the active modality's "a ingresar"
    # casilla — 40.2 -> 03, 40.3 -> 34; both are >= 0 and exactly one is non-zero.
    Modelo("202"): _DispositionSpec(
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
        declared=_M111_DECLARED,
    ),
    # IRNR autoliquidación: casilla 31 is signed; a negative result requests
    # devolución and zero is the declared cuota-cero disposition.
    Modelo("210"): _DispositionSpec(
        negative=ResultDisposition.DEVOLUCION,
        zero=ResultDisposition.NEGATIVA,
        declared=_M210_DECLARED,
    ),
}


#: Modelos whose disposition the design fixes rather than the result deriving.
#: Modelo 360 is a refund application: its design section 4 is "Devolución
#: solicitada" and its layout has no "Tipo de declaración" slot, so DEVOLUCION
#: is never rendered but still drives the account gate, receipts and events.
_FIXED_DISPOSITION: dict[str, ResultDisposition] = {
    Modelo("360"): ResultDisposition.DEVOLUCION,
}


#: The fichero "Tipo de declaración" codes that mean the negative result is
#: requested as devolución and therefore excluded from compensación carry. A
#: refunded period generates ZERO compensación carry-forward (RD
#: 1624/1992 art. 30 / Ley 37/1992 art. 116). ``D`` is the ordinary refund
#: request; ``V`` (cuenta corriente devolución) and ``X`` (devolución por
#: transferencia al extranjero) are the same disposition through a different
#: settlement channel. ``C`` (compensación, carried) is deliberately absent.
_REFUND_DISPOSITIONS: frozenset[ResultDisposition] = frozenset(
    {
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    },
)


def result_disposition_is_refund(disposition: ResultDisposition) -> bool:
    """Return whether ``disposition`` files the result as a refund (devolución).

    A refund disposition (``D`` / ``V`` / ``X``) requests devolución rather than
    carry-forward, so a refunded Modelo 303 period must generate zero compensación
    carry-forward. The carried disposition (``C``, compensación) and every
    ingreso/negativa code return ``False``. This is the single determined fact the
    export "Tipo de declaración" and the carry-forward derivation both read, so
    the fichero ``D`` and the cross-period carry cannot disagree.
    """
    return disposition in _REFUND_DISPOSITIONS


#: The codes for which the fichero must carry the taxpayer's bank account.
#: A SEPARATE axis from refund-ness, and keeping them separate is the whole
#: point of this second frozenset. Refund-ness answers "does this period carry
#: compensación forward"; this answers "does AEAT need an account number". They
#: coincide for the three refund codes and diverge at ``U``.
#:
#: ``U`` (domiciliación del ingreso en cuenta de cargo) is an INGRESO settled by
#: direct debit, so AEAT needs an account to CHARGE. The bundled Diseño de
#: Registro names the field ``Domiciliación/Devolución - IBAN`` -- one field
#: serving both directions -- and lists ``U`` among the payment forms, so the
#: account is required there by AEAT's own record design. Folding ``U`` into
#: :data:`_REFUND_DISPOSITIONS` instead would be a real defect rather than a
#: shortcut: that set drives the compensación carry decision, so a domiciliación
#: filing would generate zero carry-forward while remaining a positive-result
#: ingreso that carries nothing in the first place only by coincidence.
#:
#: ``G`` (cuenta corriente tributaria — ingreso) is deliberately EXCLUDED and the
#: exclusion is an open question rather than a ruling: settlement through the
#: tributary current account may legitimately need no debit account, and no
#: bundled AEAT text has been read that settles it. Excluded because asserting
#: the account is required there would be a guess with a filing consequence.
_BANK_ACCOUNT_DISPOSITIONS: frozenset[ResultDisposition] = _REFUND_DISPOSITIONS | {
    ResultDisposition.DOMICILIACION,
}


def result_disposition_requires_bank_account(disposition: ResultDisposition) -> bool:
    """Return whether ``disposition``'s fichero must carry a bank account.

    True for the three refund codes (AEAT pays into the account) and for ``U``,
    domiciliación del ingreso (AEAT charges the account). Read by BOTH the
    header composer that emits the account block and the record guard that
    decides whether the account page reaches disk, because those two answering
    differently is how a filing acquires an account page with no account in it,
    or an account block with no page to carry it.

    See Also:
        :func:`result_disposition_is_refund`
            The adjacent axis. Do not substitute one for the other: that one
            governs compensación carry-forward, this one governs whether the
            account is on the wire.
    """
    return disposition in _BANK_ACCOUNT_DISPOSITIONS


def result_disposition_declares(modelo: str, disposition: ResultDisposition) -> bool:
    """Return whether ``modelo``'s diseño declares ``disposition`` as a "Tipo de declaración" code.

    An operator election such as ``U`` (domiciliación) is admissible only for
    a modelo whose closed code set declares it. A modelo without a codified
    spec declares nothing, so every election on it is refused rather than
    guessed.
    """
    fixed = _FIXED_DISPOSITION.get(modelo)
    if fixed is not None:
        return disposition is fixed
    spec = _DISPOSITION_SPEC.get(modelo)
    return spec is not None and disposition in spec.declared


def has_result_disposition_spec(modelo: str) -> bool:
    """Return whether ``modelo`` derives its disposition from a result amount."""
    return modelo in _DISPOSITION_SPEC


def fixed_result_disposition(modelo: str) -> ResultDisposition | None:
    """Return the disposition the design of ``modelo`` fixes, if any."""
    return _FIXED_DISPOSITION.get(modelo)


def result_disposition_for_amount(modelo: str, result: Decimal, *, period: Period) -> ResultDisposition:
    """Map the final result of ``modelo`` in ``period`` to its diseño-grounded code.

    - ``> 0`` → :attr:`ResultDisposition.INGRESO` (``I``) for every modelo.
    - ``< 0`` → the modelo's credit code (C for M303 IVA, B for M130/M131 IRPF
      pagos fraccionados in quarters 1 to 3 and N in the 4th; N for retenciones,
      which cannot go sub-zero in practice).
    - ``== 0`` → the modelo's zero code (``N``).
    """
    spec = _DISPOSITION_SPEC[modelo]
    if result > 0:
        return ResultDisposition.INGRESO
    if result < 0:
        if spec.final_quarter_negative is not None and period.standard_code is StandardPeriodCode.Q4:
            return spec.final_quarter_negative
        return spec.negative
    return spec.zero


__all__ = [
    "ResultDisposition",
    "fixed_result_disposition",
    "has_result_disposition_spec",
    "result_disposition_declares",
    "result_disposition_for_amount",
    "result_disposition_is_refund",
    "result_disposition_requires_bank_account",
]

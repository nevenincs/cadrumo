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
:func:`application.modelo._result_disposition_resolution.resolve_modelo_result_disposition`
validates the full revision in its work-unit and registry context, then layers
:class:`~core.RefundElection` and
:func:`~domain.iva.refund_disposition_available` for Modelo 303. Export
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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from .casilla_id import CasillaId, validated_casilla_id
from ._modelo import Modelo
from .errors.hierarchy import CoreValidationError


class ResultDisposition(StrEnum):
    """AEAT fichero "Tipo de declaración" result-disposition codes (all modelos).

    The member *value* is the single-character code the fichero expects. Not every
    modelo admits every code — the per-modelo derivation only selects codes that
    modelo's diseño declares.

    See Also:
        :class:`~core.RefundElection`
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
    """The result casilla(s) and credit/zero disposition codes for one modelo.

    A positive result is always :attr:`ResultDisposition.INGRESO`. ``negative`` is
    the code for a sub-zero result (modelo-specific: C for IVA, B for IRPF pagos
    fraccionados, D for IS), and ``zero`` is the code for a zero result (N for all
    modelos here). ``U`` (domiciliación), ``G``/``V`` (cuenta corriente), ``X`` /
    ``R`` are operator elections layered on a base disposition, not derivable from
    the result amount alone; the caller records those explicitly.

    ``result_casilla_ids`` is an ordered tuple of canonical ``casilla.id`` values
    summed to the final result. It carries more than one key when a modelo has
    revision-specific result ids (M123 2019-2023 vs 2024+) or mutually-exclusive
    result casillas (M202's 40.2 vs 40.3 — exactly one is non-zero).
    """

    result_casilla_ids: tuple[CasillaId, ...]
    negative: ResultDisposition
    zero: ResultDisposition


_M303_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("71", surface="_M303_RESULT_CASILLA")
_M130_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("19", surface="_M130_RESULT_CASILLA")
_M131_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("15", surface="_M131_RESULT_CASILLA")
_M111_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("30", surface="_M111_RESULT_CASILLA")
_M115_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("05", surface="_M115_RESULT_CASILLA")
_M123_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("14", surface="_M123_RESULT_CASILLA")
_M123_2019_2023_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "08",
    surface="_M123_2019_2023_RESULT_CASILLA",
)
_M200_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "DP200014B:00599",
    surface="_M200_RESULT_CASILLA",
)
_M202_402_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("03", surface="_M202_402_RESULT_CASILLA")
_M202_403_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id("34", surface="_M202_403_RESULT_CASILLA")
_M210_RESULT_CASILLA: Final[CasillaId] = validated_casilla_id(
    "cuota_diferencial",
    surface="_M210_RESULT_CASILLA",
)


#: Per-modelo disposition spec, grounded in each bundled diseño's "Tipo de
#: declaración" note and the registry's result-casilla ``semantic_role``. Modelos
#: absent from this table return ``None`` and the caller applies a documented
#: fallback rather than a guessed mapping.
_DISPOSITION_SPEC: dict[str, _DispositionSpec] = {
    # IVA: credit is a compensar (C). Result casilla 71 "Resultado final".
    Modelo.M303: _DispositionSpec(
        result_casilla_ids=(_M303_RESULT_CASILLA,),
        negative=ResultDisposition.COMPENSACION,
        zero=ResultDisposition.NEGATIVA,
    ),
    # IRPF pago fraccionado: a negative result is "resultado a deducir" (B), not C.
    Modelo.M130: _DispositionSpec(
        result_casilla_ids=(_M130_RESULT_CASILLA,),
        negative=ResultDisposition.RESULTADO_A_DEDUCIR,
        zero=ResultDisposition.NEGATIVA,
    ),
    Modelo.M131: _DispositionSpec(
        result_casilla_ids=(_M131_RESULT_CASILLA,),
        negative=ResultDisposition.RESULTADO_A_DEDUCIR,
        zero=ResultDisposition.NEGATIVA,
    ),
    # Retenciones: only I/N (no credit code). "Resultado a ingresar" casilla.
    Modelo.M111: _DispositionSpec(
        result_casilla_ids=(_M111_RESULT_CASILLA,),
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
    ),
    Modelo.M115: _DispositionSpec(
        result_casilla_ids=(_M115_RESULT_CASILLA,),
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
    ),
    Modelo.M123: _DispositionSpec(
        result_casilla_ids=(_M123_RESULT_CASILLA, _M123_2019_2023_RESULT_CASILLA),
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
    ),
    # IS annual: credit is a devolución (D), not C. Result casilla
    # DP200014B:00599 (semantic_role is_resultado_ingresar_o_devolver, Estado),
    # signed. Renuncia R is an explicit election, not derived; default credit
    # disposition is D.
    Modelo.M200: _DispositionSpec(
        result_casilla_ids=(_M200_RESULT_CASILLA,),
        negative=ResultDisposition.DEVOLUCION,
        zero=ResultDisposition.NEGATIVA,
    ),
    # IS pago fraccionado: only I/N. Result is the active modality's "a ingresar"
    # casilla — 40.2 -> 03, 40.3 -> 34; both are >= 0 and exactly one is non-zero.
    Modelo.M202: _DispositionSpec(
        result_casilla_ids=(_M202_402_RESULT_CASILLA, _M202_403_RESULT_CASILLA),
        negative=ResultDisposition.NEGATIVA,
        zero=ResultDisposition.NEGATIVA,
    ),
    # IRNR autoliquidación: casilla 31 is signed; a negative result requests
    # devolución and zero is the declared cuota-cero disposition.
    Modelo.M210: _DispositionSpec(
        result_casilla_ids=(_M210_RESULT_CASILLA,),
        negative=ResultDisposition.DEVOLUCION,
        zero=ResultDisposition.NEGATIVA,
    ),
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


def modelo_has_codified_disposition(modelo: str) -> bool:
    """Return whether ``modelo`` has a codified, diseño-grounded disposition spec.

    This is the capability probe for callers that need to decide whether
    :func:`derive_result_disposition` can produce a :class:`ResultDisposition`
    without falling back to their own documented export default.
    """
    return modelo in _DISPOSITION_SPEC


def result_disposition_casilla_ids(modelo: str) -> tuple[CasillaId, ...] | None:
    """Return the canonical result ``casilla.id`` values for ``modelo``.

    These are the only keys :func:`derive_result_disposition` accepts in its
    ``casilla_values`` mapping. A caller holding a full calculation revision must
    validate and filter the revision to this tuple first; passing unrelated
    result metadata raises :class:`~core.errors.CoreValidationError`.
    """
    spec = _DISPOSITION_SPEC.get(modelo)
    if spec is None:
        return None
    return spec.result_casilla_ids


def derive_result_disposition(modelo: str, casilla_values: Mapping[CasillaId, Decimal]) -> ResultDisposition | None:
    """Derive the fichero result disposition for ``modelo`` from its computed result.

    Sums the modelo's final-result casilla(s) from ``casilla_values`` and maps the
    sign to the modelo's diseño-grounded code. ``casilla_values`` must contain
    only the result casilla ids returned by :func:`result_disposition_casilla_ids`;
    callers with a full revision value map must first validate it against the
    selected registry revision, then filter to those ids.

    - ``> 0`` → :attr:`ResultDisposition.INGRESO` (``I``) for every modelo.
    - ``< 0`` → the modelo's credit code (C for M303 IVA, B for M130/M131 IRPF
      pagos fraccionados; N for retenciones, which cannot go sub-zero in practice).
    - ``== 0`` (or the casilla absent) → the modelo's zero code (``N``).

    Returns the derived :class:`ResultDisposition`, or ``None`` for a modelo
    without a codified spec, so the caller applies a documented fallback rather
    than a guessed disposition.
    """
    spec = _DISPOSITION_SPEC.get(modelo)
    if spec is None:
        return None
    _reject_non_result_casilla_values(modelo, spec, casilla_values)
    result = sum((casilla_values.get(casilla_id, Decimal("0")) for casilla_id in spec.result_casilla_ids), Decimal("0"))
    if result > 0:
        return ResultDisposition.INGRESO
    if result < 0:
        return spec.negative
    return spec.zero


def _reject_non_result_casilla_values(
    modelo: str,
    spec: _DispositionSpec,
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    result_ids = frozenset(spec.result_casilla_ids)
    non_result_ids = tuple(sorted(casilla_id for casilla_id in casilla_values if casilla_id not in result_ids))
    if not non_result_ids:
        return
    accepted = ", ".join(repr(casilla_id) for casilla_id in spec.result_casilla_ids)
    received = ", ".join(repr(casilla_id) for casilla_id in non_result_ids)
    raise CoreValidationError(
        f"result disposition for modelo {modelo!r} received non-result casilla.id values "
        f"{received}; pass only result casilla.id values {accepted}",
        context={
            "modelo": modelo,
            "casilla_ids": received,
            "result_casilla_ids": accepted,
        },
    )


__all__ = [
    "ResultDisposition",
    "derive_result_disposition",
    "modelo_has_codified_disposition",
    "result_disposition_casilla_ids",
    "result_disposition_is_refund",
    "result_disposition_requires_bank_account",
]

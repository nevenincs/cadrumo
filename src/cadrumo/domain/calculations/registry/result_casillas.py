"""Each modelo's result casillas, which the registry declares.

The casilla ids are form data, so a governed fact holds them. The disposition codes
those amounts map to stay in :mod:`cadrumo.core.result_disposition`. A modelo lists
more than one id when its revisions name the result differently, or when its
result casillas are mutually exclusive.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.casilla_value_absence import AbsentCasillaReading
from ....core.errors.hierarchy import CoreValidationError
from ....core.period import Period
from ....core.result_disposition import (
    ResultDisposition,
    fixed_result_disposition,
    has_result_disposition_spec,
    result_disposition_for_amount,
)
from .form_codes import resolve_form_codes

_RESULT_CASILLAS_FACT = "modelo-result-casillas"


def result_disposition_casilla_ids(modelo: str) -> tuple[CasillaId, ...] | None:
    """Return the canonical result ``casilla.id`` values for ``modelo``.

    These are the only keys :func:`derive_result_disposition` accepts in its
    ``casilla_values`` mapping. A caller holding a full calculation revision must
    validate and filter the revision to this tuple first; passing unrelated
    result metadata raises :class:`~core.errors.hierarchy.CoreValidationError`.
    """
    if not has_result_disposition_spec(modelo):
        return None
    tokens = resolve_form_codes(_RESULT_CASILLAS_FACT).ordered_codes(f"casillas.{modelo}")
    return tuple(validated_casilla_id(token, surface=_RESULT_CASILLAS_FACT) for token in tokens)


def canonical_result_amount(modelo: str, casilla_values: Mapping[CasillaId, Decimal]) -> Decimal | None:
    """Return the canonical final-result sum after rejecting unrelated casillas.

    The caller supplies only the modelo's result-casilla subset. A missing
    declared result casilla is represented as zero for disposition derivation;
    filing-time consumers that require an observed value enforce its presence
    before calling this shared owner.
    """
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None:
        return None
    _reject_non_result_casilla_values(modelo, result_ids, casilla_values)
    return sum(
        (AbsentCasillaReading.RESULT_CASILLA_ALTERNATIVE.read(casilla_values, casilla_id) for casilla_id in result_ids),
        Decimal("0"),
    )


def derive_result_disposition(
    modelo: str, casilla_values: Mapping[CasillaId, Decimal], *, period: Period
) -> ResultDisposition | None:
    """Derive the fichero result disposition for ``modelo`` from its computed result in ``period``.

    Sums the modelo's final-result casilla(s) from ``casilla_values`` and maps the
    sign to the modelo's code. ``casilla_values`` must contain only the result
    casilla ids returned by :func:`result_disposition_casilla_ids`; callers with a
    full revision value map must first validate it against the selected registry
    revision, then filter to those ids.

    A modelo whose design fixes its disposition returns that code whatever the
    values. Returns ``None`` for a modelo without a codified spec, so the caller
    refuses or records no disposition rather than guessing one.
    """
    fixed = fixed_result_disposition(modelo)
    if fixed is not None:
        return fixed
    result = canonical_result_amount(modelo, casilla_values)
    if result is None:
        return None
    return result_disposition_for_amount(modelo, result, period=period)


def _reject_non_result_casilla_values(
    modelo: str,
    result_ids: tuple[CasillaId, ...],
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    allowed = frozenset(result_ids)
    non_result_ids = tuple(sorted(casilla_id for casilla_id in casilla_values if casilla_id not in allowed))
    if not non_result_ids:
        return
    accepted = ", ".join(repr(casilla_id) for casilla_id in result_ids)
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
    "canonical_result_amount",
    "derive_result_disposition",
    "result_disposition_casilla_ids",
]

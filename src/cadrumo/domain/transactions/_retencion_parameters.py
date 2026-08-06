"""Registry-backed loader for the RIRPF art. 95 retención rates.

The two rates that RD 439/2007 (RIRPF) art. 95.1 fixes for rendimientos de
actividades económicas profesionales — 15 % general, 7 % in the
inicio-de-actividades window — are regulatory values, so they live in
``registry/aeat/legal/irpf-retencion-actividades.toml`` under
``[parameters."rirpf-art-95:*"]`` entries with their BOE citation and review
metadata, and Python consumers read them from here. They were previously a
bare ``Decimal("0.15")`` literal in :mod:`domain.transactions._models`, where
neither the figure nor its legal basis was auditable.

The loader follows the idiom of
:mod:`domain.iva._recargo_equivalencia`: the registry parameter catalogue is
read through the cycle-safe ``load_legal_parameters_only`` entry point rather
than by a direct ``tomllib`` load, and the result is a frozen pydantic record.
The read is memoised because the withheld-amount inference that consumes the
maximum-rate bound runs per transaction on the ledger hot path.

What these rates are *for*: :attr:`RirpfArt95RetencionRates.general_rate` is the
upper bound on a **bounded inference**, not a rate the system ever applies. A
retención is declared by the operator or inferred as invoice gross minus cash
and then capped; no path may invert a rate to reconstruct a base from cash,
because selecting the applicable rate for a row is a per-row legal fact the
system cannot determine.

See Also:
    :mod:`domain.iva._components`
        Declares, per IVA category, whether a retención is expected at all.
    :mod:`domain.iva._recargo_equivalencia`
        The loader idiom this module follows.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.resources import bundled_path
from ._errors import TransactionValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping


class RirpfArt95RetencionRates(BaseModel):
    """Frozen record of the RIRPF art. 95.1 retención rates.

    Attributes:
        general_rate: 15 % applied to the ingresos íntegros satisfechos when
            the rendimiento is the contraprestación of an actividad
            profesional (RIRPF art. 95.1, first paragraph).
        inicio_actividad_rate: 7 % applied in the período impositivo of inicio
            de actividades profesionales and the two following, provided no
            professional activity was carried on in the preceding year
            (RIRPF art. 95.1, second paragraph).
    """

    model_config = STRICT_FROZEN_CONFIG

    general_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    inicio_actividad_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))


_GENERAL_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-profesionales-general"
_INICIO_PARAM_ID: Final[str] = "rirpf-art-95:retencion-actividades-profesionales-inicio"


@lru_cache(maxsize=1)
def load_retencion_actividades_rates() -> RirpfArt95RetencionRates:
    """Return the RIRPF art. 95.1 retención rates from the registry catalogue.

    Returns:
        A :class:`RirpfArt95RetencionRates` record with both rate values.

    Raises:
        TransactionValidationError: If either expected parameter id is absent,
            carries no string value, or does not parse as a ``Decimal``, or if
            the registry parameter catalogue cannot be loaded.
    """
    # Imported inside the function for the same reason the recargo loader does:
    # the full registry import path reaches back into the domain packages this
    # module belongs to, and a module-level import would close that cycle.
    from ..calculations.registry import RegistryError, load_legal_parameters_only

    try:
        parameters = load_legal_parameters_only(bundled_path("registry", "aeat"))
    except RegistryError as exc:
        raise TransactionValidationError(
            f"failed to load the RIRPF art. 95 retención parameters: {exc}",
        ) from exc
    return RirpfArt95RetencionRates(
        general_rate=_decimal_parameter(parameters, _GENERAL_PARAM_ID),
        inicio_actividad_rate=_decimal_parameter(parameters, _INICIO_PARAM_ID),
    )


def maximum_supported_activity_retencion_rate() -> Decimal:
    """Return the upper bound the withheld-amount inference is capped at.

    The bound is the RIRPF art. 95.1 general rate: an inferred retención above
    15 % of the taxable base is evidence that the recorded cash figure is the
    invoice base without IVA rather than a net-of-retención payment, so the
    inference is refused instead of persisting a fabricated withholding.

    Returns:
        The maximum retención rate the activity inference will accept.
    """
    return load_retencion_actividades_rates().general_rate


def _decimal_parameter(parameters: Mapping[str, object], parameter_id: str) -> Decimal:
    """Read one registry parameter as a ``Decimal``."""
    try:
        parameter = parameters[parameter_id]
    except KeyError as exc:
        raise TransactionValidationError(
            f"the legal-parameter catalogue is missing RIRPF art. 95 parameter {parameter_id!r}",
        ) from exc
    value = getattr(parameter, "value", None)
    if not isinstance(value, str):
        raise TransactionValidationError(
            f"RIRPF art. 95 parameter {parameter_id!r} has no string value",
        )
    try:
        return Decimal(value)
    except ArithmeticError as exc:
        raise TransactionValidationError(
            f"RIRPF art. 95 parameter {parameter_id!r} value {value!r} is not a Decimal",
        ) from exc


__all__ = [
    "RirpfArt95RetencionRates",
    "load_retencion_actividades_rates",
    "maximum_supported_activity_retencion_rate",
]

"""Registry-backed loader for LIVA art. 161 recargo de equivalencia rates.

Closes the recargo de equivalencia rate gap in the IVA substrate:
the four LIVA art. 161 rate values (general 5.2 %, reduced 1.4 %,
super-reduced 0.5 %, tobacco 1.75 %) live in
``registry/aeat/legal/iva-recargo-equivalencia.toml`` under
``[parameters."liva-art-161:*"]`` entries with explicit BOE
citations and review metadata, and Python consumers import them
from this module.

The loader follows the same idiom as
:mod:`aeat.domain.fincas._imputacion_parameters`: a frozen pydantic
record loaded once at module import time, with an explicit
:func:`recargo_rate_for` helper that maps from the substrate's
:class:`IvaRateKind` tier to the corresponding recargo Decimal.
The ``LIVA_ART_161_RECARGO`` accessor is the canonical source for
recargo de equivalencia rates across the codebase.

The recargo de equivalencia regime (LIVA arts. 148-163) applies to
comerciantes minoristas (retailers) with limited annual revenue who
buy stock for resale; their suppliers charge them an additional
recargo on top of the regular IVA rate. The four rates align with
the four IVA tiers per LIVA art. 161:

* General (21 % IVA) → 5.2 % recargo (art. 161 1.º).
* Reduced (10 % IVA, art. 91 uno) → 1.4 % recargo (art. 161 2.º).
* Super-reduced (4 % IVA, art. 91 dos) → 0.5 % recargo (art. 161 3.º).
* Tobacco-specific → 1.75 % recargo (art. 161 4.º).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.resources import bundled_path
from ._errors import IvaCatalogueError, IvaValidationError
from ._schema import IvaRateKind


class LivaArt161RecargoRates(BaseModel):
    """Frozen record of the LIVA art. 161 recargo de equivalencia rates.

    Attributes:
        general_rate: 5.2 % recargo applied alongside the 21 % IVA
            tier (LIVA art. 161 1.º).
        reducido_rate: 1.4 % recargo applied alongside the 10 % IVA
            tier (LIVA art. 161 2.º, referencing art. 91 uno).
        super_reducido_rate: 0.5 % recargo applied alongside the 4 %
            IVA tier (LIVA art. 161 3.º, referencing art. 91 dos).
        tabaco_rate: 1.75 % recargo applied to entregas de labores
            del tabaco (LIVA art. 161 4.º).
    """

    model_config = STRICT_FROZEN_CONFIG

    general_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    reducido_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    super_reducido_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    tabaco_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))


_GENERAL_PARAM_ID: Final[str] = "liva-art-161:recargo-rate-general"
_REDUCIDO_PARAM_ID: Final[str] = "liva-art-161:recargo-rate-reducido"
_SUPER_REDUCIDO_PARAM_ID: Final[str] = "liva-art-161:recargo-rate-super-reducido"
_TABACO_PARAM_ID: Final[str] = "liva-art-161:recargo-rate-tabaco"


def _load_rates() -> LivaArt161RecargoRates:
    """Read the four LIVA art. 161 rate parameters from the registry catalogue.

    Routes through ``aeat.domain.calculations.registry.load_registry_tree``
    so parameters land in the validated :class:`RegistryCatalogues.parameters`
    surface (single config-resolution path). The retired direct
    ``tomllib.load`` of ``registry/aeat/legal/iva-recargo-equivalencia.toml``
    is replaced — bypassing the loader was the same architectural drift
    pattern as direct ``os.environ`` reads.

    Returns:
        A :class:`LivaArt161RecargoRates` record with the four rate values.

    Raises:
        IvaCatalogueError: If any of the four expected parameter ids is absent
            or if the registry catalogue cannot be loaded.
    """
    # load_legal_parameters_only is the cycle-safe entry point — the full
    # load_registry_tree path pulls in registry._bindings which imports
    # from aeat.domain.iva, triggering a circular import at this very
    # module's import time.
    from ..calculations.registry import RegistryError
    from ..calculations.registry._loader import load_legal_parameters_only

    try:
        parameters = load_legal_parameters_only(bundled_path("registry", "aeat"))
    except RegistryError as exc:
        raise IvaCatalogueError(f"failed to load IVA recargo-equivalencia legal parameters: {exc}") from exc
    return _rates_from_catalogue(parameters)


def _rates_from_catalogue(parameters: Mapping[str, object]) -> LivaArt161RecargoRates:
    """Build the typed LIVA art. 161 rate record from validated registry entries."""
    try:
        general_raw = _parameter_value(parameters, _GENERAL_PARAM_ID)
        reducido_raw = _parameter_value(parameters, _REDUCIDO_PARAM_ID)
        super_reducido_raw = _parameter_value(parameters, _SUPER_REDUCIDO_PARAM_ID)
        tabaco_raw = _parameter_value(parameters, _TABACO_PARAM_ID)
    except KeyError as exc:
        raise IvaCatalogueError(
            "the IVA recargo-equivalencia legal-parameter catalogue is missing "
            f"LIVA art. 161 parameter {exc.args[0]!r}",
        ) from exc

    try:
        return LivaArt161RecargoRates(
            general_rate=Decimal(general_raw),
            reducido_rate=Decimal(reducido_raw),
            super_reducido_rate=Decimal(super_reducido_raw),
            tabaco_rate=Decimal(tabaco_raw),
        )
    except (ValueError, TypeError) as exc:
        raise IvaValidationError(f"failed to parse recargo rates as Decimal: {exc}") from exc


def _parameter_value(parameters: Mapping[str, object], parameter_id: str) -> str:
    value = getattr(parameters[parameter_id], "value", None)
    if not isinstance(value, str):
        raise IvaValidationError(f"LIVA art. 161 parameter {parameter_id!r} has no string value")
    return value


def load_recargo_rates() -> LivaArt161RecargoRates:
    """Public accessor for the LIVA art. 161 recargo de equivalencia rates.

    Reads the four art. 161 rate parameters from the bundled
    legal-parameter catalogue and returns the typed
    :class:`LivaArt161RecargoRates` record. Use
    :func:`recargo_rate_for` for the convenient ``IvaRateKind``-
    keyed lookup; tobacco callers read ``.tabaco_rate`` directly.
    """
    return _load_rates()


def recargo_rate_for(rate_kind: IvaRateKind) -> Decimal | None:
    """Return the recargo de equivalencia rate aligned with ``rate_kind``.

    Args:
        rate_kind: The substrate IVA rate tier.

    Returns:
        The matching recargo Decimal for ``GENERAL`` / ``REDUCED`` /
        ``SUPER_REDUCED`` tiers; ``None`` for ``ZERO`` and ``EXEMPT``
        (recargo de equivalencia does not apply to operations whose
        underlying IVA rate is zero or exempt).

    The tobacco-specific 1.75 % rate is not keyed by ``IvaRateKind``;
    callers that handle labores del tabaco read
    ``LIVA_ART_161_RECARGO.tabaco_rate`` directly.
    """
    rates = _load_rates()
    if rate_kind is IvaRateKind.GENERAL:
        return rates.general_rate
    if rate_kind is IvaRateKind.REDUCED:
        return rates.reducido_rate
    if rate_kind is IvaRateKind.SUPER_REDUCED:
        return rates.super_reducido_rate
    return None


__all__ = [
    "LivaArt161RecargoRates",
    "load_recargo_rates",
    "recargo_rate_for",
]

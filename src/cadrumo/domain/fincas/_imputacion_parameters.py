"""Registry-backed loader for LIRPF art. 85 imputación parameters.

The LIRPF art. 85 imputación-de-rentas-inmobiliarias rates and the
catastral-revision lookback window are no longer Python literals on
:mod:`domain.fincas._aggregates`. They live in
``registry/aeat/legal/irpf.toml`` under ``[parameters."lirpf-art-85:*"]``
entries with explicit BOE citations and review metadata, and the
rental aggregator imports them from this module.

The loader is deliberately small: it reads the TOML file once at
import time, validates the three expected parameter ids, and exposes
their values as a frozen pydantic record. The full registry parameter
loader at :mod:`domain.calculations.registry._loader` is scoped
to modelo revisions; LIRPF art. 85 imputación is a cross-cutting
LIRPF authority consumed by the rental package directly, so a
narrow loader here keeps the substrate boundary clean without
expanding the registry parameter lookup surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.resources import bundled_path
from .errors import FincaValidationError


class LirpfArt85ImputacionParameters(BaseModel):
    """Frozen record of the LIRPF art. 85 imputación parameters.

    Attributes:
        recent_revision_rate: 1,1 % rate applied when the property's
            valor catastral was revised, modified, or determined by a
            general collective valuation procedure in the period
            impositivo or in the ten preceding períodos impositivos
            (LIRPF art. 85.1 second paragraph).
        old_or_no_revision_rate: 2 % rate applied when no qualifying
            recent catastral revision exists (LIRPF art. 85.1 first
            paragraph).
        catastral_revision_lookback_years: ten-year window declared by
            "en los diez períodos impositivos anteriores" in LIRPF
            art. 85.1.
    """

    model_config = STRICT_FROZEN_CONFIG

    recent_revision_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    old_or_no_revision_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    catastral_revision_lookback_years: int = Field(gt=0)


_RECENT_REVISION_PARAM_ID: Final[str] = "lirpf-art-85:imputacion-rate-recent-revision"
_OLD_OR_NO_REVISION_PARAM_ID: Final[str] = "lirpf-art-85:imputacion-rate-old-or-no-revision"
_LOOKBACK_PARAM_ID: Final[str] = "lirpf-art-85:catastral-revision-lookback-years"


def _load_parameters() -> LirpfArt85ImputacionParameters:
    """Read the three LIRPF art. 85 parameters from the registry catalogue.

    Routes through ``cadrumo.domain.calculations.registry.load_registry_tree``
    so parameters land in the validated :class:`RegistryCatalogues.parameters`
    surface (single config-resolution path). The retired direct
    ``tomllib.load`` of ``registry/aeat/legal/irpf.toml`` is replaced —
    bypassing the loader was the same architectural drift pattern as
    direct ``os.environ`` reads.

    Returns:
        A :class:`LirpfArt85ImputacionParameters` record loaded from the
        registry catalogue.
    """
    # load_legal_parameters_only is the cycle-safe entry point — the full
    # load_registry_tree path pulls in registry._bindings which imports
    # from cadrumo.domain.iva (which itself imports rental upstream), so a
    # parameter-only loader is needed here to avoid import-time cycles.
    from cadrumo.domain.calculations.registry.loader import load_legal_parameters_only

    parameters = load_legal_parameters_only(bundled_path("registry", "aeat"))
    return _parameters_from_catalogue(parameters)


def _parameters_from_catalogue(
    parameters: Mapping[str, object],
) -> LirpfArt85ImputacionParameters:
    """Build the typed art. 85 parameter record from validated registry entries."""
    try:
        recent_raw = _parameter_value(parameters, _RECENT_REVISION_PARAM_ID)
        old_raw = _parameter_value(parameters, _OLD_OR_NO_REVISION_PARAM_ID)
        lookback_raw = _parameter_value(parameters, _LOOKBACK_PARAM_ID)
    except KeyError as exc:
        raise FincaValidationError(
            f"the IRPF legal-parameter catalogue is missing LIRPF art. 85 parameter {exc.args[0]!r}",
        ) from exc

    try:
        return LirpfArt85ImputacionParameters(
            recent_revision_rate=Decimal(recent_raw),
            old_or_no_revision_rate=Decimal(old_raw),
            catastral_revision_lookback_years=int(lookback_raw),
        )
    except (ArithmeticError, ValueError) as exc:
        raise FincaValidationError(f"invalid LIRPF art. 85 parameter value: {exc}") from exc


def _parameter_value(parameters: Mapping[str, object], parameter_id: str) -> str:
    """Return one legal-parameter value from the validated registry mapping."""
    value = getattr(parameters[parameter_id], "value", None)
    if not isinstance(value, str):
        raise FincaValidationError(f"LIRPF art. 85 parameter {parameter_id!r} has no string value")
    return value


def load_imputacion_parameters() -> LirpfArt85ImputacionParameters:
    """Public accessor for the LIRPF art. 85 imputation parameters.

    Reads the three art. 85 parameters from the bundled legal-
    parameter catalogue and returns the typed
    :class:`LirpfArt85ImputacionParameters` record. Callers that
    want the raw parameter mapping should use
    :func:`domain.calculations.registry.loader.load_legal_parameters_only`.
    """
    return _load_parameters()


__all__ = [
    "LirpfArt85ImputacionParameters",
    "load_imputacion_parameters",
]

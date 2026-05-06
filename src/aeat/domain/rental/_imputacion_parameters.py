"""Registry-backed loader for LIRPF art. 85 imputación parameters.

Closes the V-2 high-severity finding from the rate-shadow sweep:
the LIRPF art. 85 imputación-de-rentas-inmobiliarias rates and the
catastral-revision lookback window are no longer Python literals on
:mod:`aeat.domain.rental._aggregates`. They live in
``registry/aeat/legal/irpf.toml`` under ``[parameters."lirpf-art-85:*"]``
entries with explicit BOE citations and review metadata, and the
rental aggregator imports them from this module.

The loader is deliberately small: it reads the TOML file once at
import time, validates the three expected parameter ids, and exposes
their values as a frozen pydantic record. The full registry parameter
loader at :mod:`aeat.domain.calculations.registry._loader` is scoped
to modelo revisions; LIRPF art. 85 imputación is a cross-cutting
LIRPF authority consumed by the rental package directly, so a
narrow loader here keeps the substrate boundary clean without
expanding the registry parameter lookup surface.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ...core.paths import PROJECT_ROOT


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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    recent_revision_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    old_or_no_revision_rate: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    catastral_revision_lookback_years: int = Field(gt=0)


_PARAMETER_TABLE_PATH: Final[Path] = PROJECT_ROOT / "registry" / "aeat" / "legal" / "irpf.toml"

_RECENT_REVISION_PARAM_ID: Final[str] = "lirpf-art-85:imputacion-rate-recent-revision"
_OLD_OR_NO_REVISION_PARAM_ID: Final[str] = "lirpf-art-85:imputacion-rate-old-or-no-revision"
_LOOKBACK_PARAM_ID: Final[str] = "lirpf-art-85:catastral-revision-lookback-years"


def _load_parameters() -> LirpfArt85ImputacionParameters:
    """Read the three LIRPF art. 85 parameters from ``registry/aeat/legal/irpf.toml``.

    Raises:
        FileNotFoundError: If the parameter TOML is missing.
        KeyError: If any of the three expected parameter ids is absent.
        ValueError: If any value cannot be parsed as the expected type.
    """
    with _PARAMETER_TABLE_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    parameters = data.get("parameters", {})
    try:
        recent_raw = parameters[_RECENT_REVISION_PARAM_ID]["value"]
        old_raw = parameters[_OLD_OR_NO_REVISION_PARAM_ID]["value"]
        lookback_raw = parameters[_LOOKBACK_PARAM_ID]["value"]
    except KeyError as exc:
        raise KeyError(
            f"registry/aeat/legal/irpf.toml is missing LIRPF art. 85 parameter {exc.args[0]!r}"
        ) from exc

    return LirpfArt85ImputacionParameters(
        recent_revision_rate=Decimal(str(recent_raw)),
        old_or_no_revision_rate=Decimal(str(old_raw)),
        catastral_revision_lookback_years=int(lookback_raw),
    )


LIRPF_ART_85_IMPUTACION: Final[LirpfArt85ImputacionParameters] = _load_parameters()
"""Module-level frozen record loaded once at import time.

Consumers — currently :mod:`aeat.domain.rental._aggregates` —
reference ``LIRPF_ART_85_IMPUTACION.recent_revision_rate``,
``.old_or_no_revision_rate``, and ``.catastral_revision_lookback_years``
instead of carrying the values as Python literals.
"""


__all__ = [
    "LIRPF_ART_85_IMPUTACION",
    "LirpfArt85ImputacionParameters",
]

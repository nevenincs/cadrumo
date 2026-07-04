"""Fincas calculation-source readiness.

Declares whether the fincas domain may act as a calculation source that feeds
registry bindings. The fincas rendimiento and amortization aggregates are computed
in-domain (:mod:`domain.fincas`), but they are not yet persisted through the
canonical secure-storage revision boundary, so enrolling fincas as a live
calculation source would resolve bindings against non-canonical state. Until that
persistence is hardened, fincas readiness is NOT ready and the aggregation resolver
must refuse visibly (a blocked-readiness diagnostic) rather than resolve a silent
blank.

The readiness is deliberately a pure, context-independent domain fact: fincas is
unready regardless of the modelo or period being calculated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG

FINCAS_SOURCE_KIND = "fincas"


class FincasSourceReadiness(BaseModel):
    """Whether the fincas domain is ready to act as a calculation source."""

    model_config = STRICT_FROZEN_CONFIG

    ready: bool
    source_kind: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)


def fincas_source_readiness() -> FincasSourceReadiness:
    """Return the current fincas calculation-source readiness.

    Fincas is not yet a calculation source: its rendimiento and amortization
    aggregates are not persisted through the canonical secure-storage revision
    boundary, so a resolver enrolled today would read non-canonical state. The
    surface is provisioned but blocked until fincas persistence is hardened.

    Returns:
        A :class:`FincasSourceReadiness` with ``ready = False`` and the blocking
        reason, until fincas persistence is canonical.
    """
    return FincasSourceReadiness(
        ready=False,
        source_kind=FINCAS_SOURCE_KIND,
        reason=(
            "fincas is not yet a calculation source: its rendimiento and "
            "amortization aggregates are not persisted through the canonical "
            "secure-storage revision boundary"
        ),
    )


__all__ = ["FINCAS_SOURCE_KIND", "FincasSourceReadiness", "fincas_source_readiness"]

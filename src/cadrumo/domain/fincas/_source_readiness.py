"""Readiness facts for the fincas calculation source.

The strict-frozen record and context-independent readiness check describe only
whether finca state crosses the canonical secure-storage revision boundary.
They do not resolve calculation values, adapt or enroll a source, participate
in the source mesh, or emit diagnostics. The raw ``fincas`` source token is not
a :class:`~core.BindingSourceKind` member.

See Also:
    :mod:`~domain.fincas`
        Public domain facade for the finca aggregates whose persistence is not
        yet canonical calculation-source state.
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
    """Return the context-independent fincas-source readiness fact.

    The result remains not ready because the rendimiento and amortization
    aggregates are not persisted through the canonical secure-storage revision
    boundary.

    Returns:
        A :class:`~domain.fincas.FincasSourceReadiness` with ``ready = False``
        plus the raw source token and reason.
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

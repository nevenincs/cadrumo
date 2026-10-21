"""Typed logging ``extra`` payloads.

Kept apart from :mod:`cadrumo.core.logging`, which every process imports before
it has parsed a command: the scrubbing filters and logger factory there must not
cost a pydantic import, while only service-layer log-field helpers build these.
"""

from __future__ import annotations

from pydantic import ConfigDict, RootModel

LogExtraValue = str | int | float | bool | None
"""Closed union of stdlib-loggable scalar types accepted by :class:`LogExtra`."""


class LogExtra(RootModel[dict[str, LogExtraValue]]):
    """Typed logging ``extra`` payload restricted to flat loggable scalars.

    Upgrades the historical ``Mapping[str, object]`` return annotation on
    service-layer ``as_extra()`` log-field helpers (e.g.
    :class:`~cadrumo.application.aggregation.service.PerModeloAggregationLogFields`,
    :class:`~cadrumo.application.operator_surface.models.OperatorSurfaceContract`'s
    ``log_fields``): every current emitter only ever writes flat, non-secret
    scalars into :meth:`logging.Logger.debug`'s ``extra=`` mapping, so
    accepting bare ``object`` values understated the real contract. A future
    field that accidentally carried a nested mapping, a Decimal, or another
    non-serialisable value now fails loudly at construction with a
    :class:`pydantic.ValidationError` naming the offending field, instead of
    surfacing later as a JSONL-sink serialisation surprise.

    Use :meth:`for_logging` to materialise the plain ``dict`` the stdlib
    ``logging`` module's ``extra=`` parameter expects; the model itself is not
    iterable the way :meth:`logging.Logger.makeRecord` requires.
    """

    # NOT the canonical STRICT_FROZEN_CONFIG: this is a RootModel, and pydantic
    # refuses `extra` on one outright, while the canonical carries
    # extra="forbid". A constraint-shape divergence, not a weaker config.
    model_config = ConfigDict(frozen=True)

    def for_logging(self) -> dict[str, LogExtraValue]:
        """Return the payload as the plain ``dict`` ``logging`` extras expect."""
        return dict(self.root)

"""Shared lossless timing scalars for diagnostics report snapshots."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .operations.public_scalar import PublicDecimal

if TYPE_CHECKING:
    from .diagnostics_run_report_contracts import DiagnosticsLatencyPercentilesSnapshot


class _TimingSnapshot(BaseModel):
    """Canonical timing facts with the shared lossless public decimal scalar."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    runs: Annotated[int, Field(ge=0)]
    succeeded: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: PublicDecimal | None = None


def _public_timing_values(value: BaseModel, *, exclude: set[str] | None = None) -> dict[str, object]:
    """Copy only the decimal representation; preserve every other service fact."""
    values = cast("dict[str, object]", value.model_dump(exclude=exclude))
    mean = values["mean_duration_ms"]
    if isinstance(mean, Decimal):
        values["mean_duration_ms"] = PublicDecimal(decimal=str(mean))
    return values


def _native_timing_values(
    value: _TimingSnapshot | DiagnosticsLatencyPercentilesSnapshot, *, exclude: set[str] | None = None
) -> dict[str, object]:
    """Restore the shared public scalar without calculating timing metrics."""
    excluded = exclude | {"mean_duration_ms"} if exclude is not None else {"mean_duration_ms"}
    values = cast("dict[str, object]", value.model_dump(exclude=excluded))
    mean = value.mean_duration_ms
    values["mean_duration_ms"] = Decimal(mean.decimal) if mean is not None else None
    return values

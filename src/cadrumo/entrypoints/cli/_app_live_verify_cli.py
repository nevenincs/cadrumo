"""Behavior handlers for live NIF verification commands.

The ``list`` / ``view`` / ``latest`` commands read bucket-local
:class:`VerifyObservation` rows persisted by :class:`VerifyService`. The
``nif-iva`` and ``tgvi`` commands perform read-only AEAT checks, require
live-read access, and then append an audit observation; none of these commands
submits, registers, or mutates AEAT state.
"""

from __future__ import annotations

from typing import TypedDict

import typer

from ...application.live.verify import (
    VerifyObservation,
    VerifySurface,
)
from ...application.live.verify_capture_operation import VerifyCapturePublicResultV1
from ...application.live.verify_read_contracts import VerifyObservationSummaryPublicV1
from ...core.i18n.render import tr
from ...core.identity_check_verdict import IdentityCheckVerdict, IdentityCheckVerdictValue
from .common import emit_envelope
from .runtime_verify_capture import read_verify_capture_for_cli
from .runtime_verify_read import read_verify_latest_for_cli, read_verify_list_for_cli, read_verify_view_for_cli


class _VerifyRow(TypedDict):
    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


def _expected(value: str | None) -> IdentityCheckVerdictValue | None:
    if value is None:
        return None
    if value == IdentityCheckVerdict.VALID:
        return IdentityCheckVerdict.VALID
    if value == IdentityCheckVerdict.INVALID:
        return IdentityCheckVerdict.INVALID
    if value == IdentityCheckVerdict.UNKNOWN:
        return IdentityCheckVerdict.UNKNOWN
    raise typer.BadParameter(tr("cli.app.live.verify.expected_values_error"))


def _verify_row(
    observation: VerifyObservation | VerifyCapturePublicResultV1 | VerifyObservationSummaryPublicV1,
) -> _VerifyRow:
    """Project a stored verify observation into the shared CLI row shape."""
    return _VerifyRow(
        observation_id=observation.observation_id,
        surface=observation.surface.value,
        nif=observation.nif,
        verdict=observation.verdict,
        expected=observation.expected,
        matched_expectation=observation.matched_expectation,
        checked_at=observation.checked_at.isoformat(),
    )


def verify_list(
    ctx: typer.Context,
    surface: VerifySurface | None = None,
    nif: str | None = None,
) -> None:
    """List persisted NIF verification observations.

    Optional ``--surface`` filtering maps to :class:`VerifySurface`; rows are
    stored observations returned by :class:`VerifyService`, not fresh live
    checks, and are emitted through :class:`VerifyListResult`.
    """
    from ._app_live_verify_payloads import VerifyListResult, VerifyObservationSummaryPayload

    projection = read_verify_list_for_cli(ctx, surface=surface, nif=nif).projection
    bucket_id = projection.bucket_id
    rows = projection.rows
    result = VerifyListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[VerifyObservationSummaryPayload(**_verify_row(r)) for r in rows],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.observation_id}\t{r.surface.value}\t{r.nif}\t{r.verdict}\t{r.checked_at.isoformat()}")
    emit_envelope(ctx, command="app.live.verify.list", result=result, lines=lines)


def verify_show(
    ctx: typer.Context,
    observation_id: str,
) -> None:
    """Show one persisted NIF verification observation by id prefix.

    The lookup resolves a stored :class:`VerifyObservation` through
    :class:`VerifyService` and emits :class:`VerifyViewResult` with the same row
    shape as ``aeat app live verify list``.
    """
    from ._app_live_verify_payloads import VerifyViewResult

    record = read_verify_view_for_cli(ctx, observation_id=observation_id).projection
    bucket_id = record.bucket_id
    result = VerifyViewResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    emit_envelope(ctx, command="app.live.verify.view", result=result, lines=lines)


def verify_latest(
    ctx: typer.Context,
    surface: VerifySurface,
    nif: str,
) -> None:
    """Show the most recent verify observation for a surface/NIF pair.

    The command validates ``surface`` as a :class:`VerifySurface` and reads the
    latest persisted observation through :class:`VerifyService`. A missing match
    emits the stable :class:`VerifyLatestResult` shape with
    ``observation_id=None``.
    """
    from ._app_live_verify_payloads import VerifyLatestResult

    projection = read_verify_latest_for_cli(ctx, surface=surface, nif=nif).projection
    bucket_id = projection.bucket_id
    if projection.observation_id is None:
        empty = VerifyLatestResult(
            bucket_id=bucket_id,
            surface=surface,
            nif=nif,
            observation_id=None,
        )
        emit_envelope(
            ctx,
            command="app.live.verify.latest",
            result=empty,
            lines=[
                f"bucket\t{bucket_id}",
                f"surface\t{surface}",
                f"nif\t{nif}",
                "observation_id\t-",
            ],
        )
        return
    if projection.verdict is None or projection.checked_at is None:
        raise ValueError("nonempty latest verify projection lacks its required row fields")
    record = VerifyObservationSummaryPublicV1(
        observation_id=projection.observation_id,
        surface=projection.surface,
        nif=projection.nif,
        verdict=projection.verdict,
        expected=projection.expected,
        matched_expectation=projection.matched_expectation,
        checked_at=projection.checked_at,
    )
    result = VerifyLatestResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    emit_envelope(ctx, command="app.live.verify.latest", result=result, lines=lines)


def verify_nif_iva(
    ctx: typer.Context,
    nif: str,
    expected: str | None = None,
) -> None:
    """Live-check one intra-community NIF-IVA and persist the observation.

    The command uses the AEAT IXVI read surface after the live-read access gate,
    records the verdict through :class:`VerifyService`, and returns
    :class:`VerifyNifIvaResult`.
    """
    from ._app_live_verify_payloads import VerifyNifIvaResult

    record = read_verify_capture_for_cli(
        ctx,
        surface=VerifySurface.NIF_IVA,
        nif=nif,
        expected=_expected(expected),
    )
    bucket_id = record.bucket_id
    result = VerifyNifIvaResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    emit_envelope(ctx, command="app.live.verify.nif_iva", result=result, lines=lines)


def verify_tgvi(
    ctx: typer.Context,
    nif: str,
    expected: str | None = None,
) -> None:
    """Live-check one Spanish NIF's ROI/VIES registration and persist it.

    The command uses the AEAT TGVI/GROI read surface after the live-read access
    gate, records the verdict through :class:`VerifyService`, and returns
    :class:`VerifyTgviResult`.
    """
    from ._app_live_verify_payloads import VerifyTgviResult

    record = read_verify_capture_for_cli(
        ctx,
        surface=VerifySurface.TGVI,
        nif=nif,
        expected=_expected(expected),
    )
    bucket_id = record.bucket_id
    result = VerifyTgviResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    emit_envelope(ctx, command="app.live.verify.tgvi", result=result, lines=lines)


__all__ = ["verify_latest", "verify_list", "verify_nif_iva", "verify_show", "verify_tgvi"]

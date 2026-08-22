"""Typer registration for live NIF verification commands.

The ``list`` / ``view`` / ``latest`` commands read bucket-local
:class:`VerifyObservation` rows persisted by :class:`VerifyService`. The
``nif-iva`` and ``tgvi`` commands perform read-only AEAT checks, require
live-read access, and then append an audit observation; none of these commands
submits, registers, or mutates AEAT state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TypedDict

import typer

from ...application.live import VerifySurface, VerifyVerdict
from ...core.i18n import tr
from ...core.identity import tax_id_identity_token
from ...core.time import now
from ._app_execution_policies import ENCRYPTED_READ, LIVE_PROFILE_WRITE, declare_metadata_group
from ._app_live_auth_preflight import resolve_active_bucket
from ._command_policy import command_execution_policy
from ._common import _emit_envelope

_active_bucket_id: Callable[[], str] | None = None
_verify_expected: Callable[[str | None], VerifyVerdict | None] | None = None


class _VerifyRow(TypedDict):
    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


verify_app = typer.Typer(
    name="verify",
    help=tr("cli.app.live.verify.app_help", default="NIF verify audit log (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
declare_metadata_group(verify_app)


def register_verify_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    verify_expected: Callable[[str | None], VerifyVerdict | None],
) -> None:
    """Mount live verify commands on the live app."""
    global _active_bucket_id
    global _verify_expected

    _active_bucket_id = active_bucket_id
    _verify_expected = verify_expected
    app.add_typer(verify_app, name="verify")


def _bucket_id() -> str:
    return resolve_active_bucket(_active_bucket_id, family="verify")


def _expected(value: str | None) -> VerifyVerdict | None:
    if _verify_expected is None:
        raise RuntimeError("live verify commands were not registered")
    return _verify_expected(value)


def _verify_row(observation) -> _VerifyRow:
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


@verify_app.command(
    "list",
    help=tr(
        "cli.app.live.verify.list_help",
        default="List persisted verify observations (optionally filter by surface or NIF).",
    ),
)
def verify_list(
    ctx: typer.Context,
    surface: Annotated[
        VerifySurface | None,
        typer.Option(
            "--surface",
            help=tr(
                "cli.app.live.verify.surface_help",
                default="Filter to one surface: nif_iva or tgvi.",
            ),
        ),
    ] = None,
    nif: Annotated[
        str | None,
        typer.Option("--nif", help=tr("cli.app.live.verify.nif_help", default="Filter to one NIF.")),
    ] = None,
) -> None:
    """List persisted NIF verification observations.

    Optional ``--surface`` filtering maps to :class:`VerifySurface`; rows are
    stored observations returned by :class:`VerifyService`, not fresh live
    checks, and are emitted through :class:`VerifyListResult`.
    """
    from ...application.live import VerifyService
    from ._app_live_payloads import VerifyListResult, VerifyObservationSummaryPayload

    bucket_id = _bucket_id()
    rows = VerifyService().list_observations(
        bucket_id=bucket_id,
        surface=surface,
        nif=nif,
    )
    result = VerifyListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[VerifyObservationSummaryPayload(**_verify_row(r)) for r in rows],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.observation_id}\t{r.surface.value}\t{r.nif}\t{r.verdict}\t{r.checked_at.isoformat()}")
    _emit_envelope(ctx, command="app.live.verify.list", result=result, lines=lines)


@verify_app.command(
    "view",
    help=tr("cli.app.live.verify.view_help", default="View one persisted verify observation."),
)
def verify_show(
    ctx: typer.Context,
    observation_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.verify.observation_id_help",
                default="Observation id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    """Show one persisted NIF verification observation by id prefix.

    The lookup resolves a stored :class:`VerifyObservation` through
    :class:`VerifyService` and emits :class:`VerifyViewResult` with the same row
    shape as ``aeat app live verify list``.
    """
    from ...application.live import VerifyService
    from ._app_live_payloads import VerifyViewResult

    bucket_id = _bucket_id()
    record = VerifyService().show(bucket_id=bucket_id, observation_id=observation_id)
    result = VerifyViewResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit_envelope(ctx, command="app.live.verify.view", result=result, lines=lines)


@verify_app.command(
    "latest",
    help=tr(
        "cli.app.live.verify.latest_help",
        default="Show the most recent observation for a (surface, NIF) pair.",
    ),
)
def verify_latest(
    ctx: typer.Context,
    surface: Annotated[
        VerifySurface,
        typer.Option(
            "--surface",
            help=tr(
                "cli.app.live.verify.latest_surface_help",
                default="Verify surface: nif_iva or tgvi.",
            ),
        ),
    ],
    nif: Annotated[
        str,
        typer.Option("--nif", help=tr("cli.app.live.verify.latest_nif_help", default="NIF to look up.")),
    ],
) -> None:
    """Show the most recent verify observation for a surface/NIF pair.

    The command validates ``surface`` as a :class:`VerifySurface` and reads the
    latest persisted observation through :class:`VerifyService`. A missing match
    emits the stable :class:`VerifyLatestResult` shape with
    ``observation_id=None``.
    """
    from ...application.live import VerifyService
    from ._app_live_payloads import VerifyLatestResult

    bucket_id = _bucket_id()
    record = VerifyService().latest_for_nif(
        bucket_id=bucket_id,
        surface=surface,
        nif=nif,
    )
    if record is None:
        empty = VerifyLatestResult(
            bucket_id=bucket_id,
            surface=surface,
            nif=nif,
            observation_id=None,
        )
        _emit_envelope(
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
    result = VerifyLatestResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit_envelope(ctx, command="app.live.verify.latest", result=result, lines=lines)


@verify_app.command(
    "nif-iva",
    help=tr(
        "cli.app.live.verify.nif_iva_help",
        default="Live-check one intra-community NIF-IVA via AEAT IXVI and persist the observation.",
    ),
)
def verify_nif_iva(
    ctx: typer.Context,
    nif: Annotated[
        str,
        typer.Argument(help=tr("cli.app.live.verify.nif_iva_arg_help", default="NIF-IVA value (e.g. ESB12345678).")),
    ],
    expected: Annotated[
        str | None,
        typer.Option(
            "--expected",
            help=tr("cli.app.live.verify.expected_help", default="Optional expected verdict (valid|invalid|unknown)."),
        ),
    ] = None,
) -> None:
    """Live-check one intra-community NIF-IVA and persist the observation.

    The command uses the AEAT IXVI read surface after the live-read access gate,
    records the verdict through :class:`VerifyService`, and returns
    :class:`VerifyNifIvaResult`.
    """
    from ...adapters.outbound.aeat.sede import NifIvaCheckSedeDriver
    from ...application.live import VerifyService
    from ...core.access_gate import AeatAccessGate
    from ...core.config import load_settings
    from ._app_live_payloads import VerifyNifIvaResult

    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    nif_key = tax_id_identity_token(nif)
    expected_verdict = _expected(expected)
    driver = NifIvaCheckSedeDriver(settings=settings)
    result = driver.collect(b"", expected={nif_key: (expected_verdict or "unknown")})
    if not result.observations:
        raise typer.BadParameter(tr("cli.app.live.verify.no_observation_for_nif", nif=nif))
    observation = result.observations[0]
    bucket_id = _bucket_id()
    record = VerifyService(settings=settings).record(
        bucket_id=bucket_id,
        surface=VerifySurface.NIF_IVA,
        nif=observation.nif,
        verdict=observation.verdict,
        checked_at=now(),
        expected=expected_verdict,
        raw_evidence_locator=observation.raw_evidence_locator,
    )
    result = VerifyNifIvaResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit_envelope(ctx, command="app.live.verify.nif_iva", result=result, lines=lines)


@verify_app.command(
    "tgvi",
    help=tr(
        "cli.app.live.verify.tgvi_help",
        default="Live-check one Spanish NIF's ROI/VIES (GROI) registration and persist the observation.",
    ),
)
def verify_tgvi(
    ctx: typer.Context,
    nif: Annotated[
        str,
        typer.Argument(help=tr("cli.app.live.verify.tgvi_arg_help", default="Spanish NIF/NIE to check.")),
    ],
    expected: Annotated[
        str | None,
        typer.Option(
            "--expected",
            help=tr("cli.app.live.verify.expected_help", default="Optional expected verdict (valid|invalid|unknown)."),
        ),
    ] = None,
) -> None:
    """Live-check one Spanish NIF's ROI/VIES registration and persist it.

    The command uses the AEAT TGVI/GROI read surface after the live-read access
    gate, records the verdict through :class:`VerifyService`, and returns
    :class:`VerifyTgviResult`.
    """
    from ...adapters.outbound.aeat.sede import GroiSedeDriver
    from ...application.live import VerifyService
    from ...core.access_gate import AeatAccessGate
    from ...core.config import load_settings
    from ._app_live_payloads import VerifyTgviResult

    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    nif_key = tax_id_identity_token(nif)
    expected_verdict = _expected(expected)
    driver = GroiSedeDriver(settings=settings)
    result = driver.collect(b"", expected={nif_key: (expected_verdict or "unknown")})
    if not result.observations:
        raise typer.BadParameter(tr("cli.app.live.verify.no_observation_for_nif", nif=nif))
    observation = result.observations[0]
    bucket_id = _bucket_id()
    record = VerifyService(settings=settings).record(
        bucket_id=bucket_id,
        surface=VerifySurface.TGVI,
        nif=observation.nif,
        verdict=observation.verdict,
        checked_at=now(),
        expected=expected_verdict,
        raw_evidence_locator=observation.raw_evidence_locator,
    )
    result = VerifyTgviResult(bucket_id=bucket_id, **_verify_row(record))
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit_envelope(ctx, command="app.live.verify.tgvi", result=result, lines=lines)


for _callback in (verify_list, verify_show, verify_latest):
    command_execution_policy(ENCRYPTED_READ)(_callback)
for _callback in (verify_nif_iva, verify_tgvi):
    command_execution_policy(LIVE_PROFILE_WRITE)(_callback)


__all__ = ["register_verify_commands", "verify_app"]

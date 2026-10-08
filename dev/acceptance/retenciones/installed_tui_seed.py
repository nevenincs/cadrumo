"""Seed withholding continuation inputs through fresh installed public CLI processes."""

from __future__ import annotations

from dataclasses import dataclass

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .cli_annual import _capture_annual_source_allocations
from .cli_annual_source import _annual_source_revision, _attest_annual_no_activity_periods
from .cli_contracts import _ACTOR, RetencionesInstalledCliError
from .cli_observations import _require_result, _required_text
from .cli_profile import _create_withholding_profile
from .scenario import SUPPORTED_YEAR, InstalledAnnualCliSlice, build_installed_annual_cli_slices


@dataclass(frozen=True, slots=True)
class WithholdingWork:
    """A publicly created work unit and its scenario-owned natural coordinates."""

    work_unit_id: str
    modelo: str
    year: int
    period: str
    revision: str
    annual_slice_id: str


def seed_withholding_work(cli: InstalledCli, *, year: int) -> tuple[WithholdingWork, ...]:
    """Capture both scenarios and create work without calculating or filing it.

    Empty Modelo 111 quarters keep their public no-retenciones attestation;
    they never become invented zero filings. Modelo 115's separately attested
    zero quarters remain source work for the annual relation.
    """
    if year != SUPPORTED_YEAR:
        raise ValueError("the withholding continuation has independent oracles only for the supported year")
    try:
        _create_withholding_profile(cli, year=year)
    except RetencionesInstalledCliError as error:
        cause = error.__cause__
        if isinstance(cause, InstalledCliError):
            stage = error.stage
            if cause.commands and cause.commands[-1].command == "config profile complete-setup":
                stage = "profile_complete_setup"
            raise RetencionesInstalledCliError(
                stage=stage, diagnostic_code=cause.diagnostic_code, commands=tuple(cli.commands)
            ) from cause
        raise RetencionesInstalledCliError(
            stage=error.stage, diagnostic_code=error.diagnostic_code, commands=tuple(cli.commands)
        ) from error
    sources: list[WithholdingWork] = []
    annuals: list[WithholdingWork] = []
    for slice_ in build_installed_annual_cli_slices(year):
        _, captures = _capture_annual_source_allocations(cli, slice_, year)
        attestations = _attest_annual_no_activity_periods(
            cli=cli, slice_=slice_, captures_by_period=captures, year=year
        )
        source_revision = _annual_source_revision(slice_, stage="tui_source_preflight")
        for source in slice_.source_periods:
            if slice_.source_modelo == "111" and not captures.get(source.period):
                if f"{year}:{source.period}" not in attestations:
                    raise ValueError("an empty Modelo 111 source lacks its explicit no-duty attestation")
                continue
            sources.append(
                _create_work(
                    cli,
                    slice_,
                    modelo=slice_.source_modelo,
                    year=year,
                    period=source.period,
                    revision=source_revision,
                )
            )
        annuals.append(
            _create_work(cli, slice_, modelo=slice_.modelo, year=year, period=slice_.period, revision=slice_.revision)
        )
    # All quarterly local records must exist before an annual calculation reads them.
    return tuple((*sources, *annuals))


def _create_work(
    cli: InstalledCli,
    slice_: InstalledAnnualCliSlice,
    *,
    modelo: str,
    year: int,
    period: str,
    revision: str,
) -> WithholdingWork:
    result = _require_result(
        cli,
        (
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            str(year),
            "--period",
            period,
            "--revision",
            revision,
            "--by",
            _ACTOR,
        ),
        stage=f"tui_seed:{modelo}:{period}:create",
    )
    return WithholdingWork(
        work_unit_id=_required_text(result, key="work_unit_id", stage="tui_seed:work_identity"),
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        annual_slice_id=slice_.slice_id,
    )

"""Typer sub-app for the ``aeat modelos`` CLI surface.

Exposes four commands backed by :data:`aeat.models.MODELO_REGISTRY`:

- ``aeat modelos list`` — filter and list catalogue entries.
- ``aeat modelos show`` — dump a single entry.
- ``aeat modelos applicable-to`` — list modelos for a profile.
- ``aeat modelos year-plan`` — resolve filing windows through the
  deadline engine.

Every command supports a ``--json`` flag that emits JSON via
:meth:`pydantic.BaseModel.model_dump` instead of a rich table.
"""

from __future__ import annotations

import contextlib
import json
import sys

import typer
from rich.console import Console
from rich.table import Table

from ..deadlines import AutonomoProfile, IVARegime
from ._categories import ModeloCadence, ModeloCategory, TaxpayerProfile
from ._errors import UnknownModeloError
from ._metadata import ModeloMetadata
from ._registry import (
    MODELO_REGISTRY,
    get_modelo,
    modelos_for_profile,
    year_plan,
)

_CONSOLE = Console()


def _ensure_utf8_streams() -> None:
    """Reconfigure stdout/stderr to UTF-8 for the current process.

    The modelo catalogue carries Spanish and Hungarian characters
    (á, é, ő, …) that Windows legacy code-page stdout (cp1252) cannot
    encode. Calling this from the Typer callback scopes the side effect
    to ``aeat modelos`` invocations instead of every import of this
    module.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


app = typer.Typer(
    name="modelos",
    help="AEAT modelo inventory and applicability helpers.",
    no_args_is_help=True,
)


@app.callback()
def _main_callback() -> None:
    """Initialise the ``aeat modelos`` sub-app for the current invocation."""
    _ensure_utf8_streams()


def _entries_sorted() -> tuple[ModeloMetadata, ...]:
    return tuple(sorted(MODELO_REGISTRY.values(), key=lambda m: m.code.value))


def _emit_entries(entries: tuple[ModeloMetadata, ...], json_out: bool) -> None:
    if json_out:
        payload = [e.model_dump(mode="json") for e in entries]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    table = Table(title="aeat modelos", header_style="bold")
    table.add_column("code", style="cyan")
    table.add_column("category")
    table.add_column("cadence")
    table.add_column("name (es)")
    for entry in entries:
        table.add_row(
            entry.code.value,
            entry.category.value,
            entry.cadence.value,
            entry.display_label.get("es", ""),  # type: ignore[misc]
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(entries)} entry(ies)[/dim]")


@app.command(name="list", help="List modelo catalogue entries with optional filters.")
def list_command(
    category: ModeloCategory | None = typer.Option(None, "--category", help="Filter by modelo category."),
    cadence: ModeloCadence | None = typer.Option(None, "--cadence", help="Filter by filing cadence."),
    profile: TaxpayerProfile | None = typer.Option(
        None,
        "--profile",
        help="Filter by taxpayer profile (mandatory OR optional applicability).",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List catalogue entries, optionally filtered."""
    entries = _entries_sorted()
    if category is not None:
        entries = tuple(e for e in entries if e.category is category)
    if cadence is not None:
        entries = tuple(e for e in entries if e.cadence is cadence)
    if profile is not None:
        entries = tuple(
            e
            for e in entries
            if profile in e.applicability.mandatory_profiles or profile in e.applicability.optional_profiles
        )
    _emit_entries(entries, json_out)


@app.command(name="show", help="Show a single modelo catalogue entry.")
def show_command(
    code: str = typer.Argument(..., help="Three-character modelo code, e.g. '303'."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Resolve a single modelo and print its metadata."""
    try:
        metadata = get_modelo(code)
    except UnknownModeloError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    _emit_entries((metadata,), json_out=False)
    _CONSOLE.print(f"[dim]caps_into:[/dim] {metadata.caps_into.value if metadata.caps_into else '-'}")
    submission = metadata.submission_portal.value if metadata.submission_portal else "-"
    _CONSOLE.print(f"[dim]submission portal:[/dim] {submission}")


@app.command(
    name="applicable-to",
    help="List every modelo applicable to a taxpayer profile.",
)
def applicable_to_command(
    profile: TaxpayerProfile = typer.Argument(..., help="Taxpayer profile to query."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List modelos whose applicability matches ``profile``."""
    entries = modelos_for_profile(profile)
    _emit_entries(entries, json_out)


def _profiles_from_autonomo(profile: AutonomoProfile) -> frozenset[TaxpayerProfile]:
    """Infer every :class:`TaxpayerProfile` matching an :class:`AutonomoProfile`.

    An autónomo may match multiple archetypes at once (e.g. has employees
    AND performs intra-EU operations); a single-profile hierarchy would
    silently discard obligations from the non-selected traits. The CLI
    uses the returned set via intersection against the registry's
    applicability matrix so every matching obligation is retained.
    """
    matched: set[TaxpayerProfile] = set()
    if profile.bienes_extranjero_above_threshold:
        matched.add(TaxpayerProfile.AUTONOMO_ED_BIENES_EXTRANJERO)
    if profile.does_intracomunitario:
        matched.add(TaxpayerProfile.AUTONOMO_ED_UE)
    if profile.pays_rent_with_retencion:
        matched.add(TaxpayerProfile.AUTONOMO_ED_CON_ALQUILER)
    if profile.has_employees:
        matched.add(TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS)
    if profile.pays_professionals_with_retencion:
        matched.add(TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES)
    if not matched:
        matched.add(TaxpayerProfile.AUTONOMO_ED_SOLO)
    return frozenset(matched)


@app.command(name="year-plan", help="Compute filing obligations for a year + profile.")
def year_plan_command(
    year: int = typer.Argument(..., help="Fiscal year to compute the plan for."),
    tax_id: str = typer.Option(..., "--tax-id", help="NIF / NIE identifier."),
    iva_regime: IVARegime = typer.Option(
        IVARegime.GENERAL, "--iva-regime", help="IVA regime the autónomo files under."
    ),
    has_employees: bool = typer.Option(False, "--has-employees/--no-has-employees"),
    pays_professionals_with_retencion: bool = typer.Option(
        False,
        "--pays-professionals/--no-pays-professionals",
        help="Pays professional fees subject to retención.",
    ),
    professional_income_withholding_ge_70pct: bool = typer.Option(
        False,
        "--professional-income-withholding-ge-70pct/--no-professional-income-withholding-ge-70pct",
        help="At least 70% of prior-year professional income was already subject to withholding.",
    ),
    pays_rent_with_retencion: bool = typer.Option(
        False, "--pays-rent/--no-pays-rent", help="Pays local alquiler con retención."
    ),
    does_intracomunitario: bool = typer.Option(False, "--intracomunitario/--no-intracomunitario"),
    third_party_transactions_above_347_threshold: bool = typer.Option(
        False,
        "--third-party-threshold-347/--no-third-party-threshold-347",
        help="Exceeded the modelo 347 annual threshold with any third party.",
    ),
    bienes_extranjero_above_threshold: bool = typer.Option(
        False,
        "--bienes-extranjero/--no-bienes-extranjero",
        help="Holds bienes en el extranjero above the threshold.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Compute the filing :class:`aeat.deadlines.Schedule` for a profile."""
    profile = AutonomoProfile(
        tax_id=tax_id,
        iva_regime=iva_regime,
        has_employees=has_employees,
        pays_professionals_with_retencion=pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=professional_income_withholding_ge_70pct,
        pays_rent_with_retencion=pays_rent_with_retencion,
        does_intracomunitario=does_intracomunitario,
        third_party_transactions_above_347_threshold=third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=bienes_extranjero_above_threshold,
    )
    schedule = year_plan(year, profile)
    taxpayers = _profiles_from_autonomo(profile)
    filtered = []
    for obligation in schedule.obligations:
        try:
            metadata = get_modelo(obligation.modelo)
        except UnknownModeloError:
            continue
        if not taxpayers.isdisjoint(metadata.applicability.mandatory_profiles) or not taxpayers.isdisjoint(
            metadata.applicability.optional_profiles
        ):
            filtered.append(obligation)
    if json_out:
        payload = [o.model_dump(mode="json") for o in filtered]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    profile_label = ", ".join(sorted(p.value for p in taxpayers))
    table = Table(title=f"year plan {year} — {profile_label}", header_style="bold")
    table.add_column("modelo", style="cyan")
    table.add_column("period")
    table.add_column("opens_on")
    table.add_column("closes_on")
    table.add_column("status")
    for obligation in filtered:
        table.add_row(
            obligation.modelo,
            obligation.period,
            obligation.opens_on.isoformat(),
            obligation.closes_on.isoformat(),
            obligation.status.value,
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(filtered)} obligation(s)[/dim]")

"""`aeat financial profile` command group for Kent's usage ratios (#259)."""

from __future__ import annotations

import difflib
from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from ...config import load_settings
from ...financial.categories import CATEGORY_PROFILES_2025, SpendingCategory
from ...financial.usage_ratios import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
)
from ._profile_aliases import FAMILY_ALIASES

_MISSING = "(none)"
_ALIAS_LIST = ", ".join(sorted(FAMILY_ALIASES))
_SET_RATIO_KEY_HELP = f"Category id (e.g. suministros_home_office_luz) or family alias ({_ALIAS_LIST})."
_UNSET_RATIO_KEY_HELP = f"Category id or family alias ({_ALIAS_LIST})."

app = typer.Typer(
    name="profile",
    no_args_is_help=True,
    help="Kent's financial profile: per-category usage ratios (#259).",
)

ratios_app = typer.Typer(
    name="ratios",
    no_args_is_help=True,
    help="List Kent's persisted usage ratios.",
)
app.add_typer(ratios_app, name="ratios")


@ratios_app.command(name="list", help="List Kent's configured ratios alongside statutory defaults.")
def list_cmd() -> None:
    """Print every persisted ratio next to the statutory default."""
    profile = _load_profile()
    if not profile.ratios:
        typer.echo("No usage ratios configured.")
        return
    typer.echo("category\tkind\tuser_ratio\tstatutory_default")
    for category in sorted(profile.ratios, key=lambda c: c.value):
        rule = CATEGORY_PROFILES_2025[category].proportionality
        default_raw = rule.default_ratio
        default_str = _format_decimal(default_raw) if default_raw is not None else _MISSING
        typer.echo(
            "\t".join(
                [
                    category.value,
                    rule.kind.value,
                    _format_decimal(profile.ratios[category]),
                    default_str,
                ]
            )
        )


@app.command(name="set-ratio", help="Set Kent's usage ratio for one category or family alias.")
def set_ratio_cmd(
    key: str = typer.Argument(..., help=_SET_RATIO_KEY_HELP),
    value: str = typer.Argument(..., help="Ratio in [0, 1] as a decimal, e.g. 0.21."),
) -> None:
    """Persist one or more usage ratios for the resolved key."""
    categories = _resolve_key(key)
    ratio = _parse_ratio(value)
    profile = _load_profile()
    updated = profile
    for category in categories:
        try:
            updated = updated.with_ratio(category, ratio)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
    _save_profile(updated)
    for category in categories:
        typer.echo(f"set {category.value} = {_format_decimal(ratio)}")


@app.command(name="unset-ratio", help="Remove Kent's usage ratio for one category or family alias.")
def unset_ratio_cmd(
    key: str = typer.Argument(..., help=_UNSET_RATIO_KEY_HELP),
) -> None:
    """Remove persisted ratios for the resolved key."""
    categories = _resolve_key(key)
    profile = _load_profile()
    updated = profile
    removed: list[SpendingCategory] = []
    for category in categories:
        if category in updated.ratios:
            updated = updated.without_ratio(category)
            removed.append(category)
    if not removed:
        typer.echo(f"no user ratio set for {key}")
        return
    _save_profile(updated)
    for category in removed:
        typer.echo(f"unset {category.value}")


def _resolve_key(raw: str) -> tuple[SpendingCategory, ...]:
    """Expand a family alias or validate a single category id."""
    alias_members = FAMILY_ALIASES.get(raw)
    if alias_members is not None:
        return alias_members
    try:
        category = SpendingCategory(raw)
    except ValueError as exc:
        typer.echo(_format_unknown_key_hint(raw), err=True)
        raise typer.Exit(code=2) from exc
    if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
        eligible = ", ".join(sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES))
        typer.echo(
            f"{category.value!r} does not accept a usage ratio; eligible categories: {eligible}",
            err=True,
        )
        raise typer.Exit(code=2)
    return (category,)


def _format_unknown_key_hint(raw: str) -> str:
    """Build an actionable error for an unrecognised key.

    Surfaces:
      * the offending input,
      * close-match suggestions drawn from aliases + eligible category ids,
      * the full alias list and the 12 eligible category ids.
    """
    aliases = sorted(FAMILY_ALIASES)
    eligible = sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES)
    candidates = aliases + eligible
    near_matches = difflib.get_close_matches(raw, candidates, n=3, cutoff=0.6)
    lines = [f"unknown key: {raw!r}"]
    if near_matches:
        lines.append(f"  did you mean: {', '.join(near_matches)}?")
    lines.append(f"  family aliases: {', '.join(aliases)}")
    lines.append(f"  eligible categories: {', '.join(eligible)}")
    return "\n".join(lines)


def _parse_ratio(raw: str) -> Decimal:
    """Parse a user-typed ratio, rejecting non-finite and out-of-range values."""
    try:
        ratio = Decimal(raw)
    except InvalidOperation as exc:
        typer.echo(f"invalid ratio: {raw!r}", err=True)
        raise typer.Exit(code=2) from exc
    if not ratio.is_finite():
        typer.echo(f"ratio must be finite (got {ratio})", err=True)
        raise typer.Exit(code=2)
    if not (Decimal("0") <= ratio <= Decimal("1")):
        typer.echo(f"ratio must be in [0, 1] (got {ratio})", err=True)
        raise typer.Exit(code=2)
    return ratio


def _load_profile() -> UsageRatioProfile:
    try:
        return load_usage_ratios(_usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _save_profile(profile: UsageRatioProfile) -> None:
    try:
        save_usage_ratios(profile, _usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _usage_ratios_path() -> Path:
    return load_settings().aeat_usage_ratios_path.resolve()


def _format_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")

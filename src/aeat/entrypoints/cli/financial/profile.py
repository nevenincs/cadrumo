"""Implement the ``aeat financial profile`` Typer group for usage ratios.

Surfaces :mod:`aeat.domain.usage_ratios` operations as CLI verbs so the
operator can list, set, and unset per-:class:`aeat.domain.categories.SpendingCategory`
usage ratios. Family-alias expansion via
:data:`aeat.entrypoints.cli.financial._profile_aliases.FAMILY_ALIASES`
lets one command set ratios for an entire group of related categories
in a single keystroke.
"""

from __future__ import annotations

import difflib
import textwrap
from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from ....core.config import load_settings
from ....domain.categories import CATEGORY_PROFILES_2025, SpendingCategory
from ....domain.usage_ratios import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
)
from .._i18n import t, tr
from ._profile_aliases import FAMILY_ALIASES

_MISSING = "(none)"
_ALIAS_LIST = ", ".join(sorted(FAMILY_ALIASES))
_SET_RATIO_KEY_HELP = f"Category id (e.g. suministros_home_office_luz) or family alias ({_ALIAS_LIST})."
_UNSET_RATIO_KEY_HELP = f"Category id or family alias ({_ALIAS_LIST})."

app = typer.Typer(
    name="profile",
    no_args_is_help=True,
    help="Financial profile: per-category usage ratios.",
)

ratios_app = typer.Typer(
    name="ratios",
    no_args_is_help=True,
    help="List the persisted usage ratios.",
)
app.add_typer(ratios_app, name="ratios")


@ratios_app.command(name="list", help="List configured ratios alongside statutory defaults.")
def list_cmd() -> None:
    """Print every persisted ratio next to its statutory default.

    Loads the profile via :func:`aeat.domain.usage_ratios.load_usage_ratios`
    and renders one tab-separated row per category showing the current
    user-set ratio and the statutory default carried by
    :data:`aeat.domain.categories.CATEGORY_PROFILES_2025`.
    """
    profile = _load_profile()
    if not profile.ratios:
        typer.echo(
            tr(
                t(
                    "No hay ratios de uso configurados.",
                    "No usage ratios configured.",
                    "No hi ha ràtios d'ús configurades.",
                    "Nincs beállítva használati arány.",
                )
            )
        )
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


@app.command(name="set-ratio", help="Set the usage ratio for one category or family alias.")
def set_ratio_cmd(
    key: str = typer.Argument(..., help=_SET_RATIO_KEY_HELP),
    value: str = typer.Argument(..., help="Ratio in [0, 1] as a decimal, e.g. 0.21."),
) -> None:
    """Persist one or more usage ratios for the resolved key.

    Args:
        key: Either a single
            :class:`aeat.domain.categories.SpendingCategory` value or a
            family alias from
            :data:`aeat.entrypoints.cli.financial._profile_aliases.FAMILY_ALIASES`.
        value: Decimal ratio in the inclusive ``[0, 1]`` range.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when ``key`` cannot be
            resolved, when ``value`` is not a valid finite decimal in
            range, or when the
            :class:`aeat.domain.usage_ratios.UsageRatioProfile` rejects
            an individual category assignment.
    """
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
        typer.echo(
            tr(
                t(
                    f"establecido {category.value} = {_format_decimal(ratio)}",
                    f"set {category.value} = {_format_decimal(ratio)}",
                    f"establert {category.value} = {_format_decimal(ratio)}",
                    f"beallitva {category.value} = {_format_decimal(ratio)}",
                )
            )
        )


@app.command(name="unset-ratio", help="Remove the usage ratio for one category or family alias.")
def unset_ratio_cmd(
    key: str = typer.Argument(..., help=_UNSET_RATIO_KEY_HELP),
) -> None:
    """Remove persisted ratios for the resolved key.

    Args:
        key: Either a single
            :class:`aeat.domain.categories.SpendingCategory` value or a
            family alias.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when ``key`` cannot be
            resolved or when persistence fails.
    """
    categories = _resolve_key(key)
    profile = _load_profile()
    updated = profile
    removed: list[SpendingCategory] = []
    for category in categories:
        if category in updated.ratios:
            updated = updated.without_ratio(category)
            removed.append(category)
    if not removed:
        typer.echo(
            tr(
                t(
                    f"no hay ratio configurado para {key}",
                    f"no user ratio set for {key}",
                    f"no hi ha cap ràtio configurada per a {key}",
                    f"nincs beallitott arany ehhez: {key}",
                )
            )
        )
        return
    _save_profile(updated)
    for category in removed:
        typer.echo(
            tr(
                t(
                    f"eliminado {category.value}",
                    f"unset {category.value}",
                    f"eliminat {category.value}",
                    f"torolve {category.value}",
                )
            )
        )


def _resolve_key(raw: str) -> tuple[SpendingCategory, ...]:
    """Expand a family alias or validate a single category id.

    Trailing / leading whitespace is tolerated so a copy-paste of
    ``"home_office_area "`` resolves cleanly. An empty string after
    stripping falls through to the unknown-key error path.

    Args:
        raw: Operator-supplied key — alias name or category id.

    Returns:
        Tuple of resolved
        :class:`aeat.domain.categories.SpendingCategory` members.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the key is unknown
            or when a single-category resolution targets a category
            that is not in
            :data:`aeat.domain.usage_ratios.ELIGIBLE_USAGE_RATIO_CATEGORIES`.
    """
    stripped = raw.strip()
    alias_members = FAMILY_ALIASES.get(stripped)
    if alias_members is not None:
        return alias_members
    try:
        category = SpendingCategory(stripped)
    except ValueError as exc:
        typer.echo(_format_unknown_key_hint(raw), err=True)
        raise typer.Exit(code=2) from exc
    if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
        typer.echo(
            tr(
                t(
                    f"{category.value!r} no acepta ratio de uso\n{_format_eligible_list()}",
                    f"{category.value!r} does not accept a usage ratio\n{_format_eligible_list()}",
                    f"{category.value!r} no accepta una ràtio d'ús\n{_format_eligible_list()}",
                    f"{category.value!r} nem fogad el hasznalati aranyt\n{_format_eligible_list()}",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    return (category,)


def _format_unknown_key_hint(raw: str) -> str:
    """Build an actionable error message for an unrecognised key.

    The hint surfaces the offending input as typed (so trailing
    whitespace shows), close-match suggestions drawn from aliases and
    eligible category ids, the full alias list, and the eligible
    category ids — all wrapped to fit an 80-column terminal.

    Args:
        raw: The unrecognised input as typed by the operator.

    Returns:
        A multi-line, human-readable hint suitable for stderr emission.
    """
    aliases = sorted(FAMILY_ALIASES)
    eligible = sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES)
    candidates = aliases + eligible
    near_matches = difflib.get_close_matches(raw.strip(), candidates, n=3, cutoff=0.6)
    lines = [f"unknown key: {raw!r}"]
    if near_matches:
        lines.append(f"  did you mean: {', '.join(near_matches)}?")
    lines.append(_indented_wrap("family aliases:", aliases))
    lines.append(_indented_wrap("eligible categories:", eligible))
    return "\n".join(lines)


def _format_eligible_list() -> str:
    """Render the eligible categories indented and wrapped to 78 columns."""
    eligible = sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES)
    return _indented_wrap("eligible categories:", eligible)


def _indented_wrap(header: str, items: list[str]) -> str:
    """Indent a header + comma-separated list and wrap to 78 columns.

    ``break_long_words=False`` means an individual item longer than
    roughly 65 characters (78 minus the subsequent-indent) would
    overflow on its own line. The current catalogue's longest
    identifier is ``suministros_home_office_internet`` at 32 chars —
    comfortably within budget. Revisit this helper if a future
    :class:`aeat.domain.categories.SpendingCategory` id approaches 65
    characters.

    Args:
        header: Section header rendered before the comma-joined items.
        items: List of items to wrap; an empty list emits ``(none)``.

    Returns:
        Wrapped, two-space-indented text suitable for direct echoing.
    """
    if not items:
        return f"  {header} (none)"
    body = ", ".join(items)
    wrapped = textwrap.fill(
        body,
        width=78,
        initial_indent="  " + header + " ",
        subsequent_indent="    ",
        break_on_hyphens=False,
        break_long_words=False,
    )
    return wrapped


def _parse_ratio(raw: str) -> Decimal:
    """Parse a user-typed ratio, rejecting non-finite and out-of-range values.

    Args:
        raw: Operator-supplied decimal text.

    Returns:
        The parsed :class:`decimal.Decimal` ratio.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the input is not a
            valid decimal, is non-finite (``NaN`` / ``Infinity``), or
            falls outside the inclusive ``[0, 1]`` range.
    """
    try:
        ratio = Decimal(raw)
    except InvalidOperation as exc:
        typer.echo(
            tr(
                t(
                    f"ratio no válido: {raw!r}",
                    f"invalid ratio: {raw!r}",
                    f"ràtio no vàlida: {raw!r}",
                    f"ervenytelen arany: {raw!r}",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    if not ratio.is_finite():
        typer.echo(
            tr(
                t(
                    f"el ratio debe ser finito (recibido {ratio})",
                    f"ratio must be finite (got {ratio})",
                    f"la ràtio ha de ser finita (rebuda {ratio})",
                    f"az aranynak vegesnek kell lennie (kapott: {ratio})",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    if not (Decimal("0") <= ratio <= Decimal("1")):
        typer.echo(
            tr(
                t(
                    f"el ratio debe estar en [0, 1] (recibido {ratio})",
                    f"ratio must be in [0, 1] (got {ratio})",
                    f"la ràtio ha d'estar dins [0, 1] (rebuda {ratio})",
                    f"az aranynak [0, 1] tartomanyban kell lennie (kapott: {ratio})",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    return ratio


def _load_profile() -> UsageRatioProfile:
    """Load the persisted profile, exiting cleanly on a load failure."""
    try:
        return load_usage_ratios(_usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _save_profile(profile: UsageRatioProfile) -> None:
    """Persist ``profile`` to disk, exiting cleanly on a save failure."""
    try:
        save_usage_ratios(profile, _usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _usage_ratios_path() -> Path:
    """Return the resolved path to the persisted usage-ratios JSON file."""
    return load_settings().aeat_usage_ratios_path.resolve()


def _format_decimal(value: Decimal) -> str:
    """Render a :class:`decimal.Decimal` ratio as ``"0"`` or its normalised text form."""
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")

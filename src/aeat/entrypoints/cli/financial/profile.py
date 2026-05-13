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
from .._i18n import tr
from ._profile_aliases import FAMILY_ALIASES

_MISSING = "(none)"
_ALIAS_LIST = ", ".join(sorted(FAMILY_ALIASES))


app = typer.Typer(
    name="profile",
    no_args_is_help=True,
    help=tr("cli.financial.profile.app_help"),
)

ratios_app = typer.Typer(
    name="ratios",
    no_args_is_help=True,
    help=tr("cli.financial.profile.ratios_help"),
)
app.add_typer(ratios_app, name="ratios")


@ratios_app.command(name="list", help=tr("cli.financial.profile.ratios_list_help"))
def list_cmd() -> None:
    """Print every persisted ratio next to its statutory default.

    Loads the profile via :func:`aeat.domain.usage_ratios.load_usage_ratios`
    and renders one tab-separated row per category showing the current
    user-set ratio and the statutory default carried by
    :data:`aeat.domain.categories.CATEGORY_PROFILES_2025`.
    """
    profile = _load_profile()
    if not profile.ratios:
        typer.echo(tr("cli.financial.profile.labels.no_active"))
        return
    typer.echo(tr("cli.financial.profile.headers.ratios"))
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


@app.command(name="set-ratio", help=tr("cli.financial.profile.set_ratio_help"))
def set_ratio_cmd(
    key: str = typer.Argument(..., help=tr("cli.financial.profile.set_ratio_key_help", aliases=_ALIAS_LIST)),
    value: str = typer.Argument(..., help=tr("cli.financial.profile.set_ratio_value_help")),
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
        # Stable CLI confirmation echo: "set <category> = <value>". The
        # category id and the formatted ratio are non-translated tokens
        # that downstream tooling (and the operator's eye) can pin
        # against; locale-sensitive copy is reserved for help / errors.
        typer.echo(f"set {category.value} = {_format_ratio(ratio)}")


def _format_ratio(value: Decimal) -> str:
    """Render a ratio without trailing zeros (``Decimal('0.21')`` → ``'0.21'``)."""
    if value == value.to_integral_value():
        return format(value.quantize(Decimal("1")), "f")
    return format(value.normalize(), "f")


@app.command(name="unset-ratio", help=tr("cli.financial.profile.unset_ratio_help"))
def unset_ratio_cmd(
    key: str = typer.Argument(..., help=tr("cli.financial.profile.unset_ratio_key_help", aliases=_ALIAS_LIST)),
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
        # Idempotent: no-op when the target category had no override.
        # Echo the (non-translated) key so the operator sees which key
        # was inspected.
        typer.echo(f"no user ratio set for {key}")
        return
    _save_profile(updated)
    for category in removed:
        typer.echo(f"unset {category.value}")


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
        eligible = sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES)
        lines = [tr("cli.financial.profile.errors.category_not_eligible", category=category.value)]
        lines.append(_indented_wrap(tr("cli.financial.profile.errors.eligible_categories"), eligible))
        typer.echo("\n".join(lines), err=True)
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
    lines = [tr("cli.financial.profile.errors.unknown_key", raw=raw)]
    if near_matches:
        lines.append("  " + tr("cli.financial.profile.errors.did_you_mean", suggestions=", ".join(near_matches)))
    lines.append(_indented_wrap(tr("cli.financial.profile.errors.family_aliases"), aliases))
    lines.append(_indented_wrap(tr("cli.financial.profile.errors.eligible_categories"), eligible))
    return "\n".join(lines)


def _format_eligible_list() -> str:
    """Render the eligible categories indented and wrapped to 78 columns."""
    eligible = sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES)
    return _indented_wrap(tr("cli.financial.profile.errors.eligible_categories"), eligible)


def _indented_wrap(header: str, items: list[str]) -> str:
    """Indent a header + comma-separated list and wrap to 78 columns.

    ``break_long_words=False`` means an individual item longer than
    roughly 65 characters (78 minus the subsequent-indent) would
    overflow on its own line. The current catalogue's longest
    identifier is ``suministros_home_office_internet`` at 32 chars —
    comfortably within budget. Revisit this helper when a
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
            tr("cli.financial.profile.errors.invalid_ratio", raw=raw),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    if not ratio.is_finite():
        typer.echo(
            tr("cli.financial.profile.errors.must_be_finite", raw=raw),
            err=True,
        )
        raise typer.Exit(code=2)
    if not (Decimal("0") <= ratio <= Decimal("1")):
        typer.echo(
            tr("cli.financial.profile.errors.out_of_range", raw=raw),
            err=True,
        )
        raise typer.Exit(code=2)
    return ratio


def _load_profile() -> UsageRatioProfile:
    """Load the persisted profile, exiting cleanly on a load failure."""
    try:
        return load_usage_ratios()
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _save_profile(profile: UsageRatioProfile) -> None:
    """Persist ``profile`` to disk, exiting cleanly on a save failure."""
    try:
        save_usage_ratios(profile)
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

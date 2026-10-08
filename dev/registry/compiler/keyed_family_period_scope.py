"""Resolve raw period selectors for period-scoped keyed family inheritance."""

from __future__ import annotations

from collections.abc import Mapping

from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table


def _period_token(value: object) -> str | None:
    """The comparable period token of a member's or selector's period value.

    Members spell a period either bare (``"4T"``) or qualified by its year
    (``"2025 01"``); a selector always spells it bare. Taking the last
    whitespace-separated token and upper-casing it compares the two without
    inventing a canonical form for either.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return value.split()[-1].upper()


def _selector_periods_for_year(table: Mapping[str, object], year: object) -> object:
    """The periods a selector serves in one filing year, honouring a ``period_overrides`` entry.

    A transition year files a narrower surface than the years around it: an
    orden that applies from the second trimestre or the month of February
    leaves January and the first trimestre with the preceding edition. The flat
    ``periods`` tuple cannot say that, so an override replaces it for the one
    year it names. Reading the flat tuple here would inherit a period-scoped
    member for a period the successor does not file in the transition year,
    which no gate would catch because the member is individually valid.

    Mirrors ``PeriodSelector.periods_for_year`` against the raw table, since
    inheritance runs before typed construction.
    """
    if isinstance(year, int):
        overrides = table.get("period_overrides")
        if isinstance(overrides, list | tuple):
            for override in overrides:
                override_table = _as_toml_table(override)
                if override_table is not None and override_table.get("year") == year:
                    return override_table.get("periods")
    return table.get("periods")


def selector_covers(selector: object, member: object) -> bool:
    """Whether an edition's ``period_selector`` covers this member's own filing period.

    A period-scoped family states one member per filing period, so a
    predecessor's member is not withheld by a successor that simply files a
    different period - it was never the successor's to state. Inheriting it
    would give an edition a deadline for a period it does not file, which no
    gate would catch because the member is individually valid.

    Coverage is decided by the member's OWN declared ``filing_year`` and
    ``period``, never by its identifier: the identifier is a name, and for this
    family the year inside it is data that a rename can destroy.
    """
    table = _as_toml_table(selector)
    member_table = _as_toml_table(member)
    if table is None or member_table is None:
        return True
    year = member_table.get("filing_year")
    if isinstance(year, int) and not _selector_covers_year(table, year):
        return False
    return _selector_covers_period(table, member_table, year)


def _selector_covers_year(selector: Mapping[str, object], year: int) -> bool:
    years = selector.get("years")
    if isinstance(years, list | tuple) and year not in years:
        return False
    year_from = selector.get("year_from")
    if isinstance(year_from, int) and year < year_from:
        return False
    year_to = selector.get("year_to")
    return not (isinstance(year_to, int) and year > year_to)


def _selector_covers_period(selector: Mapping[str, object], member: Mapping[str, object], year: object) -> bool:
    period = _period_token(member.get("period"))
    periods = _selector_periods_for_year(selector, year)
    if period is None or not isinstance(periods, list | tuple):
        return True
    covered = {token for value in periods if (token := _period_token(value)) is not None}
    return not covered or period in covered

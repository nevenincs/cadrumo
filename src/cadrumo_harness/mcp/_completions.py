"""Argument autocompletion for the guided-workflow prompts.

The MCP ``completion/complete`` capability lets a client autocomplete a prompt
argument as the user types it. The guided workflows accept a filing year and a
period; this module serves the accepted values for each from the typed axes the
registry already declares, so the completion set cannot drift from what the CLI
accepts. It is
SDK-independent - it returns ranked string candidates - so ``_server`` adapts it
to the MCP ``Completion`` type.

Modelo codes are NOT a prompt argument here (the workflow's own skill implies the
modelo), so completions cover the filing year and period axes. If a modelo
argument is added, its candidates must come from the published authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.core.period import accepted_filing_period_codes

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue

#: The finite, enumerable FilingPeriodCode values. The prompt argument names a
#: period the operator FILES in, so the administrative censo tokens the registry
#: coordinate also accepts are deliberately not offered. ``EVENT-<number>``
#: remains an open grammar pattern and is described rather than fabricated as one
#: completion candidate.
_PERIOD_VALUES: tuple[str, ...] = tuple(str(value) for value in accepted_filing_period_codes())

_FILING_YEAR_ARG = "filing_year"
_PERIOD_ARG = "period"

#: The MCP spec caps a completion response at 100 values.
_MAX_COMPLETIONS = 100


def _authored_filing_year_values(support: SupportedFilingYearsCatalogue | None) -> tuple[str, ...]:
    """Return finite authored-coverage years from one validated authority.

    ``horizon`` describes the last year with authored coverage; it is not a
    hard ceiling. A finite completion list therefore enumerates the catalogue's
    derived ``years`` only and must not be described as the complete supported
    span when the authority leaves ``hard_ceiling`` open. Missing support data
    fails closed instead of falling back to a local year declaration.
    """
    if support is None:
        return ()
    return tuple(str(year) for year in support.years)


def complete_prompt_argument(
    argument_name: str,
    partial: str,
    *,
    supported_filing_years: SupportedFilingYearsCatalogue | None = None,
) -> tuple[str, ...]:
    """Return the completion candidates for a prompt ``argument_name``.

    Candidates are prefix-filtered by ``partial`` (case-insensitively for the
    period tokens), capped at the spec's 100-value ceiling. An argument with no
    known value set returns no candidates. Filing-year candidates come from the
    explicitly supplied validated registry authority's authored coverage.

    Args:
        argument_name: Prompt argument whose values should be completed.
        partial: User-entered prefix.
        supported_filing_years: Typed catalogue projected from a published or
            test-injected validated registry authority.

    Returns:
        The ranked candidate values, best-prefix-match order.
    """
    prefix = partial.strip()
    if argument_name == _PERIOD_ARG:
        upper = prefix.upper()
        candidates = tuple(value for value in _PERIOD_VALUES if value.startswith(upper))
    elif argument_name == _FILING_YEAR_ARG:
        candidates = tuple(
            value for value in _authored_filing_year_values(supported_filing_years) if value.startswith(prefix)
        )
    else:
        return ()
    return candidates[:_MAX_COMPLETIONS]

"""Argument autocompletion for the guided-workflow prompts.

The MCP ``completion/complete`` capability lets a client autocomplete a prompt
argument as the user types it. The guided workflows accept a filing year and a
period; this module serves the accepted values for each from the typed axes the
registry already declares (the period grammar and a plausible filing-year range),
so the completion set cannot drift from what the CLI accepts. It is
SDK-independent - it returns ranked string candidates - so ``_server`` adapts it
to the MCP ``Completion`` type.

Modelo codes are NOT a prompt argument here (the workflow's own skill implies the
modelo), so completions cover the filing year and period axes; the ``Modelo``
enum remains the completion source if a modelo argument is ever added.
"""

from __future__ import annotations

from cadrumo.core import accepted_filing_period_codes

#: The finite, enumerable FilingPeriodCode values. The prompt argument names a
#: period the operator FILES in, so the administrative censo tokens the registry
#: coordinate also accepts are deliberately not offered. ``EVENT-<number>``
#: remains an open grammar pattern and is described rather than fabricated as one
#: completion candidate.
_PERIOD_VALUES: tuple[str, ...] = tuple(str(value) for value in accepted_filing_period_codes())

#: A plausible filing-year range offered for completion. Deliberately a fixed
#: recent span (no wall clock is read at import), filtered by the typed prefix;
#: the CLI validates the actual year against the registry at call time.
_FILING_YEARS: tuple[str, ...] = tuple(str(year) for year in range(2019, 2031))

_FILING_YEAR_ARG = "filing_year"
_PERIOD_ARG = "period"

#: The MCP spec caps a completion response at 100 values.
_MAX_COMPLETIONS = 100


def complete_prompt_argument(argument_name: str, partial: str) -> tuple[str, ...]:
    """Return the completion candidates for a prompt ``argument_name``.

    Candidates are prefix-filtered by ``partial`` (case-insensitively for the
    period tokens), capped at the spec's 100-value ceiling. An argument with no
    known value set returns no candidates.

    Returns:
        The ranked candidate values, best-prefix-match order.
    """
    prefix = partial.strip()
    if argument_name == _PERIOD_ARG:
        upper = prefix.upper()
        candidates = tuple(value for value in _PERIOD_VALUES if value.startswith(upper))
    elif argument_name == _FILING_YEAR_ARG:
        candidates = tuple(value for value in _FILING_YEARS if value.startswith(prefix))
    else:
        return ()
    return candidates[:_MAX_COMPLETIONS]

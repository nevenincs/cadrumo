"""Single boundary-authority pin for the shared ledger period filter.

ADR ``2026-06-10-ledger-filter-period`` (decision 1) ratifies one shared filter
authority: the CLI ledger surface (``--filter period=``+``--filter year=`` /
``--period``+``--year``) and the modelo calculation snapshot
(``aggregation_period_for_modelo``) are two spellings of the same
``(year, AEAT-token)`` input that MUST both resolve to the same :class:`Period`
and its fully-closed :meth:`Period.contains` boundary. No parallel period
boundary implementation is permitted.

This module pins that convergence: for every canonical span token, the CLI
transport and the calc-engine transport produce an *identical* ``Period``
object. It also pins the secure-storage invariant (decision 6): the filter is a
pure in-memory selection predicate that adds no plaintext persistence surface;
the rows it selects ride the encrypted :class:`SecureObjectRepository`.
"""

from __future__ import annotations

import inspect

import pytest

from ....core import StandardPeriodCode
from ....entrypoints.cli._common import (
    _canonical_period,
    _filter_canonical_period,
)
from .. import Period, aggregation_period_for_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEARS = (2024, 2025, 2026)

# The span-shaped canonical tokens both transports filter by. Instalment claves
# (1P-4P) carry no date span and convert on neither transport.
_LEDGER_SPAN_TOKENS = tuple(
    code.value
    for code in StandardPeriodCode
    if code
    not in {
        StandardPeriodCode.P1,
        StandardPeriodCode.P2,
        StandardPeriodCode.P3,
        StandardPeriodCode.P4,
    }
)


def _cli_period_via_command_transport(token: str, *, year: int) -> Period:
    """Resolve a ``--period TOKEN --year YEAR`` pair to a Period the CLI way."""
    return _canonical_period(token, year=year)


def _cli_period_via_filter_transport(token: str, *, year: int) -> Period:
    """Resolve a ``--filter period=TOKEN --filter year=YEAR`` clause to a Period the CLI way."""
    return _filter_canonical_period(token, year=year)


def _calc_engine_period(token: str, *, year: int) -> Period:
    """Resolve the same (year, token) to a Period the calc-engine way."""
    return aggregation_period_for_modelo(filing_year=year, period=token)


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("token", _LEDGER_SPAN_TOKENS)
def test_cli_and_calc_engine_produce_an_identical_period(token: str, year: int) -> None:
    """Both transports yield the same Period for the same (year, AEAT-token).

    Strict pydantic equality across the two transports is the proof that one
    boundary authority serves the CLI filter and the modelo calculation
    snapshot. The fully-closed start/end bounds must match exactly.
    """
    command_period = _cli_period_via_command_transport(token, year=year)
    filter_period = _cli_period_via_filter_transport(token, year=year)
    engine_period = _calc_engine_period(token, year=year)

    # All three spellings collapse to one boundary object.
    assert command_period == filter_period == engine_period

    # And to the same fully-closed [start, end] span (the boundary authority).
    assert command_period.start == engine_period.start
    assert command_period.end == engine_period.end
    assert command_period.contains(command_period.start)
    assert command_period.contains(command_period.end)


def test_both_transports_route_through_one_period_boundary() -> None:
    """The CLI and calc-engine transports converge on one Period token-for-token.

    Forbids a parallel boundary implementation: for the same (year, token) the
    CLI ``(--year, AEAT token)`` resolution and the calc-engine translator must
    produce the *identical* :class:`Period` date span, so neither side can drift
    to a private boundary shape. There is no intermediate calendar string on the
    CLI side — the pair builds the Period directly.
    """
    for year in _YEARS:
        for token in _LEDGER_SPAN_TOKENS:
            cli_period = _canonical_period(token, year=year)
            engine_period = aggregation_period_for_modelo(filing_year=year, period=token)
            assert cli_period == engine_period, (year, token)


def test_no_parallel_contains_boundary_is_defined_on_period() -> None:
    """``Period.contains`` is the single boundary predicate.

    A future parallel boundary would most likely appear as a second
    membership/containment method on ``Period``. Pin the public boundary surface
    to exactly ``contains`` so a silently-added parallel predicate trips here.
    """
    boundary_methods = {
        name
        for name, _ in inspect.getmembers(Period, predicate=inspect.isfunction)
        if not name.startswith("_") and any(tok in name.lower() for tok in ("contain", "within", "covers", "includes"))
    }
    assert boundary_methods == {"contains"}, boundary_methods


def test_period_filter_adds_no_plaintext_persistence_surface() -> None:
    """The boundary authority is a pure in-memory predicate (secure-storage gate).

    ADR decision 6: the period filter selects rows that already ride the
    per-profile encrypted bucket-scoped :class:`SecureObjectRepository`; the
    filter itself must add no plaintext persistence. ``Period.contains`` is a
    pure ``date`` comparison — it performs no I/O and writes nothing. Pin that:
    the boundary computes from the model's own fields and the input date alone,
    touching no repository, file, or serialisation surface.
    """
    source = inspect.getsource(Period.contains)
    # The predicate must be a pure start<=value<=end comparison: no persistence,
    # serialisation, or repository token may appear in its body.
    forbidden = ("open(", "write", "Secure", "Repository", "serialize", "model_dump", "json", "save", "persist")
    lowered = source.lower()
    for needle in forbidden:
        assert needle.lower() not in lowered, f"Period.contains must stay a pure predicate; found {needle!r}"

    # And it genuinely discriminates: a real date inside is contained, one
    # outside is not — proving it is a live boundary, not a no-op pass-through.
    from datetime import date

    q1_2025 = aggregation_period_for_modelo(filing_year=2025, period="1T")
    assert q1_2025.contains(date(2025, 2, 14))
    assert not q1_2025.contains(date(2025, 4, 1))

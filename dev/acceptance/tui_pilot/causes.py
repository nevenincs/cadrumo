"""Whether a TUI row matches the persona table's row, and the one cause key of a row that does not.

The match is the persona table's own (``persona_table.frontend.parity``): the same three stages and every figure of
the table row shown with an equal value. A differing row gets one cause key, the first that applies:

- ``other:pilot_crash_<Class>``: the pilot itself crashed on the return (set where it crashed);
- ``edit_refused_no_detail``: an edit was refused before the return calculated;
- ``upstream:<key>``: the return was refused because an earlier return of its chain is not filed or not checked,
  and an earlier return of the same run that the workbench did not file differs with ``<key>``;
- ``tui_calendar_omits_not_applicable_verdict``: the table holds the return not owed, a verdict the TUI never shows;
- ``assumed_value_unconfirmed``, ``next_step_fill_before_<stage>`` or ``other:next_step_<action>``: the form served a
  step the pilot cannot take (it asks the filer to confirm, fill in, resolve or apply), before or after calculate;
- ``other:calculate_<code or stage>``: the return did not calculate;
- ``other:figures_differ``, ``other:verify_<stage>``, ``export_<code or stage>``: the first remaining difference.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ..persona_table.frontend import MATCHED, NOT_COMPARABLE, NOT_REACHED, STAGE_OF, figure_causes, parity
from ..persona_table.rows import TableRow
from .intake import ERROR, NOT_OWED, PASSED, SURFACE, PilotRow

CRASH_CAUSE: Final = "other:pilot_crash_"
UPSTREAM: Final = "upstream:"
#: Refusals a return meets because an earlier return of its chain is not filed or not checked.
CHAIN_REFUSALS: Final = frozenset({"REFUSED_MODELO_PRIOR_PERIOD_UNFILED", "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE"})
_EDIT_REFUSED: Final = "REFUSED_MODELO_EDIT_REFUSED"
_CONFIRM: Final = "confirm"
_FILL: Final = "fill"
_STAGES: Final = ("calculate", "verify", "export")


def outcome(row: PilotRow, table: TableRow) -> str:
    """How the persona table counts ``row`` against ``table``: matched, differs or not comparable."""
    return parity(table, SURFACE, row.result()).outcome


def row_cause(row: PilotRow, table: TableRow, earlier: Sequence[PilotRow]) -> tuple[str | None, str]:
    """The one cause key of ``row`` against the table's ``table`` row, and words naming it; ``None`` when it matches.

    ``earlier`` holds the rows the same run drove before ``row``, with their own causes. A table row with nothing to
    compare (history filed, not run) gets no cause; the words say why.
    """
    crashed = _crash(row)
    if crashed is not None:
        return crashed
    found = parity(table, SURFACE, row.result())
    if found.outcome == MATCHED:
        return None, ""
    words = "; ".join(found.causes)
    if found.outcome == NOT_COMPARABLE:
        return None, words
    return _differing_cause(row, table, earlier, words)


def _crash(row: PilotRow) -> tuple[str, str] | None:
    """The crash cause the pilot set on ``row`` with its words, else ``None``."""
    if row.cause is not None and row.cause.startswith(CRASH_CAUSE):
        return row.cause, row.cause_words
    return None


def _differing_cause(row: PilotRow, table: TableRow, earlier: Sequence[PilotRow], words: str) -> tuple[str, str]:
    """The first cause that applies to a row that differs from its comparable table row; ``words`` name the diff."""
    if row.refusal_code == _EDIT_REFUSED and row.calculate != PASSED:
        return "edit_refused_no_detail", words
    upstream = _upstream(row, earlier)
    if upstream is not None:
        return upstream
    if STAGE_OF[table.verify] == NOT_OWED and row.verify != NOT_OWED:
        return "tui_calendar_omits_not_applicable_verdict", words
    if _figures_differ(row, table):
        return "other:figures_differ", words
    return _first_step_missed(row, STAGE_OF[table.verify]), words


def _figures_differ(row: PilotRow, table: TableRow) -> bool:
    """Whether a calculated, unstopped row shows figures that differ from the table row's."""
    if row.calculate != PASSED or row.stopped_at is not None:
        return False
    return bool(figure_causes(SURFACE, dict(table.figures), row.figures))


def unreported_cause(row: PilotRow, earlier: Sequence[PilotRow]) -> tuple[str | None, str]:
    """The cause a return the run drives but does not report leaves for later returns to name upstream.

    The table reports such a return at another horizon, so no table row of this replay is its oracle: it has no
    cause once the workbench filed it or stopped it as not owed, else the first step it did not take.
    """
    crashed = _crash(row)
    if crashed is not None:
        return crashed
    if row.filed or row.verify == NOT_OWED:
        # A return the table holds not owed is never filed; its successors read the table's world, not a gap.
        return None, ""
    upstream = _upstream(row, earlier)
    if upstream is not None:
        return upstream
    return _first_step_missed(row, PASSED), "not filed through the TUI in this replay"


def _first_step_missed(row: PilotRow, verify: str | None) -> str:
    """The key of the first step the row did not take as ``verify`` expects its check, then its export."""
    if row.stopped_at is not None and row.calculate in (PASSED, NOT_REACHED):
        # The pilot stopped at a served step; a return it never calculated for that reason did not fail to calculate.
        return _stopped_key(row, row.stopped_at)
    if row.calculate != PASSED:
        return f"other:calculate_{(row.refusal_code or row.calculate or ERROR).lower()}"
    if row.verify != verify:
        return f"other:verify_{row.verify}"
    return f"export_{(row.refusal_code or row.export or ERROR).lower()}"


def _stopped_key(row: PilotRow, stopped_at: str) -> str:
    """The key of a step the form served and the pilot cannot take."""
    if stopped_at == _CONFIRM:
        # An unconfirmed assumed value withholds filing; the form rightly asks for the confirmation first.
        return "assumed_value_unconfirmed"
    if stopped_at != _FILL:
        return f"other:next_step_{stopped_at}"
    stage = next((name for name in _STAGES if getattr(row, name) == NOT_REACHED), "export")
    return f"next_step_{stopped_at}_before_{stage}"


def _upstream(row: PilotRow, earlier: Sequence[PilotRow]) -> tuple[str, str] | None:
    """``upstream:<key>`` of the first earlier differing return the workbench did not file, for a chain refusal.

    An earlier return of the same modelo is taken first, since the refusal names that modelo's chain; else the
    first earlier one of any modelo.
    """
    chosen = _unfiled_origin(row, earlier)
    if chosen is None or chosen.cause is None:
        return None
    key = chosen.cause if chosen.cause.startswith(UPSTREAM) else f"{UPSTREAM}{chosen.cause}"
    words = f"{chosen.modelo} {chosen.year} {chosen.period} is not filed through the TUI ({chosen.cause})"
    return key, words


def _unfiled_origin(row: PilotRow, earlier: Sequence[PilotRow]) -> PilotRow | None:
    """The earlier unfiled differing return a chain refusal of ``row`` names, the same modelo's first."""
    if row.refusal_code not in CHAIN_REFUSALS:
        return None
    unfiled = [before for before in earlier if before.cause is not None and not before.filed]
    same = [before for before in unfiled if before.modelo == row.modelo]
    return (same or unfiled or [None])[0]

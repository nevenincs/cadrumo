"""Whether a TUI row matches the persona table's row, and the one cause key of a row that does not.

The match is the persona table's own (``persona_table.frontend.parity``): the same three stages and every figure of
the table row shown with an equal value. A differing row gets one cause key, the first that applies:

- ``other:pilot_crash_<Class>``: the pilot itself crashed on the return (set where it crashed);
- ``edit_refused_no_detail``: an edit was refused before the return calculated;
- ``upstream:<key>``: the return was refused because an earlier return of its chain is not filed or not checked,
  and an earlier return of the same run that the workbench did not file differs with ``<key>``;
- ``tui_calendar_omits_not_applicable_verdict``: the table holds the return not owed, a verdict the TUI never shows;
- ``other:calculate_<code or stage>``: the return did not calculate;
- ``assumed_value_unconfirmed`` or ``next_step_<action>_before_<stage>``: the form served a step the pilot cannot
  take (it asks the filer to confirm or fill in) before that stage;
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
_STAGES: Final = ("calculate", "verify", "export")


def outcome(row: PilotRow, table: TableRow) -> str:
    """How the persona table counts ``row`` against ``table``: matched, differs or not comparable."""
    return parity(table, SURFACE, row.result()).outcome


def row_cause(row: PilotRow, table: TableRow, earlier: Sequence[PilotRow]) -> tuple[str | None, str]:
    """The one cause key of ``row`` against the table's ``table`` row, and words naming it; ``None`` when it matches.

    ``earlier`` holds the rows the same run drove before ``row``, with their own causes. A table row with nothing to
    compare (history filed, not run) gets no cause; the words say why.
    """
    if row.cause is not None and row.cause.startswith(CRASH_CAUSE):
        return row.cause, row.cause_words
    found = parity(table, SURFACE, row.result())
    if found.outcome == MATCHED:
        return None, ""
    words = "; ".join(found.causes)
    if found.outcome == NOT_COMPARABLE:
        return None, words
    if row.refusal_code == _EDIT_REFUSED and row.calculate != PASSED:
        return "edit_refused_no_detail", words
    upstream = _upstream(row, earlier)
    if upstream is not None:
        return upstream
    if STAGE_OF[table.verify] == NOT_OWED and row.verify != NOT_OWED:
        return "tui_calendar_omits_not_applicable_verdict", words
    if row.calculate == PASSED and row.stopped_at is None and figure_causes(SURFACE, dict(table.figures), row.figures):
        return "other:figures_differ", words
    return _first_step_missed(row, STAGE_OF[table.verify]), words


def unreported_cause(row: PilotRow, earlier: Sequence[PilotRow]) -> tuple[str | None, str]:
    """The cause a return the run drives but does not report leaves for later returns to name upstream.

    The table reports such a return at another horizon, so no table row of this replay is its oracle: it has no
    cause once the workbench filed it or stopped it as not owed, else the first step it did not take.
    """
    if row.cause is not None and row.cause.startswith(CRASH_CAUSE):
        return row.cause, row.cause_words
    if row.filed or row.verify == NOT_OWED:
        # A return the table holds not owed is never filed; its successors read the table's world, not a gap.
        return None, ""
    upstream = _upstream(row, earlier)
    if upstream is not None:
        return upstream
    return _first_step_missed(row, PASSED), "not filed through the TUI in this replay"


def _first_step_missed(row: PilotRow, verify: str | None) -> str:
    """The key of the first step the row did not take as ``verify`` expects its check, then its export."""
    if row.calculate != PASSED:
        return f"other:calculate_{(row.refusal_code or row.calculate or ERROR).lower()}"
    if row.stopped_at is not None:
        if row.stopped_at == _CONFIRM:
            # An unconfirmed assumed value withholds filing; the form rightly asks for the confirmation first.
            return "assumed_value_unconfirmed"
        stage = next((name for name in _STAGES if getattr(row, name) == NOT_REACHED), "export")
        return f"next_step_{row.stopped_at}_before_{stage}"
    if row.verify != verify:
        return f"other:verify_{row.verify}"
    return f"export_{(row.refusal_code or row.export or ERROR).lower()}"


def _upstream(row: PilotRow, earlier: Sequence[PilotRow]) -> tuple[str, str] | None:
    """``upstream:<key>`` of the first earlier differing return the workbench did not file, for a chain refusal.

    An earlier return of the same modelo is taken first, since the refusal names that modelo's chain; else the
    first earlier one of any modelo.
    """
    if row.refusal_code not in CHAIN_REFUSALS:
        return None
    unfiled = [before for before in earlier if before.cause is not None and not before.filed]
    same = [before for before in unfiled if before.modelo == row.modelo]
    chosen = (same or unfiled or [None])[0]
    if chosen is None or chosen.cause is None:
        return None
    key = chosen.cause if chosen.cause.startswith(UPSTREAM) else f"{UPSTREAM}{chosen.cause}"
    words = f"{chosen.modelo} {chosen.year} {chosen.period} is not filed through the TUI ({chosen.cause})"
    return key, words

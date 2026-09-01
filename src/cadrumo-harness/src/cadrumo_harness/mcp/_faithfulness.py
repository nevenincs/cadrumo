"""Faithfulness check: agent narration must not invent numeric tax values.

A documented failure mode of financial MCP agents is fabricating a plausible
numeric result when uncertain. This ``PostToolUse`` check extracts amount-shaped
numbers from the agent's narration and flags any whose digit sequence is absent
from the preceding tool-result JSON. It is advisory by default - relaying a
warning - and a hard block on the irreversible filing-handoff path, mirroring the
``no-silent-under-declaration`` discipline of warning where legitimate cases exist
and blocking where the consequence is irreversible. It never computes a value; it
only checks that every number the agent states came from a tool result.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Amount-shaped tokens, three alternatives:
#   1. a currency-prefixed number (``€1234``);
#   2. a thousands-grouped decimal (``1.234,56`` / ``12.345,67``);
#   3. an UNGROUPED decimal of any integer length (``1234.56`` / ``15000.00`` /
#      ``999999.99``) — the machine/en-locale amount shape.
# Bare integers (casilla numbers like ``01``, years like ``2024``) are
# intentionally NOT matched (they carry no 2-decimal fraction), to keep the
# check focused on stated monetary values. Alternative 3 closes a real
# faithfulness blind spot: without it a fabricated amount ≥1000 written without
# a thousands separator (the common machine output shape) matched neither the
# advisory nor the handoff hard-block, defeating the gate the whole surface
# exists to enforce.
_AMOUNT = re.compile(
    r"€\s?\d[\d.,]*"
    r"|\b\d{1,3}(?:[.,]\d{3})+[.,]\d{2}\b"
    r"|\b\d+[.,]\d{2}\b",
)
_ANY_NUMBER = re.compile(r"\d[\d.,]*\d|\d")


def _digits(token: str) -> str:
    """Reduce a number token to its bare digit sequence (separator-agnostic)."""
    return re.sub(r"\D", "", token)


class FaithfulnessResult(BaseModel):
    """Verdict of one faithfulness check.

    ``faithful`` is true when every amount-shaped number in the narration is
    grounded in the tool JSON. ``blocking`` records whether this check ran on the
    irreversible handoff path; ``flagged_values`` lists the ungrounded numbers.
    """

    model_config = _STRICT_FROZEN

    faithful: bool
    blocking: bool
    flagged_values: tuple[str, ...] = Field(default=())

    @property
    def blocks(self) -> bool:
        """True when the check should hard-block the action (handoff + unfaithful)."""
        return self.blocking and not self.faithful


def faithfulness_check(*, agent_text: str, tool_result_json: str, blocking: bool = False) -> FaithfulnessResult:
    """Flag amount-shaped numbers in ``agent_text`` absent from ``tool_result_json``.

    Args:
        agent_text: The agent's operator-facing narration.
        tool_result_json: The serialized JSON of the tool results the narration
            is supposed to be grounded in.
        blocking: When true (the export / record-marker handoff path), an
            unfaithful result blocks; otherwise it is advisory.

    Returns:
        :class:`FaithfulnessResult` with the advisory or blocking verdict.
    """
    grounded = {_digits(match) for match in _ANY_NUMBER.findall(tool_result_json)}
    grounded.discard("")
    flagged: list[str] = []
    for match in _AMOUNT.findall(agent_text):
        digits = _digits(match)
        if digits and digits not in grounded:
            flagged.append(match.strip())
    return FaithfulnessResult(
        faithful=not flagged,
        blocking=blocking,
        flagged_values=tuple(dict.fromkeys(flagged)),
    )


class SessionGroundingWindow:
    """A bounded, in-memory record of the session's tool-result JSON.

    The serving-path integration surface: the model's free narration
    lives client-side where the server cannot see it, so the ENFORCEABLE
    faithfulness boundary is the tool-call arguments — every amount-shaped
    number an agent sends INTO a call must be grounded in a tool result this
    same session produced. The window accumulates each call's result JSON
    (memory only, never persisted — results carry taxpayer figures and
    ``sensitive-financial-data-secure-storage-only`` forbids writing them
    outside secure storage) and serves as the grounding corpus for
    :func:`arguments_faithfulness`.

    Bounded FIFO so a long session cannot grow without limit; the bound is
    generous because a grounding figure is almost always from the immediately
    preceding calculate/revision reads.
    """

    def __init__(self, *, max_results: int = 32) -> None:
        self._max_results = max_results
        self._results: list[str] = []

    def record(self, tool_result_json: str) -> None:
        """Append one call's result JSON to the window, evicting the oldest past the bound."""
        if not tool_result_json:
            return
        self._results.append(tool_result_json)
        if len(self._results) > self._max_results:
            del self._results[0]

    def corpus(self) -> str:
        """The concatenated grounding corpus the checks run against."""
        return "\n".join(self._results)


def arguments_faithfulness(
    *,
    arguments_json: str,
    window: SessionGroundingWindow,
    blocking: bool,
) -> FaithfulnessResult:
    """Check a tool call's ARGUMENTS against the session's grounding window.

    The serving-path enforcement point: advisory on ordinary mutating calls, a
    hard block at the export / record-marker handoff (an amount the session
    never produced must not enter the irreversible artefact call). An empty
    window with amount-shaped arguments on the handoff path blocks — figures
    from nowhere are exactly the fabrication this gate exists to stop.

    Returns:
        A :class:`FaithfulnessResult`.
    """
    return faithfulness_check(
        agent_text=arguments_json,
        tool_result_json=window.corpus(),
        blocking=blocking,
    )


def advisory_line(result: FaithfulnessResult) -> str:
    """The warning line the server prepends to a result for an advisory mismatch (client-relayed, localized)."""
    from cadrumo.core.i18n.render import tr

    return tr(
        "mcp.faithfulness.advisory",
        values=", ".join(result.flagged_values),
        default=(
            "FAITHFULNESS ADVISORY: the call's arguments cite amount(s) "
            "[{values}] that no tool result in this session produced. Verify the "
            "figure against a calculate/revision read before relying on it."
        ),
    )

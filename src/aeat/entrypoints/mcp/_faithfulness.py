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

# Amount-shaped tokens: a currency-prefixed number, or a number carrying two
# decimal places (the euro-amount / casilla-value shape). Bare integers (casilla
# numbers like ``01``, years like ``2024``) are intentionally NOT matched, to keep
# the check focused on stated monetary values.
_AMOUNT = re.compile(r"€\s?\d[\d.,]*|\b\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b")
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

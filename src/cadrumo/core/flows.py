"""Closed value sets for the paged interactive-flow substrate.

The substrate's flow engine, definition contracts, and frontends all
route on the small closed taxonomies below. They live in ``core`` per
the core-authority discipline: production code and frontends accept and
emit these members, never raw strings.

``FlowWidgetKind`` carries the input-primitive taxonomy forward from the
one-shot wizard's widget set unchanged (token-identical values) and adds
``COMPARE_SELECT``, the substrate-generic candidate-comparison page.
Repeating groups are a structural construct of the flow definition (a
sub-page group instantiated N times), not an input primitive, so they do
not appear here.
"""

from __future__ import annotations

from enum import StrEnum

DEFER_TOKEN = "__defer__"
"""Canonical answer token a COMPARE_SELECT page stores when the operator
explicitly defers the decision.

Deferral is a distinct, never-silently-resolving review status, so the
token is reserved: no flow definition may declare it as a choice value.
"""

REPEATING_INSTANCE_SEPARATOR = "#"
"""Separator between a repeating-group instance prefix and a page id.

Instance-scoped answers key the canonical answer map as
``<group-id>#<index>.<page-id>`` so each instance participates
individually in validation, staleness, and review.
"""


class FlowWidgetKind(StrEnum):
    """Closed taxonomy of input primitives a flow page may declare."""

    TEXT = "text"
    SECRET = "secret"
    CONFIRM = "confirm"
    SELECT = "select"
    CHECKBOX = "checkbox"
    PATH = "path"
    INTEGER = "integer"
    COMPARE_SELECT = "compare_select"


class PageStatus(StrEnum):
    """Review-surface status of one flow page.

    ``UNANSWERED`` on an optional page renders as the legitimate
    optional-skipped state; on a required page it blocks submission.
    ``STALE`` marks an answer whose gating parent changed after it was
    given; ``DEFERRED`` marks an explicit COMPARE_SELECT deferral.
    Neither ever resolves silently: both block submission until the
    operator revisits the page.
    """

    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    INVALID = "invalid"
    STALE = "stale"
    DEFERRED = "deferred"


class FlowMode(StrEnum):
    """Which persistence posture a flow run was started under.

    ``CREATE`` runs against a record registered in an explicitly
    incomplete state, so incremental checkpoint writes are shielded from
    consumers. ``MODIFY`` edits a live record and therefore stages every
    answer in memory, committing once from review.
    """

    CREATE = "create"
    MODIFY = "modify"


class CheckpointAvailability(StrEnum):
    """Per-mode checkpoint declaration on a flow definition.

    ``UNAVAILABLE`` is the declared no-op arm: the frontend MUST surface
    that mid-flow save/resume does not exist in that mode and that an
    interrupted run discards staged answers loudly.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CopyRefKind(StrEnum):
    """Closed set of sources a page copy reference may resolve against.

    Copy is assembled at render time from the bundled authoritative
    sources; a flow definition never carries literal prose. The legal
    corpus is deliberately not a member: no mechanism assembles question
    text from it.
    """

    LOCALE_KEY = "locale_key"
    SCHEMA_FIELD = "schema_field"
    TERMINOLOGY_CONCEPT = "terminology_concept"


class FrontendCapability(StrEnum):
    """How richly the host can present an interactive flow.

    ``FULL_SCREEN`` hosts the Textual app; ``LINE`` degrades to the
    sequential line-mode frontend when a TTY exists but a full-screen
    buffer cannot start; ``NON_INTERACTIVE`` names a host that cannot
    prompt at all (piped / redirected / dumb terminal), where an
    interactive frontend must refuse rather than block.
    """

    FULL_SCREEN = "full_screen"
    LINE = "line"
    NON_INTERACTIVE = "non_interactive"


class FlowIntentKind(StrEnum):
    """Closed set of operator intents a frontend may dispatch at the engine."""

    ANSWER = "answer"
    NEXT = "next"
    BACK = "back"
    JUMP = "jump"
    RESET = "reset"
    RESTART = "restart"
    REVIEW = "review"
    CHECKPOINT = "checkpoint"
    SUBMIT = "submit"


__all__ = [
    "DEFER_TOKEN",
    "REPEATING_INSTANCE_SEPARATOR",
    "CheckpointAvailability",
    "CopyRefKind",
    "FlowIntentKind",
    "FlowMode",
    "FlowWidgetKind",
    "FrontendCapability",
    "PageStatus",
]

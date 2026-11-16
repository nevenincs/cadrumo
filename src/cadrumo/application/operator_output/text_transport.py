"""Text-mode transport rows shared by every operator-facing envelope emitter.

The CLI and the runtime executable each render a success envelope as text.
Their notice rows and the sandbox banner are the same contract, so both build
them here rather than each carrying a copy that can drift from the JSON
envelope, which already shares :mod:`.emit`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...core.json_contract import Notice
from .sandbox_notice import sandbox_banner_line, sandbox_notice_for_active_bucket

__all__ = ["notice_lines", "with_sandbox_banner"]


def notice_lines(notices: Sequence[Notice]) -> tuple[str, ...]:
    """Render envelope notices as the matching machine-parsable text lines.

    Text mode receives no ``notices`` channel of its own, so a command that
    passes notices to an envelope emitter and does not fold the same values
    into its ``lines`` emits a diagnostic in JSON that is simply absent from the
    terminal. Rebuilding the line from the notice itself is what stops the two
    surfaces drifting: the code and the message are the notice's, never a second
    sentence written beside it.

    This is the tab-separated transport form every ``app`` surface uses. The
    config storage surface renders its own wrapped, severity-labelled block
    instead; that is a presentation choice for a human-read report and is not
    substitutable here, where the line is parsed.
    """
    return tuple(f"notice\t{notice.code}\t{notice.message}" for notice in notices)


def with_sandbox_banner(lines: Sequence[str]) -> tuple[str, ...]:
    """Prepend the ``SANDBOX`` banner row when the active profile bucket is a sandbox.

    Returns ``lines`` unchanged for a real profile or when no profile is active,
    so a real profile's output is never annotated.
    """
    notice = sandbox_notice_for_active_bucket()
    if notice is None:
        return tuple(lines)
    return (sandbox_banner_line(notice), *lines)

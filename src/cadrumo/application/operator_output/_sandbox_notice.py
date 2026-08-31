"""Sandbox-active indicator shared by every operator-facing JSON/text emitter.

Any command surface that renders a success envelope or text line for the
operator — the CLI transport (:mod:`entrypoints.cli._common`) and the setup
wizard (:mod:`application.wizard.commands`) alike — must be able to warn the
operator that the active profile bucket is a discardable sandbox rather than
their real profile. Both surfaces need the SAME check, so it lives here,
below both of them, rather than duplicated per surface.

This module resolves the active label through the committed-capsule projection
rather than reading a mutable manifest. It stays cheap enough to call on every
emitted line, including the default text-mode path every terminal invocation
takes.
"""

from __future__ import annotations

from ...core.json_contract import Notice


def sandbox_notice_for_active_bucket() -> Notice | None:
    """Return the persistent sandbox-active :class:`Notice`, or ``None``.

    Resolves the active bucket id through the same core precedence chain
    every command uses (:func:`~cadrumo.core.bucket_pointer.resolve_active_bucket_id`), then
    reads its committed label projection and checks it against the reserved
    sandbox label prefix
    (:data:`~cadrumo.core.external_constants.SANDBOX_LABEL_PREFIX`). Returns
    ``None`` when no profile is active, the active bucket has no recognized
    committed capsule, or the active profile is not a sandbox, so a real
    profile's output is never annotated. The projection is deliberately re-read
    on every call (no caching) so a mid-process ``switch`` is reflected on the
    very next command.

    It reads the summary inventory rather than the authenticated aggregate.
    The aggregate takes a per-profile custody lock and can publish a label head
    as a side effect; paying that on every emitted line contradicted this
    module's own cheapness contract, and neither the lock nor the publication
    tells us anything a label check needs.
    """
    from ...application.user_profile.profile_summary import summary_inventory
    from ...core.config_state_root import FormerProductStateError
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...core.external_constants import SANDBOX_LABEL_PREFIX
    from ...core.i18n import tr
    from ...core.json_contract import NoticeSeverity

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        label = next(
            (item.label for item in summary_inventory().summaries if item.profile_id == bucket_id),
            None,
        )
    except (FormerProductStateError, ValueError):
        return None
    if label is None:
        return None
    if not label.startswith(SANDBOX_LABEL_PREFIX):
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.sandbox.active_indicator",
        message=tr(
            "cli.config.profile.sandbox.active_indicator_info",
            default=(
                "You are operating inside the sandbox %{label}, not a real profile; "
                "every command runs against this isolated, discardable bucket."
            ),
            label=label,
        ),
    )


def sandbox_banner_line(notice: Notice) -> str:
    r"""Render ``notice`` as the tab-delimited text-mode ``SANDBOX`` banner line.

    Shared formatting so every text-mode emitter (CLI transport, wizard)
    prepends an identical banner rather than each hand-formatting its own
    ``"SANDBOX\t..."`` string.
    """
    return f"SANDBOX\t{notice.message}"

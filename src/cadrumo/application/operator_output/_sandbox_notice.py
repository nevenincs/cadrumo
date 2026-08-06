"""Sandbox-active indicator shared by every operator-facing JSON/text emitter.

Any command surface that renders a success envelope or text line for the
operator — the CLI transport (:mod:`entrypoints.cli._common`) and the setup
wizard (:mod:`application.wizard._commands`) alike — must be able to warn the
operator that the active profile bucket is a discardable sandbox rather than
their real profile. Both surfaces need the SAME check, so it lives here,
below both of them, rather than duplicated per surface.

This module deliberately imports only :mod:`core` and
:mod:`adapters.persistence.storage` — never the heavier
:mod:`application.workflow` or :mod:`application.bucket_maintenance` facades
— so it stays cheap enough to call on every emitted line, including the
default text-mode path every terminal invocation takes.
"""

from __future__ import annotations

from ...core.json_contract import Notice


def sandbox_notice_for_active_bucket() -> Notice | None:
    """Return the persistent sandbox-active :class:`Notice`, or ``None``.

    Resolves the active bucket id through the same core precedence chain
    every command uses (:func:`~cadrumo.core.resolve_active_bucket_id`), then
    reads its plaintext manifest label directly through the light
    ``adapters.persistence.storage.bucket`` primitives, and checks it against
    the reserved sandbox label prefix
    (:data:`~cadrumo.core.external_constants.SANDBOX_LABEL_PREFIX`). Returns
    ``None`` when no profile is active, the active bucket's manifest is
    absent, unreadable, or fails strict validation, or the active profile is
    not a sandbox, so a real profile's output is never annotated and a
    corrupt/torn manifest degrades this purely-advisory indicator rather than
    breaking every command's output. The manifest is deliberately re-read on
    every call (no caching) so a mid-process ``switch`` is reflected on the
    very next command.
    """
    from ...adapters.persistence.storage import StorageValidationError
    from ...adapters.persistence.storage.bucket import bucket_paths, manifest_path, read_manifest
    from ...core import FormerProductStateError, resolve_active_bucket_id
    from ...core.config import load_settings
    from ...core.external_constants import SANDBOX_LABEL_PREFIX
    from ...core.i18n import tr
    from ...core.json_contract import NoticeSeverity

    try:
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        paths = bucket_paths(load_settings().cadrumo_local_storage_root, bucket_id)
        if not manifest_path(paths).is_file():
            return None
        label = read_manifest(paths).label
    except (FormerProductStateError, StorageValidationError, ValueError):
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
        suggestion="aeat config profile sandbox discard",
    )


def sandbox_banner_line(notice: Notice) -> str:
    r"""Render ``notice`` as the tab-delimited text-mode ``SANDBOX`` banner line.

    Shared formatting so every text-mode emitter (CLI transport, wizard)
    prepends an identical banner rather than each hand-formatting its own
    ``"SANDBOX\t..."`` string.
    """
    return f"SANDBOX\t{notice.message}"

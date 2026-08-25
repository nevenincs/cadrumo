"""The independently loadable ``config profile list`` leaf."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_output_language

if TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer


def profile_list_lines(
    rows: Sequence[ProfileBucketPointer],
    *,
    active: str | None,
    active_label: str | None,
) -> list[str]:
    lines = [f"active_profile\t{active_label or '<none>'}"]
    if not rows:
        lines.append("profiles\t<none>")
        return lines
    lines.extend(f"{'*' if pointer.bucket_id == active else ' '}\t{pointer.label}" for pointer in rows)
    return lines


def config_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List committed profile pointers without importing sibling commands."""
    _activate_output_language(ctx, output_language)
    from ....application.workflow import list_profile_buckets
    from ....core import resolve_active_bucket_id
    from .._config_payloads import ConfigListResult, ProfilePointerPayload

    active = resolve_active_bucket_id()
    rows = sorted(list_profile_buckets().values(), key=lambda pointer: pointer.label.casefold())
    active_label = next((pointer.label for pointer in rows if pointer.bucket_id == active), None)
    result = ConfigListResult(
        active_profile=active_label,
        profiles=[
            ProfilePointerPayload(
                name=pointer.label,
                bucket_id=pointer.bucket_id,
                active=pointer.bucket_id == active,
            )
            for pointer in rows
        ],
    )
    _emit_envelope(
        ctx,
        command="config.profile.list",
        result=result,
        lines=profile_list_lines(rows, active=active, active_label=active_label),
    )

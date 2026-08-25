"""Line-mode projection for an exact censal-review decision."""

from __future__ import annotations

import typer

from ....application.user_profile import CensalReviewProjectionV1
from ....core.i18n import tr


def confirm_censal_review(projection: CensalReviewProjectionV1) -> bool:
    """Render the reviewed facts in the CLI and require explicit approval."""
    for field in projection.fields:
        typer.echo(f"{field.path}: {field.observed_value or '—'} [{field.intent.value}]")
    return typer.confirm(tr("flows.manager.censal_review.apply"), default=False)


__all__ = ["confirm_censal_review"]

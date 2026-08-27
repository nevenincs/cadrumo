"""The independently loadable ``config profile list`` leaf.

The leaf reads storage exactly twice: one anchored summary observation and one
active-pointer read.  Everything after that is an in-memory join, so rendering
cannot re-enter persistence and the listing cost does not scale with how many
times a row is displayed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from .._common import activate_subcommand_output_language as _activate_output_language
from .._common import emit_envelope

if TYPE_CHECKING:
    from ....application.user_profile.profile_summary import ProfileSummary, ProfileSummaryInventory
    from ....core.json_contract import Notice


@dataclass(frozen=True, slots=True)
class JoinedProfileRow:
    """One summary joined to the single active-pointer observation.

    The join happens once, in memory.  Rendering receives this and never the
    inventory, so no renderer can be tempted to resolve the active profile --
    or anything else -- a second time.
    """

    summary: ProfileSummary
    active: bool

    @property
    def label(self) -> str:
        """The operator-facing label carried by the observed capsule."""
        return self.summary.label


def join_active_profile(
    inventory: ProfileSummaryInventory,
    *,
    active_bucket_id: str | None,
) -> tuple[JoinedProfileRow, ...]:
    """Join summaries to the active pointer and order them for display.

    Ordering is by casefolded label so the listing reads alphabetically to an
    operator, with the profile id as the tie-break so two profiles sharing a
    casefolded label still order deterministically between runs.
    """
    rows = tuple(
        JoinedProfileRow(summary=summary, active=summary.profile_id == active_bucket_id)
        for summary in inventory.summaries
    )
    return tuple(sorted(rows, key=lambda row: (row.label.casefold(), row.summary.profile_id)))


def active_profile_label(rows: Sequence[JoinedProfileRow]) -> str | None:
    """Return the joined active row's label without re-reading the pointer."""
    return next((row.label for row in rows if row.active), None)


def profile_list_lines(rows: Sequence[JoinedProfileRow], *, active_label: str | None) -> list[str]:
    """Render the joined rows; no row here can reach storage."""
    lines = [f"active_profile\t{active_label or '<none>'}"]
    if not rows:
        lines.append("profiles\t<none>")
        return lines
    lines.extend(f"{'*' if row.active else ' '}\t{row.label}" for row in rows)
    return lines


def _incoherent_listing_notice(inventory: ProfileSummaryInventory) -> Notice:
    """Say plainly that the listing could not be trusted, and why.

    A degraded or concurrent observation carries no rows, and an empty list is
    otherwise indistinguishable from a store that holds no profiles.  Reporting
    it silently would tell an operator their profiles are gone.
    """
    from .._modelo_rendering import advisory_notice

    outcome = str(inventory.outcome)
    return advisory_notice(
        "config.profile.list.incoherent_observation",
        tr("cli.config.profile.list.incoherent_observation_advisory", outcome=outcome),
        context={"outcome": outcome, "detail": inventory.detail or ""},
    )


def config_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List committed profiles from one summary observation and one pointer read."""
    _activate_output_language(ctx, output_language)
    from ....application.user_profile.profile_summary import summary_inventory
    from ....core.bucket_pointer import resolve_active_bucket_id
    from .._config_payloads import ConfigListResult, ProfilePointerPayload

    inventory = summary_inventory()
    rows = join_active_profile(inventory, active_bucket_id=resolve_active_bucket_id())
    active_label = active_profile_label(rows)
    result = ConfigListResult(
        active_profile=active_label,
        profiles=[
            ProfilePointerPayload(
                name=row.label,
                bucket_id=row.summary.profile_id,
                active=row.active,
            )
            for row in rows
        ],
    )
    notices = () if inventory.recognized else (_incoherent_listing_notice(inventory),)
    emit_envelope(
        ctx,
        command="config.profile.list",
        result=result,
        lines=profile_list_lines(rows, active_label=active_label),
        notices=notices,
    )

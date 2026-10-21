"""The independently loadable ``config profile list`` leaf.

The leaf reads storage exactly twice: one anchored summary observation and one
active-pointer read.  Everything after that is an in-memory join made by the
application's listing, so rendering cannot re-enter persistence and the listing
cost does not scale with how many times a row is displayed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ..common import activate_subcommand_output_language as _activate_output_language
from ..common import emit_envelope

if TYPE_CHECKING:
    from ....application.user_profile.profile_summary import ProfileListingResult, ProfileSummaryInventory
    from ....core.json_contract import Notice


def profile_list_lines(listing: ProfileListingResult) -> list[str]:
    """Render the joined rows; no row here can reach storage."""
    lines = [f"active_profile\t{listing.active_profile or '<none>'}"]
    if not listing.profiles:
        lines.append("profiles\t<none>")
        return lines
    lines.extend(f"{'*' if row.active else ' '}\t{row.name}" for row in listing.profiles)
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
    from ....application.user_profile.profile_summary import profile_listing
    from .profile_list_payloads import ConfigListResult

    listing = profile_listing()
    inventory = listing.inventory
    joined = listing.result()
    notices = () if inventory.recognized else (_incoherent_listing_notice(inventory),)
    emit_envelope(
        ctx,
        command="config.profile.list",
        result=ConfigListResult.model_validate(joined.model_dump(mode="json")),
        lines=profile_list_lines(joined),
        notices=notices,
    )

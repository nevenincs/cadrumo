"""No NEW live command reaches the operator without a risk assessment.

The risk table drives the live-write block that enforces "never file". A
command in a mutating family with no declared row classifies all-false --
including ``live_write=False`` -- which the classification tests themselves
call "the default is safe-looking, which is the trap". ``risk_declared``
exists precisely to tell an assessed-and-safe command from a never-assessed
one.

Nothing was using it against the real surface. The contract-drift gate checks
only that no row outlives its command, and declines the other direction with a
stated reason: read-only verbs are legitimately row-less, so an exact mirror
would fail against correct data. Its docstring hands the missing direction to
"the classification tests", and those prove the distinction works on PLANTED
verbs -- never that the live surface is fully assessed. So a new mutating verb
could ship undeclared, classify as not-a-live-write, and no gate would notice.

WHAT THIS LIST IS. A debt register, not a clearance. Every entry is a live
command whose risk axes were NEVER assessed, recorded as it stood when this
gate was written. Being listed asserts nothing about whether the command is
safe -- only that its absence is known rather than newly introduced. None of
them is a submission verb today, which is why this is a gap to close rather
than a breach to fix, and the 26 are frozen so the 27th cannot appear quietly.

Clearing an entry means declaring the command in the risk table and deleting
its line here, which the staleness half enforces. The register is expected to
shrink and must never grow.
"""

from __future__ import annotations

import pytest

from ....application.operator_surface import command_classification

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Live commands carrying no risk assessment when this gate was introduced.
#: NOT a statement that they are safe -- a statement that nobody judged them.
_UNASSESSED_AT_BASELINE = frozenset(
    {
        "app.live.deudas.latest",
        "app.live.deudas.list",
        "app.live.deudas.view",
        "app.live.filed.discover",
        "app.live.filed.pull_all",
        "app.live.notifications.document.history",
        "app.live.notifications.document.pull",
        "app.live.notifications.document.view",
        "config.passphrase.change",
        "config.profile.archive.export",
        "config.profile.archive.inspect",
        "config.profile.complete_setup",
        "config.profile.restore",
        "config.provision.pull",
        "config.provision.report",
        "config.provision.verify",
        "ledger.counterparty.confirm",
        "ledger.counterparty.show",
        "ledger.counterparty.withdraw",
        "ledger.detach",
        "ledger.evidence.batch",
        "ledger.evidence.consent.list",
        "ledger.evidence.consent.rederive",
        "ledger.evidence.review.list",
        "ledger.evidence.review.show",
        "modelo.work.review",
    },
)


def _unassessed_live_commands() -> set[str]:
    """Return every exposable command whose risk axes were never assessed."""
    from .._command_schema import command_schema_refs
    from .._verb_input_schema import is_exposable_command

    live = {ref.command for ref in command_schema_refs() if is_exposable_command(ref.command)}
    assert live, "exposable command set is empty, so this gate would pass while checking nothing"
    return {command for command in live if not command_classification(command).risk_declared}


def test_no_command_joins_the_surface_without_a_risk_assessment() -> None:
    """DISCRIMINATING: the 27th undeclared verb is the one that matters.

    A new mutating command with no row classifies live_write=False, so the block
    that enforces "never file" does not fire for it. That is indistinguishable
    at runtime from a command someone assessed and found safe.
    """
    newly_unassessed = sorted(_unassessed_live_commands() - _UNASSESSED_AT_BASELINE)

    assert not newly_unassessed, (
        f"these commands are exposed to the operator with no risk assessment: {newly_unassessed}. "
        "An unassessed mutating command classifies live_write=False, so the live-write block never "
        "fires for it. Declare it in COMMAND_RISK -- including to record that it is safe -- rather "
        "than adding it here."
    )


def test_the_register_shrinks_and_never_stales() -> None:
    """A cleared or retired command must leave this list.

    Without this the register would keep asserting debt that was already paid,
    and a reader could not tell the outstanding entries from the finished ones.
    """
    resolved = sorted(_UNASSESSED_AT_BASELINE - _unassessed_live_commands())

    assert not resolved, (
        f"these commands now carry a risk assessment, or no longer exist: {resolved}. Remove them "
        "from the baseline register; an entry that outlives its gap overstates what is outstanding."
    )


def test_the_baseline_is_not_a_blanket_over_the_whole_surface() -> None:
    """ANTI-TAUTOLOGY: most commands ARE assessed, so the register must be small.

    A register that grew to cover everything would satisfy both checks above
    while meaning nothing. Bounded rather than exact, so declaring one command
    does not have to update a count.
    """
    from .._command_schema import command_schema_refs
    from .._verb_input_schema import is_exposable_command

    live = {ref.command for ref in command_schema_refs() if is_exposable_command(ref.command)}

    assert len(_UNASSESSED_AT_BASELINE) * 4 < len(live), (
        f"{len(_UNASSESSED_AT_BASELINE)} of {len(live)} commands are unassessed. Past roughly a "
        "quarter this register stops reading as a debt list and starts reading as the norm"
    )

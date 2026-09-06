"""Every one-sided link direction the domain can produce is renderable.

The workspace projection flattens
:class:`~core.invoice_link.LinkInconsistencyDirection` to a bare ``str`` before
it reaches the reconciliation screen, so ``DIRECTION_STATE_COPY_KEYS`` is the
only place that membership survives on the TUI side — and it was a dict written
inline in ``on_mount`` with hand-typed strings.

A direction added to the enum and not to the map does not degrade politely. The
screen raises while building the inconsistencies table, so the operator's
reconciliation view fails to open at all rather than showing the row it could
not label — and the inconsistencies table is precisely where a one-sided link
between the transaction and invoice catalogues is disclosed.

Pinned against the enum rather than against a copy of today's two values, so
adding a third member turns this red instead of shipping a render-time refusal.
"""

from __future__ import annotations

import pytest

from .....core.i18n.render import tr
from .....core.invoice_link import LinkInconsistencyDirection
from ..reconciliation import DIRECTION_STATE_COPY_KEYS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_canonical_direction_has_operator_copy() -> None:
    """The exhaustiveness the inline dict could not state."""
    missing = {member.value for member in LinkInconsistencyDirection} - set(DIRECTION_STATE_COPY_KEYS)

    assert not missing, f"link inconsistency directions the reconciliation screen cannot render: {sorted(missing)}"


def test_the_map_claims_no_direction_the_domain_cannot_produce() -> None:
    """Drift the other way: copy for a state that no longer exists."""
    unknown = set(DIRECTION_STATE_COPY_KEYS) - {member.value for member in LinkInconsistencyDirection}

    assert not unknown, f"reconciliation copy for directions the domain does not emit: {sorted(unknown)}"


@pytest.mark.parametrize("member", list(LinkInconsistencyDirection), ids=lambda member: member.value)
def test_each_direction_resolves_to_real_copy(member: LinkInconsistencyDirection) -> None:
    """A key present but unresolvable would render the key itself to the operator."""
    rendered = tr(DIRECTION_STATE_COPY_KEYS[member.value])

    assert rendered
    assert rendered != DIRECTION_STATE_COPY_KEYS[member.value]


def test_the_two_directions_do_not_share_one_message() -> None:
    """Invoice-only and transaction-only name opposite catalogues.

    Collapsing them would tell an operator a link is one-sided without saying
    which side holds it, which is the one fact that decides what to fix.
    """
    rendered = {tr(key) for key in DIRECTION_STATE_COPY_KEYS.values()}

    assert len(rendered) == len(DIRECTION_STATE_COPY_KEYS)

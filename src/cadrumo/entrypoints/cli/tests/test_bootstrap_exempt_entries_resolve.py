"""Gate: every bootstrap exemption names a verb the tree actually registers.

An exemption is matched by command chain, so an entry naming a verb that does
not exist is not merely dead. It is armed: register a verb under that name
later and it silently inherits an exemption from the active-profile session
gate that nobody consciously granted. Six such entries accumulated once, and
the one that mattered was profile deletion.

Nothing detected them, because an exemption list is data that only participates
when a matching verb is dispatched — an entry for an absent verb is never
consulted and therefore never wrong at runtime.

The companion failure this file cannot gate is the one that motivated it: the
entries were correct while their stated REASONS had gone false. Two were found
in one day, one citing a test that was never written and one asserting a
manifest read that no longer happened. Prose cannot be checked mechanically,
which is why the module now states criteria rather than mechanisms; this gate
covers only the half that can be.
"""

from __future__ import annotations

import pytest
from typer.main import get_command

from .. import app
from .._bootstrap_exempt import BOOTSTRAP_EXEMPT_VERB_PATHS, is_bootstrap_exempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _resolves(verb_path: str) -> bool:
    """Return whether the live command tree dispatches ``verb_path``.

    Walks the real tree the way dispatch does, materialising lazily-loaded
    subcommands, so a verb behind a lazy group counts as registered.
    """
    from ...mcp._input_schema import _resolve_command

    command, _resolved, error = _resolve_command(get_command(app), verb_path.replace(" ", "."))
    return error is None and command is not None


@pytest.mark.parametrize("verb_path", BOOTSTRAP_EXEMPT_VERB_PATHS)
def test_every_exemption_names_a_registered_verb(verb_path: str) -> None:
    """A retired verb must take its exemption with it, or the entry lies in wait."""
    assert _resolves(verb_path), (
        f"bootstrap exemption {verb_path!r} names no registered verb. Remove it with the verb: "
        "left standing, it grants a future verb of that name an unreviewed exemption from the "
        "active-profile session gate."
    )


def test_the_gate_would_catch_an_exemption_for_an_absent_verb() -> None:
    """Anti-tautology: the check above is only evidence if a bad entry fails it.

    Every real entry passing proves nothing on its own — a resolver that
    returned ``True`` unconditionally would look identical.
    """
    assert not _resolves("config profile invented-verb")
    assert not _resolves("app modelo invented-verb")


def test_matching_stays_prefix_based_so_a_leaf_entry_does_not_carry_its_siblings() -> None:
    """A leaf exemption must not exempt the group, which is why leaves are used.

    ``app diagnostics telemetry status`` is deliberately a leaf so its sibling
    stays gated. If matching ever widened to the group, that sibling would be
    exempted silently and this pins the boundary.
    """
    assert is_bootstrap_exempt("app diagnostics telemetry status")
    assert is_bootstrap_exempt("app diagnostics telemetry status --json")
    assert not is_bootstrap_exempt("app diagnostics telemetry flush")
    assert not is_bootstrap_exempt("app diagnostics telemetry")

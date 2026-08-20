"""Every profile-bound write verb still names a live CLI command.

`PROFILE_BOUND_WRITE_VERB_PATHS` is the catalogue the storage write guard
matches an invocation against before allowing a bucket-scoped mutation. The
match is by VERB PATH STRING, and the failure mode when a string goes stale is
not a refusal -- it is silence. An unmatched verb is answered
``NON_PROFILE_BOUND_VERB``, so the write proceeds unguarded. The guard fails
OPEN, which is why a stale entry here is worse than a missing one anywhere else
in this tree.

This is not hypothetical. The catalogue's own comments record it happening: the
payable/collectible invoice verbs collapsed into one ``invoice`` family
discriminated by ``--kind``, the catalogue kept the pre-collapse spellings, and
every invoice mutation fell out of the guard until someone noticed.

Nothing prevented the next occurrence. A rename lands in the CLI, the
catalogue keeps the old spelling, every test stays green, and the surface is
silently unguarded -- there is no assertion anywhere that says otherwise,
because "this verb was not guarded" and "this verb does not exist" produce the
same observable nothing.

The check walks the REAL materialised Click tree rather than a schema
projection or a manifest. A projection can agree with the catalogue while both
disagree with what the operator can actually type.
"""

from __future__ import annotations

import pytest
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer.main import get_command as typer_get_command

from ...entrypoints.cli import app as cli_app
from ..storage_write_policy import PROFILE_BOUND_WRITE_VERB_PATHS

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _live_verb_paths() -> frozenset[str]:
    """Return every command path the materialised CLI actually exposes.

    Groups are included as well as terminals: the guard matches a catalogue
    entry as an exact path OR as a prefix, so an entry naming a group
    legitimately covers its children.
    """
    root = typer_get_command(cli_app)
    found: set[str] = set()

    def walk(command: ClickCommand, context: ClickContext, path: tuple[str, ...]) -> None:
        if path:
            found.add(" ".join(path))
        lister = getattr(command, "list_commands", None)
        getter = getattr(command, "get_command", None)
        if not callable(lister) or not callable(getter):
            return
        for name in (str(child) for child in lister(context)):
            child_command = getter(context, name)
            if child_command is not None:
                walk(child_command, ClickContext(child_command, parent=context, info_name=name), (*path, name))

    walk(root, ClickContext(root, info_name=str(root.name)), ())
    return frozenset(found)


def test_the_walk_finds_the_real_cli() -> None:
    """ANTI-VACUITY: an empty walk would clear every entry below.

    The assertion that follows is "no catalogue entry is missing from this
    set". If the set were empty the check would invert into passing only when
    the catalogue is empty -- and if the walk silently stopped matching, it
    would report a fully-guarded surface while looking at nothing.
    """
    paths = _live_verb_paths()

    assert len(paths) > 100, f"the Click walk found only {len(paths)} verb paths; it is not seeing the real CLI"
    assert "config profile create" in paths, "the walk is not reaching known nested verbs"


def test_every_guarded_verb_path_resolves_to_a_live_verb() -> None:
    """A rename must not drop a surface out of the write guard silently."""
    live = _live_verb_paths()
    unresolved = sorted(verb for verb in PROFILE_BOUND_WRITE_VERB_PATHS if verb not in live)

    assert not unresolved, (
        f"these guarded write verbs name no live CLI command: {unresolved}. The guard matches by "
        "verb path, and an unmatched verb is answered NON_PROFILE_BOUND_VERB -- so a stale entry "
        "does not refuse, it lets the write through unguarded. Re-point each entry at the verb's "
        "current spelling, or remove it in the same change that removed the verb."
    )


def test_the_catalogue_is_not_empty() -> None:
    """The other direction of vacuity: a guard catalogue guarding nothing.

    An empty catalogue satisfies the assertion above perfectly. Stated
    separately so that emptying it -- by accident or to make something pass --
    cannot read as a clean result.
    """
    assert len(PROFILE_BOUND_WRITE_VERB_PATHS) > 50, (
        f"the guarded-verb catalogue holds only {len(PROFILE_BOUND_WRITE_VERB_PATHS)} entries; "
        "a guard catalogue that has been emptied refuses nothing and passes everything"
    )

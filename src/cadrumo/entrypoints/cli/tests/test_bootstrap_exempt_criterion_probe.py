"""Roundtrip: the read-only exemptions answer on a pristine, sessionless root.

The registry's first membership criterion is behavioural — "the verb must
function correctly on a fresh ``CADRUMO_LOCAL_STORAGE_ROOT`` with no active
profile pointer and no encrypted state". Every other check over the exemption
list is structural: it can prove an entry names a live verb and that the verb
another entry cites still exists, but not that the verb actually works with no
session. That is the claim each entry is admitted on, and it is the one an
unrelated refactor breaks.

So it is executed here rather than asserted. Each argument-free exemption in
the read-only classes is invoked against a pristine storage root with no
pointer, no database and no buckets directory, and must exit cleanly with no
session ever opening.

The covered set is DERIVED from the registry, not listed here: a new
catalogue-class exemption is probed the moment it is added, without anyone
remembering to enrol it. Entries outside the read-only classes are excluded
because driving them would create or destroy state — the first-run wizard
prompts, the session doors mutate the session, the recovery family writes.
``config repair`` already has its own fresh-root probe, which is why the
recovery family is not a gap here so much as covered elsewhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from click import Context as ClickContext
from typer.main import get_command

from ....adapters.persistence.storage.master_key import has_active_bucket_session
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root
from .. import app
from .._bootstrap_exempt import BOOTSTRAP_EXEMPTIONS, ExemptionCriterion

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The criteria whose verbs answer from bundled, compiled or configuration data
#: and so can be driven with no state at all. The recovery, session-door and
#: first-run criteria are deliberately absent: invoking them changes state.
_PROBEABLE_CRITERIA = frozenset(
    {
        ExemptionCriterion.BUNDLED_CATALOGUE,
        ExemptionCriterion.CONFIGURATION_ONLY,
        ExemptionCriterion.DISCOVERY_DEADLOCK,
    }
)


def _leaf_without_required_arguments(verb_path: str) -> tuple[str, ...] | None:
    """Return ``verb_path`` split into tokens when it is drivable bare.

    A group, or a leaf demanding any required input, cannot be invoked without
    inventing a value the probe would then really be asserting about. The test
    is ``required`` across every parameter rather than the argument/option
    distinction: Typer vendors its own click fork, so an ``isinstance`` check
    against upstream ``click.Argument`` silently matches nothing and admits
    verbs the probe cannot drive.
    """
    root = get_command(app)
    command: object = root
    context = ClickContext(root, info_name=str(root.name))
    for token in verb_path.split():
        getter = getattr(command, "get_command", None)
        if getter is None:
            return None
        child = getter(context, token)
        if child is None:
            return None
        context = ClickContext(child, info_name=token, parent=context)
        command = child
    if getattr(command, "list_commands", None) is not None and command.list_commands(context):  # type: ignore[attr-defined]
        return None
    for parameter in getattr(command, "params", ()):
        if getattr(parameter, "required", False):
            return None
    return tuple(verb_path.split())


_PROBEABLE_VERBS: tuple[tuple[str, ...], ...] = tuple(
    tokens
    for tokens in (
        _leaf_without_required_arguments(exemption.verb_path)
        for exemption in BOOTSTRAP_EXEMPTIONS
        if exemption.criterion in _PROBEABLE_CRITERIA
    )
    if tokens is not None
)


@pytest.fixture
def _fresh_storage_root(tmp_path: Path) -> Iterator[Path]:
    """A pristine storage root: no pointer, no database, no buckets."""
    from ....core.config import override_settings

    with override_settings(cadrumo_output_language="en"):
        with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
            yield storage_root


def test_the_probe_covers_the_read_only_exemptions() -> None:
    """The derived set must actually reach the catalogue verbs it claims to.

    Without this, a change to the derivation that silently emptied the set
    would leave every probe below passing vacuously, which is exactly how a
    check stops detecting anything while still looking green.
    """
    probed = {" ".join(tokens) for tokens in _PROBEABLE_VERBS}
    for expected in ("app ledger categories", "app live portals list", "config profile list"):
        assert expected in probed, f"{expected!r} dropped out of the fresh-root probe set: {sorted(probed)}"


@pytest.mark.parametrize("verb", _PROBEABLE_VERBS, ids=lambda v: " ".join(v))
def test_a_read_only_exemption_answers_on_a_fresh_sessionless_root(
    verb: tuple[str, ...],
    _fresh_storage_root: Path,
) -> None:
    """The verb answers with no profile pointer, no encrypted state, no session.

    This is the membership criterion itself, run rather than asserted. A verb
    that acquires a session requirement keeps its exemption in the registry and
    starts refusing the operator it was exempted for; that regression surfaces
    here and nowhere else.
    """
    assert not has_active_bucket_session(), "fixture must leave no session active"

    result = invoke_cached_cli(list(verb))

    assert result.exit_code == 0, f"{' '.join(verb)} failed on a fresh root: {result.output}"
    assert "NoActiveBucketSession" not in result.output
    assert "Traceback" not in result.output
    assert not has_active_bucket_session(), f"{' '.join(verb)} opened a bucket session it is exempt from needing"

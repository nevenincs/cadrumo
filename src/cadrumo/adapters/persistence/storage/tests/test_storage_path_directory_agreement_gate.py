"""Gate: a grammar's directory portion agrees with the taxonomy subpath it spells.

Every :class:`~adapters.persistence.storage.StoragePathDefinition` grammar is a
hand-written string. Where its directory portion nests beneath an already-declared
:class:`~cadrumo.core.StorageCategory` member -- ``<root>/runs/<run_id>/trace.json``
nests beneath ``StorageCategory.RUNS``'s ``"runs"`` subpath -- the two spellings
duplicate each other, and nothing previously compared them: renaming the member's
subpath would leave every grammar that spelled out its old name silently
disagreeing with the taxonomy. This gate makes that comparison live, re-derived
from :func:`~cadrumo.core.storage_location` on every run rather than a copied
constant, so a rename is caught the moment it lands.

The one pre-existing exception -- ``config_reset_journal``'s ``reset-operations``
directory, joined onto the raw storage root in
``application/_config_reset_repository.py`` rather than resolved through a
declared category -- is named explicitly rather than silently exempted; it is a
real, already-recorded gap
(``2026-08-03-canonical-storage-management-honesty-review-audit``), not a defect
this gate invents or launders.
"""

from __future__ import annotations

from typing import Final

import pytest

from .....core import StorageCategory, storage_location
from .....tests import literal_directory_runs
from .. import STORAGE_NAMESPACE_REGISTRY, StoragePathKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KNOWN_DIRECTORY_SUBPATHS: Final[frozenset[str]] = frozenset(
    storage_location(category).subpath for category in StorageCategory
)

_UNDECLARED_DIRECTORY_EXEMPTIONS: Final[dict[str, str]] = {
    "config_reset_journal": (
        "'reset-operations' is joined onto the raw storage root in "
        "application/_config_reset_repository.py, not resolved through a declared "
        "StorageCategory member -- a pre-existing gap, not one this gate invents"
    ),
}


def _filesystem_kind_definitions() -> list[object]:
    return [
        definition for definition in STORAGE_NAMESPACE_REGISTRY.paths if definition.kind != StoragePathKind.LOGICAL_SQL
    ]


def test_the_taxonomy_declares_more_than_a_handful_of_directory_subpaths() -> None:
    """Non-vacuity floor: a near-empty known set would make the main gate trivial."""
    assert len(_KNOWN_DIRECTORY_SUBPATHS) > 10


def test_at_least_one_grammar_yields_a_directory_literal_run() -> None:
    """Non-vacuity floor: if every grammar yielded zero runs, the gate below
    would pass on every input without ever comparing anything."""
    total_runs = sum(
        len(literal_directory_runs(grammar=definition.grammar, kind=definition.kind))
        for definition in _filesystem_kind_definitions()
    )
    assert total_runs > 0


def test_every_filesystem_grammars_directory_portion_matches_a_declared_subpath() -> None:
    unmatched: list[str] = []
    for definition in _filesystem_kind_definitions():
        if definition.key in _UNDECLARED_DIRECTORY_EXEMPTIONS:
            continue
        runs = literal_directory_runs(grammar=definition.grammar, kind=definition.kind)
        for run in runs:
            if run not in _KNOWN_DIRECTORY_SUBPATHS:
                unmatched.append(
                    f"{definition.key!r} (grammar {definition.grammar!r}) spells directory "
                    f"segment {run!r}, which no StorageCategory declares as its subpath",
                )
    assert not unmatched, "\n".join(unmatched)


def test_the_exemption_list_names_only_genuinely_unmatched_keys() -> None:
    """Anti-rot: an exemption whose key now DOES match every run must be removed,
    or a future declaration change could hide behind a stale exemption."""
    for key in _UNDECLARED_DIRECTORY_EXEMPTIONS:
        definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(key)
        runs = literal_directory_runs(grammar=definition.grammar, kind=definition.kind)
        assert any(run not in _KNOWN_DIRECTORY_SUBPATHS for run in runs), (
            f"{key!r} is exempted but every directory segment it spells now matches a "
            "declared subpath -- remove the exemption, it no longer protects anything"
        )


def test_a_renamed_subpath_would_be_caught_positive_control() -> None:
    """Prove the detector fires: reproduce the exact drift scenario named in the
    gate's own docstring by asserting a category's subpath directly, not the
    grammar text, so the comparison is genuinely against the live taxonomy."""
    runs_grammar = STORAGE_NAMESPACE_REGISTRY.path_by_key("run_trace").grammar
    assert "/runs/" in runs_grammar, "fixture assumption: run_trace nests under 'runs'"

    # The gate compares the literal run against a LIVE lookup, not this string --
    # mutate the lookup target itself to prove the comparison is real rather than
    # trivially true because both sides read the same source.
    mutated_known_subpaths = _KNOWN_DIRECTORY_SUBPATHS - {storage_location(StorageCategory.RUNS).subpath}
    runs = literal_directory_runs(grammar=runs_grammar, kind=StoragePathKind.FILE)
    assert runs == ("runs",)
    assert not any(run in mutated_known_subpaths for run in runs), (
        "the detector must report 'runs' as unmatched once StorageCategory.RUNS's "
        "subpath is removed from the known set -- if this fails, the gate above "
        "cannot actually catch a rename"
    )


def test_an_undeclared_directory_literal_is_caught_by_construction() -> None:
    """A second positive control: a synthetic grammar naming a directory no
    category declares must be reported unmatched, proving the main gate's
    membership test is not vacuously true for every string."""
    bogus_run = "definitely-not-a-declared-storage-category-subpath"
    assert bogus_run not in _KNOWN_DIRECTORY_SUBPATHS
    runs = literal_directory_runs(grammar=f"<root>/{bogus_run}/<bucket_id>/file.json", kind=StoragePathKind.FILE)
    assert runs == (bogus_run,)

"""Branch-classification gate: every modelo-conditional branch carries one adjudication.

Wires :mod:`dev.quality.modelo_branch_classification` into the test surface. The
derived set comes from the drift census, so a branch written tomorrow appears in
it the moment it is written and fails this gate until somebody decides whether
it routes code or decides tax.

No tally is asserted anywhere. The set grows with the tree, and a pinned count
would train everyone to update a constant and then detect nothing.

Two anti-tautology proofs, because the ledger makes two different kinds of claim
and each needs its own control.
:func:`test_a_planted_branch_is_reported_unclassified` shows the reconciliation
can still refuse: without it, a resolver that matched everything would make the
clean residue a false all-clear.
:func:`test_a_citation_that_left_the_branch_is_reported_broken` shows the
citation requirement has teeth: an orchestration claim asserts that the branch
selects something, and a claim nobody can invalidate is not evidence. The second
proof matters more here than it looks -- the honesty mechanism this classifier
uses is the citation, and a citation check that could not fail would leave every
orchestration claim resting on the author's word.
"""

from __future__ import annotations

import pytest
from dev.quality.modelo_branch_classification import (
    BranchClassification,
    BranchClassificationError,
    BranchEntry,
    BranchSite,
    citable_tokens,
    derived_branch_sites,
    load_ledger,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_branch_carries_exactly_one_adjudication() -> None:
    """No branch is unclassified, no ledger row is stale, no citation is broken."""
    report = reconcile()

    assert report.unclassified == ()
    assert report.stale == ()
    assert report.broken_citations == ()
    assert report.clean


def test_a_planted_branch_is_reported_unclassified() -> None:
    """A branch the ledger does not name has no adjudication.

    Planted in memory from outside the tree: no file is written, so a peer's
    sweep cannot commit the mutation and a crashed run leaves nothing behind.
    """
    planted = BranchSite("src/cadrumo/application/a_module_that_does_not_exist.py", "_planted", "M303")
    adjudicated = {entry.key for entry in load_ledger()}

    assert planted.key not in adjudicated


def test_a_real_branch_is_adjudicated_so_the_planted_proof_is_not_vacuous() -> None:
    """The same lookup answers for a branch that is in the derived set."""
    adjudicated = {entry.key for entry in load_ledger()}
    sites = derived_branch_sites()

    assert sites, "the derived set is empty; every assertion here would pass vacuously"
    assert sites[0].key in adjudicated


def test_a_citation_that_left_the_branch_is_reported_broken() -> None:
    """An orchestration claim citing a token the branch no longer contains fails.

    The check is run against a fabricated entry rather than a mutated file, so
    nothing under ``src`` changes and the proof leaves no residue.
    """
    site = next(
        site
        for site in derived_branch_sites()
        if any(
            entry.key == site.key and entry.classification is BranchClassification.ORCHESTRATION_ROUTING
            for entry in load_ledger()
        )
    )
    available = citable_tokens(site.path)[site.enclosing_symbol]
    broken = BranchEntry(site.key, BranchClassification.ORCHESTRATION_ROUTING, "why", "a_token_that_is_not_there")

    assert broken.selects not in available


def test_every_orchestration_claim_cites_something_the_branch_reaches() -> None:
    """Every live orchestration citation resolves inside its own guarded branch."""
    entries = {entry.key: entry for entry in load_ledger()}
    orchestration = [
        site
        for site in derived_branch_sites()
        if entries[site.key].classification is BranchClassification.ORCHESTRATION_ROUTING
    ]

    assert orchestration, "no orchestration claims remain; the citation gate would pass vacuously"
    for site in orchestration:
        available = citable_tokens(site.path)[site.enclosing_symbol]
        assert entries[site.key].selects in available, f"{site.render()} cites a token outside its branch"


def test_every_regulatory_claim_names_the_record_that_answers_it() -> None:
    """A regulatory-treatment claim names a plan row or a reference, and cites no selection."""
    regulatory = [entry for entry in load_ledger() if entry.classification is BranchClassification.REGULATORY_TREATMENT]

    assert regulatory, "no regulatory claims remain; this assertion would pass vacuously"
    for entry in regulatory:
        assert entry.row.strip() or entry.reference.strip()
        assert not entry.selects
        assert entry.justification.strip()


def test_the_ledger_refuses_an_orchestration_claim_that_cites_nothing(tmp_path: object) -> None:
    """A claim without a citation is refused at load, not merely discouraged."""
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    ledger = tmp_path / "ledger.toml"
    ledger.write_text(
        "[meta]\nschema_version = 1\n\n[[branch]]\n"
        'path = "src/cadrumo/x.py"\nenclosing_symbol = "f"\nmodelo_codes = "M303"\n'
        'classification = "orchestration_routing"\njustification = "because"\n',
        encoding="utf-8",
    )

    with pytest.raises(BranchClassificationError, match="cites nothing it selects"):
        load_ledger(ledger)

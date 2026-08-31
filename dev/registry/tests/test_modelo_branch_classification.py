"""Gate: every modelo-conditional branch outside the registry is adjudicated exactly once.

A branch outside the registry package that asks which modelo it is holds either
orchestration routing or a regulatory rule, and the two are indistinguishable by
inspection. This gate refuses to let the ambiguity persist silently: the branch
set is derived mechanically from the core ``Modelo`` enum, and every derived
site must carry a written adjudication.

The gate is on the PROPERTY -- every derived site is adjudicated -- never on a
tally. A count would encode this moment and then detect nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..analysis.modelo_branch_classification import (
    BranchAdjudication,
    BranchClassification,
    BranchLedgerError,
    BranchSite,
    derive_branch_sites,
    load_ledger,
    modelo_codes,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_derivation_yields_a_non_empty_branch_set() -> None:
    """An empty derivation would make every assertion below vacuously true."""
    sites = derive_branch_sites()

    assert sites, (
        "the modelo-conditional branch derivation yielded nothing; a gate over an empty set is not a green gate"
    )


def test_the_derivation_keys_on_the_core_modelo_enum() -> None:
    """Every derived site names a modelo the core enum actually declares.

    This is what makes the detector widen when a modelo is added rather than
    needing an edit here.
    """
    codes = modelo_codes()
    declared = {f"M{code}" for code in codes}

    offenders = [site.key for site in derive_branch_sites() if not set(site.modelo_codes).issubset(declared)]

    assert offenders == [], f"derived sites naming a non-enum modelo member: {offenders}"


def test_every_derived_branch_is_adjudicated_exactly_once() -> None:
    """No derived modelo-conditional branch may go unclassified.

    Closing a red here means READING the branch and writing which it is. It
    never means deleting the row: a site the derivation still yields and the
    ledger does not name is exactly the state this gate exists to refuse.
    """
    unclassified, stale = reconcile()

    assert unclassified == (), (
        f"{len(unclassified)} modelo-conditional branch(es) outside the registry package carry no "
        f"adjudication: {list(unclassified[:10])}. Classify each as orchestration_routing or "
        "regulatory_treatment in modelo_branch_classification.toml, with a justification naming "
        "what the branch actually decides."
    )
    assert stale == (), (
        f"ledger rows the derivation no longer yields: {list(stale[:10])}. Remove them; a stale key "
        "silently stops matching the branch it adjudicated."
    )


def test_an_unadjudicated_derived_branch_refuses() -> None:
    """Anti-tautology: withhold one row and reconciliation must report it."""
    sites = derive_branch_sites()
    assert sites, "no derived sites to withhold"
    full = {
        site.key: BranchAdjudication(
            key=site.key,
            classification=BranchClassification.ORCHESTRATION_ROUTING,
            justification="synthetic",
        )
        for site in sites
    }
    withheld_key = sites[0].key
    partial = {key: row for key, row in full.items() if key != withheld_key}

    unclassified, stale = reconcile(sites, partial)

    assert unclassified == (withheld_key,), (
        f"the gate failed to report a withheld adjudication; it reported {unclassified!r}"
    )
    assert stale == ()


def test_a_ledger_row_the_derivation_no_longer_yields_refuses() -> None:
    """Anti-tautology: a stale key must be reported, not silently tolerated."""
    sites = derive_branch_sites()
    rows = {
        site.key: BranchAdjudication(
            key=site.key,
            classification=BranchClassification.ORCHESTRATION_ROUTING,
            justification="synthetic",
        )
        for site in sites
    }
    rows["src/cadrumo/gone.py::vanished::M303"] = BranchAdjudication(
        key="src/cadrumo/gone.py::vanished::M303",
        classification=BranchClassification.ORCHESTRATION_ROUTING,
        justification="synthetic",
    )

    unclassified, stale = reconcile(sites, rows)

    assert stale == ("src/cadrumo/gone.py::vanished::M303",)
    assert unclassified == ()


def test_an_adjudication_without_a_justification_refuses(tmp_path: Path) -> None:
    """A silent adjudication proves nothing and must not load."""
    ledger = tmp_path / "branches.toml"
    ledger.write_text(
        '[[branch]]\nkey = "src/cadrumo/x.py::f::M303"\n'
        'classification = "orchestration_routing"\njustification = "   "\n',
        encoding="utf-8",
    )

    with pytest.raises(BranchLedgerError, match="justification"):
        load_ledger(ledger)


def test_an_unknown_classification_refuses(tmp_path: Path) -> None:
    """Only the two adjudicated kinds are admissible."""
    ledger = tmp_path / "branches.toml"
    ledger.write_text(
        '[[branch]]\nkey = "src/cadrumo/x.py::f::M303"\nclassification = "probably_fine"\njustification = "because"\n',
        encoding="utf-8",
    )

    with pytest.raises(BranchLedgerError, match="unknown classification"):
        load_ledger(ledger)


def test_a_site_key_is_stable_against_edits_above_it() -> None:
    """The key carries no line number, so an edit above a branch cannot orphan it."""
    site = BranchSite(module="src/cadrumo/x.py", symbol="f", modelo_codes=("M303",))

    assert site.key == "src/cadrumo/x.py::f::M303"
    assert not any(part.isdigit() for part in site.key.split("::")[1:2])

"""Drift-census gate: no regulatory data ships in Python without an adjudication.

Wires :mod:`dev.quality.regulatory_drift_census` into the test surface. The
property it pins is exhaustiveness by construction: the finding set is derived
from the source tree, never from the ledger, so a rate, year set or
modelo-conditional branch introduced tomorrow appears in the census the moment
it is written and fails this gate until somebody decides what it is.

No tally is asserted. The census grows with the tree, and pinning its size would
train everyone to update a constant and then detect nothing. Every assertion
here is a property: that the residues are empty, that the detector recovers
instances known to exist, and that a re-run reproduces the census exactly.

The anti-tautology proofs are
:func:`test_a_planted_finding_is_reported_unadjudicated` and
:func:`test_the_allowlist_refuses_a_directory_scoped_entry`. The first shows the
reconciliation can still say no; without it, a resolver that matched everything
would make the clean result above a false all-clear. The second shows the
allowlist's key discipline is enforced rather than merely documented -- an
allowlist that can excuse a directory in one line is a mute button, and the
whole census would then be measuring how much prose somebody was willing to
write.

The test surface is deliberately outside the adjudicated scope. It carries
roughly fifteen thousand findings, almost all of them expected values a test
takes from an external authority, which the quality-gates rule requires it to
carry. That scope is measured and reported in the census audit rather than
adjudicated here, and :func:`test_the_test_surface_is_measured_not_ignored`
keeps the exclusion from becoming silent.
"""

from __future__ import annotations

import pytest
from dev.quality.regulatory_drift_census import (
    Disposition,
    DriftCensusError,
    Finding,
    FindingKind,
    census,
    load_adjudications,
    reconcile,
    render_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Files known to carry regulatory data in Python, each named by the plan row
#: this census executes. The detector recovering them is what makes a clean
#: residue mean "adjudicated" rather than "blind".
_KNOWN_INSTANCES: tuple[tuple[str, FindingKind], ...] = (
    ("src/cadrumo/domain/calculations/registry/_applicability.py", FindingKind.MODELO_KEYED_MAPPING_ENTRY),
    ("src/cadrumo/domain/calculations/registry/_m303_orden_constants.py", FindingKind.YEAR_SET),
    ("src/cadrumo/domain/calculations/registry/_m303_orden_constants.py", FindingKind.DECIMAL_LITERAL),
    ("dev/registry/_export_tree.py", FindingKind.DESIGN_PROSE_GRAMMAR),
    ("dev/registry/render_profiles", FindingKind.DEV_RESIDENT_REGULATORY_DATA),
)


def test_every_finding_carries_exactly_one_adjudication() -> None:
    """No finding is unadjudicated, no ledger row is stale, no match is ambiguous."""
    report = reconcile()

    assert report.unadjudicated == ()
    assert report.stale == ()
    assert report.ambiguous == ()
    assert report.clean


def test_the_census_reproduces_itself_exactly() -> None:
    """A re-run yields the same findings in the same order.

    A census whose output moved between runs could not be diffed, and the
    campaign's flip is gated on this census reporting zero residue -- which is
    only meaningful if two people running it get the same answer.
    """
    first = census()
    second = census()

    assert first == second
    assert render_ledger(first) == render_ledger(second)


@pytest.fixture(scope="module")
def recovered_census() -> tuple[Finding, ...]:
    """Run the census ONCE for the parametrized recovery cases.

    The census scans the production tree and measured ~19s a run, so the
    parametrized test below paid it once per case for an answer that does not
    vary with the parameters -- they filter one shared result by path and kind.

    Deliberately NOT applied to ``test_the_census_reproduces_itself_exactly``,
    and ``census`` is deliberately left unmemoised at its definition. That test
    calls it twice precisely to prove two runs agree; serving both calls from
    one cached result would make it compare an object with itself and pass no
    matter how non-deterministic the census became. The redundancy here is
    waste, but the redundancy there is the measurement.
    """
    return census()


@pytest.mark.parametrize(("path", "kind"), _KNOWN_INSTANCES, ids=lambda value: str(value).rsplit("/", 1)[-1])
def test_the_detector_recovers_known_regulatory_data(
    path: str,
    kind: FindingKind,
    recovered_census: tuple[Finding, ...],
) -> None:
    """Each file the plan names as carrying regulatory data yields a finding of the right kind."""
    matching = [f for f in recovered_census if f.path == path and f.kind is kind]

    assert matching, f"the detector found no {kind} in {path}; it is too weak to certify the rest"


def test_a_planted_finding_is_reported_unadjudicated() -> None:
    """The reconciliation still refuses something no ledger row covers.

    Planted as an in-memory record from outside the tree: no file is written, so
    a peer's sweep cannot commit the mutation and a crashed run leaves nothing
    behind.
    """
    planted = Finding(
        "src/cadrumo/domain/a_module_that_does_not_exist.py",
        "_planted",
        FindingKind.DECIMAL_LITERAL,
        "0.37",
    )
    adjudications = load_adjudications()

    assert not any(entry.matches(planted) for entry in adjudications)


def test_a_real_finding_is_covered_so_the_planted_proof_is_not_vacuous() -> None:
    """The same matcher answers for a finding the ledger does cover."""
    covered = Finding(
        "src/cadrumo/domain/calculations/registry/_applicability.py",
        "<module>",
        FindingKind.MODELO_KEYED_MAPPING_ENTRY,
        "_RULES[M100]",
    )
    adjudications = load_adjudications()

    assert any(entry.matches(covered) for entry in adjudications)


def test_the_allowlist_refuses_a_directory_scoped_entry(tmp_path: object) -> None:
    """A ``not_regulatory`` row that names no file and no symbol is refused at load.

    The constraint is that the allowlist is keyed by path and enclosing
    function. Enforcing it in the loader is what stops the ledger degrading into
    a directory-wide excuse.
    """
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    ledger = tmp_path / "ledger.toml"
    ledger.write_text(
        '[meta]\nschema_version = 1\n\n[[decision]]\npath = "src/cadrumo"\n'
        'disposition = "not_regulatory"\nrationale = "because"\n',
        encoding="utf-8",
    )

    with pytest.raises(DriftCensusError, match="allowlists without naming a file"):
        load_adjudications(ledger)


def test_every_decision_states_its_reason_and_its_reference() -> None:
    """No row is a bare acceptance: enrolled rows name a plan row, deferred rows a record."""
    adjudications = load_adjudications()

    assert adjudications, "the ledger is empty; every assertion about it would pass vacuously"
    for entry in adjudications:
        assert entry.rationale.strip()
        if entry.disposition is Disposition.ENROLLED:
            assert entry.row.strip()
        if entry.disposition is Disposition.DEFERRED:
            assert entry.reference.strip()
        if entry.disposition is Disposition.NOT_REGULATORY:
            assert entry.path.endswith(".py")
            assert entry.enclosing_symbol.strip()


def test_the_test_surface_is_measured_not_ignored() -> None:
    """The test scope is scannable, so its exclusion from adjudication is a stated decision.

    A scope nobody can measure is a scope nobody can argue with. This does not
    assert how large it is -- it asserts the instrument reaches it.
    """
    assert census(scope="tests")

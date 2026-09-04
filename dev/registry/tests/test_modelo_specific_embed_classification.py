"""Gate: every modelo-specific registry module carries exactly one classification.

The inventory this gate protects is exhaustive BY CONSTRUCTION rather than by
hand: the module set is derived mechanically from the core modelo enum, so a
modelo-specific module added after this gate was written lands in the derived
set on its first run and reds until it is adjudicated. A hand-maintained list
would catch a rename and never an addition.

The gate therefore proves four things, none of them a tally:

- the checked-in adjudication reconciles against the live derived set;
- the derivation itself catches a newly written module through each of its
  three independent signals, so no signal has quietly stopped working;
- every reconciliation refusal actually refuses -- an unclassified module, a
  ledger row the derivation no longer yields, a machinery claim leaving
  regulatory-literal evidence unanswered, and a dead claim something imports;
- the regulatory-literal detector still finds a live unowned embed, so a
  weakened detector cannot make the corpus look clean.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from ..analysis.modelo_embed_classification import (
    Classification,
    ClassificationEntry,
    EvidenceKind,
    ModeloModuleRecord,
    TreeOwnership,
    census,
    load_ledger,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The proven live unowned embed the classifier must reach independently. Its
#: Modelo 100 filing-year binding is still Python-resident pending its own
#: registry/application migration, so losing this evidence would hide real
#: unowned regulatory data rather than merely move campaign-owned M303 detail.
ANCHOR_EMBED = "src/cadrumo/domain/calculations/registry/applicability_modelo202.py"

_MODELO_SPECIFIC_BODIES: dict[str, str] = {
    "module_name": '"""A modelo-named module."""\n\nVALUE = 1\n',
    "modelo_reference": (
        '"""A module reading a concrete modelo member."""\n\nfrom cadrumo.core import Modelo\n\nOWNER = Modelo.M303\n'
    ),
    "defined_symbol": (
        '"""A module whose name and body name no modelo."""\n\n'
        "def evaluate_m210_resolve_something() -> int:\n"
        "    return 1\n"
    ),
}


@cache
def derived() -> tuple[ModeloModuleRecord, ...]:
    """Return the live derived modelo-specific module set."""
    return census()


@cache
def adjudicated() -> tuple[ClassificationEntry, ...]:
    """Return the checked-in adjudication ledger."""
    return load_ledger()


def test_every_derived_module_is_adjudicated_exactly_once() -> None:
    """The live derived set and the checked-in adjudication agree completely."""
    assert reconcile(derived(), adjudicated()) == ()
    assert {record.path for record in derived()} == {entry.path for entry in adjudicated()}


@pytest.mark.parametrize("signal", sorted(_MODELO_SPECIFIC_BODIES))
def test_derivation_catches_a_newly_written_module_by_each_signal(
    signal: str,
    tmp_path: Path,
) -> None:
    """A module written after this gate lands in the derived set on its own."""
    stem = "_m347_planted" if signal == "module_name" else "_planted_surface"
    (tmp_path / f"{stem}.py").write_text(_MODELO_SPECIFIC_BODIES[signal], encoding="utf-8")
    (tmp_path / "_plain_surface.py").write_text('"""No modelo anywhere."""\n\nVALUE = 1\n', encoding="utf-8")

    derived_here = census(tmp_path)

    assert [Path(record.path).name for record in derived_here] == [f"{stem}.py"]
    assert signal in {str(item) for item in derived_here[0].signals}


def test_an_unadjudicated_derived_module_refuses() -> None:
    """Dropping one adjudication reds the reconciliation, naming the module."""
    dropped = ANCHOR_EMBED
    failures = reconcile(derived(), tuple(entry for entry in adjudicated() if entry.path != dropped))

    assert any(dropped in failure and "carries no classification" in failure for failure in failures)


def test_an_adjudication_the_derivation_no_longer_yields_refuses() -> None:
    """A row for a module that stopped being modelo-specific reds, never rots."""
    retired = ClassificationEntry(
        path="src/cadrumo/domain/calculations/registry/_retired_surface.py",
        classification=Classification.MACHINERY,
        justification="A row the derivation does not yield.",
    )
    failures = reconcile(derived(), (*adjudicated(), retired))

    assert any("no longer derived as modelo-specific" in failure for failure in failures)


def test_machinery_may_not_leave_regulatory_literal_evidence_unanswered() -> None:
    """Calling a literal-bearing module machinery without a reason refuses."""
    with_evidence = next(record for record in derived() if record.evidence)
    silent = ClassificationEntry(
        path=with_evidence.path,
        classification=Classification.MACHINERY,
        justification="Machinery, with the evidence left unanswered.",
    )
    failures = reconcile(
        (with_evidence,),
        (silent,),
    )

    assert any("undispositioned" in failure for failure in failures)
    assert reconcile((with_evidence,), tuple(e for e in adjudicated() if e.path == with_evidence.path)) == ()


def test_a_dead_claim_for_an_imported_module_refuses() -> None:
    """Dead means nothing imports it, checked against the real import graph."""
    anchor = next(record for record in derived() if record.path == ANCHOR_EMBED)
    claimed_dead = ClassificationEntry(
        path=anchor.path,
        classification=Classification.DEAD,
        justification="Claimed dead while the tree still imports it.",
    )
    failures = reconcile((anchor,), (claimed_dead,))

    assert any("classified dead but imported by" in failure for failure in failures)


def test_an_embed_may_not_misdeclare_the_ownership_of_its_destination_tree() -> None:
    """A queued embed cannot be filed under a tree its modelos do not reach."""
    anchor = next(record for record in derived() if record.path == ANCHOR_EMBED)
    misfiled = ClassificationEntry(
        path=anchor.path,
        classification=Classification.REGULATORY_DATA_EMBED,
        justification="Correctly an embed, wrongly declared campaign-owned.",
        destination="registry authoring tree",
        tree_ownership=TreeOwnership.CAMPAIGN_OWNED,
    )
    failures = reconcile((anchor,), (misfiled,))

    assert any("not campaign-owned" in failure for failure in failures)


def test_the_detector_still_finds_the_anchor_embed() -> None:
    """The known regulatory literals stay detected and adjudicated as an embed.

    Re-anchored from ``inventory_bindings.py``, which stopped being an embed once
    its ``filing_year`` pin was retired in favour of the bindings the Modelo 100
    revision declares. The anchor's job is unchanged: pin the detector to a module
    that genuinely carries regulatory content, so the enrolment gate above cannot
    pass by finding nothing anywhere.

    Modelo 202's modality rule is the replacement because it is unambiguous --
    the four reason constants are operator-facing Spanish sentences citing LIS
    art. 40.2 and 40.3, which is regulatory prose by any reading, and the module
    exists only to state that one modelo's rule.
    """
    anchor = next(record for record in derived() if record.path == ANCHOR_EMBED)
    by_symbol = {(item.symbol, item.kind) for item in anchor.evidence}

    assert (
        "_MODELO_202_ART_40_3_MANDATORY_REASON",
        EvidenceKind.REGULATORY_PROSE_LITERAL,
    ) in by_symbol

    entry = next(item for item in adjudicated() if item.path == ANCHOR_EMBED)
    assert entry.classification is Classification.REGULATORY_DATA_EMBED
    assert entry.tree_ownership is TreeOwnership.UNOWNED


def test_a_half_written_peer_module_costs_one_file_not_the_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The race the guard anticipated was the less likely one.

    ``FileNotFoundError`` was caught because peers create and remove scratch
    modules under the walked tree, but parsing sat outside that guard - so a
    peer caught mid-write, which leaves a file that exists and does not parse,
    raised out of the whole index build instead of costing one file's imports.
    """
    from ..analysis.modelo_embed_classification import importer_index

    (tmp_path / "sound.py").write_text("import json" + chr(10), encoding="utf-8")
    (tmp_path / "half_written.py").write_text("from cadrumo import (" + chr(10), encoding="utf-8")

    index = importer_index(tmp_path)

    assert "json" in index, "the readable module's imports were lost with the broken one"
    error = capsys.readouterr().err
    assert "missing from this index" in error
    assert "half_written.py" in error


def test_a_readable_tree_indexes_silently(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice on every run would carry no information."""
    from ..analysis.modelo_embed_classification import importer_index

    (tmp_path / "sound.py").write_text("import json" + chr(10), encoding="utf-8")

    assert importer_index(tmp_path)
    assert capsys.readouterr().err == ""

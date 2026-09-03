"""Real-behaviour tests for the revision re-render comparison.

Every case drives the bundled registry and the real generation pipeline. The
corpus supplies both outcomes this module must distinguish, so no fixture is
constructed: one revision reproduces exactly, four differ only in their
provenance attestation, and two differ in a record file.
"""

from __future__ import annotations

import pathlib
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.render_check import compare_revision_against_committed

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Named once per module, as this tree requires, rather than repeated at each
#: read site where a typo would be a silent decode change.
_UTF_8: Final[str] = "utf-8"


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_reproducing_revision_is_reported_conclusively(authority: ValidatedRegistryAuthority) -> None:
    """A tree that matches its authored inputs carries no record that means something else.

    Byte equality is not asserted, and that is a deliberate weakening of the
    wrong axis. A closed-vocabulary conversion changed how one field is quoted
    across every generated tree without changing any value, so byte equality
    now fails on trees that are perfectly correct. What must hold is that every
    byte difference is accounted for - as the attestation or as spelling - and
    that nothing is left over. A changed value would land in
    ``record_differing`` and fail here.
    """
    comparison = compare_revision_against_committed(authority, modelo="303", revision="2025")
    assert comparison.semantically_reproduced
    assert comparison.record_differing == ()
    accounted = {*comparison.serialization_only, "_generation.provenance.json"}
    assert set(comparison.differing) <= accounted
    assert comparison.only_committed == () and comparison.only_rendered == ()


def test_a_stale_attestation_is_separated_from_record_drift(authority: ValidatedRegistryAuthority) -> None:
    """A tree differing only in its manifest ships correct records.

    This is the class that is safe to republish, and separating it is the whole
    point: the remedy for a stale attestation is regeneration, and the remedy
    for record drift is emphatically not.

    Pinned to a dispositioned tree. This one is safe to republish, so it will be,
    and this test fails when it is - that failure is the republication, not a
    regression. Three siblings sit in the same class and any of them replaces the
    coordinate; if the class is ever empty, construct the case rather than
    dropping it, because a provenance-only tree that nobody can produce is
    exactly when the separation from record drift stops being exercised.
    """
    comparison = compare_revision_against_committed(authority, modelo="296", revision="2024-y-siguientes")
    assert not comparison.reproduced
    assert comparison.semantically_reproduced
    assert comparison.record_differing == ()


def test_record_drift_is_reported_as_such(authority: ValidatedRegistryAuthority) -> None:
    """A tree whose record bytes differ is never reported as provenance-only.

    Both revisions of this informativa ship a declarado record that repeats over
    binding rows, which the current inputs no longer produce. Republishing them
    would collapse every counterparty into one record, so a caller must be able
    to tell this apart from a stale manifest before regenerating anything.

    Pinned to a live defect whose remedy is authored on the map, not here: the
    pipeline's own refusal names the three things the inputs must carry before
    this tree may be republished. When they do, both revisions reproduce and this
    test fails, which is the repair landing. No other tree is in this class, so
    the replacement must be constructed - a copy of a real revision with one
    record's repeat removed. Do not delete it: this is the assertion that keeps
    an unsafe republication from being reported as a stale manifest.
    """
    for revision in ("2011-2024", "2025-y-siguientes"):
        comparison = compare_revision_against_committed(authority, modelo="347", revision=revision)
        assert not comparison.reproduced
        assert not comparison.provenance_only
        assert comparison.record_differing


def test_a_revision_without_a_generated_layout_is_refused_by_name(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A revision that cannot be rendered refuses rather than comparing nothing.

    The coordinate is derived rather than named. This test previously pinned
    modelo 200's 2025 revision, which had no generated layout until someone
    published one - at which point the test failed for the best possible reason
    and said nothing useful about the refusal it exists to prove.

    Deriving it means the fixture cannot be invalidated by legitimate progress,
    and the population is asserted first so that a corpus where every revision
    had a layout would fail loudly rather than pass over an empty search.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    without_layout = [
        (modelo, revision_id)
        for modelo in sorted(str(code) for code in registry_modelo_codes())
        for revision_id, revision in authority.modelo(modelo).revisions.items()
        if not revision.export_layouts
    ]

    assert without_layout, "no revision lacks a generated layout, so this refusal cannot be exercised"

    modelo, revision_id = without_layout[0]
    with pytest.raises(ValueError, match="no export layout"):
        compare_revision_against_committed(authority, modelo=modelo, revision=revision_id)


def test_every_record_drifting_tree_is_dispositioned_and_every_disposition_is_live(
    authority: ValidatedRegistryAuthority,
) -> None:
    """No tree unsafe to republish sits unexplained, and no explanation outlives its cause.

    The ledger carries the record-drifting class alone. That is the class where
    regenerating ships something worse than what is published, so each member
    owes a written account, and the gate refuses in both directions: a drifting
    tree with no row fails, and a row whose tree has been repaired fails too.

    Manifest-only staleness is asserted rather than ledgered, in the companion
    test below. The two classes are separated here because they fail for
    different reasons and want different work: one is a repair, the other a
    republication.

    It stores no count and no ceiling. Two rows today is not the contract.
    """
    import tomllib

    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..pipeline.render_check import compare_revision_against_committed

    dispositions_path = pathlib.Path(__file__).resolve().parent.parent / "pipeline" / "generated_tree_dispositions.toml"
    declared = tomllib.loads(dispositions_path.read_text(encoding=_UTF_8))
    dispositioned = {key: value[0] for key, value in declared.items() if key != "schema_version"}

    assert all(row["class"] == "record_drift" for row in dispositioned.values()), (
        "this ledger carries the record-drifting class alone; a provenance-only row belongs to the assertion below"
    )

    drifting: set[str] = set()
    for code in sorted(str(item) for item in registry_modelo_codes()):
        for revision_id in authority.modelo(code).revisions:
            if not bundled_path("registry", "aeat", "modelos", code, "revisions", revision_id, "export").is_dir():
                continue
            comparison = compare_revision_against_committed(authority, modelo=code, revision=revision_id)
            if comparison.disposition_class == "record_drift":
                drifting.add(f"{code}/{revision_id}")

    assert drifting == set(dispositioned), (
        f"trees whose records drifted and carry no disposition: {sorted(drifting - set(dispositioned))}; "
        f"dispositions whose tree no longer drifts: {sorted(set(dispositioned) - drifting)}"
    )
    assert all(dispositioned[name]["reason"].strip() for name in dispositioned), "every disposition states a reason"


def test_every_manifest_stale_tree_really_does_reproduce_its_records(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The class that is safe to republish is asserted safe, not individually excused.

    Manifest staleness arrives in bulk - a single generator refactor invalidated
    twenty-one attestations at once - so demanding a written reason for each
    would turn the ledger into churn and teach a reader to add rows rather than
    read them. What actually matters about this class is the claim that makes it
    safe, and that claim is checkable: the records must reproduce byte-for-byte,
    with nothing differing but the manifest.

    A tree that reports itself provenance-only while a record differs fails here,
    which is the same defect the ledger catches from the other side. The
    population is reported by the screen; only the property is gated.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..pipeline.render_check import compare_revision_against_committed

    unsafe: list[str] = []
    seen = 0
    for code in sorted(str(item) for item in registry_modelo_codes()):
        for revision_id in authority.modelo(code).revisions:
            if not bundled_path("registry", "aeat", "modelos", code, "revisions", revision_id, "export").is_dir():
                continue
            comparison = compare_revision_against_committed(authority, modelo=code, revision=revision_id)
            if comparison.disposition_class != "provenance_only":
                continue
            seen += 1
            if comparison.record_differing or not comparison.semantically_reproduced:
                unsafe.append(f"{code}/{revision_id}")

    assert seen, "no tree is manifest-stale, so this assertion is exercising nothing"
    assert not unsafe, f"trees called provenance-only whose records do not in fact reproduce: {unsafe}"

"""Real-behaviour tests for the revision re-render comparison.

Every case drives the bundled registry and the real generation pipeline. The
corpus supplies both outcomes this module must distinguish, so no fixture is
constructed: one revision reproduces exactly, four differ only in their
provenance attestation, and two differ in a record file.
"""

from __future__ import annotations

import pathlib

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.render_check import compare_revision_against_committed

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


def test_every_non_reproducing_tree_is_dispositioned_and_every_disposition_is_live(
    authority: ValidatedRegistryAuthority,
) -> None:
    """No published tree sits in an unexplained state, and no explanation outlives its cause.

    The gate refuses in both directions. A tree that stops reproducing without a
    row fails, which is the point: an unexplained difference in filing data is
    exactly what nobody notices. A row whose tree has been repaired fails too,
    so a disposition cannot linger and quietly excuse a condition that returns.

    It stores no count and no ceiling. Six rows today is not the contract;
    every tree being accounted for is.
    """
    import tomllib

    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..pipeline.render_check import compare_revision_against_committed

    dispositions_path = pathlib.Path(__file__).resolve().parent.parent / "pipeline" / "generated_tree_dispositions.toml"
    declared = tomllib.loads(dispositions_path.read_text(encoding="utf-8"))
    dispositioned = {key: value[0] for key, value in declared.items() if key != "schema_version"}

    observed: dict[str, str] = {}
    for code in sorted(str(item) for item in registry_modelo_codes()):
        for revision_id in authority.modelo(code).revisions:
            if not bundled_path("registry", "aeat", "modelos", code, "revisions", revision_id, "export").is_dir():
                continue
            comparison = compare_revision_against_committed(authority, modelo=code, revision=revision_id)
            state = comparison.disposition_class
            if state is None:
                continue
            observed[f"{code}/{revision_id}"] = state

    assert set(observed) == set(dispositioned), (
        f"trees that do not reproduce and carry no disposition: {sorted(set(observed) - set(dispositioned))}; "
        f"dispositions whose tree now reproduces: {sorted(set(dispositioned) - set(observed))}"
    )
    misclassified = {name: observed[name] for name in observed if dispositioned[name]["class"] != observed[name]}
    assert not misclassified, f"dispositions whose class no longer matches the observed state: {misclassified}"
    assert all(dispositioned[name]["reason"].strip() for name in dispositioned), "every disposition states a reason"

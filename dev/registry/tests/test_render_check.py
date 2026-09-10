"""Real-behaviour tests for the revision re-render comparison.

Every case drives the bundled registry and the real generation pipeline. Safe
manifest-only drift is repaired through the canonical publisher; the remaining
record drift stays pinned to its exact source authority.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline.generated_tree_dispositions import disposition_ledger_from_path, record_drift_dispositions
from ..pipeline.render_check import (
    compare_export_tree_roots,
    compare_revision_against_committed,
    revision_render_inputs,
)

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

    # This revision now differs in its RECORDS, and legitimately: the generator
    # derives a field's sign from the official type column where it used to
    # write a constant, so a fresh render no longer matches bytes that were
    # produced before the correction. The difference is the defect being fixed.
    #
    # It is not silently tolerated. A disposition row states it, source-pinned
    # and self-retiring, and this test reads that row rather than asserting a
    # reproduction that stopped being true. The day the revision is republished
    # the row retires and the conclusive assertions below take over again.
    disposition = {item.subject: item for item in record_drift_dispositions()}.get("303/2025")
    if disposition is not None:
        assert comparison.disposition_class == "record_drift", (
            "303/2025 carries a drift disposition but no longer drifts; retire the row"
        )
        assert comparison.record_differing, "a drift row must name a real record difference"
        return

    assert comparison.semantically_reproduced
    assert comparison.record_differing == ()
    accounted = {*comparison.serialization_only, "_generation.provenance.json"}
    assert set(comparison.differing) <= accounted
    assert comparison.only_committed == () and comparison.only_rendered == ()


def test_a_published_revision_uses_its_source_defect_adjudication(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The read-only comparison reproduces M390 through its official-typo adjudication."""
    comparison = compare_revision_against_committed(authority, modelo="390", revision="2022")

    # Same correction as the revision above: the adjudication this test exists to
    # exercise is still applied, but the tree no longer reproduces byte for byte
    # because the sign is now derived from the official type column. The
    # disposition row carries that, so this reads the row rather than asserting a
    # reproduction the correction retired.
    disposition = {item.subject: item for item in record_drift_dispositions()}.get("390/2022")
    if disposition is not None:
        assert comparison.disposition_class == "record_drift", (
            "390/2022 carries a drift disposition but no longer drifts; retire the row"
        )
        assert comparison.only_committed == () and comparison.only_rendered == (), (
            "a drift is a changed record, never a missing or an extra one"
        )
        return

    assert comparison.reproduced
    assert comparison.only_committed == () and comparison.only_rendered == ()


def test_a_republished_attestation_matches_its_current_authorities(authority: ValidatedRegistryAuthority) -> None:
    """A repaired tree reproduces both its records and its generation manifest."""
    comparison = compare_revision_against_committed(authority, modelo="296", revision="2024-y-siguientes")
    assert comparison.reproduced
    assert comparison.semantically_reproduced
    assert comparison.record_differing == ()


def test_record_drift_is_reported_as_such(tmp_path: Path) -> None:
    """A tree whose record bytes differ is never reported as provenance-only.

    Modelo 347's declarado record repeats over binding rows, once per
    counterparty. Republishing a tree that dropped the repeat would collapse
    every counterparty into one record, so a caller must be able to tell that
    apart from a stale manifest before regenerating anything.

    No shipped tree is in this class any more, so the case is constructed: a
    copy of the real 347 tree whose declarado record has lost its repeat,
    compared against the real one. Do not delete it: this is the assertion that
    keeps an unsafe republication from being reported as a stale manifest.
    """
    real = bundled_path("registry", "aeat", "modelos", "347", "revisions", "2025-y-siguientes", "export")
    drifted = tmp_path / "export"
    shutil.copytree(real, drifted)
    declarado = drifted / "0002-record-m347-declarado.toml"
    original = declarado.read_text(encoding="utf-8")
    declarado.write_text(original.replace("repeat = 'binding_rows'\n", ""), encoding="utf-8")
    assert declarado.read_text(encoding="utf-8") != original

    comparison = compare_export_tree_roots(
        modelo="347",
        revision="2025-y-siguientes",
        layout_id="generated-modelo-347-2025-y-siguientes-fichero",
        committed_root=drifted,
        rendered_root=real,
    )

    assert not comparison.reproduced
    assert not comparison.provenance_only
    assert comparison.record_differing == ("0002-record-m347-declarado.toml",)
    assert comparison.disposition_class == "record_drift"


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


def test_a_cited_source_of_the_wrong_kind_is_refused_by_name_not_treated_as_the_design(
    authority: ValidatedRegistryAuthority,
) -> None:
    """An explicit ``source_ref`` that exists but is not a record-design source refuses.

    A revision cites more than the record design: procedure instructions, the
    printed form, the taxpayer calendar. Every one of those is a real row in
    ``catalogues.sources`` and a real member of the revision's own
    ``source_refs`` -- so a caller passing one by mistake is not naming a typo,
    it is naming a source that genuinely exists and genuinely belongs to this
    revision, just not as its record design. Accepting it silently would derive
    an epoch, root and record shape from the wrong document; the guard must
    name what is actually wrong (wrong kind) rather than fail later on a
    downstream symptom (no design epoch) that does not say why.

    The coordinate is derived rather than named, for the same reason as the
    sibling refusal above: a corpus where no revision cites a non-design
    source alongside its design would make this refusal unreachable, and that
    must fail loudly rather than pass over nothing.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    sources = authority.catalogues.sources
    candidates = [
        (modelo, revision_id, str(ref))
        for modelo in sorted(str(code) for code in registry_modelo_codes())
        for revision_id, revision in authority.modelo(modelo).revisions.items()
        for ref in revision.source_refs
        if (source := sources.get(ref)) is not None and source.kind != "record_design"
    ]

    assert candidates, "no revision cites a non-record-design source, so this refusal cannot be exercised"

    modelo, revision_id, wrong_kind_ref = candidates[0]
    with pytest.raises(ValueError, match="does not declare record-design source"):
        revision_render_inputs(authority, modelo=modelo, revision=revision_id, source_ref=wrong_kind_ref)


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
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..pipeline.render_check import compare_revision_against_committed

    dispositions = record_drift_dispositions()
    dispositioned = {row.subject: row for row in dispositions}
    for row in dispositions:
        revision = authority.modelo(row.modelo).revisions[row.revision]
        source = authority.catalogues.sources.get(row.source_ref)
        assert row.source_ref in revision.source_refs, f"{row.subject}: disposition source is not revision-owned"
        assert source is not None, f"{row.subject}: disposition source is absent"
        assert source.sha256 == row.source_sha256, f"{row.subject}: disposition source was reissued; reconsider the pin"

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
    assert all(
        dispositioned[name].reason.strip() and dispositioned[name].reconsideration_condition.strip()
        for name in dispositioned
    ), "every disposition states a reason and reconsideration condition"


def test_every_manifest_stale_tree_really_does_reproduce_its_records(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Every remaining manifest-stale tree differs only in semantically reproduced output."""
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from cadrumo.core.resources.bundled_data import bundled_path

    from ..pipeline.render_check import compare_revision_against_committed

    unsafe: list[str] = []
    for code in sorted(str(item) for item in registry_modelo_codes()):
        for revision_id in authority.modelo(code).revisions:
            if not bundled_path("registry", "aeat", "modelos", code, "revisions", revision_id, "export").is_dir():
                continue
            comparison = compare_revision_against_committed(authority, modelo=code, revision=revision_id)
            if comparison.disposition_class == "provenance_only" and not comparison.semantically_reproduced:
                unsafe.append(f"{code}/{revision_id}")

    assert not unsafe, f"trees called provenance-only whose records do not reproduce semantically: {unsafe}"


_VALID_SHA = "0" * 64


def _ledger_text(rows: str, *, version: int = 4) -> str:
    return f"schema_version = {version}\n{rows}"


_REFUSAL_ROW = f'''
[[dispositions]]
kind = "render_refusal"
modelo = "390"
revision = "2022"
source_ref = "aeat-dr-390-2022"
source_sha256 = "{_VALID_SHA}"
refusal_marker = "could not determine the sign"
reason = "The generator declines to emit a sign it did not determine."
reconsideration_condition = "Remove when the sign is derived from the official type column."
'''

_DRIFT_ROW = f'''
[[dispositions]]
kind = "record_drift"
modelo = "347"
revision = "2011-2024"
source_ref = "aeat-dr-347-2011"
source_sha256 = "{_VALID_SHA}"
remedy = "repair_inputs"
differing_records = 1
reason = "Shipped bytes are right and the inputs are not."
reconsideration_condition = "Remove when the inputs reproduce the repeat."
'''

_CONTRADICTION_ROW = f'''
[[dispositions]]
kind = "type_column_contradiction"
modelo = "390"
revision = "2025"
source_ref = "aeat-dr-390-2025"
source_sha256 = "{_VALID_SHA}"
derivation_code = "numeric-note-governed-amount-v1"
field_count = 80
reason = "The tree reproduces and its inputs contradict the type column."
reconsideration_condition = "Remove when the schema carries a domain on a signed field."
'''


def test_the_ledger_separates_a_refusal_from_a_drift(tmp_path: Path) -> None:
    """Both classes load, and each keeps its own identity.

    A refused tree does not render at all; a drifting tree renders and disagrees.
    Collapsing them would let a refusal be excused by a pin written for drift.
    """
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_DRIFT_ROW + _REFUSAL_ROW), encoding="utf-8")

    loaded = disposition_ledger_from_path(path)

    kinds = {item.subject: item.kind for item in loaded}
    assert kinds == {"347/2011-2024": "record_drift", "390/2022": "render_refusal"}


def test_a_refusal_row_without_a_named_cause_is_refused(tmp_path: Path) -> None:
    """An empty marker would let a row absorb ANY later refusal in the same tree."""
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_REFUSAL_ROW.replace('"could not determine the sign"', '""')), encoding="utf-8")

    with pytest.raises(ValidationError):
        disposition_ledger_from_path(path)


def test_a_row_declaring_no_class_is_refused(tmp_path: Path) -> None:
    """The class is discriminating, so an untagged row cannot be admitted silently."""
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_DRIFT_ROW.replace('kind = "record_drift"\n', "")), encoding="utf-8")

    with pytest.raises(ValidationError):
        disposition_ledger_from_path(path)


def test_an_unknown_class_is_refused(tmp_path: Path) -> None:
    """A third class would otherwise be admitted and then handled by nothing."""
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_DRIFT_ROW.replace("record_drift", "manifest_only")), encoding="utf-8")

    with pytest.raises(ValidationError):
        disposition_ledger_from_path(path)


def test_one_tree_cannot_be_both_refused_and_drifting(tmp_path: Path) -> None:
    """Two rows for one subject would make the gate's verdict order-dependent."""
    collision = _REFUSAL_ROW.replace('modelo = "390"', 'modelo = "347"').replace(
        'revision = "2022"', 'revision = "2011-2024"'
    )
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_DRIFT_ROW + collision), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate subjects"):
        disposition_ledger_from_path(path)


def test_the_previous_ledger_version_is_refused(tmp_path: Path) -> None:
    """The bump is not cosmetic: version 2 rows carry no class and cannot be read as one."""
    path = tmp_path / "dispositions.toml"
    path.write_text(_ledger_text(_DRIFT_ROW.replace('kind = "record_drift"\n', ""), version=2), encoding="utf-8")

    with pytest.raises(ValidationError):
        disposition_ledger_from_path(path)

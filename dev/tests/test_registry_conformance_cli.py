"""Real-behaviour tests for the ``python -m dev.registry.conformance`` surface.

Every test here invokes the real CLI against the real bundled registry, or the
real writer against a real copy of a shipped modelo tree. Nothing is mocked,
stubbed, skipped, or marked expected-to-fail.

The proofs are written to FLIP AN ASSERTION rather than to kill a fixture. A
test that only checks a function was called proves the wiring and none of the
semantics, and an early review round caught exactly that weakness in a sibling
gate. So: the ratchet is proved by moving ONE baseline counter and
watching the same command on the same tree change its exit code; the
absence-is-not-zero rule is proved by rendering two reports differing only in a
``None`` where the other has ``0.0`` and asserting the renders differ; the
oracle attribution gap is proved by injecting one real gap record and watching
it reach all three surfaces that must show it; and the stamp rollback is proved
by making the post-write reload genuinely fail and asserting the manifest went
back ON BYTES.

That last one is a worked example of how a proof rots. It staged a
malformed sibling fragment before calling the writer, but the pre-write check
loads the same tree the post-write reload does, so the refusal landed BEFORE any
write and the restore was never reached. Every assertion still passed, because a
file that was never written is trivially unchanged. The failure now originates in
the written bytes themselves, and the mtime is pinned and asserted to MOVE, so
the case cannot silently slide back into the pre-write branch.

Registry-wide counts are asserted against the committed baseline's own floors
rather than against literals, because the registry grows: a hard-coded ``90``
would red on the next modelo revision and teach the next reader to delete the
assertion instead of reading it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from collections.abc import Sequence
from datetime import UTC, date, datetime
from inspect import signature
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner, Result

from cadrumo.application.registry import (
    RegistryConformanceProfile,
    audit_bundled_registry_conformance,
    compare_annual_casilla_population,
    compare_annual_casilla_population_for_revision,
)
from cadrumo.core import ExternalOracleCorpus, RevisionReviewStatus, scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    REVISION_GOVERNANCE_FIELDS,
    UnattributedOraclePayload,
    bundled_authority,
    load_bundled_external_oracle_inventory,
    load_modelo_directory,
)

from ..registry.conformance._stamp import (
    GOVERNANCE_KEYS,
    StampableReviewStatus,
    StampError,
    bundled_registry_root,
    revision_manifest_path,
    stamp_revision,
)
from ..registry.conformance.cli import app
from ..registry.conformance.manager import (
    COORDINATE_CLASSIFICATIONS,
    NOT_MEASURED,
    ConformanceBaseline,
    ConformanceCoordinate,
    ConformanceCoordinateMatrix,
    ConformanceProgressFloors,
    ConformanceReport,
    baseline_path,
    baseline_weakenings,
    build_conformance_report,
    build_coverage_report,
    check_conformance_ratchet,
    load_baseline,
    load_conformance_report,
    load_locale_coverage_index,
    record_baseline,
    render_audit,
    render_coverage,
    render_report,
    reviewer_attribution,
    vacuity_warning,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_STAMPED_MODELO = "130"
_STAMPED_REVISION = "2019-y-siguientes"


class _StampArguments(TypedDict, total=False):
    """Optional keyword arguments accepted by the revision stamp writer."""

    engineered_by: str
    review_status: StampableReviewStatus | RevisionReviewStatus | str
    reviewed_by: str
    reviewed_at: date


def _real_d2025_coordinate() -> ConformanceCoordinate:
    """Return the coordinate and schema evidence from the real bundled report."""
    report = load_conformance_report(validate=True)
    if report.annual_matrix is None:
        raise AssertionError("validated report must expose the finite annual matrix")
    return report.annual_matrix.coordinates[0]


@pytest.fixture(scope="module")
def validated_report() -> ConformanceReport:
    """The real conformance report over the real bundled registry."""
    return load_conformance_report(validate=True)


@pytest.fixture(scope="module")
def degraded_report() -> ConformanceReport:
    """The same registry read through the non-validating loader."""
    return load_conformance_report(validate=False)


@pytest.fixture(scope="module")
def validated_profile() -> RegistryConformanceProfile:
    """The shipped composer's own output, before this package projects it.

    Needed whole rather than as a projected report so a governance stamp can be
    moved on a REAL row and the join under test can be computed by the real
    projection rather than by the test.
    """
    return audit_bundled_registry_conformance(validate=True)


@pytest.fixture
def registry_copy(tmp_path: Path) -> Path:
    """A real copy of one shipped modelo tree, writable without touching the registry.

    The stamp verb mutates registry TOML, and stamping a shipped revision
    ``agent_reviewed`` would write a review claim nobody made — the exact
    dishonesty this feature exists to detect. So the writer is exercised against
    a byte copy of the real tree instead: real fragments, real loader, real
    schema, and no fabricated provenance left in the repository.
    """
    root = tmp_path / "registry"
    (root / "modelos").mkdir(parents=True)
    shutil.copytree(
        Path(bundled_path("registry", "aeat")) / "modelos" / _STAMPED_MODELO,
        root / "modelos" / _STAMPED_MODELO,
    )
    return root


def _manifest_of(root: Path) -> Path:
    return root / "modelos" / _STAMPED_MODELO / "revisions" / _STAMPED_REVISION / "revision.toml"


def _empty_report() -> ConformanceReport:
    """Project a genuinely empty profile through the real builder."""
    return build_conformance_report(
        RegistryConformanceProfile(rows=(), registry_validated=True),
        locale_index={},
        locale_unavailable_modelos=(),
        oracle_inventory=load_bundled_external_oracle_inventory(),
    )


# --------------------------------------------------------------------------- #
# report and coverage screens
# --------------------------------------------------------------------------- #


def test_report_exits_zero_and_renders_a_row_for_every_composed_revision() -> None:
    """The screen renders one greppable row per revision and never gates."""
    result = CliRunner().invoke(app, ["report"])

    assert result.exit_code == 0, result.stdout
    floors = load_baseline().floors
    rows = [line for line in result.stdout.splitlines() if line.startswith("row ")]
    assert len(rows) >= floors.composed_revisions
    assert result.stdout.startswith("summary registry_validated=true ")
    assert "warning rows=0" not in result.stdout


def test_report_json_keeps_the_finite_annual_matrix_separate_from_the_portfolio() -> None:
    """The real report exposes only the provisional D2025 coordinate today."""
    result = CliRunner().invoke(app, ["report", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    matrix = payload["annual_matrix"]
    assert payload["modelo_count"] > len(matrix["coordinates"])
    assert payload["revision_count"] > len(matrix["coordinates"])
    assert len(matrix["coordinates"]) == 1
    coordinate = matrix["coordinates"][0]
    assert {
        key: coordinate[key]
        for key in (
            "modelo",
            "filing_year",
            "period",
            "law_selected_revision",
            "classification",
            "provisional",
            "authority_scope",
        )
    } == {
        "modelo": "100",
        "filing_year": 2025,
        "period": "0A",
        "law_selected_revision": "2025",
        "classification": "not_yet_measured",
        "provisional": True,
        "authority_scope": "inspection_only",
    }
    comparison = coordinate["schema_comparison"]
    assert {
        key: comparison[key]
        for key in (
            "modelo",
            "filing_year",
            "period",
            "law_selected_revision",
            "authority_scope",
            "identity_measurement",
            "printed_form_membership",
            "xsd_only_attributes",
        )
    } == {
        "modelo": "100",
        "filing_year": 2025,
        "period": "0A",
        "law_selected_revision": "2025",
        "authority_scope": "inspection_only",
        "identity_measurement": "measured",
        "printed_form_membership": "unsupported",
        "xsd_only_attributes": "unsupported",
    }
    assert len(comparison["layout_comparisons"]) == 1
    layout = comparison["layout_comparisons"][0]
    # Counts are NOT frozen here. The registry grows as revisions are authored, and a
    # hardcoded tally only records the day it was written -- it fails on legitimate
    # authoring and detects no real drift. The invariant is what carries meaning:
    # every registry casilla the dictionary does not carry is exactly one divergence.
    assert layout["registry_casilla_count"] >= layout["dictionary_casilla_count"]
    assert layout["identity_divergence_count"] == (
        layout["registry_casilla_count"] - layout["dictionary_casilla_count"]
    )
    assert layout["identity_divergence_count"] == len(layout["missing_casilla_ids"])
    assert comparison["identity_divergence_count"] == layout["identity_divergence_count"]

    # A casilla the dictionary carries but the registry does not is always a defect.
    assert layout["extra_casilla_ids"] == []

    # The missing-id SET is deliberately not pinned. Those ids are registry casillas the
    # schema dictionary does not carry, and the set legitimately moves in both directions:
    # authoring an anexo casilla adds one, and closing a gap removes one. Pinning it fails
    # on both, which is how the frozen tally above failed. What must hold is the arithmetic
    # and the one-directional rule below.

    assert set(matrix["classification_census"]) == set(COORDINATE_CLASSIFICATIONS)
    assert matrix["classification_census"]["not_yet_measured"] == 1
    assert sum(matrix["classification_census"].values()) == len(matrix["coordinates"])


def test_report_json_preserves_construct_and_casilla_provenance_ledgers() -> None:
    """The dev payload does not drop the application-level provenance axes."""
    result = CliRunner().invoke(app, ["report", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    rendered = next(row for row in payload["rows"] if row["modelo"] == "100" and row["revision"] == "2025")
    source = next(
        row
        for row in audit_bundled_registry_conformance(validate=True).rows
        if row.modelo == "100" and row.revision == "2025"
    )

    assert source.construct_evidence is not None
    assert rendered["construct_evidence"] == source.construct_evidence.model_dump(mode="json")
    assert rendered["casilla_provenance"] == [trace.model_dump(mode="json") for trace in source.casilla_provenance]


def test_report_json_and_text_expose_inspection_scope_without_filing_grade_gaps() -> None:
    """Inspection evidence remains visible and is never rendered as filing scope."""
    result = CliRunner().invoke(app, ["report", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    inspection = next(row for row in payload["rows"] if row["model_law_authority_scope"] == "inspection_only")

    assert inspection["construct_evidence_authority_scope"] == "inspection_only"
    assert inspection["required_coverage_gap_tiers"] == []
    assert inspection["construct_evidence"]["ledger"]["authority_scope"] == "inspection_only"
    assert inspection["construct_evidence"]["ledger"]["rows"]

    text = CliRunner().invoke(app, ["report"]).stdout
    row_line = next(
        line
        for line in text.splitlines()
        if line.startswith(f"row modelo={inspection['modelo']} revision={inspection['revision']} ")
    )
    assert "model_law_authority_scope=inspection_only" in row_line
    assert "construct_evidence_authority_scope=inspection_only" in row_line
    assert "required_coverage_gap_tiers=-" in row_line
    assert "construct_evidence_gaps=0" not in row_line


def test_report_json_keeps_construct_evidence_unmeasured_on_degraded_read() -> None:
    """A degraded report retains schema traces but does not claim construct proof."""
    result = CliRunner().invoke(app, ["report", "--json", "--no-validate"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    rendered = next(row for row in payload["rows"] if row["modelo"] == "100" and row["revision"] == "2025")

    assert rendered["registry_validated"] is False
    assert rendered["construct_evidence"] is None
    assert rendered["casilla_provenance"]


def test_annual_matrix_revision_is_read_from_the_validated_authority() -> None:
    """The static coordinate uses canonical inspection, not a filing snapshot."""
    report = load_conformance_report(validate=True)
    assert report.annual_matrix is not None
    coordinate = report.annual_matrix.coordinates[0]
    authority = bundled_authority()
    inspection = authority.inspect_revision("100", filing_year=2025, period="0A")
    revision = authority.modelo("100").revisions[inspection.revision_id]

    assert (coordinate.modelo, coordinate.filing_year, coordinate.period) == ("100", 2025, "0A")
    assert coordinate.law_selected_revision == inspection.revision_id
    assert coordinate.law_selected_revision == "2025"
    assert coordinate.authority_scope == "inspection_only"
    assert coordinate.schema_comparison == compare_annual_casilla_population_for_revision(
        modelo=inspection.modelo_id,
        revision=revision,
        filing_year=2025,
        period="0A",
        sources=inspection.sources,
        source_root=authority.source_root,
    )


def test_report_text_renders_provenance_counts_and_degraded_absence(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """Text summarizes provenance while JSON remains the lossless ledger surface."""
    result = CliRunner().invoke(app, ["report"])

    assert result.exit_code == 0, result.stdout
    source = next(row for row in validated_profile.rows if row.modelo == "100" and row.revision == "2025")
    if source.construct_evidence is None:
        raise AssertionError("validated source row must carry construct evidence")
    row_line = next(line for line in result.stdout.splitlines() if line.startswith("row modelo=100 revision=2025 "))
    assert f"construct_evidence_rows={len(source.construct_evidence.rows)}" in row_line
    assert f"construct_evidence_gaps={len(source.construct_evidence.gaps)}" in row_line
    assert f"casilla_provenance_traces={len(source.casilla_provenance)}" in row_line

    degraded = CliRunner().invoke(app, ["report", "--no-validate"])
    assert degraded.exit_code == 0, degraded.stdout
    degraded_line = next(
        line for line in degraded.stdout.splitlines() if line.startswith("row modelo=100 revision=2025 ")
    )
    assert "construct_evidence_rows=n/a" in degraded_line
    assert "construct_evidence_gaps=n/a" in degraded_line


def test_report_text_projects_schema_layout_and_keeps_statuses_distinct(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """Text exposes measured identity without collapsing unsupported/unmeasured states."""
    result = CliRunner().invoke(app, ["report"])

    assert result.exit_code == 0, result.stdout
    assert "annual_coordinate modelo=100 filing_year=2025 period=0A law_selected_revision=2025" in result.stdout
    assert "authority_scope=inspection_only" in result.stdout
    assert "schema_identity_measurement=measured" in result.stdout
    assert "schema_printed_form_membership=unsupported" in result.stdout
    assert "schema_xsd_only_attributes=unsupported" in result.stdout
    assert "schema_identity_divergence_count=33" in result.stdout
    assert "annual_schema_layout modelo=100 filing_year=2025 period=0A law_selected_revision=2025" in result.stdout
    assert "identity_measurement=measured" in result.stdout
    assert "registry_casilla_count=2238" in result.stdout
    assert "dictionary_casilla_count=2205" in result.stdout
    assert "identity_divergence_count=33" in result.stdout
    assert "extra_casilla_ids=-" in result.stdout
    assert "missing_casilla_ids=0059,AJ,ANOASDLG" in result.stdout

    authority = bundled_authority()
    snapshot = authority.snapshot("100", filing_year=2025, period="0A")
    unmeasured_comparison = compare_annual_casilla_population(snapshot)
    unmeasured_coordinate = ConformanceCoordinate(
        modelo="100",
        filing_year=2025,
        period="0A",
        law_selected_revision=snapshot.revision.id,
        schema_comparison=unmeasured_comparison,
        classification="not_yet_measured",
        provisional=True,
    )
    census: dict[str, int] = dict.fromkeys(COORDINATE_CLASSIFICATIONS, 0)
    census["not_yet_measured"] = 1
    locale_index, locale_unavailable_modelos = load_locale_coverage_index()
    unmeasured_report = build_conformance_report(
        validated_profile,
        locale_index=locale_index,
        locale_unavailable_modelos=locale_unavailable_modelos,
        oracle_inventory=load_bundled_external_oracle_inventory(),
        annual_matrix=ConformanceCoordinateMatrix(
            coordinates=(unmeasured_coordinate,),
            classification_census=census,
        ),
    )
    unmeasured_text = render_report(unmeasured_report)
    assert "annual_schema_layout" in unmeasured_text
    assert "identity_measurement=unmeasured" in unmeasured_text
    assert "printed_form_membership=unsupported" in unmeasured_text
    assert "xsd_only_attributes=unsupported" in unmeasured_text


def test_annual_coordinate_rejects_mismatched_schema_comparison() -> None:
    """Nested evidence cannot silently describe a different legal coordinate."""
    coordinate = _real_d2025_coordinate()
    mismatched = coordinate.schema_comparison.model_copy(update={"filing_year": 2024})

    with pytest.raises(
        ValidationError,
        match="annual schema comparison coordinate does not match enclosing coordinate",
    ):
        ConformanceCoordinate(
            modelo=coordinate.modelo,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            law_selected_revision=coordinate.law_selected_revision,
            schema_comparison=mismatched,
            classification=coordinate.classification,
            provisional=coordinate.provisional,
        )


def test_degraded_report_does_not_claim_validated_annual_coordinates(
    degraded_report: ConformanceReport,
) -> None:
    """The degraded screen keeps the coordinate axis explicitly unmeasured."""
    assert degraded_report.annual_matrix is None
    assert "annual_matrix registry_validated=false measured=false coordinates=n/a" in render_report(degraded_report)


def test_annual_matrix_rejects_an_incomplete_classification_census() -> None:
    """Every supported classification must remain visible, including zeroes."""
    coordinate = _real_d2025_coordinate()

    with pytest.raises(ValidationError, match="must name every supported disposition exactly once"):
        ConformanceCoordinateMatrix(
            coordinates=(coordinate,),
            classification_census={"not_yet_measured": 1},
        )


def test_annual_matrix_rejects_a_census_count_that_does_not_match_coordinates() -> None:
    """The census must equal the enumerated population, not merely name its keys."""
    coordinate = _real_d2025_coordinate()
    census: dict[str, int] = dict.fromkeys(COORDINATE_CLASSIFICATIONS, 0)

    with pytest.raises(ValidationError, match="classification census does not match the enumerated coordinates"):
        ConformanceCoordinateMatrix(
            coordinates=(coordinate,),
            classification_census=census,
        )


def test_annual_matrix_rejects_duplicate_exact_coordinates() -> None:
    """The finite denominator cannot count one exact coordinate twice."""
    coordinate = _real_d2025_coordinate()
    census: dict[str, int] = dict.fromkeys(COORDINATE_CLASSIFICATIONS, 0)
    census["not_yet_measured"] = 2

    with pytest.raises(ValidationError, match="annual coordinate is duplicated"):
        ConformanceCoordinateMatrix(
            coordinates=(coordinate, coordinate),
            classification_census=census,
        )


def test_report_json_is_strict_and_keeps_an_absent_claim_as_null(validated_report: ConformanceReport) -> None:
    """A revision reconciling nothing serialises ``null`` coverage, never ``0``."""
    result = CliRunner().invoke(app, ["report", "--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["rows"]) == validated_report.revision_count

    absent = [row for row in payload["rows"] if row["reconciled_casillas"] == 0]
    assert absent, "expected at least one revision that reconciles nothing"
    assert all(row["independent_check_coverage"] is None for row in absent)

    measured = [row for row in payload["rows"] if row["reconciled_casillas"] > 0]
    assert measured, "expected at least one revision that reconciles something"
    assert all(isinstance(row["independent_check_coverage"], float) for row in measured)


def test_rendering_keeps_absence_distinct_from_zero(validated_report: ConformanceReport) -> None:
    """Flip the one field from ``None`` to ``0.0`` and the render MUST change.

    The mutation touches nothing else, so a renderer that collapsed absence onto
    zero would produce identical text and this assertion would fail. Killing a
    fixture could not prove this; only moving the value can.
    """
    absent_index = next(
        index for index, row in enumerate(validated_report.rows) if row.independent_check_coverage is None
    )
    rows = list(validated_report.rows)
    rows[absent_index] = rows[absent_index].model_copy(update={"independent_check_coverage": 0.0})
    zeroed = validated_report.model_copy(update={"rows": tuple(rows)})

    original_line = render_report(validated_report).splitlines()
    zeroed_line = render_report(zeroed).splitlines()
    changed = [pair for pair in zip(original_line, zeroed_line, strict=True) if pair[0] != pair[1]]

    assert len(changed) == 1, "exactly the mutated row should render differently"
    assert f"independent_check_coverage={NOT_MEASURED}" in changed[0][0]
    assert "independent_check_coverage=0.0000" in changed[0][1]


def test_degraded_read_labels_every_row_not_only_the_envelope(degraded_report: ConformanceReport) -> None:
    """The unvalidated label rides on each row, so a filtered view cannot drop it."""
    rendered = render_report(degraded_report)
    row_lines = [line for line in rendered.splitlines() if line.startswith("row ")]

    assert row_lines
    assert all("registry_validated=false" in line for line in row_lines)
    # The three axes needing the validating authority are ABSENT, not zeroed.
    assert all(f"modelo_authorization={NOT_MEASURED}" in line for line in row_lines)
    assert all(f"latest_revision_probed={NOT_MEASURED}" in line for line in row_lines)
    assert all(f"required_coverage_gap_tiers={NOT_MEASURED}" in line for line in row_lines)
    assert "DEGRADED READ" in rendered.splitlines()[-1]


def test_validated_read_measures_the_axes_the_degraded_read_withholds(
    validated_report: ConformanceReport,
    degraded_report: ConformanceReport,
) -> None:
    """The same tree, measured both ways: absence is the READ, not the registry.

    Pairs with the degraded test above. Without this side, ``n/a`` everywhere
    would be indistinguishable from a renderer that never emits anything else.
    """
    validated_rows = [line for line in render_report(validated_report).splitlines() if line.startswith("row ")]

    assert validated_rows
    assert all("registry_validated=true" in line for line in validated_rows)
    assert any("modelo_authorization=authorized" in line for line in validated_rows)
    assert all(f"latest_revision_probed={NOT_MEASURED}" not in line for line in validated_rows)
    assert validated_report.revision_count == degraded_report.revision_count


def test_coverage_carries_the_grounding_caveat_into_json() -> None:
    """The coverage-not-correctness label rides in the payload, not only the text."""
    result = CliRunner().invoke(app, ["coverage", "--json"])

    assert result.exit_code == 0, result.stdout
    rows = {row["axis"]: row for row in json.loads(result.stdout)["rows"]}
    grounding = rows["external_grounding.independently_checked_casillas"]

    assert grounding["caveat"] is not None
    assert "never correctness" in grounding["caveat"]
    assert grounding["population"] > grounding["measured"] >= 0
    # An axis needing no caveat carries None, so a caveat is never fabricated to
    # fill the column.
    assert rows["revision.calc_grade"]["caveat"] is None


def test_coverage_reports_a_dead_axis_against_a_real_population(validated_report: ConformanceReport) -> None:
    """An unused schema surface shows zero declarations out of a real denominator."""
    rendered = render_coverage(build_coverage_report(validated_report))
    axis_lines = {
        line.split(" ")[1].removeprefix("axis="): line for line in rendered.splitlines() if line.startswith("axis ")
    }

    assert validated_report.unused_declared_axes
    for axis in validated_report.unused_declared_axes:
        line = axis_lines[f"declared_axis.{axis}"]
        assert "measured=0" in line
        assert f"population={validated_report.declared_axis_population[axis]}" in line
        assert "UNUSED, never passing" in line


# --------------------------------------------------------------------------- #
# reviewer attribution: the status column and the name column must be read together
# --------------------------------------------------------------------------- #

#: A fictional, person-shaped reviewer name.
#:
#: The misreading these surfaces defend against is a HUMAN name rendering
#: identically under both review tiers, so the fixture value has to look like a
#: person — two words, a space, and no colon, since the colon is the tier
#: separator the writer refuses inside a name. A token like ``reviewer-1`` would
#: exercise a shape the production surface never meets.
#:
#: It is deliberately fictional. A real person's name in tracked source is
#: identifying data whatever its purpose, and the repository-wide privacy lint
#: bans it; the constant is named for the SHAPE it supplies rather than for any
#: role, so nothing here reads as an invitation to substitute a real one.
_PERSON_REVIEWER_NAME = "Marta Ejemplo"


def _report_with_review(
    profile: RegistryConformanceProfile,
    *,
    status: RevisionReviewStatus,
    reviewer: str,
) -> ConformanceReport:
    """Project the real profile with its first row carrying a real review stamp.

    The governance stamp is moved on the composed row and the report is built by
    the real projection, so ``reviewed_by_attribution`` is computed by the code
    under test rather than assembled by this helper.
    """
    first = profile.rows[0]
    stamped = first.model_copy(
        update={
            "governance": first.governance.model_copy(
                update={
                    "review_status": status,
                    "reviewed_by": reviewer,
                    "reviewed_at": date(2026, 7, 28),
                },
            ),
        },
    )
    return build_conformance_report(
        profile.model_copy(update={"rows": (stamped, *profile.rows[1:])}),
        locale_index={},
        locale_unavailable_modelos=(),
        oracle_inventory=load_bundled_external_oracle_inventory(),
    )


def _row_line(rendered: str, modelo: str, revision: str) -> str:
    return next(
        item
        for item in rendered.splitlines()
        if item.startswith("row ") and f" modelo={modelo} " in item and f" revision={revision} " in item
    )


def _reviewer_field(rendered: str, modelo: str, revision: str) -> str:
    line = _row_line(rendered, modelo, revision)
    return line.split("reviewed_by_attribution=", 1)[1].split(" reviewed_at=", 1)[0]


def test_an_agent_tier_review_naming_a_person_cannot_render_as_an_operator_signoff(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """The decisive flip: change ONLY the tier and the reviewer column must change.

    ``reviewed_by`` is free text by necessity, so
    ``--review-status agent_reviewed --reviewed-by "<a person's name>"`` writes
    cleanly and is a legitimate stamp. While the reviewer rendered bare, the two
    tiers produced a byte-identical reviewer column and a reader scanning ninety
    rows read the name. This asserts the columns are no longer independent: same
    row, same name, different tier, different rendering.
    """
    row = validated_profile.rows[0]
    agent = _report_with_review(
        validated_profile,
        status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewer=_PERSON_REVIEWER_NAME,
    )
    operator = _report_with_review(
        validated_profile,
        status=RevisionReviewStatus.OPERATOR_REVIEWED,
        reviewer=_PERSON_REVIEWER_NAME,
    )

    agent_field = _reviewer_field(render_report(agent), row.modelo, row.revision)
    operator_field = _reviewer_field(render_report(operator), row.modelo, row.revision)

    assert agent_field != operator_field
    assert "agent_reviewed" in agent_field
    assert "operator_reviewed" in operator_field
    assert _PERSON_REVIEWER_NAME in agent_field
    # The bare name is never the whole rendered value, which is what a scanning
    # reader would otherwise take at face value.
    assert agent_field != json.dumps(_PERSON_REVIEWER_NAME)


def test_the_attribution_is_computed_by_the_projection_and_carried_into_json(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """The payload keeps the raw name AND the qualified form, so JSON reads it too.

    A consumer filtering on ``reviewed_by`` alone would otherwise reach the same
    misreading the text render was hardened against.
    """
    composed = _report_with_review(
        validated_profile,
        status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewer=_PERSON_REVIEWER_NAME,
    )
    row = composed.rows[0]

    assert row.reviewed_by == _PERSON_REVIEWER_NAME
    assert row.reviewed_by_attribution == f"agent_reviewed:{_PERSON_REVIEWER_NAME}"
    assert json.loads(composed.model_dump_json())["rows"][0]["reviewed_by_attribution"] == row.reviewed_by_attribution


def test_a_revision_claiming_no_review_is_never_joined_to_a_tier(
    validated_report: ConformanceReport,
) -> None:
    """Absence stays absence: an unreviewed row must not gain a manufactured claim.

    The registry schema pairs the reviewer identity with a status beyond
    ``pending_review`` and refuses either alone, so a row with no reviewer is a
    row asserting no review. Joining it to its status would print a claim the
    manifest does not make.
    """
    unreviewed = [row for row in validated_report.rows if row.reviewed_by is None]

    assert unreviewed, "expected at least one revision declaring no reviewer"
    assert all(row.reviewed_by_attribution is None for row in unreviewed)
    assert reviewer_attribution(RevisionReviewStatus.PENDING_REVIEW.value, None) is None

    rendered = render_report(validated_report)
    assert f"reviewed_by_attribution={NOT_MEASURED}" in rendered


def test_the_reviewer_key_carries_one_value_across_both_surfaces(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """One key name, one value, whichever surface reads it.

    The first pass at qualifying the reviewer rendered the joined form in TEXT
    under the key ``reviewed_by`` while the payload's ``reviewed_by`` stayed the
    raw name. The two surfaces then disagreed under the same symbol, and the one
    a program reads carried the bare name — the exact reading the join was added
    to prevent, reintroduced by the fix for it.

    This asserts the reconciliation directly: every key the text row emits and
    the payload also declares must carry the same rendered value, and the text
    must not emit a bare reviewer column at all.
    """
    composed = _report_with_review(
        validated_profile,
        status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewer=_PERSON_REVIEWER_NAME,
    )
    row = composed.rows[0]
    rendered = render_report(composed)
    line = _row_line(rendered, row.modelo, row.revision)
    payload = json.loads(composed.model_dump_json())["rows"][0]

    # The one key both surfaces name carries the one value, and the raw name is
    # NOT it: without the fix this assertion reads the raw name in JSON against
    # the qualified form in text and fails.
    assert _reviewer_field(rendered, row.modelo, row.revision) == json.dumps(payload["reviewed_by_attribution"])
    assert payload["reviewed_by_attribution"] != payload["reviewed_by"]
    # The bare reviewer column is gone from text, so no key name can disagree.
    assert " reviewed_by=" not in line
    # And the payload still declares the raw datum, documented to be read beside
    # its attribution rather than alone.
    assert payload["reviewed_by"] == _PERSON_REVIEWER_NAME
    assert payload["reviewed_by_attribution"] == f"{RevisionReviewStatus.AGENT_REVIEWED.value}:{_PERSON_REVIEWER_NAME}"


@pytest.mark.parametrize(
    "spoof",
    [
        f"operator_reviewed:{_PERSON_REVIEWER_NAME}",
        f"OPERATOR_REVIEWED:{_PERSON_REVIEWER_NAME}",
        "agent_reviewed:somebody",
    ],
)
def test_stamp_refuses_a_reviewer_that_reads_as_an_already_qualified_attribution(
    registry_copy: Path,
    spoof: str,
) -> None:
    """The one field with no vocabulary must not be able to forge one.

    The joined attribution is parsed at its first separator and is unambiguous
    whatever the name holds. The RAW ``reviewed_by`` is the exposed field: a
    payload consumer can read it alone, and a reviewer recorded as
    ``operator_reviewed:<name>`` is then indistinguishable from a genuine
    operator attribution. That is an agent-tier stamp readable as a human
    signoff without ever writing the status this CLI refuses to write.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    with pytest.raises(StampError, match="already-qualified attribution"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            review_status=StampableReviewStatus.AGENT_REVIEWED,
            reviewed_by=spoof,
            reviewed_at=date(2026, 7, 28),
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before


def test_a_qualified_reviewer_name_that_is_not_a_status_stays_legal(registry_copy: Path) -> None:
    """The paired half: the refusal is the STATUS prefix, never the separator.

    A role-qualified identity such as ``agent:opus-executor`` is how an
    automated reviewer names itself, and its colon is a role prefix rather than
    a status one. The join was never ambiguous — no status value carries a
    colon, so the tier is everything before the first one. A blanket colon
    refusal would satisfy the spoof test above while breaking every honest
    caller, and no other assertion here would notice.
    """
    result = stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:opus-executor",
        reviewed_at=date(2026, 7, 28),
        registry_root=registry_copy,
    )

    assert result.written["reviewed_by"] == '"agent:opus-executor"'
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.reviewed_by == "agent:opus-executor"
    assert reviewer_attribution(RevisionReviewStatus.AGENT_REVIEWED.value, revision.reviewed_by) == (
        "agent_reviewed:agent:opus-executor"
    )


# --------------------------------------------------------------------------- #
# oracle attribution gap: the field gains three readers
# --------------------------------------------------------------------------- #


def _with_injected_gap(report: ConformanceReport) -> ConformanceReport:
    """Return ``report`` carrying one real unattributed-payload record."""
    gap = UnattributedOraclePayload(
        corpus=ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        payload_name="modelo-999-injected-attribution-gap.json",
        gap="payload_name_lacks_modelo_and_filing_year",
        detail="injected by the conformance CLI gate to prove the gap reaches a reader",
    )
    projected = build_conformance_report(
        RegistryConformanceProfile(rows=(), registry_validated=True, unattributed_oracle_payloads=(gap,)),
        locale_index={},
        locale_unavailable_modelos=(),
        oracle_inventory=load_bundled_external_oracle_inventory(),
    )
    return report.model_copy(update={"unattributed_oracle_payloads": projected.unattributed_oracle_payloads})


def test_an_unattributed_oracle_payload_reaches_report_coverage_and_the_ratchet(
    validated_report: ConformanceReport,
) -> None:
    """One injected gap moves all three surfaces; without it, none of them move.

    The gap set is empty on the tree today, so an assertion on the live count
    would pass whether or not anything consumed the field. Injecting one real
    record and asserting the difference is what proves the field has readers.
    """
    baseline = load_baseline()
    seeded = _with_injected_gap(validated_report)

    clean_render = render_report(validated_report)
    seeded_render = render_report(seeded)
    assert "oracle_gap kind=unattributed_payload" not in clean_render
    assert "payload=modelo-999-injected-attribution-gap.json" in seeded_render

    clean_axis = _axis_line(render_coverage(build_coverage_report(validated_report)), "oracle_payloads.unattributed")
    seeded_axis = _axis_line(render_coverage(build_coverage_report(seeded)), "oracle_payloads.unattributed")
    assert "measured=0" in clean_axis
    assert "measured=1" in seeded_axis

    assert check_conformance_ratchet(validated_report, baseline).passed
    seeded_result = check_conformance_ratchet(seeded, baseline)
    assert not seeded_result.passed
    assert any("unattributed_oracle_payloads grew" in item for item in seeded_result.ratchet_violations)


def test_unmatched_oracle_evidence_has_its_own_axis_and_ceiling(validated_report: ConformanceReport) -> None:
    """The second attribution direction is a rendered axis and a ratcheted counter."""
    rendered = render_coverage(build_coverage_report(validated_report))
    line = _axis_line(rendered, "oracle_evidence.unmatched")

    assert "reaches no registry revision" in line
    assert f"population={validated_report.bundled_oracle_payload_count}" in line
    assert hasattr(load_baseline().ceilings, "unmatched_oracle_evidence")


def _axis_line(rendered: str, axis: str) -> str:
    return next(line for line in rendered.splitlines() if line.startswith(f"axis axis={axis} "))


# --------------------------------------------------------------------------- #
# audit: the only gating exit
# --------------------------------------------------------------------------- #


def test_audit_check_passes_at_the_committed_baseline() -> None:
    """The committed baseline describes the tree it was captured from."""
    result = CliRunner().invoke(app, ["audit", "--check"])

    assert result.exit_code == 0, result.stdout
    assert "passed=true" in result.stdout
    assert "violation " not in result.stdout


def test_audit_check_fails_when_one_ceiling_is_lowered(tmp_path: Path) -> None:
    """Same command, same tree, one moved counter: the exit code MUST flip."""
    seeded = _baseline_with(tmp_path / "lowered.json", ceiling="modelo_scope_classification_findings", delta=-1)
    result = CliRunner().invoke(app, ["audit", "--check", "--baseline", str(seeded)])

    assert result.exit_code == 1, result.stdout
    assert "passed=false" in result.stdout
    assert "violation kind=ratchet" in result.stdout
    assert "modelo_scope_classification_findings grew" in result.stdout


def test_audit_check_fails_when_one_floor_is_raised(tmp_path: Path) -> None:
    """A shrunken measurement is reported as vacuity, not as a clean ratchet."""
    seeded = _baseline_with(tmp_path / "raised.json", floor="reconciled_casillas", delta=1)
    result = CliRunner().invoke(app, ["audit", "--check", "--baseline", str(seeded)])

    assert result.exit_code == 1, result.stdout
    assert "violation kind=vacuity" in result.stdout
    assert "reconciled_casillas fell" in result.stdout
    assert "violation kind=ratchet" not in result.stdout


def test_audit_without_check_is_a_screen_even_when_it_finds_a_violation(tmp_path: Path) -> None:
    """Screen posture: the same violation renders and still exits 0."""
    seeded = _baseline_with(tmp_path / "screen.json", ceiling="unused_declared_axes", delta=-1)
    result = CliRunner().invoke(app, ["audit", "--baseline", str(seeded)])

    assert result.exit_code == 0, result.stdout
    assert "violation kind=ratchet" in result.stdout


def test_audit_refuses_a_report_that_composed_nothing() -> None:
    """A ratchet over an empty input reports every counter clean while checking nothing."""
    baseline = load_baseline()

    with pytest.raises(SystemExit, match="composed zero revision rows"):
        check_conformance_ratchet(_empty_report(), baseline)


def test_vacuity_warning_fires_only_when_the_screen_composed_nothing(
    validated_report: ConformanceReport,
) -> None:
    """Both branches are asserted, so a warning that always or never fires is caught."""
    assert vacuity_warning(validated_report) is None

    warning = vacuity_warning(_empty_report())
    assert warning is not None
    assert warning.startswith("warning rows=0 ")


def test_audit_refuses_to_gate_or_capture_on_a_degraded_read() -> None:
    """A degraded read leaves three axes unmeasured; freezing them as clean is refused."""
    gate = CliRunner().invoke(app, ["audit", "--check", "--no-validate"])
    capture = CliRunner().invoke(app, ["audit", "--record", "--note", "x", "--no-validate"])

    assert gate.exit_code != 0
    assert capture.exit_code != 0


def test_recording_a_baseline_requires_a_stated_reason(tmp_path: Path) -> None:
    """An unexplained re-record is indistinguishable from silencing a regression."""
    result = CliRunner().invoke(app, ["audit", "--record", "--baseline", str(tmp_path / "new.json")])

    assert result.exit_code != 0
    assert not (tmp_path / "new.json").exists()


def _with_review_statuses(
    report: ConformanceReport,
    statuses: Sequence[RevisionReviewStatus],
) -> ConformanceReport:
    """Return the real report with every row's declared review status replaced.

    The census is recomputed from the rows rather than set independently, so the
    two never disagree and a counter reading the census is measuring the same
    tree the rows describe. Only the governance axis moves; every other fact
    stays the one the real registry produced.
    """
    rows = tuple(
        row.model_copy(update={"review_status": status.value})
        for row, status in zip(report.rows, statuses, strict=True)
    )
    census = {member.value: 0 for member in RevisionReviewStatus}
    for status in statuses:
        census[status.value] += 1
    return report.model_copy(update={"rows": rows, "review_status_census": census})


def _ceiling_line(rendered: str, counter: str) -> str:
    return next(line for line in rendered.splitlines() if line.startswith(f"ceiling counter={counter} "))


def _progress_line(rendered: str, counter: str) -> str:
    return next(line for line in rendered.splitlines() if line.startswith(f"progress counter={counter} "))


def _baseline_captured_from(report: ConformanceReport, path: Path) -> ConformanceBaseline:
    """Capture a baseline from ``report`` through the real recording path."""
    record_baseline(report, note="captured by the conformance CLI gate", recorded_at="2026-07-28", path=path)
    return load_baseline(path)


def test_an_agent_review_sweep_fills_the_review_floor_but_not_the_operator_floor(
    validated_report: ConformanceReport,
) -> None:
    """The act the CLI is DESIGNED to allow must not read as progress on the gated number.

    ``stamp --review-status agent_reviewed`` is a legitimate verb an agent may
    run across every revision in the tree. Doing so drives the review floor to
    the full registry. If that were the only gated review counter, the one number
    CI protects would read complete without a single human signoff, and the
    three-state vocabulary would collapse back into the two-state laundering it
    was introduced to remove. The operator floor must sit still through exactly
    that sweep.
    """
    total = validated_report.revision_count
    swept = _with_review_statuses(validated_report, [RevisionReviewStatus.AGENT_REVIEWED] * total)

    rendered = render_audit(check_conformance_ratchet(swept, load_baseline()))

    assert f"current={total} " in _progress_line(rendered, "reviewed_revisions")
    assert "progress counter=operator_reviewed_revisions current=0 " in rendered
    # The sweep is not itself a regression: nothing was lost, so the audit still
    # passes. What must not happen is the operator floor reading as satisfied.
    assert check_conformance_ratchet(swept, load_baseline()).passed


def test_a_lost_operator_signoff_reds_the_operator_floor_the_review_floor_cannot_see(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The decisive flip: one regression, invisible to the broader counter, caught by the narrow one.

    Both states are fully agent-or-operator reviewed, so ``reviewed_revisions``
    is the full registry in each and is flat across the regression. The only
    difference is that one revision's operator signoff became an agent review.
    The audit must fail on it and must name the counter that moved.
    """
    total = validated_report.revision_count
    signed = _with_review_statuses(
        validated_report,
        [RevisionReviewStatus.OPERATOR_REVIEWED] * 10 + [RevisionReviewStatus.AGENT_REVIEWED] * (total - 10),
    )
    regressed = _with_review_statuses(
        validated_report,
        [RevisionReviewStatus.OPERATOR_REVIEWED] * 9 + [RevisionReviewStatus.AGENT_REVIEWED] * (total - 9),
    )
    baseline = _baseline_captured_from(signed, tmp_path / "signed.json")

    assert check_conformance_ratchet(signed, baseline).passed

    result = check_conformance_ratchet(regressed, baseline)
    assert not result.passed
    # Asserted as the WHOLE violation set, not with a substring exclusion: the
    # broad counter's name is a suffix of the narrow one, so
    # "reviewed_revisions fell" matches the operator sentence too and an
    # exclusion phrased that way is a false negative waiting to happen.
    moved = [item.split(" fell", 1)[0] for item in result.progress_violations]
    assert moved == ["operator_reviewed_revisions"], result.progress_violations
    assert result.progress_violations[0].startswith("operator_reviewed_revisions fell from 10 to 9")
    assert not result.ratchet_violations


def test_the_operator_floor_gates_the_real_cli_at_the_committed_baseline(tmp_path: Path) -> None:
    """The new counter has teeth in the shipped verb, not only in a fold.

    Same command, same tree, one raised floor: the exit code flips. Without this
    the field could be committed, rendered, and never actually consulted by the
    gate.
    """
    seeded = _baseline_with(tmp_path / "raised.json", progress="operator_reviewed_revisions", delta=1)
    result = CliRunner().invoke(app, ["audit", "--check", "--baseline", str(seeded)])

    assert result.exit_code == 1, result.stdout
    assert "violation kind=progress" in result.stdout
    assert "operator_reviewed_revisions fell" in result.stdout


def test_the_committed_operator_floor_equals_what_the_tool_measures(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """A floor below the measurement licenses a regression the gate cannot see.

    Anchored to a FRESH measurement, not to another committed number. An earlier
    form of this test asserted the operator counter equalled the
    ``composed_revisions`` floor, which is a CENSUS FACT — true only while
    nothing in the tree carries an operator signoff — dressed as a seeding rule.
    It would have failed on the campaign's first genuine signoff for a reason
    having nothing to do with seeding.

    The invariant that survives is the one worth keeping: the committed floor
    equals what the tool measures right now. Below the measurement is slack, and
    a revision can lose its signoff inside it without the gate noticing; above it
    the gate is already red. Either way the answer is to re-record the baseline,
    which is what the failure message should send a reader to do.
    """
    measured = _baseline_captured_from(validated_report, tmp_path / "measured.json")
    committed = load_baseline()

    assert committed.progress.operator_reviewed_revisions == (measured.progress.operator_reviewed_revisions), (
        "the committed operator floor has drifted from the measurement; re-record the baseline"
    )


def _report_with_one_more_grounding_finding(report: ConformanceReport) -> ConformanceReport:
    """Return the real report with one extra grounding finding: a RAISED ceiling."""
    return report.model_copy(update={"grounding_finding_count": report.grounding_finding_count + 1})


def _report_with_one_fewer_revision(report: ConformanceReport) -> ConformanceReport:
    """Return the real report having composed one revision fewer: a LOWERED floor.

    Deliberately a MIXED movement, not a single unambiguous one. Alongside the
    dropped revision the seeded report carries one classification finding fewer
    and one agent-reviewed revision more, so a capture of it STRENGTHENS a
    ceiling and STRENGTHENS a progress floor while weakening one vacuity floor.
    A guard that refused any movement at all would satisfy the refusal assertion
    just as well, so the mixture is what makes the direction separation provable
    across all three counter families rather than assumed.

    The census is moved with the count so the two never disagree, and the
    revision that survives as agent-reviewed is one the real tree left pending.
    """
    census = dict(report.review_status_census)
    census[RevisionReviewStatus.PENDING_REVIEW.value] -= 2
    census[RevisionReviewStatus.AGENT_REVIEWED.value] += 1
    return report.model_copy(
        update={
            "rows": report.rows[:-1],
            "revision_count": report.revision_count - 1,
            "review_status_census": census,
            "modelo_scope_classification_finding_count": report.modelo_scope_classification_finding_count - 1,
        },
    )


def test_recording_refuses_a_capture_that_raises_a_ceiling(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """A capture is an acceptance, so accepting a grown backlog must be deliberate.

    ``--record`` guarded only the report in isolation: not degraded, non-empty
    rows, non-empty note. None of those compare it against the baseline it is
    about to overwrite, and the note requirement proves only that a sentence was
    typed, never that it describes the movement.
    """
    path = tmp_path / "committed.json"
    _baseline_captured_from(validated_report, path)

    with pytest.raises(SystemExit, match="weakens the ratchet"):
        record_baseline(
            _report_with_one_more_grounding_finding(validated_report),
            note="a capture that accepts a grown backlog",
            recorded_at="2026-07-28",
            path=path,
        )

    assert load_baseline(path).ceilings.grounding_findings == validated_report.grounding_finding_count


def test_recording_refuses_a_capture_that_lowers_a_floor(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The direction that never heals, and the one the whole guard exists for.

    A raised ceiling is loud: the backlog it permits shows on the census and the
    next honest capture pulls it back. A floor lowered by a capture taken while a
    peer's half-landed change has removed revisions is silent forever, and from
    then on a genuinely half-read tree passes the anti-vacuity check that exists
    to catch precisely that.

    The seeded report strengthens one ceiling and one progress floor while
    lowering one vacuity floor, so this also asserts the guard reads all three
    directions separately instead of refusing any movement at all.
    """
    path = tmp_path / "committed.json"
    _baseline_captured_from(validated_report, path)
    shrunken = _report_with_one_fewer_revision(validated_report)

    with pytest.raises(SystemExit) as refusal:
        record_baseline(
            shrunken,
            note="a capture taken while the tree was half read",
            recorded_at="2026-07-28",
            path=path,
        )

    assert "composed_revisions would fall" in str(refusal.value)
    assert load_baseline(path).floors.composed_revisions == validated_report.revision_count

    # The three directions are read separately: the strengthened ceiling and the
    # strengthened progress floor must not be reported as weakenings, or the
    # guard is refusing movement rather than weakening and the refusal teaches
    # nothing.
    candidate = _baseline_captured_from(shrunken, tmp_path / "candidate.json")
    committed = load_baseline(path)
    total = validated_report.revision_count
    assert baseline_weakenings(candidate, committed) == (
        f"floor composed_revisions would fall from {total} to {total - 1}, demanding less measurement",
    )
    assert (
        candidate.ceilings.modelo_scope_classification_findings
        < committed.ceilings.modelo_scope_classification_findings
    )
    assert candidate.progress.reviewed_revisions > committed.progress.reviewed_revisions


def test_recording_a_strengthened_baseline_needs_no_acceptance(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The paired half: tightening the ratchet must stay frictionless.

    Without this, a guard that refused EVERY difference would satisfy both
    refusals above while making the ordinary act of recording progress require a
    flag that says the opposite of what happened.
    """
    path = tmp_path / "committed.json"
    _baseline_captured_from(_report_with_one_more_grounding_finding(validated_report), path)

    written = record_baseline(
        validated_report,
        note="the finding was fixed; tightening the ceiling",
        recorded_at="2026-07-28",
        path=path,
    )

    assert written.ceilings.grounding_findings == validated_report.grounding_finding_count
    assert load_baseline(path).ceilings.grounding_findings == validated_report.grounding_finding_count


def test_an_accepted_weakening_is_written_and_the_acceptance_reaches_the_real_verb(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The escape hatch exists, is explicit, and is wired to the shipped verb.

    A refusal with no sanctioned way past it teaches the next author to edit the
    baseline by hand, which is the unrecorded act the guard was added to remove.
    """
    path = tmp_path / "committed.json"
    _baseline_captured_from(validated_report, path)

    written = record_baseline(
        _report_with_one_more_grounding_finding(validated_report),
        note="the finding is real and accepted for now",
        recorded_at="2026-07-28",
        path=path,
        accept_weakening=True,
    )

    assert written.ceilings.grounding_findings == validated_report.grounding_finding_count + 1

    # Same command, same tree, one seeded baseline that the live measurement
    # would raise: the exit code flips on the flag alone.
    seeded = _baseline_with(tmp_path / "cli.json", ceiling="grounding_findings", delta=-1)
    arguments = ["audit", "--record", "--note", "a real capture", "--baseline", str(seeded)]

    refused = CliRunner().invoke(app, arguments)
    accepted = CliRunner().invoke(app, [*arguments, "--accept-weakening"])

    assert refused.exit_code != 0, refused.stdout
    assert accepted.exit_code == 0, accepted.stdout
    assert load_baseline(seeded).ceilings.grounding_findings == validated_report.grounding_finding_count


def test_a_recorded_baseline_lands_as_the_bytes_it_serialised(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The capture is a byte write, so nothing translates the file's terminators.

    ``record_baseline`` wrote through ``write_text``, which re-encodes under the
    platform's newline convention. On Windows every capture therefore expanded
    the baseline's LF terminators to CRLF, and ``git`` — normalising under
    ``text=auto eol=lf`` — reported no change at all, so the artefact the gate
    READS differed from its committed bytes for every reader that is not git.
    Measured on the tree that carried it: 28 LF terminators in 1932 committed
    bytes against 28 CRLF ones in 1960 on disk, with ``git diff`` silent.

    Three assertions, in the order they matter. The file must not have existed
    and must exist non-empty afterwards, so the case cannot pass on a path
    nothing wrote — the failure mode caught three times on the stamp
    writer. The bytes must carry no carriage return, which is what flips: no
    value in the payload contains one, so any CR in the file was inserted by the
    write. And the bytes must equal the serialisation of the model the function
    RETURNED, so a writer that silently wrote something else than it reported is
    caught too.

    The CR assertion is decisive only where the platform translates, which is
    where the defect was measured; on a platform whose line separator is already
    LF it holds trivially and the byte-equality assertion carries the case.
    """
    path = tmp_path / "captured.json"
    assert not path.exists()

    written = record_baseline(
        validated_report,
        note="a capture proving the writer does not translate terminators",
        recorded_at="2026-07-28",
        path=path,
    )
    raw = path.read_bytes()

    assert raw, "the capture must actually have written something"
    assert b"\r" not in raw, "the capture translated the file's terminators"
    expected = json.dumps(written.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    assert raw == expected.encode(UTF_8_ENCODING)


def test_the_committed_baseline_on_disk_matches_its_committed_terminators() -> None:
    """The artefact the gate reads must not have been rewritten by a capture.

    The defect above was invisible in review precisely because ``git diff`` stays
    clean through ``text=auto eol=lf`` normalisation while the working tree
    carries the rewrite, so nothing but a byte read could see it. This is that
    byte read, standing over the real committed file: the baseline is checked out
    LF on every platform by its git attribute, so a carriage return here means a
    capture rewrote the file after checkout and the on-disk artefact has drifted
    from the committed one.
    """
    raw = baseline_path().read_bytes()

    assert raw, "the committed baseline must exist and be non-empty"
    assert b"\r" not in raw, (
        "the committed baseline on disk carries translated terminators; a capture rewrote it after "
        "checkout and git cannot see the difference"
    )


def _baseline_with(
    path: Path,
    *,
    ceiling: str | None = None,
    floor: str | None = None,
    progress: str | None = None,
    delta: int = 0,
) -> Path:
    """Write a copy of the committed baseline with exactly one counter moved."""
    raw = json.loads(baseline_path().read_text(encoding=UTF_8_ENCODING))
    if ceiling is not None:
        raw["ceilings"][ceiling] += delta
    if floor is not None:
        raw["floors"][floor] += delta
    if progress is not None:
        raw["progress"][progress] += delta
    path.write_text(json.dumps(raw, indent=2), encoding=UTF_8_ENCODING)
    return path


# --------------------------------------------------------------------------- #
# stamp: the governance write path
# --------------------------------------------------------------------------- #


def test_the_stampable_vocabulary_excludes_operator_reviewed() -> None:
    """The narrowing is real, and it is a narrowing rather than a second taxonomy."""
    values = {member.value for member in StampableReviewStatus}

    assert values <= {member.value for member in RevisionReviewStatus}
    assert RevisionReviewStatus.OPERATOR_REVIEWED.value not in values
    assert RevisionReviewStatus.AGENT_REVIEWED.value in values


def test_the_cli_refuses_operator_reviewed_and_names_what_it_accepts() -> None:
    """An agent cannot record a human's signoff, and the refusal teaches the alternative."""
    result = CliRunner().invoke(
        app,
        ["stamp", _STAMPED_MODELO, _STAMPED_REVISION, "--review-status", "operator_reviewed"],
    )

    assert result.exit_code != 0
    assert "operator_reviewed" in result.output
    assert "pending_review" in result.output
    assert "agent_reviewed" in result.output


def test_stamp_refuses_the_core_operator_reviewed_member_handed_past_the_annotation(
    registry_copy: Path,
) -> None:
    """The narrowing must survive a caller who imports the OTHER enum.

    ``StampableReviewStatus`` narrows the vocabulary in the CLI's parse layer,
    but ``stamp_revision`` is exported and ``RevisionReviewStatus`` is one
    import away in ``cadrumo.core`` — the enum a driver script reaches for
    first. While the narrowing was only a type hint this call SUCCEEDED and left
    a manifest claiming a completed operator signoff naming an agent, and
    nothing downstream could object: the registry schema legitimately accepts
    ``operator_reviewed``, so the pre-write probe and the post-write reload both
    passed. The refusal exists only at this boundary, so only this boundary can
    prove it.

    The byte-identical assertion is the load-bearing half. A refusal that raised
    after rewriting the manifest would leave the false claim on disk and satisfy
    a ``pytest.raises`` alone.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    with pytest.raises(StampError, match="refusing to write review_status"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            review_status=RevisionReviewStatus.OPERATOR_REVIEWED,
            reviewed_by="agent:conformance-cli-gate",
            reviewed_at=date(2026, 7, 28),
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.PENDING_REVIEW
    assert revision.reviewed_by is None


def test_the_stamp_refusal_keys_on_the_value_not_on_which_enum_was_imported(
    registry_copy: Path,
) -> None:
    """The paired half: the SAME core enum's agent member is served, not refused.

    Without this, a coercion that rejected every ``RevisionReviewStatus`` member
    outright would satisfy the refusal test above while breaking every honest
    caller, and no assertion in this file would notice. What must be refused is
    the CLAIM a manifest would carry, never the class the caller imported.
    """
    result = stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:conformance-cli-gate",
        reviewed_at=date(2026, 7, 28),
        registry_root=registry_copy,
    )

    assert result.written["review_status"] == '"agent_reviewed"'
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED


@pytest.mark.parametrize("spelling", ["operator_reviewed", "OPERATOR_REVIEWED", "reviewed", ""])
def test_stamp_refuses_an_out_of_vocabulary_status_string_without_touching_the_manifest(
    registry_copy: Path,
    spelling: str,
) -> None:
    """A bare string reaches the same coercion, and a wrong one never reaches disk.

    Before the coercion these raised a bare ``AttributeError`` from deep inside
    the merge, which named neither the accepted vocabulary nor the reason
    ``operator_reviewed`` is absent from it.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    with pytest.raises(StampError, match="this CLI writes only"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            review_status=spelling,
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before


#: The same fictional person, written as an operator's own signoff attribution.
#: Declared once because five assertions below read it back off the compiled
#: revision, and a hand-copied literal in any of them would let a rewrite that
#: changed the seed pass while the assertion checked the old value.
_OPERATOR_SIGNATORY = f"{_PERSON_REVIEWER_NAME} (operator)"

_OPERATOR_SIGNOFF = f"""engineered_by = "the operator, by hand"
review_status = "operator_reviewed"
reviewed_by = "{_OPERATOR_SIGNATORY}"
reviewed_at = 2026-07-01
"""


@pytest.fixture
def operator_signed_copy(registry_copy: Path) -> Path:
    """A real modelo copy whose revision carries a hand-authored operator signoff.

    Seeded by appending the four scalars to the manifest, which is exactly the
    path deliberately left legal for the operator: the schema accepts
    ``operator_reviewed`` and this CLI cannot write it, so a genuine signoff can
    only ever arrive as a hand edit. The seed is proved to have compiled before
    any test reads it, so a test asserting a refusal cannot be passing because
    the fixture never established the state it refuses to touch.
    """
    manifest = _manifest_of(registry_copy)
    text = manifest.read_text(encoding=UTF_8_ENCODING)

    # The four scalars belong to the REVISION, so they must be written above the first
    # table header. Appending them to the end of the file binds them to whichever table
    # the manifest happens to close in -- today [family_dispositions.relations] -- and
    # the revision then refuses to compile at all.
    body = text.split("\n")
    first_table = next((index for index, line in enumerate(body) if line.startswith("[")), len(body))
    head = "\n".join(body[:first_table]).rstrip("\n")
    tail = "\n".join(body[first_table:])
    manifest.write_text(head + "\n" + _OPERATOR_SIGNOFF + tail, encoding=UTF_8_ENCODING)

    # Prove the seed landed where it was aimed, before any test reads it.
    seeded = tomllib.loads(manifest.read_text(encoding=UTF_8_ENCODING))
    assert seeded["review_status"] == "operator_reviewed"
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == _OPERATOR_SIGNATORY
    return registry_copy


@pytest.mark.parametrize(
    ("label", "arguments"),
    [
        ("substitution", {"reviewed_by": "agent:opus-executor", "reviewed_at": date(2026, 7, 28)}),
        ("reviewer_alone", {"reviewed_by": "agent:opus-executor"}),
        ("date_alone", {"reviewed_at": date(2026, 7, 28)}),
        ("erasure", {"review_status": StampableReviewStatus.PENDING_REVIEW}),
        ("downgrade", {"review_status": StampableReviewStatus.AGENT_REVIEWED, "reviewed_by": "agent:x"}),
    ],
)
def test_stamp_refuses_to_touch_the_review_axis_of_an_operator_signed_revision(
    operator_signed_copy: Path,
    label: str,
    arguments: _StampArguments,
) -> None:
    """The effective status governs, not only the requested one.

    Coercing the REQUESTED status closed the creation of a false operator claim
    and left its ATTRIBUTION writable. With no status supplied the coercion
    never fires and the merge falls through to the status the manifest already
    declares, so a lone ``reviewed_by`` wrote an agent's name against a declared
    ``operator_reviewed``: a manifest naming an agent as the operator's
    signatory. Nothing could see it — the operator ceiling counts revisions
    LACKING a signoff and this one still had one — and the overwritten identity
    and date are underivable, so nothing could restore them either.

    ``erasure`` is parametrised alongside substitution deliberately. Clearing a
    signoff DOES red the ratchet, but only after the name is already gone, so
    the ratchet catches the destruction while only this refusal prevents it.

    The byte assertion is the load-bearing half: a refusal raised after the
    rewrite would leave the false claim on disk and still satisfy
    ``pytest.raises``.
    """
    manifest = _manifest_of(operator_signed_copy)
    before = manifest.read_bytes()

    with pytest.raises(StampError, match="already declares review_status 'operator_reviewed'"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            registry_root=operator_signed_copy,
            **arguments,
        )

    assert manifest.read_bytes() == before, label
    revision = load_modelo_directory(operator_signed_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == _OPERATOR_SIGNATORY
    assert revision.reviewed_at == date(2026, 7, 1)


def test_an_authorship_claim_on_an_operator_signed_revision_is_still_served(
    operator_signed_copy: Path,
) -> None:
    """The paired half: authorship is ORTHOGONAL to signoff and must stay writable.

    Without this, a blanket "the resolved status must be stampable" rule would
    satisfy every refusal above while refusing an honest ``engineered_by`` write
    for a reason that has nothing to do with authorship, and no other assertion
    in this file would notice. Who built a revision is a different fact from who
    signed it off, so the write is served AND the signoff survives it intact.
    """
    result = stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="conformance-cli campaign",
        registry_root=operator_signed_copy,
    )

    assert result.written["engineered_by"] == '"conformance-cli campaign"'
    assert result.removed == ()
    revision = load_modelo_directory(operator_signed_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.engineered_by == "conformance-cli campaign"
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == _OPERATOR_SIGNATORY
    assert revision.reviewed_at == date(2026, 7, 1)


def test_the_review_axis_guard_reads_the_status_the_compiled_revision_carries(
    operator_signed_copy: Path,
) -> None:
    """The guard's input is the AUTHORITY, not a second reading of the manifest.

    The compiled revision is what every consumer of this registry sees, and the
    writer already loads it to prove the revision exists. Reading the declared
    status off the manifest text instead made the guard agree with the authority
    only because the loader refuses governance keys declared in a section
    fragment — the laundering path that refusal exists to close — so the guard's
    correctness rested on the mechanism it exists to complement.

    This asserts the two facts that make the swap meaningful: the compiled record
    carries the signoff, and the writer refuses on it.
    """
    compiled = load_modelo_directory(operator_signed_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert compiled.review_status is RevisionReviewStatus.OPERATOR_REVIEWED

    with pytest.raises(StampError, match=f"already declares review_status '{compiled.review_status.value}'"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            reviewed_by="agent:opus-executor",
            reviewed_at=date(2026, 7, 28),
            registry_root=operator_signed_copy,
        )


def test_a_governance_stamp_hidden_in_a_fragment_never_reaches_the_writer(registry_copy: Path) -> None:
    """The exhibit for why the guard reads the compiled record.

    A section fragment declaring the revision table with an operator signoff is
    the laundering shape: it would win the merge, so the compiled revision would
    claim a completed human review while ``revision.toml`` reads unstamped. The
    loader refuses it today, which is why the manifest text and the compiled
    record cannot currently disagree — and is precisely why a guard reading the
    manifest text was circular, since the case it would mis-handle is the case
    that refusal exists to prevent.

    Two assertions with different jobs. The write MUST NOT land, which stays true
    whichever mechanism refuses it. And the refusal today is the LOADER's, which
    is the tripwire: if that ever changes, this construction has become live and
    the compiled-status guard is what stands in front of it, so the second
    assertion failing is a signal to read this test rather than to delete it.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()
    laundered = manifest.parent / "casillas" / "zzz-laundered.toml"
    laundered.write_text(
        f'[revisions."{_STAMPED_REVISION}"]\n'
        'review_status = "operator_reviewed"\n'
        f'reviewed_by = "{_OPERATOR_SIGNATORY}"\n'
        "reviewed_at = 2026-07-01\n",
        encoding=UTF_8_ENCODING,
    )

    with pytest.raises(StampError) as refusal:
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            reviewed_by="agent:opus-executor",
            reviewed_at=date(2026, 7, 28),
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before
    assert "must be declared in the revision's revision.toml manifest" in str(refusal.value), (
        "the loader no longer refuses a governance stamp declared in a fragment; the compiled record "
        "and the manifest text can now disagree, which is the case the review-axis guard reads the "
        "compiled record to survive"
    )


def test_the_review_axis_guard_reads_the_vocabulary_and_not_one_hardcoded_status(
    registry_copy: Path,
) -> None:
    """A revision inside the vocabulary is untouched by the guard.

    The guard's predicate is membership of :class:`StampableReviewStatus`, never
    the single token ``operator_reviewed``, so a fourth status added to the core
    vocabulary without being added here enrols itself in the refusal. The other
    direction has to hold too: a revision already stamped ``agent_reviewed`` is
    a claim this CLI DID make, so restating it must remain legal or the tool
    could never correct its own record.
    """
    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:first",
        reviewed_at=date(2026, 7, 27),
        registry_root=registry_copy,
    )

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        reviewed_by="agent:second",
        reviewed_at=date(2026, 7, 28),
        registry_root=registry_copy,
    )

    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED
    assert revision.reviewed_by == "agent:second"
    # The date is restated with the reviewer rather than inherited: this case
    # used to leave 2026-07-27 standing against a reviewer who did not review
    # then, which is the smear the writer now refuses.
    assert revision.reviewed_at == date(2026, 7, 28)


def _stamp_a_first_review(root: Path, *, reviewer: str, reviewed: date) -> None:
    """Seed a real declared agent review through the real writer."""
    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by=reviewer,
        reviewed_at=reviewed,
        registry_root=root,
    )


def test_stamp_refuses_a_new_reviewer_that_does_not_restate_the_date(registry_copy: Path) -> None:
    """A re-attributed review must not inherit the previous reviewer's date.

    An omitted argument keeps what the manifest declares, which is right for
    every scalar except this pair: with a reviewer supplied and no date the merge
    carried the DECLARED date forward, so ``agent:second`` was recorded as having
    reviewed the revision on ``agent:first``'s date. In the one axis that is
    declared rather than derived, the record then states that a person reviewed a
    revision on a day they did not, and nothing downstream can tell.

    The CLI's today-defaulting does not cover this path either — it fires only
    when a status is supplied — so the refusal has to live at the writer, which
    is also the boundary a driver script reaches.

    The byte assertion is load-bearing: a refusal raised after the rewrite would
    leave the smeared claim on disk and still satisfy ``pytest.raises``.
    """
    _stamp_a_first_review(registry_copy, reviewer="agent:first", reviewed=date(2026, 1, 15))
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    with pytest.raises(StampError, match="without a date"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            reviewed_by="agent:second",
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.reviewed_by == "agent:first"
    assert revision.reviewed_at == date(2026, 1, 15)


def test_a_new_reviewer_stating_the_date_is_served(registry_copy: Path) -> None:
    """The paired half: re-attributing a review is legal when the date is stated.

    Without this, a guard refusing every reviewer change would satisfy the
    refusal above while making the tool unable to correct its own record, and no
    other assertion here would notice. Both the correction shape and the
    re-review shape are exercised: the same date restated for a typo fix, and a
    new date for a review happening now.
    """
    _stamp_a_first_review(registry_copy, reviewer="agent:frist", reviewed=date(2026, 1, 15))

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        reviewed_by="agent:first",
        reviewed_at=date(2026, 1, 15),
        registry_root=registry_copy,
    )
    corrected = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert corrected.reviewed_by == "agent:first"
    assert corrected.reviewed_at == date(2026, 1, 15)

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        reviewed_by="agent:second",
        reviewed_at=date(2026, 7, 28),
        registry_root=registry_copy,
    )
    re_reviewed = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert re_reviewed.reviewed_by == "agent:second"
    assert re_reviewed.reviewed_at == date(2026, 7, 28)


def test_restating_the_same_reviewer_or_only_the_date_stays_legal(registry_copy: Path) -> None:
    """The refusal keys on a CHANGE of reviewer, not on the reviewer argument.

    Two acts inherit a date honestly and must stay served. Restating the same
    reviewer inherits a date that is still that reviewer's own, so there is no
    claim to smear; and moving only the date is an explicit statement about the
    date, which is the opposite of inheriting one. A guard written as "refuse a
    reviewer with no date" would pass the refusal case above while breaking both
    of these.
    """
    _stamp_a_first_review(registry_copy, reviewer="agent:first", reviewed=date(2026, 1, 15))

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        reviewed_by="agent:first",
        registry_root=registry_copy,
    )
    restated = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert restated.reviewed_by == "agent:first"
    assert restated.reviewed_at == date(2026, 1, 15)

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        reviewed_at=date(2026, 7, 28),
        registry_root=registry_copy,
    )
    redated = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert redated.reviewed_by == "agent:first"
    assert redated.reviewed_at == date(2026, 7, 28)


def test_governance_keys_track_the_shipped_field_set() -> None:
    """The writer's key set IS the loader's, not a second copy of it."""
    assert set(GOVERNANCE_KEYS) == set(REVISION_GOVERNANCE_FIELDS)
    assert len(GOVERNANCE_KEYS) == len(REVISION_GOVERNANCE_FIELDS)


def test_stamp_roundtrips_through_the_real_registry_loader(registry_copy: Path) -> None:
    """What was written is what the compiled revision carries."""
    result = stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="conformance-cli gate",
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:conformance-cli-gate",
        reviewed_at=date(2026, 7, 27),
        registry_root=registry_copy,
    )

    assert result.removed == ()
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.engineered_by == "conformance-cli gate"
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED
    assert revision.reviewed_by == "agent:conformance-cli-gate"
    assert revision.reviewed_at == date(2026, 7, 27)


def test_stamp_touches_only_the_revision_manifest(registry_copy: Path) -> None:
    """The stamp cannot hide in a fragment, which is where it once silently won."""
    revision_dir = _manifest_of(registry_copy).parent
    before = {path: path.read_bytes() for path in scan_directory(revision_dir, recursive=True) if path.is_file()}

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="conformance-cli gate",
        registry_root=registry_copy,
    )

    after = {path: path.read_bytes() for path in scan_directory(revision_dir, recursive=True) if path.is_file()}
    assert set(after) == set(before), "the stamp must create and delete nothing"
    changed = [path for path, content in after.items() if before[path] != content]
    assert changed == [_manifest_of(registry_copy)]


def test_stamp_refuses_a_reviewer_recorded_against_an_unreviewed_status(registry_copy: Path) -> None:
    """The claim is refused, never silently discarded while reporting success."""
    manifest = _manifest_of(registry_copy)
    before = manifest.read_text(encoding=UTF_8_ENCODING)

    with pytest.raises(StampError, match="refusing to record"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            reviewed_by="agent:conformance-cli-gate",
            registry_root=registry_copy,
        )

    assert manifest.read_text(encoding=UTF_8_ENCODING) == before


def test_returning_a_revision_to_the_backlog_drops_the_reviewer(registry_copy: Path) -> None:
    """A reviewer must leave with the claim it attested to, or the schema refuses the pair."""
    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:conformance-cli-gate",
        reviewed_at=date(2026, 7, 27),
        registry_root=registry_copy,
    )

    result = stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        review_status=StampableReviewStatus.PENDING_REVIEW,
        registry_root=registry_copy,
    )

    assert set(result.removed) == {"reviewed_by", "reviewed_at"}
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.PENDING_REVIEW
    assert revision.reviewed_by is None
    assert revision.reviewed_at is None


def _non_governance_lines(raw: bytes) -> list[bytes]:
    """Split on the raw LF byte, keeping each line's remaining terminator bytes.

    Splitting the raw bytes rather than decoding leaves a CRLF line carrying its
    trailing carriage return, so a run that rewrote the file's terminators
    produces different elements here even though the decoded text is identical.
    The governance predicate is written out independently rather than imported from
    the writer, so this comparison cannot agree with a broken implementation by
    sharing its definition of which lines may move.

    Trailing empty elements are dropped because the writer deliberately collapses
    a manifest to exactly one terminating newline, and the shipped manifests end
    with a blank line. That is a one-byte EOF normalisation, not the whole-file
    terminator rewrite this comparison exists to catch, and the caller asserts
    the terminator count separately so dropping them here hides neither.
    """
    pattern = re.compile(rf"\s*(?:{'|'.join(GOVERNANCE_KEYS)})\s*=")
    lines = [line for line in raw.split(b"\n") if not pattern.match(line.decode(UTF_8_ENCODING))]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _pin_mtime(path: Path) -> float:
    """Set a distant fixed mtime and return it, so a write is observable.

    The pre-write refusal and the post-write restore leave byte-identical files,
    so bytes alone cannot say which branch ran. A write moves the mtime and a
    refusal does not, which distinguishes them without a mock, a patch, or a
    hook in production code.
    """
    os.utime(path, (1_000_000_000, 1_000_000_000))
    return path.stat().st_mtime


def test_a_malformed_sibling_fragment_is_refused_before_anything_is_written(registry_copy: Path) -> None:
    """A tree that already fails to load is refused by the PRE-write check.

    Kept as its own case because it used to be mislabelled as the rollback
    proof. It is a real and useful refusal — a tree the loader rejects must not
    be stamped — but nothing is written on this path, so its manifest assertion
    is true whatever the restore does. Naming it for the branch it actually
    exercises stops the next reader inheriting the same misreading.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()
    original_mtime = _pin_mtime(manifest)

    broken = manifest.parent / "casillas" / "zzzz-broken.toml"
    broken.write_text("this is not valid TOML = = =\n", encoding=UTF_8_ENCODING)

    with pytest.raises(StampError, match="registry refuses to load the modelo"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            engineered_by="a stamp that must not survive",
            registry_root=registry_copy,
        )

    assert manifest.stat().st_mtime == original_mtime, "the pre-write refusal must not touch the file"
    assert manifest.read_bytes() == before


def test_stamp_restores_the_manifest_when_the_written_tree_no_longer_loads(registry_copy: Path) -> None:
    """The rollback, proved by a reload the WRITE ITSELF makes fail.

    The failure has to originate in the written bytes, because the pre-write
    check loads the same tree the post-write reload does: any breakage staged
    beforehand is caught before a byte is written, and the restore never runs.
    An identity carrying an interior newline is the honest trigger. It survives
    the trim, which strips only the ends; the schema probe accepts it, because a
    newline in a string is nothing pydantic objects to; and the rendered basic
    string then carries a literal newline, which TOML forbids. So the manifest
    the writer produced is one the loader rejects — exactly the event the
    two-stage write-then-verify design exists for — and the restore is what
    keeps it off disk.

    Two assertions carry the proof. The mtime is pinned first and must MOVE,
    which is what pins this test to the post-write branch: without it the case
    silently degrades into the pre-write one, which is the trap the previous
    version of this test fell into and passed under for three review rounds. And
    the comparison is on BYTES, not ``read_text``, which decodes under universal
    newlines and normalises away the exact difference the module's "the original
    bytes are restored" claim is about: on Windows the restore expanded all
    eight LF terminators of this manifest to CRLF and grew it from 422 to 430
    bytes, and the text comparison called that clean.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()
    original_mtime = _pin_mtime(manifest)

    with pytest.raises(StampError, match="registry refuses to load the modelo"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            engineered_by="a stamp\nthat must not survive",
            registry_root=registry_copy,
        )

    assert manifest.stat().st_mtime != original_mtime, "the restore was never reached; nothing was written"
    assert manifest.read_bytes() == before
    assert b"must not survive" not in before


def test_a_successful_stamp_leaves_every_other_line_byte_identical(registry_copy: Path) -> None:
    """The writer claims a line editor; this measures whether it is one.

    The rollback assertion above can only ever exercise the restore. A
    SUCCESSFUL write was never measured on bytes at all, and it was the worse
    case: writing through ``write_text`` rewrote every terminator in the file, so
    a one-line stamp landed as a whole-file rewrite. In a shared worktree that is
    invisible in review, because ``git diff`` normalises line endings under
    ``text=auto`` while the working tree carries the rewrite.

    Comparing the non-governance lines as raw byte slices is what flips: under a
    terminator rewrite every single element differs, while under a true line edit
    none do.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="conformance-cli gate",
        review_status=StampableReviewStatus.AGENT_REVIEWED,
        reviewed_by="agent:conformance-cli-gate",
        reviewed_at=date(2026, 7, 27),
        registry_root=registry_copy,
    )
    after = manifest.read_bytes()

    assert after != before, "the stamp must actually have written something"
    assert _non_governance_lines(after) == _non_governance_lines(before)
    assert after.count(b"\x0d\x0a") == before.count(b"\x0d\x0a")


def test_stamp_refuses_an_identifier_that_would_escape_the_registry_root(registry_copy: Path) -> None:
    """Path traversal is refused on the shape, before any path is built."""
    with pytest.raises(StampError, match="not a plain registry identifier"):
        stamp_revision("../../etc", _STAMPED_REVISION, engineered_by="x", registry_root=registry_copy)


def test_stamp_refuses_a_revision_the_loaded_tree_does_not_declare(registry_copy: Path) -> None:
    """Existence is decided by the compiled record, never by a directory listing."""
    ghost = registry_copy / "modelos" / _STAMPED_MODELO / "revisions" / "9999-invented"
    ghost.mkdir()
    (ghost / "revision.toml").write_text('[revisions."9999-invented"]\n', encoding=UTF_8_ENCODING)

    with pytest.raises(StampError):
        stamp_revision(_STAMPED_MODELO, "9999-invented", engineered_by="x", registry_root=registry_copy)


def test_stamp_refuses_when_nothing_was_supplied_to_write(registry_copy: Path) -> None:
    """A no-op write would report success while changing nothing."""
    with pytest.raises(StampError, match="nothing to stamp"):
        stamp_revision(_STAMPED_MODELO, _STAMPED_REVISION, registry_root=registry_copy)


@pytest.mark.parametrize("field", ["engineered_by", "reviewed_by"])
def test_stamp_refuses_a_provenance_claim_that_names_nobody(registry_copy: Path, field: str) -> None:
    """A whitespace identity is a claim with no claimant, so it is never written."""
    manifest = _manifest_of(registry_copy)
    before = manifest.read_text(encoding=UTF_8_ENCODING)
    arguments: _StampArguments
    if field == "engineered_by":
        arguments = {"engineered_by": "   "}
    else:
        arguments = {
            "reviewed_by": "   ",
            "review_status": StampableReviewStatus.AGENT_REVIEWED,
            "reviewed_at": date(2026, 7, 27),
        }

    with pytest.raises(StampError, match="names nobody"):
        stamp_revision(_STAMPED_MODELO, _STAMPED_REVISION, registry_root=registry_copy, **arguments)

    assert manifest.read_text(encoding=UTF_8_ENCODING) == before


def test_stamp_trims_a_padded_identity_before_writing_it(registry_copy: Path) -> None:
    """Padding never becomes part of a name; the flip is that the stored value differs."""
    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="  conformance-cli gate\n",
        registry_root=registry_copy,
    )

    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.engineered_by == "conformance-cli gate"


# --------------------------------------------------------------------------- #
# stamp: the Typer command layer, exercised end to end
# --------------------------------------------------------------------------- #


def _stamp_cli(root: Path, *arguments: str) -> Result:
    """Invoke the real ``stamp`` verb against a byte copy of a shipped modelo tree."""
    return CliRunner().invoke(
        app,
        ["stamp", _STAMPED_MODELO, _STAMPED_REVISION, *arguments, "--registry-root", str(root)],
    )


def test_the_stamp_command_defaults_the_review_date_to_today(registry_copy: Path) -> None:
    """The command layer's own logic, exercised through the real app for the first time.

    ``stamp_revision`` has always accepted a registry root and this verb never
    passed one, so the only CLI-level stamp coverage that could exist was a
    refusal caught at the parse boundary: the today-defaulting of ``reviewed_at``
    and the translation of a writer refusal into a parameter error had no
    end-to-end test of any kind. Neither is reachable from the writer's own tests,
    because neither lives in the writer.

    The flip is sharp because the schema requires a date alongside a reviewed
    status: without the default this same invocation is refused rather than
    served, so the exit code and the compiled date move together.
    """
    result = _stamp_cli(registry_copy, "--review-status", "agent_reviewed", "--reviewed-by", "agent:opus-executor")

    assert result.exit_code == 0, result.stdout
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED
    reviewed_at = revision.reviewed_at
    assert reviewed_at == datetime.now(tz=UTC).date()
    assert reviewed_at is not None
    # Echoed back, so the written value is never implicit to the caller.
    assert f"reviewed_at={reviewed_at.isoformat()}" in result.stdout


def test_the_stamp_command_turns_a_writer_refusal_into_a_parameter_error(registry_copy: Path) -> None:
    """A refusal must reach the operator as an instructive parameter error.

    Without the translation the writer's exception escapes the command and the
    caller meets a traceback: same refusal, no message they can act on, and a
    different exit code. Both halves are asserted, so removing the translation
    flips the code AND the visible reason.
    """
    manifest = _manifest_of(registry_copy)
    before = manifest.read_bytes()

    result = _stamp_cli(registry_copy, "--engineered-by", "   ")

    assert result.exit_code == 2, result.output
    assert "names nobody" in result.output
    assert manifest.read_bytes() == before


def test_the_stamp_command_refuses_to_re_attribute_an_operator_signoff(operator_signed_copy: Path) -> None:
    """The re-attribution refusal, proved through the app rather than the writer.

    Every other test of this refusal calls ``stamp_revision`` directly, which
    leaves the command's own argument parsing and error translation unproved. It
    could not be reached at all until the verb accepted a registry root: without
    one the only tree the command can address is the shipped registry, so
    exercising it end to end would have meant writing a fabricated review into
    the bundled data.

    The byte assertion is load-bearing: a refusal raised after the rewrite would
    leave the re-attributed signoff on disk and still produce a non-zero exit.
    """
    manifest = _manifest_of(operator_signed_copy)
    before = manifest.read_bytes()

    result = _stamp_cli(operator_signed_copy, "--reviewed-by", "agent:opus-executor", "--reviewed-at", "2026-07-28")

    assert result.exit_code != 0
    assert "already declares review_status 'operator_reviewed'" in result.output
    assert manifest.read_bytes() == before
    revision = load_modelo_directory(operator_signed_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.reviewed_by == _OPERATOR_SIGNATORY


@pytest.mark.parametrize(
    "spelling",
    [f"[revisions.'{_STAMPED_REVISION}']", f'[ revisions."{_STAMPED_REVISION}" ]'],
)
def test_a_header_the_loader_accepts_but_the_line_editor_cannot_address_is_refused(
    registry_copy: Path,
    spelling: str,
) -> None:
    """The branch a coverage pragma called unreachable, reached.

    The pragma's stated ground was that the governance read proves the table
    exists. It proves the table exists in PARSED TOML, and the line editor
    compares against one exact spelling of the header LINE. Both spellings here
    are valid TOML for the same table, and the assertion that the tree still LOADS
    is the load-bearing one: it is what makes the manifest a real authoring state
    rather than a broken file the pre-write check would have caught first.

    It fails safe, so the cost was never a bad write — it was a comment telling
    the next reader a branch cannot happen when it can, and a caller left with a
    manifest the registry accepts and this writer says it has no header for.
    """
    manifest = _manifest_of(registry_copy)
    canonical = f'[revisions."{_STAMPED_REVISION}"]'
    rewritten = manifest.read_text(encoding=UTF_8_ENCODING).replace(canonical, spelling, 1)
    manifest.write_bytes(rewritten.encode(UTF_8_ENCODING))
    before = manifest.read_bytes()

    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.id == _STAMPED_REVISION, "the rewritten header must still compile, or this proves nothing"

    with pytest.raises(StampError, match="is not present as a whole line"):
        stamp_revision(
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            engineered_by="conformance-cli gate",
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before


# --------------------------------------------------------------------------- #
# audit: a growing registry versus a regressing one
# --------------------------------------------------------------------------- #


def _report_with_one_more_revision(report: ConformanceReport) -> ConformanceReport:
    """Return the real report as if a ninety-first revision had landed unstamped.

    The row is a real composed row re-keyed, so every derived count it feeds
    moves the way a genuine addition would; the census and the population move
    with it, and the new revision declares no governance because that is what a
    peer landing a revision mid-campaign actually produces.
    """
    pending = RevisionReviewStatus.PENDING_REVIEW.value
    arrival = report.rows[-1].model_copy(
        update={"revision": f"{report.rows[-1].revision}-arriving", "review_status": pending},
    )
    census = dict(report.review_status_census)
    census[pending] += 1
    return report.model_copy(
        update={
            "rows": (*report.rows, arrival),
            "revision_count": report.revision_count + 1,
            "review_status_census": census,
        },
    )


def _report_with_locale_labels(
    report: ConformanceReport,
    *,
    required_delta: int,
    translated_delta: int,
) -> ConformanceReport:
    """Return the real report with the FIRST audited locale's leaf counts moved.

    One locale only, so the registry-wide sums move by exactly the deltas asked
    for and the assertion can name the arithmetic instead of a magic number.
    """
    first, *rest = report.locale_axis
    moved = first.model_copy(
        update={
            "labels_required": first.labels_required + required_delta,
            "labels_translated": first.labels_translated + translated_delta,
        },
    )
    return report.model_copy(update={"locale_axis": (moved, *rest)})


def test_a_ninety_first_revision_landing_unstamped_leaves_the_gate_green(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The immediate failure this ratchet exists to remove, simulated end to end.

    Under the retired shape all three review counters were shrink-only ceilings
    pinned at the full population, so this exact arrival took every one of them
    past its ceiling and reddened the only gating exit the surface has. Recording
    the new state was then refused unless the operator asserted a deliberate
    weakening, so an honest registry addition and a loosening of the ratchet came
    through the same door.

    The population moves and the recorded work does not, which is the whole
    content of the fix, so both halves are asserted: the gate passes AND every
    progress floor is byte-identical across the arrival. Asserting only the pass
    would hold just as well if the counters had been deleted.
    """
    grown = _report_with_one_more_revision(validated_report)

    assert grown.revision_count == validated_report.revision_count + 1
    result = check_conformance_ratchet(grown, load_baseline())

    assert result.passed, result.violations
    # Read through the real capture path rather than a helper mirroring it: a
    # second copy of the projection would agree with a broken original.
    before = _baseline_captured_from(validated_report, tmp_path / "before.json").progress
    after = _baseline_captured_from(grown, tmp_path / "after.json").progress
    for field_name in ConformanceProgressFloors.model_fields:
        assert getattr(after, field_name) == getattr(before, field_name), field_name


def test_a_new_revision_stays_green_even_once_the_stamping_campaign_is_underway(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The case that decides between progress floors and a ratio ceiling.

    At today's total backlog a ratio ceiling would survive the arrival by
    coincidence: ninety of ninety unreviewed is a fraction of 1.0, and
    ninety-one of ninety-one is still 1.0. The choice only shows once the
    campaign has made progress, so this seeds a baseline at forty agent-reviewed
    revisions of ninety and then lands the ninety-first unstamped.

    The backlog fraction genuinely worsens — that is asserted here rather than
    reasoned, because it is the premise of the ruling — and the gate stays green
    anyway, because the recorded work is intact. A ratio ceiling would red on
    every peer's registry addition for the whole duration of the campaign this
    surface exists to support, which is the same complaint arriving later and
    harder to read.
    """
    total = validated_report.revision_count
    underway = _with_review_statuses(
        validated_report,
        [RevisionReviewStatus.AGENT_REVIEWED] * 40 + [RevisionReviewStatus.PENDING_REVIEW] * (total - 40),
    )
    baseline = _baseline_captured_from(underway, tmp_path / "underway.json")
    grown = _report_with_one_more_revision(underway)
    grown_progress = _baseline_captured_from(grown, tmp_path / "grown.json").progress

    before = baseline.progress.reviewed_revisions / underway.revision_count
    after = grown_progress.reviewed_revisions / grown.revision_count
    assert after < before, "the seeded arrival must genuinely worsen the reviewed fraction, or this proves nothing"

    result = check_conformance_ratchet(grown, baseline)
    assert result.passed, result.violations
    assert grown_progress.reviewed_revisions == baseline.progress.reviewed_revisions


def test_a_lost_translation_reds_the_gate_even_while_the_registry_grows(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The other direction, and it must survive the growth that used to mask nothing.

    The retired ceiling capped leaves left UNTRANSLATED, which every new casilla
    raises by one per audited locale — so it reddened on registry growth and said
    nothing about translation being lost. The floor counts leaves ACTUALLY
    TRANSLATED, so the two cases separate: here the required population grows by
    five and one authored leaf is deleted at the same time, and the gate reds on
    the deletion rather than on the growth.

    The paired case below is what makes this non-vacuous: the same growth without
    the deletion must stay green, or the floor would just be the old ceiling
    wearing a new name.
    """
    baseline = _baseline_captured_from(validated_report, tmp_path / "committed.json")
    regressed = _report_with_locale_labels(validated_report, required_delta=5, translated_delta=-1)

    result = check_conformance_ratchet(regressed, baseline)

    assert not result.passed
    assert any(
        item.startswith(
            f"translated_locale_labels fell from {validated_report.translated_locale_labels} to "
            f"{validated_report.translated_locale_labels - 1}",
        )
        for item in result.progress_violations
    ), result.progress_violations
    assert not result.ratchet_violations, "growth in required leaves must not read as a defect"


def test_new_casillas_adding_untranslated_leaves_leave_the_gate_green(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The paired half: registry growth alone must not red the translation gate.

    Every new casilla adds one required leaf per audited locale and translates
    none of them, which is exactly the movement the retired ceiling punished.
    Without this case the floor above could be satisfied by a counter that simply
    never fires.
    """
    baseline = _baseline_captured_from(validated_report, tmp_path / "committed.json")
    grown = _report_with_locale_labels(validated_report, required_delta=5, translated_delta=0)

    assert grown.audited_locale_leaves == validated_report.audited_locale_leaves + 5
    result = check_conformance_ratchet(grown, baseline)

    assert result.passed, result.violations


# --------------------------------------------------------------------------- #
# stamp: the shipped tree is reachable only by naming it
# --------------------------------------------------------------------------- #


def _shipped_manifest() -> Path:
    """The SHIPPED Modelo 130 manifest — the file the incident actually wrote to."""
    return bundled_registry_root() / "modelos" / _STAMPED_MODELO / "revisions" / _STAMPED_REVISION / "revision.toml"


def _flat(text: str) -> str:
    """Strip a rich error panel back to bare characters for substring assertions.

    A parameter error is rendered inside a bordered, width-wrapped panel, so a
    long value — a registry path is the case here — is broken across lines with
    box glyphs and padding inserted at the seam. A naive ``in result.output``
    then passes or fails on the terminal width of whoever runs the suite, which
    is a flake dressed as an assertion. Removing whitespace and the border glyphs
    from both sides compares the characters the message actually carries.
    """
    return "".join(text.split()).replace("│", "")


def test_the_writer_refuses_to_be_called_without_naming_a_registry_tree() -> None:
    """Dropping the root is a TypeError at the call, not a write to shipped data.

    This is the incident reproduced as the mutation that caused it. A test
    mutation upstream dropped ``registry_root=`` from one call site; the
    parameter defaulted to the bundled AEAT tree, and the suite wrote an
    ``agent_reviewed`` stamp naming an agent and today's date into the shipped
    Modelo 130 manifest. The parameter now has no default, so the same omission
    cannot construct a call at all.

    Asserted on the message rather than on the bare exception type, because a
    ``TypeError`` from any other cause would satisfy a bare ``pytest.raises`` and
    prove nothing about this argument. No manifest assertion is made here on
    purpose: binding fails before the function body runs, so "the file is
    unchanged" would hold however this code behaved — the always-true
    assertion trap this class of test keeps falling into.
    """
    with pytest.raises(TypeError, match="registry_root"):
        signature(stamp_revision).bind(_STAMPED_MODELO, _STAMPED_REVISION, engineered_by="agent:opus-executor")

    with pytest.raises(TypeError, match="registry_root"):
        signature(revision_manifest_path).bind(_STAMPED_MODELO, _STAMPED_REVISION)


def test_the_stamp_command_refuses_when_no_registry_tree_is_named() -> None:
    """The forgotten flag no longer resolves to the shipped registry.

    Before this guard, the identical invocation wrote a fabricated agent review
    into the bundled Modelo 130 manifest. The byte assertion is load-bearing
    here, unlike at the writer boundary: this call really did reach a write path,
    so an unchanged shipped manifest is a fact about the refusal rather than
    about argument binding.

    The message assertions prove the command BODY ran, which matters because a
    refusal raised at the parse boundary would also exit non-zero while proving
    nothing about the resolution rule under test.
    """
    shipped = _shipped_manifest()
    before = shipped.read_bytes()

    result = CliRunner().invoke(
        app,
        ["stamp", _STAMPED_MODELO, _STAMPED_REVISION, "--engineered-by", "agent:opus-executor"],
    )

    assert result.exit_code == 2, result.output
    flat = _flat(result.output)
    assert _flat("--registry-root") in flat
    assert _flat("--bundled-registry") in flat
    assert shipped.read_bytes() == before, "a refused stamp must leave the shipped registry untouched"


def test_the_stamp_command_refuses_two_registry_trees_at_once(registry_copy: Path) -> None:
    """Naming both doors is a contradiction, and guessing one would be worse.

    The two flags resolve to different trees by construction, so silently
    preferring either would send a write somewhere the caller did not ask for —
    the same failure the undefaulted root closes, arriving through
    over-specification instead of under-specification.
    """
    shipped = _shipped_manifest()
    before = shipped.read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "stamp",
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            "--engineered-by",
            "agent:opus-executor",
            "--registry-root",
            str(registry_copy),
            "--bundled-registry",
        ],
    )

    assert result.exit_code == 2, result.output
    assert _flat("two different trees") in _flat(result.output)
    assert shipped.read_bytes() == before
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.engineered_by is None, "the copy must not have been stamped either"


def test_a_registry_root_that_resolves_to_the_shipped_tree_is_refused_by_name() -> None:
    """Two doors to shipped data, one of them silent, is the state this closes.

    ``--bundled-registry`` earns its keep only if it is the ONLY way there: a
    path that happens to resolve to the bundled tree reaches the same file while
    reading, in the command line and in shell history, like an ordinary sandbox
    run. The refusal names the flag that says what is happening.
    """
    shipped = _shipped_manifest()
    before = shipped.read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "stamp",
            _STAMPED_MODELO,
            _STAMPED_REVISION,
            "--engineered-by",
            "agent:opus-executor",
            "--registry-root",
            str(bundled_registry_root()),
        ],
    )

    assert result.exit_code == 2, result.output
    assert _flat("--bundled-registry") in _flat(result.output)
    assert shipped.read_bytes() == before


def test_the_bundled_flag_really_reaches_the_shipped_tree_and_still_writes_nothing() -> None:
    """The override is proved to resolve where it claims, without stamping shipped data.

    A refusal test that never reached the intended tree would pass for the wrong
    reason, so the resolution is proved by driving the flag at a modelo id the
    shipped registry does not declare and reading WHERE the writer says it
    looked: the reported path is under the bundled root, which only this flag can
    produce. Nothing is written, because the manifest-existence check refuses
    before any governance line is rendered.
    """
    bundled = bundled_registry_root()
    absent_modelo = "999"
    assert not (bundled / "modelos" / absent_modelo).exists(), "the probe modelo must genuinely be absent"

    result = CliRunner().invoke(
        app,
        ["stamp", absent_modelo, _STAMPED_REVISION, "--engineered-by", "agent:opus-executor", "--bundled-registry"],
    )

    assert result.exit_code == 2, result.output
    flat = _flat(result.output)
    assert _flat("no revision manifest to stamp") in flat
    assert _flat(str(bundled / "modelos" / absent_modelo)) in flat
    assert not (bundled / "modelos" / absent_modelo).exists(), "the probe must have created nothing"


def test_a_named_sandbox_root_is_served_while_the_shipped_tree_stays_untouched(registry_copy: Path) -> None:
    """The other direction: the refusals above must not have closed the verb.

    A safety change that also broke the working path would show up as four green
    refusal tests and nothing to say whether the tool still functions, so the
    served case is asserted beside them — and the shipped manifest is asserted
    unchanged in the SUCCESS case too, which is the one place a leak would
    actually land bytes.
    """
    shipped = _shipped_manifest()
    before = shipped.read_bytes()

    result = _stamp_cli(registry_copy, "--engineered-by", "agent:opus-executor")

    assert result.exit_code == 0, result.output
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.engineered_by == "agent:opus-executor"
    assert shipped.read_bytes() == before

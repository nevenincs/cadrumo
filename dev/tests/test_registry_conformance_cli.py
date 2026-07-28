"""Real-behaviour tests for the ``python -m dev.registry.conformance`` surface.

Every test here invokes the real CLI against the real bundled registry, or the
real writer against a real copy of a shipped modelo tree. Nothing is mocked,
stubbed, skipped, or marked expected-to-fail.

The proofs are written to FLIP AN ASSERTION rather than to kill a fixture. A
test that only checks a function was called proves the wiring and none of the
semantics, and this campaign's first review round caught exactly that weakness
in a sibling gate. So: the ratchet is proved by moving ONE baseline counter and
watching the same command on the same tree change its exit code; the
absence-is-not-zero rule is proved by rendering two reports differing only in a
``None`` where the other has ``0.0`` and asserting the renders differ; the
oracle attribution gap is proved by injecting one real gap record and watching
it reach all three surfaces that must show it; and the stamp rollback is proved
by making the post-write reload genuinely fail and asserting the manifest went
back ON BYTES.

That last one is the campaign's worked example of how a proof rots. It staged a
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
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.application.registry import (
    RegistryConformanceProfile,
    audit_bundled_registry_conformance,
)
from cadrumo.core import ExternalOracleCorpus, RevisionReviewStatus
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    REVISION_GOVERNANCE_FIELDS,
    UnattributedOraclePayload,
    load_bundled_external_oracle_inventory,
    load_modelo_directory,
)

from ..registry.conformance._stamp import (
    GOVERNANCE_KEYS,
    StampableReviewStatus,
    StampError,
    stamp_revision,
)
from ..registry.conformance.cli import app
from ..registry.conformance.manager import (
    NOT_MEASURED,
    ConformanceBaseline,
    ConformanceReport,
    baseline_path,
    baseline_weakenings,
    build_conformance_report,
    build_coverage_report,
    check_conformance_ratchet,
    load_baseline,
    load_conformance_report,
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

_OPERATOR_NAME = "Gergely Wootsch"


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
    agent = _report_with_review(validated_profile, status=RevisionReviewStatus.AGENT_REVIEWED, reviewer=_OPERATOR_NAME)
    operator = _report_with_review(
        validated_profile,
        status=RevisionReviewStatus.OPERATOR_REVIEWED,
        reviewer=_OPERATOR_NAME,
    )

    agent_field = _reviewer_field(render_report(agent), row.modelo, row.revision)
    operator_field = _reviewer_field(render_report(operator), row.modelo, row.revision)

    assert agent_field != operator_field
    assert "agent_reviewed" in agent_field
    assert "operator_reviewed" in operator_field
    assert _OPERATOR_NAME in agent_field
    # The bare name is never the whole rendered value, which is what a scanning
    # reader would otherwise take at face value.
    assert agent_field != json.dumps(_OPERATOR_NAME)


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
        reviewer=_OPERATOR_NAME,
    )
    row = composed.rows[0]

    assert row.reviewed_by == _OPERATOR_NAME
    assert row.reviewed_by_attribution == f"agent_reviewed:{_OPERATOR_NAME}"
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
        reviewer=_OPERATOR_NAME,
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
    assert payload["reviewed_by"] == _OPERATOR_NAME
    assert payload["reviewed_by_attribution"] == f"{RevisionReviewStatus.AGENT_REVIEWED.value}:{_OPERATOR_NAME}"


@pytest.mark.parametrize(
    "spoof",
    ["operator_reviewed:Gergely Wootsch", "OPERATOR_REVIEWED:Gergely Wootsch", "agent_reviewed:somebody"],
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

    ``agent:opus-executor`` is the convention this campaign's own records use,
    and the join was never ambiguous — no status value carries a colon, so the
    tier is everything before the first one. A blanket colon refusal would
    satisfy the spoof test above while breaking every honest caller, and no
    other assertion here would notice.
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
    seeded = _baseline_with(tmp_path / "lowered.json", ceiling="unreviewed_revisions", delta=-1)
    result = CliRunner().invoke(app, ["audit", "--check", "--baseline", str(seeded)])

    assert result.exit_code == 1, result.stdout
    assert "passed=false" in result.stdout
    assert "violation kind=ratchet" in result.stdout
    assert "unreviewed_revisions grew" in result.stdout


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


def _baseline_captured_from(report: ConformanceReport, path: Path) -> ConformanceBaseline:
    """Capture a baseline from ``report`` through the real recording path."""
    record_baseline(report, note="captured by the conformance CLI gate", recorded_at="2026-07-28", path=path)
    return load_baseline(path)


def test_an_agent_review_sweep_empties_the_pending_ceiling_but_not_the_operator_ceiling(
    validated_report: ConformanceReport,
) -> None:
    """The act the CLI is DESIGNED to allow must not read as progress on the gated number.

    ``stamp --review-status agent_reviewed`` is a legitimate verb an agent may
    run across every revision in the tree. Doing so drives the pending census to
    zero. If that census is the only gated review counter, the one number CI
    protects reaches zero without a single human signoff, and the three-state
    vocabulary collapses back into the two-state laundering it was introduced to
    remove. The operator counter must sit still through exactly that sweep.
    """
    total = validated_report.revision_count
    swept = _with_review_statuses(validated_report, [RevisionReviewStatus.AGENT_REVIEWED] * total)

    rendered = render_audit(check_conformance_ratchet(swept, load_baseline()))

    assert "ceiling counter=unreviewed_revisions current=0 " in rendered
    assert f"current={total} " in _ceiling_line(rendered, "revisions_without_operator_review")
    # The sweep is not itself a regression: nothing grew, so the audit still
    # passes. What must not happen is the operator backlog reading as cleared.
    assert check_conformance_ratchet(swept, load_baseline()).passed


def test_a_lost_operator_signoff_reds_the_operator_ceiling_the_pending_ceiling_cannot_see(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """The decisive flip: one regression, invisible to the old counter, caught by the new.

    Both states are fully agent-or-operator reviewed, so the pending census is
    zero in each and ``unreviewed_revisions`` is flat across the regression. The
    only difference is that one revision's operator signoff became an agent
    review. Before this ceiling existed the audit passed on that; it must now
    fail, and it must name the counter that moved.
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
    assert any(
        item == f"revisions_without_operator_review grew from {total - 10} to {total - 9}"
        for item in result.ratchet_violations
    ), result.ratchet_violations
    # The old counter is blind to it: zero pending in both states.
    assert all("unreviewed_revisions" not in item for item in result.ratchet_violations)


def test_the_operator_ceiling_gates_the_real_cli_at_the_committed_baseline(tmp_path: Path) -> None:
    """The new counter has teeth in the shipped verb, not only in a fold.

    Same command, same tree, one lowered ceiling: the exit code flips. Without
    this the field could be committed, rendered, and never actually consulted by
    the gate.
    """
    seeded = _baseline_with(tmp_path / "lowered.json", ceiling="revisions_without_operator_review", delta=-1)
    result = CliRunner().invoke(app, ["audit", "--check", "--baseline", str(seeded)])

    assert result.exit_code == 1, result.stdout
    assert "revisions_without_operator_review grew" in result.stdout


def test_the_committed_operator_ceiling_equals_what_the_tool_measures(
    validated_report: ConformanceReport,
    tmp_path: Path,
) -> None:
    """A ceiling above the measurement licenses a regression the gate cannot see.

    Anchored to a FRESH measurement, not to another committed number. The
    previous form asserted the operator ceiling equalled the ``composed_revisions``
    floor, which is a CENSUS FACT — true only while nothing in the tree carries
    an operator signoff — dressed as a seeding rule. It would have failed on the
    campaign's first genuine signoff, for a reason having nothing to do with
    seeding, and the cheapest fix available to whoever met that failure would
    have been to delete it.

    The invariant that survives is the one worth keeping: the committed ceiling
    equals what the tool measures right now. Above the measurement is headroom,
    and a revision can lose its signoff inside it without the gate noticing.
    Below it the gate is already red. Either way the answer is to re-record the
    baseline, which is what the failure message should send a reader to do.
    """
    measured = _baseline_captured_from(validated_report, tmp_path / "measured.json")
    committed = load_baseline()

    assert committed.ceilings.revisions_without_operator_review == (
        measured.ceilings.revisions_without_operator_review
    ), "the committed operator ceiling has drifted from the measurement; re-record the baseline"


def _report_with_one_more_grounding_finding(report: ConformanceReport) -> ConformanceReport:
    """Return the real report with one extra grounding finding: a RAISED ceiling."""
    return report.model_copy(update={"grounding_finding_count": report.grounding_finding_count + 1})


def _report_with_one_fewer_revision(report: ConformanceReport) -> ConformanceReport:
    """Return the real report having composed one revision fewer: a LOWERED floor.

    The census is moved with the count so the two never disagree, and a
    ``pending_review`` row is the one dropped so the ceilings MOVE DOWNWARD while
    the floor moves down too. A capture of this report therefore strengthens two
    ceilings and weakens one floor at once, which is the mixture the guard has
    to read correctly rather than a single unambiguous movement.
    """
    census = dict(report.review_status_census)
    census[RevisionReviewStatus.PENDING_REVIEW.value] -= 1
    return report.model_copy(
        update={
            "rows": report.rows[:-1],
            "revision_count": report.revision_count - 1,
            "review_status_census": census,
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

    The seeded report strengthens two ceilings while lowering one floor, so this
    also asserts the guard reads the two directions separately instead of
    refusing any movement at all.
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

    # The two directions are read separately: the strengthened ceilings must not
    # be reported as weakenings, or the guard is refusing movement rather than
    # weakening and the refusal teaches nothing.
    candidate = _baseline_captured_from(shrunken, tmp_path / "candidate.json")
    committed = load_baseline(path)
    total = validated_report.revision_count
    assert baseline_weakenings(candidate, committed) == (
        f"floor composed_revisions would fall from {total} to {total - 1}, demanding less measurement",
    )
    assert candidate.ceilings.unreviewed_revisions < committed.ceilings.unreviewed_revisions


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


def _baseline_with(path: Path, *, ceiling: str | None = None, floor: str | None = None, delta: int = 0) -> Path:
    """Write a copy of the committed baseline with exactly one counter moved."""
    raw = json.loads(baseline_path().read_text(encoding=UTF_8_ENCODING))
    if ceiling is not None:
        raw["ceilings"][ceiling] += delta
    if floor is not None:
        raw["floors"][floor] += delta
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
            review_status=RevisionReviewStatus.OPERATOR_REVIEWED,  # type: ignore[arg-type]
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
        review_status=RevisionReviewStatus.AGENT_REVIEWED,  # type: ignore[arg-type]
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
            review_status=spelling,  # type: ignore[arg-type]
            registry_root=registry_copy,
        )

    assert manifest.read_bytes() == before


_OPERATOR_SIGNOFF = """engineered_by = "the operator, by hand"
review_status = "operator_reviewed"
reviewed_by = "Gergely Wootsch (operator)"
reviewed_at = 2026-07-01
"""


@pytest.fixture
def operator_signed_copy(registry_copy: Path) -> Path:
    """A real modelo copy whose revision carries a hand-authored operator signoff.

    Seeded by appending the four scalars to the manifest, which is exactly the
    path the governing decision keeps legal for the operator: the schema accepts
    ``operator_reviewed`` and this CLI cannot write it, so a genuine signoff can
    only ever arrive as a hand edit. The seed is proved to have compiled before
    any test reads it, so a test asserting a refusal cannot be passing because
    the fixture never established the state it refuses to touch.
    """
    manifest = _manifest_of(registry_copy)
    manifest.write_text(
        manifest.read_text(encoding=UTF_8_ENCODING).rstrip("\n") + "\n" + _OPERATOR_SIGNOFF,
        encoding=UTF_8_ENCODING,
    )
    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == "Gergely Wootsch (operator)"
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
    arguments: dict[str, object],
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
            **arguments,  # type: ignore[arg-type]
        )

    assert manifest.read_bytes() == before, label
    revision = load_modelo_directory(operator_signed_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED
    assert revision.reviewed_by == "Gergely Wootsch (operator)"
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
    assert revision.reviewed_by == "Gergely Wootsch (operator)"
    assert revision.reviewed_at == date(2026, 7, 1)


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
        registry_root=registry_copy,
    )

    revision = load_modelo_directory(registry_copy / "modelos" / _STAMPED_MODELO).revisions[_STAMPED_REVISION]
    assert revision.review_status is RevisionReviewStatus.AGENT_REVIEWED
    assert revision.reviewed_by == "agent:second"


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
    before = {path: path.read_bytes() for path in sorted(revision_dir.rglob("*")) if path.is_file()}

    stamp_revision(
        _STAMPED_MODELO,
        _STAMPED_REVISION,
        engineered_by="conformance-cli gate",
        registry_root=registry_copy,
    )

    after = {path: path.read_bytes() for path in sorted(revision_dir.rglob("*")) if path.is_file()}
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
    two-phase design exists for — and the restore is what keeps it off disk.

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
    arguments: dict[str, object] = {field: "   "}
    if field == "reviewed_by":
        arguments["review_status"] = StampableReviewStatus.AGENT_REVIEWED
        arguments["reviewed_at"] = date(2026, 7, 27)

    with pytest.raises(StampError, match="names nobody"):
        stamp_revision(_STAMPED_MODELO, _STAMPED_REVISION, registry_root=registry_copy, **arguments)  # type: ignore[arg-type]

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

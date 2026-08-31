"""The transport boundary that folds justificante evidence advisories into the envelope.

The application layer already raises one typed WARNING per stored artefact that
yielded no evidence, each naming its own reason. That only reaches an operator if
the CLI forwards it, and the forwarding is a single ``extend`` at the boundary
where three advisory sources converge on one channel.

These assertions drive that builder directly. Reading ``evidence_notices`` back
off a run the test just constructed proves only that pydantic stores a tuple: it
cannot fail if the forwarding is deleted, because the field is populated by the
test rather than by the code under test. The distinction matters here more than
usual, because the reasons exist precisely to undo a uniform silence -- a capture
that extracted casillas while enrolling nothing used to report an unexplained
zero, indistinguishable from a period with no receipt to enrol.
"""

from __future__ import annotations

import io
import json
from typing import NotRequired, TypedDict

import pytest

from ....application.live.filed_data_capture import (
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
)
from ....application.live.filed_observation_persistence import (
    FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
    FiledJustificanteUnreachedReason,
)
from ....application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.json_contract import Notice, NoticeSeverity, emit_json_success
from ....core.period import Period
from .._app_live import _filed_capture_notices, _filed_pull_all_notices, _filed_pull_all_result_and_lines
from .._app_live_filed_payloads import FiledCaptureResult, FiledCaptureSourcesResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _CaptureReportFields(TypedDict):
    """Common typed tally fields shared by the filed-capture report models."""

    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]
    evidence_notices: tuple[Notice, ...]
    reached_count: NotRequired[int]


def _answered_pair() -> FiledHistoryPairOutcome:
    """A pair that answered with filings, so it raises no advisory of its own."""
    return FiledHistoryPairOutcome(
        modelo="303",
        ejercicio=2025,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
        row_count=1,
    )


def _unreached_notice(reason: FiledJustificanteUnreachedReason) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
        message=f"artefact produced no evidence ({reason.value})",
        context={"reason": reason.value, "modelo": "130", "expediente_id": "202613000000199Z"},
    )


def _run(
    *notices: Notice,
    pairs: tuple[FiledHistoryPairOutcome, ...] | None = None,
) -> FiledHistoryOnboardingRun:
    """A run whose only advisories are the ones passed in.

    ``carries_a_taxpayer_specific_denominator`` is set so the builder's own
    denominator warning stays out of the way; the default pair answers, so no
    expected-but-not-found notice fires either.
    """
    return FiledHistoryOnboardingRun(
        pairs=pairs if pairs is not None else (_answered_pair(),),
        carries_a_taxpayer_specific_denominator=True,
        evidence_notices=notices,
    )


def test_the_transport_forwards_every_unreached_reason_as_its_own_notice() -> None:
    """Every member of the reason taxonomy survives the fold onto the envelope.

    Driving the FULL enum rather than a hand-listed sample is what makes a newly
    added reason fail here instead of going unrelayed: the expected set is derived
    from the enum, so it cannot drift behind it.
    """
    reasons = tuple(FiledJustificanteUnreachedReason)
    assert reasons, "the reason taxonomy is empty, so this test would pass vacuously"

    notices = _filed_pull_all_notices(_run(*(_unreached_notice(reason) for reason in reasons)))

    relayed = [notice for notice in notices if notice.code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE]
    assert {notice.context["reason"] for notice in relayed if notice.context} == {reason.value for reason in reasons}
    # One per reason. A builder that merged two dead ends into a single
    # "evidence not enrolled" notice would rebuild the uniform silence one layer
    # up, while still emitting something and still looking like a relay.
    assert len(relayed) == len(reasons)


def test_the_transport_preserves_each_forwarded_notice_verbatim() -> None:
    """The advisory arrives unrewritten, context included.

    Severity, code, message and context all have to survive: an operator triaging
    an unusable receipt needs the reason and the expediente, and a boundary that
    rebuilt the notice from its code alone would drop exactly those.
    """
    original = _unreached_notice(FiledJustificanteUnreachedReason.CSV_MISMATCH)

    notices = _filed_pull_all_notices(_run(original))

    assert original in notices


def test_the_transport_keeps_run_advisories_and_evidence_advisories_distinct() -> None:
    """Two authorities, one channel, still two readable facts.

    A refused pair and an unusable receipt are different events: the first says
    the read did not happen, the second says it happened and produced nothing
    enrollable. Sharing the notices channel must not merge their identities.
    """
    refused = FiledHistoryPairOutcome(
        modelo="303",
        ejercicio=2024,
        signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
        row_count=0,
        refused=True,
    )
    run = _run(
        _unreached_notice(FiledJustificanteUnreachedReason.UNPARSABLE_PDF),
        pairs=(_answered_pair(), refused),
    )

    codes = [notice.code for notice in _filed_pull_all_notices(run)]

    assert FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE in codes
    assert "live.filed.pull_all.pairs_refused" in codes
    refused_notice = next(
        notice for notice in _filed_pull_all_notices(run) if notice.code == "live.filed.pull_all.pairs_refused"
    )
    assert refused_notice.action is not None
    assert refused_notice.action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.live.filed.pull_all",
            "target_command_key": "app.live.filed.pull_all",
            "cli_path": ["app", "live", "filed", "pull-all"],
        },
        "argument_bindings": [],
    }


def test_a_run_that_reached_all_its_evidence_forwards_no_unreached_notice() -> None:
    """The channel stays clean on the success path.

    Without this, a builder appending the advisory unconditionally would satisfy
    every assertion above while telling an operator that a wholly successful pull
    reached no evidence.
    """
    codes = [notice.code for notice in _filed_pull_all_notices(_run())]

    assert FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE not in codes


def _submitted_file_notice() -> Notice:
    """One already-typed application advisory, as a CLI relay receives it."""
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="live.filed.pull.submitted_file_extraction_failed",
        message=(
            "Modelo 303 filing 1T 2025 (expediente 2025303000000001) could not be read through its "
            "submitted-file layout. Parser reason: modelo-303-layout record ended early"
        ),
        context={
            "modelo": "303",
            "filing_year": "2025",
            "period": "1T",
            "expediente_id": "2025303000000001",
            "reason": "modelo-303-layout record ended early",
        },
    )


def _capture_report_fields(
    notice: Notice,
    *,
    captured_count: int = 1,
    observation_paths: tuple[str, ...] = ("303/2025/1T/manifest.json",),
    reached_count: int | None = None,
) -> _CaptureReportFields:
    fields: _CaptureReportFields = {
        "captured_count": captured_count,
        "observation_paths": observation_paths,
        "artefact_refs": ("sha256:submitted-file",),
        "casilla_count": 0,
        "calculation_observation_count": 0,
        "calculation_observation_keys": (),
        "evidence_notices": (notice,),
    }
    if reached_count is not None:
        fields["reached_count"] = reached_count
    return fields


def _emitted_notice_codes(*, command: str, result: object, notices: tuple[Notice, ...]) -> set[str]:
    stream = io.StringIO()
    emit_json_success(command, result, notices=notices, active_profile=None, stream=stream)
    envelope = json.loads(stream.getvalue())
    return {item["code"] for item in envelope["notices"]}


def test_the_submitted_file_advisory_reaches_every_filed_pull_envelope() -> None:
    """Direct and all-history pull modes forward the public report/run notice lane."""
    notice = _submitted_file_notice()
    single_report = FiledDataCaptureReport(
        output_root="var/filed",
        modelo="303",
        year=2025,
        **_capture_report_fields(notice),
    )
    source_report = SourceFiledDataCaptureReport(
        output_root="var/filed",
        target_modelo="303",
        target_year=2025,
        target_period=Period.from_year_and_code(2025, "1T"),
        **_capture_report_fields(notice),
    )
    bulk_report = BulkFiledDataCaptureReport(
        output_root="var/filed",
        modelos=("303",),
        year_from=2025,
        year_to=2025,
        failed_count=0,
        **_capture_report_fields(notice),
    )

    assert _filed_capture_notices(single_report) == (notice,)
    assert _filed_capture_notices(source_report) == (notice,)
    assert _filed_capture_notices(bulk_report) == (notice,)

    single_payload = FiledCaptureResult(
        output_root=single_report.output_root,
        modelo=single_report.modelo,
        year=single_report.year,
        captured_count=single_report.captured_count,
        observation_paths=list(single_report.observation_paths),
        artefact_refs=list(single_report.artefact_refs),
        casilla_count=single_report.casilla_count,
        calculation_observation_count=single_report.calculation_observation_count,
        calculation_observation_keys=list(single_report.calculation_observation_keys),
    )
    source_payload = FiledCaptureSourcesResult(
        output_root=source_report.output_root,
        target_modelo=source_report.target_modelo,
        target_year=source_report.target_year,
        target_period=source_report.target_period,
        captured_count=source_report.captured_count,
        observation_paths=list(source_report.observation_paths),
        artefact_refs=list(source_report.artefact_refs),
        casilla_count=source_report.casilla_count,
        calculation_observation_count=source_report.calculation_observation_count,
        calculation_observation_keys=list(source_report.calculation_observation_keys),
    )
    run = _run(notice)
    all_payload, _lines = _filed_pull_all_result_and_lines(run)

    assert notice.code in _emitted_notice_codes(
        command="app.live.filed.pull",
        result=single_payload,
        notices=_filed_capture_notices(single_report),
    )
    assert notice.code in _emitted_notice_codes(
        command="app.live.filed.pull_sources",
        result=source_payload,
        notices=_filed_capture_notices(source_report),
    )
    assert notice.code in _emitted_notice_codes(
        command="app.live.filed.pull_all",
        result=all_payload,
        notices=tuple(_filed_pull_all_notices(run)),
    )
    assert "evidence_notices" not in FiledCaptureResult.model_fields
    assert "evidence_notices" not in FiledCaptureSourcesResult.model_fields
    assert "submitted_file_extraction_error" not in FiledCaptureResult.model_fields
    assert "submitted_file_extraction_error" not in FiledCaptureSourcesResult.model_fields


# ------------------------------------------------ the sweep that stopped early

_TRUNCATION_CODE = "live.filed.limit_reached"


def _sweep(*, reached: int, captured: int) -> FiledHistoryOnboardingRun:
    """A run that reached ``reached`` declaraciones and wrote ``captured`` of them.

    The two are separately settable because they diverge on the path this notice
    exists for: a preview reaches declaraciones and writes none.
    """
    return FiledHistoryOnboardingRun(
        pairs=(_answered_pair(),),
        carries_a_taxpayer_specific_denominator=True,
        reached_count=reached,
        captured_count=captured,
    )


def test_a_sweep_that_hit_its_limit_warns_that_the_rest_was_not_walked() -> None:
    """Truncation is stated, not left for the operator to infer from a count.

    Without it the run reports its pairs and stops, and a pair the sweep never
    reached is indistinguishable from one AEAT holds nothing for -- which is the
    reading that turns an interrupted sweep into "nothing was filed".
    """
    notices = _filed_pull_all_notices(_sweep(reached=5, captured=5), limit=5)

    truncation = [notice for notice in notices if notice.code == _TRUNCATION_CODE]
    assert len(truncation) == 1
    assert truncation[0].severity is NoticeSeverity.WARNING
    assert truncation[0].context == {"limit": "5", "reached_count": "5"}
    assert truncation[0].action is not None
    assert truncation[0].action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.live.filed.pull_all",
            "target_command_key": "app.live.filed.pull_all",
            "cli_path": ["app", "live", "filed", "pull-all"],
        },
        "argument_bindings": [],
    }


def test_the_truncation_warning_leads_the_channel() -> None:
    """It precedes the advisories it qualifies.

    An expected-but-not-found warning about a pair the sweep never walked is an
    artefact of the truncation, so the truncation has to be readable first.
    """
    run = FiledHistoryOnboardingRun(
        pairs=(_answered_pair(),),
        carries_a_taxpayer_specific_denominator=False,
        reached_count=2,
    )

    codes = [notice.code for notice in _filed_pull_all_notices(run, limit=2)]

    assert codes.index(_TRUNCATION_CODE) == 0
    # A positive control: the notice it precedes really is on this channel, so
    # the ordering assertion is over two present codes rather than one.
    assert "live.filed.pull_all.no_taxpayer_specific_denominator" in codes


def test_a_sweep_that_finished_inside_its_limit_stays_silent() -> None:
    """The success path keeps the channel clean."""
    notices = _filed_pull_all_notices(_sweep(reached=3, captured=3), limit=10)

    assert _TRUNCATION_CODE not in [notice.code for notice in notices]


def test_an_unlimited_sweep_cannot_be_truncated_and_says_nothing() -> None:
    """No ``--limit`` means no early stop to report, whatever the tally reached."""
    notices = _filed_pull_all_notices(_sweep(reached=9999, captured=9999), limit=None)

    assert _TRUNCATION_CODE not in [notice.code for notice in notices]


def test_the_preview_that_captured_nothing_still_reports_its_truncation() -> None:
    """The predicate reads the reached tally, never the written one.

    ``captured_count`` is ``len(observation_paths)``, and a preview appends no
    paths -- so a ``captured_count >= limit`` predicate reads FALSE exactly when a
    dry run was truncated, staying silent on the one path where the operator has
    no other way to notice. This drives the preview shape directly.
    """
    run = _sweep(reached=4, captured=0)
    # Guard the shape before asserting on it: if the model ever stopped allowing
    # a reached-but-uncaptured run, the assertion below would pass while proving
    # nothing about previews.
    assert run.captured_count == 0 < run.reached_count, "this is no longer the preview shape"

    codes = [notice.code for notice in _filed_pull_all_notices(run, limit=4)]

    assert _TRUNCATION_CODE in codes
    # The discarded predicate, evaluated so its silence is on record rather than
    # only described in prose.
    truncated_by_the_written_tally = run.captured_count >= 4
    assert not truncated_by_the_written_tally


def test_every_limit_bearing_filed_read_reports_its_own_truncation() -> None:
    """The sweep is not the only surface that can stop early.

    ``filed pull`` takes the same ``--limit``, and in bulk mode it is the surface
    that also takes ``--dry-run`` -- the combination where the written tally is
    zero however much was reached. One builder answers for both, so a fix here
    cannot hold on one door while the other stays silent.
    """
    bulk = BulkFiledDataCaptureReport(
        output_root="var/filed",
        modelos=("303",),
        year_from=2025,
        year_to=2025,
        failed_count=0,
        **_capture_report_fields(
            _submitted_file_notice(),
            captured_count=0,
            observation_paths=(),
            reached_count=6,
        ),
    )
    # The preview shape, guarded before it is asserted on.
    assert bulk.captured_count == 0 < bulk.reached_count

    codes = [notice.code for notice in _filed_capture_notices(bulk, limit=6)]

    assert codes[0] == _TRUNCATION_CODE
    # The capture's own advisory still rides behind it, unmerged.
    assert len(codes) == 2


def test_a_capture_given_no_limit_keeps_its_notices_untouched() -> None:
    """Without a ``--limit`` the builder is the identity it was before.

    ``pull-sources`` has no limit option at all, so its call site takes the
    default -- this pins that the default cannot invent a truncation.
    """
    notice = _submitted_file_notice()
    report = BulkFiledDataCaptureReport(
        output_root="var/filed",
        modelos=("303",),
        year_from=2025,
        year_to=2025,
        failed_count=0,
        **_capture_report_fields(notice, reached_count=9999),
    )

    assert _filed_capture_notices(report) == (notice,)

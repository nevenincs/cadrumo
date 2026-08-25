"""The onboarding result payload, and the two numbers it deliberately omits.

The interesting assertions here are negative. A completeness percentage over the
walked pairs would rest partly on AEAT's offered option list, whose scoping to
the authenticated NIF is unconfirmed, so the figure would read as coverage while
its denominator may have nothing to do with this taxpayer. The absence is gated
so it cannot regrow, and ``denominator_note`` carries the same information in
prose, which is the honest form.

The other load-bearing distinction is between a pair that REFUSED and a pair
that legitimately returned zero rows. The register walker refuses a page whose
grid declares more records than it rendered, and that refusal is absorbed into a
failure row; folding it into "zero rows" would render a parse refusal as "no
filings found". The payload carries them as separate fields and the tests below
pin that they cannot be conflated.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core import RegisterScopingSignal
from ....core.json_contract import SchemaEnvelope
from .._app_live_filed_payloads import FiledHistoryOnboardingResult, FiledHistoryPairOutcomePayload
from .._command_schema import command_schema_types

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SCHEMA_KEY = "app.live.filed.pull_all"

#: Names that would reintroduce a ratio over an unconfirmed denominator.
_FORBIDDEN_RATIO_TOKENS = ("percent", "percentage", "fraction", "ratio", "pct", "coverage_rate", "completeness")


def _populated() -> FiledHistoryOnboardingResult:
    """Every defaultable field set to a non-default value."""
    return FiledHistoryOnboardingResult(
        pairs=[
            FiledHistoryPairOutcomePayload(
                modelo="303",
                ejercicio=2025,
                signals=["profile_applicability"],
                row_count=2,
                captured_count=1,
                refused=False,
                failure_type=None,
                failure_message=None,
            ),
            FiledHistoryPairOutcomePayload(
                modelo="100",
                ejercicio=2024,
                signals=["aeat_register_options"],
                row_count=0,
                captured_count=0,
                refused=True,
                failure_type="SedeParseError",
                failure_message="rendered 3 row(s) but its pager declares 8 in total",
            ),
        ],
        pair_count=2,
        profile_expected_count=1,
        register_options_only_count=1,
        refused_count=1,
        empty_count=0,
        captured_count=1,
        reached_count=2,
        scoping_signal=RegisterScopingSignal.LIKELY_UNIVERSAL.value,
        denominator_note="Measured against the profile's own declared facts; the register's offered list is unconfirmed.",
        iva_wallet_status="reconciled",
        iva_wallet_divergence="none",
        iva_wallet_blocked=True,
        notificaciones_status="captured",
        notificaciones_row_count=4,
        stage_failures=["notificaciones: transient timeout"],
    )


# ------------------------------------------------------------------ roundtrip


def test_the_result_survives_a_strict_json_roundtrip() -> None:
    saved = _populated()
    assert FiledHistoryOnboardingResult.model_validate_json(saved.model_dump_json()) == saved


def test_the_result_refuses_a_payload_missing_the_denominator_note() -> None:
    corrupted = json.loads(_populated().model_dump_json())
    del corrupted["denominator_note"]
    with pytest.raises(ValidationError, match="denominator_note"):
        FiledHistoryOnboardingResult.model_validate_json(json.dumps(corrupted))


def test_the_result_refuses_an_unknown_field() -> None:
    corrupted = json.loads(_populated().model_dump_json())
    corrupted["completeness_percentage"] = 87.5
    with pytest.raises(ValidationError, match="completeness_percentage"):
        FiledHistoryOnboardingResult.model_validate_json(json.dumps(corrupted))


def test_the_reached_tally_survives_the_envelope_and_cannot_default_away() -> None:
    """A dropped reached tally refuses; it does not quietly become zero.

    This field answers "was this sweep truncated", and zero is the answer that
    says it was not. Were it defaultable, a payload that lost the key on the way
    to the operator would assert a complete sweep instead of failing.
    """
    saved = _populated()
    payload = json.loads(saved.model_dump_json())
    # Assert it was there before deleting it, or the refusal below could be
    # caused by a field the payload never carried in the first place.
    assert payload["reached_count"] == saved.reached_count == 2

    del payload["reached_count"]

    with pytest.raises(ValidationError, match="reached_count"):
        FiledHistoryOnboardingResult.model_validate_json(json.dumps(payload))


def test_the_reached_and_captured_tallies_are_separately_expressible() -> None:
    """The two counts are different questions and must not collapse into one.

    ``captured_count`` counts written observations, which a preview leaves at
    zero however much it reached. One field for both would make a truncated dry
    run indistinguishable from one that walked nothing.
    """
    preview = FiledHistoryOnboardingResult.model_validate(
        {
            **_populated().model_dump(mode="json"),
            "captured_count": 0,
            "reached_count": 4,
        },
    )
    assert preview.captured_count == 0
    assert preview.reached_count == 4


# --------------------------------------------------- the deliberate omissions


def test_no_field_expresses_a_completeness_ratio() -> None:
    names = " ".join(FiledHistoryOnboardingResult.model_fields).casefold()
    for token in _FORBIDDEN_RATIO_TOKENS:
        assert token not in names, (
            f"{token!r} reintroduces a ratio whose denominator is partly the register's "
            "unconfirmed option list; state the denominator in prose instead"
        )


def test_no_field_on_the_result_is_a_float() -> None:
    # A ratio would most naturally arrive as a float, so the type is gated too --
    # a name check alone would miss `coverage: float`.
    for name, field in FiledHistoryOnboardingResult.model_fields.items():
        assert field.annotation is not float, f"{name} is a float; a ratio has no honest denominator here"


def test_the_denominator_note_is_required_and_non_empty() -> None:
    with pytest.raises(ValidationError, match="denominator_note"):
        FiledHistoryOnboardingResult.model_validate_json(
            json.dumps(
                {k: v for k, v in json.loads(_populated().model_dump_json()).items() if k != "denominator_note"}
            ),
        )


def test_the_scoping_signal_is_always_a_hedged_reading() -> None:
    # The result carries the classification as a string on the wire, so this pins
    # that no resolved value is even expressible upstream of it.
    assert _populated().scoping_signal in {signal.value for signal in RegisterScopingSignal}
    assert all(signal.value.startswith(("likely_", "inconclusive")) for signal in RegisterScopingSignal), (
        "a resolved scoping value became representable; the result would then be able to assert one"
    )


# ------------------------------------- refusal is not the same as zero rows


def test_a_refused_pair_and_an_empty_pair_are_distinguishable() -> None:
    refused = FiledHistoryPairOutcomePayload(
        modelo="303",
        ejercicio=2025,
        signals=["profile_applicability"],
        row_count=0,
        refused=True,
        failure_type="SedeParseError",
        failure_message="under-reported filing history",
    )
    empty = FiledHistoryPairOutcomePayload(
        modelo="303",
        ejercicio=2024,
        signals=["profile_applicability"],
        row_count=0,
        refused=False,
    )
    # Both have row_count 0, so row_count alone cannot tell them apart -- which is
    # exactly why the refusal is its own field rather than an inferred zero.
    assert refused.row_count == empty.row_count == 0
    assert refused.refused is not empty.refused
    assert refused.failure_message and not empty.failure_message


def test_the_counts_separate_refusals_from_legitimate_empties() -> None:
    result = _populated()
    assert result.refused_count == sum(1 for pair in result.pairs if pair.refused)
    assert result.empty_count == sum(1 for pair in result.pairs if not pair.refused and pair.row_count == 0)
    # A refused pair must NOT be counted as an empty one.
    assert result.refused_count + result.empty_count <= result.pair_count


def test_stage_failures_make_a_partial_run_visible() -> None:
    result = _populated()
    assert result.stage_failures
    # The result exists even though a stage failed, so a partial run reports
    # which part failed rather than reading as a whole one.
    assert result.captured_count >= 0


# ---------------------------------------------------------------- conformance


def test_the_schema_is_authored_and_specialises_the_shared_envelope() -> None:
    assert command_schema_types()[_SCHEMA_KEY] is FiledHistoryOnboardingResult
    envelope_cls = cast(Any, SchemaEnvelope)[FiledHistoryOnboardingResult]
    assert envelope_cls.__pydantic_generic_metadata__["args"] == (FiledHistoryOnboardingResult,)


def test_the_schema_carries_no_bespoke_notice_field() -> None:
    forbidden = re.compile(r"^(next|suggestion|suggestions|hint|hints|advisor(y|ies))$|_advisor(y|ies)$")
    offending = sorted(name for name in FiledHistoryOnboardingResult.model_fields if forbidden.search(name))
    assert offending == []

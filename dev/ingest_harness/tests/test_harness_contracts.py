"""The harness must refuse every shape a figure has been misquoted in.

These run against a small synthetic key payload rather than the external corpus,
so they exercise the refusals anywhere, including where the corpus is absent.
That is not a stand-in for the thing under test: the code under test is the
refusal logic, and a hand-built payload is simply a different input document.
The corpus-anchored facts live beside this file and carry the integration marker.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from .._caveats import SPANISH_OPTIMISM_BIAS_CAVEAT
from .._key import CorpusKey, CorpusKeyError
from .._reference_points import ReferencePoint
from .._result import (
    EmittedOnly,
    EngineRoute,
    HarnessRefusalError,
    ModelTier,
    PipelineStage,
    ResultRow,
    Scored,
    amounts_match,
    build_result_row,
)
from .._runner import HarnessReport, format_report, require_model_tier, verify_decimal_comparison_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHA = "a" * 64


def _entry(
    doc_id: str,
    *,
    ground_truth: dict[str, Any] | None = None,
    language: str = "es",
    file_format: str = "image_photo",
    provenance: dict[str, Any] | None = None,
    path: str = "purchase_invoice/x.pdf",
    notes: str = "",
    category_scorable: Any = None,
) -> dict[str, Any]:
    hints: dict[str, Any] = {"tolerance_cents": 1, "unreadable_fields": [], "expected_refusal": False}
    if category_scorable is not None:
        hints["category_scorable"] = category_scorable
    return {
        "doc_id": doc_id,
        "path": path,
        "provenance": provenance if provenance is not None else {"generator": "spec.py"},
        "axes": {
            "language": language,
            "file_format": file_format,
            "territory": "domestic_es",
            "structural_difficulty": [],
        },
        "ground_truth": ground_truth if ground_truth is not None else {"base_total": "100,00", "series": None},
        "scoring_hints": hints,
        "notes": notes,
    }


def _key(entries: list[dict[str, Any]]) -> CorpusKey:
    return CorpusKey.from_payload({"schema_version": "1.0", "documents": entries}, sha256=_SHA, byte_length=1)


# ----------------------------------------------------------------------------
# a row without its tier is refused, not warned about
# ----------------------------------------------------------------------------


def test_a_result_row_cannot_be_built_without_a_model_tier() -> None:
    """The typed row makes the tier mandatory for anything built in process."""
    key = _key([_entry("DOC-1")])
    document = key.document("DOC-1")

    assert build_result_row(
        document=document,
        key_sha256=_SHA,
        stage=PipelineStage.S1_TRANSCRIPTION,
        engine_route=EngineRoute.GATED_CLOUD,
        model_identity="m",
        model_revision="r",
        model_tier=ModelTier.CLOUD_DESIGN_PROXY,
        outcome=Scored(scorable_field_count=1, matched=1, wrong=0, fabricated=0),
    ), "positive control: a complete row must build, or the refusals below prove nothing"

    with pytest.raises(ValidationError):
        ResultRow.model_validate_json(
            '{"doc_id": "DOC-1", "key_sha256": "' + _SHA + '", "stage": "s1_transcription",'
            ' "engine_route": "gated_cloud", "model_identity": "m", "model_revision": "r",'
            ' "outcome": {"emitted_field_count": 1}}',
        )


@pytest.mark.parametrize(
    "payload", [{"doc_id": "DOC-1"}, {"doc_id": "DOC-1", "model_tier": None}, {"doc_id": "DOC-1", "model_tier": "   "}]
)
def test_a_row_arriving_as_data_without_a_tier_is_refused(payload: dict[str, Any]) -> None:
    """The same gate at the boundary a missing tier would actually come from.

    A persisted result file or another tool's output is where the omission
    happens; the in-process type cannot police that direction.
    """
    with pytest.raises(HarnessRefusalError, match=r"(?i)model_tier|tier"):
        require_model_tier(payload)


def test_an_unknown_tier_is_refused_and_names_the_accepted_set() -> None:
    """A refusal that does not list the accepted values just restates the problem."""
    with pytest.raises(HarnessRefusalError, match=r"on_host_small") as caught:
        require_model_tier({"doc_id": "DOC-1", "model_tier": "gpt-9-ultra"})

    assert "cloud_design_proxy" in str(caught.value)
    assert "upper_reference" in str(caught.value)


def test_only_the_upper_reference_tier_is_barred_from_setting_a_floor() -> None:
    """The tier is not decoration: it decides baseline eligibility."""
    assert ModelTier.ON_HOST_SMALL.is_baseline_eligible
    assert ModelTier.CLOUD_DESIGN_PROXY.is_baseline_eligible
    assert not ModelTier.UPPER_REFERENCE.is_baseline_eligible


# ----------------------------------------------------------------------------
# An accuracy over documents with no authored truth must be unrepresentable
# ----------------------------------------------------------------------------


def test_a_scored_outcome_is_refused_over_a_document_with_no_authored_truth() -> None:
    """The '0-1 of 8 recovered' shape: an accuracy with no denominator in existence."""
    key = _key([_entry("NO-TRUTH", ground_truth={})])

    with pytest.raises(HarnessRefusalError, match=r"(?i)no authored truth|denominator"):
        build_result_row(
            document=key.document("NO-TRUTH"),
            key_sha256=_SHA,
            stage=PipelineStage.S2_EXTRACTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.CLOUD_DESIGN_PROXY,
            outcome=Scored(scorable_field_count=8, matched=1, wrong=0, fabricated=0),
        )


def test_an_emitted_only_outcome_carries_no_rate_to_quote() -> None:
    """The type has no accuracy, so a reader cannot extract one from it."""
    outcome = EmittedOnly(emitted_field_count=1)

    assert not hasattr(outcome, "accuracy")
    assert "UNDEFINED rather than zero" in outcome.why_unscored


def test_an_emitted_only_outcome_is_refused_where_truth_exists() -> None:
    """The opposite direction: a bare emitted count would discard a real denominator."""
    key = _key([_entry("HAS-TRUTH")])

    with pytest.raises(HarnessRefusalError, match=r"(?i)authored|scorable"):
        build_result_row(
            document=key.document("HAS-TRUTH"),
            key_sha256=_SHA,
            stage=PipelineStage.S2_EXTRACTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.CLOUD_DESIGN_PROXY,
            outcome=EmittedOnly(emitted_field_count=1),
        )


def test_a_denominator_that_is_not_the_keys_own_is_refused() -> None:
    """A figure over a set nobody can reconstruct from the key is not quotable."""
    key = _key([_entry("HAS-TRUTH")])

    with pytest.raises(HarnessRefusalError, match=r"(?i)denominator"):
        build_result_row(
            document=key.document("HAS-TRUTH"),
            key_sha256=_SHA,
            stage=PipelineStage.S2_EXTRACTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.CLOUD_DESIGN_PROXY,
            outcome=Scored(scorable_field_count=99, matched=1, wrong=0, fabricated=0),
        )


def test_a_null_truth_field_is_a_fabrication_trap_not_a_scorable_slot() -> None:
    """`null` truth means the document LACKS the field, so a value there is invented."""
    key = _key([_entry("DOC-1", ground_truth={"base_total": "100,00", "series": None, "recargo_amount": None})])
    document = key.document("DOC-1")

    assert document.scorable_fields == ("base_total",)
    assert set(document.fabrication_trap_fields) == {"series", "recargo_amount"}


# ----------------------------------------------------------------------------
# Caveats are stamped, not remembered
# ----------------------------------------------------------------------------


def test_every_spanish_row_carries_the_optimism_bias_caveat_without_being_asked() -> None:
    """The caller cannot forget it, because the caller never supplies it."""
    key = _key([_entry("ES-DOC", language="es"), _entry("EN-DOC", language="en")])

    def row(doc_id: str) -> ResultRow:
        return build_result_row(
            document=key.document(doc_id),
            key_sha256=_SHA,
            stage=PipelineStage.S1_TRANSCRIPTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.CLOUD_DESIGN_PROXY,
            outcome=Scored(scorable_field_count=1, matched=1, wrong=0, fabricated=0),
        )

    assert SPANISH_OPTIMISM_BIAS_CAVEAT in row("ES-DOC").caveats
    assert row("EN-DOC").caveats == (), "the caveat is about Spanish rendering, so it must not blanket everything"


def test_the_mixed_language_spanish_tag_still_carries_the_caveat() -> None:
    """`es-en` is rendered by the same synthetic renderer and carries the same bias."""
    key = _key([_entry("MIX", language="es-en")])

    assert key.document("MIX").is_spanish


# ----------------------------------------------------------------------------
# Key integrity, derivations and the twin link
# ----------------------------------------------------------------------------


def test_a_key_whose_provenance_contradicts_its_path_is_refused() -> None:
    """Two independent signals that disagree mean the corpus was reshuffled."""
    with pytest.raises(CorpusKeyError, match=r"(?i)provenance|path prefix"):
        _key([_entry("BAD", provenance={"generator": "spec.py"}, path="operator/corpus/x.xml")])


def test_the_generated_set_is_category_scorable_despite_carrying_no_flag() -> None:
    """The trap: reading the flag alone silently drops the whole generated set.

    The generated documents' category is intrinsic, so the key records no
    scorability flag for them at all. A filter written as `flag is True` would
    return one of these two documents instead of both.
    """
    key = _key(
        [
            _entry("GEN", provenance={"generator": "spec.py"}, path="purchase_invoice/a.pdf"),
            _entry("OP", provenance={"origin": "x"}, path="operator/b.xml", category_scorable=True),
            _entry("OP-CONV", provenance={"origin": "x"}, path="operator/c.xml", category_scorable=False),
        ],
    )

    assert key.category_scorable_ids == {"GEN", "OP"}


def test_a_twin_naming_an_unknown_original_is_refused() -> None:
    """A pair pointing at nothing would shrink the twin denominator silently."""
    with pytest.raises(CorpusKeyError, match=r"(?i)twin"):
        _key([_entry("TWIN", notes="VISION-PATH TWIN of DOES-NOT-EXIST")])


def test_twin_pairs_resolve_from_the_prose_note() -> None:
    """The link is a sentence, which is exactly why the harness declares it."""
    key = _key(
        [
            _entry("ORIG", notes="the original"),
            _entry("TWIN", notes="VISION-PATH TWIN of ORIG -- identical figures, delivered as pixels."),
        ],
    )

    assert len(key.twin_pairs) == 1
    assert key.twin_pairs[0].twin_doc_id == "TWIN"
    assert key.twin_pairs[0].original_doc_id == "ORIG"


def test_an_unknown_document_id_raises_rather_than_returning_none() -> None:
    """A silent None becomes a skipped row, and a skipped row shrinks a denominator."""
    key = _key([_entry("DOC-1")])

    with pytest.raises(CorpusKeyError, match=r"(?i)no corpus document"):
        key.document("NOPE")


# ----------------------------------------------------------------------------
# Reference points cannot become baselines
# ----------------------------------------------------------------------------


def test_a_reference_point_recorded_at_a_baseline_tier_is_refused() -> None:
    """Otherwise a frontier figure sets a floor no shipped configuration can meet."""
    with pytest.raises(ValidationError, match=r"(?i)baseline"):
        ReferencePoint(
            label="x",
            doc_id="DOC-1",
            stage=PipelineStage.S1_TRANSCRIPTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.CLOUD_DESIGN_PROXY,
            reported_matched=7,
            reported_denominator=8,
            fabricated=0,
            elapsed_seconds=4.4,
            caveats=("stated",),
        )


def test_a_reference_point_must_state_at_least_one_caveat() -> None:
    """An unqualified reference point is indistinguishable from a baseline."""
    with pytest.raises(ValidationError):
        ReferencePoint(
            label="x",
            doc_id="DOC-1",
            stage=PipelineStage.S1_TRANSCRIPTION,
            engine_route=EngineRoute.GATED_CLOUD,
            model_identity="m",
            model_revision="r",
            model_tier=ModelTier.UPPER_REFERENCE,
            reported_matched=7,
            reported_denominator=8,
            fabricated=0,
            elapsed_seconds=4.4,
            caveats=(),
        )


# ----------------------------------------------------------------------------
# Amounts, and the report's own provenance discipline
# ----------------------------------------------------------------------------


def test_amount_comparison_is_exact_decimal_within_the_keys_tolerance() -> None:
    """A cent tolerance must mean a cent."""
    assert amounts_match(Decimal("2420.00"), Decimal("2420.01"), tolerance_cents=1)
    assert not amounts_match(Decimal("2420.00"), Decimal("2420.02"), tolerance_cents=1)
    assert "exact decimal" in verify_decimal_comparison_path()


def test_a_report_refuses_rows_measured_against_a_different_key() -> None:
    """Figures from two keys must never share a report."""
    key = _key([_entry("DOC-1")])
    report = HarnessReport(key)
    foreign = build_result_row(
        document=key.document("DOC-1"),
        key_sha256="b" * 64,
        stage=PipelineStage.S1_TRANSCRIPTION,
        engine_route=EngineRoute.GATED_CLOUD,
        model_identity="m",
        model_revision="r",
        model_tier=ModelTier.CLOUD_DESIGN_PROXY,
        outcome=Scored(scorable_field_count=1, matched=1, wrong=0, fabricated=0),
    )

    with pytest.raises(HarnessRefusalError, match=r"(?i)key"):
        report.add(foreign)


def test_the_report_prints_the_key_hash_before_any_figure() -> None:
    """There must be no rendering path that emits a number first."""
    key = _key([_entry("DOC-1")])
    rendered = format_report(HarnessReport(key), key=key)

    assert rendered.index(_SHA) < rendered.index("ROWS:")
    assert "STALE, NEVER CITE THIS" in rendered, "the stale schema_version must be labelled where it is shown"

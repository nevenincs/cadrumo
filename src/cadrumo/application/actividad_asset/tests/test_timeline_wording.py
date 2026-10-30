"""The timeline words every changed value that is not plain text, driven by the models' own fields.

A value is plain when a reader can show it as it is: a name, a date, a reference, a number.
A token or a flag has a catalogue key, a share a percentage and a table class its official
name.  The sweep below walks the fields of the records the timeline reports, so a field
added to a model that no wording covers fails here and never reaches a reader as a raw value.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

import pytest
from pydantic import BaseModel

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    TIMELINE_LABELLED_FIELDS,
    TIMELINE_TOKEN_FAMILIES,
    activity_asset_label_key,
    timeline_token_key,
)
from cadrumo.application.actividad_asset.fact_wording import (
    ActivityAssetFlag,
    share_label,
    timeline_token_families,
    token_family,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AmortizationMethod,
    DigitOrder,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.fact_leaves import FactKind, fact_leaves, indexed_to_step_path
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.register_records import (
    ActivityAssetDescriptorFacts,
    ActivityAssetEventKind,
)

from ..register_timeline import _flatten
from .register_support import _published_class_labels
from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELS: tuple[type[BaseModel], ...] = (ActivityAssetRevision, ActivityAssetDescriptorFacts)
_WORDED = frozenset({FactKind.CHOICE, FactKind.FLAG})
_LABELLED = frozenset({FactKind.SHARE, FactKind.CLASS})


def test_every_field_a_record_can_emit_is_either_plain_or_worded() -> None:
    leaves = [leaf for model in _MODELS for leaf in fact_leaves(model)]

    for leaf in leaves:
        assert (leaf.dotted in TIMELINE_TOKEN_FAMILIES) is (leaf.kind in _WORDED), leaf.dotted
        assert (leaf.dotted in TIMELINE_LABELLED_FIELDS) is (leaf.kind in _LABELLED), leaf.dotted
    assert set(TIMELINE_TOKEN_FAMILIES) | set(TIMELINE_LABELLED_FIELDS) == {
        leaf.dotted for leaf in leaves if leaf.kind in _WORDED | _LABELLED
    }


def test_every_worded_field_names_the_family_of_its_own_enum_and_keys_each_member() -> None:
    for leaf in (leaf for model in _MODELS for leaf in fact_leaves(model) if leaf.kind in _WORDED):
        family, enum = TIMELINE_TOKEN_FAMILIES[leaf.dotted]
        assert enum is (leaf.tokens or ActivityAssetFlag), leaf.dotted
        assert family == token_family(enum)
        for member in enum:
            assert timeline_token_key(leaf.dotted, member.value) == activity_asset_label_key(family, member)


def test_a_repeated_row_is_found_by_its_step_path_whatever_its_position() -> None:
    assert indexed_to_step_path("further_acquisitions[3].shape") == "further_acquisitions[].shape"
    assert indexed_to_step_path("basis.stage") == "basis.stage"
    assert timeline_token_key("further_acquisitions[7].shape", "ancillary_cost") == (
        "ledger.actividad_asset.acquisition_shape.ancillary_cost"
    )


def test_a_dumped_row_is_flattened_by_position_and_a_flag_reads_as_a_token() -> None:
    flat = _flatten({"rows": [{"shape": "ancillary_cost"}, {"shape": "primary_purchase"}], "none": [], "flag": True})

    assert flat == {
        "rows[0].shape": "ancillary_cost",
        "rows[1].shape": "primary_purchase",
        "none": None,
        "flag": "true",
    }
    flag = flat["flag"]
    assert flag is not None
    assert timeline_token_key("basis.is_property", flag) == "ledger.actividad_asset.flag.true"


def test_a_model_with_an_enum_no_family_words_is_refused_instead_of_shown_raw() -> None:
    class Unworded(StrEnum):
        ONE = "one"

    class Record(BaseModel):
        kind: Unworded

    (leaf,) = fact_leaves(Record)

    assert leaf.kind is FactKind.CHOICE
    with pytest.raises(KeyError):
        token_family(Unworded)
    assert "kind" not in timeline_token_families()


def test_a_model_with_a_type_no_reader_words_is_refused() -> None:
    class Record(BaseModel):
        when: list[date]

    with pytest.raises(TypeError, match="when"):
        fact_leaves(Record)


def test_a_share_reads_as_a_percentage() -> None:
    assert [share_label(text) for text in ("0.5", "0.25", "1", "0.125", "0.0500")] == [
        "50%",
        "25%",
        "100%",
        "12.5%",
        "5%",
    ]


def test_the_timeline_words_a_changed_class_share_method_order_and_opening_method() -> None:
    labels = _published_class_labels(DirectEstimationRegime.SIMPLIFIED, 2025)
    before_class = "equipo-informacion-software"
    after_class = next(key for key in sorted(labels) if key != before_class)
    operations, _ = _operations()
    first_data = _revision().model_dump()
    first_data["basis"] = ActivityAssetBasis(
        stage=AssetBasisStage.TAXPAYER_OWNED,
        basis_amount=Decimal("2000"),
        non_deductible_iva=Decimal("0"),
        business_use_share=Decimal("0.5"),
    ).model_dump()
    first = ActivityAssetRevision.model_validate(first_data)
    operations.create(first, _NAME)
    second_data = first.model_dump()
    second_data.update(
        revision_number=2,
        supersedes_revision_id=first.revision_id,
        basis={**first.basis.model_dump(), "business_use_share": Decimal("0.25")},
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("100"),
            amortization_method=AmortizationMethod.LINEAR,
            covered_through_tax_year=2025,
        ).model_dump(),
        amortization={
            **first.amortization.model_dump(),
            "method": AmortizationMethod.SUM_OF_DIGITS,
            "authority_class_key": after_class,
            "sum_of_digits_period_years": 4,
            "digit_order": DigitOrder.ASCENDING,
        },
    )
    operations.correct(ActivityAssetRevision.model_validate(second_data))

    revisions = [event for event in operations.timeline("laptop-1") if event.kind is ActivityAssetEventKind.REVISION]

    changes = {change.field: change for change in revisions[-1].changes}
    method = changes["amortization.method"]
    assert (method.before_key, method.after_key) == (
        "ledger.actividad_asset.method.linear",
        "ledger.actividad_asset.method.sum_of_digits",
    )
    assert changes["amortization.digit_order"].after_key == "ledger.actividad_asset.digit_order.ascending"
    assert changes["opening_history.amortization_method"].after_key == "ledger.actividad_asset.method.linear"
    klass = changes["amortization.authority_class_key"]
    assert (klass.before_label, klass.after_label) == (labels[before_class], labels[after_class])
    assert klass.before_label != before_class
    share = changes["basis.business_use_share"]
    assert (share.before_label, share.after_label) == ("50%", "25%")
    assert changes["opening_history.covered_through_tax_year"].after_label is None
    assert changes["opening_history.covered_through_tax_year"].after_key is None

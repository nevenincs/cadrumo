"""Signed singleton policies preserve the official N type through the real codec."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field

from ...compiler.authority import compiled_bundled_authority
from .._export_tree import render_complete_export_tree
from ..render_check import RevisionRenderInputs, revision_render_inputs
from ..render_profile import validate_render_profile
from ..render_profile_rules import SingletonNumericRule

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def signed_singleton_inputs() -> RevisionRenderInputs:
    return revision_render_inputs(compiled_bundled_authority(), modelo="360", revision="2010-y-siguientes")


def test_official_signed_singletons_round_trip_positive_zero_and_negative_amounts(
    signed_singleton_inputs: RevisionRenderInputs,
    tmp_path,
) -> None:
    inputs = signed_singleton_inputs
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )
    fields = {str(field.id): field for record in rendered.layout.records for field in record.fields}
    signed_source_fields = [field for field in inputs.joined.fields if field.parser_field.aeat_type == "N"]
    assert signed_source_fields
    for source_field in signed_source_fields:
        field = fields[str(source_field.semantic_entry.export_field_id)]
        assert field.signed and field.data_type == "money"
        assert field.sign_position is None and field.value_policy is None
        for amount in (Decimal("12345.67"), Decimal("0.00"), Decimal("-12345.67")):
            wire = render_fixed_width_export_field(field, amount)
            assert len(wire) == source_field.parser_field.length
            assert wire.startswith("N") == (amount < 0)
            assert parse_fixed_width_export_field(field, wire) == amount


@pytest.mark.parametrize(
    "changes",
    [
        {"sign_policy": "unsigned"},
        {"decimal_digits": 3},
        {"semantic_kind": "integer"},
        {"aeat_type": "Num"},
    ],
)
def test_singleton_sign_and_scale_contradictions_are_refused(
    signed_singleton_inputs: RevisionRenderInputs,
    changes: dict[str, object],
) -> None:
    rule = next(rule for rule in signed_singleton_inputs.render_profile.singleton_rules if rule.aeat_type == "N")
    payload = {**rule.model_dump(mode="json"), **changes}
    with pytest.raises(ValidationError, match="representation"):
        SingletonNumericRule.model_validate_json(json.dumps(payload))


def test_a_valid_unsigned_rule_cannot_retype_an_official_signed_slot(
    signed_singleton_inputs: RevisionRenderInputs,
) -> None:
    inputs = signed_singleton_inputs
    profile = inputs.render_profile
    signed = next(rule for rule in profile.singleton_rules if rule.aeat_type == "N")
    payload = {**signed.model_dump(mode="json"), "aeat_type": "Num", "sign_policy": "unsigned"}
    wrong = SingletonNumericRule.model_validate_json(json.dumps(payload))
    changed = profile.model_copy(
        update={"singleton_rules": tuple(wrong if rule == signed else rule for rule in profile.singleton_rules)}
    )
    with pytest.raises(RegistryValidationError, match="singleton sign conflicts with official type"):
        validate_render_profile(changed, inputs.joined, inputs.render_profile_source_evidence)

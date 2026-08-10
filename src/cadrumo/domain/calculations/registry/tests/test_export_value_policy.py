"""Strict runtime contract for reviewed fixed-width export value policies."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExportValuePolicy,
    RegistryValidationError,
    parse_export_payload,
    project_export_value,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GROUNDING = {
    "legal_refs": ("ley-27-2014:art-40",),
    "source_refs": ("aeat-dr-200-2025",),
}


def _field(
    policy: ExportValuePolicy | None,
    *,
    field_id: str = "selected",
    casilla_id: str = "01",
    length: int | None = None,
    **overrides: object,
) -> ExportFieldDefinition:
    payload: dict[str, object] = {
        "id": field_id,
        "offset": 1,
        "length": length or (2 if policy is ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS else 1),
        "kind": "casilla",
        "casilla_id": casilla_id,
        "data_type": "integer",
        "required": False,
        "padding": "left_zero",
        "justification": "right",
        "signed": False,
        "value_policy": policy,
        **_GROUNDING,
    }
    payload.update(overrides)
    return ExportFieldDefinition.model_validate(payload)


def _layout(field: ExportFieldDefinition, *, record_id: str = "record") -> ExportLayoutDefinition:
    return ExportLayoutDefinition(
        id="policy-layout",
        source_refs=_GROUNDING["source_refs"],
        legal_refs=_GROUNDING["legal_refs"],
        records=(
            ExportRecordDefinition(
                id=record_id,
                record_type="1",
                order=0,
                encoding="ascii",
                line_ending="none",
                fields=(field,),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "0"),
        ("", "0"),
        (False, "0"),
        (0, "0"),
        (Decimal("0"), "0"),
        ("0", "0"),
        (True, "1"),
        (1, "1"),
        (Decimal("1.0"), "1"),
        ("1", "1"),
    ],
)
def test_checkbox_projector_accepts_only_exact_declared_states(value: object, expected: str) -> None:
    assert project_export_value(ExportValuePolicy.SELECTED_1_UNSELECTED_0, value) == expected


@pytest.mark.parametrize(
    "value",
    [" ", "01", "true", 2, -1, Decimal("0.1"), Decimal("sNaN"), float("nan"), float("inf"), object()],
)
def test_checkbox_projector_refuses_every_other_shape(value: object) -> None:
    with pytest.raises(RegistryValidationError):
        project_export_value(ExportValuePolicy.SELECTED_1_UNSELECTED_0, value)


@pytest.mark.parametrize(("value", "expected"), [(2026, "26"), ("2026", "26"), (1000, "00"), ("0001", "01")])
def test_short_year_projector_requires_four_digits(value: object, expected: str) -> None:
    assert project_export_value(ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS, value) == expected


@pytest.mark.parametrize("value", [26, "26", True, 2026.0, Decimal("2026"), "+2026", " 2026", "２０２６"])
def test_short_year_projector_refuses_noncanonical_inputs(value: object) -> None:
    with pytest.raises(RegistryValidationError):
        project_export_value(ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS, value)


def test_none_policy_is_inert_and_not_an_inferred_default() -> None:
    marker = object()
    assert project_export_value(None, marker) is marker


def test_schema_hydrates_only_the_two_public_policy_tokens() -> None:
    baseline = _field(ExportValuePolicy.SELECTED_1_UNSELECTED_0).model_dump(mode="python")
    hydrated = ExportFieldDefinition.model_validate(
        baseline | {"value_policy": ExportValuePolicy.SELECTED_1_UNSELECTED_0.value},
    )

    assert hydrated.value_policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate(baseline | {"value_policy": "checkbox-default"})


@pytest.mark.parametrize("policy", tuple(ExportValuePolicy))
@pytest.mark.parametrize(
    "overrides",
    [
        {"data_type": "text"},
        {"signed": True},
        {"padding": "right_space"},
        {"justification": "left"},
        {"decimals": 0},
        {"date_format": "YYYY"},
        {"kind": "filler", "casilla_id": None},
        {"kind": "literal", "casilla_id": None, "literal": "0"},
        {"kind": "checksum", "casilla_id": None},
    ],
)
def test_each_policy_refuses_inconsistent_field_shapes(
    policy: ExportValuePolicy,
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _field(policy, **overrides)


def test_checkbox_policy_requires_exactly_one_wire_byte() -> None:
    with pytest.raises(ValidationError):
        _field(ExportValuePolicy.SELECTED_1_UNSELECTED_0, length=2)


def test_short_year_policy_requires_exactly_two_wire_bytes() -> None:
    with pytest.raises(ValidationError):
        _field(ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS, length=4)


@pytest.mark.parametrize(
    ("policy", "valid", "invalid"),
    [
        (ExportValuePolicy.SELECTED_1_UNSELECTED_0, b"1", (b"X", b" ", b"2")),
        (ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS, b"26", (b"2X", b" 6", b"\xff6")),
    ],
)
def test_parser_accepts_exact_policy_wire_tokens_and_refuses_mutations(
    policy: ExportValuePolicy,
    valid: bytes,
    invalid: tuple[bytes, ...],
) -> None:
    layout = _layout(_field(policy))
    assert parse_export_payload(layout, valid).fields[0].raw == valid.decode("ascii")
    for mutation in invalid:
        with pytest.raises(RegistryValidationError):
            parse_export_payload(layout, mutation)


def test_runtime_policy_tokens_have_one_production_owner_and_consumers_import_the_projector() -> None:
    src_root = Path("src/cadrumo")
    owner = src_root / "domain/calculations/registry/_export_value_policy.py"
    tokens = tuple(policy.value for policy in ExportValuePolicy)
    redeclarations = {
        path.as_posix(): token
        for path in src_root.rglob("*.py")
        if path != owner
        for token in tokens
        if token in path.read_text(encoding="utf-8")
    }
    assert redeclarations == {}

    for consumer in (
        src_root / "application/filing/_export.py",
        src_root / "adapters/outbound/aeat/export/_registry_record_renderer.py",
    ):
        source = consumer.read_text(encoding="utf-8")
        assert "project_export_value" in source
        assert "._export_value_policy" not in source

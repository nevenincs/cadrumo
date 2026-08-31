"""Strict runtime contract for reviewed fixed-width export value policies."""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.directory_scan import scan_directory
from ..errors import RegistryValidationError
from ..export_parse import parse_export_payload
from ..export_value_policy import ExportValuePolicy, ParsedExportPolicyWireValue, project_export_value
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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
    payload_overrides: dict[str, object] | None = None,
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
    if payload_overrides is not None:
        payload.update(payload_overrides)
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


def test_schema_hydrates_only_public_policy_tokens() -> None:
    baseline = _field(ExportValuePolicy.SELECTED_1_UNSELECTED_0).model_dump(mode="python")
    hydrated = ExportFieldDefinition.model_validate(
        baseline | {"value_policy": ExportValuePolicy.SELECTED_1_UNSELECTED_0.value},
    )

    assert hydrated.value_policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate(baseline | {"value_policy": "checkbox-default"})


@pytest.mark.parametrize(
    ("policy", "value", "expected"),
    (
        (ExportValuePolicy.UNSIGNED_INTEGER, Decimal("12"), Decimal("12")),
        (ExportValuePolicy.IMPLIED_DECIMAL, "12.50", Decimal("12.50")),
        (ExportValuePolicy.ENUMERATED_DIGITS, "2", Decimal("2")),
        (ExportValuePolicy.DIGIT_STRING, "0123", "0123"),
        (ExportValuePolicy.IDENTIFIER_DIGITS, "0012345678901", "0012345678901"),
        (ExportValuePolicy.FOUR_DIGIT_YEAR, 2026, "2026"),
        (ExportValuePolicy.TWO_DIGIT_MONTH, 8, "08"),
        (ExportValuePolicy.TWO_DIGIT_DAY, "9", "09"),
        (ExportValuePolicy.YYYYMMDD, date(2024, 2, 29), "20240229"),
        (ExportValuePolicy.DDMMYYYY, date(2024, 2, 29), "29022024"),
    ),
)
def test_reviewed_singleton_policies_project_exact_semantic_values(
    policy: ExportValuePolicy,
    value: object,
    expected: object,
) -> None:
    assert project_export_value(policy, value) == expected


@pytest.mark.parametrize(
    ("policy", "value"),
    (
        (ExportValuePolicy.UNSIGNED_INTEGER, Decimal("1.5")),
        (ExportValuePolicy.UNSIGNED_INTEGER, -1),
        (ExportValuePolicy.UNSIGNED_INTEGER, Decimal("-0")),
        (ExportValuePolicy.IMPLIED_DECIMAL, float("nan")),
        (ExportValuePolicy.IMPLIED_DECIMAL, "1e2"),
        (ExportValuePolicy.IMPLIED_DECIMAL, Decimal("-0.00")),
        (ExportValuePolicy.ENUMERATED_DIGITS, True),
        (ExportValuePolicy.DIGIT_STRING, 123),
        (ExportValuePolicy.DIGIT_STRING, "１２３"),
        (ExportValuePolicy.IDENTIFIER_DIGITS, "12 3"),
        (ExportValuePolicy.FOUR_DIGIT_YEAR, "026"),
        (ExportValuePolicy.TWO_DIGIT_MONTH, 13),
        (ExportValuePolicy.TWO_DIGIT_DAY, "00"),
        (ExportValuePolicy.YYYYMMDD, "20230229"),
        (ExportValuePolicy.DDMMYYYY, "29022023"),
    ),
)
def test_reviewed_singleton_policies_refuse_noncanonical_semantic_values(
    policy: ExportValuePolicy,
    value: object,
) -> None:
    with pytest.raises(RegistryValidationError):
        project_export_value(policy, value)


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
        _field(policy, payload_overrides=overrides)


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
    parsed = parse_export_payload(layout, valid).fields[0]
    assert parsed.raw == valid.decode("ascii")
    if policy is ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS:
        assert parsed.value == ParsedExportPolicyWireValue(policy=policy, raw="26")
    for mutation in invalid:
        with pytest.raises(RegistryValidationError):
            parse_export_payload(layout, mutation)


def test_runtime_policy_tokens_have_one_production_owner_and_consumers_import_the_projector() -> None:
    src_root = Path("src/cadrumo")
    owner = src_root / "domain/calculations/registry/export_value_policy.py"
    tokens = frozenset(policy.value for policy in ExportValuePolicy)
    redeclarations = {
        path.as_posix(): declared
        for path in scan_directory(src_root, pattern="*.py", recursive=True, prune_directories=("tests",))
        if path != owner
        for declared in _export_policy_declarations(path.read_text(encoding="utf-8"), tokens=tokens)
    }
    assert redeclarations == {}

    codec = src_root / "domain/calculations/registry/fixed_width_codec.py"
    assert "project_export_value" in codec.read_text(encoding="utf-8")

    for consumer in (
        src_root / "application/filing/_export.py",
        src_root / "adapters/outbound/aeat/export/_registry_record_renderer.py",
    ):
        source = consumer.read_text(encoding="utf-8")
        assert "render_fixed_width_export_field" in source
        assert ".export_value_policy" not in source


def _export_policy_declarations(source: str, *, tokens: frozenset[str]) -> frozenset[str]:
    """Find policy declarations while excluding non-export parser format labels."""
    tree = ast.parse(source)
    declarations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(_is_enum_base(base) for base in node.bases):
            declarations.update(
                value
                for statement in node.body
                if isinstance(statement, ast.Assign)
                for value in (_string_constant(statement.value),)
                if value in tokens
            )
        if isinstance(node, ast.Call):
            declarations.update(
                value
                for keyword in node.keywords
                if keyword.arg == "value_policy"
                for value in (_string_constant(keyword.value),)
                if value in tokens
            )
        if isinstance(node, ast.Dict):
            declarations.update(
                value
                for key, item in zip(node.keys, node.values, strict=True)
                if _string_constant(key) == "value_policy"
                for value in (_string_constant(item),)
                if value in tokens
            )
        if isinstance(node, ast.Assign) and any(_is_policy_target(target) for target in node.targets):
            value = _string_constant(node.value)
            if value in tokens:
                declarations.add(value)
        if isinstance(node, ast.AnnAssign) and _is_policy_target(node.target):
            value = _string_constant(node.value)
            if value in tokens:
                declarations.add(value)
    return frozenset(declarations)


def _is_enum_base(node: ast.expr) -> bool:
    return (isinstance(node, ast.Name) and node.id in {"Enum", "StrEnum"}) or (
        isinstance(node, ast.Attribute) and node.attr in {"Enum", "StrEnum"}
    )


def _is_policy_target(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id.casefold().endswith("value_policy")


def _string_constant(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

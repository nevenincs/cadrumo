"""Real-IR and mutation proofs for the reviewed render-profile authority."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core import FilingProducerKey, scan_directory
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    CasillaFieldKind,
    ExportValuePolicy,
    RegistryValidationError,
    load_catalogue_file,
    resolve_record_design_binary,
)

from ..pipeline import _export_tree, _render_profile
from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignWorkbookFormat,
    load_record_design_intermediate,
)
from ..pipeline._render_profile import (
    OfficialSourceEvidence,
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileDesignIdentity,
    RenderProfileFragment,
    RenderProfileSourceEvidence,
    RenderProfileSourceEvidenceEntry,
    ReviewedPolicyDecision,
    SingletonNumericRule,
    Width17MembershipRule,
    _is_source_reserved_field,
    load_and_validate_render_profile,
    load_render_profile,
    load_render_profile_source_evidence,
    project_render_profile_eligibility,
    render_profile_digest,
    validate_render_profile,
    validate_render_profile_authority,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import (
    JoinedRecordDesign,
    JoinedRecordDesignField,
    JoinedRecordDesignRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _anchor(row: int) -> RenderProfileAnchor:
    return RenderProfileAnchor(
        sheet="DP200001",
        source_row=row,
        source_cell=f"A{row}",
        ordinal=str(row - 9),
        record_identity="DP200001",
    )


def _design_identity(*, sha256: str = "a" * 64) -> RenderProfileDesignIdentity:
    return RenderProfileDesignIdentity(
        modelo="200",
        design_epoch="2025",
        source_ref="aeat-dr-200-2025",
        source_sha256=sha256,
    )


def _intermediate(*, smaller_content: str | None = None, smaller_length: int = 2) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-200-2025",
                "source_sha256": "a" * 64,
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2025",
            },
            "sheets": (
                {
                    "sheet": "DP200001",
                    "record_identity": "DP200001",
                    "declared_total": 38 + smaller_length,
                    "fields": (
                        _field(10, offset=1, length=17, aeat_type="Num"),
                        _field(11, offset=18, length=17, aeat_type="N"),
                        _field(12, offset=35, length=smaller_length, aeat_type="Num", content=smaller_content),
                        _field(13, offset=35 + smaller_length, length=4, aeat_type="An", content=None),
                    ),
                },
            ),
        },
    )


def _field(
    row: int,
    *,
    offset: int,
    length: int,
    aeat_type: str,
    content: str | None = None,
) -> dict[str, object]:
    return {
        "sheet": "DP200001",
        "record_identity": "DP200001",
        "source_row": row,
        "source_cell": f"A{row}",
        "ordinal": str(row - 9),
        "offset": offset,
        "length": length,
        "aeat_type": aeat_type,
        "normalized_description": f"Reviewed field {row}",
        "validation": None,
        "content": content,
    }


def _joined(intermediate: RecordDesignIntermediate | None = None) -> JoinedRecordDesign:
    parsed = intermediate or _intermediate()
    sheet = parsed.sheets[0]
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "200",
            "design_epoch": "2025",
            "source_ref": parsed.source.source_ref,
            "source_sha256": parsed.source.source_sha256,
            "records": (
                {
                    "sheet": sheet.sheet,
                    "record_identity": sheet.record_identity,
                    "export_record_id": "reviewed-record",
                    "record_type": "detail",
                },
            ),
            "entries": tuple(
                {
                    "anchor": {
                        "sheet": field.sheet,
                        "source_row": field.source_row,
                        "source_cell": field.source_cell,
                        "ordinal": field.ordinal,
                        "record_identity": field.record_identity,
                    },
                    "export_field_id": f"reviewed.field-{field.ordinal}",
                    "kind": "filler",
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                }
                for field in sheet.fields
            ),
        },
    )
    fields = tuple(
        JoinedRecordDesignField(parser_field=field, semantic_entry=entry)
        for field, entry in zip(sheet.fields, semantic_map.entries, strict=True)
    )
    return JoinedRecordDesign(
        modelo="200",
        source=parsed.source,
        records=(
            JoinedRecordDesignRecord(
                parser_sheet=sheet,
                semantic_record=semantic_map.records[0],
                fields=fields,
            ),
        ),
        fields=fields,
    )


def _width_rule(aeat_type: str, anchor: RenderProfileAnchor) -> Width17MembershipRule:
    payload = {
        "rule_kind": "width_17_membership",
        "aeat_type": aeat_type,
        "anchors": (anchor,),
        "integer_digits": 15 if aeat_type == "Num" else 14,
        "decimal_digits": 2,
        "sign_policy": "unsigned" if aeat_type == "Num" else "n-prefix-negative-blank-nonnegative",
        "evidence": {
            "authority_kind": "official_source",
            "source_sheet": "DP200001",
            "source_cell": "A121",
            "expected_normalized_statement": "The official source states the amount digit allocation here.",
            "justification": "The reviewed membership explicitly identifies this amount anchor.",
        },
    }
    return Width17MembershipRule.model_validate(payload)


def _singleton(anchor: RenderProfileAnchor) -> SingletonNumericRule:
    return SingletonNumericRule(
        rule_kind="singleton_numeric",
        anchor=anchor,
        aeat_type="Num",
        semantic_kind="digit_string",
        value_policy="digit-string",
        integer_digits=2,
        decimal_digits=0,
        sign_policy="unsigned",
        allowed_values=(),
        evidence=OfficialSourceEvidence(
            authority_kind="official_source",
            source_sheet=anchor.sheet,
            source_cell=anchor.source_cell or "",
            expected_normalized_statement="Independent review identifies this exact field as a two-digit string.",
            justification="Leading zeroes are semantically significant for this exact anchor.",
        ),
    )


def _profile() -> RenderProfile:
    return RenderProfile(
        schema_version=1,
        design_identity=_design_identity(),
        fragment_ids=("width-17", "smaller-fields"),
        width_17_rules=(
            _width_rule("Num", _anchor(10)),
            _width_rule("N", _anchor(11)),
        ),
        singleton_rules=(_singleton(_anchor(12)),),
    )


def _source_evidence() -> RenderProfileSourceEvidence:
    return RenderProfileSourceEvidence(
        design_identity=_design_identity(),
        entries=(
            RenderProfileSourceEvidenceEntry(
                sheet="DP200001",
                cell="A121",
                normalized_statement="The official source states the amount digit allocation here.",
            ),
            RenderProfileSourceEvidenceEntry(
                sheet="DP200001",
                cell="A12",
                normalized_statement="Independent review identifies this exact field as a two-digit string.",
            ),
        ),
    )


def _fragment_toml(fragment: RenderProfileFragment) -> str:
    """Order root scalar arrays before TOML tables for the test artefact writer."""
    payload = fragment.model_dump(mode="json")
    ordered = {
        "schema_version": payload["schema_version"],
        "fragment_id": payload["fragment_id"],
    }
    if payload["width_17_rules"]:
        ordered["singleton_rules"] = []
        ordered["width_17_rules"] = payload["width_17_rules"]
    else:
        ordered["width_17_rules"] = []
        ordered["singleton_rules"] = payload["singleton_rules"]
    ordered["design_identity"] = payload["design_identity"]
    return rtoml.dumps(ordered)


def test_complete_profile_covers_only_blank_fixed_numeric_fields_and_preserves_num_n_policy() -> None:
    """The production validator accepts exact membership, not a type/width default."""
    profile = _profile()
    validate_render_profile(profile, _joined(), _source_evidence())

    assert profile.width_17_rules[0].sign_policy == "unsigned"
    assert profile.width_17_rules[1].sign_policy == "n-prefix-negative-blank-nonnegative"
    evidence = profile.singleton_rules[0].evidence
    assert isinstance(evidence, OfficialSourceEvidence)
    assert evidence.source_cell == profile.singleton_rules[0].anchor.source_cell


def test_singleton_rules_consume_the_public_closed_value_policy_axis() -> None:
    profile = _profile()

    assert all(isinstance(rule.value_policy, ExportValuePolicy) for rule in profile.singleton_rules)
    source = Path("dev/registry/pipeline/_render_profile.py").read_text(encoding="utf-8")
    assert "SingletonValuePolicy" not in source
    assert "BeforeValidator(coerce_export_value_policy)" not in source


def test_render_profile_digest_is_order_independent_and_evidence_sensitive() -> None:
    profile = _profile()
    source_evidence = _source_evidence()
    reordered = profile.model_copy(
        update={
            "fragment_ids": tuple(reversed(profile.fragment_ids)),
            "width_17_rules": tuple(reversed(profile.width_17_rules)),
            "singleton_rules": tuple(reversed(profile.singleton_rules)),
        },
    )
    reordered_evidence = source_evidence.model_copy(
        update={"entries": tuple(reversed(source_evidence.entries))},
    )
    changed_evidence = source_evidence.model_copy(
        update={
            "entries": (
                source_evidence.entries[0].model_copy(
                    update={"normalized_statement": "A distinct reviewed source statement."},
                ),
                *source_evidence.entries[1:],
            ),
        },
    )

    baseline = render_profile_digest(profile, source_evidence)

    assert render_profile_digest(reordered, reordered_evidence) == baseline
    assert render_profile_digest(profile, changed_evidence) != baseline
    assert render_profile_digest(profile.model_copy(update={"fragment_ids": ("changed",)}), source_evidence) != baseline


def test_wire_authority_profiles_have_one_unambiguous_class_home() -> None:
    production_paths = scan_directory(Path(__file__).parents[1] / "pipeline", pattern="*.py")
    class_homes: dict[str, list[str]] = {"RenderProfile": [], "ExportTreeTransportProfile": []}
    for path in production_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in class_homes:
                class_homes[node.name].append(path.name)
        assert "ExportRenderProfile" not in path.read_text(encoding="utf-8")

    assert class_homes == {
        "RenderProfile": ["_render_profile.py"],
        "ExportTreeTransportProfile": ["_export_tree.py"],
    }


def test_fragment_toml_refuses_a_missing_required_value_policy(tmp_path: Path) -> None:
    fragment = RenderProfileFragment(
        schema_version=1,
        fragment_id="missing-policy",
        design_identity=_design_identity(),
        width_17_rules=(),
        singleton_rules=(_singleton(_anchor(12)),),
    )
    source = _fragment_toml(fragment)
    assert 'value_policy = "digit-string"\n' in source
    (tmp_path / "0001.toml").write_text(
        source.replace('value_policy = "digit-string"\n', "", 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="value_policy"):
        load_render_profile(tmp_path)


@pytest.mark.parametrize(
    ("profile", "joined", "error"),
    (
        (
            _profile().model_copy(update={"design_identity": _design_identity(sha256="b" * 64)}),
            _joined(),
            "identity",
        ),
        (
            _profile().model_copy(update={"singleton_rules": ()}),
            _joined(),
            "cover exactly",
        ),
        (
            _profile().model_copy(
                update={"singleton_rules": (_singleton(_anchor(12)), _singleton(_anchor(12)))},
            ),
            _joined(),
            "duplicate or overlapping",
        ),
        (_profile(), _joined(_intermediate(smaller_content="2 enteros")), "cover exactly"),
        (_profile(), _joined().model_copy(update={"modelo": "303"}), "identity"),
    ),
)
def test_profile_refuses_identity_missing_overlap_present_content_and_modelo_drift(
    profile: RenderProfile,
    joined: JoinedRecordDesign,
    error: str,
) -> None:
    """Plausible authority mutations refuse the entire design."""
    with pytest.raises(RegistryValidationError, match=error):
        validate_render_profile(profile, joined, _source_evidence())


@pytest.mark.parametrize(
    ("source_sheet", "source_cell", "statement", "error"),
    (
        ("DP200001", "Z999", "The official source states the amount digit allocation here.", "does not exist"),
        ("DP200001", "A121", "Different source text", "does not match verified source"),
    ),
)
def test_profile_refuses_nonexistent_or_mismatched_source_evidence(
    source_sheet: str,
    source_cell: str,
    statement: str,
    error: str,
) -> None:
    """A profile-authored claim must resolve exactly against separate verified source evidence."""
    profile = _profile()
    width_rule = profile.width_17_rules[0]
    contradicted_rule = width_rule.model_copy(
        update={
            "evidence": width_rule.evidence.model_copy(
                update={
                    "source_sheet": source_sheet,
                    "source_cell": source_cell,
                    "expected_normalized_statement": statement,
                },
            ),
        },
    )
    contradicted_profile = profile.model_copy(
        update={"width_17_rules": (contradicted_rule, profile.width_17_rules[1])},
    )

    with pytest.raises(RegistryValidationError, match=error):
        validate_render_profile(contradicted_profile, _joined(), _source_evidence())


def test_profile_refuses_source_evidence_sha_drift() -> None:
    """Exact cell text from a different source digest is inapplicable authority."""
    drifted = _source_evidence().model_copy(
        update={"design_identity": _design_identity(sha256="b" * 64)},
    )
    with pytest.raises(RegistryValidationError, match=r"source evidence.*identity"):
        validate_render_profile(_profile(), _joined(), drifted)


def test_profile_models_refuse_implicit_defaults_selectors_and_sign_conflicts() -> None:
    """Authored rules are strict and every wire choice is explicit.

    ``source_cell`` is the ONE documented exception, and it is not a weakening:
    a PDF design has no parser-column cell to name, so requiring the key made
    every PDF anchor unauthorable rather than making any choice explicit. The
    exception is exactly the one :class:`SemanticMapAnchor` already carries, for
    the same reason. Every other anchor key stays required, which is what the
    ``source_row`` case below pins -- omit the exception and the principle it
    guards disappears with it.
    """
    anchor_payload = _anchor(12).model_dump(mode="python")
    del anchor_payload["source_cell"]
    omitted_cell = RenderProfileAnchor.model_validate(anchor_payload)
    assert omitted_cell.source_cell is None

    anchor_payload = _anchor(12).model_dump(mode="python")
    del anchor_payload["source_row"]
    with pytest.raises(ValidationError, match="source_row"):
        RenderProfileAnchor.model_validate(anchor_payload)

    anchor_payload = _anchor(12).model_dump(mode="python")
    del anchor_payload["ordinal"]
    with pytest.raises(ValidationError, match="ordinal"):
        RenderProfileAnchor.model_validate(anchor_payload)

    singleton_payload = _singleton(_anchor(12)).model_dump(mode="python")
    del singleton_payload["semantic_kind"]
    with pytest.raises(ValidationError, match="semantic_kind"):
        SingletonNumericRule.model_validate(singleton_payload)

    singleton_payload = _singleton(_anchor(12)).model_dump(mode="python")
    del singleton_payload["value_policy"]
    with pytest.raises(ValidationError, match="value_policy"):
        SingletonNumericRule.model_validate(singleton_payload)

    singleton_payload["value_policy"] = None
    with pytest.raises(ValidationError, match="value_policy"):
        SingletonNumericRule.model_validate(singleton_payload)

    selector_payload = _singleton(_anchor(12)).model_dump(mode="python") | {"selector": "Num:2"}
    with pytest.raises(ValidationError, match="selector"):
        SingletonNumericRule.model_validate(selector_payload)

    signed_payload = _width_rule("N", _anchor(11)).model_dump(mode="python")
    signed_payload["sign_policy"] = "unsigned"
    with pytest.raises(ValidationError, match="sign policy"):
        Width17MembershipRule.model_validate(signed_payload)

    unsigned_payload = _width_rule("Num", _anchor(10)).model_dump(mode="python")
    unsigned_payload["integer_digits"] = 14
    with pytest.raises(ValidationError, match="sign policy"):
        Width17MembershipRule.model_validate(unsigned_payload)

    policy_payload = _singleton(_anchor(12)).model_dump(mode="python")
    policy_payload["semantic_kind"] = "checkbox"
    policy_payload["value_policy"] = "selected-1-unselected-0"
    policy_payload["integer_digits"] = 1
    policy_payload["allowed_values"] = ("0", "1")
    policy_payload["evidence"] = {
        "authority_kind": "reviewed_policy",
        "decision_id": "m200-2025-dp200001-r0012",
        "governed_anchor": _anchor(13),
        "decision_statement": "Encode selected as 1 and absent or unselected as 0.",
        "justification": "Reviewed exact-anchor decision, not official-source text.",
    }
    with pytest.raises(ValidationError, match="exact governed anchor"):
        SingletonNumericRule.model_validate(policy_payload)

    policy_payload["evidence"]["governed_anchor"] = _anchor(12)
    policy_payload["value_policy"] = "enumerated-digits"
    with pytest.raises(ValidationError, match="selected-1-unselected-0"):
        SingletonNumericRule.model_validate(policy_payload)


@pytest.mark.parametrize(
    ("semantic_kind", "value_policy", "integer_digits", "decimal_digits", "allowed_values", "error"),
    (
        ("date_yyyymmdd", "yyyymmdd", 7, 0, (), "exactly 8 integer digits"),
        ("date_yyyymmdd", "yyyymmdd", 8, 1, (), "exactly 8 integer digits"),
        ("date_ddmmyyyy", "ddmmyyyy", 7, 0, (), "exactly 8 integer digits"),
        ("date_ddmmyyyy", "ddmmyyyy", 8, 1, (), "exactly 8 integer digits"),
        ("integer", "unsigned-integer", 0, 0, (), "positive integer digits"),
        ("integer", "unsigned-integer", 2, 1, (), "0 decimal digits"),
        ("decimal", "implied-decimal", 2, 0, (), "positive integer and decimal digits"),
        ("percentage_decimal", "implied-decimal", 0, 2, (), "positive integer and decimal digits"),
        ("digit_string", "digit-string", 1, 1, (), "0 decimal digits"),
        ("identifier_digits", "identifier-digits", 1, 1, (), "0 decimal digits"),
        ("enumeration", "enumerated-digits", 1, 1, ("1", "2"), "0 decimal digits"),
    ),
)
def test_singleton_schema_refuses_semantic_kind_wire_contradictions(
    semantic_kind: str,
    value_policy: str,
    integer_digits: int,
    decimal_digits: int,
    allowed_values: tuple[str, ...],
    error: str,
) -> None:
    """An authored kind never supplies an internally contradictory wire shape."""
    payload = _singleton(_anchor(12)).model_dump(mode="python")
    payload.update(
        semantic_kind=semantic_kind,
        value_policy=value_policy,
        integer_digits=integer_digits,
        decimal_digits=decimal_digits,
        allowed_values=allowed_values,
    )
    with pytest.raises(ValidationError, match=error):
        SingletonNumericRule.model_validate(payload)


def test_enumeration_domain_uses_semantic_integers_not_padded_wire_spellings() -> None:
    payload = _singleton(_anchor(12)).model_dump(mode="python")
    payload.update(
        semantic_kind="enumeration",
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        integer_digits=2,
        decimal_digits=0,
        allowed_values=("1", "3"),
    )

    rule = SingletonNumericRule.model_validate(payload)
    assert rule.allowed_values == ("1", "3")

    payload["allowed_values"] = ("01", "03")
    with pytest.raises(ValidationError, match="canonical ASCII-integer"):
        SingletonNumericRule.model_validate(payload)


@pytest.mark.parametrize(
    (
        "semantic_kind",
        "policy",
        "integer_digits",
        "decimal_digits",
        "allowed_values",
        "data_type",
        "padding",
        "date_format",
    ),
    (
        ("checkbox", ExportValuePolicy.SELECTED_1_UNSELECTED_0, 1, 0, ("0", "1"), "integer", "left_zero", None),
        (
            "year_last_two_digits",
            ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
            2,
            0,
            (),
            "integer",
            "left_zero",
            None,
        ),
        ("integer", ExportValuePolicy.UNSIGNED_INTEGER, 2, 0, (), "integer", "left_zero", None),
        ("percentage_decimal", ExportValuePolicy.IMPLIED_DECIMAL, 3, 2, (), "decimal", "left_zero", None),
        ("date_yyyymmdd", ExportValuePolicy.YYYYMMDD, 8, 0, (), "date", "none", "aaaammdd"),
        ("date_ddmmyyyy", ExportValuePolicy.DDMMYYYY, 8, 0, (), "date", "none", "ddmmaaaa"),
        ("enumeration", ExportValuePolicy.ENUMERATED_DIGITS, 2, 0, ("1", "3"), "integer", "left_zero", None),
        ("digit_string", ExportValuePolicy.DIGIT_STRING, 4, 0, (), "text", "none", None),
        ("identifier_digits", ExportValuePolicy.IDENTIFIER_DIGITS, 13, 0, (), "text", "none", None),
        ("year_yyyy", ExportValuePolicy.FOUR_DIGIT_YEAR, 4, 0, (), "integer", "left_zero", None),
        ("month_mm", ExportValuePolicy.TWO_DIGIT_MONTH, 2, 0, (), "integer", "left_zero", None),
        ("day_dd", ExportValuePolicy.TWO_DIGIT_DAY, 2, 0, (), "integer", "left_zero", None),
    ),
)
def test_singleton_mapper_projects_every_public_policy_to_an_exact_schema_shape(
    semantic_kind: str,
    policy: ExportValuePolicy,
    integer_digits: int,
    decimal_digits: int,
    allowed_values: tuple[str, ...],
    data_type: str,
    padding: str,
    date_format: str | None,
) -> None:
    width = integer_digits + decimal_digits
    joined = _joined(_intermediate(smaller_length=width)).fields[2]
    joined = JoinedRecordDesignField(
        parser_field=joined.parser_field,
        semantic_entry=joined.semantic_entry.model_copy(
            update={
                "kind": CasillaFieldKind.HEADER,
                "producer_key": FilingProducerKey.PRESENTER_TAX_ID,
            },
        ),
    )
    rule = SingletonNumericRule.model_validate(
        _singleton(_anchor(12)).model_dump(mode="python")
        | {
            "semantic_kind": semantic_kind,
            "value_policy": policy,
            "integer_digits": integer_digits,
            "decimal_digits": decimal_digits,
            "allowed_values": allowed_values,
        },
    )

    derivation = _export_tree._profile_singleton_derivation(
        joined,
        rule,
        export_record_id="reviewed-record",
    )

    assert derivation.field.value_policy is policy
    assert derivation.field.data_type == data_type
    assert derivation.field.padding == padding
    assert derivation.field.date_format == date_format
    expected_allowed_values = allowed_values or None if policy is ExportValuePolicy.ENUMERATED_DIGITS else None
    assert derivation.field.allowed_values == expected_allowed_values
    assert set(_export_tree._SINGLETON_POLICY_SHAPES) == set(ExportValuePolicy)


def test_fragment_loader_compiles_by_filename_and_refuses_fragment_identity_drift(tmp_path: Path) -> None:
    """Fragmentation changes review size only; compilation order and identity stay deterministic."""
    profile = _profile()
    unsigned = RenderProfileFragment(
        schema_version=1,
        fragment_id="width-17-num",
        design_identity=profile.design_identity,
        width_17_rules=(profile.width_17_rules[0],),
        singleton_rules=(),
    )
    signed = RenderProfileFragment(
        schema_version=1,
        fragment_id="width-17-n",
        design_identity=profile.design_identity,
        width_17_rules=(profile.width_17_rules[1],),
        singleton_rules=(),
    )
    smaller = RenderProfileFragment(
        schema_version=1,
        fragment_id="smaller-field",
        design_identity=profile.design_identity,
        width_17_rules=(),
        singleton_rules=profile.singleton_rules,
    )
    (tmp_path / "0300-smaller.toml").write_text(_fragment_toml(smaller), encoding="utf-8")
    (tmp_path / "0200-signed.toml").write_text(_fragment_toml(signed), encoding="utf-8")
    (tmp_path / "0100-unsigned.toml").write_text(_fragment_toml(unsigned), encoding="utf-8")

    compiled = load_and_validate_render_profile(tmp_path, _joined(), _source_evidence())
    assert compiled.fragment_ids == ("width-17-num", "width-17-n", "smaller-field")

    drifted = smaller.model_copy(update={"design_identity": _design_identity(sha256="b" * 64)})
    (tmp_path / "0300-smaller.toml").write_text(_fragment_toml(drifted), encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="inapplicable design identities"):
        load_and_validate_render_profile(tmp_path, _joined(), _source_evidence())


def test_profile_loader_refuses_legacy_or_non_profile_siblings(tmp_path: Path) -> None:
    """A profile directory is an exhaustive authority set, never a tolerant legacy container."""
    profile = _profile()
    fragment = RenderProfileFragment(
        schema_version=1,
        fragment_id="width-17-num",
        design_identity=profile.design_identity,
        width_17_rules=(profile.width_17_rules[0],),
        singleton_rules=(),
    )
    (tmp_path / "0001-profile.toml").write_text(_fragment_toml(fragment), encoding="utf-8")
    (tmp_path / "legacy-derived-layout.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="only regular TOML fragments"):
        load_render_profile(tmp_path)


def test_profile_loader_refuses_conflicting_width17_authority(tmp_path: Path) -> None:
    """Splitting one numeric type cannot smuggle in a contradictory reviewed convention."""
    profile = _profile()
    first = RenderProfileFragment(
        schema_version=1,
        fragment_id="width-17-num-a",
        design_identity=profile.design_identity,
        width_17_rules=(profile.width_17_rules[0],),
        singleton_rules=(),
    )
    num_rule = profile.width_17_rules[0]
    assert isinstance(num_rule.evidence, OfficialSourceEvidence)
    conflicting_rule = num_rule.model_copy(
        update={
            "evidence": num_rule.evidence.model_copy(
                update={"expected_normalized_statement": "Contradictory reviewed source statement."},
            ),
        },
    )
    conflicting = RenderProfileFragment(
        schema_version=1,
        fragment_id="width-17-num-b",
        design_identity=profile.design_identity,
        width_17_rules=(conflicting_rule,),
        singleton_rules=(),
    )
    (tmp_path / "0001-num-a.toml").write_text(_fragment_toml(first), encoding="utf-8")
    (tmp_path / "0002-num-b.toml").write_text(_fragment_toml(conflicting), encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="conflict on width-17 Num authority"):
        load_render_profile(tmp_path)


def test_profile_refuses_unknown_anchor_without_tolerating_partial_coverage() -> None:
    """An anchor outside parser-owned eligibility blocks the entire reviewed profile."""
    unknown = RenderProfileAnchor(
        sheet="DP200001",
        source_row=99,
        source_cell="A99",
        ordinal="99",
        record_identity="DP200001",
    )
    unknown_rule = _singleton(unknown).model_copy(
        update={
            "evidence": OfficialSourceEvidence(
                authority_kind="official_source",
                source_sheet="DP200001",
                source_cell="A12",
                expected_normalized_statement="Independent review identifies this exact field as a two-digit string.",
                justification="The source claim is real; only its governed parser anchor is inapplicable.",
            ),
        },
    )
    profile = _profile().model_copy(update={"singleton_rules": (unknown_rule,)})

    with pytest.raises(RegistryValidationError, match="unknown="):
        validate_render_profile(profile, _joined(), _source_evidence())


def test_real_m200_profile_exactly_covers_source_eligibility_and_excludes_variable_envelope() -> None:
    """The committed profile validates exhaustively against the hash-verified source."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    eligibility = project_render_profile_eligibility(field for sheet in intermediate.sheets for field in sheet.fields)
    design_identity = RenderProfileDesignIdentity(
        modelo="200",
        design_epoch=intermediate.source.design_epoch,
        source_ref=intermediate.source.source_ref,
        source_sha256=intermediate.source.source_sha256,
    )
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    profile_directory = Path(__file__).parents[1] / "render_profiles" / "modelo_200" / "2025"
    profile = load_render_profile(profile_directory)
    evidence = load_render_profile_source_evidence(resolved.path, profile)
    validate_render_profile_authority(profile, design_identity, eligibility, evidence)

    width_rules = {rule.aeat_type: rule for rule in profile.width_17_rules}
    assert set(width_rules) == {"Num", "N"}
    assert (
        width_rules["Num"].integer_digits,
        width_rules["Num"].decimal_digits,
        width_rules["Num"].sign_policy,
    ) == (15, 2, "unsigned")
    assert (
        width_rules["N"].integer_digits,
        width_rules["N"].decimal_digits,
        width_rules["N"].sign_policy,
    ) == (14, 2, "n-prefix-negative-blank-nonnegative")

    eligible_anchors = {
        RenderProfileAnchor(
            sheet=field.sheet,
            source_row=field.source_row,
            source_cell=field.source_cell,
            ordinal=field.ordinal,
            record_identity=field.record_identity,
        )
        for field in eligibility.all_fields
    }
    governed_anchors = {
        *(anchor for rule in profile.width_17_rules for anchor in rule.anchors),
        *(rule.anchor for rule in profile.singleton_rules),
    }
    assert governed_anchors == eligible_anchors
    assert {rule.anchor for rule in profile.singleton_rules} == {
        RenderProfileAnchor(
            sheet=field.sheet,
            source_row=field.source_row,
            source_cell=field.source_cell,
            ordinal=field.ordinal,
            record_identity=field.record_identity,
        )
        for field in eligibility.smaller_fields
    }
    assert set(eligibility.all_fields) == set(eligibility.width_17_fields) | set(eligibility.smaller_fields)
    assert not set(eligibility.width_17_fields).intersection(eligibility.smaller_fields)
    assert intermediate.variable_envelopes
    assert not any(field.sheet == "DP200000" for field in eligibility.all_fields)

    checkbox_rows = {
        *(("DP200001", row) for row in (24, 27)),
        *(("DP200001", row) for row in range(29, 106)),
        *(("DP200001", row) for row in range(107, 110)),
        ("DP200001B", 22),
        ("DP200001B", 23),
        ("DP200002B", 149),
        ("DP200020B", 39),
    }
    checkbox_rules = {rule for rule in profile.singleton_rules if rule.semantic_kind == "checkbox"}
    assert {(rule.anchor.sheet, rule.anchor.source_row) for rule in checkbox_rules} == checkbox_rows
    assert all(
        rule.allowed_values == ("0", "1")
        and rule.value_policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0
        and isinstance(rule.evidence, ReviewedPolicyDecision)
        and rule.evidence.governed_anchor == rule.anchor
        for rule in checkbox_rules
    )
    year_rules = {rule for rule in profile.singleton_rules if rule.semantic_kind == "year_last_two_digits"}
    assert {(rule.anchor.sheet, rule.anchor.source_row) for rule in year_rules} == {
        ("DP200DID", 17),
        ("DP200DID", 20),
    }
    assert all(
        rule.value_policy is ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS
        and isinstance(rule.evidence, ReviewedPolicyDecision)
        and rule.evidence.governed_anchor == rule.anchor
        for rule in year_rules
    )
    assert all(
        isinstance(rule.evidence, OfficialSourceEvidence)
        for rule in profile.singleton_rules
        if rule not in checkbox_rules | year_rules
    )


def test_real_m390_2022_profile_exactly_covers_source_eligibility_and_binds_day_first_dates() -> None:
    """The 2022 M390 profile binds all nine blank numeric fields to its pinned source."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-390-2022",
        filing_year=2022,
        design_epoch="2022",
    )
    eligibility = project_render_profile_eligibility(field for sheet in intermediate.sheets for field in sheet.fields)
    design_identity = RenderProfileDesignIdentity(
        modelo="390",
        design_epoch=intermediate.source.design_epoch,
        source_ref=intermediate.source.source_ref,
        source_sha256=intermediate.source.source_sha256,
    )
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-390-2022",
        filing_year=2022,
        design_epoch="2022",
    )
    profile_directory = Path(__file__).parents[1] / "render_profiles" / "modelo_390" / "2022"
    profile = load_render_profile(profile_directory)
    evidence = load_render_profile_source_evidence(resolved.path, profile)
    validate_render_profile_authority(profile, design_identity, eligibility, evidence)

    eligible_anchors = {
        RenderProfileAnchor(
            sheet=field.sheet,
            source_row=field.source_row,
            source_cell=field.source_cell,
            ordinal=field.ordinal,
            record_identity=field.record_identity,
        )
        for field in eligibility.all_fields
    }
    governed_anchors = {rule.anchor for rule in profile.singleton_rules}
    assert len(eligibility.all_fields) == 9
    assert governed_anchors == eligible_anchors

    day_first_rules = tuple(rule for rule in profile.singleton_rules if rule.semantic_kind == "date_ddmmyyyy")
    assert {(rule.anchor.sheet, rule.anchor.source_row, rule.value_policy) for rule in day_first_rules} == {
        ("Pág. 1", 65, ExportValuePolicy.DDMMYYYY),
        ("Pág. 1", 69, ExportValuePolicy.DDMMYYYY),
        ("Pág. 1", 73, ExportValuePolicy.DDMMYYYY),
    }
    assert all(isinstance(rule.evidence, OfficialSourceEvidence) for rule in day_first_rules)
    assert {(entry.sheet, entry.cell, entry.normalized_statement) for entry in evidence.entries} == {
        (
            "Pág. 1",
            "E65",
            "4. Representante - Personas Jurídicas - Represent. 1 - Fecha Poder (DDMMAAAA)",
        ),
        (
            "Pág. 1",
            "E69",
            "4. Representante - Personas Jurídicas - Represent. 2 - Fecha Poder (DDMMAAAA)",
        ),
        (
            "Pág. 1",
            "E73",
            "4. Representante - Personas Jurídicas - Represent. 3 - Fecha Poder (DDMMAAAA)",
        ),
    }


def test_real_source_loader_refuses_nonexistent_cell_statement_and_sha_mutations() -> None:
    """Source claims resolve from the binary and every identity or text drift fails closed."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    profile = load_render_profile(
        Path(__file__).parents[1] / "render_profiles" / "modelo_200" / "2025",
    )
    first_rule = profile.width_17_rules[0]
    assert isinstance(first_rule.evidence, OfficialSourceEvidence)

    missing_rule = first_rule.model_copy(
        update={
            "evidence": first_rule.evidence.model_copy(update={"source_cell": "Z999"}),
        },
    )
    missing_profile = profile.model_copy(
        update={"width_17_rules": (missing_rule, profile.width_17_rules[1])},
    )
    with pytest.raises(RegistryValidationError, match="does not contain source text"):
        load_render_profile_source_evidence(resolved.path, missing_profile)

    evidence = load_render_profile_source_evidence(resolved.path, profile)
    mismatched_rule = first_rule.model_copy(
        update={
            "evidence": first_rule.evidence.model_copy(
                update={"expected_normalized_statement": "Contradicted official source text"},
            ),
        },
    )
    mismatched_profile = profile.model_copy(
        update={"width_17_rules": (mismatched_rule, profile.width_17_rules[1])},
    )
    eligibility = project_render_profile_eligibility(
        field
        for sheet in load_record_design_intermediate(
            source_root,
            catalogues.sources,
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="2025",
        ).sheets
        for field in sheet.fields
    )
    with pytest.raises(RegistryValidationError, match="does not match verified source"):
        validate_render_profile_authority(
            mismatched_profile,
            profile.design_identity,
            eligibility,
            evidence,
        )

    drifted = profile.model_copy(
        update={
            "design_identity": profile.design_identity.model_copy(
                update={"source_sha256": "b" * 64},
            ),
        },
    )
    with pytest.raises(RegistryValidationError, match="SHA-256"):
        load_render_profile_source_evidence(resolved.path, drifted)


def test_real_source_loader_refuses_a_linked_official_binary_before_hashing(tmp_path: Path) -> None:
    """A link never becomes a substitute source for profile evidence."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    profile = load_render_profile(
        Path(__file__).parents[1] / "render_profiles" / "modelo_200" / "2025",
    )
    linked_source = tmp_path / resolved.path.name
    linked_source.symlink_to(resolved.path)

    with pytest.raises(RegistryValidationError, match="regular file"):
        load_render_profile_source_evidence(linked_source, profile)


def test_profile_authority_has_no_legacy_tree_or_layout_oracle() -> None:
    """The authority depends only on parser IR and exact joined source fields."""
    module = ast.parse(inspect.getsource(_render_profile))
    local_imports = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.level and node.module is not None
    }
    assert local_imports == {"_record_design_ir", "_semantic_map_join"}
    source_loader = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_render_profile_source_evidence"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "is_link_like"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "source_path"
        for node in ast.walk(source_loader)
    )


def test_real_profile_fragments_stay_below_the_reviewability_line_cap() -> None:
    """Deterministic partitioning keeps every authored fragment reviewable."""
    profile_directory = Path(__file__).parents[1] / "render_profiles" / "modelo_200" / "2025"
    paths = scan_directory(profile_directory, pattern="*.toml")
    assert paths
    assert all(len(path.read_text(encoding="utf-8").splitlines()) <= 500 for path in paths)


def test_source_reserved_slots_are_never_eligible_while_blank_numerics_remain_eligible() -> None:
    """Reservation is read from the description because the type column lies.

    Both directions are asserted deliberately: a predicate that excluded every
    field would satisfy the reserved half alone and silently empty the profile.
    """
    reserved_num = RecordDesignIntermediateField(
        sheet="DP30302",
        record_identity="DP30302",
        source_row=97,
        source_cell="A97",
        ordinal="92",
        offset=1000,
        length=3,
        aeat_type="Num",
        normalized_description="Reservado para la AEAT",
    )
    reserved_upper_case = reserved_num.model_copy(
        update={"ordinal": "93", "source_row": 98, "source_cell": "A98", "offset": 1003},
    ).model_copy(update={"normalized_description": "RESERVADO PARA LA A.E.A.T. (Dejar en blanco)"})
    live_blank_numeric = RecordDesignIntermediateField(
        sheet="DP30301",
        record_identity="DP30301",
        source_row=14,
        source_cell="A14",
        ordinal="9",
        offset=20,
        length=4,
        aeat_type="Num",
        normalized_description="Devengo (2) - Ejercicio",
    )
    eligibility = project_render_profile_eligibility(
        (reserved_num, reserved_upper_case, live_blank_numeric),
    )
    assert live_blank_numeric in eligibility.all_fields
    assert reserved_num not in eligibility.all_fields
    assert reserved_upper_case not in eligibility.all_fields
    assert eligibility.all_fields == (live_blank_numeric,)


def test_real_modelo_303_reserved_numeric_slots_are_excluded_from_eligibility() -> None:
    """The exclusion holds against the real epoch that exhibits the vestigial typing."""
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref="aeat-dr-303-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    fixed = tuple(field for sheet in intermediate.sheets for field in sheet.fields)
    reserved_numeric = tuple(
        field
        for field in fixed
        if field.aeat_type in {"Num", "N"} and "reservado" in field.normalized_description.casefold()
    )
    assert reserved_numeric, "the 2025 design must still exhibit vestigially typed reserved slots"
    eligibility = project_render_profile_eligibility(fixed)
    assert not set(reserved_numeric) & set(eligibility.all_fields)
    assert eligibility.all_fields, "excluding reserved slots must not empty the eligible set"


def _eligibility_for(source_ref: str, epoch: str, catalogue: str) -> tuple[object, ...]:
    """Return the eligible fields of one hash-verified design."""
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", catalogue))
    intermediate = load_record_design_intermediate(
        bundled_path(), catalogues.sources,
        source_ref=source_ref, filing_year=2025, design_epoch=epoch,
    )
    fields = [field for sheet in intermediate.sheets for field in sheet.fields]
    return project_render_profile_eligibility(fields).all_fields


def test_a_pdf_design_numeric_anchor_is_eligible_for_a_reviewed_rule() -> None:
    """Modelo 347 is PDF-sourced, and its numeric anchors need reviewed wire facts.

    Selecting on the workbook abbreviations alone made every one of them
    ineligible: a PDF design spells the naturaleza in full, and the parser
    canonicalises it to ``Numérico``. With no eligible field, an EMPTY render
    profile satisfied exhaustive coverage completely and the design generated
    with no declared numeric format, sign policy or decimal placement.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "2025", "operaciones-terceros.toml")

    assert len(eligible) == 19
    assert all(field.source_cell is None for field in eligible), "modelo 347 is PDF-sourced"


def test_pdf_prose_in_content_is_not_read_as_a_stated_wire_fact() -> None:
    """A PDF field's ``content`` is description, not a Contenido cell.

    Every one of Modelo 347's numeric anchors carries non-blank content, and it
    reads like "Se consignará el número identificativo correspondiente a la
    declaración". Under the workbook rule that non-blank content meant the design
    had stated the wire fact, which is the wrong positive inference this test
    pins.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "2025", "operaciones-terceros.toml")

    assert eligible, "no eligible field to assert on"
    assert all(field.content and field.content.strip() for field in eligible)


@pytest.mark.parametrize(
    ("source_ref", "epoch", "catalogue"),
    [("aeat-dr-232-2018", "2018", "is.toml"),
     ("aeat-dr-210-2022", "2022", "irnr.toml"),
     ("aeat-dr-303-2025", "2025", "iva.toml")],
)
def test_a_workbook_design_keeps_its_exact_previous_eligibility(
    source_ref: str, epoch: str, catalogue: str,
) -> None:
    """Widening to PDF sources must not move a workbook's eligible set at all.

    Re-derives the ORIGINAL rule here -- workbook abbreviations plus a blank
    Contenido cell -- and requires the live projection to agree on it exactly. A
    workbook field carries a ``source_cell``, so the content test still applies
    to it; if that ever stops holding, these three designs silently grow rules
    they never needed.
    """
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", catalogue))
    intermediate = load_record_design_intermediate(
        bundled_path(), catalogues.sources,
        source_ref=source_ref, filing_year=2025, design_epoch=epoch,
    )
    fields = [field for sheet in intermediate.sheets for field in sheet.fields]
    original = {
        (field.record_identity, field.offset)
        for field in fields
        if field.aeat_type in {"Num", "N"}
        and (field.content is None or not field.content.strip())
        and not _is_source_reserved_field(field)
    }
    live = {
        (field.record_identity, field.offset)
        for field in project_render_profile_eligibility(fields).all_fields
    }

    assert live == original


def test_a_source_reserved_pdf_slot_stays_ineligible() -> None:
    """A reserved run carries no wire fact on either source shape.

    Widening the numeric-type match must not start demanding a numeric rule for
    a slot the design reserves, which would force an author to model meaning onto
    filler.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "2025", "operaciones-terceros.toml")

    assert not [field for field in eligible if _is_source_reserved_field(field)]

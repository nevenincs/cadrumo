"""Real-IR and mutation proofs for the reviewed render-profile authority."""

from __future__ import annotations

from pathlib import Path

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import RegistryValidationError, load_catalogue_file

from .._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignWorkbookFormat,
    load_record_design_intermediate,
)
from .._render_profile import (
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileDesignIdentity,
    RenderProfileFragment,
    RenderProfileSourceEvidence,
    RenderProfileSourceEvidenceEntry,
    ReviewedEvidence,
    SingletonNumericRule,
    Width17MembershipRule,
    load_and_validate_render_profile,
    project_render_profile_eligibility,
    validate_render_profile,
)
from .._semantic_map import SemanticMap
from .._semantic_map_join import (
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
        ordinal=row - 9,
        record_identity="DP200001",
    )


def _design_identity(*, sha256: str = "a" * 64) -> RenderProfileDesignIdentity:
    return RenderProfileDesignIdentity(
        modelo="200",
        design_epoch="2025",
        source_ref="aeat-dr-200-2025",
        source_sha256=sha256,
    )


def _intermediate(*, smaller_content: str | None = None) -> RecordDesignIntermediate:
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
                    "declared_total": 40,
                    "fields": (
                        _field(10, offset=1, length=17, aeat_type="Num"),
                        _field(11, offset=18, length=17, aeat_type="N"),
                        _field(12, offset=35, length=2, aeat_type="Num", content=smaller_content),
                        _field(13, offset=37, length=4, aeat_type="An", content=None),
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
        "ordinal": row - 9,
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
        integer_digits=2,
        decimal_digits=0,
        sign_policy="unsigned",
        allowed_values=(),
        evidence=ReviewedEvidence(
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
    assert profile.singleton_rules[0].evidence.source_cell == profile.singleton_rules[0].anchor.source_cell


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
    """Authored rules are strict and every wire choice is explicit."""
    singleton_payload = _singleton(_anchor(12)).model_dump(mode="python")
    del singleton_payload["semantic_kind"]
    with pytest.raises(ValidationError, match="semantic_kind"):
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


@pytest.mark.parametrize(
    ("semantic_kind", "integer_digits", "decimal_digits", "allowed_values", "error"),
    (
        ("date_yyyymmdd", 7, 0, (), "exactly 8 integer digits"),
        ("date_yyyymmdd", 8, 1, (), "exactly 8 integer digits"),
        ("integer", 0, 0, (), "positive integer digits"),
        ("integer", 2, 1, (), "0 decimal digits"),
        ("decimal", 2, 0, (), "positive integer and decimal digits"),
        ("percentage_decimal", 0, 2, (), "positive integer and decimal digits"),
        ("digit_string", 1, 1, (), "0 decimal digits"),
        ("identifier_digits", 1, 1, (), "0 decimal digits"),
        ("enumeration", 1, 1, ("01", "02"), "0 decimal digits"),
    ),
)
def test_singleton_schema_refuses_semantic_kind_wire_contradictions(
    semantic_kind: str,
    integer_digits: int,
    decimal_digits: int,
    allowed_values: tuple[str, ...],
    error: str,
) -> None:
    """An authored kind never supplies an internally contradictory wire shape."""
    payload = _singleton(_anchor(12)).model_dump(mode="python")
    payload.update(
        semantic_kind=semantic_kind,
        integer_digits=integer_digits,
        decimal_digits=decimal_digits,
        allowed_values=allowed_values,
    )
    with pytest.raises(ValidationError, match=error):
        SingletonNumericRule.model_validate(payload)


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


def test_real_m200_ir_refuses_absent_authority_and_excludes_variable_envelope() -> None:
    """The real source stays blocked until every smaller blank numeric anchor is reviewed."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    eligibility = project_render_profile_eligibility(
        field for sheet in intermediate.sheets for field in sheet.fields
    )
    assert eligibility.smaller_fields
    assert set(eligibility.all_fields) == set(eligibility.width_17_fields) | set(eligibility.smaller_fields)
    assert not set(eligibility.width_17_fields).intersection(eligibility.smaller_fields)
    assert intermediate.variable_envelopes
    assert not any(field.sheet == "DP200000" for field in eligibility.all_fields)

    profile_directory = Path(__file__).parents[1] / "render_profiles" / "modelo_200" / "2025"
    assert not profile_directory.exists()

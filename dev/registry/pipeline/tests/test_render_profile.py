"""Real-IR and mutation proofs for the reviewed render-profile authority."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
    project_export_value,
    validate_export_wire_value,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .. import export_field_render_profile_derivation
from ..joined_record_design import (
    JoinedRecordDesign,
    JoinedRecordDesignField,
    JoinedRecordDesignRecord,
)
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignWorkbookFormat,
)
from ..render_profile import load_and_validate_render_profile, render_profile_digest, validate_render_profile
from ..render_profile_evidence import (
    OfficialSourceEvidence,
    RenderProfileSourceEvidence,
    RenderProfileSourceEvidenceEntry,
    ReviewedPolicyDecision,
)
from ..render_profile_loading import load_render_profile
from ..render_profile_model import RenderProfile
from ..render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from ..render_profile_rules import RenderProfileFragment, SingletonNumericRule, Width17MembershipRule
from ..semantic_map import SemanticMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DESIGN_EPOCH = str(filing_year_envelope().horizon)
_SOURCE_REF = f"aeat-dr-200-{_DESIGN_EPOCH}"


def render_profile_anchor(row: int) -> RenderProfileAnchor:
    return RenderProfileAnchor(
        sheet="DP200001",
        source_row=row,
        source_cell=f"A{row}",
        ordinal=str(row - 9),
        record_identity="DP200001",
    )


def design_identity(*, sha256: str = "a" * 64) -> RenderProfileDesignIdentity:
    return RenderProfileDesignIdentity(
        modelo="200",
        design_epoch=_DESIGN_EPOCH,
        source_ref=_SOURCE_REF,
        source_sha256=sha256,
    )


def _intermediate(*, smaller_content: str | None = None, smaller_length: int = 2) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": _SOURCE_REF,
                "source_sha256": "a" * 64,
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": _DESIGN_EPOCH,
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
            "design_epoch": _DESIGN_EPOCH,
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
                    "source_refs": (_SOURCE_REF,),
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


def width_rule(aeat_type: str, anchor: RenderProfileAnchor) -> Width17MembershipRule:
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


def singleton(anchor: RenderProfileAnchor) -> SingletonNumericRule:
    return SingletonNumericRule(
        rule_kind="singleton_numeric",
        anchor=anchor,
        aeat_type="Num",
        semantic_kind="digit_string",
        value_policy=ExportValuePolicy.DIGIT_STRING,
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


def render_profile() -> RenderProfile:
    return RenderProfile(
        schema_version=1,
        design_identity=design_identity(),
        fragment_ids=("width-17", "smaller-fields"),
        width_17_rules=(
            width_rule("Num", render_profile_anchor(10)),
            width_rule("N", render_profile_anchor(11)),
        ),
        singleton_rules=(singleton(render_profile_anchor(12)),),
    )


def _source_evidence() -> RenderProfileSourceEvidence:
    return RenderProfileSourceEvidence(
        design_identity=design_identity(),
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
    profile = render_profile()
    validate_render_profile(profile, _joined(), _source_evidence())

    assert profile.width_17_rules[0].sign_policy == "unsigned"
    assert profile.width_17_rules[1].sign_policy == "n-prefix-negative-blank-nonnegative"
    evidence = profile.singleton_rules[0].evidence
    assert isinstance(evidence, OfficialSourceEvidence)
    assert evidence.source_cell == profile.singleton_rules[0].anchor.source_cell


def test_singleton_rules_consume_the_public_closed_value_policy_axis() -> None:
    profile = render_profile()

    assert all(isinstance(rule.value_policy, ExportValuePolicy) for rule in profile.singleton_rules)
    source = Path("dev/registry/pipeline/render_profile.py").read_text(encoding="utf-8")
    assert "SingletonValuePolicy" not in source
    assert "BeforeValidator(coerce_export_value_policy)" not in source


def test_render_profile_digest_is_order_independent_and_evidence_sensitive() -> None:
    profile = render_profile()
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
    production_paths = tuple(
        path
        for path in scan_directory(Path(__file__).parents[2] / "pipeline", pattern="*.py")
        if not path.name.startswith("test_")
    )
    class_homes: dict[str, list[str]] = {"RenderProfile": [], "ExportTreeTransportProfile": []}
    for path in production_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in class_homes:
                class_homes[node.name].append(path.name)
        assert "ExportRenderProfile" not in path.read_text(encoding="utf-8")

    assert class_homes == {
        "RenderProfile": ["render_profile_model.py"],
        "ExportTreeTransportProfile": ["export_tree_models.py"],
    }


def test_fragment_toml_refuses_a_missing_required_value_policy(tmp_path: Path) -> None:
    fragment = RenderProfileFragment(
        schema_version=1,
        fragment_id="missing-policy",
        design_identity=design_identity(),
        width_17_rules=(),
        singleton_rules=(singleton(render_profile_anchor(12)),),
    )
    source = _fragment_toml(fragment)
    assert 'value_policy = "digit-string"\n' in source
    (tmp_path / "0001.toml").write_text(
        source.replace('value_policy = "digit-string"\n', "", 1),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="value_policy"):
        load_render_profile(tmp_path)


def test_empty_rules_fragment_refusal_never_carries_a_sibling_fields_value(tmp_path: Path) -> None:
    """The fragment-level ``ValidationError`` site must never echo an unrelated field.

    ``RenderProfileFragment._require_authored_rules`` is a model-level
    validator: when it raises, pydantic's ``str(ValidationError)`` embeds an
    ``input_value=`` repr of the WHOLE fragment dict, not just the fields the
    validator inspected. Reproduced here with an authored-but-empty fragment
    (no width-17 or singleton rules) whose ``fragment_id`` -- a field the
    validator never looks at -- carries a short, easy-to-miss value; that
    value is proven present in the raw ``ValidationError`` before
    :func:`load_render_profile` ever sees it, going through the exact
    rtoml-load-then-JSON-validate pipeline the loader itself uses.
    """
    for secret in ("zz", "nif-z"):
        toml_text = (
            "schema_version = 1\n"
            "width_17_rules = []\n"
            "singleton_rules = []\n"
            f'design_identity = {{ modelo = "200", design_epoch = "{_DESIGN_EPOCH}", '
            f'source_ref = "{_SOURCE_REF}", source_sha256 = "{"a" * 64}" }}\n'
            # Inserted last so pydantic's length-truncated repr of the whole
            # payload keeps this field in its surviving tail rather than
            # eliding it -- measured against this exact field ordering, not
            # assumed.
            f'fragment_id = "{secret}"\n'
        )

        with pytest.raises(ValidationError) as raw_excinfo:
            RenderProfileFragment.model_validate_json(json.dumps(rtoml.load(toml_text)))
        assert secret in str(raw_excinfo.value), "premise: the raw ValidationError must actually carry the secret"

        (tmp_path / "0001.toml").write_text(toml_text, encoding="utf-8")
        with pytest.raises(RegistryValidationError) as excinfo:
            load_render_profile(tmp_path)

        message = str(excinfo.value)
        assert secret not in message
        assert "input_value" not in message
        assert "errors.pydantic.dev" not in message
        assert "requires rules or an exclusive empty eligibility assertion" in message


@pytest.mark.parametrize(
    ("profile", "joined", "error"),
    (
        (
            render_profile().model_copy(update={"design_identity": design_identity(sha256="b" * 64)}),
            _joined(),
            "identity",
        ),
        (
            render_profile().model_copy(update={"singleton_rules": ()}),
            _joined(),
            "cover exactly",
        ),
        (
            render_profile().model_copy(
                update={
                    "singleton_rules": (singleton(render_profile_anchor(12)), singleton(render_profile_anchor(12)))
                },
            ),
            _joined(),
            "duplicate or overlapping",
        ),
        (render_profile(), _joined(_intermediate(smaller_content="2 enteros")), "cover exactly"),
        (render_profile(), _joined().model_copy(update={"modelo": "303"}), "identity"),
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
    profile = render_profile()
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
        update={"design_identity": design_identity(sha256="b" * 64)},
    )
    with pytest.raises(RegistryValidationError, match=r"source evidence.*identity"):
        validate_render_profile(render_profile(), _joined(), drifted)


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
    anchor_payload = render_profile_anchor(12).model_dump(mode="python")
    del anchor_payload["source_cell"]
    omitted_cell = RenderProfileAnchor.model_validate(anchor_payload)
    assert omitted_cell.source_cell is None

    anchor_payload = render_profile_anchor(12).model_dump(mode="python")
    del anchor_payload["source_row"]
    with pytest.raises(ValidationError, match="source_row"):
        RenderProfileAnchor.model_validate(anchor_payload)

    anchor_payload = render_profile_anchor(12).model_dump(mode="python")
    del anchor_payload["ordinal"]
    with pytest.raises(ValidationError, match="ordinal"):
        RenderProfileAnchor.model_validate(anchor_payload)

    singleton_payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
    del singleton_payload["semantic_kind"]
    with pytest.raises(ValidationError, match="semantic_kind"):
        SingletonNumericRule.model_validate(singleton_payload)

    singleton_payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
    del singleton_payload["value_policy"]
    with pytest.raises(ValidationError, match="value_policy"):
        SingletonNumericRule.model_validate(singleton_payload)

    singleton_payload["value_policy"] = None
    with pytest.raises(ValidationError, match="value_policy"):
        SingletonNumericRule.model_validate(singleton_payload)

    selector_payload = singleton(render_profile_anchor(12)).model_dump(mode="python") | {"selector": "Num:2"}
    with pytest.raises(ValidationError, match="selector"):
        SingletonNumericRule.model_validate(selector_payload)

    signed_payload = width_rule("N", render_profile_anchor(11)).model_dump(mode="python")
    signed_payload["sign_policy"] = "unsigned"
    with pytest.raises(ValidationError, match="sign policy"):
        Width17MembershipRule.model_validate(signed_payload)

    unsigned_payload = width_rule("Num", render_profile_anchor(10)).model_dump(mode="python")
    unsigned_payload["integer_digits"] = 14
    with pytest.raises(ValidationError, match="sign policy"):
        Width17MembershipRule.model_validate(unsigned_payload)

    policy_payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
    policy_payload["semantic_kind"] = "checkbox"
    policy_payload["value_policy"] = "selected-1-unselected-0"
    policy_payload["integer_digits"] = 1
    policy_payload["allowed_values"] = ("0", "1")
    policy_payload["evidence"] = {
        "authority_kind": "reviewed_policy",
        "decision_id": "m200-2025-dp200001-r0012",
        "governed_anchor": render_profile_anchor(13),
        "decision_statement": "Encode selected as 1 and absent or unselected as 0.",
        "justification": "Reviewed exact-anchor decision, not official-source text.",
    }
    with pytest.raises(ValidationError, match="exact governed anchor"):
        SingletonNumericRule.model_validate(policy_payload)

    policy_payload["evidence"]["governed_anchor"] = render_profile_anchor(12)
    policy_payload["value_policy"] = "enumerated-digits"
    with pytest.raises(ValidationError, match="selected-1-unselected-0"):
        SingletonNumericRule.model_validate(policy_payload)


def _membership_policy_evidence() -> dict[str, object]:
    return {
        "authority_kind": "reviewed_policy",
        "decision_id": "m200-2025-width17-num-amount-representation",
        "decision_statement": "Every width-17 Num amount slot carries fifteen integer positions and two decimals.",
        "justification": "The official design states type, alignment and padding but never the decimal split.",
    }


def test_width_17_membership_accepts_a_reviewed_policy_over_its_anchor_enumeration() -> None:
    """A membership rule may rest on reviewed policy, governing its own anchors.

    An official design that states an amount type, its alignment and its sign but
    never its integer/decimal split cannot ground that split.  Requiring
    official-source evidence here would force the split's reviewed inference to
    be labelled as quoted official text, asserting an authority the quoted
    statement does not carry.
    """
    payload = width_rule("Num", render_profile_anchor(10)).model_dump(mode="python")
    payload["evidence"] = _membership_policy_evidence()
    rule = Width17MembershipRule.model_validate(payload)
    evidence = rule.evidence
    assert isinstance(evidence, ReviewedPolicyDecision)
    assert evidence.governed_anchor is None
    assert rule.anchors == (render_profile_anchor(10),)


def test_width_17_membership_policy_refuses_a_named_governed_anchor() -> None:
    """A membership decision governs the rule's enumeration, never one anchor."""
    payload = width_rule("N", render_profile_anchor(11)).model_dump(mode="python")
    payload["evidence"] = _membership_policy_evidence() | {
        "decision_id": "m200-2025-width17-n-amount-representation",
        "governed_anchor": render_profile_anchor(11),
    }
    with pytest.raises(ValidationError, match="anchor enumeration"):
        Width17MembershipRule.model_validate(payload)


def test_singleton_policy_refuses_an_omitted_governed_anchor() -> None:
    """A singleton decision must still name the exact anchor it governs."""
    payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
    payload["evidence"] = _membership_policy_evidence() | {
        "decision_id": "m200-2025-dp200001-r0012",
    }
    with pytest.raises(ValidationError, match="exact governed anchor"):
        SingletonNumericRule.model_validate(payload)


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
    payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
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
    payload = singleton(render_profile_anchor(12)).model_dump(mode="python")
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
        singleton(render_profile_anchor(12)).model_dump(mode="python")
        | {
            "semantic_kind": semantic_kind,
            "value_policy": policy,
            "integer_digits": integer_digits,
            "decimal_digits": decimal_digits,
            "allowed_values": allowed_values,
        },
    )

    derivation = export_field_render_profile_derivation.profile_singleton_derivation(
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
    # Sign bytes are source-printed semantic parts, governed by the signed
    # component route rather than a numeric singleton profile rule.
    signed_part_only = {ExportValuePolicy.SIGNED_COMPONENT_SIGN, ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN}
    assert not set(export_field_render_profile_derivation.SINGLETON_POLICY_SHAPES) & signed_part_only
    assert set(export_field_render_profile_derivation.SINGLETON_POLICY_SHAPES) | signed_part_only == set(
        ExportValuePolicy
    )


def test_source_part_sign_policies_project_and_refuse_their_distinct_wire_domains() -> None:
    assert project_export_value(ExportValuePolicy.SIGNED_COMPONENT_SIGN, "-1") == "N"
    assert project_export_value(ExportValuePolicy.SIGNED_COMPONENT_SIGN, "1") == " "
    assert project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, "-1") == "N"
    assert project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, "0") == "0"
    for policy, accepted in (
        (ExportValuePolicy.SIGNED_COMPONENT_SIGN, ("N", " ")),
        (ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, ("N", "0")),
    ):
        for wire in accepted:
            validate_export_wire_value(policy, wire)
        for refused in {"N", " ", "0"} - set(accepted):
            with pytest.raises(RegistryValidationError):
                validate_export_wire_value(policy, refused)
    with pytest.raises(RegistryValidationError, match="cannot encode a positive amount"):
        project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, "1")


def test_fragment_loader_compiles_by_filename_and_refuses_fragment_identity_drift(tmp_path: Path) -> None:
    """Fragmentation changes review size only; compilation order and identity stay deterministic."""
    profile = render_profile()
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

    drifted = smaller.model_copy(update={"design_identity": design_identity(sha256="b" * 64)})
    (tmp_path / "0300-smaller.toml").write_text(_fragment_toml(drifted), encoding="utf-8")
    with pytest.raises(RegistryValidationError, match="inapplicable design identities"):
        load_and_validate_render_profile(tmp_path, _joined(), _source_evidence())


def test_profile_loader_refuses_legacy_or_non_profile_siblings(tmp_path: Path) -> None:
    """A profile directory is an exhaustive authority set, never a tolerant legacy container."""
    profile = render_profile()
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
    profile = render_profile()
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
    unknown_rule = singleton(unknown).model_copy(
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
    profile = render_profile().model_copy(update={"singleton_rules": (unknown_rule,)})

    with pytest.raises(RegistryValidationError, match="unknown="):
        validate_render_profile(profile, _joined(), _source_evidence())

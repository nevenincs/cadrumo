"""Reviewed unsplit signed monetary composites stay source-pinned and fail closed."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    parse_fixed_width_export_field,
    render_fixed_width_export_field,
)

from ..compiler.loader import load_catalogue_file
from . import _export_tree
from .joined_record_design import JoinedRecordDesignField
from .record_design_intermediate import RecordDesignIntermediateField, load_record_design_intermediate
from .render_profile import (
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    ReviewedPolicyDecision,
    SignedMonetaryCompositeRule,
    SingletonNumericRule,
    SourceStatedCompositeEvidence,
    load_render_profile,
    render_profile_digest,
    validate_render_profile_authority,
)
from .render_profile_eligibility import RenderProfileEligibility, project_render_profile_eligibility
from .semantic_map import SemanticMapEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_CONTENT = (
    "Se consignará la suma algebraica total. Este campo se subdivide en: "
    "145 SIGNO: Alfabético. Se cumplimentará cuando el resultado anteriormente mencionado sea menor de 0 "
    '(cero). En este caso se consignará una "N", en cualquier otro caso el contenido de este campo será un '
    "espacio. 146-159 IMPORTE: Campo numérico de 14 posiciones. Se consignará sin signo y sin coma decimal, "
    "el importe mencionado anteriormente. Este campo se subdivide en dos: 146-157 Parte entera del importe, "
    "si no tiene contenido se consignará a ceros. 158-159 Parte decimal del importe, si no tiene contenido se "
    "consignará a ceros."
)


def _anchor() -> RenderProfileAnchor:
    return RenderProfileAnchor(
        sheet="PDF record design",
        source_row=177,
        ordinal="12",
        record_identity="PDF record design",
    )


def _identity() -> RenderProfileDesignIdentity:
    return RenderProfileDesignIdentity(
        modelo="296",
        design_epoch="2024",
        source_ref="aeat-dr-296-2024",
        source_sha256="abec12e56073f8325b159c45a6b25de713bd53f8315c26c0f5243024f00d0378",
    )


def _rule(**updates: object) -> SignedMonetaryCompositeRule:
    anchor = _anchor()
    payload: dict[str, object] = {
        "rule_kind": "signed_monetary_composite",
        "integer_digits": 12,
        "decimal_digits": 2,
        "sign_policy": "blank-or-n-leading",
        "anchor": anchor,
        "evidence": SourceStatedCompositeEvidence(
            authority_kind="official_parser_anchor",
            governed_anchor=anchor,
            decision_statement="The source states the complete signed monetary composite.",
            justification="Every clause is checked against this exact parser anchor.",
        ),
    }
    payload.update(updates)
    return SignedMonetaryCompositeRule.model_validate(payload)


def _profile(rule: SignedMonetaryCompositeRule | None = None) -> RenderProfile:
    return RenderProfile(
        schema_version=1,
        design_identity=_identity(),
        fragment_ids=("signed-composite",),
        width_17_rules=(),
        singleton_rules=(),
        signed_composite_rules=(rule or _rule(),),
    )


def _field(*, content: str = _SOURCE_CONTENT, **updates: object) -> RecordDesignIntermediateField:
    payload: dict[str, object] = {
        "sheet": "PDF record design",
        "record_identity": "PDF record design",
        "source_row": 177,
        "source_cell": None,
        "ordinal": "12",
        "offset": 145,
        "length": 15,
        "aeat_type": "Alfanumérico",
        "normalized_description": "BASE RETENCIONES E INGRESOS A CUENTA",
        "validation": None,
        "content": content,
    }
    payload.update(updates)
    return RecordDesignIntermediateField.model_validate(payload)


def _eligibility(field: RecordDesignIntermediateField) -> RenderProfileEligibility:
    anchor = _anchor()
    return project_render_profile_eligibility(
        (field,),
        signed_composite_anchor_keys=frozenset(
            ((anchor.sheet, anchor.source_row, anchor.source_cell, anchor.ordinal, anchor.record_identity),)
        ),
    )


def _validate(field: RecordDesignIntermediateField, profile: RenderProfile | None = None) -> None:
    validate_render_profile_authority(
        profile or _profile(),
        _identity(),
        _eligibility(field),
        RenderProfileSourceEvidence(design_identity=_identity(), entries=()),
    )


def _joined_field(field: RecordDesignIntermediateField) -> JoinedRecordDesignField:
    entry = SemanticMapEntry.model_validate(
        {
            "anchor": _anchor().model_dump(mode="json"),
            "export_field_id": "m296-2024.declarante.f013",
            "kind": CasillaFieldKind.CASILLA,
            "casilla_id": "02",
            "legal_refs": ("trlirnr-rdleg-5-2004:art-24",),
            "source_refs": ("aeat-dr-296-2024",),
        }
    )
    return JoinedRecordDesignField(parser_field=field, semantic_entry=entry)


def test_reviewed_definition_accepts_normalised_prose_case_but_preserves_wire_token_case() -> None:
    content = _SOURCE_CONTENT.lower().replace('una "n"', 'una "N"')
    _validate(_field(content=content))


def test_reviewed_composite_projects_through_existing_money_codec_and_distinct_provenance() -> None:
    field = _field()
    profile = _profile()
    _validate(field, profile)

    derived = _export_tree._normalise_cell(  # pyright: ignore[reportPrivateUsage]
        _joined_field(field),
        _export_tree.ExportTreeTransportProfile(
            modelo="296",
            design_epoch="2024",
            source_ref="aeat-dr-296-2024",
            source_sha256=_identity().source_sha256,
            layout_id="generated-modelo-296-fichero",
            format="fixed_width",
            encoding=ExportEncoding.ISO_8859_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        ),
        profile,
        export_record_id="m296-declarante",
    )

    assert derived.derivation_code == "render-profile-signed-monetary-composite-v1"
    assert derived.parser_field.aeat_type == "Alfanumérico"
    assert derived.field.sign_position is not None
    assert (
        derived.field.data_type,
        derived.field.length,
        derived.field.padding.value,
        derived.field.justification.value,
        derived.field.signed,
        derived.field.sign_position.value,
    ) == ("money", 15, "left_zero", "right", True, "blank_or_n")
    cases = (
        (Decimal("1234.56"), " " + "123456".rjust(14, "0")),
        (Decimal("-1234.56"), "N" + "123456".rjust(14, "0")),
        (Decimal(0), " " + "0" * 14),
        (None, " " + "0" * 14),
        (Decimal("999999999999.99"), " 99999999999999"),
    )
    for value, wire in cases:
        assert render_fixed_width_export_field(derived.field, value) == wire
        if value is not None:
            assert parse_fixed_width_export_field(derived.field, wire) == value
    with pytest.raises(RegistryValidationError, match="exceeds length"):
        render_fixed_width_export_field(derived.field, Decimal("1000000000000.00"))
    with pytest.raises(RegistryValidationError, match="'N' or a space"):
        parse_fixed_width_export_field(derived.field, "0" * 15)


@pytest.mark.parametrize(
    "content",
    (
        _SOURCE_CONTENT.replace("145 SIGNO:", "146 SIGNO:"),
        _SOURCE_CONTENT.replace("146-159 IMPORTE", "146-158 IMPORTE"),
        _SOURCE_CONTENT.replace("14 posiciones", "13 posiciones"),
        _SOURCE_CONTENT.replace("146-157 Parte entera", "146-156 Parte entera"),
        _SOURCE_CONTENT.replace("158-159 Parte decimal", "157-159 Parte decimal"),
        _SOURCE_CONTENT.replace("158-159 Parte decimal", "159-159 Parte decimal"),
        _SOURCE_CONTENT.replace('una "N"', 'un "M"'),
        _SOURCE_CONTENT.replace("SIGNO: Alfabético", "SIGNO: Numérico"),
        _SOURCE_CONTENT.replace('una "N"', 'una "n"'),
        _SOURCE_CONTENT.replace("sea menor de 0", "sea NO menor de 0"),
        _SOURCE_CONTENT.replace("sin signo y sin coma decimal", "con signo y con coma decimal"),
        _SOURCE_CONTENT.replace("sin signo y sin coma decimal", "sin signo y con coma decimal"),
        _SOURCE_CONTENT + " 145 SIGNO:",
        _SOURCE_CONTENT + ' En cualquier otro caso se consignará una "N".',
        "Se consignará con signo y con coma decimal. " + _SOURCE_CONTENT,
        _SOURCE_CONTENT.replace(
            "un espacio. 146-159 IMPORTE",
            "un espacio. Se consignará con signo y con coma decimal. 146-159 IMPORTE",
        ),
        _SOURCE_CONTENT + " Se consignará con signo y con coma decimal.",
        _SOURCE_CONTENT.replace(
            "Campo numérico de 14 posiciones.",
            "Campo numérico de 14 posiciones. Se consignarán 15 dígitos.",
        ),
        _SOURCE_CONTENT + " La parte decimal tendrá tres posiciones.",
        "Nombre y apellidos del declarante.",
        "",
    ),
)
def test_incomplete_drifted_duplicate_or_contradictory_claimed_composite_refuses_without_text_fallback(
    content: str,
) -> None:
    with pytest.raises(RegistryValidationError, match="signed monetary composite"):
        _validate(_field(content=content))


def test_rule_shape_anchor_and_source_identity_are_closed_and_digest_is_deterministic() -> None:
    with pytest.raises(ValueError, match="exact governed anchor"):
        _rule(
            evidence=SourceStatedCompositeEvidence(
                authority_kind="official_parser_anchor",
                governed_anchor=_anchor().model_copy(update={"source_row": 178}),
                decision_statement="Source statement.",
                justification="Exact anchor proof.",
            )
        )
    with pytest.raises(RegistryValidationError, match="identity"):
        validate_render_profile_authority(
            _profile(),
            _identity().model_copy(update={"source_sha256": "b" * 64}),
            _eligibility(_field()),
            RenderProfileSourceEvidence(design_identity=_identity(), entries=()),
        )
    evidence = RenderProfileSourceEvidence(design_identity=_identity(), entries=())
    assert render_profile_digest(_profile(), evidence) == render_profile_digest(_profile(), evidence)


def test_one_anchor_cannot_claim_both_ordinary_numeric_and_signed_composite_ownership() -> None:
    anchor = _anchor()
    ordinary = SingletonNumericRule(
        rule_kind="singleton_numeric",
        aeat_type="Num",
        semantic_kind="integer",
        value_policy=ExportValuePolicy.UNSIGNED_INTEGER,
        integer_digits=15,
        decimal_digits=0,
        sign_policy="unsigned",
        allowed_values=(),
        anchor=anchor,
        evidence=ReviewedPolicyDecision(
            authority_kind="reviewed_policy",
            decision_id="conflicting-ordinary-owner",
            governed_anchor=anchor,
            decision_statement="Planted conflicting ordinary ownership.",
            justification="Detector control only.",
        ),
    )
    conflicting = _profile().model_copy(update={"singleton_rules": (ordinary,)})

    with pytest.raises(RegistryValidationError, match="duplicate or overlapping exact anchors"):
        _validate(_field(), conflicting)


def test_profiles_without_composites_retain_the_pre_extension_digest_representation() -> None:
    profile = RenderProfile(
        schema_version=1,
        design_identity=_identity(),
        fragment_ids=(),
        width_17_rules=(),
        singleton_rules=(),
    )
    evidence = RenderProfileSourceEvidence(design_identity=_identity(), entries=())
    legacy_payload: dict[str, object] = {
        "schema_version": 1,
        "design_identity": _identity().model_dump(mode="json"),
        "fragment_ids": [],
        "width_17_rules": [],
        "singleton_rules": [],
        "source_evidence": {
            "design_identity": _identity().model_dump(mode="json"),
            "entries": [],
        },
    }

    assert render_profile_digest(profile, evidence) == content_hash_hex(legacy_payload)


def test_committed_modelo_296_profile_enrols_the_exact_hash_verified_parser_anchor() -> None:
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "irnr.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-296-2024",
        filing_year=2024,
        design_epoch="2024",
    )
    profile = load_render_profile(Path(__file__).parents[1] / "render_profiles/modelo_296/2024")
    fields = tuple(field for sheet in intermediate.sheets for field in sheet.fields)
    field = next(
        field
        for field in fields
        if (field.sheet, field.source_row, field.ordinal, field.record_identity)
        == ("PDF record design", 177, "12", "PDF record design")
    )
    composite_keys = frozenset(
        (
            rule.anchor.sheet,
            rule.anchor.source_row,
            rule.anchor.source_cell,
            rule.anchor.ordinal,
            rule.anchor.record_identity,
        )
        for rule in profile.signed_composite_rules
    )
    eligibility = project_render_profile_eligibility(
        fields,
        signed_composite_anchor_keys=composite_keys,
    )
    validate_render_profile_authority(
        profile,
        _identity(),
        eligibility,
        RenderProfileSourceEvidence(design_identity=_identity(), entries=()),
    )
    rendered = _export_tree._normalise_cell(  # pyright: ignore[reportPrivateUsage]
        _joined_field(field),
        _export_tree.ExportTreeTransportProfile(
            modelo="296",
            design_epoch="2024",
            source_ref="aeat-dr-296-2024",
            source_sha256=_identity().source_sha256,
            layout_id="generated-modelo-296-fichero",
            format="fixed_width",
            encoding=ExportEncoding.ISO_8859_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        ),
        profile,
        export_record_id="m296-declarante",
    )
    assert (rendered.derivation_code, rendered.field.data_type, rendered.field.sign_position) == (
        "render-profile-signed-monetary-composite-v1",
        "money",
        "blank_or_n",
    )
    assert tuple(
        (rule.anchor.source_row, rule.integer_digits, rule.decimal_digits) for rule in profile.signed_composite_rules
    ) == ((177, 12, 2),)

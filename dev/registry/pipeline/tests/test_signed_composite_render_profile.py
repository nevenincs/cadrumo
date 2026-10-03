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
    render_fixed_width_export_field,
)
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition

from ...compiler.loader import load_catalogue_file
from .. import _export_tree
from ..joined_record_design import JoinedRecordDesignField
from ..record_design_intermediate import RecordDesignIntermediateField, load_record_design_intermediate
from ..render_profile import render_profile_digest
from ..render_profile_authority import _validate_signed_composite_source_agreement, validate_render_profile_authority
from ..render_profile_eligibility import RenderProfileEligibility, project_render_profile_eligibility
from ..render_profile_evidence import RenderProfileSourceEvidence, ReviewedPolicyDecision, SourceStatedCompositeEvidence
from ..render_profile_loading import load_render_profile
from ..render_profile_model import RenderProfile
from ..render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from ..render_profile_rules import SignedMonetaryCompositeRule, SingletonNumericRule
from ..semantic_map import SemanticMap, SemanticMapEntry, load_semantic_map
from ..source_defects import PrintedPartitionDefectDeclaration

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
            (
                (
                    anchor.sheet,
                    anchor.source_row,
                    anchor.source_cell,
                    anchor.ordinal,
                    anchor.record_identity,
                    anchor.semantic_part_offset,
                ),
            )
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
    profile = load_render_profile(Path(__file__).parents[2] / "render_profiles/modelo_296/2024")
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
            rule.anchor.semantic_part_offset,
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


def _m180_composite(
    epoch: str, row: int
) -> tuple[SignedMonetaryCompositeRule, RecordDesignIntermediateField, RenderProfileDesignIdentity]:
    root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "irpf.toml"))
    intermediate = load_record_design_intermediate(
        root,
        catalogues.sources,
        source_ref=f"aeat-dr-180-{epoch}",
        filing_year=int(epoch),
        design_epoch=epoch,
    )
    profile = load_render_profile(Path(__file__).parents[2] / f"render_profiles/modelo_180/{epoch}")
    rule = next(rule for rule in profile.signed_composite_rules if rule.anchor.source_row == row)
    field = next(field for sheet in intermediate.sheets for field in sheet.fields if field.source_row == row)
    return rule, field, profile.design_identity


@pytest.mark.parametrize("epoch, row", (("2014", 116), ("2014", 302), ("2023", 109), ("2023", 292)))
def test_m180_composites_validate_through_the_one_composite_grammar(epoch: str, row: int) -> None:
    rule, field, identity = _m180_composite(epoch, row)
    _validate_signed_composite_source_agreement(rule, field, identity)

    for changed_field in (
        field.model_copy(update={"length": 17}),
        field.model_copy(update={"content": (field.content or "") + " Se consignará con signo y con coma decimal."}),
        field.model_copy(update={"content": (field.content or "").replace("SIGNO:", "SIGNO: Numérico.", 1)}),
    ):
        with pytest.raises(RegistryValidationError, match="signed monetary composite"):
            _validate_signed_composite_source_agreement(rule, changed_field, identity)


@pytest.mark.parametrize("epoch, row", (("2014", 116), ("2023", 109)))
def test_m180_printed_partition_overlap_resolves_only_through_its_pinned_declaration(epoch: str, row: int) -> None:
    rule, field, identity = _m180_composite(epoch, row)
    assert "146-159 Parte entera" in (field.content or "")
    assert "159-160 Parte decimal" in (field.content or "")

    for changed_identity, changed_field in (
        (identity.model_copy(update={"source_sha256": "0" * 64}), field),
        (identity, field.model_copy(update={"source_row": row + 1})),
        (identity, field.model_copy(update={"content": (field.content or "").replace("146-159", "146-157", 1)})),
    ):
        with pytest.raises(RegistryValidationError, match="do not exactly partition"):
            _validate_signed_composite_source_agreement(rule, changed_field, changed_identity)


def test_m180_printed_overlap_renders_signed_limits_losslessly() -> None:
    root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "irpf.toml"))
    intermediate = load_record_design_intermediate(
        root,
        catalogues.sources,
        source_ref="aeat-dr-180-2023",
        filing_year=2023,
        design_epoch="2023",
    )
    profile = load_render_profile(Path(__file__).parents[2] / "render_profiles/modelo_180/2023")
    semantic = load_semantic_map(Path(__file__).parents[2] / "mappings/modelo_180/2023")
    field = next(field for sheet in intermediate.sheets for field in sheet.fields if field.source_row == 109)
    entry = next(entry for entry in semantic.entries if entry.anchor.source_row == 109)
    derived = _export_tree._normalise_cell(  # pyright: ignore[reportPrivateUsage]
        JoinedRecordDesignField(parser_field=field, semantic_entry=entry),
        _export_tree.ExportTreeTransportProfile(
            modelo="180",
            design_epoch="2023",
            source_ref="aeat-dr-180-2023",
            source_sha256=profile.design_identity.source_sha256,
            layout_id="generated-modelo-180-fichero",
            format="fixed_width",
            encoding=ExportEncoding.ISO_8859_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        ),
        profile,
        export_record_id="modelo-180-t1",
    )
    for amount in (Decimal("9999999999999.99"), Decimal("-9999999999999.99"), Decimal("-0.01")):
        wire = render_fixed_width_export_field(derived.field, amount)
        assert len(wire) == 16
        assert wire[0] == ("N" if amount < 0 else " ")
        assert parse_fixed_width_export_field(derived.field, wire) == amount
    with pytest.raises(RegistryValidationError, match="exceeds length"):
        render_fixed_width_export_field(derived.field, Decimal("10000000000000.00"))


_M347_DESIGNS = (("2025", "aeat-dr-347-2025", 2025), ("2011", "aeat-dr-347-2011", 2011))


def _m347_design(
    epoch: str, source_ref: str, filing_year: int
) -> tuple[RenderProfile, tuple[RecordDesignIntermediateField, ...], SemanticMap]:
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "operaciones-terceros.toml"))
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=epoch,
    )
    profile = load_render_profile(Path(__file__).parents[2] / f"render_profiles/modelo_347/{epoch}")
    semantic = load_semantic_map(Path(__file__).parents[2] / f"mappings/modelo_347/{epoch}")
    return profile, tuple(field for sheet in intermediate.sheets for field in sheet.fields), semantic


def _m347_composite_fields(epoch: str, source_ref: str, filing_year: int) -> tuple[ExportFieldDefinition, ...]:
    profile, fields, semantic = _m347_design(epoch, source_ref, filing_year)
    by_row = {field.source_row: field for field in fields}
    entries = {entry.anchor.source_row: entry for entry in semantic.entries}
    transport = _export_tree.ExportTreeTransportProfile(
        modelo="347",
        design_epoch=epoch,
        source_ref=source_ref,
        source_sha256=profile.design_identity.source_sha256,
        layout_id=f"generated-modelo-347-{epoch}-fichero",
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    derived = []
    for rule in profile.signed_composite_rules:
        field = by_row[rule.anchor.source_row]
        _validate_signed_composite_source_agreement(rule, field, profile.design_identity)
        joined = JoinedRecordDesignField(parser_field=field, semantic_entry=entries[rule.anchor.source_row])
        derived.append(_export_tree._normalise_cell(joined, transport, profile, export_record_id="m347-record").field)
    return tuple(derived)


@pytest.mark.parametrize(("epoch", "source_ref", "filing_year"), _M347_DESIGNS)
def test_every_m347_signed_amount_renders_a_blank_or_n_sign_and_thirteen_plus_two_digits(
    epoch: str, source_ref: str, filing_year: int
) -> None:
    """aeat-dr-347-2011/2025: "N" when the amount is below 0, otherwise a space, then 13+2 digits."""
    fields = _m347_composite_fields(epoch, source_ref, filing_year)
    offsets = {field.offset for field in fields}
    assert {83, 116, 136, 145, 152, 168, 184, 200, 216, 232, 248} <= offsets
    if epoch == "2025":
        assert {99, 170, 284} <= offsets
    for field in fields:
        assert field.sign_position is not None
        assert (field.data_type, field.length, field.signed, field.sign_position.value) == (
            "money",
            16,
            True,
            "blank_or_n",
        )
        assert render_fixed_width_export_field(field, Decimal("1234.56")) == " 000000000123456"
        assert render_fixed_width_export_field(field, Decimal("-1234.56")) == "N000000000123456"
        assert render_fixed_width_export_field(field, Decimal(0)) == " 000000000000000"
        assert parse_fixed_width_export_field(field, "N000000000123456") == Decimal("-1234.56")


def test_the_m347_inmueble_amount_is_a_signed_composite_although_its_type_column_prints_numeric() -> None:
    """2025 inmueble pos. 99: '99 SIGNO ... se consignara una "N"' under a 'Numerico' naturaleza."""
    profile, fields, _semantic = _m347_design("2025", "aeat-dr-347-2025", 2025)
    rule = next(rule for rule in profile.signed_composite_rules if rule.anchor.sheet == "Tipo 2 - Registro De Inmueble")
    field = next(field for field in fields if field.source_row == rule.anchor.source_row)
    assert (field.offset, field.aeat_type) == (99, "Numérico")
    assert all(singleton.anchor != rule.anchor for singleton in profile.singleton_rules)


@pytest.mark.parametrize(
    "mutation",
    (
        ("sea menor que 0", "sea mayor que 0"),
        ("84-96 Parte entera", "84-95 Parte entera"),
        ("campo numérico de 15 posiciones", "campo numérico de 14 posiciones"),
        ("En cualquier otro caso el contenido", "En cualquier otro caso se consignará una cifra y el contenido"),
        ("Los importes deben consignarse en EUROS.", "Los importes se consignarán con dos decimales."),
    ),
)
def test_a_m347_amount_with_one_clause_altered_is_refused(mutation: tuple[str, str]) -> None:
    profile, fields, _semantic = _m347_design("2025", "aeat-dr-347-2025", 2025)
    rule = next(rule for rule in profile.signed_composite_rules if rule.anchor.source_row == 349)
    field = next(field for field in fields if field.source_row == 349)
    _validate_signed_composite_source_agreement(rule, field, profile.design_identity)
    original, altered = mutation
    assert original in (field.content or "")
    with pytest.raises(RegistryValidationError, match="signed monetary composite"):
        _validate_signed_composite_source_agreement(
            rule,
            field.model_copy(update={"content": (field.content or "").replace(original, altered, 1)}),
            profile.design_identity,
        )


def test_only_exact_boe_page_furniture_is_removed_before_the_grammar_reads_a_cell() -> None:
    """The 2011 Q3 cell carries a BOE running header mid-cell; a lookalike carrying a wire word is refused."""
    profile, fields, _semantic = _m347_design("2011", "aeat-dr-347-2011", 2011)
    rule = next(rule for rule in profile.signed_composite_rules if rule.anchor.source_row == 637)
    field = next(field for field in fields if field.source_row == 637)
    assert "cve: BOE-A-2011-19397" in (field.content or "")
    _validate_signed_composite_source_agreement(rule, field, profile.design_identity)
    lookalike = (field.content or "").replace("Pág. 132703", "Pág. 132703 con signo")
    with pytest.raises(RegistryValidationError, match="signed monetary composite"):
        _validate_signed_composite_source_agreement(
            rule, field.model_copy(update={"content": lookalike}), profile.design_identity
        )


@pytest.mark.parametrize(
    ("published", "adjudicated"),
    (((146, 159), (147, 158)), ((146, 159), (146, 159)), ((146, 159), (146, 160))),
)
def test_a_printed_partition_declaration_can_only_withdraw_the_overlap(
    published: tuple[int, int], adjudicated: tuple[int, int]
) -> None:
    with pytest.raises(ValueError, match="only withdraws the overlap"):
        PrintedPartitionDefectDeclaration(
            source_ref="aeat-dr-180-2023",
            source_sha256="f" * 64,
            sheet="Tipo 1",
            source_row=109,
            published_integer_range=published,
            adjudicated_integer_range=adjudicated,
            evidence="Detector control.",
        )

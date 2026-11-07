"""The committed render profiles checked exhaustively against their hash-verified AEAT record designs."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_args

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
)

from ...compiler.loader import load_catalogue_file
from ...maintenance_support import resolve_record_design_binary
from ...tests.authored_edition_support import source_first_exercise, source_reference, source_with_sha256
from .. import render_profile, render_profile_eligibility, render_profile_source_reader
from ..record_design_intermediate import (
    RecordDesignIntermediateField,
    load_record_design_intermediate,
)
from ..render_profile_authority import validate_render_profile_authority
from ..render_profile_eligibility import (
    is_source_reserved_field,
    project_render_profile_eligibility,
)
from ..render_profile_evidence import (
    OfficialSourceEvidence,
    ReviewedPolicyDecision,
)
from ..render_profile_loading import WIDTH_17_TYPE_ORDER, load_render_profile
from ..render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from ..render_profile_rules import Width17MembershipRule
from ..render_profile_source_reader import load_render_profile_source_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_M200_SOURCE = "aeat-dr-200-2025"
_M200_EXERCISE = source_first_exercise(source_reference(_M200_SOURCE))
_M200_PROFILES = Path(__file__).parents[2] / "render_profiles" / "modelo_200"


def _exercise(source_ref: str) -> int:
    """Return the first exercise one catalogued design covers, which is also its design epoch."""
    return source_first_exercise(source_reference(source_ref))


#: Floors for the live modelo 200 eligibility this coverage test equates against
#: the shipped profile. Live: 5682 fields, of which 5556 are width-17 and 126
#: are smaller.
_MINIMUM_M200_ELIGIBLE_FIELDS = 4000
_MINIMUM_M200_SMALLER_FIELDS = 80


def _load_validated_m200_profile():
    """Load the committed Modelo 200 profile, validating it against the hash-verified source."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=_M200_SOURCE,
        filing_year=_M200_EXERCISE,
        design_epoch=str(_M200_EXERCISE),
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
        source_ref=_M200_SOURCE,
        filing_year=_M200_EXERCISE,
        design_epoch=str(_M200_EXERCISE),
    )
    profile_directory = _M200_PROFILES / str(_M200_EXERCISE)
    profile = load_render_profile(profile_directory)
    evidence = load_render_profile_source_evidence(resolved.path, profile)
    validate_render_profile_authority(profile, design_identity, eligibility, evidence)
    return intermediate, eligibility, profile


def _assert_m200_width_rules(profile) -> None:
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


def _assert_m200_eligibility_is_not_vacuous(eligibility) -> None:
    # Every coverage claim below equates two sets DERIVED from this one
    # eligibility, so each holds when both sides are empty. This module's own
    # sibling records that exact incident: with no eligible field, an empty
    # render profile satisfied exhaustive coverage completely. The split is
    # lopsided -- 5556 width-17 against 126 smaller -- so a single total would
    # sit clear while the smaller branch, which the singleton equality covers,
    # emptied entirely.
    assert len(eligibility.all_fields) >= _MINIMUM_M200_ELIGIBLE_FIELDS, (
        f"modelo 200 projected {len(eligibility.all_fields)} eligible field(s); the "
        "coverage equalities below compare two empty sets and pass"
    )
    assert len(eligibility.smaller_fields) >= _MINIMUM_M200_SMALLER_FIELDS, (
        f"only {len(eligibility.smaller_fields)} smaller field(s) of "
        f"{len(eligibility.all_fields)}; the singleton-rule equality below is over this "
        "branch alone, and the width-17 majority keeps any total floor clear"
    )


def _assert_m200_rules_cover_exactly_the_eligible_anchors(intermediate, eligibility, profile) -> None:
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


def _assert_m200_semantic_singleton_rules(profile) -> None:
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


def test_real_m200_profile_exactly_covers_source_eligibility_and_excludes_variable_envelope() -> None:
    """The committed profile validates exhaustively against the hash-verified source."""
    intermediate, eligibility, profile = _load_validated_m200_profile()
    _assert_m200_width_rules(profile)
    _assert_m200_eligibility_is_not_vacuous(eligibility)
    _assert_m200_rules_cover_exactly_the_eligible_anchors(intermediate, eligibility, profile)
    _assert_m200_semantic_singleton_rules(profile)


#: The pinned Modelo 390 design whose committed render profile is checked, found by
#: its bytes; its applicability names the exercise and the profile directory.
_M390_PINNED_DESIGN = source_with_sha256("7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe")
_M390_PINNED_PROFILE_EXERCISE = source_first_exercise(_M390_PINNED_DESIGN)


def test_real_m390_pinned_profile_exactly_covers_source_eligibility_and_binds_day_first_dates() -> None:
    """The pinned M390 profile binds all nine blank numeric fields to its pinned source."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    intermediate = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=_M390_PINNED_DESIGN.id,
        filing_year=_M390_PINNED_PROFILE_EXERCISE,
        design_epoch=str(_M390_PINNED_PROFILE_EXERCISE),
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
        source_ref=_M390_PINNED_DESIGN.id,
        filing_year=_M390_PINNED_PROFILE_EXERCISE,
        design_epoch=str(_M390_PINNED_PROFILE_EXERCISE),
    )
    profile_directory = (
        Path(__file__).parents[2] / "render_profiles" / "modelo_390" / str(_M390_PINNED_PROFILE_EXERCISE)
    )
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


def _first_blank_in_range_cell(source_path: Path, sheet_name: str) -> str:
    """Return an A1 cell inside ``sheet_name``'s used range that holds no text.

    The blank-cell guard needs a locator the reader can resolve but that carries
    no statement. Hardcoding one would pin the test to today's design, so the
    cell is discovered through the same reader the loader uses.
    """
    import xlrd

    book = xlrd.open_workbook(str(source_path), on_demand=True)
    try:
        sheet = book.sheet_by_name(sheet_name)
        for row in range(sheet.nrows):
            for col in range(sheet.ncols):
                if not str(sheet.cell_value(row, col)).strip():
                    column = ""
                    index = col
                    while True:
                        column = chr(ord("A") + index % 26) + column
                        index = index // 26 - 1
                        if index < 0:
                            break
                    return f"{column}{row + 1}"
    finally:
        book.release_resources()
    raise AssertionError(f"no blank cell inside {sheet_name!r}; the guard cannot be exercised")


def test_real_source_loader_refuses_nonexistent_cell_statement_and_sha_mutations() -> None:
    """Source claims resolve from the binary and every identity or text drift fails closed."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=_M200_SOURCE,
        filing_year=_M200_EXERCISE,
        design_epoch=str(_M200_EXERCISE),
    )
    profile = load_render_profile(
        _M200_PROFILES / str(_M200_EXERCISE),
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
    # Z999 is OUTSIDE the workbook's used range, so the refusal names the missing
    # locator. It read as "does not contain source text" only while this design
    # was a .xlsx whose declared dimensions happened to cover Z999 and returned
    # an empty cell; registering the bundled designs repointed it to the real
    # .xls, where the range is genuinely smaller.
    with pytest.raises(RegistryValidationError, match="locator does not exist"):
        load_render_profile_source_evidence(resolved.path, missing_profile)

    # The blank-but-present branch is a DIFFERENT guard, and this is its only
    # coverage: a locator inside the used range whose cell carries no statement.
    # Probed rather than hardcoded so it survives a design revision.
    blank_cell = _first_blank_in_range_cell(resolved.path, first_rule.evidence.source_sheet)
    blank_rule = first_rule.model_copy(
        update={"evidence": first_rule.evidence.model_copy(update={"source_cell": blank_cell})},
    )
    blank_profile = profile.model_copy(
        update={"width_17_rules": (blank_rule, profile.width_17_rules[1])},
    )
    with pytest.raises(RegistryValidationError, match="does not contain source text"):
        load_render_profile_source_evidence(resolved.path, blank_profile)

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
            source_ref=_M200_SOURCE,
            filing_year=_M200_EXERCISE,
            design_epoch=str(_M200_EXERCISE),
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
        source_ref=_M200_SOURCE,
        filing_year=_M200_EXERCISE,
        design_epoch=str(_M200_EXERCISE),
    )
    profile = load_render_profile(
        _M200_PROFILES / str(_M200_EXERCISE),
    )
    linked_source = tmp_path / resolved.path.name
    linked_source.symlink_to(resolved.path)

    with pytest.raises(RegistryValidationError, match="regular file"):
        load_render_profile_source_evidence(linked_source, profile)


def test_profile_authority_has_no_legacy_tree_or_layout_oracle() -> None:
    """The authority depends only on parser IR and exact joined source facts.

    The set is an ALLOW-LIST, not a record of what the module happens to import:
    what it forbids is this authority reaching a generated tree, an export
    layout, or any other downstream artefact to decide what a field's wire
    representation is. Eligibility must be answerable from the official design
    the parser read and the reviewed declarations pinned to that exact design,
    or the render profile stops being the thing that states an absent wire fact
    and starts inferring it from what was already generated.

    The eligibility contract -- its projection, its predicates and the resolver
    that pins a source's declarations to it -- lives in the public
    ``render_profile_eligibility`` module, because consumers outside this package
    must ask it and an underscore-private module is not a cross-package API. The
    allow-list therefore covers BOTH modules: moving the projection out of the
    authority must not move it out of the reach of this gate.

    ``source_defects`` is admitted on the eligibility module, not by accretion:
    it carries the adjudicated declarations ABOUT the same pinned source -- which
    notes state applicability rather than format, and which amounts a read note
    governs -- and the resolver validates each against that source's own digest
    before projecting. It is source-side evidence, not a tree or layout oracle. A
    new local import outside either set still fails, which is the point.
    """
    module = ast.parse(inspect.getsource(render_profile))
    local_imports = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.level and node.module is not None
    }
    assert local_imports == {
        "joined_record_design",
        "render_profile_authority",
        "render_profile_evidence",
        "render_profile_eligibility",
        "render_profile_loading",
        "render_profile_model",
        "render_profile_model_base",
        "render_profile_validation",
    }
    eligibility_module = ast.parse(inspect.getsource(render_profile_eligibility))
    eligibility_imports = {
        node.module
        for node in ast.walk(eligibility_module)
        if isinstance(node, ast.ImportFrom) and node.level and node.module is not None
    }
    # ``compiler.record_design_pdf_rows`` supplies only the record design's own
    # "No consta" type token, read from the same pinned source.
    # ``source_stated_composites`` reads source-pinned sign and magnitude
    # components; it does not consume a generated layout or export tree.
    assert eligibility_imports == {
        "compiler.record_design_pdf_rows",
        "record_design_intermediate",
        "source_defects",
        "source_stated_composites",
        "year_constraints",
    }
    source_reader = ast.parse(inspect.getsource(render_profile_source_reader))
    source_guard = next(
        node
        for node in source_reader.body
        if isinstance(node, ast.FunctionDef) and node.name == "_require_render_profile_source_binary"
    )
    guard_statements = source_guard.body
    link_guard_index = next(
        index
        for index, statement in enumerate(guard_statements)
        if isinstance(statement, ast.If)
        and any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "is_link_like"
            for node in ast.walk(statement.test)
        )
    )
    hash_index = next(
        index
        for index, statement in enumerate(guard_statements)
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sha256_file"
            for node in ast.walk(statement.value)
        )
    )
    assert link_guard_index < hash_index
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_require_render_profile_source_binary"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "source_path"
        for node in ast.walk(
            next(
                node
                for node in source_reader.body
                if isinstance(node, ast.FunctionDef) and node.name == "load_render_profile_source_evidence"
            ),
        )
    )


def test_real_profile_fragments_stay_below_the_reviewability_line_cap() -> None:
    """Deterministic partitioning keeps every authored fragment reviewable."""
    profile_directory = _M200_PROFILES / str(_M200_EXERCISE)
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
        filing_year=_exercise("aeat-dr-303-2025"),
        design_epoch=str(_exercise("aeat-dr-303-2025")),
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


#: Floor for modelo 347's eligible fields. Live the design yields 22, and a
#: narrowed naturaleza match once took the same set to ZERO. Two thirds of
#: live, so ordinary design movement never fires it.
_MINIMUM_ELIGIBLE_347_FIELDS = 15


def _eligibility_for(source_ref: str, catalogue: str) -> tuple[RecordDesignIntermediateField, ...]:
    """Return the eligible fields of one hash-verified design."""
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", catalogue))
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=_exercise(source_ref),
        design_epoch=str(_exercise(source_ref)),
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

    **19 became 22, and the three are real.** The parser learned to fold a
    desglose AEAT prints WITHOUT dotted ordinals, and the export IR descends to
    the leaves, so two of 347's printed parents dissolved into the rows they
    subdivide: ``PERSONA CON QUIEN RELACIONARSE`` @59+49 into TELÉFONO @59+9 and
    APELLIDOS Y NOMBRE @68+40, and ``IMPORTE PERCIBIDO EN METÁLICO`` @101+15 into
    its printed ``Parte entera`` @101+13 and ``Parte decimal`` @114+2. Four
    ordinal-less leaves replaced two ordinal-bearing parents, and every one of
    them has an EMPTY naturaleza cell, which is the strongest case for a reviewed
    rule there is. Moving the count to 22 records that the profile now governs
    each leaf; leaving it at 19 would have asserted that three rows carrying no
    stated wire fact need no reviewed rule.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "operaciones-terceros.toml")

    assert len(eligible) == 22
    assert all(field.source_cell is None for field in eligible), "modelo 347 is PDF-sourced"


def test_pdf_prose_in_content_is_not_read_as_a_stated_wire_fact() -> None:
    """A PDF field's ``content`` is description, not a Contenido cell.

    Modelo 347's ordinal-bearing numeric anchors carry non-blank content, and it
    reads like "Se consignará el número identificativo correspondiente a la
    declaración". Under the workbook rule that non-blank content meant the design
    had stated the wire fact, which is the wrong positive inference this test
    pins.

    Scoped to the anchors that HAVE content, because the desglose leaves the
    parser now descends to carry none: a folded sub-row inherits no Contenido
    cell, so its content is empty and the prose that describes it lives on the
    parent that no longer reaches here. An empty content field cannot state a
    wire fact either, so those rows are eligible for the same reason -- but they
    are not evidence for the inference this test exists to refuse, and asserting
    over them would quietly turn the assertion vacuous the moment it flipped.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "operaciones-terceros.toml")

    with_content = [
        field for field in eligible if (field.content is not None and field.content) and field.content.strip()
    ]
    assert with_content, "no eligible field carrying content to assert on"
    assert all(field.ordinal is not None for field in with_content), (
        "every content-bearing eligible anchor should be one AEAT printed with an ordinal"
    )


@pytest.mark.parametrize(
    ("source_ref", "catalogue"),
    [
        ("aeat-dr-232-2018", "is.toml"),
        ("aeat-dr-210-2022", "irnr.toml"),
        ("aeat-dr-303-2025", "iva.toml"),
    ],
)
def test_a_workbook_design_keeps_its_exact_previous_eligibility(
    source_ref: str,
    catalogue: str,
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
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=_exercise(source_ref),
        design_epoch=str(_exercise(source_ref)),
    )
    fields = [field for sheet in intermediate.sheets for field in sheet.fields]
    original = {
        (field.record_identity, field.offset)
        for field in fields
        if field.aeat_type in {"Num", "N"}
        and (field.content is None or not field.content.strip())
        and not is_source_reserved_field(field)
    }
    live = {(field.record_identity, field.offset) for field in project_render_profile_eligibility(fields).all_fields}

    assert live == original


def test_a_source_reserved_pdf_slot_stays_ineligible() -> None:
    """A reserved run carries no wire fact on either source shape.

    Widening the numeric-type match must not start demanding a numeric rule for
    a slot the design reserves, which would force an author to model meaning onto
    filler.
    """
    eligible = _eligibility_for("aeat-dr-347-2025", "operaciones-terceros.toml")

    # The claim is an ABSENCE, so it needs the population it is absent from.
    # This has already happened here once: selecting on workbook abbreviations
    # alone made every 347 field ineligible, and the sibling above records that
    # "an EMPTY render profile satisfied exhaustive coverage completely" while
    # the design shipped with no numeric format, sign policy or decimal
    # placement. An emptied eligibility set satisfies the absence below the same
    # way. Live the design yields 22 eligible fields, none of them reserved.
    assert len(eligible) >= _MINIMUM_ELIGIBLE_347_FIELDS, (
        f"only {len(eligible)} eligible field(s) for modelo 347; below this the reserved-slot "
        "absence below holds because nothing was eligible, not because nothing was reserved"
    )
    reserved = [field for field in eligible if is_source_reserved_field(field)]
    assert not reserved, f"a slot the design reserves became eligible for a reviewed rule: {reserved}"


def test_width_17_type_order_covers_every_declared_aeat_type() -> None:
    """The emit order must enumerate every width-17 type the model admits.

    ``_compile_width_17_rules`` walks ``_WIDTH_17_TYPE_ORDER`` and reads
    ``by_type`` through it, so a type present in the rules but absent from that
    tuple is dropped without a refusal -- its declared width, sign policy and
    evidence never reach the compiled profile, and the fields it governs render
    as though the rule had never been authored. Nothing else fails when that
    happens, which is why this is asserted rather than left to review.
    """
    declared = set(get_args(Width17MembershipRule.model_fields["aeat_type"].annotation))
    ordered = set(WIDTH_17_TYPE_ORDER)
    assert ordered == declared, (
        f"width-17 emit order {sorted(ordered)} does not cover the declared aeat_type set "
        f"{sorted(declared)}; a type admitted by the model but missing from the order is "
        "silently discarded during compilation"
    )

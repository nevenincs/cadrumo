"""Tests for committed Modelo 720 registry foundation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import cast

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_revision_members import DependencyClassificationDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..conformance.registry_schema_support import committed_modelo
from .modelo_registry_surface_support import (
    FORBIDDEN_REMOTE_ACTIONS,
    assert_authenticated_read_surface_is_read_only,
    assert_declaration_pdf_profile_legal_refs,
    assert_review_surfaces_require_snapshot,
)
from .profile_schema_support import committed_registry_validator, committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_REVISION_ID = str(open_ended_revision("720").id)


def _load_modelo_720() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo("720")


_DECLARATION_PROFILE_TARGET_LEGAL_REFS = frozenset(
    [
        "ley-58-2003:art-93",
        "orden-hap-72-2013:art-1",
        "orden-hap-72-2013:art-7",
    ]
)
_COMPLETENESS_MANIFEST_LEGAL_REFS = frozenset(
    [
        "ley-58-2003:art-93",
        "ley-58-2003:da-18",
        "orden-hap-72-2013:art-1",
        "orden-hap-72-2013:art-2",
        "orden-hap-72-2013:art-7",
        "rd-1065-2007:art-42-bis",
        "rd-1065-2007:art-42-ter",
        "rd-1065-2007:art-54-bis",
    ]
)


def test_committed_modelo_720_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_720()
    committed_registry_validator(catalogues).validate_modelo(modelo)
    assert set(modelo.revisions) == {_REVISION_ID}


def _modelo_720_with_previous_filing_classification(
    rewrite: Callable[[DependencyClassificationDefinition], DependencyClassificationDefinition | None],
) -> tuple[ModeloDefinition, RegistryCatalogues]:
    """The loaded Modelo 720 with its prior-year classification rewritten, or removed when ``rewrite`` returns ``None``.

    The classification leaves its construct's membership list in both cases, so
    a refusal proves the direct previous-filing gate rather than a dangling id.
    """
    modelo, catalogues = _load_modelo_720()
    revision = modelo.revisions[_REVISION_ID]
    classification = next(item for item in revision.dependency_classifications if item.source_modelo == "720")
    construct = next(item for item in revision.constructs if classification.id in item.dependency_classifications)
    mutated_construct = construct.model_copy(
        update={
            "dependency_classifications": tuple(
                item for item in construct.dependency_classifications if item != classification.id
            ),
        },
    )
    replacement = rewrite(classification)
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                item
                for item in (
                    replacement if candidate.id == classification.id else candidate
                    for candidate in revision.dependency_classifications
                )
                if item is not None
            ),
            "constructs": tuple(item if item.id != construct.id else mutated_construct for item in revision.constructs),
        },
    )
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: mutated_revision}},
    )
    return mutated_modelo, catalogues


def test_validator_rejects_missing_factual_evidence_previous_filing_classification() -> None:
    """The actual prior-year valuations require their Modelo 720 classification.

    This removes the loaded revision's sole factual-evidence classification and
    its construct membership together, so the refusal proves the direct
    previous-filing completeness gate rather than a dangling construct id.
    """
    mutated_modelo, catalogues = _modelo_720_with_previous_filing_classification(lambda _classification: None)

    with pytest.raises(
        RegistryValidationError,
        match=r"binding source modelo '720' has no dependency classification",
    ):
        committed_registry_validator(catalogues).validate_modelo(mutated_modelo)


def test_validator_rejects_non_dependency_previous_filing_classification() -> None:
    """A direct prior-year baseline cannot be re-labelled as non-dependent."""
    mutated_modelo, catalogues = _modelo_720_with_previous_filing_classification(
        lambda classification: classification.model_copy(
            update={"treatment": "non_dependency", "target_constructs": (), "binding_refs": ()},
        )
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"binding source modelo '720' cannot be classified as non_dependency",
    ):
        committed_registry_validator(catalogues).validate_modelo(mutated_modelo)


_SUPPORT = committed_supported_filing_years()


@pytest.mark.parametrize(
    "filing_year",
    sorted({_SUPPORT.floor, (_SUPPORT.floor + _SUPPORT.horizon) // 2, _SUPPORT.horizon}),
)
def test_committed_modelo_720_resolves_revision_by_filing_year(filing_year: int) -> None:
    """Every supported year selects the single open-ended edition."""
    expected_revision = _REVISION_ID
    modelo, catalogues = _load_modelo_720()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    assert snapshot.revision.id == expected_revision
    assert snapshot.revision.orden_aplicabilidad == ("orden-hap-72-2013:art-1",)


def test_committed_modelo_720_is_informative_only() -> None:
    modelo, _ = _load_modelo_720()
    assert modelo.calculation_class == "informative", (
        "Modelo 720 must be declared calculation_class='informative' in its manifest"
    )
    for revision in modelo.revisions.values():
        assert revision.formulas == (), (
            f"revision {revision.id!r} declares calculation formulas; "
            "Modelo 720 is informative-only and must not own filing-grade calculations"
        )
        assert not any(binding.source.value == "relation_prefill" for binding in revision.bindings), (
            f"revision {revision.id!r} declares cross-model relation-prefill bindings; Modelo 720 is informative-only"
        )
        for casilla in revision.casillas:
            assert casilla.input_kind in {InputKind.INFORMATIONAL, InputKind.MANUAL}, casilla.id


def test_committed_modelo_720_workbook_parity_resolves_to_corpus_artefact() -> None:
    modelo, catalogues = _load_modelo_720()
    assert catalogues.sources["aeat-modelo-720-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-720-2013-form"].evidence_tier == "layout_authority"
    for revision in modelo.revisions.values():
        ref = next(
            (r for r in revision.workbook_parity_refs if r.workbook_source == "aeat-dr-720"),
            None,
        )
        assert ref is not None, revision.id
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        source = catalogues.sources["aeat-dr-720"]
        assert source.evidence_tier == "layout_authority"
        artefact_path = bundled_path() / source.corpus_path
        assert artefact_path.is_file(), artefact_path


def test_committed_modelo_720_static_cross_reference_forbids_remote_writes() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        decision = next(ref for ref in revision.live_cross_references if ref.surface == "static_official_documentation")
        assert decision.requires_authentication is False
        assert decision.synthetic_data_allowed is False
        assert FORBIDDEN_REMOTE_ACTIONS.issubset(decision.forbidden_actions), revision.id


def test_committed_modelo_720_authenticated_read_surface_is_read_only_and_guarded() -> None:
    modelo, _ = _load_modelo_720()
    assert_authenticated_read_surface_is_read_only(modelo)


def test_committed_modelo_720_declaration_pdf_extraction_profile_targets_declarante_casillas() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        pdf_profiles = [profile for profile in revision.extraction_profiles if profile.surface == "declaracion_pdf"]
        assert pdf_profiles, revision.id
        for profile in pdf_profiles:
            assert profile.parser == "cadrumo.adapters.inbound.declaracion.parser.parse_declaracion"
            assert profile.confidence == "strict"
            assert profile.corpus_round_trip_verified is True
            assert profile.failure_semantics == "fail_hard"
            assert {t.casilla_id for t in profile.target_casillas} <= casilla_ids


def test_committed_modelo_720_declaration_pdf_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_720()
    assert_declaration_pdf_profile_legal_refs(modelo, _DECLARATION_PROFILE_TARGET_LEGAL_REFS)


def test_committed_modelo_720_completeness_manifest_legal_refs_match_declarante_closure() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert revision.completeness_manifest is not None, revision.id
        assert frozenset(revision.completeness_manifest.legal_refs) == _COMPLETENESS_MANIFEST_LEGAL_REFS


def test_committed_modelo_720_verification_expectation_is_informative_strict() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        assert revision.verification_expectations, revision.id
        for expectation in revision.verification_expectations:
            assert expectation.tolerance == 0
            assert expectation.rounding == "none"
            assert expectation.discrepancy_causes == ("extraction_unreliable",)
            assert set(expectation.computed_casilla_ids) <= casilla_ids


def test_committed_modelo_720_filing_schedule_is_annual() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert revision.filing_schedules, revision.id
        for schedule in revision.filing_schedules:
            assert schedule.period_kind == "annual"
            assert schedule.periods == ("0A",)


@pytest.mark.parametrize(
    ("sample", "open_month", "close_month", "close_day"),
    [
        # First ejercicio had a transitional plazo until 30 April of the following year per Orden HAP/72/2013 DT
        ("first", 2, 4, 30),
        # Subsequent ejercicios run from 1 January to 31 March of the following year per art 7
        ("second", 1, 3, 31),
        ("middle", 1, 3, 31),
        ("last", 1, 3, 31),
    ],
)
def test_committed_modelo_720_deadline_window_is_january_to_march_following_ejercicio(
    sample: str,
    open_month: int,
    close_month: int,
    close_day: int,
) -> None:
    modelo, _ = _load_modelo_720()
    authored_exercises = sorted(
        {window.filing_year for revision in modelo.revisions.values() for window in revision.deadline_windows}
    )
    filing_year = {
        "first": authored_exercises[0],
        "second": authored_exercises[1],
        "middle": authored_exercises[len(authored_exercises) // 2],
        "last": authored_exercises[-1],
    }[sample]
    expected_open = date(filing_year + 1, open_month, 1)
    expected_close = date(filing_year + 1, close_month, close_day)
    windows = [
        window
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.filing_year == filing_year
    ]
    assert len(windows) == 1, filing_year
    window = windows[0]
    assert window.period_kind == "annual"
    assert window.opens_on == expected_open
    assert window.closes_on == expected_close
    assert "aeat-modelo-720-procedure" in window.source_refs


def _layout_bindings_for(revision: ModeloRevision, record_name: str):
    return tuple(binding for binding in revision.bindings if selector_as_dict(binding).get("record") == record_name)


def test_committed_modelo_720_type_1_bindings_target_declarante_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "type_1")
        assert bindings, revision.id
        # DR720 position 1 is the record literal; filing year and taxpayer
        # identity supply the rest of the prefix without manual bindings.
        record = next(record for record in revision.export_layouts[0].records if record.record_type == "type_1")
        record_type = next(field for field in record.fields if field.offset == 1)
        assert record_type.kind.value == "literal"
        assert record_type.literal == "1"
        assert record_type.binding is None
        # TIPO DE SOPORTE at position 58 is the first manual field.
        first_offset = min(int(cast(int, selector_as_dict(b)["offset"])) for b in bindings)
        assert first_offset == 58, first_offset


def test_committed_modelo_720_type_2_bindings_target_detalle_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        bindings = _layout_bindings_for(revision, "type_2")
        assert bindings, revision.id
        # DR720 supplies the type, model, year and declarante NIF prefix from
        # literals and identity; NIF DEL DECLARADO starts manual input at 18.
        record = next(record for record in revision.export_layouts[0].records if record.record_type == "type_2")
        record_type = next(field for field in record.fields if field.offset == 1)
        assert record_type.kind.value == "literal"
        assert record_type.literal == "2"
        assert record_type.binding is None
        first_offset = min(int(cast(int, selector_as_dict(b)["offset"])) for b in bindings)
        assert first_offset == 18, first_offset
        # Type 2 closes at position 480 (PORCENTAJE DE PARTICIPACIÓN, last field of detalle record)
        ranges = sorted(
            (int(cast(int, selector_as_dict(b)["offset"])), int(cast(int, selector_as_dict(b)["length"])))
            for b in bindings
        )
        last_offset, last_length = ranges[-1]
        assert last_offset + last_length - 1 == 480, last_offset + last_length - 1


def test_committed_modelo_720_export_layout_uses_repeating_detalle_record() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        layout = revision.export_layouts[0]
        type_1 = next(r for r in layout.records if r.record_type == "type_1")
        type_2 = next(r for r in layout.records if r.record_type == "type_2")
        assert type_1.binding_record == "type_1"
        assert type_1.repeat is None
        assert type_2.binding_record == "type_2"
        assert type_2.repeat == "binding_rows"


def test_committed_modelo_720_construct_includes_revision_members() -> None:
    modelo, _ = _load_modelo_720()
    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1, revision.id
        construct = revision.constructs[0]
        assert construct.casilla_ids == tuple(c.id for c in revision.casillas)
        assert construct.extraction_profiles == tuple(p.id for p in revision.extraction_profiles)
        assert construct.verification_expectations == tuple(e.id for e in revision.verification_expectations)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)
        revision_binding_ids = {binding.id for binding in revision.bindings}
        assert revision_binding_ids <= set(construct.bindings)
        assert construct.export_layouts == tuple(layout.id for layout in revision.export_layouts)
        link_surfaces = {link.surface for link in revision.application_links}
        assert {
            "portal",
            "filing",
            "extractor",
            "deadline",
            "export",
            "review",
            "approval",
            "reconciliation",
            "workflow",
        } <= link_surfaces, revision.id


def test_modelo_720_workflow_surfaces_are_snapshot_gated_and_construct_scoped() -> None:
    modelo, _ = _load_modelo_720()
    assert_review_surfaces_require_snapshot(modelo)

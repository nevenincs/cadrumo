"""Real-authority tests for semantic-map to parser-intermediate validation."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.filing_projection_ref import (
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.domain.calculations.registry.authority import bundled_revision_inspection
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline import _semantic_map_validation
from ..pipeline._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_validation import SemanticMapAnomalyException, validate_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def _m303_snapshot():
    return bundled_revision_inspection("303", filing_year=2025, period="4T")


def _intermediate_payload(
    *,
    source_sha256: str = "0" * 64,
    source_ref: str = "aeat-dr-200-2025",
    design_epoch: str = "2025",
) -> dict[str, object]:
    return {
        "source": {
            "source_ref": source_ref,
            "source_sha256": source_sha256,
            "workbook_format": RecordDesignWorkbookFormat.XLSX,
            "design_epoch": design_epoch,
        },
        "sheets": (
            {
                "sheet": "Registro tipo 1",
                "record_identity": "registro-tipo-1",
                "declared_total": 2,
                "fields": (
                    {
                        "sheet": "Registro tipo 1",
                        "record_identity": "registro-tipo-1",
                        "source_row": 14,
                        "source_cell": "A14",
                        "ordinal": "1",
                        "offset": 1,
                        "length": 1,
                        "aeat_type": "AN",
                        "normalized_description": "Campo uno",
                    },
                    {
                        "sheet": "Registro tipo 1",
                        "record_identity": "registro-tipo-1",
                        "source_row": 15,
                        "source_cell": "A15",
                        "ordinal": "2",
                        "offset": 2,
                        "length": 1,
                        "aeat_type": "AN",
                        "normalized_description": "Campo dos",
                    },
                ),
            },
        ),
    }


def _semantic_map_payload(
    *,
    entries: tuple[dict[str, object], ...],
    source_ref: str = "aeat-dr-200-2025",
    source_sha256: str = "92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509",
    modelo: str = "200",
    design_epoch: str = "2025",
) -> dict[str, object]:
    return {
        "modelo": modelo,
        "design_epoch": design_epoch,
        "source_ref": source_ref,
        "source_sha256": source_sha256,
        "records": (
            {
                "sheet": "Registro tipo 1",
                "record_identity": "registro-tipo-1",
                "export_record_id": "registro-tipo-1",
                "record_type": "declaracion",
            },
        ),
        "entries": entries,
    }


def _entry(
    *,
    row: int,
    ordinal: int,
    field_id: str,
    kind: str = "literal",
    legal_ref: str = "ley-27-2014:art-40",
    source_ref: str = "aeat-dr-200-2025",
    **payload: object,
) -> dict[str, object]:
    return {
        "anchor": {
            "sheet": "Registro tipo 1",
            "source_row": row,
            "source_cell": f"A{row}",
            # The anchor ordinal is the design's PRINTED ordinal and is carried
            # as a string -- DP30302's simplified rows number sequentially with
            # no dotted or `bis` label, but other sheets do. This fixture passed
            # an int, which the model now refuses, and the refusal cascaded into
            # a `too_short` on the field tuple that made the cause unreadable.
            "ordinal": str(ordinal),
            "record_identity": "registro-tipo-1",
        },
        "export_field_id": field_id,
        "kind": kind,
        "legal_refs": (legal_ref,),
        "source_refs": (source_ref,),
        **payload,
    }


def _real_source_sha256(snapshot, source_ref: str = "aeat-dr-200-2025") -> str:
    return snapshot.sources[source_ref].sha256


#: A REAL target-revision authority that declares no projection endpoint.
#:
#: Four cases below assert refusals that have nothing to do with projections --
#: the happy path, the unresolved-reference family, the anomaly-exception pin and
#: the no-legacy-inference proof. They ran against modelo 200, which has since
#: gained 578 projection declarations, and `validate_semantic_map` checks the map
#: against those as a BIJECTION. A two-entry synthetic map cannot satisfy 578, so
#: every one of them refused on "omits target-revision projection declarations"
#: before reaching the defect it planted.
#:
#: Modelo 130 is the same shape of authority -- a real revision with a bundled
#: diseño, casillas, bindings and resolvable refs -- and declares zero
#: projections, so the toy map satisfies the bijection trivially and each case
#: reaches its own assertion again. The projection-specific cases keep modelo 200
#: and modelo 303 deliberately: their subject IS the declaration bijection.
_M130_MODELO = "130"
_M130_EPOCH = "2019"
_M130_DESIGN_REF = "aeat-dr-130-2019-v12"
_M130_LEGAL_REF = "rd-439-2007:art-110"


def _projection_ref() -> M303ProrrataActivityProjectionRef:
    return M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=M303ProrrataActivityProjectionField.CNAE,
        casilla_id=validated_casilla_id("500", surface="test"),
    )


def test_validation_accepts_complete_exact_map_with_live_revision_authority(m130_inspection_snapshot) -> None:
    """A complete map resolves through the real M200 source and target revision."""
    source_sha256 = _real_source_sha256(m130_inspection_snapshot, _M130_DESIGN_REF)
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=source_sha256, source_ref=_M130_DESIGN_REF, design_epoch=_M130_EPOCH)
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            modelo=_M130_MODELO,
            source_ref=_M130_DESIGN_REF,
            design_epoch=_M130_EPOCH,
            source_sha256=source_sha256,
            entries=(
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=14,
                    ordinal=1,
                    field_id="generated.literal.one",
                    literal="T",
                ),
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=15,
                    ordinal=2,
                    field_id="generated.literal.two",
                    literal="0",
                ),
            ),
        ),
    )

    validate_semantic_map(semantic_map, intermediate, m130_inspection_snapshot)


@pytest.mark.parametrize(
    ("source_ref", "source_sha256", "message"),
    (
        ("aeat-dr-200-2025", "b" * 64, "semantic map SHA-256 does not match parser intermediate source"),
        ("aeat-dr-303-2025", "a" * 64, "semantic map source .* does not match parser intermediate source"),
    ),
)
def test_validation_refuses_changed_or_mixed_semantic_map_source_identity(
    m200_inspection_snapshot,
    source_ref: str,
    source_sha256: str,
    message: str,
) -> None:
    """Map source pins are exact and cannot cross-match a same-epoch design."""
    intermediate_source_sha256 = _real_source_sha256(m200_inspection_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=intermediate_source_sha256),
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            source_ref=source_ref,
            source_sha256=source_sha256,
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match=message):
        validate_semantic_map(semantic_map, intermediate, m200_inspection_snapshot)


def test_validation_refuses_catalogued_parser_source_absent_from_selected_revision(m200_inspection_snapshot) -> None:
    """A source catalogue entry cannot implicitly select a different revision authority."""
    source_ref = "aeat-dr-200-2025"
    source_sha256 = m200_inspection_snapshot.sources[source_ref].sha256
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=source_sha256),
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            source_ref=source_ref,
            source_sha256=source_sha256,
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
            ),
        ),
    )
    snapshot_without_parser_source = m200_inspection_snapshot.model_copy(
        update={
            "revision_source_refs": tuple(
                ref for ref in m200_inspection_snapshot.revision_source_refs if ref != source_ref
            ),
        },
    )

    with pytest.raises(RegistryValidationError, match="is not an authority of selected revision"):
        validate_semantic_map(semantic_map, intermediate, snapshot_without_parser_source)


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            (_entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),),
            "missing semantic entries",
        ),
        (
            (
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=14, ordinal=1, field_id="generated.literal.two", literal="0"),
                _entry(row=15, ordinal=2, field_id="generated.literal.three", literal="0"),
            ),
            "duplicate exact anchors",
        ),
        (
            (
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
                _entry(row=16, ordinal=3, field_id="generated.literal.three", literal="0"),
            ),
            "extra semantic entries",
        ),
    ],
)
def test_validation_refuses_missing_duplicate_or_extra_anchor_mappings(
    m200_inspection_snapshot,
    entries: tuple[dict[str, object], ...],
    message: str,
) -> None:
    """No anomaly declaration can turn an incomplete or ambiguous map into a join."""
    source_sha256 = _real_source_sha256(m200_inspection_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(_semantic_map_payload(entries=entries, source_sha256=source_sha256))
    exception = SemanticMapAnomalyException(
        source_ref="aeat-dr-200-2025",
        source_sha256=source_sha256,
        category="parser_anomaly",
        reason="Reviewed parser anomaly does not waive map completeness.",
    )

    with pytest.raises(RegistryValidationError, match=message):
        validate_semantic_map(semantic_map, intermediate, m200_inspection_snapshot, anomaly_exceptions=(exception,))


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            _entry(
                legal_ref=_M130_LEGAL_REF,
                source_ref=_M130_DESIGN_REF,
                row=14,
                ordinal=1,
                field_id="generated.casilla.one",
                kind="casilla",
                casilla_id="casilla.999999",
            ),
            "unknown target-revision casilla",
        ),
        (
            _entry(
                legal_ref=_M130_LEGAL_REF,
                source_ref=_M130_DESIGN_REF,
                row=14,
                ordinal=1,
                field_id="generated.binding.one",
                kind="binding",
                binding="unknown.binding",
            ),
            "unknown target-revision binding",
        ),
        (
            _entry(
                legal_ref=_M130_LEGAL_REF,
                source_ref=_M130_DESIGN_REF,
                row=14,
                ordinal=1,
                field_id="generated.literal.one",
                literal="T",
                legal_refs=("unknown:legal",),
            ),
            "unresolved legal refs",
        ),
        (
            _entry(
                legal_ref=_M130_LEGAL_REF,
                source_ref=_M130_DESIGN_REF,
                row=14,
                ordinal=1,
                field_id="generated.literal.one",
                literal="T",
                source_refs=("unknown-source",),
            ),
            "unresolved source refs",
        ),
    ],
)
def test_validation_refuses_unresolved_canonical_semantic_references(
    m130_inspection_snapshot,
    entry: dict[str, object],
    message: str,
) -> None:
    """Casilla, binding, and evidence references resolve only through the snapshot."""
    source_sha256 = _real_source_sha256(m130_inspection_snapshot, _M130_DESIGN_REF)
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=source_sha256, source_ref=_M130_DESIGN_REF, design_epoch=_M130_EPOCH)
    )
    second = _entry(
        legal_ref=_M130_LEGAL_REF,
        source_ref=_M130_DESIGN_REF,
        row=15,
        ordinal=2,
        field_id="generated.literal.two",
        literal="0",
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            modelo=_M130_MODELO,
            source_ref=_M130_DESIGN_REF,
            design_epoch=_M130_EPOCH,
            source_sha256=source_sha256,
            entries=(entry, second),
        ),
    )

    with pytest.raises(RegistryValidationError, match=message):
        validate_semantic_map(semantic_map, intermediate, m130_inspection_snapshot)


def test_validation_refuses_duplicate_export_id_without_consulting_legacy_layout(m200_inspection_snapshot) -> None:
    """Generated-layout identifiers are grammar-validated and map-local unique."""
    source_sha256 = _real_source_sha256(m200_inspection_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal", literal="0"),
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match="duplicate canonical export field ids"):
        validate_semantic_map(semantic_map, intermediate, m200_inspection_snapshot)


def test_validation_refuses_duplicate_projection_refs_before_any_snapshot_inference(m200_inspection_snapshot) -> None:
    """An exact typed ref may appear at most once, independent of its source anchor."""
    source_sha256 = _real_source_sha256(m200_inspection_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    projection_ref = _projection_ref()
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(
                    row=14,
                    ordinal=1,
                    field_id="generated.projection.one",
                    kind="projection",
                    projection_ref=projection_ref,
                ),
                _entry(
                    row=15,
                    ordinal=2,
                    field_id="generated.projection.two",
                    kind="projection",
                    projection_ref=projection_ref,
                ),
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match="duplicate projection references"):
        validate_semantic_map(semantic_map, intermediate, m200_inspection_snapshot)


def test_validation_refuses_projection_ref_not_admitted_by_the_selected_snapshot(m200_inspection_snapshot) -> None:
    """A source anchor cannot admit a typed row owner absent from the revision."""
    source_sha256 = _real_source_sha256(m200_inspection_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(
                    row=14,
                    ordinal=1,
                    field_id="generated.projection.one",
                    kind="projection",
                    projection_ref=_projection_ref(),
                ),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match="not admitted by the target revision"):
        validate_semantic_map(semantic_map, intermediate, m200_inspection_snapshot)


def test_projection_admission_uses_the_real_revision_declaration_bijection(_m303_snapshot) -> None:
    """A selected M303 snapshot admits its complete typed endpoint matrix only."""
    references = tuple(declaration.projection_ref for declaration in _m303_snapshot.projection_endpoints)

    _semantic_map_validation._validate_projection_ref_bijection(
        references,
        projection_endpoints=_m303_snapshot.projection_endpoints,
    )

    with pytest.raises(RegistryValidationError, match="omits target-revision projection declarations"):
        _semantic_map_validation._validate_projection_ref_bijection(
            references[1:],
            projection_endpoints=_m303_snapshot.projection_endpoints,
        )


def test_anomaly_exception_is_hash_pinned_and_cannot_supply_coordinates(m130_inspection_snapshot) -> None:
    """Anomalies name only a source condition and retain the full bijection gate."""
    source_sha256 = _real_source_sha256(m130_inspection_snapshot, _M130_DESIGN_REF)
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=source_sha256, source_ref=_M130_DESIGN_REF, design_epoch=_M130_EPOCH)
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            modelo=_M130_MODELO,
            source_ref=_M130_DESIGN_REF,
            design_epoch=_M130_EPOCH,
            source_sha256=source_sha256,
            entries=(
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=14,
                    ordinal=1,
                    field_id="generated.literal.one",
                    literal="T",
                ),
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=15,
                    ordinal=2,
                    field_id="generated.literal.two",
                    literal="0",
                ),
            ),
        ),
    )
    exception = SemanticMapAnomalyException(
        source_ref=_M130_DESIGN_REF,
        source_sha256=source_sha256,
        category="source_anomaly",
        reason="Official workbook records a reviewable source anomaly.",
    )

    validate_semantic_map(semantic_map, intermediate, m130_inspection_snapshot, anomaly_exceptions=(exception,))

    with pytest.raises(RegistryValidationError, match="not pinned to the parser intermediate SHA-256"):
        validate_semantic_map(
            semantic_map,
            intermediate,
            m130_inspection_snapshot,
            anomaly_exceptions=(exception.model_copy(update={"source_sha256": "1" * 64}),),
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SemanticMapAnomalyException.model_validate(
            {
                **exception.model_dump(),
                "source_row": 14,
            },
        )


def test_validation_uses_no_legacy_export_layout_membership_or_identifier_inference(m130_inspection_snapshot) -> None:
    """A novel generated ID validates without consulting the unverified legacy tree."""
    source_sha256 = _real_source_sha256(m130_inspection_snapshot, _M130_DESIGN_REF)
    intermediate = RecordDesignIntermediate.model_validate(
        _intermediate_payload(source_sha256=source_sha256, source_ref=_M130_DESIGN_REF, design_epoch=_M130_EPOCH)
    )
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            modelo=_M130_MODELO,
            source_ref=_M130_DESIGN_REF,
            design_epoch=_M130_EPOCH,
            source_sha256=source_sha256,
            entries=(
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=14,
                    ordinal=1,
                    field_id="generated.s05.literal.one",
                    literal="T",
                ),
                _entry(
                    legal_ref=_M130_LEGAL_REF,
                    source_ref=_M130_DESIGN_REF,
                    row=15,
                    ordinal=2,
                    field_id="generated.s05.literal.two",
                    literal="0",
                ),
            ),
        ),
    )
    validate_semantic_map(semantic_map, intermediate, m130_inspection_snapshot)


def test_validation_module_carries_no_legacy_layout_dependency() -> None:
    """Structural guard: validation cannot read a legacy layout as an admission oracle."""
    module = ast.parse(inspect.getsource(_semantic_map_validation))
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    string_constants = {
        node.value for node in ast.walk(module) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "export_layouts" not in attribute_names
    assert "resolve_export_layout" not in referenced_names
    assert "export_layouts" not in string_constants
    assert "cadrumo.domain.calculations.registry.export" not in imported_modules

"""Casilla addressing referential-integrity tests split from part1."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, FormulaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_surfaces import CalculationCompletenessCasilla
from cadrumo.domain.calculations.registry.tests._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    build_minimal_snapshot,
    completeness_manifest,
    minimal_application_link,
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    segmented_casilla,
)

from .....core import BindingSourceKind, CasillaId, validated_casilla_id
from ..schema_base import SourceCitation
from ..schema_input_kind import InputKind
from ..validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")
_NUMERIC_CASILLA_02: CasillaId = validated_casilla_id("02", surface="_NUMERIC_CASILLA_02")
_SEGMENTED_LIQUIDACION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_SEGMENTED_LIQUIDACION_CASILLA",
)
_SEGMENTED_ECPN_CASILLA: CasillaId = validated_casilla_id("DP200032:00562", surface="_SEGMENTED_ECPN_CASILLA")
_SEGMENTED_TARGET_CASILLA: CasillaId = validated_casilla_id("DP200014:00999", surface="_SEGMENTED_TARGET_CASILLA")
_BARE_REUSED_NUMBER_CASILLA: CasillaId = validated_casilla_id("00562", surface="_BARE_REUSED_NUMBER_CASILLA")
_BARE_REUSED_NUMBER_ALT_CASILLA: CasillaId = validated_casilla_id(
    "00562-alt",
    surface="_BARE_REUSED_NUMBER_ALT_CASILLA",
)
_SEGMENTED_LIQUIDACION_ALT_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562-alt",
    surface="_SEGMENTED_LIQUIDACION_ALT_CASILLA",
)
_SEGMENTED_EXPORT_FIELD_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00592",
    surface="_SEGMENTED_EXPORT_FIELD_CASILLA",
)
_BARE_EXPORT_FIELD_CASILLA: CasillaId = validated_casilla_id("00592", surface="_BARE_EXPORT_FIELD_CASILLA")
_REFERENCE_FORMULA_CITATION = SourceCitation(source_ref=REFERENCE_SOURCE_ID, required_text=("test formula source",))
_FORMULA_REVISION_APPLICATION_LINKS = (
    minimal_application_link("filing"),
    minimal_application_link("calculation").model_copy(update={"id": "al.test.calculation"}),
)


def _validate_revision(revision: ModeloRevision) -> None:
    RegistryValidator(minimal_catalogues()).validate_modelo(minimal_modelo(revision))


def test_same_number_distinct_segmento_casillas_validate() -> None:
    """Two casillas sharing a number under distinct segmento values both validate.

    This is the multi-segment AEAT shape (e.g. Modelo 200 casilla 00562
    appearing in both the Liquidacion and ECPN record segments). The
    casillas carry distinct ids and distinct segmento codes, so the
    (segmento, number) metadata pairs (DP200014, 00562) and
    (DP200032, 00562) are unique and the validator must accept them.
    """
    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    _validate_revision(minimal_revision(casillas=(liquidacion, ecpn)))


def test_single_segment_duplicate_number_collision_fails() -> None:
    """Two segmento-unset casillas sharing a number hard-fail on (None, number).

    The casillas carry distinct ids, so the per-kind duplicate-id check
    does NOT fire. Only the generalised (segmento, number) metadata
    uniqueness invariant catches the collision: with segmento unset on both, the
    pair degrades to (None, '00562') and the duplicate is reported with
    the bare-number message, exactly as the prior duplicate-id check did.
    """
    first = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00562", None)
    second = segmented_casilla(_BARE_REUSED_NUMBER_ALT_CASILLA, "00562", None)
    revision = minimal_revision(casillas=(first, second))
    with pytest.raises(RegistryValidationError, match=r"duplicate casilla number '00562'"):
        _validate_revision(revision)


def test_same_segmento_duplicate_number_collision_fails() -> None:
    """Two casillas sharing a number within one segmento hard-fail.

    Within a single record segment a casilla number must still be
    unique; the (segmento, number) pair (DP200014, 00562) declared twice
    is a duplicate and the validator reports it segment-qualified.
    """
    first = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    second = segmented_casilla(_SEGMENTED_LIQUIDACION_ALT_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(first, second))
    with pytest.raises(
        RegistryValidationError,
        match=r"duplicate casilla number '00562' within segmento 'DP200014'",
    ):
        _validate_revision(revision)


def test_single_segment_numeric_casilla_id_reference_resolves() -> None:
    """A formula may reference a numeric token only when it is the casilla id.

    The casilla sets ``id == number`` with ``segmento`` unset, so ``01``
    is the canonical ``casilla.id``. A formula whose expression reads
    that id and whose target is a computed casilla must validate with no
    unknown-casilla failure.
    """
    input_casilla = segmented_casilla(_NUMERIC_CASILLA_01, "01", None)
    computed_casilla = segmented_casilla(_NUMERIC_CASILLA_02, "02", None).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_02,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        source_citations=(_REFERENCE_FORMULA_CITATION,),
    )
    manifest = completeness_manifest(
        (
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_02, number="02"),
        ),
    )
    revision = minimal_revision(
        casillas=(input_casilla, computed_casilla),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    ).model_copy(
        update={"completeness_manifest": manifest},
    )
    _validate_revision(revision)


def test_ambiguous_cross_segment_bare_number_reference_does_not_resolve() -> None:
    """A bare-number reference to a number reused across segments fails to resolve.

    Casilla number 00562 occurs in two record segments, so the bare
    number is ambiguous. A formula expression that references '00562'
    directly must NOT resolve: the validator reports an unknown casilla,
    forcing the formula to name the intended occurrence by its
    segment-qualified id.
    """
    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    target_casilla_def = segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_BARE_REUSED_NUMBER_CASILLA),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        source_citations=(_REFERENCE_FORMULA_CITATION,),
    )
    revision = minimal_revision(
        casillas=(liquidacion, ecpn, target_casilla_def),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    )
    with pytest.raises(RegistryValidationError, match="unknown casilla '00562'"):
        _validate_revision(revision)


def test_reused_number_with_bare_canonical_id_fails() -> None:
    """A reused printed number cannot leave one casilla addressable by the bare number."""
    ecpn = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00562", None)
    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(ecpn, liquidacion))
    with pytest.raises(RegistryValidationError, match=r"ambiguous bare casilla ids \['00562'\]"):
        _validate_revision(revision)


def test_casilla_id_cannot_equal_another_casilla_display_token() -> None:
    """A token cannot be one casilla's id and another casilla's display metadata."""
    canonical_owner = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00563", None)
    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(canonical_owner, display_owner))
    with pytest.raises(RegistryValidationError, match="casilla reference token '00562' is ambiguous"):
        _validate_revision(revision)


def test_casilla_display_token_cannot_equal_binding_id() -> None:
    """Casilla metadata tokens cannot collide with non-casilla registry ids."""
    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    binding = DataBindingDefinition(
        id="00562",
        source=BindingSourceKind.MANUAL_INPUT,
        selector={
            "record": "DPA",
            "field": "test",
            "offset": 1,
            "length": 1,
            "data_type": "integer",
        },
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(display_owner,), bindings=(binding,))

    with pytest.raises(
        RegistryValidationError,
        match="casilla reference token '00562' is ambiguous; it is binding id '00562'",
    ):
        _validate_revision(revision)


def test_snapshot_builder_rejects_ambiguous_selected_revision_identity() -> None:
    """Even direct snapshot construction must fail before publishing ambiguous casilla refs."""
    canonical_owner = segmented_casilla(_BARE_REUSED_NUMBER_CASILLA, "00563", None)
    display_owner = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    revision = minimal_revision(casillas=(canonical_owner, display_owner))

    with pytest.raises(RegistryValidationError, match="casilla reference token '00562' is ambiguous"):
        build_minimal_snapshot(revision)


def test_bare_number_reference_does_not_resolve_when_id_is_segment_qualified() -> None:
    """A bare number is not a reference shorthand for a segment-qualified casilla.

    ``CasillaDefinition.number`` is AEAT/display metadata, not a
    foreign key. Even when a printed number occurs exactly once in the
    revision, a reference to a segment-qualified casilla must name the
    canonical ``casilla.id``.
    """
    sole_occurrence = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    target_casilla_def = segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_BARE_REUSED_NUMBER_CASILLA),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        source_citations=(_REFERENCE_FORMULA_CITATION,),
    )
    revision = minimal_revision(
        casillas=(sole_occurrence, target_casilla_def),
        formulas=(formula,),
        application_links=_FORMULA_REVISION_APPLICATION_LINKS,
    )
    with pytest.raises(RegistryValidationError, match="unknown casilla '00562'"):
        _validate_revision(revision)


def test_duplicate_export_field_ownership_fails() -> None:
    """An export field can be declared by exactly one casilla."""
    first = segmented_casilla(_SEGMENTED_EXPORT_FIELD_CASILLA, "00592", "DP200014").model_copy(
        update={"export_refs": ("modelo-200-page-014b-casilla-00592",)},
    )
    second = segmented_casilla(_BARE_EXPORT_FIELD_CASILLA, "00592", None).model_copy(
        update={"export_refs": ("modelo-200-page-014b-casilla-00592",)},
    )
    revision = minimal_revision(casillas=(first, second))
    with pytest.raises(RegistryValidationError, match="is declared by multiple casillas"):
        _validate_revision(revision)

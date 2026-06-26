"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

import pytest

from .. import CasillaId, validated_casilla_id
from .._schema_input_kind import InputKind
from ._referential_integrity_support import (
    _DUMMY_LEGAL_ID,
    _DUMMY_SOURCE_ID,
    CalculationCompletenessCasilla,
    CasillaDefinition,
    RegistryValidationError,
    ValidationError,
    _completeness_manifest,
    _minimal_casilla,
    _minimal_catalogues,
    _minimal_modelo,
    _minimal_revision,
    _segmented_casilla,
    _single_segment_casilla,
    freeze_toml,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_NUMERIC_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_NUMERIC_CASILLA_01")
_NUMERIC_CASILLA_02: CasillaId = validated_casilla_id("02", surface="_NUMERIC_CASILLA_02")
_SEGMENTED_LIQUIDACION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_SEGMENTED_LIQUIDACION_CASILLA",
)
_SEGMENTED_ECPN_CASILLA: CasillaId = validated_casilla_id(
    "DP200032:00562",
    surface="_SEGMENTED_ECPN_CASILLA",
)
_SEGMENTED_TARGET_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00999",
    surface="_SEGMENTED_TARGET_CASILLA",
)


def test_segment_qualified_reference_resolves_across_segments() -> None:
    """A formula naming a casilla by its segment-qualified id resolves cleanly.

    With number 00562 reused across two segments, a formula expression
    that references the segment-qualified id 'DP200014:00562' resolves to
    the intended Liquidacion occurrence and produces no unknown-casilla
    failure.
    """
    from .._schema import FormulaDefinition, FormulaExpression
    from .._validate import RegistryValidator

    liquidacion = _segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = _segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    target_casilla_def = _segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_SEGMENTED_LIQUIDACION_CASILLA),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    revision = _minimal_revision(
        casillas=(liquidacion, ecpn, target_casilla_def),
        formulas=(formula,),
    )
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(
        _minimal_modelo(revision),
        revision,
    )
    unknown_casilla_failures = [f for f in failures if "unknown casilla" in f]
    assert unknown_casilla_failures == [], (
        f"a segment-qualified casilla reference must resolve; got: {unknown_casilla_failures}"
    )


def test_casilla_segmento_defaults_unset() -> None:
    """A single-segment casilla leaves segmento unset; the field defaults to None."""
    casilla = _single_segment_casilla()

    assert casilla.segmento is None


def test_casilla_segmento_accepts_aeat_record_segment_code() -> None:
    """A multi-segment casilla carries the AEAT record-segment code in segmento."""
    casilla = _single_segment_casilla().model_copy(update={"segmento": "DP200014"})

    assert casilla.segmento == "DP200014"


def test_single_segment_casilla_validates_unchanged_with_segmento_unset() -> None:
    """A single-segment casilla (segmento unset) survives a strict pydantic round-trip.

    The segmento field is purely additive: every existing CasillaDefinition
    that never declares segmento must validate exactly as before, with
    segmento absent from the serialised payload's meaningful state.
    """
    casilla = _single_segment_casilla()

    round_tripped = CasillaDefinition.model_validate(casilla.model_dump())

    assert round_tripped == casilla
    assert round_tripped.segmento is None
    assert "segmento" not in casilla.model_dump(exclude_defaults=True)


def test_casilla_segmento_rejects_empty_string() -> None:
    """An empty segmento is rejected so 'unset' stays distinct from 'empty'."""
    with pytest.raises(ValidationError, match="segmento"):
        CasillaDefinition.model_validate({**_single_segment_casilla().model_dump(), "segmento": ""})


def test_segmented_casilla_survives_strict_load_cycle_roundtrip() -> None:
    """A casilla carrying a non-default segmento survives the real load cycle.

    A multi-segment CasillaDefinition is fully populated — every
    defaultable field set to a non-default value, including the
    additive ``segmento`` field set to a real AEAT record-segment code —
    then pushed through the registry's genuine on-disk load transform:
    ``model_dump`` to the fragment payload shape, ``freeze_toml`` (the
    exact normalisation ``_merge_revision_fragment`` applies to every
    TOML fragment it reads), then ``model_validate`` back across the
    strict / frozen / ``extra="forbid"`` boundary. Strict pydantic
    equality across that boundary proves the additive ``segmento`` field
    is neither dropped on serialise nor re-defaulted on load.

    Populating the defaultable fields is deliberate: a
    save-drops-field / load-re-defaults-field regression on ``segmento``
    is invisible if the fixture leaves it at the ``None`` default, which
    is exactly the gap the existing segmento-unset roundtrip test cannot
    close.
    """
    casilla = CasillaDefinition(
        id=_SEGMENTED_LIQUIDACION_CASILLA,
        number="00562",
        segmento="DP200014",
        label="Liquidación III - Base imponible - Cuota íntegra [00562]",
        section=("liquidacion_iii", "base_imponible"),
        data_type="money",
        semantic_role="is_liquidacion_iii_cuota_integra",
        semantic_role_cardinality="intentional_singleton",
        semantic_role_cardinality_reason=(
            "Liquidación III cuota íntegra is the single cuota-chain integral-quota casilla within the modelo revision."
        ),
        required=False,
        input_kind=InputKind.MANUAL,
        export_refs=("modelo-200-page-014-casilla-00562",),
        legal_refs=("ley-27-2014:art-30", "ley-27-2014:art-29"),
        source_refs=("aeat-dr-200-2025", "aeat-modelo-200-manual-2024"),
    )
    assert casilla.segmento == "DP200014"

    frozen_payload = freeze_toml(casilla.model_dump(mode="python"))
    round_tripped = CasillaDefinition.model_validate(frozen_payload)

    assert round_tripped == casilla
    assert round_tripped.segmento == "DP200014"
    assert round_tripped.semantic_role == "is_liquidacion_iii_cuota_integra"


def test_revision_without_manifest_passes_completeness_gate() -> None:
    """A revision with no completeness_manifest is not failed by the gate.

    The completeness gate is rollout-staged: until a modelo's manifest is
    authored, a casilla-bearing revision must keep validating. A minimal
    revision that declares one casilla and no manifest must produce zero
    completeness-gate failures.
    """
    from .._validate import RegistryValidator

    revision = _minimal_revision(casillas=(_minimal_casilla(_NUMERIC_CASILLA_01),))
    modelo = _minimal_modelo(revision)
    # A clean return proves the manifest-less revision clears the gate.
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_passes_when_manifest_required_subset_of_declared() -> None:
    """A revision whose declared casillas cover the manifest's required set validates.

    The manifest enumerates a single required canonical casilla id; the
    revision declares exactly that casilla, so the required set is a
    subset of the declared set and the gate raises nothing.
    """
    from .._validate import RegistryValidator

    casilla = _minimal_casilla(_NUMERIC_CASILLA_01)
    manifest = _completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = _minimal_revision(casillas=(casilla,)).model_copy(update={"completeness_manifest": manifest})
    modelo = _minimal_modelo(revision)
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_passes_when_revision_declares_extra_accounting_casilla() -> None:
    """A declared casilla absent from the calculation manifest is not a failure.

    The refocused gate enforces `manifest-required ⊆ declared`, not
    `declared == manifest`. The manifest requires only calculation-closure
    casilla '01'; the revision additionally declares casilla '02', a pure
    accounting-statement data-entry field outside the calculation closure.
    The extra casilla must NOT red the gate — a modelo can clear the gate
    without an exhaustive full-Diseño backfill.
    """
    from .._validate import RegistryValidator

    manifest = _completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = _minimal_revision(
        casillas=(_minimal_casilla(_NUMERIC_CASILLA_01), _minimal_casilla(_NUMERIC_CASILLA_02)),
    ).model_copy(
        update={"completeness_manifest": manifest},
    )
    modelo = _minimal_modelo(revision)
    # A clean return proves the extra accounting casilla does not fail.
    RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_missing_required_casilla() -> None:
    """A manifest requiring a casilla the revision omits hard-fails the gate.

    The manifest requires calculation-closure casilla ids '01' and '02'
    but the revision declares only '01'. The completeness gate must
    report the missing required '02' as a hard RegistryValidationError.
    """
    from .._validate import RegistryValidator

    manifest = _completeness_manifest(
        (
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_02, number="02"),
        ),
    )
    revision = _minimal_revision(casillas=(_minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest},
    )
    modelo = _minimal_modelo(revision)
    with pytest.raises(
        RegistryValidationError,
        match=(
            r"calculation-completeness manifest requires casilla\.id '02' "
            r"but the revision does not declare it"
        ),
    ):
        RegistryValidator(_minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_manifest_metadata_mismatch() -> None:
    """A manifest whose metadata disagrees with its casilla id hard-fails the gate.

    The manifest resolves by canonical casilla id DP200014:00562, then
    verifies the retained record-design metadata. If the manifest says
    that id belongs under DP200032, validation must fail as a metadata
    mismatch instead of treating DP200032:00562 as a second address.
    """
    from .._validate import RegistryValidator

    declared = _segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    manifest = _completeness_manifest(
        (
            CalculationCompletenessCasilla(
                casilla_id=_SEGMENTED_LIQUIDACION_CASILLA,
                number="00562",
                segmento="DP200032",
            ),
        ),
    )
    revision = _minimal_revision(casillas=(declared,)).model_copy(update={"completeness_manifest": manifest})
    modelo = _minimal_modelo(revision)
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(modelo, revision)
    mismatch = [
        f
        for f in failures
        if "casilla.id 'DP200014:00562' metadata mismatch" in f
        and "within segmento 'DP200032'" in f
        and "within segmento 'DP200014'" in f
    ]
    missing = [f for f in failures if "requires casilla.id" in f]
    assert mismatch, f"manifest metadata mismatch must be reported; got: {failures}"
    assert not missing, f"the manifest id resolves, so this must not be reported as missing; got: {failures}"


def test_completeness_gate_fails_on_ungrounded_required_casilla() -> None:
    """A required casilla declared without legal/source grounding hard-fails the gate.

    The manifest requires calculation-closure casilla '01'. The revision
    declares casilla '01' but without `legal_refs` and `source_refs` — a
    casilla constructed via ``model_construct`` to bypass the schema's
    non-empty-refs validator and reach the gate's defensive grounding
    branch. The gate must report the required casilla as ungrounded.

    This proves the gate's grounding check is load-bearing: the contract
    amendment requires every calculation-closure casilla to carry its
    `legal_refs` / `source_refs` provenance, and the gate enforces that
    independently of the schema-level field constraint.
    """
    from .._validate import RegistryValidator

    ungrounded = CasillaDefinition.model_construct(
        id=_NUMERIC_CASILLA_01,
        number="01",
        segmento=None,
        label="Casilla 01",
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(),
        source_refs=(),
    )
    manifest = _completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = _minimal_revision(casillas=(_minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest, "casillas": (ungrounded,)},
    )
    modelo = _minimal_modelo(revision)
    failures = RegistryValidator(_minimal_catalogues())._validate_revision(modelo, revision)
    legal = [f for f in failures if "casilla.id '01'" in f and "without legal_refs" in f]
    source = [f for f in failures if "casilla.id '01'" in f and "without source_refs" in f]
    assert legal, f"ungrounded required casilla must be reported without legal_refs; got: {failures}"
    assert source, f"ungrounded required casilla must be reported without source_refs; got: {failures}"


def test_filing_modelo_with_formula_passes_invariant() -> None:
    """A filing modelo that declares a formula is not rejected by the informative invariant.

    Calls the invariant check directly because the full validate_modelo surface also
    enforces source-citation and calculation-link requirements that a minimal
    FormulaDefinition does not satisfy.  The invariant under test is solely concerned
    with calculation_class discrimination.
    """
    from .._schema import FormulaDefinition, FormulaExpression
    from .._validate_revision_rules import validate_informative_class_invariant

    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_01,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    computed_casilla = _minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    revision = _minimal_revision(
        casillas=(computed_casilla,),
        formulas=(formula,),
    )
    filing_modelo = _minimal_modelo(revision)  # default calculation_class == "filing"
    # The informative invariant must return no failures for a filing modelo.
    failures = validate_informative_class_invariant(filing_modelo)
    assert failures == [], f"filing modelo must not be rejected by informative invariant; got: {failures}"

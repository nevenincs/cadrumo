"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

import pytest

from .....core import CasillaId, validated_casilla_id
from ..record_design_coverage import calculation_closure_casilla_ids
from ..schema import CasillaContinuidadEvolutionDefinition, ModeloDefinition, RegistryCatalogues
from ..schema_input_kind import InputKind
from ..validate import RegistryValidator
from ._record_design_support import _committed_registry_tree
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    CalculationCompletenessCasilla,
    CasillaDefinition,
    RegistryValidationError,
    ValidationError,
    build_snapshot_with_missing_legal,
    build_snapshot_with_missing_source,
    check_all_id_references,
    completeness_manifest,
    freeze_toml,
    minimal_casilla,
    minimal_catalogues,
    minimal_legal_ref,
    minimal_modelo,
    minimal_revision,
    minimal_source_ref,
    segmented_casilla,
    single_segment_casilla,
    snapshot_for_revision,
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
_MISSING_LEGAL_ID = "ley-35-2006:art-9999"
_MISSING_SOURCE_ID = "aeat-missing-source"
_EXTRA_LEGAL_ID = "ley-35-2006:art-9998"
_EXTRA_SOURCE_ID = "aeat-extra-source"
_PARITY_SOURCE_ID = "aeat-open-parity-source"


def _modelo_validation_failures(modelo: ModeloDefinition) -> list[str]:
    try:
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)
    except RegistryValidationError as exc:
        return str(exc).splitlines()
    return []


def _catalogues_with_executable_parity_source() -> RegistryCatalogues:
    parity_source = minimal_source_ref().model_copy(
        update={
            "id": _PARITY_SOURCE_ID,
            "evidence_tier": "executable_parity_evidence",
        },
    )
    catalogues = minimal_catalogues()
    return RegistryCatalogues(
        legal=catalogues.legal,
        sources={**catalogues.sources, _PARITY_SOURCE_ID: parity_source},
    )


def test_segment_qualified_reference_resolves_across_segments() -> None:
    """A formula naming a casilla by its segment-qualified id resolves cleanly.

    With number 00562 reused across two segments, a formula expression
    that references the segment-qualified id 'DP200014:00562' resolves to
    the intended Liquidacion occurrence and produces no unknown-casilla
    failure.
    """
    from ..schema import FormulaDefinition, FormulaExpression

    liquidacion = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    ecpn = segmented_casilla(_SEGMENTED_ECPN_CASILLA, "00562", "DP200032")
    target_casilla_def = segmented_casilla(_SEGMENTED_TARGET_CASILLA, "00999", "DP200014").model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_SEGMENTED_TARGET_CASILLA,
        expression=FormulaExpression(casilla_id=_SEGMENTED_LIQUIDACION_CASILLA),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    manifest = completeness_manifest(
        (
            CalculationCompletenessCasilla(
                casilla_id=_SEGMENTED_LIQUIDACION_CASILLA,
                number="00562",
                segmento="DP200014",
            ),
            CalculationCompletenessCasilla(
                casilla_id=_SEGMENTED_TARGET_CASILLA,
                number="00999",
                segmento="DP200014",
            ),
        ),
    )
    revision = minimal_revision(
        casillas=(liquidacion, ecpn, target_casilla_def),
        formulas=(formula,),
    ).model_copy(
        update={"completeness_manifest": manifest},
    )
    failures = _modelo_validation_failures(minimal_modelo(revision))
    unknown_casilla_failures = [f for f in failures if "unknown casilla" in f]
    assert unknown_casilla_failures == [], (
        f"a segment-qualified casilla reference must resolve; got: {unknown_casilla_failures}"
    )


def test_casilla_segmento_defaults_unset() -> None:
    """A single-segment casilla leaves segmento unset; the field defaults to None."""
    casilla = single_segment_casilla()

    assert casilla.segmento is None


def test_casilla_segmento_accepts_aeat_record_segment_code() -> None:
    """A multi-segment casilla carries the AEAT record-segment code in segmento."""
    casilla = single_segment_casilla().model_copy(update={"segmento": "DP200014"})

    assert casilla.segmento == "DP200014"


def test_single_segment_casilla_validates_unchanged_with_segmento_unset() -> None:
    """A single-segment casilla (segmento unset) survives a strict pydantic round-trip.

    The segmento field is purely additive: every existing CasillaDefinition
    that never declares segmento must validate exactly as before, with
    segmento absent from the serialised payload's meaningful state.
    """
    casilla = single_segment_casilla()

    round_tripped = CasillaDefinition.model_validate(
        {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
    )

    assert round_tripped == casilla
    assert round_tripped.segmento is None
    assert "segmento" not in casilla.model_dump(exclude_defaults=True)


def test_casilla_segmento_rejects_empty_string() -> None:
    """An empty segmento is rejected so 'unset' stays distinct from 'empty'."""
    with pytest.raises(ValidationError, match="segmento"):
        CasillaDefinition.model_validate({**single_segment_casilla().model_dump(), "segmento": ""})


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
        localization_keys=("test.schema.casilla.label",),
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
    round_tripped = CasillaDefinition.model_validate(
        {**frozen_payload, "localization_keys": casilla.localization_keys},
    )

    assert round_tripped == casilla
    assert round_tripped.segmento == "DP200014"
    assert round_tripped.semantic_role == "is_liquidacion_iii_cuota_integra"


def test_revision_without_calculation_closure_passes_without_completeness_manifest() -> None:
    """A revision with no calculation closure does not need a completeness manifest.

    Informative/no-calculation revisions remain valid without a
    completeness manifest. The fail-closed rule applies only once a
    revision has a formula/binding/relation/verification calculation
    closure.
    """
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),))
    modelo = minimal_modelo(revision)
    # A clean return proves no-calculation revisions are not forced to author an empty manifest.
    RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_calculation_bearing_revision_without_manifest_fails_closed() -> None:
    """A revision with a calculation closure must declare a completeness manifest."""
    from ..schema import FormulaDefinition, FormulaExpression

    input_casilla = minimal_casilla(_NUMERIC_CASILLA_01)
    computed_casilla = minimal_casilla(_NUMERIC_CASILLA_02).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_02,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(input_casilla, computed_casilla), formulas=(formula,))
    modelo = minimal_modelo(revision)

    with pytest.raises(
        RegistryValidationError,
        match="calculation-bearing revision declares no calculation-completeness manifest",
    ):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_bundled_manifest_rejects_omitted_non_internal_closure_casilla() -> None:
    """A bundled-corpus manifest cannot omit one of its non-internal closure casillas."""
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == "200")
    revision = next(iter(modelo.revisions.values()))
    manifest = revision.completeness_manifest
    assert manifest is not None

    closure = calculation_closure_casilla_ids(revision, modelo.id)
    omittable = tuple(
        casilla
        for casilla in sorted(revision.casillas, key=lambda item: item.id)
        if casilla.id in closure and not casilla.internal_only
    )
    assert omittable, "bundled Modelo 200 must expose a non-internal calculation-closure casilla"
    omitted = omittable[0]
    malformed_manifest = manifest.model_copy(
        update={
            "casillas": tuple(casilla for casilla in manifest.casillas if casilla.casilla_id != omitted.id),
        },
    )
    malformed_revision = revision.model_copy(update={"completeness_manifest": malformed_manifest})
    malformed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, malformed_revision.id: malformed_revision}},
    )

    with pytest.raises(RegistryValidationError) as caught:
        RegistryValidator(catalogues).validate_modelo(malformed_modelo)

    assert (
        f"calculation-completeness manifest omits non-internal calculation-closure casilla ids: {omitted.id!r}"
        in str(caught.value)
    )


def test_bundled_manifest_refuses_internal_only_closure_casillas() -> None:
    """Internal calculation nodes cannot become official manifest denominator rows."""
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == "200")
    revision = next(iter(modelo.revisions.values()))
    manifest = revision.completeness_manifest
    assert manifest is not None

    closure = calculation_closure_casilla_ids(revision, modelo.id)
    internal_closure_ids = {
        casilla.id for casilla in revision.casillas if casilla.id in closure and casilla.internal_only
    }
    assert internal_closure_ids, "bundled Modelo 200 must exercise an internal-only calculation node"
    assert internal_closure_ids.isdisjoint(manifest_casilla.casilla_id for manifest_casilla in manifest.casillas)
    internal = next(casilla for casilla in revision.casillas if casilla.id in internal_closure_ids)
    manifest_with_internal = manifest.model_copy(
        update={
            "casillas": (
                *manifest.casillas,
                CalculationCompletenessCasilla(
                    casilla_id=internal.id,
                    segmento=internal.segmento,
                    number=internal.number,
                ),
            ),
        },
    )
    malformed_revision = revision.model_copy(update={"completeness_manifest": manifest_with_internal})
    malformed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, malformed_revision.id: malformed_revision}},
    )

    with pytest.raises(RegistryValidationError, match="manifest includes internal-only"):
        RegistryValidator(catalogues).validate_modelo(malformed_modelo)


def test_completeness_gate_passes_when_manifest_required_subset_of_declared() -> None:
    """A revision whose declared casillas cover the manifest's required set validates.

    The manifest enumerates a single required canonical casilla id; the
    revision declares exactly that casilla, so the required set is a
    subset of the declared set and the gate raises nothing.
    """
    casilla = minimal_casilla(_NUMERIC_CASILLA_01)
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = minimal_revision(casillas=(casilla,)).model_copy(update={"completeness_manifest": manifest})
    modelo = minimal_modelo(revision)
    RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_passes_when_revision_declares_extra_accounting_casilla() -> None:
    """A declared casilla absent from the calculation manifest is not a failure.

    The refocused gate enforces `manifest-required ⊆ declared`, not
    `declared == manifest`. The manifest requires only calculation-closure
    casilla '01'; the revision additionally declares casilla '02', a pure
    accounting-statement data-entry field outside the calculation closure.
    The extra casilla must NOT red the gate — a modelo can clear the gate
    without an exhaustive full-Diseño backfill.
    """
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = minimal_revision(
        casillas=(minimal_casilla(_NUMERIC_CASILLA_01), minimal_casilla(_NUMERIC_CASILLA_02)),
    ).model_copy(
        update={"completeness_manifest": manifest},
    )
    modelo = minimal_modelo(revision)
    # A clean return proves the extra accounting casilla does not fail.
    RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_missing_required_casilla() -> None:
    """A manifest requiring a casilla the revision omits hard-fails the gate.

    The manifest requires calculation-closure casilla ids '01' and '02'
    but the revision declares only '01'. The completeness gate must
    report the missing required '02' as a hard RegistryValidationError.
    """
    manifest = completeness_manifest(
        (
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),
            CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_02, number="02"),
        ),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest},
    )
    modelo = minimal_modelo(revision)
    with pytest.raises(
        RegistryValidationError,
        match=(
            r"calculation-completeness manifest requires casilla\.id '02' "
            r"but the revision does not declare it"
        ),
    ):
        RegistryValidator(minimal_catalogues()).validate_modelo(modelo)


def test_completeness_gate_fails_on_manifest_metadata_mismatch() -> None:
    """A manifest whose metadata disagrees with its casilla id hard-fails the gate.

    The manifest resolves by canonical casilla id DP200014:00562, then
    verifies the retained record-design metadata. If the manifest says
    that id belongs under DP200032, validation must fail as a metadata
    mismatch instead of treating DP200032:00562 as a second address.
    """
    declared = segmented_casilla(_SEGMENTED_LIQUIDACION_CASILLA, "00562", "DP200014")
    manifest = completeness_manifest(
        (
            CalculationCompletenessCasilla(
                casilla_id=_SEGMENTED_LIQUIDACION_CASILLA,
                number="00562",
                segmento="DP200032",
            ),
        ),
    )
    revision = minimal_revision(casillas=(declared,)).model_copy(update={"completeness_manifest": manifest})
    modelo = minimal_modelo(revision)
    failures = _modelo_validation_failures(modelo)
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
    ungrounded = CasillaDefinition.model_construct(
        id=_NUMERIC_CASILLA_01,
        number="01",
        segmento=None,
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        input_kind=InputKind.MANUAL,
        legal_refs=(),
        source_refs=(),
    )
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest, "casillas": (ungrounded,)},
    )
    modelo = minimal_modelo(revision)
    failures = _modelo_validation_failures(modelo)
    legal = [f for f in failures if "casilla.id '01'" in f and "without legal_refs" in f]
    source = [f for f in failures if "casilla.id '01'" in f and "without source_refs" in f]
    assert legal, f"ungrounded required casilla must be reported without legal_refs; got: {failures}"
    assert source, f"ungrounded required casilla must be reported without source_refs; got: {failures}"


def test_completeness_manifest_refs_must_resolve_in_registry_validation() -> None:
    """Manifest-level legal/source refs are load-blocking catalogue references."""
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    ).model_copy(
        update={
            "legal_refs": (_MISSING_LEGAL_ID,),
            "source_ref": _MISSING_SOURCE_ID,
            "source_refs": (_MISSING_SOURCE_ID,),
        },
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest},
    )

    failures = _modelo_validation_failures(minimal_modelo(revision))

    assert any(
        "calculation-completeness manifest references unknown legal id 'ley-35-2006:art-9999'" in failure
        for failure in failures
    ), f"manifest legal_refs must be checked against the legal catalogue; got: {failures}"
    assert any(
        "calculation-completeness manifest references unknown source id 'aeat-missing-source'" in failure
        for failure in failures
    ), f"manifest source_refs must be checked against the source catalogue; got: {failures}"


def test_modelo_validation_rejects_manifest_sourced_only_by_executable_parity() -> None:
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    ).model_copy(
        update={"source_ref": _PARITY_SOURCE_ID, "source_refs": (_PARITY_SOURCE_ID,)},
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"completeness_manifest": manifest},
    )

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"calculation-completeness manifest "
            r"requires one of official_source_guidance, layout_authority source evidence"
        ),
    ):
        RegistryValidator(_catalogues_with_executable_parity_source()).validate_modelo(minimal_modelo(revision))


def test_casilla_continuidad_evolution_refs_must_resolve_in_registry_validation() -> None:
    """Continuity-evolution legal/source refs are load-blocking catalogue references."""
    evolution = CasillaContinuidadEvolutionDefinition(
        id="test-continuidad-2024-2025",
        continuidad_id="test-continuidad",
        from_revision="2024",
        to_revision="2025",
        evolution_kind="label_evolved",
        legal_refs=(_MISSING_LEGAL_ID,),
        source_refs=(_MISSING_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"casilla_continuidad_evolutions": (evolution,)},
    )

    failures = _modelo_validation_failures(minimal_modelo(revision))

    assert any(
        "casilla continuidad evolution 'test-continuidad-2024-2025' "
        "references unknown legal id 'ley-35-2006:art-9999'" in failure
        for failure in failures
    ), f"continuity evolution legal_refs must be checked against the legal catalogue; got: {failures}"
    assert any(
        "casilla continuidad evolution 'test-continuidad-2024-2025' references unknown source id "
        "'aeat-missing-source'" in failure
        for failure in failures
    ), f"continuity evolution source_refs must be checked against the source catalogue; got: {failures}"


def test_modelo_validation_rejects_continuity_evolution_sourced_only_by_executable_parity() -> None:
    evolution = CasillaContinuidadEvolutionDefinition(
        id="test-continuidad-2024-2025",
        continuidad_id="test-continuidad",
        from_revision="2024",
        to_revision="2025",
        evolution_kind="label_evolved",
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(_PARITY_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"casilla_continuidad_evolutions": (evolution,)},
    )

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"casilla continuidad evolution 'test-continuidad-2024-2025' "
            r"requires one of official_source_guidance, layout_authority source evidence"
        ),
    ):
        RegistryValidator(_catalogues_with_executable_parity_source()).validate_modelo(minimal_modelo(revision))


def test_snapshot_carries_manifest_and_continuity_refs() -> None:
    """Slice snapshots retain manifest and continuity-evolution legal/source evidence."""
    manifest = completeness_manifest(
        (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
    ).model_copy(
        update={
            "legal_refs": (_EXTRA_LEGAL_ID,),
            "source_ref": _EXTRA_SOURCE_ID,
            "source_refs": (_EXTRA_SOURCE_ID,),
        },
    )
    evolution = CasillaContinuidadEvolutionDefinition(
        id="test-continuidad-2024-2025",
        continuidad_id="test-continuidad",
        from_revision="2024",
        to_revision="2025",
        evolution_kind="legal_refs_evolved",
        legal_refs=(_EXTRA_LEGAL_ID,),
        source_refs=(_EXTRA_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={
            "completeness_manifest": manifest,
            "casilla_continuidad_evolutions": (evolution,),
        },
    )
    catalogues = minimal_catalogues()
    catalogues = RegistryCatalogues(
        legal={
            **catalogues.legal,
            _EXTRA_LEGAL_ID: minimal_legal_ref().model_copy(update={"id": _EXTRA_LEGAL_ID}),
        },
        sources={
            **catalogues.sources,
            _EXTRA_SOURCE_ID: minimal_source_ref().model_copy(update={"id": _EXTRA_SOURCE_ID}),
        },
    )

    snapshot = snapshot_for_revision(minimal_modelo(revision), catalogues, revision)

    assert _EXTRA_LEGAL_ID in snapshot.legal
    assert _EXTRA_SOURCE_ID in snapshot.sources
    check_all_id_references(snapshot)


def test_snapshot_integrity_checks_completeness_manifest_refs() -> None:
    """Snapshot integrity rejects manifest refs missing from the slice catalogue."""
    cases = (
        (
            {"legal_refs": (REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID)},
            build_snapshot_with_missing_legal,
            _MISSING_LEGAL_ID,
            r"calculation_completeness_manifest\.legal_refs",
        ),
        (
            {"source_ref": _MISSING_SOURCE_ID, "source_refs": (_MISSING_SOURCE_ID,)},
            build_snapshot_with_missing_source,
            _MISSING_SOURCE_ID,
            r"calculation_completeness_manifest\.source_ref",
        ),
    )
    for manifest_update, snapshot_builder, missing_ref, match in cases:
        manifest = completeness_manifest(
            (CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),),
        ).model_copy(update=manifest_update)
        revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
            update={"completeness_manifest": manifest},
        )
        snapshot = snapshot_builder(revision, missing_ref)

        with pytest.raises(RegistryValidationError, match=match):
            check_all_id_references(snapshot)


def test_snapshot_integrity_checks_casilla_continuidad_evolution_refs() -> None:
    """Snapshot integrity rejects continuity-evolution refs missing from the slice catalogue."""
    evolution = CasillaContinuidadEvolutionDefinition(
        id="test-continuidad-2024-2025",
        continuidad_id="test-continuidad",
        from_revision="2024",
        to_revision="2025",
        evolution_kind="label_evolved",
        legal_refs=(REFERENCE_LEGAL_ID, _MISSING_LEGAL_ID),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(minimal_casilla(_NUMERIC_CASILLA_01),)).model_copy(
        update={"casilla_continuidad_evolutions": (evolution,)},
    )
    snapshot = build_snapshot_with_missing_legal(revision, _MISSING_LEGAL_ID)

    with pytest.raises(RegistryValidationError, match=r"casilla_continuidad_evolution test-continuidad-2024-2025"):
        check_all_id_references(snapshot)


def test_filing_modelo_with_formula_passes_invariant() -> None:
    """A filing modelo that declares a formula is not rejected by the informative invariant.

    Calls the invariant check directly because the full validate_modelo surface also
    enforces source-citation and calculation-link requirements that a minimal
    FormulaDefinition does not satisfy.  The invariant under test is solely concerned
    with calculation_class discrimination.
    """
    from ..schema import FormulaDefinition, FormulaExpression
    from .._validate_revision_rules import validate_informative_class_invariant

    formula = FormulaDefinition(
        id="test.formula",
        target_casilla_id=_NUMERIC_CASILLA_01,
        expression=FormulaExpression(casilla_id=_NUMERIC_CASILLA_01),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    computed_casilla = minimal_casilla(_NUMERIC_CASILLA_01).model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "test.formula"},
    )
    revision = minimal_revision(
        casillas=(computed_casilla,),
        formulas=(formula,),
    )
    filing_modelo = minimal_modelo(revision)  # default calculation_class == "filing"
    # The informative invariant must return no failures for a filing modelo.
    failures = validate_informative_class_invariant(filing_modelo)
    assert failures == [], f"filing modelo must not be rejected by informative invariant; got: {failures}"

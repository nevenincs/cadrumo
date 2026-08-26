"""Real source contracts for the Modelo 303 annual Orden compiler."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .....domain.iva import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ..authority import bundled_authority
from ..errors import RegistryLoadError, RegistryValidationError
from ..m303_orden_manifest import (
    check_m303_annual_orden_manifest,
    load_m303_annual_orden_authority,
)
from ..m303_orden_projection_models import M303AnnualOrdenProjection
from ..m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ..m303_orden_source import extract_m303_annual_orden_source
from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    (
        "ejercicio",
        "source_ref",
        "expected_digest",
        "expected_agricultural_axis_count",
        "expects_lorca_2022_reduction",
    ),
    (
        (
            2022,
            "boe-orden-hfp-1335-2021-iva-authority",
            "29f6edf412129634c9cf16a9a60aede5fe0f962a8489e8e6f2efe7bd0e104c5a",
            16,
            True,
        ),
        (
            2023,
            "boe-orden-hfp-1172-2022-iva-authority",
            "1cab2ef540868ec0d5344d8e801ac6c52b5ee27c1aefb794ca7c0330df693957",
            16,
            False,
        ),
        (
            2024,
            "boe-orden-hfp-1359-2023-iva-authority",
            "e403d33762cc7353ca3f752820df71244291217aeb35309d5e383f166cde49a5",
            16,
            False,
        ),
        (
            2025,
            "boe-orden-hac-1347-2024-iva-authority",
            "fca55fa51ca1b68e4b8098ebfc4749e4d5f9daac880112d35085352df46c8165",
            17,
            False,
        ),
        (
            2026,
            "boe-orden-hac-1425-2025-iva-authority",
            "7762218c63fcc914dfc5ed532d6c0daa3b21f506427c924b93eb2698527d3ac8",
            17,
            False,
        ),
    ),
)
def test_pinned_boe_orden_compiler_extracts_the_complete_annual_iva_catalogue(
    ejercicio: int,
    source_ref: str,
    expected_digest: str,
    expected_agricultural_axis_count: int,
    expects_lorca_2022_reduction: bool,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Each pinned BOE source supplies all 49 tables and 141 module rows."""
    _, catalogues = registry_tree

    census = extract_m303_annual_orden_source(
        ejercicio=ejercicio,
        source=catalogues.sources[source_ref],
        source_root=bundled_path(),
    )

    assert len(census.activities) == 49
    assert {activity.annex_heading for activity in census.activities} == {"ANEXO II"}
    assert sum(len(activity.modules) for activity in census.activities) == 141
    assert Counter(len(activity.modules) for activity in census.activities) == {
        1: 2,
        2: 25,
        3: 12,
        4: 4,
        5: 1,
        6: 3,
        7: 2,
    }
    assert len(census.agricultural_indexes) == expected_agricultural_axis_count
    assert len(census.agricultural_ingresos_a_cuenta) == expected_agricultural_axis_count
    assert len(census.non_agricultural_ingresos_a_cuenta) == 47
    assert tuple((item.minimum_days, item.maximum_days, item.coefficient) for item in census.seasonal_indexes) == (
        (1, 60, Decimal("1.50")),
        (61, 120, Decimal("1.35")),
        (121, 180, Decimal("1.25")),
    )
    assert census.difficult_justification.percentage == 1
    if expects_lorca_2022_reduction:
        assert census.lorca_2022_reduction is not None
        assert census.lorca_2022_reduction.municipality == "Lorca"
        assert census.lorca_2022_reduction.percentage == 20
        assert "anexo II de esta Orden" in census.lorca_2022_reduction.required_text[1]
        assert "cuota trimestral" in census.lorca_2022_reduction.required_text[2]
        assert "cuota anual" in census.lorca_2022_reduction.required_text[2]
    else:
        assert census.lorca_2022_reduction is None
    assert (
        sha256(
            json.dumps(
                census.activities,
                default=lambda value: value.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        ).hexdigest()
        == expected_digest
    )


def test_pinned_boe_orden_compiler_refuses_a_real_truncated_copy(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A copied source whose bytes no longer match its pinned digest cannot compile."""
    _, catalogues = registry_tree
    source = catalogues.sources["boe-orden-hac-1425-2025-iva-authority"]
    copied_path = tmp_path / source.corpus_path
    copied_path.parent.mkdir(parents=True)
    copyfile(bundled_path() / source.corpus_path, copied_path)
    copied_path.write_bytes(copied_path.read_bytes()[:1000])

    with pytest.raises(RegistryLoadError, match="digest mismatch"):
        extract_m303_annual_orden_source(
            ejercicio=2026,
            source=source,
            source_root=tmp_path,
        )


def test_pinned_boe_orden_compiler_refuses_a_divergent_markdown_sidecar(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The committed Markdown and JSON sidecars are one inseparable generated pair."""
    _, catalogues = registry_tree
    source = catalogues.sources["boe-orden-hac-1425-2025-iva-authority"]
    source_path = bundled_path() / source.corpus_path
    copied_path = tmp_path / source.corpus_path
    copied_path.parent.mkdir(parents=True)
    copyfile(source_path, copied_path)
    copyfile(
        source_path.with_name(source_path.name + ".extracted.json"),
        copied_path.with_name(copied_path.name + ".extracted.json"),
    )
    markdown_path = copied_path.with_name(copied_path.name + ".extracted.md")
    copyfile(source_path.with_name(source_path.name + ".extracted.md"), markdown_path)
    markdown_path.write_text(markdown_path.read_text(encoding="utf-8") + "\ncorrupt", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="sidecar pair diverges"):
        extract_m303_annual_orden_source(
            ejercicio=2026,
            source=source,
            source_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("field", "unknown_scope"),
    (
        ("schema_version", None),
        ("source_kind", None),
        ("status", None),
        ("source_relpath", None),
        ("attribution", None),
        ("unknown_top_level", "top"),
        ("unknown_unit", "unit"),
    ),
)
def test_pinned_boe_orden_compiler_refuses_noncanonical_sidecar_shape(
    tmp_path: Path,
    field: str,
    unknown_scope: str | None,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Copied sidecars must retain the exact canonical envelope and unit shapes."""
    _, catalogues = registry_tree
    source = catalogues.sources["boe-orden-hac-1425-2025-iva-authority"]
    source_path = bundled_path() / source.corpus_path
    copied_path = tmp_path / source.corpus_path
    copied_path.parent.mkdir(parents=True)
    copyfile(source_path, copied_path)
    json_source = source_path.with_name(source_path.name + ".extracted.json")
    json_copy = copied_path.with_name(copied_path.name + ".extracted.json")
    payload = json.loads(json_source.read_text(encoding="utf-8"))
    if unknown_scope == "top":
        payload[field] = "forbidden"
    elif unknown_scope == "unit":
        payload["units"][0][field] = "forbidden"
    else:
        del payload[field]
    json_copy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    copyfile(
        source_path.with_name(source_path.name + ".extracted.md"),
        copied_path.with_name(copied_path.name + ".extracted.md"),
    )

    with pytest.raises(RegistryLoadError, match="sidecar"):
        extract_m303_annual_orden_source(
            ejercicio=2026,
            source=source,
            source_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("invalid_value", "expected_refusal"),
    (
        ([], "contains a non-object unit"),
        (7, "contains a non-text unit"),
    ),
)
def test_pinned_boe_orden_compiler_refuses_invalid_units_before_pair_comparison(
    tmp_path: Path,
    invalid_value: object,
    expected_refusal: str,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Unit-envelope defects retain precedence over the sidecar-pair comparison."""
    _, catalogues = registry_tree
    source = catalogues.sources["boe-orden-hac-1425-2025-iva-authority"]
    source_path = bundled_path() / source.corpus_path
    copied_path = tmp_path / source.corpus_path
    copied_path.parent.mkdir(parents=True)
    copyfile(source_path, copied_path)
    json_source = source_path.with_name(source_path.name + ".extracted.json")
    json_copy = copied_path.with_name(copied_path.name + ".extracted.json")
    payload = json.loads(json_source.read_text(encoding="utf-8"))
    if isinstance(invalid_value, list):
        payload["units"][0] = invalid_value
    else:
        payload["units"][0]["anchor"] = invalid_value
    json_copy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    copyfile(
        source_path.with_name(source_path.name + ".extracted.md"),
        copied_path.with_name(copied_path.name + ".extracted.md"),
    )

    with pytest.raises(RegistryLoadError, match=expected_refusal):
        extract_m303_annual_orden_source(
            ejercicio=2026,
            source=source,
            source_root=tmp_path,
        )


def test_pinned_boe_orden_compiler_refuses_duplicate_semantic_table_anchor(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The complete sidecar pair cannot collapse two official tables onto one anchor."""
    _, catalogues = registry_tree
    source = catalogues.sources["boe-orden-hac-1425-2025-iva-authority"]
    source_path = bundled_path() / source.corpus_path
    copied_path = tmp_path / source.corpus_path
    copied_path.parent.mkdir(parents=True)
    copyfile(source_path, copied_path)
    json_source = source_path.with_name(source_path.name + ".extracted.json")
    json_copy = copied_path.with_name(copied_path.name + ".extracted.json")
    payload = json.loads(json_source.read_text(encoding="utf-8"))
    first_anchor = "#m303-anexo-ii-iva-419-1-industrias-del-pan-y-de-la-bolleria"
    second_anchor = "#m303-anexo-ii-iva-419-2-industrias-de-la-bolleria-pasteleria-y-galletas"
    second_unit = next(unit for unit in payload["units"] if unit["anchor"] == second_anchor)
    second_unit["anchor"] = first_anchor
    json_copy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    copyfile(
        source_path.with_name(source_path.name + ".extracted.md"),
        copied_path.with_name(copied_path.name + ".extracted.md"),
    )

    with pytest.raises(RegistryLoadError, match="extra, missing, or cross-year authority units"):
        extract_m303_annual_orden_source(
            ejercicio=2026,
            source=source,
            source_root=tmp_path,
        )


def test_resolved_annual_orden_snapshot_refuses_reference_coordinate_drift() -> None:
    """A reference cannot retain its Orden id while changing source provenance."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2025, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    assert resolved.orden is not None
    payload = resolved.orden.model_dump(mode="python")
    payload["activity_refs"][0]["source_content_digest"] = "0" * 64

    with pytest.raises(ValidationError, match="exact source coordinate"):
        type(resolved.orden).model_validate(payload)


def test_resolved_annual_orden_snapshot_carries_source_derived_identity_and_minimum_quota() -> None:
    """The bundled authority, not a test fixture, supplies row identity and minimum quota."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    assert resolved.orden is not None
    activity = next(item for item in resolved.orden.activities if item.orden_id == "m303:2026:iva:82e3988053fc055b601e")

    assert activity.cuota_minima_pct == 20


def test_every_pinned_annual_orden_source_has_unambiguous_iae_discriminators(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Every pinned source retains the discriminator for each repeated IAE epigraph."""
    modelos, catalogues = registry_tree
    manifest = check_m303_annual_orden_manifest(
        manifest_path=bundled_path("registry", "aeat", "m303_orden_anual", "manifest.toml"),
        source_root=bundled_path(),
        sources=catalogues.sources,
    )
    compilation = load_m303_annual_orden_authority(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        modelos=modelos,
        sources=catalogues.sources,
    )
    projections_by_source: dict[str, list[M303AnnualOrdenProjection]] = {}
    for projection in compilation.authority.projections:
        projections_by_source.setdefault(projection.source_ref, []).append(projection)

    assert set(projections_by_source) == {source.source_ref for source in manifest.sources}
    for source in manifest.sources:
        projections = projections_by_source[source.source_ref]
        assert {projection.ejercicio for projection in projections} == {source.ejercicio}
        for projection in projections:
            identities = tuple(
                (activity.iae_epigrafe, activity.auxiliary_activity_indicator)
                for activity in projection.activities
                if activity.kind == "no_agricola"
            )
            assert len(identities) == len(set(identities))
            repeated_indicators = {
                iae_epigrafe: frozenset(
                    indicator for current_iae, indicator in identities if current_iae == iae_epigrafe
                )
                for iae_epigrafe in ("691.9", "722")
            }
            assert repeated_indicators == {"691.9": frozenset({"1", "2"}), "722": frozenset({"1", "2"})}


@pytest.mark.parametrize(
    ("iae_epigrafe", "mutation"),
    (("691.9", "missing"), ("691.9", "duplicate"), ("722", "missing"), ("722", "duplicate")),
)
def test_annual_orden_projection_refuses_missing_or_duplicate_iae_discriminators(
    iae_epigrafe: str,
    mutation: str,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The live collision pairs cannot be accepted without their exact discriminator."""
    modelos, catalogues = registry_tree
    compilation = load_m303_annual_orden_authority(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        modelos=modelos,
        sources=catalogues.sources,
    )
    projection = next(item for item in compilation.authority.projections if item.ejercicio == 2026)
    payload = projection.model_dump(mode="python")
    collision_indices = [
        index for index, activity in enumerate(payload["activities"]) if activity["iae_epigrafe"] == iae_epigrafe
    ]
    assert len(collision_indices) == 2
    first, second = collision_indices
    if mutation == "missing":
        payload["activities"][first]["auxiliary_activity_indicator"] = None
    else:
        payload["activities"][second]["auxiliary_activity_indicator"] = payload["activities"][first][
            "auxiliary_activity_indicator"
        ]

    with pytest.raises(ValidationError, match="ambiguous non-agricultural activity identities"):
        type(projection).model_validate(payload)


def test_2022_snapshot_carries_lorca_authority_and_crosswalk_refusal_with_exact_sources() -> None:
    """The 2022 snapshot keeps the available reduction separate from the unavailable crosswalk."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2022, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )

    assert resolved.record_design.id == "aeat-dr-303-2022"
    reduction = resolved.orden.lorca_2022_reduction
    assert reduction is not None
    assert reduction.percentage == Decimal("20")
    assert reduction.annex_scope == "ANEXO II"
    assert reduction.calculation_periods == ("trimestral", "anual")
    assert reduction.legal_refs == ("orden-hfp-1335-2021:da-4-lorca-2022-reduction:lorca-2022-reduction",)
    assert reduction.source_refs == ("boe-orden-hfp-1335-2021-iva-authority",)
    assert reduction.source_content_digest == "3fda96dcf2dcb3b3f0863bc07b0eabd45e21c6850d4b611e635627befb450c46"

    agricultural = resolved.orden.agricultural_authority
    assert agricultural.status == "official_code_crosswalk_unavailable"
    assert agricultural.filing_record == "DP30302"
    assert agricultural.filing_code_digits == 2
    assert agricultural.annual_orden_source_ref == "boe-orden-hfp-1335-2021-iva-authority"
    assert agricultural.record_design_source_ref == "aeat-dr-303-2022"
    assert agricultural.record_design_source_content_digest == (
        "6648f6b319579e49cd5bfdaae69e7451db75767e7f19da0b90383b25b79b3f60"
    )
    assert agricultural.refusal_reason == "annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk"


def test_2022_snapshot_refuses_lorca_authority_with_a_drifted_source_reference() -> None:
    """The available Lorca rate cannot survive without its exact BOE source identity."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2022, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    payload = resolved.orden.model_dump(mode="python")
    assert payload["lorca_2022_reduction"] is not None
    payload["lorca_2022_reduction"]["source_refs"] = ("boe-orden-unrelated",)

    with pytest.raises(ValidationError, match="exact HFP/1335 source reference"):
        type(resolved.orden).model_validate(payload)


def test_2022_snapshot_refuses_a_stripped_lorca_authority_from_the_real_envelope() -> None:
    """The exact 2022 public snapshot is incomplete when its available reduction is removed."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2022, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    payload = resolved.orden.model_dump(mode="python")
    payload["lorca_2022_reduction"] = None

    with pytest.raises(ValidationError, match="2022 snapshot lacks its Lorca reduction authority"):
        type(resolved.orden).model_validate(payload)


def test_2025_snapshot_refuses_an_injected_lorca_authority_from_the_real_2022_envelope() -> None:
    """The one-year Lorca authority cannot be copied into another annual snapshot."""
    scope_decision = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    resolved_2022 = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot("303", filing_year=2022, period="4T"),
        scope_decision=scope_decision,
    )
    resolved_2025 = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot("303", filing_year=2025, period="4T"),
        scope_decision=scope_decision,
    )
    payload = resolved_2025.orden.model_dump(mode="python")
    reduction = resolved_2022.orden.lorca_2022_reduction
    assert reduction is not None
    payload["lorca_2022_reduction"] = reduction.model_dump(mode="python")

    with pytest.raises(ValidationError, match="only the 2022 annual Orden snapshot may carry the Lorca reduction"):
        type(resolved_2025.orden).model_validate(payload)


def test_2022_snapshot_refuses_coordinated_lorca_parent_and_child_source_drift() -> None:
    """A coordinated parent/child rewrite cannot replace the HFP/1335 Lorca authority."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2022, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    payload = resolved.model_dump(mode="python")
    payload["orden"]["source_ref"] = "boe-orden-hfp-1172-2022-iva-authority"
    payload["orden"]["source_content_digest"] = "3ba48312e1ae6b939de017dbcf9a34d25559594ccbc14a6da14492af87755abb"
    assert payload["orden"]["lorca_2022_reduction"] is not None
    payload["orden"]["lorca_2022_reduction"]["legal_refs"] = (
        "orden-hfp-1172-2022:da-4-lorca-2022-reduction:lorca-2022-reduction",
    )
    payload["orden"]["lorca_2022_reduction"]["source_refs"] = ("boe-orden-hfp-1172-2022-iva-authority",)
    payload["orden"]["lorca_2022_reduction"]["source_content_digest"] = (
        "3ba48312e1ae6b939de017dbcf9a34d25559594ccbc14a6da14492af87755abb"
    )

    with pytest.raises(ValidationError, match="exact HFP/1335 legal reference"):
        type(resolved).model_validate(payload)


def test_2022_snapshot_refuses_coordinated_record_design_parent_and_child_drift() -> None:
    """The crosswalk refusal cannot move with a substituted record-design envelope."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2022, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    other_snapshot = bundled_authority().snapshot("303", filing_year=2023, period="4T")
    other_resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=other_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    payload = resolved.model_dump(mode="python")
    payload["record_design"] = other_resolved.record_design.model_dump(mode="python")
    payload["orden"]["agricultural_authority"]["record_design_source_ref"] = other_resolved.record_design.id
    payload["orden"]["agricultural_authority"]["record_design_source_content_digest"] = (
        other_resolved.record_design.sha256
    )

    with pytest.raises(ValidationError, match="exact AEAT design source"):
        type(resolved).model_validate(payload)


def test_snapshot_refuses_cross_envelope_filing_year_and_record_design_drift() -> None:
    """The public snapshot retains one filing-year/revision/record-design coordinate."""
    registry_snapshot = bundled_authority().snapshot("303", filing_year=2025, period="4T")
    resolved = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=M303RegimenSimplificadoScopeDecision(
            scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
    )
    year_payload = resolved.model_dump(mode="python")
    year_payload["filing_year"] = 2026
    with pytest.raises(ValidationError, match="filing year and revision coordinate"):
        type(resolved).model_validate(year_payload)

    record_design_payload = resolved.model_dump(mode="python")
    record_design_payload["orden"]["agricultural_authority"]["record_design_source_ref"] = "aeat-dr-303-2022"
    record_design_payload["orden"]["agricultural_authority"]["record_design_source_content_digest"] = (
        "6648f6b319579e49cd5bfdaae69e7451db75767e7f19da0b90383b25b79b3f60"
    )
    with pytest.raises(ValidationError, match="resolved record-design source"):
        type(resolved).model_validate(record_design_payload)


def test_generated_directory_refuses_an_extra_toml_file(
    tmp_path: Path,
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A parallel hand-authored taxonomy cannot coexist with the generated manifest."""
    _, catalogues = registry_tree
    directory = tmp_path / "m303_orden_anual"
    directory.mkdir()
    copyfile(bundled_path("registry", "aeat", "m303_orden_anual", "manifest.toml"), directory / "manifest.toml")
    (directory / "parallel.toml").write_text("[parallel]\nenabled = true\n", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match=r"unexpected entries: parallel\.toml"):
        check_m303_annual_orden_manifest(
            manifest_path=directory / "manifest.toml",
            source_root=bundled_path(),
            sources=catalogues.sources,
        )


def test_generated_annual_orden_legal_ids_cover_every_compiled_source_axis(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Every pinned regulatory axis receives its own exact legal provenance."""
    modelos, catalogues = registry_tree
    compilation = load_m303_annual_orden_authority(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        modelos=modelos,
        sources=catalogues.sources,
    )

    axis_legal_refs_by_source: dict[str, tuple[str, ...]] = {}
    for projection in compilation.authority.projections:
        axis_legal_refs = tuple(
            legal_ref
            for legal_refs in (
                *(activity.legal_refs for activity in projection.activities),
                *(item.legal_refs for item in projection.agricultural_authority.quota_indexes),
                *(item.legal_refs for item in projection.agricultural_authority.ingreso_a_cuenta_percentages),
                *(item.legal_refs for item in projection.non_agricultural_ingresos_a_cuenta),
                *(item.legal_refs for item in projection.seasonal_indexes),
                projection.difficult_justification.legal_refs,
                (() if projection.lorca_2022_reduction is None else projection.lorca_2022_reduction.legal_refs),
            )
            for legal_ref in legal_refs
        )
        assert len(axis_legal_refs) == len(set(axis_legal_refs))
        existing = axis_legal_refs_by_source.setdefault(projection.source_ref, axis_legal_refs)
        assert existing == axis_legal_refs

    assert set().union(*(set(axis_legal_refs) for axis_legal_refs in axis_legal_refs_by_source.values())) == set(
        compilation.legal
    )
    assert "orden-hfp-1335-2021:da-4-lorca-2022-reduction:lorca-2022-reduction" in compilation.legal
    for source in compilation.authority.projections:
        corpus_path = bundled_path() / catalogues.sources[source.source_ref].corpus_path
        assert "#m303-anexo-i-iva-" in corpus_path.with_name(corpus_path.name + ".extracted.json").read_text(
            encoding="utf-8",
        )


def test_m303_revision_refuses_a_second_cross_year_annual_orden_source(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A real revision cannot cite its own Orden plus another year's authority."""
    modelos, catalogues = registry_tree
    modelo = next(item for item in modelos if item.id == "303")
    revision = modelo.revisions["2023"]
    contaminated_revision = revision.model_copy(
        update={"source_refs": (*revision.source_refs, "boe-orden-hac-1425-2025-iva-authority")},
    )
    contaminated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: contaminated_revision}},
    )

    with pytest.raises(RegistryValidationError, match="must cite exactly its filing-year annual Orden source"):
        load_m303_annual_orden_authority(
            bundled_path("registry", "aeat"),
            source_root=bundled_path(),
            modelos=(contaminated_modelo,),
            sources=catalogues.sources,
        )

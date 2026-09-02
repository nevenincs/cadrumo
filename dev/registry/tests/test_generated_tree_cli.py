"""Focused command-surface tests for generated export-tree publication."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

from ..pipeline._export_tree import render_complete_export_tree
from ..pipeline.cli import _check, _Invocation, _PreparedInvocation, _publish, app
from ..pipeline.render_check import (
    GeneratedExportBootstrapTransport,
    RevisionRenderInputs,
    revision_render_inputs,
)
from .test_export_tree import _ISOLATED_TREE, _real_authorities, _write_isolated_generated_authority_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_pipeline_cli_registers_the_separate_check_and_publish_verbs() -> None:
    """The developer-only lifecycle surface exposes both authority modes."""
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "check" in result.output
    assert "publish" in result.output


def test_pipeline_cli_refuses_an_undeclared_record_design_source_before_staging() -> None:
    """An explicit source selector is checked against the revision, never guessed."""
    result = CliRunner().invoke(
        app,
        ["check", "200", "2024", "not-a-declared-source", "2024", "0A"],
    )

    assert result.exit_code == 1
    assert "does not declare record-design source" in result.output


def _prepared_absent_target(candidate_base: Path, target_root: Path) -> _PreparedInvocation:
    """Build a real isolated candidate for the bootstrap-path detector test."""
    validation, joined, semantic_map, rendered, candidate_export_root = _write_isolated_generated_authority_tree(
        candidate_base,
    )
    shutil.rmtree(candidate_export_root)
    _joined, _semantic_map, transport, render_profile, evidence = _real_authorities(_ISOLATED_TREE)
    inputs = RevisionRenderInputs(
        revision_id=validation.target.revision_id,
        layout_id=str(rendered.layout.id),
        joined=joined,
        semantic_map=semantic_map,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        transport_profile=transport,
    )
    return _PreparedInvocation(
        invocation=_Invocation(
            _ISOLATED_TREE.modelo,
            _ISOLATED_TREE.revision,
            _ISOLATED_TREE.source_ref,
            _ISOLATED_TREE.filing_year,
            _ISOLATED_TREE.period,
        ),
        inputs=inputs,
        validation=validation,
        candidate_root=validation.registry_root,
        target_root=target_root,
        target_export_root=target_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export",
        published_modelo_root=None,
    )


def test_absent_tree_is_validated_then_published_through_the_canonical_authorities(tmp_path: Path) -> None:
    """An owed tree is bootstrap-publishable only after its fresh candidate validates."""
    first = _prepared_absent_target(tmp_path / "check", tmp_path / "target" / "registry" / "aeat")
    shutil.copytree(first.candidate_root, first.target_root)

    assert _check(first) == "publishable_absence"
    assert first.candidate_root.joinpath(
        "modelos",
        _ISOLATED_TREE.modelo,
        "revisions",
        _ISOLATED_TREE.revision,
        "export",
    ).is_dir()
    assert not first.target_export_root.exists()

    publication = _prepared_absent_target(tmp_path / "publish", first.target_root)
    _publish(publication)

    assert first.target_export_root.is_dir()


def test_modelo_200_calculation_grade_does_not_widen_its_runtime_filing_authority() -> None:
    """Bootstrap publication can validate static output without promoting Modelo 200."""
    authority = bundled_authority()

    calculation = authority.snapshot(
        "200",
        filing_year=2024,
        period="0A",
        revision_id="2024",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    with pytest.raises(RegistrySnapshotError, match="cannot satisfy the requested 'filing' snapshot authority"):
        authority.snapshot(
            "200",
            filing_year=2024,
            period="0A",
            revision_id="2024",
            grade=RegistryAuthorityGrade.FILING,
        )

    assert str(calculation.revision.id) == "2024"


def test_modelo_200_bootstrap_assembly_reaches_the_real_join_and_renderer(tmp_path: Path) -> None:
    """An unpublished revision is assembled from its selected official design, not a missing layout."""
    inputs = revision_render_inputs(
        bundled_authority(),
        modelo="200",
        revision="2025-y-siguientes",
        source_ref="aeat-dr-200-2025",
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-200-2025-y-siguientes-fichero",
            line_ending="crlf",
        ),
    )

    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )

    assert inputs.layout_id == "generated-modelo-200-2025-y-siguientes-fichero"
    assert rendered.output_files

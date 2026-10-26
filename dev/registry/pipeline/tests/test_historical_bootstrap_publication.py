"""Historical bootstrap publication preserves its static admission boundary."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from .._tree_publication import publish_validated_generated_export_tree
from .._tree_validation import ValidatedHistoricalStaticGeneratedExportTree
from ..bootstrap_supersession import validate_bootstrap_manual_export_layout_supersession
from ..cli import GeneratedTreeInvocation, check_prepared_invocation, prepare_generated_tree_invocation
from ..export_tree_serialization import render_toml_bytes
from ..tree_publication_contracts import (
    GeneratedExportSupersession,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_historical_bootstrap_supersedes_only_its_pinned_manual_layout(tmp_path: Path) -> None:
    """A real enrolled 2021 target publishes without acquiring a runtime snapshot."""
    authority = compiled_bundled_authority()
    invocation = GeneratedTreeInvocation("490", "2021", "aeat-dr-490-2021", 2021, "1T")
    prepared = prepare_generated_tree_invocation(invocation, tmp_path / "candidate", authority=authority)
    _outcome, rendered, _live_receipt = check_prepared_invocation(prepared)
    assert prepared.validation.historical_static_source_ref == invocation.source_ref
    original = authority.modelo("490").revisions["2021"]
    target_root = tmp_path / "publication" / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", "490"), target_root / "modelos" / "490")
    for family in ("facts", "legal"):
        shutil.copytree(bundled_path("registry", "aeat", family), target_root / family)
    export_root = target_root / "modelos" / "490" / "revisions" / "2021" / "export"
    # Recreate the superseded manual declaration in this isolated fixture so
    # the proof survives retirement of the production bootstrap enrollment.
    if export_root.exists():
        shutil.rmtree(export_root)
    manual_root = export_root.parent / "export_layouts"
    manual_root.mkdir(exist_ok=True)
    if not tuple(manual_root.iterdir()):
        document = rendered.layout.model_dump(mode="json", exclude_none=True)
        records = document.pop("records")
        (manual_root / "0001-manual-layout.toml").write_bytes(
            render_toml_bytes(
                "0001-manual-layout.toml",
                {"revisions": {"2021": {"export_layouts": [{**document, "records": records}]}}},
            ),
        )
    source = authority.catalogues.sources[invocation.source_ref]
    fingerprint = validate_bootstrap_manual_export_layout_supersession(
        target_root / "modelos" / "490",
        revision="2021",
        superseded_layout_id=str(rendered.layout.id),
        generated_layout_id=str(rendered.layout.id),
        expected_references=0,
        source_ref=invocation.source_ref,
        source_sha256=source.sha256,
    )
    supersession = GeneratedExportSupersession(
        superseded_layout_id=str(rendered.layout.id),
        generated_layout_id=str(rendered.layout.id),
        expected_construct_references=0,
        source_state_sha256=fingerprint,
        source_ref=invocation.source_ref,
        source_sha256=source.sha256,
    )
    receipt = GeneratedExportTreeTargetStateReceipt.observe(export_root, supersession_source_sha256=fingerprint)
    context = GeneratedExportTreePublicationContext(
        validation=prepared.validation,
        temporary_root=prepared.candidate_root.parents[2],
        target_root=target_root,
        target_export_root=export_root,
        expected_target_state=receipt,
        supersession=supersession,
    )
    published = publish_validated_generated_export_tree(
        context=context,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )
    assert isinstance(published.validated, ValidatedHistoricalStaticGeneratedExportTree)
    assert not hasattr(published.validated, "snapshot")
    loaded = load_modelo_directory(target_root / "modelos" / "490").revisions["2021"]
    assert loaded.model_dump(exclude={"export_layouts", "form_layouts"}) == original.model_dump(
        exclude={"export_layouts", "form_layouts"}
    )
    assert loaded.export_layouts == (rendered.layout,)
    assert not (export_root.parent / "export_layouts").exists()
    assert not GeneratedExportTransactionPaths.for_context(context).journal.exists()
    with pytest.raises(RegistrySnapshotError, match="support envelope"):
        authority.snapshot("490", filing_year=2021, period="1T")

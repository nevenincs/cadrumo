"""M190's real source-pinned export/form repair and pre-cutover refusals."""

from __future__ import annotations

import shutil
from hashlib import sha256
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.authority import compile_validated_authority
from ...form_layout.cli import synchronise_form_layouts
from .. import cli
from ..generated_form_bridge import generated_form_companion_changed, prepare_generated_form_bridge
from ..generated_tree_dispositions import GeneratedTreeRecordDriftDisposition
from ..tree_publication_contracts import GeneratedExportTransactionPaths

pytestmark = [pytest.mark.hex_core]

_REVISION = "2025-y-siguientes"
_SOURCE = "aeat-dr-190-2025"
_SOURCE_SHA = "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d"
_OLD_MANIFEST_SHA = "c686e3d09a298c32d8025ef9c98f26455548be20d6796df8df05c8509a4d222a"


@pytest.mark.parametrize("defect", ["modelo", "revision", "source", "source_sha", "manifest"])
@pytest.mark.unit
def test_m190_bridge_refuses_an_unreviewed_repair_before_source_access(tmp_path: Path, defect: str) -> None:
    """A reviewed source pin grants no authority to repair another target or package."""
    with pytest.raises(RegistryValidationError, match="exact reviewed source and old target"):
        prepare_generated_form_bridge(
            registry_root=tmp_path / "absent-live",
            candidate_root=tmp_path / "absent-candidate",
            modelo="191" if defect == "modelo" else "190",
            revision="2024" if defect == "revision" else _REVISION,
            source_ref="aeat-dr-190-2024" if defect == "source" else _SOURCE,
            source_sha256="0" * 64 if defect == "source_sha" else _SOURCE_SHA,
            expected_manifest_sha256="0" * 64 if defect == "manifest" else _OLD_MANIFEST_SHA,
        )


@pytest.mark.integration
@pytest.mark.timeout(900)
def test_m190_republication_preserves_other_authority_and_closes_the_generated_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retained historical package requires its real export and form owners together.

    The fixture contains the exact pre-repeat source package from the integration
    checkpoint, rather than a render mirrored from the implementation under test.
    Every candidate and final authority is compiled by the genuine compiler.
    """
    registry_root = tmp_path / "registry" / "aeat"
    shutil.copytree(bundled_path("registry", "aeat"), registry_root)
    revision_root = registry_root / "modelos" / "190" / "revisions" / _REVISION
    fixture = Path(__file__).with_name("fixtures") / "m190-pre-repeat"
    for path in fixture.rglob("*"):
        if path.is_file():
            target = revision_root / path.relative_to(fixture)
            target.write_bytes(path.read_bytes())
    old_form = revision_root / "form_layouts" / "0001-form-layout.toml"
    old_form_bytes = old_form.read_bytes()
    manifest = revision_root / "export" / "_generation.provenance.json"
    assert sha256(manifest.read_bytes()).hexdigest() == _OLD_MANIFEST_SHA
    other_before = {
        path.relative_to(registry_root): path.read_bytes()
        for path in registry_root.rglob("*")
        if path.is_file() and not path.is_relative_to(revision_root / "export") and path != old_form
    }
    source_root = bundled_path()
    original_bundled_path = bundled_path

    def selected_path(*parts: str) -> Path:
        return registry_root if parts == ("registry", "aeat") else original_bundled_path(*parts)

    def source_authority() -> ValidatedRegistryAuthority:
        return compile_validated_authority(registry_root, source_root)

    monkeypatch.setattr(cli, "bundled_path", selected_path)
    monkeypatch.setattr(cli, "compiled_bundled_authority", source_authority)
    disposition = GeneratedTreeRecordDriftDisposition(
        kind="record_drift",
        modelo="190",
        revision=_REVISION,
        source_ref=_SOURCE,
        source_sha256=_SOURCE_SHA,
        remedy="republish",
        differing_records=3,
        reason=(
            "The retained historical package precedes the source-pinned repeated-row mapping "
            "and the declarante's signed monetary total."
        ),
        reconsideration_condition="Retire after both fragments and the canonical form reproduce their current inputs.",
    )
    monkeypatch.setattr(cli, "record_drift_dispositions", lambda: (disposition,))
    prepared_old = cli.prepare_generated_tree_invocation(
        cli.GeneratedTreeInvocation("190", _REVISION, _SOURCE, 2025, "0A", _OLD_MANIFEST_SHA),
        tmp_path / "corrupt-pin-candidate",
        authority=source_authority(),
    )
    cli._render_candidate(prepared_old)
    old_form.write_bytes(old_form_bytes + b"\n# intervening edit\n")
    try:
        with pytest.raises(RegistryValidationError, match="old manifest or form differs from reviewed bytes"):
            prepare_generated_form_bridge(
                registry_root=registry_root,
                candidate_root=prepared_old.candidate_root,
                modelo="190",
                revision=_REVISION,
                source_ref=_SOURCE,
                source_sha256=_SOURCE_SHA,
                expected_manifest_sha256=_OLD_MANIFEST_SHA,
            )
        assert sha256(manifest.read_bytes()).hexdigest() == _OLD_MANIFEST_SHA
    finally:
        old_form.write_bytes(old_form_bytes)
    cli.republish_target_command("190", _REVISION, _SOURCE, 2025, "0A", _OLD_MANIFEST_SHA)

    assert old_form.read_bytes() != old_form_bytes
    assert synchronise_form_layouts(registry_root, source_root, modelos=("190",), check=True) == ([], [])
    authority = source_authority()
    assert cli.target_currentness("190", _REVISION, _SOURCE, 2025, "0A", authority=authority).state is (
        cli.TargetCurrentnessState.CURRENT
    )
    assert all((registry_root / path).read_bytes() == data for path, data in other_before.items())
    assert not GeneratedExportTransactionPaths(
        target_root=registry_root, modelo="190", revision_id=_REVISION
    ).journal.exists()
    prepared = cli.prepare_generated_tree_invocation(
        cli.GeneratedTreeInvocation("190", _REVISION, _SOURCE, 2025, "0A"),
        tmp_path / "reproduced",
        authority=authority,
    )
    cli.check_prepared_invocation(prepared)
    assert not generated_form_companion_changed(registry_root, prepared.candidate_root, "190", _REVISION)

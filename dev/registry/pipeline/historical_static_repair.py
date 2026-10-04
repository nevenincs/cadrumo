"""Break one stale generated-target compilation cycle without granting authority.

The committed M232/2016 export still contains obsolete binding identifiers, so
it cannot be a validated source authority for its own replacement. Canonical
structural components may render a temporary repair witness; only a complete
whole-registry validation of that exact one-target overlay grants the authority
used by the ordinary digest-bound publisher.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.authority import compile_validated_authority, inspect_authoring_candidate
from ..compiler.identity import resolve_registry_identity
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from ._export_tree import render_complete_export_tree
from .generated_form_bridge import generated_form_interpreting_input_digest, registry_evidence_content_digest
from .render_check import _revision_render_inputs, compare_export_tree_roots, revision_render_inputs
from .source_defects import source_defects_for
from .tree_publication_artifacts import verify_generated_export_package

_REVISION = "2016-2017"
_MODELO = "232"
_SOURCE_REF = "aeat-dr-232-2016"
_SOURCE_SHA256 = "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad"
_OLD_MANIFEST_SHA256 = "f4e1bb800af4c511c93e0d1df74520b70cc0ee986338b57f31c46c619582d6fa"
_STALE_BINDING = re.compile(r"^modelo 232 revision 2016-2017: export field '[^']+' references unknown binding '[^']+'$")


def _unchanged_files(root: Path) -> dict[str, str]:
    """Hash all other members, excluding the export and its generated form."""
    excluded = f"modelos/{_MODELO}/revisions/{_REVISION}/export/"
    form = f"modelos/{_MODELO}/revisions/{_REVISION}/form_layouts/0001-form-layout.toml"
    return {
        relative: sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
        and not (relative := path.relative_to(root).as_posix()).startswith(excluded)
        and relative != form
    }


def validated_historical_repair_source(
    *, modelo: str, revision: str, source_ref: str, filing_year: int, period: str, expected_manifest_sha256: str | None
) -> ValidatedRegistryAuthority:
    """Validate a one-target temporary overlay before the normal publisher runs."""
    if (modelo, revision, source_ref, filing_year, period, expected_manifest_sha256) != (
        _MODELO,
        _REVISION,
        _SOURCE_REF,
        2016,
        "0A",
        _OLD_MANIFEST_SHA256,
    ):
        raise RegistryValidationError("historical repair requires the exact reviewed M232/2016 target and manifest")
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    interpreting_digest = generated_form_interpreting_input_digest("232")
    evidence_content_digest = registry_evidence_content_digest(source_root)
    target_export = registry_root / "modelos" / modelo / "revisions" / revision / "export"
    old_manifest = target_export / "_generation.provenance.json"
    if sha256(old_manifest.read_bytes()).hexdigest() != expected_manifest_sha256:
        raise RegistryValidationError("historical repair old manifest changed from the reviewed digest")
    old_package = verify_generated_export_package(target_export)
    old_identity = (
        str(old_package.modelo),
        str(old_package.revision_id),
        str(old_package.source_ref),
        old_package.source_sha256,
    )
    if old_identity != (
        modelo,
        revision,
        source_ref,
        _SOURCE_SHA256,
    ):
        raise RegistryValidationError("historical repair old package identity or source pin changed")
    initial_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
    )
    original = inspect_authoring_candidate(registry_root, source_root, identity=initial_identity)
    if len(original.findings) != 140 or any(_STALE_BINDING.fullmatch(finding) is None for finding in original.findings):
        raise RegistryValidationError("historical repair has findings beyond the 140 reviewed stale bindings")
    selected_source = original.components.catalogues.sources.get(source_ref)
    if selected_source is None or selected_source.sha256 != _SOURCE_SHA256:
        raise RegistryValidationError("historical repair selected official source changed")
    definition = next((item for item in original.components.modelos if str(item.id) == modelo), None)
    if definition is None:
        raise RegistryValidationError("historical repair structural source lacks its target modelo")
    preliminary = _revision_render_inputs(
        definition,
        original.components.catalogues,
        modelo=modelo,
        revision=revision,
        source_ref=source_ref,
        bootstrap_transport=None,
        filing_year=filing_year,
        period=period,
    )
    if preliminary.layout_id != "generated-modelo-232-2016-2017-fichero" or (
        preliminary.transport_profile.line_ending != "crlf"
    ):
        raise RegistryValidationError("historical repair generated transport differs from the reviewed target")
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-m232-static-repair-", dir=prepare_temporary_directory()
    ) as scratch:
        overlay = Path(scratch) / "registry" / "aeat"
        shutil.copytree(registry_root, overlay)
        overlay_export = overlay / "modelos" / modelo / "revisions" / revision / "export"
        if not overlay_export.resolve().is_relative_to(overlay.resolve()):
            raise RegistryValidationError("historical repair export path escaped its temporary overlay")
        shutil.rmtree(overlay_export)
        preliminary_render = render_complete_export_tree(
            overlay_export,
            revision_id=preliminary.revision_id,
            joined=preliminary.joined,
            semantic_map=preliminary.semantic_map,
            transport_profile=preliminary.transport_profile,
            render_profile=preliminary.render_profile,
            render_profile_source_evidence=preliminary.render_profile_source_evidence,
            source_defects=source_defects_for(source_ref),
        )
        overlay_revision = load_modelo_directory(overlay / "modelos" / modelo).revisions[revision]
        generated_form = generate_revision_layout(
            modelo,
            overlay_revision,
            sources={str(key): value for key, value in original.components.catalogues.sources.items()},
            data_root=source_root,
        )
        if generated_form.layout is None:
            raise RegistryValidationError(f"historical repair generated form refuses: {generated_form.failure}")
        form_fragment = form_layout_fragment_path(overlay_export.parent)
        if not form_fragment.is_file():
            raise RegistryValidationError("historical repair generated form companion is absent")
        form_fragment.write_text(
            render_form_layout_toml(revision, generated_form.layout), encoding="utf-8", newline="\n"
        )
        if _unchanged_files(overlay) != _unchanged_files(registry_root):
            raise RegistryValidationError("historical repair overlay changed a nontarget registry member")
        validated = compile_validated_authority(
            overlay,
            source_root,
            verify_evidence_bytes=True,
            complete_validation=True,
        )
        ordinary = revision_render_inputs(
            validated,
            modelo=modelo,
            revision=revision,
            source_ref=source_ref,
            filing_year=filing_year,
            period=period,
        )
        if ordinary != preliminary:
            raise RegistryValidationError("historical repair validated render inputs differ from structural inputs")
        with tempfile.TemporaryDirectory(
            prefix="cadrumo-m232-static-rerender-", dir=prepare_temporary_directory()
        ) as rerender:
            confirmed_root = Path(rerender) / "export"
            confirmed = render_complete_export_tree(
                confirmed_root,
                revision_id=ordinary.revision_id,
                joined=ordinary.joined,
                semantic_map=ordinary.semantic_map,
                transport_profile=ordinary.transport_profile,
                render_profile=ordinary.render_profile,
                render_profile_source_evidence=ordinary.render_profile_source_evidence,
                source_defects=source_defects_for(source_ref),
            )
            if (
                confirmed.layout != preliminary_render.layout
                or confirmed.field_derivations != preliminary_render.field_derivations
            ):
                raise RegistryValidationError("historical repair validated output differs from structural render")
            comparison = compare_export_tree_roots(
                modelo=modelo,
                revision=revision,
                layout_id=ordinary.layout_id,
                committed_root=overlay_export,
                rendered_root=confirmed_root,
            )
            if not comparison.reproduced:
                raise RegistryValidationError("historical repair validated render does not reproduce overlay")
        after = resolve_registry_identity(
            registry_root,
            collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
        )
        evidence_after = collect_source_evidence_fingerprints(source_root, use_cache=False)
        if (
            after.digest != original.registry_fingerprint
            or evidence_after != original.source_evidence_fingerprint
            or registry_evidence_content_digest(source_root) != evidence_content_digest
            or generated_form_interpreting_input_digest("232") != interpreting_digest
            or sha256(old_manifest.read_bytes()).hexdigest() != expected_manifest_sha256
        ):
            raise RegistryValidationError("historical repair live source or old target changed during validation")
        return validated

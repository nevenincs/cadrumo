"""Break one stale generated-target compilation cycle without granting authority.

Reviewed targets can contain retired binding identifiers, so they cannot be
a validated source authority for their own replacement. Canonical
structural components may render a temporary repair witness; only a complete
whole-registry validation of that exact one-target overlay grants the authority
used by the ordinary digest-bound publisher.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class _RepairTarget:
    source_sha256: str
    layout_id: str
    finding_count: int
    exact_findings: frozenset[str] | None = None


_REVIEWED_TARGETS = {
    (_MODELO, _REVISION, _SOURCE_REF, 2016, "0A", _OLD_MANIFEST_SHA256): _RepairTarget(
        _SOURCE_SHA256, "generated-modelo-232-2016-2017-fichero", 140
    ),
    (
        "720",
        "2013-y-siguientes",
        "aeat-dr-720",
        2024,
        "0A",
        "1217b488e839465f1499fba090eeab3faa1e39e83068d7447de68467427f398d",
    ): _RepairTarget(
        "ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7",
        "modelo-720-fichero-aeat",
        9,
        frozenset(
            f"modelo 720 revision 2013-y-siguientes: export field 'modelo-720-{record}-{field}' "
            f"references unknown binding 'modelo-720.{record}.{field}'"
            for record, field in (
                ("type_1", "ejercicio"),
                ("type_1", "n-i-f-del-declarante"),
                ("type_1", "apellidos-y-nombre-o-razon-social-del-declarante"),
                ("type_2", "ejercicio"),
                ("type_2", "n-i-f-del-declarante"),
            )
        )
        | frozenset(
            {
                "modelo 720 revision 2013-y-siguientes: form layout 'form-layout' form layout is stale: "
                "its source_state_digest no longer matches the revision; regenerate it",
            }
        )
        | frozenset(
            "modelo 720 revision 2013-y-siguientes: form layout 'form-layout' shows binding "
            f"'modelo-720.type_1.{field}', which the revision does not declare"
            for field in (
                "ejercicio",
                "n-i-f-del-declarante",
                "apellidos-y-nombre-o-razon-social-del-declarante",
            )
        ),
    ),
    (
        "720",
        "2013-y-siguientes",
        "aeat-dr-720",
        2024,
        "0A",
        "83c26f2c7c2848ec9544889d070b071d69d24608f48bd52782a6d608039d23b9",
    ): _RepairTarget(
        "ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7",
        "modelo-720-fichero-aeat",
        6,
        frozenset(
            f"modelo 720 revision 2013-y-siguientes: export field 'modelo-720-{record}-{field}' "
            f"references unknown binding 'modelo-720.{record}.{field}'"
            for record in ("type_1", "type_2")
            for field in ("tipo-de-registro", "modelo-declaracion")
        )
        | frozenset(
            {
                "modelo 720 revision 2013-y-siguientes: fixed-width export layout 'modelo-720-fichero-aeat' "
                "has 2 design record(s) without a unique source-to-record join, so per-record coverage is unverified. "
                "design record 'Tipo 1 - Registro De Declarante': "
                "no unique authored record joins its source constants; "
                "layout-wide byte coverage cannot verify this record | "
                "design record 'Tipo 2 - Registro De Detalle': no unique authored record joins its source constants; "
                "layout-wide byte coverage cannot verify this record",
                "modelo 720 revision 2013-y-siguientes: form layout 'form-layout' form layout is stale: "
                "its source_state_digest no longer matches the revision; regenerate it",
            }
        ),
    ),
}


def _validate_repair_findings(target: _RepairTarget, findings: tuple[str, ...]) -> None:
    exact = target.exact_findings
    if len(findings) != target.finding_count or (
        frozenset(findings) != exact
        if exact is not None
        else any(_STALE_BINDING.fullmatch(finding) is None for finding in findings)
    ):
        raise RegistryValidationError("historical repair has findings beyond the reviewed target defects")


def _unchanged_files(root: Path, *, modelo: str, revision: str) -> dict[str, str]:
    """Hash all other members, excluding the export and its generated form."""
    excluded = f"modelos/{modelo}/revisions/{revision}/export/"
    form = f"modelos/{modelo}/revisions/{revision}/form_layouts/0001-form-layout.toml"
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
    if expected_manifest_sha256 is None:
        raise RegistryValidationError("historical repair requires the exact reviewed target manifest")
    target = _REVIEWED_TARGETS.get((modelo, revision, source_ref, filing_year, period, expected_manifest_sha256))
    if target is None:
        raise RegistryValidationError(
            "historical repair requires an exact reviewed M232/2016 or M720/2024 target and manifest"
        )
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    interpreting_digest = generated_form_interpreting_input_digest(modelo)
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
        target.source_sha256,
    ):
        raise RegistryValidationError("historical repair old package identity or source pin changed")
    initial_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
    )
    original = inspect_authoring_candidate(registry_root, source_root, identity=initial_identity)
    _validate_repair_findings(target, original.findings)
    selected_source = original.components.catalogues.sources.get(source_ref)
    if selected_source is None or selected_source.sha256 != target.source_sha256:
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
        source_root=source_root,
    )
    if preliminary.layout_id != target.layout_id or (preliminary.transport_profile.line_ending != "crlf"):
        raise RegistryValidationError("historical repair generated transport differs from the reviewed target")
    with tempfile.TemporaryDirectory(
        prefix=f"cadrumo-m{modelo}-static-repair-", dir=prepare_temporary_directory()
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
        if _unchanged_files(overlay, modelo=modelo, revision=revision) != _unchanged_files(
            registry_root, modelo=modelo, revision=revision
        ):
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
            source_root=source_root,
        )
        if ordinary != preliminary:
            raise RegistryValidationError("historical repair validated render inputs differ from structural inputs")
        with tempfile.TemporaryDirectory(
            prefix=f"cadrumo-m{modelo}-static-rerender-", dir=prepare_temporary_directory()
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
        changed_inputs = {
            "registry": after.digest != original.registry_fingerprint,
            "evidence_inventory": evidence_after != original.source_evidence_fingerprint,
            "evidence_content": registry_evidence_content_digest(source_root) != evidence_content_digest,
            "interpreting_inputs": generated_form_interpreting_input_digest(modelo) != interpreting_digest,
            "target_manifest": sha256(old_manifest.read_bytes()).hexdigest() != expected_manifest_sha256,
        }
        changed = [name for name, differs in changed_inputs.items() if differs]
        if changed:
            before_paths = {
                path: (size, modified, digest) for path, size, modified, digest in initial_identity.fingerprints
            }
            after_paths = {path: (size, modified, digest) for path, size, modified, digest in after.fingerprints}
            changed_paths = sorted(
                path
                for path in before_paths.keys() | after_paths.keys()
                if before_paths.get(path) != after_paths.get(path)
            )
            raise RegistryValidationError(
                "historical repair live source or old target changed during validation: "
                f"inputs={changed}; registry_paths={changed_paths[:12]}; registry_path_count={len(changed_paths)}"
            )
        return validated

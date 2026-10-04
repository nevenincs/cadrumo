"""Separate-owner generated export/form repair with an exact source closure.

The generated export publisher journals only export/. A corrected envelope also
changes its generated form digest, so the canonical form owner runs after the
export journal commits. The interval is explicitly incomplete: full authority
and target currentness are required again before the command reports success.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutReviewState

from ..compiler.authority import compile_validated_authority
from ..compiler.loader import load_registry_tree
from ..compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from ..form_layout.cli import synchronise_form_layouts, synchronise_selected_form_layout
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from ..registry_collapse_fingerprints import fingerprint_digest, fingerprint_paths, fingerprint_tree
from ..registry_collapse_inputs import _tool_input_paths
from .tree_publication_artifacts import verify_generated_export_package
from .tree_publication_contracts import GeneratedExportTransactionPaths
from .tree_publication_journal import _journal_backup_path, load_generated_export_publication_journal

_REVIEWED: dict[tuple[str, str], tuple[str, str, str, str]] = {
    ("190", "2025-y-siguientes"): (
        "aeat-dr-190-2025",
        "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d",
        "c686e3d09a298c32d8025ef9c98f26455548be20d6796df8df05c8509a4d222a",
        "3ccbf778c6cf016254508cf12ca8eb1ecd7d2af2a5681eb48d6adf833c40cffe",
    ),
    ("232", "2016-2017"): (
        "aeat-dr-232-2016",
        "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
        "f4e1bb800af4c511c93e0d1df74520b70cc0ee986338b57f31c46c619582d6fa",
        "87587cd44e6be0d35afaffa93e35b458e8a61f3aebde2f6d4279a083d33ce647",
    ),
    ("232", "2018-y-siguientes"): (
        "aeat-dr-232-2018",
        "a61485dfc480393ec1dfc926142fd0b6a9386e28e60746da3dfbf2fdaf3bffff",
        "fb76af52570a20598382d59257ff685297864aa6091b1eac0d6155709dc52243",
        "a4e2d574372a6539b15d0467d566e6b1a03f75bb1ae3f75978ff352e09863405",
    ),
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _other_files(root: Path, modelo: str, revision: str, *, transaction_backup: Path | None = None) -> dict[str, str]:
    prefix = f"modelos/{modelo}/revisions/{revision}/export/"
    form = f"modelos/{modelo}/revisions/{revision}/form_layouts/0001-form-layout.toml"
    return {
        relative: _sha(path)
        for path in root.rglob("*")
        if path.is_file()
        and not (relative := path.relative_to(root).as_posix()).startswith(prefix)
        and relative != form
        and (transaction_backup is None or not path.is_relative_to(transaction_backup))
    }


def _active_verified_backup(
    registry_root: Path, modelo: str, revision: str, candidate_manifest_sha256: str, old_manifest_sha256: str
) -> Path | None:
    """Identify only this target's journal-attested, intact old export package."""
    paths = GeneratedExportTransactionPaths(target_root=registry_root.resolve(), modelo=modelo, revision_id=revision)
    if not paths.journal.exists():
        return None
    journal = load_generated_export_publication_journal(paths.journal)
    if (
        journal.state != "candidate_live"
        or journal.is_supersession
        or str(journal.modelo) != modelo
        or str(journal.revision_id) != revision
        or journal.candidate_manifest_sha256 != candidate_manifest_sha256
    ):
        raise RegistryValidationError("Generated export cutover has no matching active publication journal")
    staged = Path(journal.candidate_export)
    if staged.parent != paths.target_root or not staged.name.startswith(paths.staging_prefix) or staged.exists():
        raise RegistryValidationError("Generated export cutover journal has no consumed target-scoped candidate")
    backup = _journal_backup_path(
        journal, registry_root / "modelos" / modelo / "revisions" / revision / "export", paths.target_root
    )
    if is_link_like(backup) or not backup.is_dir():
        raise RegistryValidationError("Generated export cutover backup is not a regular directory")
    old_manifest = old_manifest_sha256
    if _sha(backup / "_generation.provenance.json") != old_manifest:
        raise RegistryValidationError("Generated export cutover backup differs from reviewed old manifest")
    old_package = verify_generated_export_package(backup)
    if (
        str(old_package.modelo),
        str(old_package.revision_id),
        str(old_package.source_ref),
        old_package.source_sha256,
    ) != (modelo, revision, _REVIEWED[(modelo, revision)][0], _REVIEWED[(modelo, revision)][1]):
        raise RegistryValidationError("Generated export cutover backup differs from reviewed old source")
    return backup


def generated_form_interpreting_input_digest(modelo: str) -> str:
    """Fresh canonical interpreter census plus exact selected modelo maps/profiles."""
    repo_root = Path(__file__).resolve().parents[3]
    authored = tuple(
        path
        for directory in (
            repo_root / "dev" / "registry" / "mappings" / f"modelo_{modelo}",
            repo_root / "dev" / "registry" / "render_profiles" / f"modelo_{modelo}",
        )
        for path in directory.rglob("*")
        if path.is_file()
    )
    return fingerprint_digest(fingerprint_paths((*_tool_input_paths(repo_root), *authored), relative_to=repo_root))


def registry_evidence_content_digest(source_root: Path) -> str:
    """Hash actual corpus bytes and path membership, including same-size edits."""
    paths = (
        Path(path) for path, _size, _mtime_ns in collect_source_evidence_fingerprints(source_root, use_cache=False)
    )
    return fingerprint_digest(fingerprint_paths(paths, relative_to=source_root))


def _candidate_generated_form_bytes(candidate_root: Path, modelo_id: str, revision_id: str, source_root: Path) -> bytes:
    """Reproduce the staged form through its owner, including detached editions.

    A detached candidate may hold the form in ``0001-complete-edition.toml``.
    The live form owner always writes ``0001-form-layout.toml``, so the bridge
    carries canonical generated bytes rather than copying a staged filename.
    """
    revision_root = candidate_root / "modelos" / modelo_id / "revisions" / revision_id
    form_root = revision_root / "form_layouts"
    fragments = scan_directory(form_root)
    if (
        len(fragments) != 1
        or fragments[0].name
        not in {
            "0001-form-layout.toml",
            "0001-complete-edition.toml",
        }
        or is_link_like(fragments[0])
    ):
        raise RegistryValidationError("Generated bridge candidate has no unique generated form fragment")
    modelos, catalogues = load_registry_tree(candidate_root)
    modelo = next((item for item in modelos if str(item.id) == modelo_id), None)
    if modelo is None or revision_id not in modelo.revisions:
        raise RegistryValidationError("Generated bridge candidate revision is absent")
    revision = modelo.revisions[revision_id]
    if len(revision.form_layouts) != 1 or revision.form_layouts[0].review.state is FormLayoutReviewState.REVIEWED:
        raise RegistryValidationError("Generated bridge requires one unreviewed generated candidate form")
    generated = generate_revision_layout(modelo_id, revision, sources=catalogues.sources, data_root=source_root)
    if generated.layout is None or generated.layout != revision.form_layouts[0]:
        raise RegistryValidationError("Generated bridge candidate form differs from its fresh canonical generation")
    return render_form_layout_toml(revision_id, generated.layout).encode("utf-8")


def generated_form_companion_changed(registry_root: Path, candidate_root: Path, modelo: str, revision: str) -> bool:
    """Require a bridge only when the validated candidate changes its generated form.

    Later provenance-only repairs keep the current form and use the ordinary
    publisher's complete final-live validator without historical repair pins.
    """
    old_form = form_layout_fragment_path(registry_root / "modelos" / modelo / "revisions" / revision)
    return old_form.read_bytes() != _candidate_generated_form_bytes(candidate_root, modelo, revision, bundled_path())


@dataclass(frozen=True, slots=True)
class GeneratedFormBridge:
    """The exact validated export/form candidate and still-live old form pin."""

    modelo: str
    revision: str
    source_ref: str
    old_manifest_sha256: str
    source_sha256: str
    old_form_sha256: str
    candidate_form_sha256: str
    candidate_manifest_sha256: str
    other_files: dict[str, str]
    interpreting_digest: str
    evidence_content_digest: str
    profile_schema_fingerprint: object

    def _require_dependencies_current(self, source_root: Path) -> None:
        if (
            generated_form_interpreting_input_digest(self.modelo) != self.interpreting_digest
            or registry_evidence_content_digest(source_root) != self.evidence_content_digest
            or fingerprint_tree(source_root / "registry" / "cadrumo") != self.profile_schema_fingerprint
        ):
            raise RegistryValidationError(
                "Generated source, profile, or interpreting inputs changed after prevalidation"
            )

    def require_export_cutover(self, registry_root: Path) -> None:
        """Admit the known incomplete export-only interval after its journal."""
        revision_root = registry_root / "modelos" / self.modelo / "revisions" / self.revision
        manifest = revision_root / "export" / "_generation.provenance.json"
        form = form_layout_fragment_path(revision_root)
        self._require_dependencies_current(bundled_path())
        backup = _active_verified_backup(
            registry_root, self.modelo, self.revision, self.candidate_manifest_sha256, self.old_manifest_sha256
        )
        if (
            _sha(manifest) != self.candidate_manifest_sha256
            or _sha(form) != self.old_form_sha256
            or _other_files(registry_root, self.modelo, self.revision, transaction_backup=backup) != self.other_files
        ):
            raise RegistryValidationError(
                "Generated export cutover changed the target package, old form, or other source"
            )
        package = verify_generated_export_package(revision_root / "export")
        if str(package.source_ref) != self.source_ref or package.source_sha256 != self.source_sha256:
            raise RegistryValidationError("Generated export cutover changed the selected official source pin")

    def finish_with_form_owner(self, registry_root: Path, source_root: Path) -> None:
        """Run the form owner only after the export journal commits."""
        self.require_export_cutover(registry_root)
        target_form = form_layout_fragment_path(registry_root / "modelos" / self.modelo / "revisions" / self.revision)
        stale, undeclared = synchronise_form_layouts(registry_root, source_root, modelos=(self.modelo,), check=True)
        expected_changes = set() if self.candidate_form_sha256 == self.old_form_sha256 else {target_form.resolve()}
        if undeclared or {Path(path).resolve() for path in stale} != expected_changes:
            raise RegistryValidationError("Generated form owner found a stale companion outside the exact target")
        if expected_changes:
            self._require_dependencies_current(source_root)
            if not synchronise_selected_form_layout(
                registry_root,
                source_root,
                modelo_id=self.modelo,
                revision_id=self.revision,
                expected_old_sha256=self.old_form_sha256,
                expected_new_sha256=self.candidate_form_sha256,
            ):
                raise RegistryValidationError("Generated selected form owner did not perform its required write")
        if _sha(target_form) != self.candidate_form_sha256:
            raise RegistryValidationError(
                "Generated canonical form owner output differs from the prevalidated candidate"
            )
        if _other_files(registry_root, self.modelo, self.revision) != self.other_files:
            raise RegistryValidationError("Generated form cutover changed another registry source member")
        stale_after, undeclared_after = synchronise_form_layouts(
            registry_root, source_root, modelos=(self.modelo,), check=True
        )
        if stale_after or undeclared_after:
            raise RegistryValidationError("Generated form companion remains stale after complete live validation")


def prepare_generated_form_bridge(
    *,
    registry_root: Path,
    candidate_root: Path,
    modelo: str,
    revision: str,
    source_ref: str,
    source_sha256: str,
    expected_manifest_sha256: str | None,
) -> GeneratedFormBridge:
    """Prove full export+form source validity before the export-only journal."""
    reviewed = _REVIEWED.get((modelo, revision))
    if reviewed is None or (source_ref, source_sha256, expected_manifest_sha256) != reviewed[:3]:
        raise RegistryValidationError("Generated form bridge requires one exact reviewed source and old target")
    source_root = bundled_path()
    interpreting_digest = generated_form_interpreting_input_digest(modelo)
    evidence_content_digest = registry_evidence_content_digest(source_root)
    profile_fingerprint = fingerprint_tree(source_root / "registry" / "cadrumo")
    live_revision = registry_root / "modelos" / modelo / "revisions" / revision
    candidate_revision = candidate_root / "modelos" / modelo / "revisions" / revision
    old_form = form_layout_fragment_path(live_revision)
    old_manifest = live_revision / "export" / "_generation.provenance.json"
    new_manifest = candidate_revision / "export" / "_generation.provenance.json"
    if _sha(old_manifest) != expected_manifest_sha256 or _sha(old_form) != reviewed[3]:
        raise RegistryValidationError("Generated form bridge old manifest or form differs from reviewed bytes")
    old_package = verify_generated_export_package(live_revision / "export")
    new_package = verify_generated_export_package(candidate_revision / "export")
    if any(
        (str(package.modelo), str(package.revision_id), str(package.source_ref), package.source_sha256)
        != (modelo, revision, source_ref, source_sha256)
        for package in (old_package, new_package)
    ):
        raise RegistryValidationError("Generated form bridge package identity or official source changed")
    generated_form_bytes = _candidate_generated_form_bytes(candidate_root, modelo, revision, source_root)
    other = _other_files(registry_root, modelo, revision)
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-generated-form-bridge-", dir=prepare_temporary_directory()
    ) as scratch:
        overlay = Path(scratch) / "registry" / "aeat"
        shutil.copytree(registry_root, overlay)
        overlay_revision = overlay / "modelos" / modelo / "revisions" / revision
        overlay_export = overlay_revision / "export"
        if not overlay_export.resolve().is_relative_to(overlay.resolve()):
            raise RegistryValidationError("Generated form bridge overlay export escaped temporary root")
        shutil.rmtree(overlay_export)
        shutil.copytree(candidate_revision / "export", overlay_export)
        form_layout_fragment_path(overlay_revision).write_bytes(generated_form_bytes)
        if _other_files(overlay, modelo, revision) != other:
            raise RegistryValidationError("Generated form bridge overlay changed another registry member")
        compile_validated_authority(
            overlay,
            source_root,
            complete_validation=True,
            verify_evidence_bytes=True,
        )
    if _other_files(registry_root, modelo, revision) != other or _sha(old_manifest) != expected_manifest_sha256:
        raise RegistryValidationError("Generated form bridge live source changed during complete validation")
    if (
        generated_form_interpreting_input_digest(modelo) != interpreting_digest
        or registry_evidence_content_digest(source_root) != evidence_content_digest
        or fingerprint_tree(source_root / "registry" / "cadrumo") != profile_fingerprint
    ):
        raise RegistryValidationError("Generated bridge interpreting or evidence inputs changed during validation")
    return GeneratedFormBridge(
        modelo=modelo,
        revision=revision,
        old_manifest_sha256=reviewed[2],
        source_ref=source_ref,
        source_sha256=source_sha256,
        old_form_sha256=reviewed[3],
        candidate_form_sha256=sha256(generated_form_bytes).hexdigest(),
        candidate_manifest_sha256=_sha(new_manifest),
        other_files=other,
        interpreting_digest=interpreting_digest,
        evidence_content_digest=evidence_content_digest,
        profile_schema_fingerprint=profile_fingerprint,
    )

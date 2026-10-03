"""Separate-owner M232 export/form repair with an exact source closure.

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

from cadrumo.core.link_safety import is_link_like
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.authority import compile_validated_authority
from ..compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from ..form_layout.cli import synchronise_form_layouts, synchronise_selected_form_layout
from ..form_layout.serialization import form_layout_fragment_path
from ..registry_collapse_fingerprints import fingerprint_digest, fingerprint_paths, fingerprint_tree
from ..registry_collapse_inputs import _tool_input_paths
from .tree_publication_artifacts import verify_generated_export_package
from .tree_publication_contracts import GeneratedExportTransactionPaths
from .tree_publication_journal import _journal_backup_path, load_generated_export_publication_journal

_REVIEWED: dict[str, tuple[str, str, str, str]] = {
    "2016-2017": (
        "aeat-dr-232-2016",
        "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad",
        "f4e1bb800af4c511c93e0d1df74520b70cc0ee986338b57f31c46c619582d6fa",
        "87587cd44e6be0d35afaffa93e35b458e8a61f3aebde2f6d4279a083d33ce647",
    ),
    "2018-y-siguientes": (
        "aeat-dr-232-2018",
        "a61485dfc480393ec1dfc926142fd0b6a9386e28e60746da3dfbf2fdaf3bffff",
        "fb76af52570a20598382d59257ff685297864aa6091b1eac0d6155709dc52243",
        "a4e2d574372a6539b15d0467d566e6b1a03f75bb1ae3f75978ff352e09863405",
    ),
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _other_files(root: Path, revision: str, *, transaction_backup: Path | None = None) -> dict[str, str]:
    prefix = f"modelos/232/revisions/{revision}/export/"
    form = f"modelos/232/revisions/{revision}/form_layouts/0001-form-layout.toml"
    return {
        relative: _sha(path)
        for path in root.rglob("*")
        if path.is_file()
        and not (relative := path.relative_to(root).as_posix()).startswith(prefix)
        and relative != form
        and (transaction_backup is None or not path.is_relative_to(transaction_backup))
    }


def _active_verified_backup(registry_root: Path, revision: str, candidate_manifest_sha256: str) -> Path | None:
    """Identify only this target's journal-attested, intact old export package."""
    paths = GeneratedExportTransactionPaths(target_root=registry_root.resolve(), modelo="232", revision_id=revision)
    if not paths.journal.exists():
        return None
    journal = load_generated_export_publication_journal(paths.journal)
    if (
        journal.state != "candidate_live"
        or journal.is_supersession
        or str(journal.modelo) != "232"
        or str(journal.revision_id) != revision
        or journal.candidate_manifest_sha256 != candidate_manifest_sha256
    ):
        raise RegistryValidationError("M232 export cutover has no matching active publication journal")
    staged = Path(journal.candidate_export)
    if staged.parent != paths.target_root or not staged.name.startswith(paths.staging_prefix) or staged.exists():
        raise RegistryValidationError("M232 export cutover journal has no consumed target-scoped candidate")
    backup = _journal_backup_path(
        journal, registry_root / "modelos" / "232" / "revisions" / revision / "export", paths.target_root
    )
    if is_link_like(backup) or not backup.is_dir():
        raise RegistryValidationError("M232 export cutover backup is not a regular directory")
    old_manifest = _REVIEWED[revision][2]
    if _sha(backup / "_generation.provenance.json") != old_manifest:
        raise RegistryValidationError("M232 export cutover backup differs from reviewed old manifest")
    old_package = verify_generated_export_package(backup)
    if (
        str(old_package.modelo),
        str(old_package.revision_id),
        str(old_package.source_ref),
        old_package.source_sha256,
    ) != ("232", revision, _REVIEWED[revision][0], _REVIEWED[revision][1]):
        raise RegistryValidationError("M232 export cutover backup differs from reviewed old source")
    return backup


def m232_interpreting_input_digest() -> str:
    """Fresh canonical interpreter census plus exact M232 maps/profiles."""
    repo_root = Path(__file__).resolve().parents[3]
    authored = tuple(
        path
        for directory in (
            repo_root / "dev" / "registry" / "mappings" / "modelo_232",
            repo_root / "dev" / "registry" / "render_profiles" / "modelo_232",
        )
        for path in directory.rglob("*")
        if path.is_file()
    )
    return fingerprint_digest(fingerprint_paths((*_tool_input_paths(repo_root), *authored), relative_to=repo_root))


def m232_evidence_content_digest(source_root: Path) -> str:
    """Hash actual corpus bytes and path membership, including same-size edits."""
    paths = (
        Path(path) for path, _size, _mtime_ns in collect_source_evidence_fingerprints(source_root, use_cache=False)
    )
    return fingerprint_digest(fingerprint_paths(paths, relative_to=source_root))


@dataclass(frozen=True, slots=True)
class M232FormBridge:
    """The exact validated export/form candidate and still-live old form pin."""

    revision: str
    source_ref: str
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
            m232_interpreting_input_digest() != self.interpreting_digest
            or m232_evidence_content_digest(source_root) != self.evidence_content_digest
            or fingerprint_tree(source_root / "registry" / "cadrumo") != self.profile_schema_fingerprint
        ):
            raise RegistryValidationError("M232 source, profile, or interpreting inputs changed after prevalidation")

    def require_export_cutover(self, registry_root: Path) -> None:
        """Admit the known incomplete export-only interval after its journal."""
        revision_root = registry_root / "modelos" / "232" / "revisions" / self.revision
        manifest = revision_root / "export" / "_generation.provenance.json"
        form = form_layout_fragment_path(revision_root)
        self._require_dependencies_current(bundled_path())
        backup = _active_verified_backup(registry_root, self.revision, self.candidate_manifest_sha256)
        if (
            _sha(manifest) != self.candidate_manifest_sha256
            or _sha(form) != self.old_form_sha256
            or _other_files(registry_root, self.revision, transaction_backup=backup) != self.other_files
        ):
            raise RegistryValidationError("M232 export cutover changed the target package, old form, or other source")
        package = verify_generated_export_package(revision_root / "export")
        if str(package.source_ref) != self.source_ref or package.source_sha256 != self.source_sha256:
            raise RegistryValidationError("M232 export cutover changed the selected official source pin")

    def finish_with_form_owner(self, registry_root: Path, source_root: Path) -> None:
        """Run the form owner only after the export journal commits."""
        self.require_export_cutover(registry_root)
        target_form = form_layout_fragment_path(registry_root / "modelos" / "232" / "revisions" / self.revision)
        stale, undeclared = synchronise_form_layouts(registry_root, source_root, modelos=("232",), check=True)
        expected_changes = set() if self.candidate_form_sha256 == self.old_form_sha256 else {target_form.resolve()}
        if undeclared or {Path(path).resolve() for path in stale} != expected_changes:
            raise RegistryValidationError("M232 form owner found a stale companion outside the exact target")
        if expected_changes:
            self._require_dependencies_current(source_root)
            if not synchronise_selected_form_layout(
                registry_root,
                source_root,
                modelo_id="232",
                revision_id=self.revision,
                expected_old_sha256=self.old_form_sha256,
                expected_new_sha256=self.candidate_form_sha256,
            ):
                raise RegistryValidationError("M232 selected form owner did not perform its required write")
        if _sha(target_form) != self.candidate_form_sha256:
            raise RegistryValidationError("M232 canonical form owner output differs from the prevalidated candidate")
        if _other_files(registry_root, self.revision) != self.other_files:
            raise RegistryValidationError("M232 form cutover changed another registry source member")
        stale_after, undeclared_after = synchronise_form_layouts(
            registry_root, source_root, modelos=("232",), check=True
        )
        if stale_after or undeclared_after:
            raise RegistryValidationError("M232 form companion remains stale after complete live validation")


def prepare_m232_form_bridge(
    *,
    registry_root: Path,
    candidate_root: Path,
    revision: str,
    source_ref: str,
    source_sha256: str,
    expected_manifest_sha256: str | None,
) -> M232FormBridge:
    """Prove full export+form source validity before the export-only journal."""
    reviewed = _REVIEWED.get(revision)
    if reviewed is None or (source_ref, source_sha256, expected_manifest_sha256) != reviewed[:3]:
        raise RegistryValidationError("M232 form bridge requires one exact reviewed source and old target")
    source_root = bundled_path()
    interpreting_digest = m232_interpreting_input_digest()
    evidence_content_digest = m232_evidence_content_digest(source_root)
    profile_fingerprint = fingerprint_tree(source_root / "registry" / "cadrumo")
    live_revision = registry_root / "modelos" / "232" / "revisions" / revision
    candidate_revision = candidate_root / "modelos" / "232" / "revisions" / revision
    old_form = form_layout_fragment_path(live_revision)
    new_form = form_layout_fragment_path(candidate_revision)
    old_manifest = live_revision / "export" / "_generation.provenance.json"
    new_manifest = candidate_revision / "export" / "_generation.provenance.json"
    if _sha(old_manifest) != expected_manifest_sha256 or _sha(old_form) != reviewed[3]:
        raise RegistryValidationError("M232 form bridge old manifest or form differs from reviewed bytes")
    old_package = verify_generated_export_package(live_revision / "export")
    new_package = verify_generated_export_package(candidate_revision / "export")
    if any(
        (str(package.modelo), str(package.revision_id), str(package.source_ref), package.source_sha256)
        != ("232", revision, source_ref, source_sha256)
        for package in (old_package, new_package)
    ):
        raise RegistryValidationError("M232 form bridge package identity or official source changed")
    other = _other_files(registry_root, revision)
    with tempfile.TemporaryDirectory(prefix="cadrumo-m232-form-bridge-", dir=prepare_temporary_directory()) as scratch:
        overlay = Path(scratch) / "registry" / "aeat"
        shutil.copytree(registry_root, overlay)
        overlay_revision = overlay / "modelos" / "232" / "revisions" / revision
        overlay_export = overlay_revision / "export"
        if not overlay_export.resolve().is_relative_to(overlay.resolve()):
            raise RegistryValidationError("M232 form bridge overlay export escaped temporary root")
        shutil.rmtree(overlay_export)
        shutil.copytree(candidate_revision / "export", overlay_export)
        shutil.copy2(new_form, form_layout_fragment_path(overlay_revision))
        if _other_files(overlay, revision) != other:
            raise RegistryValidationError("M232 form bridge overlay changed another registry member")
        compile_validated_authority(
            overlay,
            source_root,
            complete_validation=True,
            verify_evidence_bytes=True,
        )
    if _other_files(registry_root, revision) != other or _sha(old_manifest) != expected_manifest_sha256:
        raise RegistryValidationError("M232 form bridge live source changed during complete validation")
    if (
        m232_interpreting_input_digest() != interpreting_digest
        or m232_evidence_content_digest(source_root) != evidence_content_digest
        or fingerprint_tree(source_root / "registry" / "cadrumo") != profile_fingerprint
    ):
        raise RegistryValidationError("M232 bridge interpreting or evidence inputs changed during validation")
    return M232FormBridge(
        revision=revision,
        source_ref=source_ref,
        source_sha256=source_sha256,
        old_form_sha256=reviewed[3],
        candidate_form_sha256=_sha(new_form),
        candidate_manifest_sha256=_sha(new_manifest),
        other_files=other,
        interpreting_digest=interpreting_digest,
        evidence_content_digest=evidence_content_digest,
        profile_schema_fingerprint=profile_fingerprint,
    )

"""First-export authoring through separate export and authored-form owners.

The existing export journal remains export-only. A fully validated overlay and
exact source receipts admit the brief stale-form interval; the form owner then
finishes it before complete live validation and any runtime publication.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copytree

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compile_validated_authority
from ..compiler.loader import load_modelo_directory
from ..export_clearance import ExportClearanceRetirement, prepare_export_clearance_retirement
from ..form_layout.reconciliation import (
    install_authored_export_reconciliation,
    reconcile_authored_export_addition,
    reconcile_export_casilla_splits,
    reconcile_unreferenced_export_producers,
)
from ..form_layout.row_binding_reconciliation import reconcile_export_row_bindings
from ..form_layout.scalar_source_reconciliation import reconcile_scalar_export_sources
from ..form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from ..registry_collapse_fingerprints import fingerprint_tree
from ._form_layout_companion import _editable_form_layout_fragment
from .generated_form_bridge import (
    _active_verified_backup,
    _other_files,
    _sha,
    generated_form_interpreting_input_digest,
    registry_evidence_content_digest,
)
from .tree_paths import require_existing_non_link
from .tree_publication_artifacts import verify_generated_export_package


@dataclass(frozen=True)
class AuthoredFormBridge:
    """Captured first-export and unchanged authored-form source receipts."""

    registry_root: Path
    source_root: Path
    modelo: str
    before: ModeloRevision
    old_form_sha256: str
    new_form_sha256: str
    manifest_sha256: str
    other_files: dict[str, str]
    interpreting_digest: str
    evidence_digest: str
    profile_fingerprint: object
    unreferenced_producers: bool = False
    old_manifest_sha256: str | None = None
    old_source: tuple[str, str] | None = None
    clearance: ExportClearanceRetirement | None = None
    casilla_splits: bool = False
    row_bindings: bool = False
    scalar_sources: dict[str, tuple[str, str]] | None = None

    def require_dependencies(self, *, transaction_backup: Path | None = None, finalized: bool = False) -> None:
        """Reject source or interpreter changes since complete prevalidation."""
        changed = []
        if generated_form_interpreting_input_digest(self.modelo) != self.interpreting_digest:
            changed.append("registry interpreter inputs")
        if registry_evidence_content_digest(self.source_root) != self.evidence_digest:
            changed.append("official evidence bytes")
        if fingerprint_tree(self.source_root / "registry" / "cadrumo") != self.profile_fingerprint:
            changed.append("profile registry")
        actual = _other_files(
            self.registry_root, self.modelo, str(self.before.id), transaction_backup=transaction_backup
        )
        expected = self.expected_other_files(finalized=finalized)
        if actual != expected:
            paths = sorted(path for path in actual.keys() | expected.keys() if actual.get(path) != expected.get(path))
            changed.append(f"registry members {paths!r}")
        if changed:
            raise RegistryValidationError(
                f"authored first-export source changed after prevalidation: {'; '.join(changed)}"
            )

    def expected_other_files(self, *, finalized: bool) -> dict[str, str]:
        """Name the exact source receipts before or after manifest retirement."""
        expected = dict(self.other_files)
        if finalized and self.clearance is not None:
            expected[f"modelos/{self.modelo}/revisions/{self.before.id}/revision.toml"] = sha256(
                self.clearance.after
            ).hexdigest()
        return expected

    def require_export_cutover(self, _registry_root: Path | None = None) -> None:
        """Validate exactly the prevalidated export plus still-unchanged old form."""
        backup = (
            _active_verified_backup(
                self.registry_root,
                self.modelo,
                str(self.before.id),
                self.manifest_sha256,
                self.old_manifest_sha256,
                reviewed_source=self.old_source,
            )
            if self.old_manifest_sha256 is not None
            else None
        )
        self.require_dependencies(transaction_backup=backup)
        revision_root = self.registry_root / "modelos" / self.modelo / "revisions" / str(self.before.id)
        if _sha(form_layout_fragment_path(revision_root)) != self.old_form_sha256:
            raise RegistryValidationError("authored first-export form changed before reconciliation")
        if _sha(revision_root / "export" / "_generation.provenance.json") != self.manifest_sha256:
            raise RegistryValidationError("authored first-export package differs from its validated candidate")
        verify_generated_export_package(revision_root / "export")

    def finish_with_form_owner(self, _registry_root: Path, _source_root: Path) -> None:
        """Install only the independently derived, receipt-matching form."""
        self.require_export_cutover()
        install_authored_export_reconciliation(
            self.registry_root / "modelos" / self.modelo,
            before=self.before,
            expected_old_sha256=self.old_form_sha256,
            expected_new_sha256=self.new_form_sha256,
            unreferenced_producers=self.unreferenced_producers,
            casilla_splits=self.casilla_splits,
            row_bindings=self.row_bindings,
            scalar_sources=self.scalar_sources,
        )
        if self.clearance is not None:
            self.clearance.install(self.registry_root / "modelos" / self.modelo)
        self.require_dependencies(finalized=True)


def prepare_authored_form_bridge(
    *,
    registry_root: Path,
    candidate_root: Path,
    source_root: Path,
    temporary_root: Path,
    modelo: str,
    revision: str,
    unreferenced_producers: bool = False,
    casilla_splits: bool = False,
    row_bindings: bool = False,
    scalar_sources: bool = False,
) -> AuthoredFormBridge:
    """Reconcile one first-export candidate and validate the complete future tree."""
    if sum((unreferenced_producers, casilla_splits, row_bindings, scalar_sources)) > 1:
        raise RegistryValidationError("choose one authored form reconciliation mode")
    replacing = unreferenced_producers or casilla_splits or row_bindings or scalar_sources
    require_existing_non_link(candidate_root, subject="authored form candidate")
    if candidate_root.resolve() == registry_root.resolve() or not candidate_root.resolve().is_relative_to(
        temporary_root.resolve()
    ):
        raise RegistryValidationError("authored form reconciliation requires an isolated candidate")
    live_revision = registry_root / "modelos" / modelo / "revisions" / revision
    candidate_revision = candidate_root / "modelos" / modelo / "revisions" / revision
    old_manifest = _sha(live_revision / "export" / "_generation.provenance.json") if replacing else None
    old_package = verify_generated_export_package(live_revision / "export") if replacing else None
    if not replacing and (live_revision / "export").exists():
        raise RegistryValidationError("authored first-export bridge refuses an existing target")
    overlay = temporary_root / "authored-form-validation" / "registry" / "aeat"
    copytree(registry_root, overlay)
    overlay_revision = overlay / "modelos" / modelo / "revisions" / revision
    copytree(candidate_revision / "export", overlay_revision / "export", dirs_exist_ok=replacing)
    before = load_modelo_directory(registry_root / "modelos" / modelo).revisions[revision]
    # The pipeline candidate may detach storage ancestry for isolated rendering.
    # Compare the actual future chain so no lineage or family metadata is waived.
    after = load_modelo_directory(overlay / "modelos" / modelo).revisions[revision]
    replacements = None
    if scalar_sources:
        old_fields = {
            str(field.id): field
            for layout in before.export_layouts
            for record in layout.records
            for field in record.fields
        }
        # The reviewed semantic mapping has already rendered these endpoints.
        # Capture exact old/new identities for the independent form-owner finish.
        replacements = {
            str(field.id): (str(old.binding if old.kind.value == "binding" else old.casilla_id), str(field.casilla_id))
            for layout in after.export_layouts
            for record in layout.records
            for field in record.fields
            if (old := old_fields.get(str(field.id))) is not None
            and old.kind.value in {"binding", "casilla"}
            and field.kind.value == "casilla"
            and field.casilla_id is not None
            and (old.kind.value == "binding" or old.casilla_id != field.casilla_id)
        }
    reconciled = (
        reconcile_scalar_export_sources(before, after, replacements=replacements)
        if replacements is not None
        else reconcile_export_row_bindings(before, after)
        if row_bindings
        else reconcile_export_casilla_splits(before, after)
        if casilla_splits
        else (
            reconcile_unreferenced_export_producers(before, after)
            if unreferenced_producers
            else reconcile_authored_export_addition(before, after)
        )
    )
    new_bytes = render_form_layout_toml(revision, reconciled).encode("utf-8")
    live_form = form_layout_fragment_path(live_revision)
    old_sha = _sha(live_form)
    other = _other_files(registry_root, modelo, revision)
    interpreting = generated_form_interpreting_input_digest(modelo)
    evidence = registry_evidence_content_digest(source_root)
    profile = fingerprint_tree(source_root / "registry" / "cadrumo")
    _editable_form_layout_fragment(candidate_revision).write_bytes(new_bytes)
    verify_generated_export_package(candidate_revision / "export")
    form_layout_fragment_path(overlay_revision).write_bytes(new_bytes)
    if _other_files(overlay, modelo, revision) != other:
        raise RegistryValidationError("authored first-export overlay changed unrelated source")
    clearance = prepare_export_clearance_retirement(registry_root / "modelos" / modelo, revision)
    if clearance is not None:
        clearance.install(overlay / "modelos" / modelo)
        candidate_clearance = prepare_export_clearance_retirement(candidate_root / "modelos" / modelo, revision)
        if candidate_clearance is not None:
            candidate_clearance.install(candidate_root / "modelos" / modelo)
    compile_validated_authority(overlay, source_root, complete_validation=True, verify_evidence_bytes=True)
    bridge = AuthoredFormBridge(
        registry_root,
        source_root,
        modelo,
        before,
        old_sha,
        sha256(new_bytes).hexdigest(),
        _sha(candidate_revision / "export" / "_generation.provenance.json"),
        other,
        interpreting,
        evidence,
        profile,
        unreferenced_producers,
        old_manifest,
        (str(old_package.source_ref), old_package.source_sha256) if old_package is not None else None,
        clearance,
        casilla_splits,
        row_bindings,
        replacements,
    )
    bridge.require_dependencies()
    target_changed = (
        _sha(live_revision / "export" / "_generation.provenance.json") != old_manifest
        if replacing
        else (live_revision / "export").exists()
    )
    if target_changed or _sha(live_form) != old_sha:
        raise RegistryValidationError("authored first-export target changed during prevalidation")
    return bridge

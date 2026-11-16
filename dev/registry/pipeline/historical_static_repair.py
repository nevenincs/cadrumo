"""Break one stale generated-target compilation cycle without granting authority.

Reviewed targets can contain retired binding identifiers, so they cannot be
a validated source authority for their own replacement. Canonical
structural components may render a temporary repair witness; only a complete
whole-registry validation of that exact one-target overlay grants the authority
used by the ordinary digest-bound publisher.

A reviewed casilla rename makes every target that names a retired casilla
unloadable at once, so no one target can be repaired while the others stay
stale. A reviewed rename set therefore compiles its structure from an overlay
with every listed export removed, renders every member and regenerates each
member's form through the form owner's generator inside that overlay, and
grants authority only after one complete validation of the whole overlay. The
set is then published by the publisher's set transaction, which installs every
member's export and generated form together or none of them.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from dev.temporary_output import prepare_temp_root

from ..compiler.authority import (
    AuthoringCandidateInspection,
    compile_structural_authority,
    compile_validated_authority,
    inspect_authoring_candidate,
)
from ..compiler.identity import RegistryIdentity, resolve_registry_identity
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.revision_export_projection import UndeclaredExportTargetError
from ..compiler.source_evidence_fingerprint import collect_source_evidence_fingerprints
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from .export_tree import render_complete_export_tree
from .export_tree_models import RenderedExportTree
from .generated_form_bridge import generated_form_interpreting_input_digest, registry_evidence_content_digest
from .render_check import (
    GeneratedExportBootstrapTransport,
    RevisionRenderInputs,
    build_revision_render_inputs,
    compare_export_tree_roots,
    revision_render_inputs,
)
from .source_defects import source_defects_for
from .tree_publication_artifacts import verify_generated_export_package

_MODELO = "232"
_SOURCE_REF = "aeat-dr-232-2016"
_SOURCE_SHA256 = "fb6802dcf8746e69331b67873cb2e5cae90c3343c69b4f4d430aecde3c56b6ad"
_OLD_MANIFEST_SHA256 = "f4e1bb800af4c511c93e0d1df74520b70cc0ee986338b57f31c46c619582d6fa"

#: Stands for the target revision in a reviewed layout id or finding. The old
#: manifest digest pins the revision the reviewed package was generated for, so
#: the revision is the invocation's, checked against that package, never
#: written into this table.
_REVISION_SLOT = "{revision}"


@dataclass(frozen=True, slots=True)
class _RepairTarget:
    source_sha256: str
    layout_id: str
    finding_count: int
    exact_findings: frozenset[str] | None = None
    stale_binding: re.Pattern[str] | None = None

    def for_revision(self, modelo: str, revision: str) -> _RepairTarget:
        """Return this reviewed target with its revision slot filled for one invocation."""
        return _RepairTarget(
            source_sha256=self.source_sha256,
            layout_id=self.layout_id.replace(_REVISION_SLOT, revision),
            finding_count=self.finding_count,
            exact_findings=(
                None
                if self.exact_findings is None
                else frozenset(finding.replace(_REVISION_SLOT, revision) for finding in self.exact_findings)
            ),
            stale_binding=re.compile(
                rf"^modelo {re.escape(modelo)} revision {re.escape(revision)}: "
                r"export field '[^']+' references unknown binding '[^']+'$"
            ),
        )


#: Reviewed repair targets keyed by (modelo, official design, old manifest SHA-256).
REVIEWED_TARGETS = {
    (_MODELO, _SOURCE_REF, _OLD_MANIFEST_SHA256): _RepairTarget(
        _SOURCE_SHA256, f"generated-modelo-{_MODELO}-{_REVISION_SLOT}-fichero", 140
    ),
    (
        "720",
        "aeat-dr-720",
        "1217b488e839465f1499fba090eeab3faa1e39e83068d7447de68467427f398d",
    ): _RepairTarget(
        "ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7",
        "modelo-720-fichero-aeat",
        9,
        frozenset(
            f"modelo 720 revision {_REVISION_SLOT}: export field 'modelo-720-{record}-{field}' "
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
                f"modelo 720 revision {_REVISION_SLOT}: form layout 'form-layout' form layout is stale: "
                "its source_state_digest no longer matches the revision; regenerate it",
            }
        )
        | frozenset(
            f"modelo 720 revision {_REVISION_SLOT}: form layout 'form-layout' shows binding "
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
        "aeat-dr-720",
        "83c26f2c7c2848ec9544889d070b071d69d24608f48bd52782a6d608039d23b9",
    ): _RepairTarget(
        "ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7",
        "modelo-720-fichero-aeat",
        6,
        frozenset(
            f"modelo 720 revision {_REVISION_SLOT}: export field 'modelo-720-{record}-{field}' "
            f"references unknown binding 'modelo-720.{record}.{field}'"
            for record in ("type_1", "type_2")
            for field in ("tipo-de-registro", "modelo-declaracion")
        )
        | frozenset(
            {
                f"modelo 720 revision {_REVISION_SLOT}: fixed-width export layout 'modelo-720-fichero-aeat' "
                "has 2 design record(s) without a unique source-to-record join, so per-record coverage is unverified. "
                "design record 'Tipo 1 - Registro De Declarante': "
                "no unique authored record joins its source constants; "
                "layout-wide byte coverage cannot verify this record | "
                "design record 'Tipo 2 - Registro De Detalle': no unique authored record joins its source constants; "
                "layout-wide byte coverage cannot verify this record",
                f"modelo 720 revision {_REVISION_SLOT}: form layout 'form-layout' form layout is stale: "
                "its source_state_digest no longer matches the revision; regenerate it",
            }
        ),
    ),
}


def validate_repair_findings(target: _RepairTarget, findings: tuple[str, ...]) -> None:
    """Require repair findings to match the target's expected count and exact findings."""
    exact = target.exact_findings
    if len(findings) != target.finding_count or (
        frozenset(findings) != exact
        if exact is not None
        else target.stale_binding is None
        or any(target.stale_binding.fullmatch(finding) is None for finding in findings)
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
    target, expected_manifest_sha256 = _reviewed_repair_target(
        modelo, revision, source_ref, filing_year, period, expected_manifest_sha256
    )
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    interpreting_digest = generated_form_interpreting_input_digest(modelo)
    evidence_content_digest = registry_evidence_content_digest(source_root)
    target_export = registry_root / "modelos" / modelo / "revisions" / revision / "export"
    old_manifest = target_export / "_generation.provenance.json"
    _require_old_repair_package(
        old_manifest, target_export, expected_manifest_sha256, modelo, revision, source_ref, target
    )
    initial_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
    )
    original = inspect_authoring_candidate(registry_root, source_root, identity=initial_identity)
    validate_repair_findings(target, original.findings)
    definition = _reviewed_repair_definition(original, source_ref, target, modelo)
    preliminary = build_revision_render_inputs(
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
    with tempfile.TemporaryDirectory(prefix=f"cadrumo-m{modelo}-static-repair-", dir=prepare_temp_root()) as scratch:
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
        _require_reproduced_repair(ordinary, preliminary_render, overlay_export, modelo, revision, source_ref)
        _require_unchanged_repair_inputs(
            registry_root,
            source_root,
            modelo,
            original,
            initial_identity,
            evidence_content_digest,
            interpreting_digest,
            old_manifest,
            expected_manifest_sha256,
        )
        return validated


def _reviewed_repair_definition(
    original: AuthoringCandidateInspection, source_ref: str, target: _RepairTarget, modelo: str
) -> ModeloDefinition:
    selected_source = original.components.catalogues.sources.get(source_ref)
    if selected_source is None or selected_source.sha256 != target.source_sha256:
        raise RegistryValidationError("historical repair selected official source changed")
    definition = next((item for item in original.components.modelos if str(item.id) == modelo), None)
    if definition is None:
        raise RegistryValidationError("historical repair structural source lacks its target modelo")
    return definition


def _reviewed_repair_target(
    modelo: str,
    revision: str,
    source_ref: str,
    filing_year: int,
    period: str,
    expected_manifest_sha256: str | None,
) -> tuple[_RepairTarget, str]:
    if expected_manifest_sha256 is None:
        raise RegistryValidationError("historical repair requires the exact reviewed target manifest")
    target = REVIEWED_TARGETS.get((modelo, source_ref, expected_manifest_sha256))
    if target is None or not _revision_selects(modelo, revision, filing_year, period):
        raise RegistryValidationError(
            "historical repair requires an exact reviewed target and manifest at a coordinate its revision selects"
        )
    return target.for_revision(modelo, revision), expected_manifest_sha256


def _revision_selects(modelo: str, revision: str, filing_year: int, period: str) -> bool:
    """Return whether the authored revision's own period selector selects the requested frame."""
    revisions = load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo)).revisions
    selected = revisions.get(revision)
    if selected is None:
        return False
    selector = selected.period_selector
    return selector.includes_year(filing_year) and period in selector.periods_for_year(filing_year)


def _require_unchanged_repair_inputs(
    registry_root: Path,
    source_root: Path,
    modelo: str,
    original: AuthoringCandidateInspection,
    initial_identity: RegistryIdentity,
    evidence_content_digest: str,
    interpreting_digest: str,
    old_manifest: Path,
    expected_manifest_sha256: str,
) -> None:
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
            path for path in before_paths.keys() | after_paths.keys() if before_paths.get(path) != after_paths.get(path)
        )
        raise RegistryValidationError(
            "historical repair live source or old target changed during validation: "
            f"inputs={changed}; registry_paths={changed_paths[:12]}; registry_path_count={len(changed_paths)}"
        )


def _require_reproduced_repair(
    ordinary: RevisionRenderInputs,
    preliminary_render: RenderedExportTree,
    overlay_export: Path,
    modelo: str,
    revision: str,
    source_ref: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"cadrumo-m{modelo}-static-rerender-", dir=prepare_temp_root()) as rerender:
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


def _require_old_repair_package(
    old_manifest: Path,
    target_export: Path,
    expected_manifest_sha256: str,
    modelo: str,
    revision: str,
    source_ref: str,
    target: _RepairTarget,
) -> None:
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


_MemberRender = tuple[RevisionRenderInputs, RenderedExportTree]


@dataclass(frozen=True, slots=True)
class _RenameRepairMember:
    source_ref: str
    source_sha256: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class _RenameRepairSet:
    modelo: str
    renamed_casilla_ids: frozenset[str]
    members: tuple[_RenameRepairMember, ...]


#: Reviewed rename repairs. Each member pins its official design and the exact
#: manifest of its committed export; the revision is the one whose committed
#: export carries that manifest, so no revision is written here. Members are
#: rendered and published in the listed order.
REVIEWED_RENAME_SETS: tuple[_RenameRepairSet, ...] = (
    _RenameRepairSet(
        "200",
        frozenset({"00524", "00525", "00526"}),
        (
            _RenameRepairMember(
                "aeat-dr-200-2024",
                "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218",
                "68dc1db25f84924598fd805df2ebc7bd5d0160630382dbb8fdb20998aa1a92a4",
            ),
            _RenameRepairMember(
                "aeat-dr-200-2025",
                "92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509",
                "013186aa4d2780d5ef75dd878f2ed98344f5b032cde3b9de8fc1fbe1ac570642",
            ),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RenameRepairTarget:
    """One reviewed member's coordinates, resolved from its committed export and authored selector."""

    revision: str
    source_ref: str
    filing_year: int
    period: str
    expected_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ValidatedRenameRepair:
    """The completely validated overlay of one reviewed rename set and its generated forms.

    ``overlay_root`` lives under the caller's temporary root and stays the
    staging source for every member's publication candidate.
    """

    authority: ValidatedRegistryAuthority
    overlay_root: Path
    targets: tuple[RenameRepairTarget, ...]
    form_fragments: dict[str, bytes]


def reviewed_rename_set(
    modelo: str,
    source_ref: str,
    manifest_sha256: str | None,
    *,
    reviewed_sets: tuple[_RenameRepairSet, ...] = REVIEWED_RENAME_SETS,
) -> _RenameRepairSet:
    """Return the reviewed rename set the invoked target and its exact manifest belong to."""
    for reviewed in reviewed_sets:
        if reviewed.modelo == modelo and any(
            (member.source_ref, member.manifest_sha256) == (source_ref, manifest_sha256) for member in reviewed.members
        ):
            return reviewed
    raise RegistryValidationError(
        "rename repair requires an exact reviewed rename-set member and its current target manifest"
    )


def validate_rename_refusal(reviewed: _RenameRepairSet, refusal: UndeclaredExportTargetError) -> None:
    """Admit the typed refusal only when it names exactly the reviewed renamed casillas of the set's modelo."""
    if (
        refusal.modelo_id != reviewed.modelo
        or len(set(refusal.casilla_ids)) != len(refusal.casilla_ids)
        or frozenset(refusal.casilla_ids) != reviewed.renamed_casilla_ids
    ):
        raise RegistryValidationError(
            "rename repair refusal names casillas beyond the reviewed rename: "
            f"modelo={refusal.modelo_id} revision={refusal.revision_id} casillas={list(refusal.casilla_ids)}"
        )


def _committed_revision(modelo_root: Path, member: _RenameRepairMember, modelo: str) -> str:
    """Return the one revision whose committed export carries the member's exact manifest."""
    matches = [
        revision_root.name
        for revision_root in sorted((modelo_root / "revisions").iterdir())
        if (manifest := revision_root / "export" / "_generation.provenance.json").is_file()
        and sha256(manifest.read_bytes()).hexdigest() == member.manifest_sha256
    ]
    if len(matches) != 1:
        raise RegistryValidationError(
            f"rename repair member {member.source_ref} manifest differs from the reviewed digest"
        )
    package = verify_generated_export_package(modelo_root / "revisions" / matches[0] / "export")
    if (str(package.modelo), str(package.revision_id), str(package.source_ref), package.source_sha256) != (
        modelo,
        matches[0],
        member.source_ref,
        member.source_sha256,
    ):
        raise RegistryValidationError("rename repair old package identity or source pin changed")
    return matches[0]


def _member_coordinates(
    definition: ModeloDefinition, revision: str, *, filing_year: int | None, period: str
) -> tuple[int, str]:
    """Use the invoked frame, or the earliest frame the member's own authored selector selects."""
    selector = definition.revisions[revision].period_selector
    year = filing_year
    if year is None:
        year = selector.year_from if selector.year_from is not None else min(selector.years or ())
    periods = tuple(str(item) for item in selector.periods_for_year(year)) if selector.includes_year(year) else ()
    if period in periods:
        return year, period
    if filing_year is None and periods:
        return year, periods[0]
    raise RegistryValidationError(f"rename repair member {revision} does not select {year}/{period}")


_LINE_ENDINGS: frozenset[str] = frozenset({"crlf", "lf", "none"})


def _committed_transport(
    export_root: Path, revision: str, member: _RenameRepairMember
) -> GeneratedExportBootstrapTransport:
    """Read the verified committed package's transport identity, which its unloadable layout cannot lend.

    The package digests were verified before this read, so the layout id and
    record line ending are the shipped ones. The validated overlay must later
    reproduce them without this bootstrap.
    """
    layouts = rtoml.load(export_root / "0000-export-layout.toml")["revisions"][revision]["export_layouts"]
    endings = {
        str(record["line_ending"])
        for fragment in sorted(export_root.glob("*-record-*.toml"))
        for layout in rtoml.load(fragment)["revisions"][revision]["export_layouts"]
        for record in layout.get("records", ())
    }
    if len(layouts) != 1 or len(endings) != 1 or not endings <= _LINE_ENDINGS:
        raise RegistryValidationError("rename repair committed package has no single layout and line ending")
    return GeneratedExportBootstrapTransport(
        layout_id=str(layouts[0]["id"]),
        line_ending=cast(Literal["crlf", "lf", "none"], endings.pop()),
        source_ref=member.source_ref,
        source_sha256=member.source_sha256,
    )


def _unchanged_files_except(root: Path, *, modelo: str, revisions: tuple[str, ...]) -> dict[str, str]:
    """Hash every member except the listed revisions' exports and generated forms."""
    excluded = tuple(f"modelos/{modelo}/revisions/{revision}/export/" for revision in revisions)
    forms = {f"modelos/{modelo}/revisions/{revision}/form_layouts/0001-form-layout.toml" for revision in revisions}
    return {
        relative: sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
        and not (relative := path.relative_to(root).as_posix()).startswith(excluded)
        and relative not in forms
    }


def _render_rename_members(
    overlay: Path,
    transports: tuple[GeneratedExportBootstrapTransport, ...],
    source_root: Path,
    modelo: str,
    reviewed: _RenameRepairSet,
    revisions: tuple[str, ...],
    invoked: int,
    filing_year: int,
    period: str,
) -> tuple[tuple[RenameRepairTarget, ...], tuple[_MemberRender, ...], RegistryCatalogues]:
    """Render every member into the overlay from the overlay's own structural compile."""
    components = compile_structural_authority(overlay, source_root)
    definition = next((item for item in components.modelos if str(item.id) == modelo), None)
    if definition is None:
        raise RegistryValidationError("rename repair structural source lacks its target modelo")
    targets: list[RenameRepairTarget] = []
    renders: list[_MemberRender] = []
    for index, (member, member_revision, transport) in enumerate(
        zip(reviewed.members, revisions, transports, strict=True)
    ):
        selected_source = components.catalogues.sources.get(member.source_ref)
        if selected_source is None or selected_source.sha256 != member.source_sha256:
            raise RegistryValidationError("rename repair selected official source changed")
        year, member_period = _member_coordinates(
            definition, member_revision, filing_year=filing_year if index == invoked else None, period=period
        )
        preliminary = build_revision_render_inputs(
            definition,
            components.catalogues,
            modelo=modelo,
            revision=member_revision,
            source_ref=member.source_ref,
            bootstrap_transport=transport,
            filing_year=year,
            period=member_period,
            source_root=source_root,
        )
        rendered = render_complete_export_tree(
            overlay / "modelos" / modelo / "revisions" / member_revision / "export",
            revision_id=preliminary.revision_id,
            joined=preliminary.joined,
            semantic_map=preliminary.semantic_map,
            transport_profile=preliminary.transport_profile,
            render_profile=preliminary.render_profile,
            render_profile_source_evidence=preliminary.render_profile_source_evidence,
            source_defects=source_defects_for(member.source_ref),
        )
        targets.append(
            RenameRepairTarget(member_revision, member.source_ref, year, member_period, member.manifest_sha256)
        )
        renders.append((preliminary, rendered))
    return tuple(targets), tuple(renders), components.catalogues


def _generate_rename_member_forms(
    overlay: Path, source_root: Path, modelo: str, revisions: tuple[str, ...], catalogues: RegistryCatalogues
) -> dict[str, bytes]:
    """Regenerate each member's form through the form owner's generator inside the overlay."""
    overlay_definition = load_modelo_directory(overlay / "modelos" / modelo)
    catalogue_sources = {str(key): value for key, value in catalogues.sources.items()}
    form_fragments: dict[str, bytes] = {}
    for member_revision in revisions:
        generated_form = generate_revision_layout(
            modelo,
            overlay_definition.revisions[member_revision],
            sources=catalogue_sources,
            data_root=source_root,
        )
        if generated_form.layout is None:
            raise RegistryValidationError(f"rename repair generated form refuses: {generated_form.failure}")
        form_fragment = form_layout_fragment_path(overlay / "modelos" / modelo / "revisions" / member_revision)
        if not form_fragment.is_file():
            raise RegistryValidationError("rename repair generated form companion is absent")
        form_fragment.write_text(
            render_form_layout_toml(member_revision, generated_form.layout), encoding="utf-8", newline="\n"
        )
        form_fragments[member_revision] = form_fragment.read_bytes()
    return form_fragments


def validated_rename_repair_source(
    *,
    refusal: UndeclaredExportTargetError,
    modelo: str,
    revision: str,
    source_ref: str,
    filing_year: int,
    period: str,
    expected_manifest_sha256: str | None,
    overlay_parent: Path,
) -> ValidatedRenameRepair:
    """Validate one reviewed rename set's whole-registry overlay before the set publisher runs."""
    reviewed = reviewed_rename_set(modelo, source_ref, expected_manifest_sha256)
    validate_rename_refusal(reviewed, refusal)
    source_root = bundled_path()
    registry_root = bundled_path("registry", "aeat")
    modelo_root = registry_root / "modelos" / modelo
    revisions = tuple(_committed_revision(modelo_root, member, modelo) for member in reviewed.members)
    invoked = next(index for index, member in enumerate(reviewed.members) if member.source_ref == source_ref)
    if revisions[invoked] != revision or refusal.revision_id not in revisions:
        raise RegistryValidationError("rename repair invocation or refusal names a revision outside the reviewed set")
    initial_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
    )
    evidence_content_digest = registry_evidence_content_digest(source_root)
    interpreting_digest = generated_form_interpreting_input_digest(modelo)
    transports = tuple(
        _committed_transport(modelo_root / "revisions" / member_revision / "export", member_revision, member)
        for member, member_revision in zip(reviewed.members, revisions, strict=True)
    )
    overlay = overlay_parent / "registry" / "aeat"
    shutil.copytree(registry_root, overlay)
    for member_revision in revisions:
        overlay_export = overlay / "modelos" / modelo / "revisions" / member_revision / "export"
        if not overlay_export.resolve().is_relative_to(overlay.resolve()):
            raise RegistryValidationError("rename repair export path escaped its temporary overlay")
        shutil.rmtree(overlay_export)
    targets, renders, catalogues = _render_rename_members(
        overlay, transports, source_root, modelo, reviewed, revisions, invoked, filing_year, period
    )
    form_fragments = _generate_rename_member_forms(overlay, source_root, modelo, revisions, catalogues)
    if _unchanged_files_except(overlay, modelo=modelo, revisions=revisions) != _unchanged_files_except(
        registry_root, modelo=modelo, revisions=revisions
    ):
        raise RegistryValidationError("rename repair overlay changed a nontarget registry member")
    validated = compile_validated_authority(overlay, source_root, verify_evidence_bytes=True, complete_validation=True)
    for target, (preliminary, rendered) in zip(targets, renders, strict=True):
        ordinary = revision_render_inputs(
            validated,
            modelo=modelo,
            revision=target.revision,
            source_ref=target.source_ref,
            filing_year=target.filing_year,
            period=target.period,
            source_root=source_root,
        )
        if ordinary != preliminary:
            raise RegistryValidationError("rename repair validated render inputs differ from structural inputs")
        _require_reproduced_repair(
            ordinary,
            rendered,
            overlay / "modelos" / modelo / "revisions" / target.revision / "export",
            modelo,
            target.revision,
            target.source_ref,
        )
    after = resolve_registry_identity(
        registry_root,
        collect_fingerprints=lambda path: collect_registry_tree_fingerprints(path, use_cache=False),
    )
    if (
        after.digest != initial_identity.digest
        or registry_evidence_content_digest(source_root) != evidence_content_digest
        or generated_form_interpreting_input_digest(modelo) != interpreting_digest
        or tuple(_committed_revision(modelo_root, member, modelo) for member in reviewed.members) != revisions
    ):
        raise RegistryValidationError("rename repair live source or old targets changed during validation")
    return ValidatedRenameRepair(validated, overlay, targets, form_fragments)

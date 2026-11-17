"""Repair a reviewed casilla-rename set of generated targets in one overlay.

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
import tomllib
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

from ..compiler.authority import (
    compile_structural_authority,
    compile_validated_authority,
)
from ..compiler.identity import resolve_registry_identity
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.revision_export_projection import UndeclaredExportTargetError
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import form_layout_fragment_path, render_form_layout_toml
from .export_tree import render_complete_export_tree
from .export_tree_models import RenderedExportTree
from .generated_form_bridge import generated_form_interpreting_input_digest, registry_evidence_content_digest
from .historical_static_repair import require_reproduced_repair
from .render_check import (
    GeneratedExportBootstrapTransport,
    RevisionRenderInputs,
    build_revision_render_inputs,
    revision_render_inputs,
)
from .source_defects import source_defects_for
from .tree_publication_artifacts import verify_generated_export_package

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


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_REVIEWED_RENAME_SETS_PATH = Path(__file__).with_name("reviewed_rename_sets.toml")


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryValidationError(f"reviewed rename sets: {where} must be a non-empty string")
    return value


def _sha256(value: object, where: str) -> str:
    text = _text(value, where)
    if _SHA256_HEX.fullmatch(text) is None:
        raise RegistryValidationError(f"reviewed rename sets: {where} must be a lowercase sha256 hex digest")
    return text


def _reviewed_member(raw: object, where: str) -> _RenameRepairMember:
    if not isinstance(raw, dict) or set(raw) != {"source_ref", "source_sha256", "manifest_sha256"}:
        raise RegistryValidationError(f"reviewed rename sets: {where} must hold exactly its source and manifest pins")
    return _RenameRepairMember(
        _text(raw["source_ref"], f"{where}.source_ref"),
        _sha256(raw["source_sha256"], f"{where}.source_sha256"),
        _sha256(raw["manifest_sha256"], f"{where}.manifest_sha256"),
    )


def _reviewed_set(raw: object, where: str) -> _RenameRepairSet:
    if not isinstance(raw, dict) or set(raw) != {"modelo", "renamed_casilla_ids", "members"}:
        raise RegistryValidationError(f"reviewed rename sets: {where} must hold its modelo, renamed ids and members")
    ids = raw["renamed_casilla_ids"]
    members = raw["members"]
    if not isinstance(ids, list) or not ids:
        raise RegistryValidationError(f"reviewed rename sets: {where}.renamed_casilla_ids must be a non-empty list")
    renamed = [_text(item, f"{where}.renamed_casilla_ids") for item in ids]
    if len(set(renamed)) != len(renamed):
        raise RegistryValidationError(f"reviewed rename sets: {where}.renamed_casilla_ids repeats an id")
    if not isinstance(members, list) or not members:
        raise RegistryValidationError(f"reviewed rename sets: {where}.members must be a non-empty list")
    return _RenameRepairSet(
        _text(raw["modelo"], f"{where}.modelo"),
        frozenset(renamed),
        tuple(_reviewed_member(member, f"{where}.members[{index}]") for index, member in enumerate(members)),
    )


def load_reviewed_rename_sets(path: Path = _REVIEWED_RENAME_SETS_PATH) -> tuple[_RenameRepairSet, ...]:
    """Read and validate the reviewed rename sets the data file next to this module declares."""
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryValidationError(f"reviewed rename sets: cannot read {path.name}: {exc}") from exc
    sets = document.get("sets")
    if set(document) != {"sets"} or not isinstance(sets, list) or not sets:
        raise RegistryValidationError(f"reviewed rename sets: {path.name} must hold a non-empty [[sets]] array only")
    return tuple(_reviewed_set(raw, f"sets[{index}]") for index, raw in enumerate(sets))


#: Reviewed rename repairs. Each member pins its official design and the exact
#: manifest of its committed export; the revision is the one whose committed
#: export carries that manifest, so no revision is written here. Members are
#: rendered and published in the listed order.
REVIEWED_RENAME_SETS: tuple[_RenameRepairSet, ...] = load_reviewed_rename_sets()


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


def _invoked_member_index(
    reviewed: _RenameRepairSet,
    revisions: tuple[str, ...],
    refusal: UndeclaredExportTargetError,
    revision: str,
    source_ref: str,
) -> int:
    invoked = next(index for index, member in enumerate(reviewed.members) if member.source_ref == source_ref)
    if revisions[invoked] != revision or refusal.revision_id not in revisions:
        raise RegistryValidationError("rename repair invocation or refusal names a revision outside the reviewed set")
    return invoked


def _copy_overlay_without_member_exports(
    registry_root: Path, overlay: Path, modelo: str, revisions: tuple[str, ...]
) -> None:
    shutil.copytree(registry_root, overlay)
    for member_revision in revisions:
        overlay_export = overlay / "modelos" / modelo / "revisions" / member_revision / "export"
        if not overlay_export.resolve().is_relative_to(overlay.resolve()):
            raise RegistryValidationError("rename repair export path escaped its temporary overlay")
        shutil.rmtree(overlay_export)


def _require_reproduced_members(
    validated: ValidatedRegistryAuthority,
    overlay: Path,
    targets: tuple[RenameRepairTarget, ...],
    renders: tuple[_MemberRender, ...],
    source_root: Path,
    modelo: str,
) -> None:
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
        require_reproduced_repair(
            ordinary,
            rendered,
            overlay / "modelos" / modelo / "revisions" / target.revision / "export",
            modelo,
            target.revision,
            target.source_ref,
        )


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
    invoked = _invoked_member_index(reviewed, revisions, refusal, revision, source_ref)
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
    _copy_overlay_without_member_exports(registry_root, overlay, modelo, revisions)
    targets, renders, catalogues = _render_rename_members(
        overlay, transports, source_root, modelo, reviewed, revisions, invoked, filing_year, period
    )
    form_fragments = _generate_rename_member_forms(overlay, source_root, modelo, revisions, catalogues)
    if _unchanged_files_except(overlay, modelo=modelo, revisions=revisions) != _unchanged_files_except(
        registry_root, modelo=modelo, revisions=revisions
    ):
        raise RegistryValidationError("rename repair overlay changed a nontarget registry member")
    validated = compile_validated_authority(overlay, source_root, verify_evidence_bytes=True, complete_validation=True)
    _require_reproduced_members(validated, overlay, targets, renders, source_root, modelo)
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

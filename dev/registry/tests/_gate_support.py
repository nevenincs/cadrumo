"""Shared helpers for registry gate tests."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.keyed_families import CASILLAS_FAMILY
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot import collect_snapshot_ref_ids

from ..compiler.loader import load_modelo_declarations, load_registry_tree
from ..compiler.validator import _runtime_legal_reference_ids

#: Catalogue directories a single-modelo scratch tree needs in order to
#: compile. The modelo's own directory is copied separately; the rest of the
#: registry is deliberately left out, because a whole-tree copy plus its
#: fingerprint walk dominates the runtime of every mutation gate and none of
#: the other modelos is read.
_SCRATCH_CATALOGUE_DIRECTORIES: Final[tuple[str, ...]] = (
    "apoderamientos",
    "categories",
    "iva",
    "legal",
    "topics",
)

#: Sections whose fragments live under a directory spelled differently from
#: the ``ModeloRevision`` field they carry.
_SECTION_DIRECTORY_NAMES: Final[dict[str, tuple[str, ...]]] = {
    "export_layouts": ("export", "export_layouts"),
}

_CASILLA_STORAGE_BASELINE: Final = "casilla_storage_baseline"
_FAMILY_STORAGE_BASELINE: Final = "family_storage_baseline"
_PREDECESSOR: Final = "predecessor"

_BASIC_STRING: Final = re.compile(r'"([^"\\\n]*)"')


def _literal_quoted(source: str) -> str:
    """The same TOML source with basic strings respelled as literal strings.

    Hand-authored declarations quote with ``"``; a generated section such as
    the export tree is written by the TOML renderer, which quotes with ``'``.
    Both spell the same declaration, so a gate anchored on meaning must not red
    merely because the renderer owns the fragment it addresses.
    """
    return _BASIC_STRING.sub(lambda match: f"'{match.group(1)}'", source)


def scratch_registry_tree(tmp_path: Path, *modelo_ids: str) -> Path:
    """Copy the named modelos and the shared catalogues into an isolated tree.

    A mutation gate re-introduces a defect in registry SOURCE to prove the
    assertion above it has teeth. That mutation never touches the tracked tree,
    and it never depends on a modelo the gate does not name.
    """
    if not modelo_ids:
        msg = "a scratch registry tree needs at least one modelo"
        raise AssertionError(msg)
    bundled_root = bundled_path("registry", "aeat")
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    for modelo_id in modelo_ids:
        shutil.copytree(bundled_root / "modelos" / modelo_id, scratch_root / "modelos" / modelo_id)
    for catalogue_dir in _SCRATCH_CATALOGUE_DIRECTORIES:
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)
    return scratch_root


def _storage_chain(modelo_directory: Path, revision_id: str, section: str) -> tuple[str, ...]:
    """The editions that can physically hold *section* for *revision_id*.

    A delta edition states only what it changes and resolves the rest from its
    storage baseline, so the fragment a gate wants to rewrite is frequently
    authored several editions back. The chain starts at the edition under test
    and follows the baseline declared for this family, falling back to the
    declared predecessor where the family names no baseline of its own.
    """
    revisions = load_modelo_declarations(modelo_directory).get("revisions")
    if not isinstance(revisions, dict):
        msg = f"{modelo_directory}: modelo declares no revisions"
        raise AssertionError(msg)
    if revision_id not in revisions:
        msg = f"{modelo_directory}: no edition {revision_id!r}; editions are {sorted(revisions)!r}"
        raise AssertionError(msg)
    baseline_field = _CASILLA_STORAGE_BASELINE if section == CASILLAS_FAMILY else _FAMILY_STORAGE_BASELINE
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = revision_id
    while isinstance(current, str) and current not in seen:
        seen.add(current)
        chain.append(current)
        table = revisions.get(current)
        declared = table.get(baseline_field) or table.get(_PREDECESSOR) if isinstance(table, dict) else None
        current = declared if isinstance(declared, str) else None
    return tuple(chain)


def _section_directories(revision_root: Path, section: str) -> tuple[Path, ...]:
    return tuple(revision_root / name for name in _SECTION_DIRECTORY_NAMES.get(section, (section,)))


@dataclass(frozen=True, slots=True)
class DeclaringFragment:
    """The one fragment that physically declares a member of an edition's family.

    ``edition`` is the edition under test only when that edition restates the
    family; otherwise it is the storage baseline the edition resolves the
    declaration from, which is where a mutation has to land for the edition
    under test to see it.
    """

    path: Path
    edition: str
    revision_id: str
    section: str

    def mutate(self, find: str, replace: str, *, after: str | None = None) -> None:
        """Rewrite one occurrence of *find*, refusing a target that is not there.

        *after* scopes the rewrite to the declaration beginning at that text,
        for a fragment whose other members spell the same term.
        """
        original = self.path.read_text(encoding="utf-8")
        candidates = (
            (find, replace, after),
            (_literal_quoted(find), _literal_quoted(replace), after if after is None else _literal_quoted(after)),
        )
        for target, replacement, scope in candidates:
            start = 0 if scope is None else original.find(scope)
            if start < 0 or target not in original[start:]:
                continue
            self.path.write_text(
                original[:start] + original[start:].replace(target, replacement, 1),
                encoding="utf-8",
            )
            return
        msg = f"{self.path}: {find!r} is not declared there -- the mutation is stale, diagnose before re-anchoring"
        raise AssertionError(msg)


def declaring_fragment(modelo_directory: Path, *, revision_id: str, section: str, anchor: str) -> DeclaringFragment:
    """The fragment an edition resolves *anchor* from, across its storage chain.

    A source-text mutation has to name the file it rewrites, and naming it by
    FILENAME rots the moment a section is re-fragmented or collapsed: gates
    addressing ``0001-export_layouts.toml`` went stale when the layout split,
    and gates addressing ``<casilla-id>.toml`` went stale again when every
    family collapsed into one aggregated fragment per edition. Resolving by
    CONTENT survives both.

    Resolving by content within ONE edition is not enough either. Under the
    delta layout an edition carries only the families it changes -- modelo 303's
    2025 edition has no ``casillas/`` or ``bindings/`` directory at all -- so
    the anchor is looked for along the edition's storage chain and the nearest
    edition declaring it wins. That is the edition the loader itself resolves
    the declaration from.

    An edition has two storage loci for one family, not one: the section
    fragments, and the overrides its ``revision.toml`` states against a
    baseline member. Modelo 303 authors box 10's projection formula as a
    ``casilla_overrides`` entry, so a search restricted to ``casillas/``
    concludes the declaration is gone when it is merely delta-authored. Both
    loci are searched for every edition on the chain.

    Zero matches anywhere on the chain means the anchor genuinely no longer
    exists, which is a real staleness the caller must diagnose rather than
    paper over -- do NOT respond by pointing the anchor at a nearby string,
    because a mutation retargeted at a convenient neighbour mutates something
    the gate was never about. More than one match within one edition means a
    single-occurrence rewrite would silently pick the first, so the mutation
    would no longer be the one the test describes.

    Args:
        modelo_directory: The modelo root holding ``revisions/``.
        revision_id: The edition under test.
        section: The revision family the declaration belongs to.
        anchor: The exact source text the caller intends to rewrite.

    Returns:
        The single fragment declaring *anchor*, with the edition holding it.
    """
    chain = _storage_chain(modelo_directory, revision_id, section)
    spellings = (anchor, _literal_quoted(anchor))
    for edition in chain:
        revision_root = modelo_directory / "revisions" / edition
        candidates: list[Path] = []
        for directory in _section_directories(revision_root, section):
            if directory.is_dir():
                candidates.extend(scan_directory(directory, pattern="*.toml"))
        manifest = revision_root / "revision.toml"
        if manifest.is_file():
            candidates.append(manifest)
        matches = [
            path for path in candidates if any(spelling in path.read_text(encoding="utf-8") for spelling in spellings)
        ]
        if not matches:
            continue
        if len(matches) > 1:
            named = ", ".join(path.name for path in matches)
            msg = (
                f"{anchor!r} appears in {len(matches)} files of edition {edition} "
                f"({named}); a single-occurrence mutation is ambiguous"
            )
            raise AssertionError(msg)
        return DeclaringFragment(path=matches[0], edition=edition, revision_id=revision_id, section=section)
    msg = (
        f"no fragment declares {anchor!r} for {section} of edition {revision_id!r} "
        f"(storage chain {list(chain)!r}) -- the gate is stale, diagnose before re-anchoring"
    )
    raise AssertionError(msg)


def _m130_definition() -> ModeloDefinition:
    modelos, _full = load_registry_tree(bundled_path("registry", "aeat"))
    return next(item for item in modelos if str(item.id) == "130")


def _m130_declared_reference_ids(modelo: ModeloDefinition) -> tuple[set[str], set[str]]:
    legal_ids: set[str] = {str(ref) for ref in modelo.legal_refs}
    source_ids: set[str] = {str(ref) for ref in modelo.source_refs}
    for revision in modelo.revisions.values():
        revision_legal, revision_sources = collect_snapshot_ref_ids(modelo, revision)
        legal_ids.update(str(ref) for ref in revision_legal)
        source_ids.update(str(ref) for ref in revision_sources)
    return legal_ids, source_ids


def _catalogue_carried_reference_ids(catalogues: RegistryCatalogues) -> tuple[frozenset[str], frozenset[str]]:
    """Return the legal and source ids the catalogues themselves cite, modelo aside."""
    legal = set(_runtime_legal_reference_ids(catalogues.runtime))
    sources: set[str] = set()
    for fact in catalogues.facts.facts.values():
        for variant in fact.variants:
            legal.update(str(ref) for ref in variant.legal_refs)
            sources.update(str(ref) for ref in variant.source_refs)
            sources.update(str(citation.source_ref) for citation in variant.source_citations)
    return frozenset(legal), frozenset(sources)


def catalogues_for_m130_gate_tests(catalogues: RegistryCatalogues) -> RegistryCatalogues:
    """Narrow ``catalogues`` to exactly the refs modelo 130 declares.

    The modelo 130 gate tests validate against a NARROWED catalogue, so a rule
    leaning on an unrelated entry is caught. The narrowing was a hand-listed set
    of eight legal ids, and it went stale the moment modelo 130's applicability
    rule began citing `trlirnr-rdleg-5-2004:art-2`: every case then failed on
    "references unknown legal id", an artefact of the isolation rather than a
    defect in what it validates.

    Derived from the modelo's own declared refs instead. It stays a REAL
    narrowing -- the walk collects only what this modelo cites, never the whole
    catalogue -- and it cannot go stale, because a newly cited ref joins it the
    same way the modelo declares it.
    """
    modelo = _m130_definition()
    legal_ids, _source_ids = _m130_declared_reference_ids(modelo)
    # The catalogues carry more than one modelo's declarations: the runtime
    # tables and the governed facts cite their own legal and source identities,
    # and catalogue validation checks those whichever modelo is being validated.
    # Narrowing to the modelo's refs alone left them dangling, so every case
    # here failed on "references unknown legal id" -- again an artefact of the
    # isolation rather than a defect in what it validates. The narrowing stays
    # real for the MODELO's own refs, which is what these gates isolate.
    carried_legal, _carried_sources = _catalogue_carried_reference_ids(catalogues)
    legal_ids = legal_ids | carried_legal
    return catalogues.model_copy(
        update={
            "legal": {ref_id: catalogues.legal[ref_id] for ref_id in sorted(legal_ids) if ref_id in catalogues.legal},
            # The SOURCE map stays whole. These gates validate against the real
            # bundled source root, and the source-side checks walk that root:
            # the semantic-annotation check reads every annotation sidecar under
            # it and requires a declared source target for each. A narrowed map
            # contradicts the root the validator is reading, so it reported
            # annotations of other modelos as untargeted. The legal narrowing
            # above is what these gates isolate, and it still holds.
        },
    )

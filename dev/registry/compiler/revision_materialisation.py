"""Resolve raw revision chains into materialised tables and aligned row origins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.keyed_families import (
    KEYED_FAMILY_SPECS,
    KeyedFamilySpec,
)
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from cadrumo.domain.calculations.registry.revision_contracts import validate_predecessor_forest
from dev.registry.compiler.toml_helpers import as_toml_table

from . import casilla_inheritance, family_disposition_inheritance, keyed_family_inheritance
from .casilla_inheritance import LabelOrigins
from .loader_fields import (
    CASILLA_STORAGE_BASELINE_FIELD,
    CLEARED_FAMILIES_FIELD,
    DISPOSITIONS_FIELD,
    FAMILY_STORAGE_BASELINE_FIELD,
    INHERITED_SECTION,
    NO_PREDECESSOR_TABLE_KEY,
    PREDECESSOR_FIELD,
)

_KEYED_FAMILIES: Final[tuple[KeyedFamilySpec, ...]] = KEYED_FAMILY_SPECS

_REVISION_ID_ADAPTER: Final = TypeAdapter(RevisionId)


@dataclass(frozen=True, slots=True)
class _RawPredecessorDeclarations:
    """Each edition's predecessor declaration, read from the raw revision tables."""

    named: Mapping[str, str]
    declared_roots: frozenset[str]
    keyless: frozenset[str]


def raw_predecessor_declarations(raw_revisions: Mapping[str, object]) -> _RawPredecessorDeclarations | None:
    """Project every edition's authored ``predecessor`` onto the three declaration states.

    Returns ``None`` when any edition is not a table or spells its declaration
    in a shape no state admits. Materialisation then does nothing, and typed
    construction refuses the malformed edition with the declaration's own
    error rather than one this projection would have to invent.
    """
    named: dict[str, str] = {}
    declared_roots: set[str] = set()
    keyless: set[str] = set()
    for revision_id, raw_revision in raw_revisions.items():
        table = as_toml_table(raw_revision)
        if table is None:
            return None
        declaration = table.get(PREDECESSOR_FIELD)
        if declaration is None:
            keyless.add(revision_id)
        elif isinstance(declaration, str) and _is_revision_id(declaration):
            named[revision_id] = declaration
        elif isinstance(declaration, Mapping) and set(declaration) == {NO_PREDECESSOR_TABLE_KEY}:
            declared_roots.add(revision_id)
        else:
            return None
    return _RawPredecessorDeclarations(
        named=named,
        declared_roots=frozenset(declared_roots),
        keyless=frozenset(keyless),
    )


def _is_revision_id(value: str) -> bool:
    try:
        _REVISION_ID_ADAPTER.validate_python(value)
    except ValidationError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class _MaterialisedRevisions:
    """Every edition's raw table after materialisation, with the label origins of the inherited rows.

    The origins travel beside the tables rather than inside them because the
    raw table must stay the exact shape the closed typed model accepts. Only an
    edition that inherits appears in ``label_origins``.
    """

    revisions: Mapping[str, object]
    label_origins: Mapping[str, LabelOrigins]
    text_origins: Mapping[str, LabelOrigins] = dataclass_field(default_factory=dict)
    """Per inheriting edition, the edition whose catalogue holds each row's text.

    It differs from ``label_origins`` only for a row a storage patch restates
    without changing its label identity: the patch makes the row stated for
    reference resolution and minimality, but its text still lives where the
    edition that stated the row put it.
    """


@dataclass(frozen=True, slots=True)
class _MaterialisedRevision:
    """One edition resolved against its chain; ``label_origins`` is ``None`` when it inherits nothing."""

    table: Mapping[str, object]
    label_origins: LabelOrigins | None
    text_origins: LabelOrigins | None = None


def materialise_revisions(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
) -> _MaterialisedRevisions:
    """Resolve every edition naming a predecessor into the full raw revision it stands for.

    The output has the shape typed construction already consumes, one raw
    table per edition in declaration order, so nothing downstream can tell a
    materialised edition from one that states every row itself.

    An edition is delta-authored only when its manifest names a predecessor.
    Nothing here infers one: an edition omitting the key, or declaring that no
    predecessor exists, is returned as the identical object it arrived as, and
    a modelo none of whose editions names a predecessor is returned whole.

    Inheritance covers the casilla family and nothing else. Every other family
    is declared in full by every edition. The completeness manifest is excluded
    deliberately, not by omission: its rows are casilla-shaped, but a manifest
    is a derived assertion about its own edition's formula closure, and its
    presence is a graded capability claim, so an inherited one would attest
    support the successor never earned.

    Within the casilla family, rows are matched on ``continuidad_id``:

    - an inherited row is kept unless a stated row carries its lineage, in
      which case the stated row replaces it in its position. A kept row loses
      ``continuidad_origin`` and ``continuidad_evidence`` and is otherwise
      unchanged: both state the row's relationship to the edition before the
      one that stated it, which is false one edition later;
    - a stated row carrying no inherited lineage is new and is appended after
      the inherited rows, in stated order;
    - an inherited row whose lineage the successor retires, through a
      ``retired`` casilla evolution whose ``to_revision`` is the successor, is
      dropped.

    That fixes the materialised row order: inherited rows in the predecessor's
    materialised order, each superseding row in the position of the row it
    supersedes, and new rows after them in stated order. The order is defined
    by this merge, not reproduced from any full copy the edition replaced.

    Refused, because each would otherwise resolve silently to a guess:

    - a stated row whose id collides with an inherited row it does not
      supersede, which is a repurpose nobody declared; two rows without lineage
      sharing an id are refused the same way, since supersession has no key;
    - two stated rows carrying one lineage, or a stated lineage that the
      predecessor carries on more than one row;
    - a stated row carrying a lineage the same edition retires.

    The predecessor graph is checked as a forest first, so the recursion walks
    a tree and a chain resolves its predecessor before the successor. Every
    edge is a storage relationship only; it neither changes nor constrains the
    successor's independently declared capability.

    Where it stops: an inherited row keeps the formula and binding references
    its stating edition authored; the label origins returned beside the rows
    are what lets them be resolved against the successor afterwards. It adds no
    locale identity to the rows either; enrolment afterwards derives every
    row's keys from the edition it now sits in, and the label origins returned
    beside the rows let enrolment add the one fallback an inherited row needs.
    The same origins become each typed row's ``inherited_from`` marker after
    enrolment; the raw rows carry no marker, so a materialised table written
    back as a full copy states nothing the loader would refuse.
    """
    family_disposition_inheritance.refuse_authored_disposition_markers(source_path, raw_revisions)
    declarations = raw_predecessor_declarations(raw_revisions)
    storage_named, family_storage_named = _storage_baselines(source_path, raw_revisions)
    if not _requires_materialisation(declarations, storage_named, family_storage_named):
        family_disposition_inheritance.refuse_removals_without_predecessor(source_path, raw_revisions)
        return _MaterialisedRevisions(revisions=raw_revisions, label_origins={})
    _validate_predecessor_declarations(source_path, modelo_id, declarations)
    semantic_named = {} if declarations is None else declarations.named
    return _materialise_revision_set(
        source_path,
        modelo_id,
        raw_revisions,
        semantic_named,
        storage_named,
        family_storage_named,
    )


def _storage_baselines(source_path: Path, raw_revisions: Mapping[str, object]) -> tuple[dict[str, str], dict[str, str]]:
    storage_named: dict[str, str] = {}
    family_storage_named: dict[str, str] = {}
    for revision_id, raw_revision in raw_revisions.items():
        table = as_toml_table(raw_revision)
        baseline = None if table is None else table.get(CASILLA_STORAGE_BASELINE_FIELD)
        if isinstance(baseline, str):
            if baseline == revision_id or baseline not in raw_revisions:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} has invalid casilla storage baseline {baseline!r}"
                )
            storage_named[revision_id] = baseline
        family_baseline = None if table is None else table.get(FAMILY_STORAGE_BASELINE_FIELD)
        if isinstance(family_baseline, str):
            if family_baseline == revision_id or family_baseline not in raw_revisions:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} has invalid family storage baseline {family_baseline!r}"
                )
            family_storage_named[revision_id] = family_baseline
    return storage_named, family_storage_named


def _requires_materialisation(
    declarations: _RawPredecessorDeclarations | None,
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
) -> bool:
    return bool((declarations is not None and declarations.named) or storage_named or family_storage_named)


def _validate_predecessor_declarations(
    source_path: Path,
    modelo_id: str,
    declarations: _RawPredecessorDeclarations | None,
) -> None:
    if declarations is None or not declarations.named:
        return
    try:
        validate_predecessor_forest(
            modelo_id,
            named=declarations.named,
            declared_roots=declarations.declared_roots,
            keyless=declarations.keyless,
        )
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def _materialise_revision_set(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    semantic_named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
) -> _MaterialisedRevisions:
    resolved: dict[str, _MaterialisedRevision] = {}
    materialised: dict[str, object] = dict(raw_revisions)
    label_origins: dict[str, LabelOrigins] = {}
    text_origins: dict[str, LabelOrigins] = {}
    revision_ids = dict.fromkeys((*semantic_named, *storage_named, *family_storage_named))
    for revision_id in revision_ids:
        revision = _materialise_revision(
            source_path,
            modelo_id,
            raw_revisions,
            semantic_named,
            storage_named,
            family_storage_named,
            revision_id,
            resolved,
        )
        materialised[revision_id] = revision.table
        _record_origins(revision_id, revision, label_origins, text_origins)
    return _MaterialisedRevisions(revisions=materialised, label_origins=label_origins, text_origins=text_origins)


def _record_origins(
    revision_id: str,
    revision: _MaterialisedRevision,
    label_origins: dict[str, LabelOrigins],
    text_origins: dict[str, LabelOrigins],
) -> None:
    if revision.label_origins is not None:
        label_origins[revision_id] = revision.label_origins
    if revision.text_origins is not None:
        text_origins[revision_id] = revision.text_origins


def _materialise_revision(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
    revision_id: str,
    resolved: dict[str, _MaterialisedRevision],
) -> _MaterialisedRevision:
    """Return one edition with its predecessor chain's casillas resolved into it."""
    cached = resolved.get(revision_id)
    if cached is not None:
        return cached
    table = _revision_table(source_path, revision_id, raw_revisions)
    predecessor_id = named.get(revision_id)
    casilla_baseline_id = predecessor_id or storage_named.get(revision_id)
    family_baseline_id = predecessor_id or family_storage_named.get(revision_id)
    if casilla_baseline_id is None and family_baseline_id is None:
        family_disposition_inheritance.inherit_family_dispositions(
            f"{source_path}: revision {revision_id!r}",
            modelo_id=modelo_id,
            baseline_id=None,
            predecessor=None,
            successor=table,
        )
        result = _MaterialisedRevision(table=table, label_origins=None)
    else:
        rows, label_origins, text_origins = _materialise_revision_casillas(
            source_path,
            modelo_id,
            raw_revisions,
            named,
            storage_named,
            family_storage_named,
            revision_id,
            predecessor_id,
            casilla_baseline_id,
            table,
            resolved,
        )
        merged: dict[str, object] = {**table, INHERITED_SECTION: rows}
        restated = keyed_family_inheritance.restated_families(table)
        if family_baseline_id is not None:
            _inherit_revision_families(
                source_path,
                modelo_id,
                raw_revisions,
                named,
                storage_named,
                family_storage_named,
                revision_id,
                family_baseline_id,
                restated,
                rows,
                table,
                merged,
                resolved,
            )
        _inherit_revision_dispositions(
            source_path,
            modelo_id,
            raw_revisions,
            named,
            storage_named,
            family_storage_named,
            revision_id,
            family_baseline_id,
            table,
            merged,
            resolved,
        )
        result = _MaterialisedRevision(table=merged, label_origins=label_origins, text_origins=text_origins)
    resolved[revision_id] = result
    return result


def _revision_table(
    source_path: Path,
    revision_id: str,
    raw_revisions: Mapping[str, object],
) -> Mapping[str, object]:
    table = as_toml_table(raw_revisions[revision_id])
    if table is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
    return table


def _materialise_revision_casillas(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
    revision_id: str,
    predecessor_id: str | None,
    baseline_id: str | None,
    table: Mapping[str, object],
    resolved: dict[str, _MaterialisedRevision],
) -> tuple[tuple[object, ...], LabelOrigins | None, LabelOrigins | None]:
    if baseline_id is None:
        return raw_casilla_rows(source_path, revision_id, table), None, None
    predecessor = _materialise_revision(
        source_path, modelo_id, raw_revisions, named, storage_named, family_storage_named, baseline_id, resolved
    )
    relation = "inheriting from" if predecessor_id is not None else "hydrating casillas from"
    rows, label_origins, text_origins = casilla_inheritance.inherit_casillas(
        f"{source_path}: revision {revision_id!r} {relation} {baseline_id!r}",
        revision_id=revision_id,
        predecessor_id=baseline_id,
        inherited=raw_casilla_rows(source_path, baseline_id, predecessor.table),
        inherited_label_origins=predecessor.label_origins,
        inherited_text_origins=predecessor.text_origins,
        successor=table,
    )
    return rows, label_origins, text_origins


def _inherit_revision_families(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
    revision_id: str,
    baseline_id: str,
    restated: frozenset[str],
    rows: tuple[object, ...],
    successor: Mapping[str, object],
    merged: dict[str, object],
    resolved: dict[str, _MaterialisedRevision],
) -> None:
    predecessor = _materialise_revision(
        source_path, modelo_id, raw_revisions, named, storage_named, family_storage_named, baseline_id, resolved
    )
    asserted = as_toml_array(successor.get("scoped_families", ())) or ()
    declined = cleared_family_names(successor.get(CLEARED_FAMILIES_FIELD, ()))
    for family in _KEYED_FAMILIES:
        if family.section in restated:
            continue
        members = _materialise_one_family(
            source_path,
            revision_id,
            baseline_id,
            family,
            predecessor.table,
            rows,
            successor,
            asserted,
            declined,
        )
        if members is not None:
            merged[family.section] = members


def _inherit_revision_dispositions(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    storage_named: Mapping[str, str],
    family_storage_named: Mapping[str, str],
    revision_id: str,
    baseline_id: str | None,
    successor: Mapping[str, object],
    merged: dict[str, object],
    resolved: dict[str, _MaterialisedRevision],
) -> None:
    """Replace the edition's authored dispositions with its effective ones, over the family link."""
    predecessor = (
        None
        if baseline_id is None
        else _materialise_revision(
            source_path, modelo_id, raw_revisions, named, storage_named, family_storage_named, baseline_id, resolved
        ).table
    )
    effective = family_disposition_inheritance.inherit_family_dispositions(
        f"{source_path}: revision {revision_id!r} inheriting from {baseline_id!r}",
        modelo_id=modelo_id,
        baseline_id=baseline_id,
        predecessor=predecessor,
        successor=successor,
    )
    if effective:
        merged[DISPOSITIONS_FIELD] = effective


def _materialise_one_family(
    source_path: Path,
    revision_id: str,
    baseline_id: str,
    family: KeyedFamilySpec,
    predecessor: Mapping[str, object],
    rows: tuple[object, ...],
    successor: Mapping[str, object],
    asserted: tuple[object, ...],
    declined: frozenset[str],
) -> object | None:
    context = f"{source_path}: revision {revision_id!r} inheriting from {baseline_id!r}"
    inherited = keyed_family_inheritance.raw_keyed_members(source_path, baseline_id, predecessor, family)
    if family.scoped and family.section not in asserted:
        keyed_family_inheritance.refuse_undecided_scoped_family(
            context,
            family=family,
            inherited=inherited,
            stated=keyed_family_inheritance.raw_keyed_members(source_path, revision_id, successor, family),
            declined=declined,
        )
        return None
    family_members = keyed_family_inheritance.inherit_keyed_family(
        context,
        revision_id=revision_id,
        predecessor_id=baseline_id,
        predecessor=predecessor,
        family=family,
        inherited=inherited,
        inherited_casillas=raw_casilla_rows(source_path, baseline_id, predecessor),
        successor_casillas=rows,
        successor=successor,
    )
    if family.singleton:
        return family_members[0] if family_members else None
    return family_members


def raw_casilla_rows(source_path: Path, revision_id: str, table: Mapping[str, object]) -> tuple[object, ...]:
    rows = as_toml_array(table.get(INHERITED_SECTION, ()))
    if rows is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} casillas must be an array")
    return rows

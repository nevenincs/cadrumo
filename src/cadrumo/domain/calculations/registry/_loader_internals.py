"""Registry TOML loading internals.

The loading contract lives in :mod:`loader`; the fragment merge, the numbered-
fragment grammar, the directory walk and the memoised load paths are here, so a
caller outside this package cannot bind to a compilation step or a cache the
contract does not promise.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from ....core.authority_grade import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
from ....core.directory_scan import (
    DirectoryEntryKind,
    scan_directory,
)
from ....core.filing_producer_key import FilingProducerKey
from ....core.filing_projection_ref import compile_filing_projection_ref
from ....core.toml import freeze_toml, read_toml
from ._loader_revision_fragments import (
    REVISION_SECTION_FIELDS as _REVISION_SECTION_FIELDS,
)
from ._loader_revision_fragments import (
    merge_revision_fragment as _merge_revision_fragment,
)
from ._loader_revision_fragments import (
    merge_revision_manifest as _merge_revision_manifest,
)
from ._loader_revision_fragments import (
    reject_local_catalogues as _reject_local_catalogues,
)
from ._toml_helpers import as_toml_table as _as_toml_table
from .errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryLoadError,
    RegistryValidationError,
)
from .export_field_casilla import derive_casilla_export_refs
from .export_semantics import ExportComputedKey, ExportDraftAttribute
from .identifier_lineage import identifier_lineage
from .ids import RevisionId
from .loader_cache import (
    BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    is_bundled_registry_root,
    toml_file_fingerprint,
)
from .loader_cache import (
    ModeloRevisionSource as _ModeloRevisionSource,
)
from .loader_fingerprints import (
    _registry_fingerprint_cache,
    bind_tree_fingerprint_collectors,
)
from .loader_fingerprints import (
    clear_fingerprint_cache as _clear_fingerprint_cache,
)
from .loader_fingerprints import (
    refresh_toml_fingerprint_after_load_error as _refresh_toml_fingerprint_after_load_error,
)
from .modelo_localization import (
    ModeloLocalizationFieldKind,
    as_toml_array,
    casilla_occurrence_locale_key,
    enroll_revision_localization,
    modelo_locale_key,
)
from .revision_predecessor_forest import validate_predecessor_forest
from .schema import (
    REVISION_GOVERNANCE_FIELDS as _REVISION_GOVERNANCE_FIELDS,
)
from .schema import (
    REVISION_MANIFEST_ONLY_FIELDS as _REVISION_MANIFEST_ONLY_FIELDS,
)
from .schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SupportedFilingYearsCatalogue,
)
from .schema_references import LegalParameter, LegalReference, SourceReference
from .schema_surfaces import CasillaDefinition, CasillaEvolutionKind
from .validate_revision_identity import revision_reference_identity_failures

_PREDECESSOR_FIELD: Final = "predecessor"
_AUTHORITY_GRADE_FIELD: Final = "authority_grade"
_NO_PREDECESSOR_TABLE_KEY: Final = "none"
_INHERITED_SECTION: Final = "casillas"
_RETIREMENT_SECTION: Final = "casilla_continuidad_evolutions"
_EDITION_SOURCE_DEFAULT_FIELD: Final = "casilla_source_refs"
_EDITION_ORDEN_FIELD: Final = "orden_aplicabilidad"
_ROW_SOURCE_FIELD: Final = "source_refs"
_ROW_LEGAL_FIELD: Final = "legal_refs"
_ROW_CONSTRAINTS_FIELD: Final = "constraints"
_EXPORT_REFS_FIELD: Final = "export_refs"
_REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}
"""Each casilla reference field, and the edition section whose declarations it names."""
_REVISION_ID_ADAPTER: Final = TypeAdapter(RevisionId)

ModeloRevisionSource = _ModeloRevisionSource
clear_fingerprint_cache = _clear_fingerprint_cache
REVISION_GOVERNANCE_FIELDS = _REVISION_GOVERNANCE_FIELDS
REVISION_MANIFEST_ONLY_FIELDS = _REVISION_MANIFEST_ONLY_FIELDS
type _RegistryPathFingerprint = tuple[str, int, int, str]
type _RegistryPathFingerprints = tuple[_RegistryPathFingerprint, ...]


def load_modelo_file(path: Path) -> ModeloDefinition:
    """Load one modelo TOML file into strict schema objects.

    Returns:
        The compiled :class:`ModeloDefinition` from the TOML file.
    """
    resolved = path.resolve()
    fingerprint = _toml_fingerprint(resolved)
    try:
        return _load_modelo_file_cached(str(resolved), fingerprint[1], fingerprint[2], fingerprint[3])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_modelo_file_cached(str(resolved), refreshed[1], refreshed[2], refreshed[3])


@lru_cache(maxsize=256)
def _load_modelo_file_cached(path: str, byte_count: int, modified_ns: int, content_digest: str) -> ModeloDefinition:
    del byte_count, modified_ns, content_digest
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    return _build_modelo_definition_from_data(source_path, data)


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, object]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = _as_toml_table(data["modelo"])
    if modelo_table is None:
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
    declared_revisions = _as_toml_table(data.get("revisions"))
    if not declared_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    materialised = _materialise_revisions(source_path, str(modelo_id_for_context), declared_revisions)
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in materialised.revisions.items():
        raw_revision_table = _as_toml_table(raw_revision)
        if raw_revision_table is None:
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        label_origins = materialised.label_origins.get(revision_id)
        if label_origins is not None:
            raw_revision_table = _resolve_inherited_references(
                source_path,
                revision_id=revision_id,
                table=raw_revision_table,
                label_origins=label_origins,
            )
        raw_revision_table = _apply_edition_reference_defaults(raw_revision_table)
        payload = enroll_revision_localization(
            modelo_id=str(modelo_id_for_context),
            revision_id=revision_id,
            raw_revision=raw_revision_table,
        )
        if label_origins is not None:
            payload = _enroll_inherited_label_fallbacks(
                f"{source_path}: revision {revision_id!r}",
                modelo_id=str(modelo_id_for_context),
                payload=payload,
                label_origins=label_origins,
            )
        payload = _compile_revision_projection_semantics(source_path, payload)
        _refuse_authored_export_refs(source_path, revision_id, payload)
        try:
            revision = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
        revision = _with_derived_export_refs(source_path, revision, payload)
        _raise_on_ambiguous_revision_identity(
            source_path,
            modelo_id=modelo_id_for_context,
            revision_id=revision_id,
            revision=revision,
        )
        revisions[revision_id] = revision
    try:
        return ModeloDefinition.model_validate(
            {
                **modelo_table,
                "title_localization_key": modelo_locale_key(str(modelo_id_for_context), "title"),
                "official_name_localization_key": modelo_locale_key(str(modelo_id_for_context), "official_name"),
                "revisions": revisions,
            }
        )
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


@dataclass(frozen=True, slots=True)
class _RawPredecessorDeclarations:
    """Each edition's predecessor declaration, read from the raw revision tables."""

    named: Mapping[str, str]
    declared_roots: frozenset[str]
    keyless: frozenset[str]


def _raw_predecessor_declarations(raw_revisions: Mapping[str, object]) -> _RawPredecessorDeclarations | None:
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
        table = _as_toml_table(raw_revision)
        if table is None:
            return None
        declaration = table.get(_PREDECESSOR_FIELD)
        if declaration is None:
            keyless.add(revision_id)
        elif isinstance(declaration, str) and _is_revision_id(declaration):
            named[revision_id] = declaration
        elif isinstance(declaration, Mapping) and set(declaration) == {_NO_PREDECESSOR_TABLE_KEY}:
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


type _LabelOrigins = tuple[str | None, ...]
"""Per casilla row, in row order: the edition that last stated the row, or ``None`` if its own edition states it."""


@dataclass(frozen=True, slots=True)
class _MaterialisedRevisions:
    """Every edition's raw table after materialisation, with the label origins of the inherited rows.

    The origins travel beside the tables rather than inside them because the
    raw table must stay the exact shape the closed typed model accepts. Only an
    edition that inherits appears in ``label_origins``.
    """

    revisions: Mapping[str, object]
    label_origins: Mapping[str, _LabelOrigins]


@dataclass(frozen=True, slots=True)
class _MaterialisedRevision:
    """One edition resolved against its chain; ``label_origins`` is ``None`` when it inherits nothing."""

    table: Mapping[str, object]
    label_origins: _LabelOrigins | None


def _materialise_revisions(
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

    - an inherited row is kept unchanged unless a stated row carries its
      lineage, in which case the stated row replaces it in its position;
    - a stated row carrying no inherited lineage is new and is appended after
      the inherited rows, in stated order;
    - an inherited row whose lineage the successor retires, through a
      ``retired`` casilla evolution whose ``to_revision`` is the successor, is
      dropped.

    Refused, because each would otherwise resolve silently to a guess:

    - a stated row whose id collides with an inherited row it does not
      supersede, which is a repurpose nobody declared; two rows without lineage
      sharing an id are refused the same way, since supersession has no key;
    - two stated rows carrying one lineage, or a stated lineage that the
      predecessor carries on more than one row;
    - a stated row carrying a lineage the same edition retires.

    The predecessor graph is checked as a forest first, so the recursion walks
    a tree and a chain resolves its predecessor before the successor. Every
    edge is then refused where the successor declares a lower authority grade
    than its predecessor, before anything is inherited.

    Where it stops: an inherited row keeps the formula and binding references
    its stating edition authored; the label origins returned beside the rows
    are what lets them be resolved against the successor afterwards. It adds no
    locale identity to the rows either; enrolment afterwards derives every
    row's keys from the edition it now sits in, and the label origins returned
    beside the rows let enrolment add the one fallback an inherited row needs.
    """
    declarations = _raw_predecessor_declarations(raw_revisions)
    if declarations is None or not declarations.named:
        return _MaterialisedRevisions(revisions=raw_revisions, label_origins={})
    try:
        validate_predecessor_forest(
            modelo_id,
            named=declarations.named,
            declared_roots=declarations.declared_roots,
            keyless=declarations.keyless,
        )
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc
    _refuse_predecessor_above_successor_grade(source_path, raw_revisions, declarations.named)
    resolved: dict[str, _MaterialisedRevision] = {}
    materialised: dict[str, object] = dict(raw_revisions)
    label_origins: dict[str, _LabelOrigins] = {}
    for revision_id in declarations.named:
        revision = _materialise_revision(
            source_path,
            raw_revisions,
            declarations.named,
            revision_id,
            resolved,
        )
        materialised[revision_id] = revision.table
        if revision.label_origins is not None:
            label_origins[revision_id] = revision.label_origins
    return _MaterialisedRevisions(revisions=materialised, label_origins=label_origins)


def _refuse_predecessor_above_successor_grade(
    source_path: Path,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
) -> None:
    """Refuse a declared predecessor whose authority grade outranks its successor's.

    A successor declaring a lower grade than its predecessor withholds by
    design: it deliberately claims less than the edition before it. Inheriting
    there would carry the predecessor's rows into an edition that chose not to
    state them, turning an honest deferral into a complete-looking edition, so
    such a successor must stay full-copy. The minimality screen cannot see this,
    because a sparse successor's stated rows match nothing inherited.

    The comparison reads the declared ``authority_grade`` of both editions, never
    their row counts. An undeclared grade reads as
    :data:`~cadrumo.core.authority_grade.UNDECLARED_REGISTRY_AUTHORITY_GRADE`, the
    floor, so an ungraded successor of a graded predecessor above that floor is
    refused. A token that names no grade is left to typed construction, which
    refuses the edition with the grade field's own error.

    Where it stops: an edition declaring only a header while refusing to state
    figures it cannot ground is refused only when that refusal also lowers its
    declared grade. Nothing in the schema declares header-only withholding at an
    equal grade, and this check does not infer it from how many rows an edition
    carries.
    """
    ladder = tuple(RegistryAuthorityGrade)
    for successor_id, predecessor_id in named.items():
        successor_grade = _declared_authority_grade(raw_revisions.get(successor_id))
        predecessor_grade = _declared_authority_grade(raw_revisions.get(predecessor_id))
        if successor_grade is None or predecessor_grade is None:
            continue
        if ladder.index(successor_grade) >= ladder.index(predecessor_grade):
            continue
        raise RegistryLoadError(
            f"{source_path}: revision {successor_id!r} declares predecessor {predecessor_id!r}, but its authority "
            f"grade {successor_grade.value!r} is lower than the predecessor's {predecessor_grade.value!r}; an "
            "edition withholding by design must state every row itself, so remove the predecessor declaration"
        )


def _declared_authority_grade(raw_revision: object) -> RegistryAuthorityGrade | None:
    """Return the edition's authority grade, the floor when undeclared, ``None`` when unreadable."""
    table = _as_toml_table(raw_revision)
    if table is None:
        return None
    token = table.get(_AUTHORITY_GRADE_FIELD)
    if token is None:
        return UNDECLARED_REGISTRY_AUTHORITY_GRADE
    if not isinstance(token, str) or token not in RegistryAuthorityGrade:
        return None
    return RegistryAuthorityGrade(token)


def _materialise_revision(
    source_path: Path,
    raw_revisions: Mapping[str, object],
    named: Mapping[str, str],
    revision_id: str,
    resolved: dict[str, _MaterialisedRevision],
) -> _MaterialisedRevision:
    """Return one edition with its predecessor chain's casillas resolved into it."""
    cached = resolved.get(revision_id)
    if cached is not None:
        return cached
    table = _as_toml_table(raw_revisions[revision_id])
    if table is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
    predecessor_id = named.get(revision_id)
    result = _MaterialisedRevision(table=table, label_origins=None)
    if predecessor_id is not None:
        predecessor = _materialise_revision(source_path, raw_revisions, named, predecessor_id, resolved)
        rows, label_origins = _inherit_casillas(
            f"{source_path}: revision {revision_id!r} inheriting from {predecessor_id!r}",
            revision_id=revision_id,
            predecessor_id=predecessor_id,
            inherited=_raw_casilla_rows(source_path, predecessor_id, predecessor.table),
            inherited_label_origins=predecessor.label_origins,
            successor=table,
        )
        result = _MaterialisedRevision(table={**table, _INHERITED_SECTION: rows}, label_origins=label_origins)
    resolved[revision_id] = result
    return result


def _raw_casilla_rows(source_path: Path, revision_id: str, table: Mapping[str, object]) -> tuple[object, ...]:
    rows = as_toml_array(table.get(_INHERITED_SECTION, ()))
    if rows is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} casillas must be an array")
    return rows


def _inherit_casillas(
    context: str,
    *,
    revision_id: str,
    predecessor_id: str,
    inherited: tuple[object, ...],
    inherited_label_origins: _LabelOrigins | None,
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], _LabelOrigins]:
    """Merge the predecessor's materialised casillas with the successor's stated ones.

    Returns the merged rows and, aligned with them, each row's label origin.
    A kept inherited row takes the origin it already had in the predecessor,
    or the predecessor itself when the predecessor stated it, so the origin of
    a row carried down a chain is the edition that last stated it rather than
    the immediate predecessor, whose catalogue has no entry for it either.
    """
    if inherited_label_origins is not None and len(inherited_label_origins) != len(inherited):
        raise RegistryLoadError(
            f"{context}: the predecessor's label origins cover {len(inherited_label_origins)} of its "
            f"{len(inherited)} casillas",
        )
    stated = as_toml_array(successor.get(_INHERITED_SECTION, ()))
    if stated is None:
        raise RegistryLoadError(f"{context}: casillas must be an array")
    retired = _retired_lineages(successor, revision_id)
    superseders = _stated_rows_by_lineage(context, stated, retired)
    inherited_lineage_counts = Counter(lineage for row in inherited if (lineage := _row_lineage(row)) is not None)
    ambiguous = sorted(lineage for lineage in superseders if inherited_lineage_counts[lineage] > 1)
    if ambiguous:
        raise RegistryLoadError(
            f"{context}: the predecessor carries lineage {ambiguous!r} on more than one row, so a stated row "
            "carrying it cannot say which one it supersedes",
        )
    rows: list[object] = []
    label_origins: list[str | None] = []
    kept_lineage_by_id: dict[str, str | None] = {}
    superseded: set[str] = set()
    for index, row in enumerate(inherited):
        lineage = _row_lineage(row)
        if lineage is not None and lineage in retired:
            continue
        if lineage is not None and lineage in superseders:
            rows.append(superseders[lineage])
            label_origins.append(None)
            superseded.add(lineage)
            continue
        rows.append(row)
        carried_origin = None if inherited_label_origins is None else inherited_label_origins[index]
        label_origins.append(carried_origin if carried_origin is not None else predecessor_id)
        row_id = _row_id(row)
        if row_id is not None:
            kept_lineage_by_id[row_id] = lineage
    for row in stated:
        lineage = _row_lineage(row)
        row_id = _row_id(row)
        if row_id is not None and row_id in kept_lineage_by_id:
            raise RegistryLoadError(
                f"{context}: stated casilla {row_id!r} of lineage {_lineage_label(lineage)} collides with the "
                f"inherited casilla {row_id!r} of lineage {_lineage_label(kept_lineage_by_id[row_id])}; a stated "
                "row supersedes only the inherited row carrying its own lineage, so declare the repurpose by "
                "keeping the lineage, or retire the inherited lineage",
            )
        if lineage is None or lineage not in superseded:
            rows.append(row)
            label_origins.append(None)
    return tuple(rows), tuple(label_origins)


def _stated_rows_by_lineage(
    context: str,
    stated: tuple[object, ...],
    retired: frozenset[str],
) -> dict[str, object]:
    by_lineage: dict[str, object] = {}
    for row in stated:
        lineage = _row_lineage(row)
        if lineage is None:
            continue
        if lineage in retired:
            raise RegistryLoadError(
                f"{context}: states a casilla of lineage {lineage!r}, which the same edition retires",
            )
        if lineage in by_lineage:
            raise RegistryLoadError(
                f"{context}: states more than one casilla of lineage {lineage!r}, so neither can supersede "
                "the inherited row",
            )
        by_lineage[lineage] = row
    return by_lineage


def _retired_lineages(successor: Mapping[str, object], revision_id: str) -> frozenset[str]:
    """Return the lineages the successor withdraws through a ``retired`` evolution into itself."""
    evolutions = as_toml_array(successor.get(_RETIREMENT_SECTION, ())) or ()
    retired: set[str] = set()
    for raw_evolution in evolutions:
        evolution = _as_toml_table(raw_evolution)
        if evolution is None or evolution.get("to_revision") != revision_id:
            continue
        lineage = evolution.get("continuidad_id")
        if evolution.get("evolution_kind") == CasillaEvolutionKind.RETIRED and isinstance(lineage, str):
            retired.add(lineage)
    return frozenset(retired)


def _row_lineage(row: object) -> str | None:
    table = _as_toml_table(row)
    lineage = None if table is None else table.get("continuidad_id")
    return lineage if isinstance(lineage, str) else None


def _row_id(row: object) -> str | None:
    table = _as_toml_table(row)
    row_id = None if table is None else table.get("id")
    return row_id if isinstance(row_id, str) else None


def _lineage_label(lineage: str | None) -> str:
    return repr(lineage) if lineage is not None else "(none declared)"


def _apply_edition_reference_defaults(table: Mapping[str, object]) -> Mapping[str, object]:
    """Fill the edition's declared reference defaults into the casilla rows that state none.

    Two defaults, both declared once on the edition's manifest:

    - ``casilla_source_refs`` becomes the ``source_refs`` of every casilla row,
      and of every row's ``constraints`` table, that states no ``source_refs``;
    - ``orden_aplicabilidad``, the edition's approving ordenes, becomes the
      ``legal_refs`` of every casilla row and ``constraints`` table that states
      no ``legal_refs``.

    A stated value is kept whole, including a stated empty array, which typed
    construction then refuses. A default is never merged into a stated value.

    It runs on the materialised edition, so an inherited row is defaulted from
    the edition it now sits in: source references are declared per edition, and
    a row the predecessor did not ground itself must not carry the
    predecessor's grounding forward. This relies on inheritance reading each
    predecessor's rows before its own defaults are applied.

    Returns the identical table when it fills nothing, so an edition declaring
    no default reaches typed construction exactly as authored. A default that is
    absent, empty or not an array fills nothing and is left to typed
    construction, as is a casilla section or row that is not the shape it
    should be.
    """
    defaults: dict[str, tuple[object, ...]] = {}
    source_default = as_toml_array(table.get(_EDITION_SOURCE_DEFAULT_FIELD))
    if source_default:
        defaults[_ROW_SOURCE_FIELD] = source_default
    orden_default = as_toml_array(table.get(_EDITION_ORDEN_FIELD))
    if orden_default:
        defaults[_ROW_LEGAL_FIELD] = orden_default
    rows = as_toml_array(table.get(_INHERITED_SECTION, ()))
    if not defaults or not rows:
        return table
    defaulted = tuple(_default_row_references(row, defaults) for row in rows)
    if all(new is old for new, old in zip(defaulted, rows, strict=True)):
        return table
    return {**table, _INHERITED_SECTION: defaulted}


def _default_row_references(row: object, defaults: Mapping[str, tuple[object, ...]]) -> object:
    """Return ``row`` with every default it does not state filled in, or ``row`` itself when it states them all."""
    table = _as_toml_table(row)
    if table is None:
        return row
    filled: dict[str, object] = {name: value for name, value in defaults.items() if name not in table}
    constraints = _as_toml_table(table.get(_ROW_CONSTRAINTS_FIELD))
    if constraints is not None:
        missing = {name: value for name, value in defaults.items() if name not in constraints}
        if missing:
            filled[_ROW_CONSTRAINTS_FIELD] = {**constraints, **missing}
    if not filled:
        return row
    return {**table, **filled}


def _resolve_inherited_references(
    source_path: Path,
    *,
    revision_id: str,
    table: Mapping[str, object],
    label_origins: _LabelOrigins,
) -> Mapping[str, object]:
    """Point every inherited casilla's formula and binding references at this edition's own declarations.

    An inherited row arrives with the references its stating edition authored,
    which name that edition's formulas and bindings. Each reference is replaced
    by the declaration of this edition carrying the same lineage, as
    :func:`~cadrumo.domain.calculations.registry.identifier_lineage.identifier_lineage`
    defines it: the reference's lineage is taken against the stating edition,
    each declaration's against this one. A reference whose lineage no
    declaration of this edition carries is refused rather than kept, since the
    pointer it holds names another edition's declaration.

    Stated rows are returned untouched; their references are this edition's
    own, and reference validation checks them as authored. A field or row that
    is not the shape it should be is left for typed construction to refuse.

    Returns the identical table when no reference changes, which is always the
    case once identifiers stop embedding an edition key and every inherited
    reference resolves to itself.
    """
    context = f"{source_path}: revision {revision_id!r}"
    rows = _raw_casilla_rows(source_path, revision_id, table)
    if len(rows) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} of the edition's {len(rows)} casillas",
        )
    declarations = {
        section: _declarations_by_lineage(table, section, revision_id) for section in _REFERENCE_SECTIONS.values()
    }
    resolved = tuple(
        row
        if origin is None
        else _resolve_row_references(context, row, origin=origin, revision_id=revision_id, declarations=declarations)
        for row, origin in zip(rows, label_origins, strict=True)
    )
    if all(new is old for new, old in zip(resolved, rows, strict=True)):
        return table
    return {**table, _INHERITED_SECTION: resolved}


def _declarations_by_lineage(
    table: Mapping[str, object],
    section: str,
    revision_id: str,
) -> Mapping[str, tuple[str, ...]]:
    """Group the edition's declared identifiers of one section by lineage."""
    by_lineage: dict[str, dict[str, None]] = {}
    for raw in as_toml_array(table.get(section, ())) or ():
        declaration_id = _row_id(raw)
        if declaration_id is not None:
            by_lineage.setdefault(identifier_lineage(declaration_id, revision_id), {})[declaration_id] = None
    return {lineage: tuple(ids) for lineage, ids in by_lineage.items()}


def _resolve_row_references(
    context: str,
    row: object,
    *,
    origin: str,
    revision_id: str,
    declarations: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> object:
    """Return ``row`` with its references resolved, or ``row`` itself when each already names its target."""
    table = _as_toml_table(row)
    if table is None:
        return row
    casilla_id = _row_id(table)
    updates: dict[str, object] = {}
    for field, section in _REFERENCE_SECTIONS.items():
        value = table.get(field)

        def resolve(reference: str, *, field: str = field, section: str = section) -> str:
            return _resolve_reference(
                context,
                casilla_id=casilla_id,
                field=field,
                reference=reference,
                origin=origin,
                revision_id=revision_id,
                section=section,
                declarations=declarations[section],
            )

        if isinstance(value, str):
            resolved: object = resolve(value)
        elif (items := as_toml_array(value)) is not None:
            resolved = tuple(resolve(item) if isinstance(item, str) else item for item in items)
        else:
            continue
        if resolved != value:
            updates[field] = resolved
    if not updates:
        return row
    return {**table, **updates}


def _resolve_reference(
    context: str,
    *,
    casilla_id: str | None,
    field: str,
    reference: str,
    origin: str,
    revision_id: str,
    section: str,
    declarations: Mapping[str, tuple[str, ...]],
) -> str:
    lineage = identifier_lineage(reference, origin)
    candidates = declarations.get(lineage, ())
    if len(candidates) == 1:
        return candidates[0]
    found = (
        f"{len(candidates)} {section} declarations {list(candidates)!r}" if candidates else f"no {section} declaration"
    )
    raise RegistryLoadError(
        f"{context}: inherited casilla {casilla_id!r} {field} reference {reference!r}, stated in revision "
        f"{origin!r}, has lineage {lineage!r}, and revision {revision_id!r} carries {found} of that lineage; "
        "an inherited reference must resolve to exactly one of this edition's own declarations, so declare it "
        "here or state the row in this edition",
    )


def _enroll_inherited_label_fallbacks(
    context: str,
    *,
    modelo_id: str,
    payload: dict[str, object],
    label_origins: _LabelOrigins,
) -> dict[str, object]:
    """Give every inherited casilla the occurrence key of the edition that last stated it.

    Enrolment keys an inherited row to the edition it now sits in, which is the
    right identity, but the label catalogue is authored per edition and holds
    the row's text only under the key of the edition that stated it. That key
    joins the row's resolution chain directly after its own occurrence key and
    ahead of its continuity key: an entry the successor authors for the row
    still wins, the stated edition's exact text comes next, and the lineage-wide
    text stays the last tier. A row whose chain resolves nowhere still raises on
    lookup, exactly as before.

    An alias resolves through one key with no chain, so an inherited row that
    carries aliases is refused here instead of loading with alias labels that
    raise on first read.
    """
    casillas = as_toml_array(payload.get(_INHERITED_SECTION))
    if casillas is None or len(casillas) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} casillas but enrolment produced "
            f"{'no casilla array' if casillas is None else len(casillas)}",
        )
    enrolled: list[object] = []
    for casilla, origin in zip(casillas, label_origins, strict=True):
        table = None if origin is None else _as_toml_table(casilla)
        keys = None if table is None else table.get("localization_keys")
        casilla_id = None if table is None else table.get("id")
        # A row enrolment could not key is left for typed construction to refuse.
        if table is None or origin is None or not isinstance(casilla_id, str) or not isinstance(keys, tuple):
            enrolled.append(casilla)
            continue
        if table.get("aliases"):
            raise RegistryLoadError(
                f"{context}: inherited casilla {casilla_id!r} carries aliases, whose labels resolve only under "
                f"this edition's key and have no fallback to {origin!r}; state the row in this edition",
            )
        fallback = casilla_occurrence_locale_key(modelo_id, origin, casilla_id, ModeloLocalizationFieldKind.LABEL)
        enrolled.append({**table, "localization_keys": (*keys[:1], fallback, *keys[1:])})
    return {**payload, _INHERITED_SECTION: tuple(enrolled)}


def _raise_on_ambiguous_revision_identity(
    source_path: Path,
    *,
    modelo_id: str,
    revision_id: RevisionId,
    revision: ModeloRevision,
) -> None:
    prefix = f"{source_path}: modelo {modelo_id} revision {revision_id}"
    failures = revision_reference_identity_failures(prefix, revision)
    if failures:
        raise RegistryValidationError(
            "registry revision identity is ambiguous:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _refuse_authored_export_refs(source_path: Path, revision_id: str, payload: Mapping[str, object]) -> None:
    """Refuse a casilla row that declares ``export_refs``, which the loader derives from the layouts."""
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    authored = sorted(
        str(table.get("id"))
        for row in rows
        if (table := _as_toml_table(row)) is not None and _EXPORT_REFS_FIELD in table
    )
    if authored:
        raise RegistryLoadError(
            f"{source_path}: revision {revision_id!r} casillas {authored!r} declare export_refs; a casilla's "
            "export references are derived from the export fields that resolve to it, so remove the key",
        )


def _with_derived_export_refs(
    source_path: Path,
    revision: ModeloRevision,
    payload: Mapping[str, object],
) -> ModeloRevision:
    """Return ``revision`` with every casilla's ``export_refs`` derived from the edition's own layouts.

    The derivation runs on the materialised edition, so an inherited row takes
    the references of the layout it now sits beside and never its origin's.
    Each re-derived row is constructed again from its enrolled payload, so the
    casilla's own coherence rules see the derived value exactly as they would
    an authored one.
    """
    try:
        derived = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    if not derived:
        return revision
    declared = {casilla.id for casilla in revision.casillas}
    undeclared = sorted(casilla_id for casilla_id in derived if casilla_id not in declared)
    if undeclared:
        raise RegistryLoadError(
            f"{source_path}: invalid revision {revision.id!r}: export fields resolve to casillas {undeclared!r}, "
            "which the edition does not declare",
        )
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    casillas = []
    for casilla, row in zip(revision.casillas, rows, strict=True):
        refs = derived.get(casilla.id)
        table = _as_toml_table(row)
        if refs is None or table is None:
            casillas.append(casilla)
            continue
        try:
            casillas.append(CasillaDefinition.model_validate({**table, _EXPORT_REFS_FIELD: refs}))
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    return revision.model_copy(update={_INHERITED_SECTION: tuple(casillas)})


def _passthrough_toml_row(raw: object) -> dict[str, object]:
    """Carry a non-table TOML row through unchanged, so validation still sees it.

    Enrolment adds locale identities; it is not a validator. A row that is not a
    table gets no derived key -- there is no id to derive one from -- but it must
    still reach ``model_validate``, which is what turns a malformed fragment into
    an attributable error. Dropping it here would make it vanish silently
    instead.
    """
    # CAST-RATIONALE-TOML-ROW: raw TOML value, shape confirmed by the isinstance
    # guard in the same expression. One site rather than the three near-identical
    # copies this replaces, so the escape hatch is declared once.
    # nosemgrep: no-cast-in-domain-application
    return dict(cast(Mapping[str, object], raw)) if isinstance(raw, Mapping) else {"value": raw}


def _compile_export_semantic_field(source_path: Path, raw_field: object) -> dict[str, object]:
    """Construct closed export selector enums at the TOML compiler boundary.

    Strict registry models deliberately accept only enum members.  This is the
    one boundary where committed TOML's scalar token becomes that member; no
    model validator, renderer, or application call site may repeat it.
    """
    field = _as_toml_table(raw_field)
    if field is None:
        return _passthrough_toml_row(raw_field)
    if "header_key" in field:
        raise RegistryLoadError(
            f"{source_path}: legacy export field header_key is not accepted; use producer_key with a canonical "
            "FilingProducerKey identity",
        )
    payload = dict(field)
    for name, enum_type in (
        ("producer_key", FilingProducerKey),
        ("draft_attribute", ExportDraftAttribute),
        ("computed_key", ExportComputedKey),
    ):
        raw_value = payload.get(name)
        if raw_value is None or isinstance(raw_value, enum_type):
            continue
        if not isinstance(raw_value, str):
            raise RegistryLoadError(
                f"{source_path}: export field {name} must be a canonical string token, got "
                f"{type(raw_value).__name__!r}",
            )
        try:
            payload[name] = enum_type(raw_value)
        except ValueError as exc:
            raise RegistryLoadError(
                f"{source_path}: export field {name} {raw_value!r} is not a canonical {enum_type.__name__}",
            ) from exc
    raw_projection_ref = payload.get("projection_ref")
    if raw_projection_ref is not None:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(raw_projection_ref)
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(
                f"{source_path}: export field projection_ref is not a canonical FilingProjectionRef: {exc}",
            ) from exc
    return payload


def _compile_projection_endpoint_declaration(source_path: Path, raw_declaration: object) -> dict[str, object]:
    """Hydrate one revision-owned projection declaration at the TOML boundary."""
    declaration = _as_toml_table(raw_declaration)
    if declaration is None:
        return _passthrough_toml_row(raw_declaration)
    payload = dict(declaration)
    if "projection_ref" in payload:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(payload["projection_ref"])
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(f"{source_path}: {exc}") from exc
    return payload


def _compile_revision_projection_record(source_path: Path, raw_record: object) -> dict[str, object]:
    record = _as_toml_table(raw_record)
    if record is None:
        return _passthrough_toml_row(raw_record)
    compiled = dict(record)
    fields = as_toml_array(record.get("fields"))
    if fields is not None:
        compiled["fields"] = tuple(_compile_export_semantic_field(source_path, raw_field) for raw_field in fields)
    return compiled


def _compile_revision_projection_layout(source_path: Path, raw_layout: object) -> dict[str, object]:
    layout = _as_toml_table(raw_layout)
    if layout is None:
        return _passthrough_toml_row(raw_layout)
    compiled = dict(layout)
    records = as_toml_array(layout.get("records"))
    if records is not None:
        compiled["records"] = tuple(
            _compile_revision_projection_record(source_path, raw_record) for raw_record in records
        )
    return compiled


def _compile_revision_projection_semantics(source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Compile revision-owned typed tokens before schema construction."""
    compiled = dict(payload)
    declarations = as_toml_array(payload.get("projection_endpoints"))
    if declarations is not None:
        compiled["projection_endpoints"] = tuple(
            _compile_projection_endpoint_declaration(source_path, raw_declaration) for raw_declaration in declarations
        )
    layouts = as_toml_array(payload.get("export_layouts"))
    if layouts is not None:
        compiled["export_layouts"] = tuple(
            _compile_revision_projection_layout(source_path, raw_layout) for raw_layout in layouts
        )
    return compiled


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: _RegistryPathFingerprints,
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    return _build_modelo_definition_from_data(resolved, merged)


def _load_modelo_manifest(resolved: Path) -> dict[str, object]:
    """Load the directory-mode manifest.toml and reject inlined [revisions]."""
    manifest_path = resolved / "manifest.toml"
    manifest_data = freeze_toml(read_toml(manifest_path, error_factory=RegistryLoadError))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            f"revision data lives in revisions/<id>.toml",
        )
    return manifest_data


def _load_modelo_revisions(resolved: Path) -> dict[str, object]:
    """Read every ``revisions/*.toml`` and merge into one ``{revision_id: raw}`` map.

    A missing ``revisions/`` directory returns an empty dict; the
    caller raises if no revisions land. Each per-file ``[revisions.X]``
    payload is added to the merged map under its id, rejecting
    inline ``[modelo]`` declarations, local catalogues, and any
    duplicate ``revision_id`` across files.
    """
    revisions_dir = resolved / "revisions"
    if not revisions_dir.is_dir():
        return {}
    merged_revisions: dict[str, object] = {}
    for path in scan_directory(revisions_dir, pattern="*.toml"):
        _merge_revision_file(path, merged_revisions)
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.DIRECTORIES):
        _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_file(path: Path, merged_revisions: dict[str, object]) -> None:
    """Validate one revisions/*.toml file and append its revisions into ``merged_revisions``."""
    rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    _reject_local_catalogues(path, rev_data)
    if "modelo" in rev_data:
        raise RegistryLoadError(f"{path}: revision file must not declare [modelo]; that lives in manifest.toml")
    file_revisions = _as_toml_table(rev_data.get("revisions"))
    if not file_revisions:
        raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
    for revision_id, raw_revision in file_revisions.items():
        if revision_id in merged_revisions:
            raise RegistryLoadError(
                f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file",
            )
        merged_revisions[revision_id] = raw_revision


def _merge_revision_directory(path: Path, merged_revisions: dict[str, object]) -> None:
    """Merge a ``revisions/{id}/`` fragment tree into ``merged_revisions``."""
    revision_id = path.name
    if revision_id in merged_revisions:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file")
    revision_manifest = path / "revision.toml"
    if not revision_manifest.is_file():
        raise RegistryLoadError(f"{path}: revision fragment directory must contain revision.toml")
    section_fragments = _revision_section_fragment_paths(_revision_section_directories(path))
    merged_revision: dict[str, object] = {}
    _merge_revision_manifest(revision_manifest, revision_id, merged_revision)
    for fragment_path in section_fragments:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _revision_section_directories(path: Path) -> tuple[Path, ...]:
    # require_root: the caller has already resolved this revision fragment
    # directory and read its revision.toml, so an unreadable path here is a
    # broken tree, not an empty revision. Silently returning no sections would
    # compile a revision with none of its casillas.
    return tuple(
        entry
        for entry in scan_directory(path, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        if entry.name != "locales"
    )


def _revision_section_fragment_paths(section_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    """Collect every section directory's fragments, refusing an empty section.

    One listing per section directory answers both questions the loader asks
    of it -- "is this section populated" and "which files does it hold" -- so
    the two cannot disagree. They were previously two independent one-level
    walks kept textually identical by hand, on the reasoning that a guard
    seeing more than the collector could call a section "populated" while the
    collector read nothing from it. Deriving both from a single listing makes
    that agreement structural rather than editorial, and halves the walks.

    The listing is narrowed to files, which is what the emptiness question
    always meant: a directory named ``*.toml`` is not a fragment. Nothing of
    the sort can exist anyway -- :func:`_validate_section_fragment_names`
    (``loader_cache.py``, run for every section directory before a fragment
    tree is merged) refuses ANY subdirectory nested inside a section
    directory outright -- so the narrowing restates an upstream categorical
    block rather than introducing a new rule.
    """
    fragments: list[Path] = []
    for section_dir in section_dirs:
        section_fragments = scan_directory(section_dir, pattern="*.toml", select=DirectoryEntryKind.FILES)
        if not section_fragments:
            raise RegistryLoadError(f"{section_dir}: revision section fragment directory contains no TOML fragments")
        fragments.extend(section_fragments)
    return tuple(sorted(fragments))


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
    content_digest: str,
) -> RegistryCatalogues:
    del byte_count, modified_ns, content_digest
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    legal = _validate_catalogue_section(
        source_path,
        raw=data.get("legal"),
        kind="legal reference",
        model=LegalReference,
    )
    sources = _validate_catalogue_section(
        source_path,
        raw=data.get("sources") or data.get("source"),
        kind="source reference",
        model=SourceReference,
    )
    parameters = _validate_catalogue_section(
        source_path,
        raw=data.get("parameters"),
        kind="legal parameter",
        model=LegalParameter,
    )
    supported_filing_years = None
    raw_supported_filing_years = data.get("supported_filing_years")
    if raw_supported_filing_years is not None:
        try:
            supported_filing_years = SupportedFilingYearsCatalogue.model_validate(raw_supported_filing_years)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid supported_filing_years catalogue: {exc}") from exc
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        parameters=parameters,
        supported_filing_years=supported_filing_years,
    )


def _validate_catalogue_section[T: BaseModel](
    source_path: Path,
    *,
    raw: object,
    kind: str,
    model: type[T],
) -> dict[str, T]:
    """Validate one ``{id: payload}`` section of a catalogue TOML into typed records.

    Returns an empty dict when ``raw`` is not a dict (the section is
    absent or malformed at the top level — the absent case is
    legitimate for catalogues that don't declare every section).
    Each ``(id, payload)`` pair is fed through ``model.model_validate``
    with ``id`` injected; type-shape errors raise the typed
    ``RegistryLoadError`` envelope so the catalogue loader's failure
    mode stays uniform across the three sections (legal, sources,
    parameters).
    """
    table = _as_toml_table(raw)
    if table is None:
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in table.items():
        payload_table = _as_toml_table(payload)
        if payload_table is None:
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload_table})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def _validate_legal_parameter_refs(
    scope: Path,
    *,
    parameters: Mapping[str, LegalParameter],
    legal: Mapping[str, LegalReference],
) -> None:
    failures = [
        f"legal parameter {parameter_id!r} references unknown legal id {legal_ref!r}"
        for parameter_id, parameter in sorted(parameters.items())
        for legal_ref in parameter.legal_refs
        if legal_ref not in legal
    ]
    if failures:
        raise RegistryLoadError(
            f"{scope}: unresolved legal parameter references:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _live_cached_fingerprints(
    resolved: Path,
    *,
    now: float,
    ttl: float,
    directory_fingerprints: _RegistryPathFingerprints | None,
) -> _RegistryPathFingerprints | None:
    """Return the cached fingerprints when the entry is still live, else ``None``.

    ``directory_fingerprints`` is ``None`` for the pre-walk bundled
    short-circuit, where the entry's own age is the only question. When it is
    supplied, a live entry must ALSO agree with the freshly walked directory
    fingerprints; a disagreement means the tree's layout changed under the entry,
    so it is evicted rather than served. An entry that has merely aged out is
    left in place for the caller to overwrite.
    """
    entry = _registry_fingerprint_cache.get(resolved)
    if entry is None:
        return None
    cached_time, cached_directories, cached_value = entry
    if now - cached_time >= ttl:
        return None
    if directory_fingerprints is None or cached_directories == directory_fingerprints:
        return cached_value
    _registry_fingerprint_cache.pop(resolved, None)
    return None


def _registry_source_fingerprints(resolved: Path) -> tuple[_RegistryPathFingerprint, ...]:
    """Fingerprint every catalogue TOML the loader will subsequently re-open.

    Ordering is part of the cache key, so the sequence here (legal, single-file
    modelos, directory-mode modelos, user-profile schema) is load-bearing and
    must not be reordered.
    """
    fingerprints: list[_RegistryPathFingerprint] = []
    for path in scan_directory(resolved / "legal", pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    modelos_dir = resolved / "modelos"
    for path in scan_directory(modelos_dir, pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    for entry in scan_directory(modelos_dir):
        fingerprints.extend(_modelo_directory_fingerprints(entry))
    schema_path = resolved / "user_profile" / "schema.toml"
    if schema_path.is_file():
        fingerprints.append(_toml_fingerprint(schema_path))
    return tuple(fingerprints)


def _store_registry_fingerprints(
    resolved: Path,
    *,
    directory_fingerprints: _RegistryPathFingerprints,
    fingerprints: _RegistryPathFingerprints,
    walk_started: float,
    bundled: bool,
) -> None:
    """Record the freshly walked fingerprints, stamped for their TTL window.

    The bundled tree is read-only package data, so its TTL bounds how often we
    redo the expensive walk rather than how stale the observation may be: stamp
    it at walk COMPLETION so the full window is available to callers. Stamping at
    walk start instead charges the walk's own cost (~1s idle, several times that
    on a loaded machine) against the window, which on a busy host can consume it
    entirely and defeat the cache exactly when it is worth most. A mutable
    authoring tree keeps the conservative start stamp: there the TTL is a
    staleness bound on a tree that can change under us.
    """
    import time

    stamped = time.time() if bundled else walk_started
    _registry_fingerprint_cache[resolved] = (stamped, directory_fingerprints, fingerprints)


def _collect_registry_directory_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    if not resolved.is_dir():
        return ()

    def _raise_walk_error(exc: OSError) -> None:
        raise RegistryLoadError(
            f"{resolved}: registry directory could not be walked during cache fingerprinting; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "directory_walk"},
            ),
        ) from exc

    fingerprints: list[_RegistryPathFingerprint] = []
    for dirpath, dirnames, _filenames in os.walk(resolved, onerror=_raise_walk_error):
        dirnames.sort()
        fingerprints.append(_directory_fingerprint(Path(dirpath)))
    return tuple(fingerprints)


def _collect_modelo_directory_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    manifest_path = resolved / "manifest.toml"
    fingerprints: list[_RegistryPathFingerprint] = list(_collect_registry_directory_fingerprints(resolved))
    fingerprints.append(_toml_fingerprint(manifest_path))
    for path in scan_directory(resolved / "locales", pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    for path in scan_directory(resolved / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(path))
    return tuple(fingerprints)


def _modelo_directory_fingerprints(entry: Path) -> _RegistryPathFingerprints:
    """Return fingerprints for one directory-mode modelo entry, or ``()`` if not in that layout."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[_RegistryPathFingerprint] = [_toml_fingerprint(entry / "manifest.toml")]
    for path in scan_directory(entry / "locales", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(path))
    for rev_path in scan_directory(entry / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


def _validate_legal_directory(legal_dir: Path) -> None:
    """Require the shared legal catalogue to remain one flat TOML directory."""
    if not legal_dir.is_dir():
        return
    for entry in scan_directory(legal_dir):
        if entry.is_dir():
            raise RegistryLoadError(f"{entry}: unrecognized legal directory; legal catalogues must be flat")
        if not entry.is_file() or entry.suffix != ".toml":
            raise RegistryLoadError(
                f"{entry}: unrecognized legal catalogue file; legal catalogues must use the '.toml' suffix",
            )


def _refresh_modelo_directory_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_modelo_directory_fingerprints(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: modelo directory changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={
                    "path": str(resolved),
                    "registry_tree_quiescent": False,
                    "operation": "modelo_directory_refresh",
                },
            ),
        ) from refresh_error


def _refresh_registry_tree_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_registry_tree_fingerprints_uncached(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: registry tree changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "registry_tree_refresh"},
            ),
        ) from refresh_error


def _directory_fingerprint(path: Path) -> _RegistryPathFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry directory could not be fingerprinted; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(path), "registry_tree_quiescent": False, "operation": "directory_stat"},
            ),
        ) from exc
    # A directory has no hashable content of its own; layout changes are what
    # its stat observes, and member-file content is covered by the per-file
    # digests, so the content slot stays empty.
    return str(path), stat.st_size, stat.st_mtime_ns, ""


def _toml_fingerprint(path: Path) -> _RegistryPathFingerprint:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one TOML file.

    Delegates to :func:`~cadrumo.domain.calculations.registry.loader_cache.toml_file_fingerprint`,
    the shared primitive that makes mutable-tree fingerprints content-sensitive
    (a same-size, same-mtime rewrite still re-keys every cache above the
    loader) while the read-only bundled tree keeps the cheap stat-only form.
    """
    return toml_file_fingerprint(path)


_TREE_FINGERPRINT_COLLECTORS = bind_tree_fingerprint_collectors(
    is_bundled_root=is_bundled_registry_root,
    bundled_ttl=BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    live_cached=_live_cached_fingerprints,
    collect_directory=_collect_registry_directory_fingerprints,
    collect_sources=_registry_source_fingerprints,
    store=_store_registry_fingerprints,
)
_collect_registry_tree_fingerprints = _TREE_FINGERPRINT_COLLECTORS[0]
_collect_registry_tree_fingerprints_uncached = _TREE_FINGERPRINT_COLLECTORS[1]

#: This module's docstring already states the boundary this enforces: a
#: caller OUTSIDE the package cannot bind to a compilation step or cache this
#: module does not promise. Within the package, :mod:`loader` is the one
#: sanctioned consumer of the compilation internals below, so this lists every
#: name it (and the module's own test suite) actually reaches across the
#: module boundary -- never a wildcard, and never widened to symbols nothing
#: outside this file uses.
__all__ = [
    "_REVISION_SECTION_FIELDS",
    "_RegistryPathFingerprints",
    "_collect_modelo_directory_fingerprints",
    "_collect_registry_directory_fingerprints",
    "_collect_registry_tree_fingerprints",
    "_collect_registry_tree_fingerprints_uncached",
    "_compile_export_semantic_field",
    "_compile_projection_endpoint_declaration",
    "_load_catalogue_file_cached",
    "_load_modelo_directory_cached",
    "_refresh_modelo_directory_fingerprints_after_load_error",
    "_refresh_registry_tree_fingerprints_after_load_error",
    "_revision_section_fragment_paths",
    "_toml_fingerprint",
    "_validate_legal_directory",
    "_validate_legal_parameter_refs",
    "load_modelo_file",
]

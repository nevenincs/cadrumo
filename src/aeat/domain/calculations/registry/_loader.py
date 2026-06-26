"""Read-only TOML loader for AEAT registry definitions.

Compiles TOML authoring fragments into strict runtime objects. Each
:class:`ModeloDefinition` is assembled from one TOML file or a directory
manifest; each :class:`ModeloRevision` is compiled from a single revision
file or a set of append fragments merged in deterministic order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast, get_origin

from pydantic import BaseModel, Field, ValidationError

from ....core import freeze_toml, read_toml
from ._errors import RegistryLoadError, RegistryValidationError
from ._ids import CasillaId, validated_casilla_id
from ._schema import (
    LegalParameter,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
)
from ._validate_revision_identity import revision_reference_identity_failures

_REVISION_EXPORT_LAYOUTS = "export_layouts"
_REVISION_CONSTRUCTS = "constructs"
_REVISION_COMPLETENESS_MANIFEST = "completeness_manifest"
_REVISION_SPECIAL_MERGE_FIELDS = frozenset({_REVISION_EXPORT_LAYOUTS, _REVISION_CONSTRUCTS})
_REVISION_APPEND_ARRAYS: frozenset[str] = frozenset(
    field_name
    for field_name, field in ModeloRevision.model_fields.items()
    if field.default == ()
    and get_origin(field.annotation) is tuple
    and field_name not in _REVISION_SPECIAL_MERGE_FIELDS
)
_COMPLETENESS_MANIFEST_APPEND_ARRAYS: frozenset[str] = frozenset({"casillas"})
_CONSTRUCT_APPEND_ARRAYS: frozenset[str] = frozenset(
    {
        "casilla_ids",
        "formulas",
        "parameters",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
        "dependency_classifications",
    },
)
ModeloSourceLayout = Literal["single_file", "directory"]
ModeloRevisionSourceLayout = Literal["revision_file", "fragment_directory"]
_REGISTRY_TREE_CACHE_SCHEMA_VERSION = "binding-selector-typed-enum-v3"


@dataclass(frozen=True, slots=True)
class ModeloRevisionSource:
    """On-disk source for one modelo revision before schema validation."""

    revision_id: str
    layout: ModeloRevisionSourceLayout
    path: Path
    fragment_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ModeloSource:
    """On-disk source for one modelo before schema validation."""

    modelo_id: str
    layout: ModeloSourceLayout
    path: Path
    manifest_path: Path
    revision_sources: tuple[ModeloRevisionSource, ...] = ()


def _as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``.

    ``tomllib`` and :func:`freeze_toml` always emit ``str`` keys, so a
    parsed-TOML ``dict`` is genuinely ``dict[str, object]``. The runtime
    ``isinstance`` check loses the key type because TOML payloads flow
    through ``object``; the annotation below re-attaches the known ``str``
    key type at this single TOML deserialization boundary.
    """
    if isinstance(value, dict):
        # CAST-RATIONALE-TOML-STR-KEY-ERASURE: tomllib/freeze_toml always
        # produces str-keyed dicts; isinstance loses the key type annotation.
        return cast("dict[str, object]", value)
    return None


def _toml_table_id(value: object) -> str | None:
    """Return the string ``id`` of a TOML table value, or ``None``."""
    table = _as_toml_table(value)
    if table is None:
        return None
    table_id = table.get("id")
    return table_id if isinstance(table_id, str) else None


def _reject_local_catalogues(path: Path, data: Mapping[str, object]) -> None:
    forbidden = {"source", "sources", "legal", "legal_refs_catalogue"}
    present = sorted(forbidden.intersection(data))
    if present:
        raise RegistryLoadError(f"{path}: modelo files must not define local legal/source catalogues: {present!r}")


def load_modelo_file(path: Path) -> ModeloDefinition:
    """Load one modelo TOML file into strict schema objects.

    Returns:
        The compiled :class:`ModeloDefinition` from the TOML file.
    """
    resolved = path.resolve()
    stat = resolved.stat()
    return _load_modelo_file_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _load_modelo_file_cached(path: str, byte_count: int, modified_ns: int) -> ModeloDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    return _build_modelo_definition_from_data(source_path, data)


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, object]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = data["modelo"]
    if not isinstance(modelo_table, dict):
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
    raw_revisions = data.get("revisions")
    if not isinstance(raw_revisions, dict) or not raw_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        if not isinstance(revision_id, str):
            raise RegistryLoadError(f"{source_path}: revision key must be a string")
        if not isinstance(raw_revision, dict):
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        payload = {"id": revision_id, **raw_revision}
        try:
            revision = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
        _raise_on_ambiguous_revision_identity(
            source_path,
            modelo_id=modelo_id_for_context,
            revision_id=revision_id,
            revision=revision,
        )
        revisions[revision_id] = revision
    try:
        return ModeloDefinition.model_validate({**modelo_table, "revisions": revisions})
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def _raise_on_ambiguous_revision_identity(
    source_path: Path,
    *,
    modelo_id: str,
    revision_id: str,
    revision: ModeloRevision,
) -> None:
    prefix = f"{source_path}: modelo {modelo_id} revision {revision_id}"
    failures = revision_reference_identity_failures(prefix, revision)
    if failures:
        raise RegistryValidationError(
            "registry revision identity is ambiguous:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from a directory layout.

    The directory must contain ``manifest.toml`` carrying the ``[modelo]``
    metadata table. Per-revision data lives in ``revisions/{id}.toml``
    files, or in ``revisions/{id}/`` fragment directories. Revision
    files declare one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    Fragment directories declare exactly the directory revision id
    across one or more TOML files using the same table shape. All
    revision sources are merged into the single in-memory
    :class:`ModeloDefinition` that single-file mode produces.

    Public API stays identical to ``load_modelo_file``: callers receive
    the same :class:`ModeloDefinition` regardless of on-disk layout.
    """
    resolved = directory.resolve()
    if not resolved.is_dir():
        raise RegistryLoadError(f"{resolved}: modelo directory does not exist")
    manifest_path = resolved / "manifest.toml"
    if not manifest_path.is_file():
        raise RegistryLoadError(f"{resolved}: missing manifest.toml")

    fingerprints: list[tuple[str, int, int]] = [_toml_fingerprint(manifest_path)]
    locales_dir = resolved / "locales"
    if locales_dir.is_dir():
        for path in sorted(locales_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    revisions_dir = resolved / "revisions"
    if revisions_dir.is_dir():
        for path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    return _load_modelo_directory_cached(str(resolved), tuple(fingerprints))


def load_modelo_path(path: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from either supported on-disk layout."""
    resolved = path.resolve()
    if resolved.is_file():
        return load_modelo_file(resolved)
    if resolved.is_dir():
        return load_modelo_directory(resolved)
    raise RegistryLoadError(f"{resolved}: modelo source does not exist")


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Load a modelo from a discovered source descriptor.

    Returns:
        The compiled :class:`ModeloDefinition` from the source.
    """
    if source.layout == "single_file":
        return load_modelo_file(source.path)
    return load_modelo_directory(source.path)


class RegistryLocaleTranslation(BaseModel):
    labels: dict[str, str] = Field(default_factory=dict)
    help: dict[str, str] = Field(default_factory=dict)


def _load_locale_translation(path: Path) -> RegistryLocaleTranslation:
    try:
        raw_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
        return RegistryLocaleTranslation.model_validate(raw_data)
    except Exception as exc:
        raise RegistryValidationError(f"Invalid locales file {path}: {exc}") from exc


def _merge_locale_translation(
    *,
    language: str,
    target: RegistryLocaleTranslation,
    source: RegistryLocaleTranslation,
    path: Path,
) -> RegistryLocaleTranslation:
    labels = dict(target.labels)
    help_text = dict(target.help)
    duplicate_labels = sorted(set(labels).intersection(source.labels))
    duplicate_help = sorted(set(help_text).intersection(source.help))
    if duplicate_labels or duplicate_help:
        details: list[str] = []
        if duplicate_labels:
            details.append(f"labels={duplicate_labels!r}")
        if duplicate_help:
            details.append(f"help={duplicate_help!r}")
        raise RegistryValidationError(
            f"Duplicate {language!r} locale translation keys in {path}: {', '.join(details)}",
        )
    labels.update(source.labels)
    help_text.update(source.help)
    return RegistryLocaleTranslation(labels=labels, help=help_text)


def _load_locale_translation_group(language: str, paths: Iterable[Path]) -> RegistryLocaleTranslation:
    merged = RegistryLocaleTranslation()
    for path in sorted(paths):
        merged = _merge_locale_translation(
            language=language,
            target=merged,
            source=_load_locale_translation(path),
            path=path,
        )
    return merged


def _load_locale_translations(locales_dir: Path) -> dict[str, RegistryLocaleTranslation]:
    translations: dict[str, RegistryLocaleTranslation] = {}
    if not locales_dir.is_dir():
        return translations
    for path in sorted(locales_dir.glob("*.toml")):
        translations[path.stem] = _load_locale_translation_group(path.stem, (path,))
    for language_dir in sorted(path for path in locales_dir.iterdir() if path.is_dir()):
        paths = tuple(sorted(language_dir.glob("*.toml")))
        if not paths:
            continue
        if language_dir.name in translations:
            raise RegistryValidationError(
                f"Locale {language_dir.name!r} is declared both as a file and a fragment directory in {locales_dir}",
            )
        translations[language_dir.name] = _load_locale_translation_group(language_dir.name, paths)
    return translations


def _load_modelo_translations(modelo_dir: Path) -> dict[str, RegistryLocaleTranslation]:
    return _load_locale_translations(modelo_dir / "locales")


def _load_revision_translations(
    modelo_dir: Path,
) -> dict[str, dict[str, RegistryLocaleTranslation]]:
    translations: dict[str, dict[str, RegistryLocaleTranslation]] = {}
    revisions_dir = modelo_dir / "revisions"
    if not revisions_dir.is_dir():
        return translations
    for path in sorted(revisions_dir.iterdir()):
        if not path.is_dir():
            continue
        rev_locales_dir = path / "locales"
        locale_map = _load_locale_translations(rev_locales_dir)
        if locale_map:
            translations[path.name] = locale_map
    return translations


def _collect_valid_locale_ids(
    merged_revisions: dict[str, object],
) -> tuple[dict[str, set[CasillaId]], set[str]]:
    valid_casilla_ids: dict[str, set[CasillaId]] = {}
    valid_continuidad_ids: set[str] = set()
    for revision_id, raw_rev in merged_revisions.items():
        raw_rev_table = _as_toml_table(raw_rev)
        if raw_rev_table is None:
            continue
        casillas_list = raw_rev_table.get("casillas", ())
        if not isinstance(casillas_list, (list, tuple)):
            continue
        rev_casilla_ids: set[CasillaId] = set()
        for casilla in casillas_list:
            casilla_table = _as_toml_table(casilla)
            if casilla_table is None:
                continue
            c_id = casilla_table.get("id")
            if isinstance(c_id, str):
                try:
                    rev_casilla_ids.add(validated_casilla_id(c_id, surface=f"revision {revision_id!r} casilla id"))
                except ValueError as exc:
                    raise RegistryValidationError(
                        f"Invalid casilla id {c_id!r} in revision {revision_id!r}: expected canonical casilla.id",
                    ) from exc
            cont_id = casilla_table.get("continuidad_id")
            if isinstance(cont_id, str):
                valid_continuidad_ids.add(cont_id)
        valid_casilla_ids[revision_id] = rev_casilla_ids
    return valid_casilla_ids, valid_continuidad_ids


def _validate_translation_keys(
    trans: RegistryLocaleTranslation,
    valid_ids: set[str] | set[CasillaId],
    locale: str,
    *,
    context: str,
    reason: str,
) -> None:
    for field_name, mapping in (("labels", trans.labels), ("help", trans.help)):
        for key in mapping:
            if key not in valid_ids:
                raise RegistryValidationError(
                    f"Invalid translation key {key!r} in {field_name} for locale {locale!r}{context}: {reason}",
                )


def _check_locale_referential_integrity(
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
    valid_casilla_ids: dict[str, set[CasillaId]],
    valid_continuidad_ids: set[str],
) -> None:
    for locale, trans in modelo_translations.items():
        _validate_translation_keys(
            trans,
            valid_continuidad_ids,
            locale,
            context="",
            reason="no continuity chain found with this continuity id",
        )
    for revision_id, locale_map in revision_translations.items():
        rev_ids = valid_casilla_ids.get(revision_id, set())
        for locale, trans in locale_map.items():
            _validate_translation_keys(
                trans,
                rev_ids,
                locale,
                context=f" under revision {revision_id!r}",
                reason="no casilla found with this id",
            )


def _localize_casilla(
    casilla: object,
    revision_id: str,
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
) -> object:
    casilla_table = _as_toml_table(casilla)
    if casilla_table is None:
        return casilla

    casilla_id = casilla_table.get("id")
    continuidad_id = casilla_table.get("continuidad_id")

    localized_labels: dict[str, str] = {}
    localized_help: dict[str, str] = {}

    # Concept continuity (modelo-wide) translations
    if isinstance(continuidad_id, str):
        for locale, trans in modelo_translations.items():
            if continuidad_id in trans.labels:
                localized_labels[locale] = trans.labels[continuidad_id]
            if continuidad_id in trans.help:
                localized_help[locale] = trans.help[continuidad_id]

    # Revision-local override translations
    if isinstance(casilla_id, str):
        for locale, trans in revision_translations.get(revision_id, {}).items():
            if casilla_id in trans.labels:
                localized_labels[locale] = trans.labels[casilla_id]
            if casilla_id in trans.help:
                localized_help[locale] = trans.help[casilla_id]

    new_casilla = dict(casilla_table)
    new_casilla["localized_labels"] = localized_labels
    new_casilla["localized_help"] = localized_help
    return new_casilla


def _inject_localized_translations(
    merged_revisions: dict[str, object],
    modelo_translations: dict[str, RegistryLocaleTranslation],
    revision_translations: dict[str, dict[str, RegistryLocaleTranslation]],
) -> None:
    for revision_id, raw_rev in merged_revisions.items():
        raw_rev_table = _as_toml_table(raw_rev)
        if raw_rev_table is None:
            continue
        casillas_list = raw_rev_table.get("casillas", ())
        if not isinstance(casillas_list, (list, tuple)):
            continue
        raw_rev_table["casillas"] = tuple(
            _localize_casilla(casilla, revision_id, modelo_translations, revision_translations)
            for casilla in casillas_list
        )


def _apply_locales(modelo_dir: Path, merged_revisions: dict[str, object]) -> None:
    modelo_translations = _load_modelo_translations(modelo_dir)
    revision_translations = _load_revision_translations(modelo_dir)
    valid_casilla_ids, valid_continuidad_ids = _collect_valid_locale_ids(merged_revisions)
    _check_locale_referential_integrity(
        modelo_translations,
        revision_translations,
        valid_casilla_ids,
        valid_continuidad_ids,
    )
    _inject_localized_translations(merged_revisions, modelo_translations, revision_translations)


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    _apply_locales(resolved, merged_revisions)
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
    for path in sorted(revisions_dir.glob("*.toml")):
        _merge_revision_file(path, merged_revisions)
    for path in sorted(revisions_dir.iterdir()):
        if path.is_dir():
            _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_file(path: Path, merged_revisions: dict[str, object]) -> None:
    """Validate one revisions/*.toml file and append its revisions into ``merged_revisions``."""
    rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    _reject_local_catalogues(path, rev_data)
    if "modelo" in rev_data:
        raise RegistryLoadError(f"{path}: revision file must not declare [modelo]; that lives in manifest.toml")
    file_revisions = rev_data.get("revisions")
    if not isinstance(file_revisions, dict) or not file_revisions:
        raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
    for revision_id, raw_revision in file_revisions.items():
        if not isinstance(revision_id, str):
            raise RegistryLoadError(f"{path}: revision key must be a string")
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
    fragment_paths = [revision_manifest]
    fragment_paths.extend(
        sorted(
            p for p in path.rglob("*.toml") if p != revision_manifest and not any(part == "locales" for part in p.parts)
        ),
    )
    merged_revision: dict[str, object] = {}
    for fragment_path in fragment_paths:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _merge_revision_fragment(path: Path, expected_revision_id: str, merged_revision: dict[str, object]) -> None:
    """Merge one fragment TOML into a single raw revision payload."""
    fragment_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    _reject_local_catalogues(path, fragment_data)
    if "modelo" in fragment_data:
        raise RegistryLoadError(f"{path}: revision fragment must not declare [modelo]; that lives in manifest.toml")
    file_revisions = fragment_data.get("revisions")
    if not isinstance(file_revisions, dict) or not file_revisions:
        raise RegistryLoadError(f"{path}: revision fragment must declare [revisions.<id>]")
    if len(file_revisions) != 1:
        raise RegistryLoadError(f"{path}: revision fragment must declare exactly one revision")
    revision_id, raw_revision = next(iter(file_revisions.items()))
    if not isinstance(revision_id, str):
        raise RegistryLoadError(f"{path}: revision key must be a string")
    if revision_id != expected_revision_id:
        raise RegistryLoadError(
            f"{path}: revision fragment declares {revision_id!r}, expected {expected_revision_id!r}",
        )
    raw_revision_table = _as_toml_table(raw_revision)
    if raw_revision_table is None:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} must be a table")
    for key, value in raw_revision_table.items():
        _merge_revision_fragment_field(path, key, value, merged_revision)


def _merge_revision_fragment_field(
    path: Path,
    key: str,
    value: object,
    merged_revision: dict[str, object],
) -> None:
    if key == _REVISION_CONSTRUCTS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'constructs' must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'constructs' conflicts with a non-array field")
        merged_revision[key] = _merge_table_array_fragments(
            path,
            existing,
            value,
            item_label="construct",
            append_array_fields=_CONSTRUCT_APPEND_ARRAYS,
        )
        return
    if key in _REVISION_APPEND_ARRAYS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field {key!r} must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field {key!r} conflicts with a non-array field")
        merged_revision[key] = (*existing, *value)
        return
    if key == _REVISION_EXPORT_LAYOUTS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'export_layouts' must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(
                f"{path}: revision fragment field 'export_layouts' conflicts with a non-array field",
            )
        merged_revision[key] = _merge_export_layout_fragments(path, existing, value)
        return
    if key == _REVISION_COMPLETENESS_MANIFEST:
        existing = merged_revision.get(key)
        merged_revision[key] = _merge_singleton_table_fragment(
            path,
            key,
            existing,
            value,
            append_array_fields=_COMPLETENESS_MANIFEST_APPEND_ARRAYS,
        )
        return
    if key in merged_revision:
        raise RegistryLoadError(f"{path}: revision fragment redeclares scalar field {key!r}")
    merged_revision[key] = value


def _merge_singleton_table_fragment(
    path: Path,
    field_name: str,
    existing: object | None,
    incoming: object,
    *,
    append_array_fields: frozenset[str],
) -> dict[str, object]:
    """Merge a singleton nested TOML table whose selected arrays are appendable."""
    incoming_table = _as_toml_table(incoming)
    if incoming_table is None:
        raise RegistryLoadError(f"{path}: revision fragment field {field_name!r} must be a table")
    if existing is None:
        existing_table: dict[str, object] | None = {}
    else:
        existing_table = _as_toml_table(existing)
        if existing_table is None:
            raise RegistryLoadError(f"{path}: revision fragment field {field_name!r} conflicts with a non-table field")

    merged = dict(existing_table)
    for key, value in incoming_table.items():
        if key in append_array_fields:
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: revision fragment field {field_name!r}.{key!r} must be an array")
            existing_values = merged.get(key, ())
            if not isinstance(existing_values, tuple):
                raise RegistryLoadError(
                    f"{path}: revision fragment field {field_name!r}.{key!r} conflicts with a non-array field",
                )
            merged[key] = (*existing_values, *value)
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(
                f"{path}: revision fragment field {field_name!r}.{key!r} conflicts with another fragment",
            )
        merged[key] = value
    return merged


def _merge_export_layout_fragments(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
) -> tuple[object, ...]:
    """Merge export-layout fragments by layout id, appending record arrays."""
    layouts: list[object] = list(existing)
    index_by_id: dict[str, int] = {}
    for index, layout in enumerate(layouts):
        layout_id = _toml_table_id(layout)
        if layout_id is not None:
            index_by_id[layout_id] = index
    for layout in incoming:
        incoming_table = _as_toml_table(layout)
        layout_id = None if incoming_table is None else _toml_table_id(incoming_table)
        if incoming_table is None or layout_id is None:
            layouts.append(layout)
            continue
        existing_index = index_by_id.get(layout_id)
        if existing_index is None:
            index_by_id[layout_id] = len(layouts)
            layouts.append(layout)
            continue
        existing_layout = _as_toml_table(layouts[existing_index])
        if existing_layout is None:
            raise RegistryLoadError(f"{path}: export layout {layout_id!r} conflicts with a non-table layout")
        layouts[existing_index] = _merge_export_layout_by_id(path, layout_id, existing_layout, incoming_table)
    return tuple(layouts)


def _merge_export_layout_by_id(
    path: Path,
    layout_id: str,
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "id":
            continue
        if key == "records":
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} records must be an array")
            existing_records = merged.get("records", ())
            if not isinstance(existing_records, tuple):
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} existing records are not an array")
            merged["records"] = _merge_table_array_fragments(
                path,
                existing_records,
                value,
                item_label=f"export layout {layout_id!r} record",
                append_array_fields=frozenset({"fields"}),
            )
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(
                f"{path}: export layout {layout_id!r} field {key!r} conflicts with another fragment",
            )
        merged[key] = value
    return merged


def _merge_table_array_fragments(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
    *,
    item_label: str,
    append_array_fields: frozenset[str],
) -> tuple[object, ...]:
    """Merge fragment table arrays by ``id``, appending explicitly mergeable arrays."""
    items: list[object] = list(existing)
    index_by_id: dict[str, int] = {}
    for index, item in enumerate(items):
        item_id = _toml_table_id(item)
        if item_id is not None:
            index_by_id[item_id] = index
    for item in incoming:
        incoming_table = _as_toml_table(item)
        item_id = None if incoming_table is None else _toml_table_id(incoming_table)
        if incoming_table is None or item_id is None:
            items.append(item)
            continue
        existing_index = index_by_id.get(item_id)
        if existing_index is None:
            index_by_id[item_id] = len(items)
            items.append(item)
            continue
        existing_item = _as_toml_table(items[existing_index])
        if existing_item is None:
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} conflicts with a non-table fragment")
        items[existing_index] = _merge_table_fragment_by_id(
            path,
            existing_item,
            incoming_table,
            item_label=item_label,
            item_id=item_id,
            append_array_fields=append_array_fields,
        )
    return tuple(items)


def _merge_table_fragment_by_id(
    path: Path,
    existing: dict[str, object],
    incoming: dict[str, object],
    *,
    item_label: str,
    item_id: str,
    append_array_fields: frozenset[str],
) -> dict[str, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "id":
            continue
        if key in append_array_fields:
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} must be an array")
            existing_values = merged.get(key, ())
            if not isinstance(existing_values, tuple):
                raise RegistryLoadError(
                    f"{path}: {item_label} {item_id!r} field {key!r} conflicts with a non-array fragment",
                )
            _reject_duplicate_appended_table_ids(path, existing_values, value, item_label, item_id, key)
            merged[key] = (*existing_values, *value)
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} conflicts with another fragment")
        merged[key] = value
    return merged


def _reject_duplicate_appended_table_ids(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
    item_label: str,
    item_id: str,
    field: str,
) -> None:
    existing_ids = {iid for item in existing if (iid := _toml_table_id(item)) is not None}
    incoming_ids = {iid for item in incoming if (iid := _toml_table_id(item)) is not None}
    duplicate_ids = sorted(existing_ids.intersection(incoming_ids))
    if duplicate_ids:
        raise RegistryLoadError(
            f"{path}: {item_label} {item_id!r} field {field!r} appends duplicate ids {duplicate_ids!r}",
        )


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Load one shared legal/source catalogue TOML file.

    Returns:
        The compiled :class:`RegistryCatalogues` from the TOML file.
    """
    resolved = path.resolve()
    stat = resolved.stat()
    return _load_catalogue_file_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(path: str, byte_count: int, modified_ns: int) -> RegistryCatalogues:
    del byte_count, modified_ns
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
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


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
    if not isinstance(raw, dict):
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in raw.items():
        if not isinstance(ref_id, str) or not isinstance(payload, dict):
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def load_legal_parameters_only(root: Path) -> Mapping[str, LegalParameter]:
    """Load only the legal-parameter catalogue from ``root/legal/*.toml``.

    Lightweight cycle-safe entry point. Consumers in ``aeat.domain.iva``
    and ``aeat.domain.rental`` need parameter values at module-import
    time, but the full :func:`load_registry_tree` path pulls in
    ``_bindings`` which itself imports from ``aeat.domain.iva`` — a
    circular import.

    This function reuses :func:`load_catalogue_file` (already
    Pydantic-validated and ``lru_cache``-deduplicated) and walks only
    ``root/legal/*.toml``. Modelo parsing, binding validation, and
    cross-catalogue checks do not run; for that, callers must use
    :func:`load_registry_tree`.

    Args:
        root: Repository ``registry/aeat`` directory.

    Returns:
        Frozen mapping of parameter-id → :class:`LegalParameter`.

    Raises:
        RegistryLoadError: When duplicate parameter ids are found across
            multiple TOML files in ``root/legal/``.
    """
    resolved = root.resolve()
    legal_dir = resolved / "legal"
    parameters: dict[str, LegalParameter] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap = set(parameters).intersection(catalogue.parameters)
        if overlap:
            raise RegistryLoadError(f"{path}: duplicate parameter ids {sorted(overlap)!r}")
        parameters.update(catalogue.parameters)
    return parameters


def load_registry_tree(root: Path) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.

    Returns:
        A tuple of all :class:`ModeloDefinition` objects and the merged :class:`RegistryCatalogues`.
    """
    resolved = root.resolve()
    fingerprints = _collect_registry_tree_fingerprints(resolved)
    return _load_registry_tree_cached(str(resolved), fingerprints)


def discover_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    """Discover :class:`ModeloSource` layouts under a ``modelos/`` directory.

    This is the generic source-layout contract for the registry: callers
    can reason about single-file modelos, directory-mode modelos,
    per-revision files, and fragmented revision directories without
    special-casing a modelo id.
    """
    resolved = modelos_dir.resolve()
    sources: list[ModeloSource] = []
    seen_modelo_ids: dict[str, ModeloSource] = {}
    for path in sorted(resolved.glob("*.toml")):
        try:
            raw_data = read_toml(path, error_factory=RegistryLoadError)
            modelo_table = _as_toml_table(raw_data.get("modelo"))
            if modelo_table is None or "id" not in modelo_table:
                raise RegistryLoadError(f"{path}: missing [modelo].id")
            modelo_id = str(modelo_table["id"])
        except Exception as exc:
            raise RegistryLoadError(f"{path}: invalid modelo file: {exc}") from exc
        source = ModeloSource(
            modelo_id=modelo_id,
            layout="single_file",
            path=path.resolve(),
            manifest_path=path.resolve(),
        )
        _append_modelo_source(source, sources, seen_modelo_ids)
    if resolved.is_dir():
        for entry in sorted(resolved.iterdir()):
            if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
                continue
            manifest_path = entry / "manifest.toml"
            try:
                manifest_data = read_toml(manifest_path, error_factory=RegistryLoadError)
                modelo_table = _as_toml_table(manifest_data.get("modelo"))
                if modelo_table is None or "id" not in modelo_table:
                    raise RegistryLoadError(f"{manifest_path}: missing [modelo].id")
                modelo_id = str(modelo_table["id"])
            except Exception as exc:
                raise RegistryLoadError(f"{manifest_path}: invalid manifest: {exc}") from exc
            source = ModeloSource(
                modelo_id=modelo_id,
                layout="directory",
                path=entry.resolve(),
                manifest_path=manifest_path.resolve(),
                revision_sources=_discover_revision_sources(entry / "revisions"),
            )
            _append_modelo_source(source, sources, seen_modelo_ids)
    return tuple(sources)


def _append_modelo_source(
    source: ModeloSource,
    sources: list[ModeloSource],
    seen_modelo_ids: dict[str, ModeloSource],
) -> None:
    previous = seen_modelo_ids.get(source.modelo_id)
    if previous is not None:
        raise RegistryLoadError(
            f"{source.path}: modelo {source.modelo_id!r} also declared at {previous.path}; "
            "remove one of the two layouts",
        )
    seen_modelo_ids[source.modelo_id] = source
    sources.append(source)


def _discover_revision_sources(revisions_dir: Path) -> tuple[ModeloRevisionSource, ...]:
    if not revisions_dir.is_dir():
        return ()
    sources: list[ModeloRevisionSource] = []
    for path in sorted(revisions_dir.glob("*.toml")):
        rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
        file_revisions = rev_data.get("revisions")
        if not isinstance(file_revisions, dict) or not file_revisions:
            raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
        for revision_id in sorted(file_revisions):
            if not isinstance(revision_id, str):
                raise RegistryLoadError(f"{path}: revision key must be a string")
            sources.append(
                ModeloRevisionSource(
                    revision_id=revision_id,
                    layout="revision_file",
                    path=path,
                    fragment_paths=(path,),
                ),
            )
    for path in sorted(revisions_dir.iterdir()):
        if not path.is_dir():
            continue
        revision_manifest = path / "revision.toml"
        fragment_paths = (revision_manifest,) if revision_manifest.is_file() else ()
        fragment_paths = (
            *fragment_paths,
            *tuple(
                p
                for p in sorted(path.rglob("*.toml"))
                if p != revision_manifest and not any(part == "locales" for part in p.parts)
            ),
        )
        sources.append(
            ModeloRevisionSource(
                revision_id=path.name,
                layout="fragment_directory",
                path=path,
                fragment_paths=fragment_paths,
            ),
        )
    return tuple(sources)


_registry_fingerprint_cache: dict[Path, tuple[float, tuple[tuple[str, int, int], ...]]] = {}


def clear_fingerprint_cache() -> None:
    """Clear the 1-second TTL fingerprint cache."""
    _registry_fingerprint_cache.clear()


def _collect_registry_tree_fingerprints(resolved: Path) -> tuple[tuple[str, int, int], ...]:
    """Walk ``resolved`` and return ``(path, size, mtime)`` fingerprints for the lru_cache key.

    Covers every catalogue source the loader will subsequently
    re-open: ``legal/*.toml``, single-file ``modelos/*.toml``, and
    directory-mode ``modelos/<id>/manifest.toml`` plus its
    ``revisions/*.toml`` siblings. It also covers every multi-year-renta
    ``authorization.d/<modelo>.toml`` fragment, which the authority reads at
    the same registry root: per ``aeat-registry-authority-flow`` the
    authorization surface must invalidate the registry cache when it
    changes, so adding, editing, or removing an enrollment fragment reliably
    re-derives every per-modelo capability rather than serving a stale
    authorization. The cache key invalidates the moment any of those files
    changes shape on disk.
    """
    import time

    now = time.time()
    if resolved in _registry_fingerprint_cache:
        cached_time, cached_val = _registry_fingerprint_cache[resolved]
        if now - cached_time < 1.0:
            return cached_val

    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    fingerprints: list[tuple[str, int, int]] = []
    authorization_dir = resolved / "authorization.d"
    if authorization_dir.is_dir():
        for fragment in sorted(authorization_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(fragment))
    for path in sorted(legal_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    for path in sorted(modelos_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    if modelos_dir.is_dir():
        for entry in sorted(modelos_dir.iterdir()):
            fingerprints.extend(_modelo_directory_fingerprints(entry))
    schema_path = resolved / "user_profile" / "schema.toml"
    if schema_path.is_file():
        fingerprints.append(_toml_fingerprint(schema_path))
    res = tuple(fingerprints)
    _registry_fingerprint_cache[resolved] = (now, res)
    return res


def _modelo_directory_fingerprints(entry: Path) -> tuple[tuple[str, int, int], ...]:
    """Return fingerprints for one directory-mode modelo entry, or ``()`` if not in that layout."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[tuple[str, int, int]] = [_toml_fingerprint(entry / "manifest.toml")]
    locales_dir = entry / "locales"
    if locales_dir.is_dir():
        for path in sorted(locales_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    revisions_dir = entry / "revisions"
    if revisions_dir.is_dir():
        for rev_path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    import contextlib
    import hashlib
    import os
    import pickle
    import tempfile

    hasher = hashlib.sha256()
    hasher.update(_REGISTRY_TREE_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(root.encode("utf-8"))
    for item in fingerprints:
        hasher.update(item[0].encode("utf-8"))
        hasher.update(str(item[1]).encode("utf-8"))
        hasher.update(str(item[2]).encode("utf-8"))
    key_hash = hasher.hexdigest()

    cache_path = Path(tempfile.gettempdir()) / f"aeat_registry_{key_hash}.pkl"
    if cache_path.is_file():
        # Internal same-user performance cache of first-party registry data only.
        # The payload is produced exclusively by the dump below in this process and
        # keyed by a sha256 of the registry tree fingerprints; no untrusted input is
        # ever deserialized here. A corrupt/foreign file is swallowed and recomputed.
        with contextlib.suppress(Exception), open(cache_path, "rb") as f:
            return pickle.load(f)  # noqa: S301  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle

    resolved = Path(root)
    catalogues = _load_shared_catalogue_files(resolved / "legal")
    modelos = _load_all_modelo_definitions(resolved / "modelos")
    result = (modelos, catalogues)

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=cache_path.parent, delete=False) as tf:
            # Serialises first-party registry objects to the same-user temp cache read
            # back above; the data never crosses a trust boundary. See the load note.
            pickle.dump(result, tf, protocol=pickle.HIGHEST_PROTOCOL)  # nosemgrep
            temp_name = tf.name
        os.replace(temp_name, cache_path)
    except Exception:
        if temp_name is not None:
            with contextlib.suppress(Exception):
                os.unlink(temp_name)
    return result


def _load_shared_catalogue_files(legal_dir: Path) -> RegistryCatalogues:
    """Load every ``legal/*.toml`` shared-catalogue file with duplicate-id rejection."""
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    parameters: dict[str, LegalParameter] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_sources = set(sources).intersection(catalogue.sources)
        overlap_parameters = set(parameters).intersection(catalogue.parameters)
        if overlap_legal or overlap_sources or overlap_parameters:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} "
                f"sources={sorted(overlap_sources)!r} parameters={sorted(overlap_parameters)!r}",
            )
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


def _load_all_modelo_definitions(modelos_dir: Path) -> tuple[ModeloDefinition, ...]:
    """Load every modelo (single-file + directory-mode) and reject layout collisions.

    A modelo id present both as ``modelos/<id>.toml`` and as
    ``modelos/<id>/manifest.toml`` is a configuration mistake — the
    loader cannot tell which layout is authoritative, so it raises
    instead of silently picking one.
    """
    return tuple(load_modelo_source(source) for source in discover_modelo_sources(modelos_dir))


def _toml_fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns

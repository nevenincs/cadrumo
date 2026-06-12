"""Typed contract for modelo schema-local locale management.

The runtime registry loader owns how schema-local translations are applied:
modelo-level locale TOML is keyed by ``continuidad_id`` and revision-level
locale TOML is keyed by ``casilla_id``. This module gives the locales CLI a
typed authoring contract for :class:`ModeloDefinition` / :class:`ModeloRevision`
storage without moving those translations into the eager application YAML
catalogues.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core import read_toml
from ..core.errors import AeatError
from ..core.external_constants import UTF_8_ENCODING, OutputLanguage
from ..core.resources import bundled_path
from ..domain.calculations.registry._loader import (
    _build_modelo_definition_from_data,
    _load_modelo_manifest,
    _load_modelo_revisions,
)
from ..domain.calculations.registry._schema import CasillaDefinition, ModeloDefinition, ModeloRevision


class ModeloLocaleError(AeatError, ValueError):
    """Raised when modelo schema-local locale management fails."""


class ModeloLocaleScope(StrEnum):
    """Registry-local file scope for modelo schema translations."""

    MODELO = "modelo"
    REVISION = "revision"


class ModeloLocaleFieldKind(StrEnum):
    """Supported translation tables inside registry-local locale TOML files."""

    LABELS = "labels"
    HELP = "help"


class ModeloLocaleDriftKind(StrEnum):
    """Schema-local translation drift categories reported by the manager."""

    MISSING = "missing"
    STALE = "stale"


class ModeloLocaleFileTarget(BaseModel):
    """One registry-local locale TOML target."""

    model_config = ConfigDict(frozen=True)

    locale: OutputLanguage
    modelo_id: str = Field(min_length=1)
    scope: ModeloLocaleScope
    revision_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_scope_revision(self) -> ModeloLocaleFileTarget:
        if self.scope is ModeloLocaleScope.REVISION and self.revision_id is None:
            raise ModeloLocaleError("revision-scoped modelo locale targets require revision_id")
        if self.scope is ModeloLocaleScope.MODELO and self.revision_id is not None:
            raise ModeloLocaleError("modelo-scoped locale targets must not carry revision_id")
        return self

    @property
    def relative_path(self) -> Path:
        """Return this target's path relative to the registry ``modelos`` root."""
        if self.scope is ModeloLocaleScope.MODELO:
            return Path(self.modelo_id) / "locales" / f"{self.locale.value}.toml"
        if self.revision_id is None:
            raise ModeloLocaleError("revision-scoped target lost revision_id")
        return Path(self.modelo_id) / "revisions" / self.revision_id / "locales" / f"{self.locale.value}.toml"


class ModeloLocaleTranslationFile(BaseModel):
    """Parsed contents of one schema-local locale TOML file."""

    model_config = ConfigDict(frozen=True)

    target: ModeloLocaleFileTarget
    path: Path
    labels: dict[str, str] = Field(default_factory=dict)
    help: dict[str, str] = Field(default_factory=dict)

    def table(self, field: ModeloLocaleFieldKind) -> dict[str, str]:
        """Return the translation table for ``field``."""
        return self.labels if field is ModeloLocaleFieldKind.LABELS else self.help


class ModeloLocaleInventoryKey(BaseModel):
    """One schema key that can be translated in a registry-local locale file."""

    model_config = ConfigDict(frozen=True)

    modelo_id: str = Field(min_length=1)
    revision_id: str | None = Field(default=None, min_length=1)
    scope: ModeloLocaleScope
    field: ModeloLocaleFieldKind
    key: str = Field(min_length=1)
    source_casilla_id: str = Field(min_length=1)
    source_continuidad_id: str | None = Field(default=None, min_length=1)
    official_label: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_scope_revision(self) -> ModeloLocaleInventoryKey:
        if self.scope is ModeloLocaleScope.REVISION and self.revision_id is None:
            raise ModeloLocaleError("revision-scoped inventory keys require revision_id")
        if self.scope is ModeloLocaleScope.MODELO and self.revision_id is not None:
            raise ModeloLocaleError("modelo-scoped inventory keys must not carry revision_id")
        return self


class ModeloLocaleDriftRecord(BaseModel):
    """One missing or stale schema-local translation leaf."""

    model_config = ConfigDict(frozen=True)

    target: ModeloLocaleFileTarget
    field: ModeloLocaleFieldKind
    key: str = Field(min_length=1)
    kind: ModeloLocaleDriftKind


class ModeloLocaleCoverageRecord(BaseModel):
    """Coverage summary for one modelo revision and locale."""

    model_config = ConfigDict(frozen=True)

    locale: OutputLanguage
    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    label_required: int = Field(ge=0)
    label_translated: int = Field(ge=0)
    help_required: int = Field(ge=0)
    help_translated: int = Field(ge=0)
    drift: tuple[ModeloLocaleDriftRecord, ...] = ()

    @property
    def required_total(self) -> int:
        """Return total required translation leaves."""
        return self.label_required + self.help_required

    @property
    def translated_total(self) -> int:
        """Return total present translation leaves."""
        return self.label_translated + self.help_translated

    @property
    def complete(self) -> bool:
        """Return whether all required translation leaves are present."""
        return self.translated_total == self.required_total and not any(
            record.kind is ModeloLocaleDriftKind.STALE for record in self.drift
        )


class ModeloLocaleManager:
    """Path authority for registry-local modelo schema translation files."""

    def __init__(self, registry_root: Path | None = None):
        """Initialise the manager with a contained AEAT registry root.

        Args:
            registry_root: Directory containing the AEAT registry tree. When
                omitted, the bundled ``registry/aeat`` resource is used.

        Raises:
            ModeloLocaleError: If the root or required ``modelos`` directory is
                missing.
        """
        root = bundled_path("registry", "aeat") if registry_root is None else registry_root
        self.registry_root = root.resolve()
        if not self.registry_root.is_dir():
            raise ModeloLocaleError(f"Registry root does not exist: {self.registry_root}")
        self.modelos_root = self._contained_path("modelos")
        if not self.modelos_root.is_dir():
            raise ModeloLocaleError(f"Registry modelos root does not exist: {self.modelos_root}")

    def resolve_modelo_dir(self, modelo_id: str) -> Path:
        """Resolve one directory-mode modelo under the contained registry root."""
        self._validate_segment(modelo_id, field_name="modelo_id")
        modelo_dir = self._contained_path("modelos", modelo_id)
        if not modelo_dir.is_dir() or not modelo_dir.joinpath("manifest.toml").is_file():
            raise ModeloLocaleError(f"Directory-mode modelo not found: {modelo_id!r}")
        return modelo_dir

    def resolve_revision_dir(self, modelo_id: str, revision_id: str) -> Path:
        """Resolve one revision directory under a directory-mode modelo."""
        self._validate_segment(revision_id, field_name="revision_id")
        modelo_dir = self.resolve_modelo_dir(modelo_id)
        revision_dir = self._contained_path(
            "modelos",
            modelo_dir.name,
            "revisions",
            revision_id,
        )
        if not revision_dir.is_dir():
            raise ModeloLocaleError(f"Revision directory not found: {modelo_id!r}/{revision_id!r}")
        return revision_dir

    def load_modelo(self, modelo_id: str) -> ModeloDefinition:
        """Load a directory-mode modelo without applying locale TOML files."""
        modelo_dir = self.resolve_modelo_dir(modelo_id)
        revisions = _load_modelo_revisions(modelo_dir)
        if not revisions:
            raise ModeloLocaleError(f"{modelo_dir}: no revisions found in revisions/")
        merged = {**_load_modelo_manifest(modelo_dir), "revisions": revisions}
        return _build_modelo_definition_from_data(modelo_dir, merged)

    def revision_ids(self, modelo_id: str) -> tuple[str, ...]:
        """Return sorted revision ids for ``modelo_id``."""
        modelo = self.load_modelo(modelo_id)
        return tuple(sorted(str(revision_id) for revision_id in modelo.revisions))

    def inventory_keys(
        self,
        modelo_id: str,
        revision_id: str | None = None,
    ) -> tuple[ModeloLocaleInventoryKey, ...]:
        """Return registry-backed schema-local translation keys for a modelo.

        Revision-local records are keyed by ``casilla_id``. Modelo-local
        records are keyed by ``continuidad_id`` and deduplicated across the
        selected revisions because the target TOML file is modelo-wide.
        """
        modelo = self.load_modelo(modelo_id)
        revisions = _selected_revisions(modelo, revision_id)
        records: dict[tuple[ModeloLocaleScope, str | None, ModeloLocaleFieldKind, str], ModeloLocaleInventoryKey] = {}
        for revision in revisions:
            for casilla in sorted(revision.casillas, key=lambda item: item.id):
                _add_revision_inventory(records, modelo_id=str(modelo.id), revision=revision, casilla=casilla)
                if casilla.continuidad_id is not None:
                    _add_modelo_inventory(records, modelo_id=str(modelo.id), casilla=casilla)
        return tuple(
            records[key]
            for key in sorted(records, key=lambda item: (item[0].value, item[1] or "", item[2].value, item[3]))
        )

    def drift_records(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
    ) -> tuple[ModeloLocaleDriftRecord, ...]:
        """Return missing and stale schema-local translation leaves."""
        language = _coerce_output_language(locale)
        expected = self.inventory_keys(modelo_id, revision_id)
        expected_by_target = _expected_keys_by_target(expected, locale=language)
        valid_by_target = _expected_keys_by_target(self.inventory_keys(modelo_id), locale=language)

        records: list[ModeloLocaleDriftRecord] = []
        for target in _drift_targets(language=language, modelo_id=modelo_id, revision_id=revision_id):
            translation = self.load_translation_file(target)
            for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP):
                expected_keys = _keys_for_target(expected_by_target, target, field)
                valid_keys = _keys_for_target(valid_by_target, target, field)
                actual = translation.table(field)
                for key in sorted(expected_keys - set(actual)):
                    records.append(
                        ModeloLocaleDriftRecord(
                            target=target,
                            field=field,
                            key=key,
                            kind=ModeloLocaleDriftKind.MISSING,
                        ),
                    )
                for key in sorted(set(actual) - valid_keys):
                    records.append(
                        ModeloLocaleDriftRecord(
                            target=target,
                            field=field,
                            key=key,
                            kind=ModeloLocaleDriftKind.STALE,
                        ),
                    )
        return tuple(records)

    def coverage_record(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
    ) -> ModeloLocaleCoverageRecord:
        """Return schema-local translation coverage for one modelo revision."""
        language = _coerce_output_language(locale)
        expected = self.inventory_keys(modelo_id, revision_id)
        expected_by_target = _expected_keys_by_target(expected, locale=language)

        label_required = sum(1 for item in expected if item.field is ModeloLocaleFieldKind.LABELS)
        help_required = sum(1 for item in expected if item.field is ModeloLocaleFieldKind.HELP)
        label_translated = 0
        help_translated = 0
        for target in expected_by_target:
            translation = self.load_translation_file(target)
            label_keys = expected_by_target[target][ModeloLocaleFieldKind.LABELS]
            help_keys = expected_by_target[target][ModeloLocaleFieldKind.HELP]
            label_translated += len(_translated_keys(translation.labels, label_keys))
            help_translated += len(_translated_keys(translation.help, help_keys))

        return ModeloLocaleCoverageRecord(
            locale=language,
            modelo_id=modelo_id,
            revision_id=revision_id,
            label_required=label_required,
            label_translated=label_translated,
            help_required=help_required,
            help_translated=help_translated,
            drift=self.drift_records(language, modelo_id, revision_id),
        )

    def scaffold_revision(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
    ) -> tuple[Path, ...]:
        """Align locale TOML targets for one modelo revision.

        Missing leaves are inserted with the schema key as an untranslated
        placeholder. Existing translated values are preserved. Stale leaves are
        removed because they no longer point at registry-backed schema keys.
        """
        language = _coerce_output_language(locale)
        expected = _expected_keys_by_target(self.inventory_keys(modelo_id, revision_id), locale=language)
        valid = _expected_keys_by_target(self.inventory_keys(modelo_id), locale=language)
        changed_paths: list[Path] = []
        for target in _drift_targets(language=language, modelo_id=modelo_id, revision_id=revision_id):
            current = self.load_translation_file(target)
            updated = _aligned_translation_file(current, expected=expected, valid=valid)
            changed = updated.labels != current.labels or updated.help != current.help
            missing_required_file = not current.path.exists() and _target_has_expected_keys(expected, target)
            if changed or missing_required_file:
                changed_paths.append(self.write_translation_file(updated))
        return tuple(changed_paths)

    def set_translation_value(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
        field: ModeloLocaleFieldKind | str,
        key: str,
        value: str,
    ) -> Path:
        """Set one schema-local translated leaf after registry-key validation."""
        field_kind = _coerce_field_kind(field)
        target = self._target_for_key(locale, modelo_id, revision_id, field_kind, key)
        path = self._translation_leaf_path(target, field_kind, key)
        current = self._load_translation_path(target, path)
        labels = dict(current.labels)
        help_text = dict(current.help)
        table = labels if field_kind is ModeloLocaleFieldKind.LABELS else help_text
        table[key] = value
        return self._write_translation_path(path, labels=labels, help_text=help_text)

    def remove_translation_value(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
        field: ModeloLocaleFieldKind | str,
        key: str,
    ) -> Path:
        """Remove one existing schema-local translated leaf."""
        field_kind = _coerce_field_kind(field)
        language = _coerce_output_language(locale)
        candidates = _drift_targets(language=language, modelo_id=modelo_id, revision_id=revision_id)
        matches: list[ModeloLocaleTranslationFile] = []
        for target in candidates:
            for path in self._translation_paths(target):
                current = self._load_translation_path(target, path)
                if key in current.table(field_kind):
                    matches.append(current)
        if not matches:
            raise ModeloLocaleError(f"Modelo locale key not found: {field_kind.value}/{key!r}")
        if len(matches) > 1:
            raise ModeloLocaleError(f"Modelo locale key is ambiguous across scopes: {field_kind.value}/{key!r}")
        current = matches[0]
        labels = dict(current.labels)
        help_text = dict(current.help)
        table = labels if field_kind is ModeloLocaleFieldKind.LABELS else help_text
        del table[key]
        return self._write_translation_path(current.path, labels=labels, help_text=help_text)

    def _target_for_key(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
        field: ModeloLocaleFieldKind,
        key: str,
    ) -> ModeloLocaleFileTarget:
        """Resolve which locale TOML target owns a schema key."""
        language = _coerce_output_language(locale)
        matching_targets = {
            _target_for_inventory_key(item, locale=language)
            for item in self.inventory_keys(modelo_id, revision_id)
            if item.field is field and item.key == key
        }
        if not matching_targets:
            raise ModeloLocaleError(f"Modelo schema key not found: {field.value}/{key!r}")
        if len(matching_targets) > 1:
            raise ModeloLocaleError(f"Modelo schema key is ambiguous across scopes: {field.value}/{key!r}")
        return next(iter(matching_targets))

    def resolve_target_path(self, target: ModeloLocaleFileTarget) -> Path:
        """Resolve a locale target to a contained TOML file path."""
        if target.scope is ModeloLocaleScope.MODELO:
            modelo_dir = self.resolve_modelo_dir(target.modelo_id)
            return self._contained_path("modelos", modelo_dir.name, "locales", f"{target.locale.value}.toml")
        if target.revision_id is None:
            raise ModeloLocaleError("revision-scoped target lost revision_id")
        revision_dir = self.resolve_revision_dir(target.modelo_id, target.revision_id)
        return self._contained_path(
            "modelos",
            revision_dir.parent.parent.name,
            "revisions",
            revision_dir.name,
            "locales",
            f"{target.locale.value}.toml",
        )

    def load_translation_file(
        self,
        target: ModeloLocaleFileTarget,
        *,
        require_exists: bool = False,
    ) -> ModeloLocaleTranslationFile:
        """Load one schema-local locale TOML file, or return an empty file model."""
        paths = self._translation_paths(target)
        if len(paths) == 1 and not paths[0].exists():
            if require_exists:
                raise ModeloLocaleError(f"Modelo locale file not found: {paths[0]}")
            return ModeloLocaleTranslationFile(target=target, path=paths[0], labels={}, help={})

        labels: dict[str, str] = {}
        help_text: dict[str, str] = {}
        for path in paths:
            current = self._load_translation_path(target, path)
            _merge_translation_table(labels, current.labels, path=path, table_name="labels")
            _merge_translation_table(help_text, current.help, path=path, table_name="help")
        return ModeloLocaleTranslationFile(
            target=target,
            path=self.resolve_target_path(target),
            labels=labels,
            help=help_text,
        )

    def write_translation_file(self, translation: ModeloLocaleTranslationFile) -> Path:
        """Write one schema-local locale TOML file with stable table ordering."""
        expected_path = self.resolve_target_path(translation.target)
        if translation.path.resolve() != expected_path:
            raise ModeloLocaleError(f"Modelo locale file path mismatch: {translation.path}")
        fragment_dir = expected_path.with_suffix("")
        if fragment_dir.is_dir() and not expected_path.exists():
            raise ModeloLocaleError(
                f"Modelo locale target is fragmented; update existing fragments with set/remove: {fragment_dir}",
            )
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        return self._write_translation_path(expected_path, labels=translation.labels, help_text=translation.help)

    def _translation_paths(self, target: ModeloLocaleFileTarget) -> tuple[Path, ...]:
        """Return the flat file or fragment files that make up ``target``."""
        flat_path = self.resolve_target_path(target)
        fragment_dir = flat_path.with_suffix("")
        if flat_path.exists() and fragment_dir.is_dir():
            raise ModeloLocaleError(
                f"Locale {target.locale.value!r} is declared both as a file and a fragment directory in "
                f"{flat_path.parent}",
            )
        if flat_path.exists():
            if not flat_path.is_file():
                raise ModeloLocaleError(f"Modelo locale target is not a file: {flat_path}")
            return (flat_path,)
        if fragment_dir.is_dir():
            paths = tuple(sorted(fragment_dir.glob("*.toml")))
            if paths:
                return paths
        return (flat_path,)

    def _translation_leaf_path(
        self,
        target: ModeloLocaleFileTarget,
        field: ModeloLocaleFieldKind,
        key: str,
    ) -> Path:
        """Return the concrete TOML file that owns ``field/key`` for ``target``."""
        paths = self._translation_paths(target)
        if len(paths) == 1:
            return paths[0]
        matches: list[Path] = []
        for path in paths:
            translation = self._load_translation_path(target, path)
            if key in translation.table(field):
                matches.append(path)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ModeloLocaleError(f"Modelo locale key is duplicated across fragments: {field.value}/{key!r}")
        raise ModeloLocaleError(f"Modelo locale key has no owning fragment: {field.value}/{key!r}")

    def _load_translation_path(self, target: ModeloLocaleFileTarget, path: Path) -> ModeloLocaleTranslationFile:
        """Load one concrete schema-local locale TOML file."""
        if not path.exists():
            return ModeloLocaleTranslationFile(target=target, path=path, labels={}, help={})
        if not path.is_file():
            raise ModeloLocaleError(f"Modelo locale target is not a file: {path}")
        raw = read_toml(path, error_factory=ModeloLocaleError)
        return ModeloLocaleTranslationFile(
            target=target,
            path=path,
            labels=_coerce_translation_table(raw.get("labels", {}), path=path, table_name="labels"),
            help=_coerce_translation_table(raw.get("help", {}), path=path, table_name="help"),
        )

    @staticmethod
    def _write_translation_path(path: Path, *, labels: dict[str, str], help_text: dict[str, str]) -> Path:
        """Write one concrete schema-local locale TOML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _render_translation_toml(labels=labels, help_text=help_text),
            encoding=UTF_8_ENCODING,
        )
        return path.resolve()

    def _contained_path(self, *segments: str) -> Path:
        """Return a resolved path guaranteed to stay below ``registry_root``."""
        for segment in segments:
            self._validate_segment(segment, field_name="path segment")
        candidate = self.registry_root.joinpath(*segments).resolve()
        try:
            candidate.relative_to(self.registry_root)
        except ValueError as exc:
            raise ModeloLocaleError(f"Registry path escapes root: {candidate}") from exc
        return candidate

    @staticmethod
    def _validate_segment(segment: str, *, field_name: str) -> None:
        """Reject path-like values where registry identifiers are expected."""
        if not segment or segment in {".", ".."}:
            raise ModeloLocaleError(f"Invalid {field_name}: {segment!r}")
        if any(token in segment for token in ("/", "\\", ":")):
            raise ModeloLocaleError(f"Invalid {field_name}: {segment!r}")


def _selected_revisions(modelo: ModeloDefinition, revision_id: str | None) -> tuple[ModeloRevision, ...]:
    """Return selected revisions from ``modelo``."""
    if revision_id is None:
        return tuple(modelo.revisions[key] for key in sorted(modelo.revisions))
    revision = modelo.revisions.get(revision_id)
    if revision is None:
        raise ModeloLocaleError(f"Revision not found: {modelo.id!s}/{revision_id!r}")
    return (revision,)


def _add_revision_inventory(
    records: dict[tuple[ModeloLocaleScope, str | None, ModeloLocaleFieldKind, str], ModeloLocaleInventoryKey],
    *,
    modelo_id: str,
    revision: ModeloRevision,
    casilla: CasillaDefinition,
) -> None:
    """Add label/help inventory records for a revision-local casilla key."""
    for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP):
        records[(ModeloLocaleScope.REVISION, str(revision.id), field, casilla.id)] = ModeloLocaleInventoryKey(
            modelo_id=modelo_id,
            revision_id=str(revision.id),
            scope=ModeloLocaleScope.REVISION,
            field=field,
            key=casilla.id,
            source_casilla_id=casilla.id,
            source_continuidad_id=casilla.continuidad_id,
            official_label=casilla.label,
        )


def _add_modelo_inventory(
    records: dict[tuple[ModeloLocaleScope, str | None, ModeloLocaleFieldKind, str], ModeloLocaleInventoryKey],
    *,
    modelo_id: str,
    casilla: CasillaDefinition,
) -> None:
    """Add label/help inventory records for a modelo-wide continuity key."""
    if casilla.continuidad_id is None:
        return
    for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP):
        records.setdefault(
            (ModeloLocaleScope.MODELO, None, field, casilla.continuidad_id),
            ModeloLocaleInventoryKey(
                modelo_id=modelo_id,
                revision_id=None,
                scope=ModeloLocaleScope.MODELO,
                field=field,
                key=casilla.continuidad_id,
                source_casilla_id=casilla.id,
                source_continuidad_id=casilla.continuidad_id,
                official_label=casilla.label,
            ),
        )


def _coerce_output_language(locale: OutputLanguage | str) -> OutputLanguage:
    """Return ``locale`` as an :class:`OutputLanguage`."""
    if isinstance(locale, OutputLanguage):
        return locale
    try:
        return OutputLanguage(locale)
    except ValueError as exc:
        raise ModeloLocaleError(f"Unsupported locale: {locale!r}") from exc


def _coerce_field_kind(field: ModeloLocaleFieldKind | str) -> ModeloLocaleFieldKind:
    """Return ``field`` as a :class:`ModeloLocaleFieldKind`."""
    if isinstance(field, ModeloLocaleFieldKind):
        return field
    try:
        return ModeloLocaleFieldKind(field)
    except ValueError as exc:
        raise ModeloLocaleError(f"Unsupported modelo locale field: {field!r}") from exc


def _target_for_inventory_key(item: ModeloLocaleInventoryKey, *, locale: OutputLanguage) -> ModeloLocaleFileTarget:
    """Build the TOML target that stores ``item``."""
    return ModeloLocaleFileTarget(
        locale=locale,
        modelo_id=item.modelo_id,
        scope=item.scope,
        revision_id=item.revision_id,
    )


type _ExpectedKeysByTarget = dict[ModeloLocaleFileTarget, dict[ModeloLocaleFieldKind, set[str]]]


def _expected_keys_by_target(
    items: tuple[ModeloLocaleInventoryKey, ...],
    *,
    locale: OutputLanguage,
) -> _ExpectedKeysByTarget:
    """Group expected inventory keys by locale TOML target and field."""
    grouped: _ExpectedKeysByTarget = {}
    for item in items:
        target = _target_for_inventory_key(item, locale=locale)
        grouped.setdefault(
            target,
            {
                ModeloLocaleFieldKind.LABELS: set(),
                ModeloLocaleFieldKind.HELP: set(),
            },
        )[item.field].add(item.key)
    return grouped


def _drift_targets(
    *,
    language: OutputLanguage,
    modelo_id: str,
    revision_id: str,
) -> tuple[ModeloLocaleFileTarget, ModeloLocaleFileTarget]:
    """Return the modelo and revision targets relevant to a revision audit."""
    return (
        ModeloLocaleFileTarget(locale=language, modelo_id=modelo_id, scope=ModeloLocaleScope.MODELO),
        ModeloLocaleFileTarget(
            locale=language,
            modelo_id=modelo_id,
            scope=ModeloLocaleScope.REVISION,
            revision_id=revision_id,
        ),
    )


def _keys_for_target(
    grouped: _ExpectedKeysByTarget,
    target: ModeloLocaleFileTarget,
    field: ModeloLocaleFieldKind,
) -> set[str]:
    """Return expected keys for ``target`` and ``field``."""
    fields = grouped.get(target)
    if fields is None:
        return set()
    return fields[field]


def _target_has_expected_keys(grouped: _ExpectedKeysByTarget, target: ModeloLocaleFileTarget) -> bool:
    """Return whether ``target`` has at least one expected translation leaf."""
    fields = grouped.get(target)
    return fields is not None and any(
        fields[field] for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP)
    )


def _aligned_translation_file(
    current: ModeloLocaleTranslationFile,
    *,
    expected: _ExpectedKeysByTarget,
    valid: _ExpectedKeysByTarget,
) -> ModeloLocaleTranslationFile:
    """Return ``current`` aligned to the expected and valid schema keys."""
    labels = _aligned_table(
        current.labels,
        expected_keys=_keys_for_target(expected, current.target, ModeloLocaleFieldKind.LABELS),
        valid_keys=_keys_for_target(valid, current.target, ModeloLocaleFieldKind.LABELS),
    )
    help_text = _aligned_table(
        current.help,
        expected_keys=_keys_for_target(expected, current.target, ModeloLocaleFieldKind.HELP),
        valid_keys=_keys_for_target(valid, current.target, ModeloLocaleFieldKind.HELP),
    )
    return ModeloLocaleTranslationFile(target=current.target, path=current.path, labels=labels, help=help_text)


def _aligned_table(current: dict[str, str], *, expected_keys: set[str], valid_keys: set[str]) -> dict[str, str]:
    """Preserve translated values, add placeholders, and drop stale keys."""
    aligned = {key: value for key, value in current.items() if key in valid_keys}
    for key in expected_keys:
        aligned.setdefault(key, key)
    return aligned


def _translated_keys(table: dict[str, str], expected_keys: set[str]) -> set[str]:
    """Return keys present with non-placeholder values."""
    return {key for key in expected_keys if key in table and table[key] != key}


def _target_sort_key(target: ModeloLocaleFileTarget) -> tuple[str, str, str, str]:
    """Return a deterministic sort key for locale file targets."""
    return (
        target.modelo_id,
        target.scope.value,
        target.revision_id or "",
        target.locale.value,
    )


def _coerce_translation_table(raw: object, *, path: Path, table_name: str) -> dict[str, str]:
    """Return ``raw`` as a str-to-str translation table."""
    if not isinstance(raw, dict):
        raise ModeloLocaleError(f"{path}: [{table_name}] must be a TOML table")
    table: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ModeloLocaleError(f"{path}: [{table_name}] keys must be strings")
        if not isinstance(value, str):
            raise ModeloLocaleError(f"{path}: [{table_name}] {key!r} must be a string")
        table[key] = value
    return table


def _merge_translation_table(target: dict[str, str], source: dict[str, str], *, path: Path, table_name: str) -> None:
    """Merge one fragment table, rejecting duplicate keys."""
    for key, value in source.items():
        if key in target:
            raise ModeloLocaleError(f"{path}: duplicate [{table_name}] key across locale fragments: {key!r}")
        target[key] = value


def _render_translation_toml(*, labels: dict[str, str], help_text: dict[str, str]) -> str:
    """Render schema-local translations to deterministic TOML text."""
    lines: list[str] = []
    _append_toml_table(lines, "labels", labels)
    lines.append("")
    _append_toml_table(lines, "help", help_text)
    return "\n".join(lines) + "\n"


def _append_toml_table(lines: list[str], table_name: str, table: dict[str, str]) -> None:
    """Append one TOML string table to ``lines``."""
    lines.append(f"[{table_name}]")
    for key in sorted(table):
        lines.append(f"{_toml_string(key)} = {_toml_string(table[key])}")


def _toml_string(value: str) -> str:
    """Render ``value`` as a TOML basic string."""
    escapes: dict[str, str] = {
        "\\": "\\\\",
        '"': '\\"',
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }
    rendered = "".join(escapes.get(char, char) for char in value)
    return f'"{rendered}"'


__all__ = [
    "ModeloLocaleCoverageRecord",
    "ModeloLocaleDriftKind",
    "ModeloLocaleDriftRecord",
    "ModeloLocaleError",
    "ModeloLocaleFieldKind",
    "ModeloLocaleFileTarget",
    "ModeloLocaleInventoryKey",
    "ModeloLocaleManager",
    "ModeloLocaleScope",
    "ModeloLocaleTranslationFile",
]

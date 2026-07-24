"""Typed contract for modelo schema-local locale management.

The runtime registry loader owns how schema-local translations are applied:
modelo-level locale TOML is keyed by ``continuidad_id`` and revision-level
locale TOML is keyed by ``casilla_id``. This module gives the locales CLI a
typed authoring contract for :class:`ModeloDefinition` / :class:`ModeloRevision`
storage without moving those translations into the eager application YAML
catalogues.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core import CasillaId, read_toml
from ..core.atomic_write import atomic_write_text
from ..core.errors import CadrumoError
from ..core.external_constants import UTF_8_ENCODING, OutputLanguage
from ..core.resources import bundled_path
from ..domain.calculations.registry import (
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryLoadError,
    load_modelo_directory_without_locales,
)


class ModeloLocaleError(CadrumoError, ValueError):
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


class ModeloLocaleLeafState(StrEnum):
    """Honest per-leaf translation state for one schema-local value.

    A leaf is classified into exactly one state so that reported counts
    always partition the required key set. Only ``AUTHORED`` counts as
    translated: a value that echoes its own key is the scaffold
    placeholder, and a help value that merely repeats the label (in this
    locale or the official Spanish schema label) documents nothing.
    """

    AUTHORED = "authored"
    KEY_ECHO = "key_echo"
    BLANK = "blank"
    MIRRORED = "mirrored"
    ABSENT = "absent"


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
    source_casilla_id: CasillaId
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
    """Coverage summary for one modelo revision and locale.

    The per-field counters partition the required key set by
    :class:`ModeloLocaleLeafState`: ``translated`` counts authored values
    only, while key-echo placeholders, mirrored help, and absent leaves
    are reported separately so no counter can overstate progress.
    """

    model_config = ConfigDict(frozen=True)

    locale: OutputLanguage
    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    label_required: int = Field(ge=0)
    label_translated: int = Field(ge=0)
    label_key_echo: int = Field(ge=0, default=0)
    label_blank: int = Field(ge=0, default=0)
    help_required: int = Field(ge=0)
    help_translated: int = Field(ge=0)
    help_key_echo: int = Field(ge=0, default=0)
    help_blank: int = Field(ge=0, default=0)
    help_mirrored: int = Field(ge=0, default=0)
    drift: tuple[ModeloLocaleDriftRecord, ...] = ()

    @property
    def label_absent(self) -> int:
        """Return required label leaves with no value on disk."""
        return self.label_required - self.label_translated - self.label_key_echo - self.label_blank

    @property
    def help_absent(self) -> int:
        """Return required help leaves with no value on disk."""
        return self.help_required - self.help_translated - self.help_key_echo - self.help_blank - self.help_mirrored

    @property
    def required_total(self) -> int:
        """Return total required translation leaves."""
        return self.label_required + self.help_required

    @property
    def translated_total(self) -> int:
        """Return total authored translation leaves."""
        return self.label_translated + self.help_translated

    @property
    def complete(self) -> bool:
        """Return whether every label is authored and no stale keys remain.

        Completeness gates on labels only: labels translate an
        authoritative source (the official Spanish schema label), while
        the registry declares no help source, so demanding help would
        demand prose with no authority behind it. The help partition is
        still fully reported as an optional enrichment dimension.
        """
        return self.label_translated == self.label_required and not any(
            record.kind is ModeloLocaleDriftKind.STALE for record in self.drift
        )


class ModeloLocaleManager:
    """Path authority for registry-local modelo schema translation files."""

    def __init__(self, registry_root: Path | None = None, *, fragment_leaf_capacity: int = 1000):
        """Initialise the manager with a contained AEAT registry root.

        Args:
            registry_root: Directory containing the AEAT registry tree. When
                omitted, the bundled ``registry/aeat`` resource is used.
            fragment_leaf_capacity: Maximum translation leaves per fragment
                file for fragmented locale targets. The default matches the
                shipped fragment convention of 1000 leaves per file.

        Raises:
            ModeloLocaleError: If the root or required ``modelos`` directory is
                missing, or the fragment capacity is not positive.
        """
        if fragment_leaf_capacity < 1:
            raise ModeloLocaleError(f"Fragment leaf capacity must be positive: {fragment_leaf_capacity}")
        self.fragment_leaf_capacity = fragment_leaf_capacity
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
        """Load a directory-mode :class:`ModeloDefinition` without applying locale TOML files."""
        modelo_dir = self.resolve_modelo_dir(modelo_id)
        try:
            return load_modelo_directory_without_locales(modelo_dir)
        except RegistryLoadError as exc:
            raise ModeloLocaleError(str(exc)) from exc

    def modelo_ids(self) -> tuple[str, ...]:
        """Return sorted directory-mode modelo ids under the registry root."""
        return tuple(
            sorted(
                path.name
                for path in self.modelos_root.iterdir()
                if path.is_dir() and path.joinpath("manifest.toml").is_file()
            ),
        )

    def revision_ids(self, modelo_id: str) -> tuple[str, ...]:
        """Return sorted revision ids for ``modelo_id``."""
        modelo = self.load_modelo(modelo_id)
        return tuple(sorted(str(revision_id) for revision_id in modelo.revisions))

    def inventory_keys(
        self,
        modelo_id: str,
        revision_id: str | None = None,
    ) -> tuple[ModeloLocaleInventoryKey, ...]:
        """Return :class:`ModeloLocaleInventoryKey` rows for a modelo.

        Revision-local records are keyed by ``casilla_id``. Modelo-local
        records are keyed by ``continuidad_id`` and deduplicated across the
        selected revisions because the target TOML file is modelo-wide.
        """
        return _inventory_records(self.load_modelo(modelo_id), revision_id)

    def drift_records(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
    ) -> tuple[ModeloLocaleDriftRecord, ...]:
        """Return :class:`ModeloLocaleDriftRecord` rows for missing and stale schema-local leaves."""
        language = _coerce_output_language(locale)
        return self._drift_from_modelo(language, self.load_modelo(modelo_id), revision_id)

    def _drift_from_modelo(
        self,
        language: OutputLanguage,
        modelo: ModeloDefinition,
        revision_id: str,
    ) -> tuple[ModeloLocaleDriftRecord, ...]:
        """Compute drift rows for one revision of an already-loaded modelo."""
        modelo_id = str(modelo.id)
        expected = _inventory_records(modelo, revision_id)
        expected_by_target = _expected_keys_by_target(expected, locale=language)
        valid_by_target = _expected_keys_by_target(_inventory_records(modelo, None), locale=language)

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
        """Return a :class:`ModeloLocaleCoverageRecord` for one modelo revision.

        Counters are derived from :func:`classify_modelo_locale_leaf`, so a
        key-echo placeholder or a mirrored help value never increments the
        translated counts.
        """
        return self._coverage_from_modelo(_coerce_output_language(locale), self.load_modelo(modelo_id), revision_id)

    def coverage_records(
        self,
        modelo_id: str,
        *,
        revision_id: str | None = None,
        locales: tuple[OutputLanguage, ...],
    ) -> tuple[ModeloLocaleCoverageRecord, ...]:
        """Return coverage records for selected revisions and locales.

        The modelo is loaded once and reused across every
        ``revision x locale`` combination, keeping a registry-wide status
        sweep tractable for large modelos.
        """
        modelo = self.load_modelo(modelo_id)
        revision_ids = (
            (revision_id,) if revision_id is not None else tuple(sorted(str(key) for key in modelo.revisions))
        )
        return tuple(
            self._coverage_from_modelo(_coerce_output_language(language), modelo, selected)
            for selected in revision_ids
            for language in locales
        )

    def _coverage_from_modelo(
        self,
        language: OutputLanguage,
        modelo: ModeloDefinition,
        revision_id: str,
    ) -> ModeloLocaleCoverageRecord:
        """Compute one coverage record from an already-loaded modelo."""
        modelo_id = str(modelo.id)
        expected = _inventory_records(modelo, revision_id)
        expected_by_target = _expected_keys_by_target(expected, locale=language)
        official_by_target = _official_labels_by_target(expected, locale=language)

        label_required = sum(1 for item in expected if item.field is ModeloLocaleFieldKind.LABELS)
        help_required = sum(1 for item in expected if item.field is ModeloLocaleFieldKind.HELP)
        counts: dict[tuple[ModeloLocaleFieldKind, ModeloLocaleLeafState], int] = {}
        for target in expected_by_target:
            translation = self.load_translation_file(target)
            officials = official_by_target.get(target, {})
            for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP):
                table = translation.table(field)
                for key in expected_by_target[target][field]:
                    state = classify_modelo_locale_leaf(
                        field,
                        key,
                        table.get(key),
                        label_value=translation.labels.get(key),
                        official_label=officials.get(key),
                    )
                    counts[(field, state)] = counts.get((field, state), 0) + 1

        return ModeloLocaleCoverageRecord(
            locale=language,
            modelo_id=modelo_id,
            revision_id=revision_id,
            label_required=label_required,
            label_translated=counts.get((ModeloLocaleFieldKind.LABELS, ModeloLocaleLeafState.AUTHORED), 0),
            label_key_echo=counts.get((ModeloLocaleFieldKind.LABELS, ModeloLocaleLeafState.KEY_ECHO), 0),
            label_blank=counts.get((ModeloLocaleFieldKind.LABELS, ModeloLocaleLeafState.BLANK), 0),
            help_required=help_required,
            help_translated=counts.get((ModeloLocaleFieldKind.HELP, ModeloLocaleLeafState.AUTHORED), 0),
            help_key_echo=counts.get((ModeloLocaleFieldKind.HELP, ModeloLocaleLeafState.KEY_ECHO), 0),
            help_blank=counts.get((ModeloLocaleFieldKind.HELP, ModeloLocaleLeafState.BLANK), 0),
            help_mirrored=counts.get((ModeloLocaleFieldKind.HELP, ModeloLocaleLeafState.MIRRORED), 0),
            drift=self._drift_from_modelo(language, modelo, revision_id),
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
        Fragmented targets are aligned fragment-by-fragment: stale keys are
        dropped from their owning fragments and missing keys are appended to
        the tail fragment of their field family, spilling into new fragments
        at :attr:`fragment_leaf_capacity`.
        """
        language = _coerce_output_language(locale)
        expected = _expected_keys_by_target(self.inventory_keys(modelo_id, revision_id), locale=language)
        valid = _expected_keys_by_target(self.inventory_keys(modelo_id), locale=language)
        changed_paths: list[Path] = []
        for target in _drift_targets(language=language, modelo_id=modelo_id, revision_id=revision_id):
            flat_path = self.resolve_target_path(target)
            if flat_path.with_suffix("").is_dir() and not flat_path.exists():
                changed_paths.extend(self._scaffold_fragmented_target(target, expected=expected, valid=valid))
                continue
            current = self.load_translation_file(target)
            updated = _aligned_translation_file(current, expected=expected, valid=valid)
            changed = updated.labels != current.labels or updated.help != current.help
            missing_required_file = not current.path.exists() and _target_has_expected_keys(expected, target)
            if changed or missing_required_file:
                changed_paths.append(self.write_translation_file(updated))
        return tuple(changed_paths)

    def _scaffold_fragmented_target(
        self,
        target: ModeloLocaleFileTarget,
        *,
        expected: _ExpectedKeysByTarget,
        valid: _ExpectedKeysByTarget,
    ) -> list[Path]:
        """Align one fragmented locale target, preserving translated leaves."""
        fragment_dir = self.resolve_target_path(target).with_suffix("")
        changed: list[Path] = []
        present: dict[ModeloLocaleFieldKind, set[str]] = {
            ModeloLocaleFieldKind.LABELS: set(),
            ModeloLocaleFieldKind.HELP: set(),
        }
        for path in sorted(fragment_dir.glob("*.toml")):
            current = self._load_translation_path(target, path)
            labels = {
                key: value
                for key, value in current.labels.items()
                if key in _keys_for_target(valid, target, ModeloLocaleFieldKind.LABELS)
            }
            help_text = {
                key: value
                for key, value in current.help.items()
                if key in _keys_for_target(valid, target, ModeloLocaleFieldKind.HELP)
            }
            present[ModeloLocaleFieldKind.LABELS].update(labels)
            present[ModeloLocaleFieldKind.HELP].update(help_text)
            if labels != current.labels or help_text != current.help:
                changed.append(self._write_translation_path(path, labels=labels, help_text=help_text))

        for field in (ModeloLocaleFieldKind.LABELS, ModeloLocaleFieldKind.HELP):
            missing = sorted(_keys_for_target(expected, target, field) - present[field])
            while missing:
                path = self._fragment_append_target(target, field)
                current = self._load_translation_path(target, path)
                table = dict(current.table(field))
                room = self.fragment_leaf_capacity - len(table)
                batch, missing = missing[:room], missing[room:]
                for key in batch:
                    table[key] = key
                labels = table if field is ModeloLocaleFieldKind.LABELS else dict(current.labels)
                help_text = table if field is ModeloLocaleFieldKind.HELP else dict(current.help)
                written = self._write_translation_path(path, labels=labels, help_text=help_text)
                if written not in changed:
                    changed.append(written)
        return changed

    def _fragment_append_target(self, target: ModeloLocaleFileTarget, field: ModeloLocaleFieldKind) -> Path:
        """Return the fragment file that accepts new ``field`` leaves for ``target``.

        The tail fragment of the field's family receives new keys until it
        reaches :attr:`fragment_leaf_capacity`; the next numbered fragment is
        created beyond that. A family with no fragment yet starts at the
        conventional first name.
        """
        fragment_dir = self.resolve_target_path(target).with_suffix("")
        family = [
            path
            for path in sorted(fragment_dir.glob("*.toml"))
            if (match := _FRAGMENT_NAME_PATTERN.match(path.name)) is not None and match.group("family") == field.value
        ]
        if not family:
            return fragment_dir / _FIRST_FRAGMENT_NAMES[field]
        tail = family[-1]
        if len(self._load_translation_path(target, tail).table(field)) < self.fragment_leaf_capacity:
            return tail
        tail_match = _FRAGMENT_NAME_PATTERN.match(tail.name)
        if tail_match is None:  # pragma: no cover - family membership guarantees a match
            raise ModeloLocaleError(f"Modelo locale fragment name is not numbered: {tail}")
        number = tail_match.group("num")
        return fragment_dir / f"{int(number) + 1:0{len(number)}d}-{field.value}.toml"

    def set_translation_value(
        self,
        locale: OutputLanguage | str,
        modelo_id: str,
        revision_id: str,
        field: ModeloLocaleFieldKind | str,
        key: str,
        value: str,
    ) -> Path:
        """Set one schema-local translated leaf after registry-key validation.

        A blank value is refused: an empty or whitespace-only leaf reads
        as present to a membership check while carrying nothing.
        """
        if not value.strip():
            raise ModeloLocaleError(f"Cannot set {key!r}: a modelo locale value must not be blank")
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
        matching_targets: list[ModeloLocaleFileTarget] = []
        for item in self.inventory_keys(modelo_id, revision_id):
            if item.field is not field or item.key != key:
                continue
            target = _target_for_inventory_key(item, locale=language)
            if target not in matching_targets:
                matching_targets.append(target)
        if not matching_targets:
            raise ModeloLocaleError(f"Modelo schema key not found: {field.value}/{key!r}")
        if len(matching_targets) > 1:
            raise ModeloLocaleError(f"Modelo schema key is ambiguous across scopes: {field.value}/{key!r}")
        return matching_targets[0]

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
        """Load a :class:`ModeloLocaleTranslationFile`, or return an empty file model."""
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
        """Return the concrete TOML file that owns ``field/key`` for ``target``.

        A schema key with no owning fragment routes to the field family's
        append fragment so that fragmented targets can accept new keys.
        """
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
        return self._fragment_append_target(target, field)

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
        """Atomically write one concrete schema-local locale TOML file.

        A concurrent reader must never observe a truncated or empty fragment
        mid-batch, so the rendered TOML is persisted through
        :func:`~cadrumo.core.atomic_write.atomic_write_text`.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path,
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


def _inventory_records(
    modelo: ModeloDefinition,
    revision_id: str | None,
) -> tuple[ModeloLocaleInventoryKey, ...]:
    """Return sorted inventory rows for an already-loaded modelo."""
    records: dict[tuple[ModeloLocaleScope, str | None, ModeloLocaleFieldKind, str], ModeloLocaleInventoryKey] = {}
    for revision in _selected_revisions(modelo, revision_id):
        for casilla in sorted(revision.casillas, key=lambda item: item.id):
            _add_revision_inventory(records, modelo_id=str(modelo.id), revision=revision, casilla=casilla)
            if casilla.continuidad_id is not None:
                _add_modelo_inventory(records, modelo_id=str(modelo.id), casilla=casilla)
    return tuple(
        records[key] for key in sorted(records, key=lambda item: (item[0].value, item[1] or "", item[2].value, item[3]))
    )


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
    """Preserve translated values, add placeholders, and drop stale keys.

    Refuses a silent mass-wipe. A partial registry load (a fingerprinting race
    against a concurrent registry edit) can hand this a ``valid_keys`` set that is
    missing keys ``expected_keys`` still lists; the filter below would then drop an
    authored value and the ``setdefault`` loop would re-add it as its own key,
    silently replacing a real translation with a key-echo placeholder. A key that
    is expected but not valid is an inventory inconsistency, so an *authored* value
    in that state raises rather than being wiped. A genuinely stale key -- absent
    from both sets -- is still dropped, as intended.
    """
    would_wipe = sorted(
        key for key, value in current.items() if value != key and key not in valid_keys and key in expected_keys
    )
    if would_wipe:
        raise ModeloLocaleError(
            f"Refusing to echo-convert {len(would_wipe)} authored modelo-locale value(s): "
            f"key(s) expected by the revision but absent from the modelo inventory, which "
            f"indicates a partial registry load (race), not a legitimate stale-key drop: "
            f"{would_wipe[:5]}",
        )
    aligned = {key: value for key, value in current.items() if key in valid_keys}
    for key in expected_keys:
        aligned.setdefault(key, key)
    return aligned


_FRAGMENT_NAME_PATTERN = re.compile(r"^(?P<num>\d+)-(?P<family>labels|help)\.toml$")
_FIRST_FRAGMENT_NAMES: dict[ModeloLocaleFieldKind, str] = {
    ModeloLocaleFieldKind.LABELS: "001-labels.toml",
    ModeloLocaleFieldKind.HELP: "101-help.toml",
}


def classify_modelo_locale_leaf(
    field: ModeloLocaleFieldKind,
    key: str,
    value: str | None,
    *,
    label_value: str | None = None,
    official_label: str | None = None,
) -> ModeloLocaleLeafState:
    """Classify one schema-local translation leaf into its honest state.

    Args:
        field: Translation table the leaf belongs to.
        key: Schema key the leaf translates.
        value: Stored value, or ``None`` when the leaf is missing.
        label_value: The same target's label value for ``key``, used to
            detect help that merely mirrors the label.
        official_label: The official Spanish schema label for ``key``.

    Comparison is whitespace-normalised so a stray space or trailing
    punctuation cannot smuggle a placeholder past the echo check, and an
    empty-after-strip value is its own never-authored state.

    Returns:
        Exactly one :class:`ModeloLocaleLeafState`; only ``AUTHORED`` may be
        counted as translated.
    """
    if value is None:
        return ModeloLocaleLeafState.ABSENT
    stripped = value.strip()
    if not stripped:
        return ModeloLocaleLeafState.BLANK
    if stripped == key or stripped.rstrip(".:").rstrip() == key:
        return ModeloLocaleLeafState.KEY_ECHO
    if field is ModeloLocaleFieldKind.HELP and stripped in {
        label_value.strip() if label_value is not None else None,
        official_label.strip() if official_label is not None else None,
    }:
        return ModeloLocaleLeafState.MIRRORED
    return ModeloLocaleLeafState.AUTHORED


def _official_labels_by_target(
    items: tuple[ModeloLocaleInventoryKey, ...],
    *,
    locale: OutputLanguage,
) -> dict[ModeloLocaleFileTarget, dict[str, str]]:
    """Group official Spanish schema labels by locale TOML target and key."""
    grouped: dict[ModeloLocaleFileTarget, dict[str, str]] = {}
    for item in items:
        target = _target_for_inventory_key(item, locale=locale)
        grouped.setdefault(target, {})[item.key] = item.official_label
    return grouped


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
    "ModeloLocaleLeafState",
    "ModeloLocaleManager",
    "ModeloLocaleScope",
    "ModeloLocaleTranslationFile",
    "classify_modelo_locale_leaf",
]

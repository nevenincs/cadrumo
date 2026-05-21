"""Validated access point for registry-backed modelo definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from ._errors import RegistrySnapshotError, RegistryValidationError
from ._loader import _collect_registry_tree_fingerprints, load_registry_tree
from ._schema import DeadlineWindowDefinition, ModeloDefinition, ModeloRevision, RegistryCatalogues, RegistrySnapshot
from ._snapshot import _build_validated_snapshot
from ._validate import RegistryValidator

_SnapshotKey = tuple[str, int, str, date | None, str | None]
_DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]


@dataclass(slots=True)
class ValidatedRegistryAuthority:
    """Load, validate, and cache registry material behind one access point."""

    root: Path
    source_root: Path
    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    _modelos_by_id: dict[str, ModeloDefinition]
    _validator: RegistryValidator
    _registry_validated: bool
    _validated_modelos: set[str]
    _snapshots: dict[_SnapshotKey, RegistrySnapshot]

    @classmethod
    def load(cls, root: Path, *, source_root: Path) -> ValidatedRegistryAuthority:
        """Load registry TOML and construct a reusable authority instance."""

        resolved_root = root.expanduser().resolve()
        return _load_authority(
            resolved_root,
            source_root.expanduser().resolve(),
            _collect_registry_tree_fingerprints(resolved_root),
        )

    def modelo(self, modelo_id: str) -> ModeloDefinition:
        """Return a modelo definition by id."""

        try:
            return self._modelos_by_id[modelo_id]
        except KeyError as exc:
            raise RegistrySnapshotError(f"modelo {modelo_id!r} is not present in the calculation registry") from exc

    def validate_modelo(self, modelo_id: str) -> ModeloDefinition:
        """Validate one modelo once and return its definition."""

        modelo = self.modelo(modelo_id)
        if not self._registry_validated and modelo_id not in self._validated_modelos:
            self._validator.validate_modelo(modelo)
            self._validated_modelos.add(modelo_id)
        return modelo

    def validate_registry(self) -> None:
        """Validate the full registry tree once."""

        if self._registry_validated:
            return
        self._validator.validate_registry(self.modelos)
        self._registry_validated = True
        self._validated_modelos.update(modelo.id for modelo in self.modelos)

    def snapshot(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: str | None = None,
    ) -> RegistrySnapshot:
        """Return a cached validated snapshot for one filing context."""

        key = (modelo_id, filing_year, period, on, revision_id)
        cached = self._snapshots.get(key)
        if cached is not None:
            return cached
        modelo = self.validate_modelo(modelo_id)
        snapshot = _build_validated_snapshot(
            modelo,
            self.catalogues,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
        )
        self._snapshots[key] = snapshot
        return snapshot

    def deadline_windows(
        self,
        year: int,
        *,
        modelos: tuple[str, ...] | None = None,
    ) -> tuple[_DeadlineWindow, ...]:
        """Return validated deadline windows registered for ``year``."""

        out: list[_DeadlineWindow] = []
        for modelo in self._selected_modelos(modelos):
            candidates = tuple(
                (revision, window)
                for revision in modelo.revisions.values()
                for window in revision.deadline_windows
                if window.filing_year == year
            )
            if not candidates:
                continue
            try:
                self.validate_modelo(modelo.id)
            except RegistryValidationError:
                raise
            for revision, window in candidates:
                out.append((modelo.id, revision, window))
        out.sort(key=lambda item: (item[2].closes_on, item[0], item[2].period))
        return tuple(out)

    def _selected_modelos(self, modelos: tuple[str, ...] | None) -> tuple[ModeloDefinition, ...]:
        if modelos is None:
            return self.modelos
        return tuple(self.modelo(modelo_id) for modelo_id in modelos)


@lru_cache(maxsize=16)
def _load_authority(
    root: Path,
    source_root: Path,
    _fingerprint: tuple[tuple[str, int, int], ...],
) -> ValidatedRegistryAuthority:
    del _fingerprint
    modelos, catalogues = load_registry_tree(root)
    return ValidatedRegistryAuthority(
        root=root,
        source_root=source_root,
        modelos=modelos,
        catalogues=catalogues,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        _validator=RegistryValidator(catalogues, source_root=source_root),
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
    )

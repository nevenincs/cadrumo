"""Validated access point for registry-backed modelo definitions.

:class:`ValidatedRegistryAuthority` is the production boundary for all registry
access. It loads TOML sources via the compiler in ``_loader``, compiles them
into :class:`ModeloDefinition` and :class:`ModeloRevision` objects, and
produces :class:`RegistrySnapshot` instances on demand for each filing context.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from ....core.access_gate import (
    AuthorizationManifest,
    ModeloAuthorization,
    derive_modelo_authorization,
    load_authorization_manifest,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.resources import bundled_path as _bundled_path
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._loader import _collect_registry_tree_fingerprints, load_registry_tree
from ._schema import DeadlineWindowDefinition, ModeloDefinition, ModeloRevision, RegistryCatalogues, RegistrySnapshot
from ._snapshot import _build_validated_snapshot
from ._validate import RegistryValidator

_SnapshotKey = tuple[str, int, str, date | None, str | None]
_DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]
_AUTHORITY_CACHE_SCHEMA_VERSION = "period-value-object-v1"


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
    _authorization_manifest: AuthorizationManifest

    @classmethod
    def load(cls, root: Path, *, source_root: Path) -> ValidatedRegistryAuthority:
        """Load registry TOML and construct a reusable :class:`ValidatedRegistryAuthority` instance."""
        resolved_root = root.expanduser().resolve()
        return _load_authority(
            resolved_root,
            source_root.expanduser().resolve(),
            _collect_registry_tree_fingerprints(resolved_root),
        )

    def modelo(self, modelo_id: str) -> ModeloDefinition:
        """Return a modelo definition by id.

        Returns:
            The :class:`ModeloDefinition` for ``modelo_id``.
        """
        try:
            return self._modelos_by_id[modelo_id]
        except KeyError as exc:
            raise RegistrySnapshotError(f"modelo {modelo_id!r} is not present in the calculation registry") from exc

    def validate_modelo(self, modelo_id: str) -> ModeloDefinition:
        """Validate one modelo once and return its definition.

        Returns:
            The validated :class:`ModeloDefinition` for ``modelo_id``.
        """
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

    @property
    def authorization_manifest(self) -> AuthorizationManifest:
        """Return the loaded multi-year-renta authorization manifest.

        The manifest is the single writable authorization surface; the CI
        meta-test reads it through this accessor to cross-check each
        enrolling claim against the recorder evidence.

        Returns:
            The loaded :class:`AuthorizationManifest` object.
        """
        return self._authorization_manifest

    def modelo_has_engine(self, modelo_id: str) -> bool:
        """Return whether ``modelo_id`` declares a calculation surface.

        A modelo "has an engine" when any of its revisions declares an
        application-link whose ``surface`` is ``"calculation"`` — the
        registry's own marker that a runtime calculation consumer is wired
        for the modelo. This drives the authorization gate's
        ADVISORY-vs-refusal split (an unauthorized modelo with an engine
        still computes with an advisory banner; one with no engine is
        refused at ``work create``). Returns ``False`` for an unknown
        modelo rather than raising, so the fleet-wide capability sweep can
        ask about every canonical modelo id including the engine-build
        modelos that do not load yet.
        """
        modelo = self._modelos_by_id.get(modelo_id)
        if modelo is None:
            return False
        return any(
            link.surface == "calculation"
            for revision in modelo.revisions.values()
            for link in revision.application_links
        )

    def authorization(self, modelo_id: str) -> ModeloAuthorization:
        """Return the derived per-modelo authorization capability.

        This is the layer-(b) derivation of the ``modelo-multiyear-renta``
        gate: the capability is *computed* from the manifest (layer a)
        cross-checked against the loaded registry — never an independently
        authored per-revision flag — so it cannot drift from the manifest.
        An unknown / not-yet-loadable modelo derives to ``UNAUTHORIZED``
        with ``has_engine = False``, which is the correct default for the
        engine-build modelos that carry no loadable definition yet.

        Returns:
            The derived :class:`ModeloAuthorization` for ``modelo_id``.
        """
        return derive_modelo_authorization(
            modelo_id,
            manifest=self._authorization_manifest,
            has_engine=self.modelo_has_engine(modelo_id),
        )

    def snapshot(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: str | None = None,
    ) -> RegistrySnapshot:
        """Return a cached validated :class:`RegistrySnapshot` for one filing context."""
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
        out.sort(
            key=lambda item: (
                item[2].closes_on,
                item[0],
                *_deadline_window_period_sort_key(item[2]),
            ),
        )
        return tuple(out)

    def _selected_modelos(self, modelos: tuple[str, ...] | None) -> tuple[ModeloDefinition, ...]:
        if modelos is None:
            return self.modelos
        return tuple(self.modelo(modelo_id) for modelo_id in modelos)


def _deadline_window_period_sort_key(window: DeadlineWindowDefinition) -> tuple[int, str]:
    return window.filing_year, window.period.registry_token


def bundled_authority() -> ValidatedRegistryAuthority:
    """Return an authority loaded from the package-bundled AEAT registry.

    Callers that always load the same default registry path use this
    instead of writing the bundled-path boilerplate inline.  The result
    is backed by :func:`_load_authority`'s LRU cache, so repeated calls
    within one process are free.

    Returns:
        A :class:`ValidatedRegistryAuthority` loaded from the bundled registry tree.
    """
    root = _bundled_path("registry", "aeat")
    return ValidatedRegistryAuthority.load(root, source_root=_bundled_path())


@lru_cache(maxsize=16)
def _load_authority(
    root: Path,
    source_root: Path,
    _fingerprint: tuple[tuple[str, int, int], ...],
) -> ValidatedRegistryAuthority:
    import hashlib
    import tempfile

    hasher = hashlib.sha256()
    hasher.update(_AUTHORITY_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(str(root.resolve()).encode("utf-8"))
    hasher.update(str(source_root.resolve()).encode("utf-8"))
    for item in _fingerprint:
        hasher.update(item[0].encode("utf-8"))
        hasher.update(str(item[1]).encode("utf-8"))
        hasher.update(str(item[2]).encode("utf-8"))
    val_key_hash = hasher.hexdigest()
    validated_cache_path = Path(tempfile.gettempdir()) / f"aeat_registry_{val_key_hash}_validated.tmp"

    modelos, catalogues = load_registry_tree(root)

    if validated_cache_path.is_file():
        authority = ValidatedRegistryAuthority(
            root=root,
            source_root=source_root,
            modelos=modelos,
            catalogues=catalogues,
            _modelos_by_id={modelo.id: modelo for modelo in modelos},
            _validator=RegistryValidator(catalogues, source_root=source_root, catalogue_corpus_strict=False),
            _registry_validated=True,
            _validated_modelos={modelo.id for modelo in modelos},
            _snapshots={},
            _authorization_manifest=load_authorization_manifest(root),
        )
        return authority

    authority = ValidatedRegistryAuthority(
        root=root,
        source_root=source_root,
        modelos=modelos,
        catalogues=catalogues,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        # Production authority skips required_text corpus checks so that
        # a pending corpus annotation never aborts a user-facing workflow
        # (bindings list, work calculate, etc.).  Strict corpus checks are
        # performed by verify_registry_tree via a dedicated strict validator.
        _validator=RegistryValidator(catalogues, source_root=source_root, catalogue_corpus_strict=False),
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
        # Authorization is derived at this boundary from the manifest
        # (default-deny-by-absence: an absent manifest authorizes nothing).
        # The manifest is fingerprinted into _collect_registry_tree_fingerprints
        # so this lru_cache invalidates when the manifest changes on disk.
        _authorization_manifest=load_authorization_manifest(root),
    )
    authority.validate_registry()
    with suppress(Exception):
        validated_cache_path.write_text("validated", encoding=UTF_8_ENCODING)
    return authority

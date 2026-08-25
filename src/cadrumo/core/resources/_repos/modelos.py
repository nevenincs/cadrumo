"""StaticModeloRepository: thin façade over ValidatedRegistryAuthority.

The modelos repository is the only one that backs onto an
aggregate (:class:`ValidatedRegistryAuthority`) rather than a direct
loader. The authority owns the validator + snapshot caches that
the test suite already relies on; the Repository preserves
those caches by holding a reference to the authority instance
and delegating ``get`` / ``all`` through it. Both return
:class:`ModeloDefinition` records resolved from the authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from ..errors import ResourceNotFoundError
from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.calculations.registry import ModeloDefinition, ValidatedRegistryAuthority


class StaticModeloRepository(ResourceCacheRepository["ModeloDefinition", str]):
    """Modelo definitions keyed by their typed id (``"100"``, ``"180"``, …).

    Wraps :class:`cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`.
    The authority is constructed lazily on first ``get`` so the
    bundled registry only loads when actually needed.
    """

    def __init__(self, root: Path | None = None, source_root: Path | None = None) -> None:
        super().__init__()
        self._root = root
        self._source_root = source_root
        self._authority: ValidatedRegistryAuthority | None = None

    def _resolve_authority(self) -> ValidatedRegistryAuthority:
        if self._authority is not None:
            return self._authority
        from ....domain.calculations.registry import (
            ValidatedRegistryAuthority as _ValidatedRegistryAuthority,
        )
        from .._boundary import bundled_path

        root = self._root or bundled_path("registry", "aeat")
        source_root = self._source_root or bundled_path()
        self._authority = _ValidatedRegistryAuthority.load(root, source_root=source_root)
        return self._authority

    @property
    def authority(self) -> ValidatedRegistryAuthority:
        """Return the backing :class:`ValidatedRegistryAuthority` instance."""
        return self._resolve_authority()

    @override
    def _load(self, key: str) -> ModeloDefinition:
        from ....domain.calculations.registry import RegistrySnapshotError

        authority = self._resolve_authority()
        try:
            return authority.modelo(key)
        except RegistrySnapshotError as exc:
            raise ResourceNotFoundError(f"no modelo definition registered for {key!r}") from exc

    @override
    def all(self) -> tuple[ModeloDefinition, ...]:
        """Return every modelo definition in the bundled registry.

        Returns:
            A tuple of every :class:`ModeloDefinition` known to the
            backing authority.
        """
        authority = self._resolve_authority()
        return tuple(authority.modelos)

    @override
    def clear_cache(self) -> None:
        """Clear the Identity Map AND the backing authority reference."""
        super().clear_cache()
        self._authority = None

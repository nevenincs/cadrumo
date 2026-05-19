"""LegalParameterRepository: singleton legal-parameter catalogue."""

from __future__ import annotations

from .._repository import Repository


class LegalParameterRepository(Repository[object, type(None)]):
    """Singleton-keyed repository for the registry-wide legal parameters.

    Wraps :func:`aeat.domain.calculations.registry.load_legal_parameters_only`
    rooted at the bundled registry tree.
    """

    def _load(self, key: None) -> object:
        from ....domain.calculations.registry import load_legal_parameters_only
        from .._boundary import bundled_path

        return load_legal_parameters_only(bundled_path("registry", "aeat"))

    @property
    def singleton(self) -> object:
        return self.get(None)

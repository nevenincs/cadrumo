"""Fail-fast validation for registry definitions.

Validates :class:`ModeloDefinition` instances and their constituent
:class:`ModeloRevision` records against the legal and source catalogues.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ._corpus_catalogue import verify_source_catalogue
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._validate_cache import (
    CATALOGUE_FAILURE_CACHE,
    MODELO_VALIDATION_CACHE,
    REGISTRY_VALIDATION_CACHE,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import _missing_refs
from ._validate_registry_scope import validate_registry_scope
from ._validate_revision_rules import (
    validate_informative_class_invariant,
    validate_revision_windows,
)
from ._validate_revision_sections import validate_revision_definition

if TYPE_CHECKING:
    from ...user_profile._schema import ProfileSchemaDefinition


class RegistryValidator:
    """Validate legal/source closure and calculability for modelos."""

    def __init__(
        self,
        catalogues: RegistryCatalogues,
        *,
        source_root: Path | None = None,
        justificante_corpus_root: Path | None = None,
        user_profile_schema: ProfileSchemaDefinition | None = None,
    ) -> None:
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._source_root = source_root
        self._user_profile_schema = user_profile_schema
        self._evidence = EvidenceValidator(
            legal_refs=self._legal,
            source_refs=self._sources,
            source_root=self._source_root,
        )
        self._catalogue_failures: tuple[str, ...] | None = None
        # Corpus root for declaracion_pdf specimen gate:
        # caller may supply it directly; when not supplied, derive from
        # source_root by navigating to the co-located tests/fixtures/justificantes
        # directory.  Production callers pass source_root=bundled_path() which
        # resolves to src/aeat/_data, so parents[0] = src/aeat, and the corpus
        # lives at src/aeat/tests/fixtures/justificantes.
        if justificante_corpus_root is not None:
            self._justificante_corpus_root: Path | None = justificante_corpus_root
        elif source_root is not None:
            candidate = source_root.resolve().parents[0] / "tests" / "fixtures" / "justificantes"
            self._justificante_corpus_root = candidate if candidate.is_dir() else None
        else:
            self._justificante_corpus_root = None

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
        failures = self._cached_modelo_failures(modelo)
        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

    @property
    def justificante_corpus_root(self) -> Path | None:
        return self._justificante_corpus_root

    def _source_root_key(self) -> str | None:
        return str(self._source_root.expanduser().resolve()) if self._source_root is not None else None

    def _corpus_root_key(self) -> str | None:
        return (
            str(self._justificante_corpus_root.expanduser().resolve())
            if self._justificante_corpus_root is not None
            else None
        )

    def _cached_modelo_failures(self, modelo: ModeloDefinition) -> tuple[str, ...]:
        cache_key = (
            id(modelo),
            id(self._legal),
            id(self._sources),
            self._source_root_key(),
            self._corpus_root_key(),
        )
        cached = MODELO_VALIDATION_CACHE.get(cache_key)
        if cached is not None and cached[0] is modelo and cached[1] is self._legal and cached[2] is self._sources:
            return cached[3]
        failures = tuple(self._validate_modelo(modelo, validate_catalogues=True))
        MODELO_VALIDATION_CACHE[cache_key] = (modelo, self._legal, self._sources, failures)
        return failures

    def _validate_catalogues(self) -> tuple[str, ...]:
        if self._catalogue_failures is not None:
            return self._catalogue_failures
        source_root_key = self._source_root_key()
        cache_key = (id(self._legal), id(self._sources), source_root_key)
        cached = CATALOGUE_FAILURE_CACHE.get(cache_key)
        if cached is not None and cached[0] is self._legal and cached[1] is self._sources:
            self._catalogue_failures = cached[2]
            return self._catalogue_failures

        failures: list[str] = []
        try:
            verify_legal_catalogue(
                self._legal,
                source_root=self._source_root,
            )
        except RegistryValidationError as exc:
            failures.append(str(exc))
        if self._source_root is not None:
            try:
                verify_source_catalogue(self._source_root, self._sources)
            except RegistryValidationError as exc:
                failures.append(str(exc))
        self._catalogue_failures = tuple(failures)
        CATALOGUE_FAILURE_CACHE[cache_key] = (self._legal, self._sources, self._catalogue_failures)
        return self._catalogue_failures

    def _validate_modelo(self, modelo: ModeloDefinition, *, validate_catalogues: bool) -> list[str]:
        failures: list[str] = []
        if validate_catalogues:
            failures.extend(self._validate_catalogues())
        failures.extend(_missing_refs("modelo", modelo.id, modelo.legal_refs, self._legal, "legal"))
        failures.extend(_missing_refs("modelo", modelo.id, modelo.source_refs, self._sources, "source"))
        for revision in modelo.revisions.values():
            failures.extend(self._validate_revision(modelo, revision))
        failures.extend(self._validate_user_profile_contract((modelo,)))
        failures.extend(validate_revision_windows(modelo))
        failures.extend(validate_informative_class_invariant(modelo))
        return failures

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph.

        Args:
            modelos: Iterable of :class:`ModeloDefinition` instances to validate.
        """
        modelo_tuple = tuple(modelos)
        cache_key = (
            tuple(id(modelo) for modelo in modelo_tuple),
            id(self._legal),
            id(self._sources),
            self._source_root_key(),
            self._corpus_root_key(),
        )
        cached = REGISTRY_VALIDATION_CACHE.get(cache_key)
        if cached is not None and cached[0] == modelo_tuple and cached[1] is self._legal and cached[2] is self._sources:
            if cached[3]:
                raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in cached[3]))
            return

        failures: list[str] = list(self._validate_catalogues())
        for modelo in modelo_tuple:
            failures.extend(self._validate_modelo(modelo, validate_catalogues=False))

        failures.extend(validate_registry_scope(modelo_tuple))

        if failures:
            REGISTRY_VALIDATION_CACHE[cache_key] = (modelo_tuple, self._legal, self._sources, tuple(failures))
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))
        REGISTRY_VALIDATION_CACHE[cache_key] = (modelo_tuple, self._legal, self._sources, ())

    def _validate_user_profile_contract(self, modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
        from ...user_profile._loader import load_user_profile_schema
        from ...user_profile._registry_contract import validate_user_profile_registry_contract

        schema = self._user_profile_schema or load_user_profile_schema()
        report = validate_user_profile_registry_contract(modelos, schema)
        return tuple(
            f"modelo {issue.modelo_id} revision {issue.revision_id}: user-profile schema {schema.id} "
            f"{issue.surface} {issue.construct_id!r} selector {issue.selector!r}: {issue.message}"
            for issue in report.errors
        )

    def _validate_revision(self, modelo: ModeloDefinition, revision: ModeloRevision) -> list[str]:
        return validate_revision_definition(
            modelo,
            revision,
            legal_refs=self._legal,
            source_refs=self._sources,
            evidence=self._evidence,
            justificante_corpus_root=self._justificante_corpus_root,
        )

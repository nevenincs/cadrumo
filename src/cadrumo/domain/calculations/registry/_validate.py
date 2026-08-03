"""Fail-fast validation for registry definitions.

Validates :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
instances and their constituent
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` records against the
legal and source catalogues.

The validator owns catalogue checks,
:class:`~cadrumo.domain.calculations.registry._validate_evidence.EvidenceValidator`
source-tier checks, per-revision dispatch through
:func:`cadrumo.domain.calculations.registry._validate_revision_sections.validate_revision_definition`,
and cross-model scope validation.

See Also:
    :class:`cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`
        Production authority that loads registry material before validation.
    :func:`cadrumo.domain.calculations.registry._validate_registry_scope.validate_registry_scope`
        Cross-model relation and registry-scope validation invoked here.
    :mod:`cadrumo.domain.calculations.registry._validate_cache`
        Identity-keyed failure caches used by this validator.
    :func:`cadrumo.domain.calculations.registry._source_evidence_fingerprint.derive_justificante_corpus_candidate`
        Checkout-gated derivation of the dev-only declaracion_pdf specimen
        corpus; :attr:`RegistryValidator.justificante_corpus_unavailable_advisory`
        surfaces a non-blocking, introspectable signal when it fails.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.paths import StateRootInputs
from ._corpus_catalogue import verify_source_catalogue
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._source_evidence_fingerprint import (
    JustificanteCorpusUnavailableAdvisory,
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
    derive_justificante_corpus_candidate,
)
from ._validate_cache import (
    CATALOGUE_FAILURE_CACHE,
    MODELO_VALIDATION_CACHE,
    REGISTRY_VALIDATION_CACHE,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_registry_scope import validate_registry_scope
from ._validate_revision_rules import (
    validate_informative_class_invariant,
    validate_m210_tipo_renta_code_projection_parity,
    validate_revision_windows,
)
from ._validate_revision_sections import validate_revision_definition

if TYPE_CHECKING:
    from ...user_profile import ProfileSchemaDefinition

_MODELO_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


class RegistryValidator:
    """Validate legal/source closure and calculability for registry modelos.

    The validator accepts
    :class:`~cadrumo.domain.calculations.registry.RegistryCatalogues`, checks each
    :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`, and delegates
    each :class:`~cadrumo.domain.calculations.registry.ModeloRevision` to the
    section-level dispatcher.
    """

    def __init__(
        self,
        catalogues: RegistryCatalogues,
        *,
        source_root: Path | None = None,
        justificante_corpus_root: Path | None = None,
        user_profile_schema: ProfileSchemaDefinition | None = None,
        source_evidence_fingerprint: SourceEvidenceFingerprint | None = None,
        state_root_inputs: StateRootInputs | None = None,
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
        # Corpus root for declaracion_pdf specimen gate: caller may supply it
        # directly (an explicit opt-out of derivation, never a silent gap); when
        # not supplied, derive_justificante_corpus_candidate() resolves it from
        # source_root, gated on RunMode.CHECKOUT so an installed distribution
        # (which ships no tests/ tree) never blindly probes a repo-shaped path.
        # A failed derivation is captured as a non-blocking, introspectable
        # advisory rather than an unexplained None; see
        # justificante_corpus_unavailable_advisory.
        self._justificante_corpus_unavailable_advisory: JustificanteCorpusUnavailableAdvisory | None = None
        if justificante_corpus_root is not None:
            self._justificante_corpus_root: Path | None = justificante_corpus_root
        elif source_root is not None:
            self._justificante_corpus_root, self._justificante_corpus_unavailable_advisory = (
                derive_justificante_corpus_candidate(source_root, state_root_inputs=state_root_inputs)
            )
        else:
            self._justificante_corpus_root = None
        self._source_evidence_fingerprint = (
            source_evidence_fingerprint
            if source_evidence_fingerprint is not None
            else collect_source_evidence_fingerprints(
                self._source_root,
                justificante_corpus_root=self._justificante_corpus_root,
                state_root_inputs=state_root_inputs,
            )
        )

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
        """Validate one modelo definition and raise on accumulated failures.

        Args:
            modelo: The
                :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
                whose catalogue refs, revisions, user-profile contract, and
                revision windows are validated.
        """
        failures = self._cached_modelo_failures(modelo)
        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

    @property
    def justificante_corpus_root(self) -> Path | None:
        return self._justificante_corpus_root

    @property
    def justificante_corpus_unavailable_advisory(self) -> JustificanteCorpusUnavailableAdvisory | None:
        """Return why the declaracion_pdf specimen corpus could not be derived, if it could not.

        ``None`` means either a corpus root was resolved (the specimen and
        round-trip gates in ``_validate_extraction_profiles`` ran for this
        validation pass) or the caller explicitly injected
        ``justificante_corpus_root`` at construction (an explicit opt-out, not a
        silent gap). A non-``None`` value means derivation was attempted and
        failed — the gates did not run — and carries the reason so a caller can
        surface it through its own operator-facing diagnostic channel; this
        validator does not raise for the condition itself.
        """
        return self._justificante_corpus_unavailable_advisory

    def _source_root_key(self) -> str | None:
        return str(self._source_root.expanduser().resolve()) if self._source_root is not None else None

    def _corpus_root_key(self) -> str | None:
        return (
            str(self._justificante_corpus_root.expanduser().resolve())
            if self._justificante_corpus_root is not None
            else None
        )

    def _source_evidence_key(self) -> SourceEvidenceFingerprint:
        return self._source_evidence_fingerprint

    def _cached_modelo_failures(self, modelo: ModeloDefinition) -> tuple[str, ...]:
        cache_key = (
            id(modelo),
            id(self._legal),
            id(self._sources),
            self._source_root_key(),
            self._corpus_root_key(),
            self._source_evidence_key(),
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
        cache_key = (id(self._legal), id(self._sources), source_root_key, self._source_evidence_key())
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
        failures.extend(
            self._evidence.require_any_source_tier("modelo", modelo.id, modelo.source_refs, _MODELO_SOURCE_TIERS)
        )
        for revision in modelo.revisions.values():
            failures.extend(self._validate_revision(modelo, revision))
        failures.extend(self._validate_user_profile_contract((modelo,)))
        failures.extend(validate_revision_windows(modelo))
        failures.extend(validate_informative_class_invariant(modelo))
        failures.extend(validate_m210_tipo_renta_code_projection_parity(modelo))
        return failures

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph.

        Args:
            modelos: Iterable of
                :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
                instances to validate together before
                :func:`cadrumo.domain.calculations.registry._validate_registry_scope.validate_registry_scope`
                checks cross-model closure.
        """
        modelo_tuple = tuple(modelos)
        cache_key = (
            tuple(id(modelo) for modelo in modelo_tuple),
            id(self._legal),
            id(self._sources),
            self._source_root_key(),
            self._corpus_root_key(),
            self._source_evidence_key(),
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
        from ...user_profile import load_user_profile_schema, validate_user_profile_registry_contract

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

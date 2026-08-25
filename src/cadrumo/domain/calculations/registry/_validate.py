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
    :mod:`cadrumo.domain.calculations.registry._validation_memoization`
        Identity-keyed failure caches used by this validator.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ._corpus_catalogue import verify_source_catalogue
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue_grounding
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_layout_authority_content import validate_layout_authority_content
from ._validate_official_source_guidance_content import validate_suppression_notice_content
from ._validate_producer_inventory import validate_producer_inventory
from ._validate_record_design_epochs import (
    validate_record_design_epoch_uniqueness,
    validate_record_design_epoch_window,
)
from ._validate_registry_scope import validate_registry_scope
from ._validate_revision_rules import (
    validate_deadline_window_cadence,
    validate_deadline_window_ownership,
    validate_deadline_window_uniqueness,
    validate_informative_class_invariant,
    validate_m210_tipo_renta_code_projection_parity,
    validate_periodic_deadline_completeness,
    validate_revision_windows,
)
from ._validate_revision_sections import validate_revision_definition
from ._validation_memoization import (
    CATALOGUE_FAILURE_CACHE,
    MODELO_VALIDATION_CACHE,
    REGISTRY_VALIDATION_CACHE,
)

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
    ) -> None:
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._supported_filing_years = (
            () if catalogues.supported_filing_years is None else catalogues.supported_filing_years.years
        )
        self._source_root = source_root
        self._user_profile_schema = user_profile_schema
        self._evidence = EvidenceValidator(
            legal_refs=self._legal,
            source_refs=self._sources,
            source_root=self._source_root,
        )
        self._catalogue_failures: tuple[str, ...] | None = None
        # Corpus root for the declaracion_pdf specimen gate: SUPPLIED, never
        # derived. The specimen corpus is a checkout-time authoring input, so
        # the authoring tool that owns it passes its location in. Production
        # does not go looking: deriving it meant probing a repo-shaped path,
        # which required asking whether this process runs from a source
        # checkout -- a question a tax-filing product has no business asking.
        # Unsupplied means the gate does not run, which is the correct and only
        # outcome for every installed run.
        self._justificante_corpus_root: Path | None = justificante_corpus_root
        self._source_evidence_fingerprint = (
            source_evidence_fingerprint
            if source_evidence_fingerprint is not None
            else collect_source_evidence_fingerprints(
                self._source_root,
                justificante_corpus_root=self._justificante_corpus_root,
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
            self._supported_filing_years,
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
            verify_legal_catalogue_grounding(
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
        # Deliberately NOT behind the source-root guard above: epoch uniqueness is a
        # property of the declarations themselves, so it holds whether or not the
        # bundled files are reachable for hashing. Gating it on the root would make
        # the check disappear in exactly the configurations that skip file
        # verification.
        failures.extend(validate_record_design_epoch_uniqueness(self._sources))
        failures.extend(validate_record_design_epoch_window(self._sources))
        # Accumulating rather than raising through verify_source_catalogue: that
        # path stops at the first bad source and dedupes by file, so a cohort of
        # unbacked claims would surface as one message naming one of them. Each
        # claim is its own declaration and each is named.
        failures.extend(validate_layout_authority_content(self._sources, source_root=self._source_root))
        failures.extend(validate_suppression_notice_content(self._sources, source_root=self._source_root))
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
        failures.extend(validate_deadline_window_ownership(modelo))
        failures.extend(validate_deadline_window_cadence(modelo))
        failures.extend(validate_deadline_window_uniqueness(modelo))
        failures.extend(
            validate_periodic_deadline_completeness(
                modelo,
                supported_filing_years=self._supported_filing_years,
            ),
        )
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
            self._supported_filing_years,
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
        from ...user_profile.loader import load_user_profile_schema
        from ...user_profile.registry_contract import validate_user_profile_registry_contract

        schema = self._user_profile_schema or load_user_profile_schema()
        report = validate_user_profile_registry_contract(modelos, schema)
        return tuple(
            f"modelo {issue.modelo_id} revision {issue.revision_id}: user-profile schema {schema.id} "
            f"{issue.surface} {issue.construct_id!r} selector {issue.selector!r}: {issue.message}"
            for issue in report.errors
        )

    def _validate_revision(self, modelo: ModeloDefinition, revision: ModeloRevision) -> list[str]:
        prefix = f"modelo {modelo.id} revision {revision.id}"
        failures = validate_revision_definition(
            modelo,
            revision,
            legal_refs=self._legal,
            source_refs=self._sources,
            evidence=self._evidence,
            source_root=self._source_root,
            justificante_corpus_root=self._justificante_corpus_root,
        )
        for failure in validate_producer_inventory(prefix, revision):
            if failure not in failures:
                failures.append(failure)
        return failures

"""Fail-fast validation for registry definitions.

Validates :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
instances and their constituent
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` records against the
legal and source catalogues.

The validator owns catalogue checks,
:class:`~cadrumo.domain.calculations.registry.validate_evidence.EvidenceValidator`
source-tier checks, per-revision dispatch through
:func:`cadrumo.domain.calculations.registry.validate_revision_sections.validate_revision_definition`,
and cross-model scope validation.

See Also:
    :class:`cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`
        Production authority that loads registry material before validation.
    :func:`cadrumo.domain.calculations.registry.validate_registry_scope.validate_registry_scope`
        Cross-model relation and registry-scope validation invoked here.
    :mod:`dev.registry.compiler.validation_memoization`
        Identity-keyed failure caches used by this validator.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.invoice_bindings import InvoiceProviderBase
from cadrumo.domain.calculations.registry.ledger_iva_bindings import ledger_iva_revision_vocabulary_failures
from cadrumo.domain.calculations.registry.ledger_oss_bindings import ledger_oss_revision_vocabulary_failures
from cadrumo.domain.calculations.registry.m347_threshold import resolve_counterpart_operation_claves
from cadrumo.domain.calculations.registry.runtime_catalogues import RuntimeRegistryCatalogues
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import REGISTRY_SOURCE_GROUNDING_TIERS
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

from .corpus_catalogue import (
    compile_record_design_manifest_catalogue,
    verify_catalogue_identity_bindings,
    verify_manual_annotation_catalogue,
    verify_source_catalogue,
)
from .fact_validation import (
    governed_fact_catalogue_failures,
    iva_binding_cash_accounting_vocabulary_failures,
    retired_fact_provider_closure_failures,
)
from .legal_grounding import legal_reference_quotes_corpus, verify_legal_catalogue_grounding
from .registry_scope import validate_registry_scope
from .source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)
from .validate_evidence import EvidenceValidator, flush_corpus_text_cache
from .validate_form_geometry import validate_form_geometry
from .validate_helpers import missing_refs
from .validate_household_row_owners import validate_household_row_owners
from .validate_inherited_family_pairing import inherited_family_pairing_failures
from .validate_layout_authority_content import validate_layout_authority_content
from .validate_official_source_guidance_content import validate_suppression_notice_content
from .validate_producer_inventory import validate_producer_inventory
from .validate_record_design_epochs import (
    validate_record_design_epoch_uniqueness,
    validate_record_design_epoch_window,
)
from .validate_revision_rules import (
    validate_deadline_window_cadence,
    validate_deadline_window_ownership,
    validate_deadline_window_uniqueness,
    validate_informative_class_invariant,
    validate_m210_tipo_renta_code_projection_parity,
    validate_periodic_deadline_completeness,
    validate_revision_windows,
)
from .validate_revision_sections import validate_revision_definition
from .validation_memoization import (
    CATALOGUE_FAILURE_CACHE,
    MODELO_VALIDATION_CACHE,
    REGISTRY_VALIDATION_CACHE,
)
from .validation_verdict_cache import ValidationVerdictScope, is_validated, record_validated

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.facts.variants import GovernedFactVariant
    from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition


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
        verdicts: ValidationVerdictScope | None = None,
    ) -> None:
        """Bind the catalogues and optional evidence roots the checks read.

        Args:
            catalogues: Compiled registry catalogues every modelo is checked against.
            source_root: Source-material root for evidence checks; unsupplied skips them.
            justificante_corpus_root: Specimen corpus root for the declaracion PDF gate.
            user_profile_schema: Profile schema used to close profile-sourced bindings.
            source_evidence_fingerprint: Precomputed evidence fingerprint for memoization.
            verdicts: Recorded clean per-modelo validations this run may reuse and extend.
        """
        self._verdicts = verdicts
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._facts = catalogues.facts
        self._runtime = catalogues.runtime
        self._support = catalogues.supported_filing_years
        self._supported_filing_years = () if self._support is None else self._support.years
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
                justificante_corpus_root=self.justificante_corpus_root,
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
        """Return the explicitly supplied authoring corpus root."""
        return self._justificante_corpus_root

    def _source_root_key(self) -> str | None:
        return str(self._source_root.expanduser().resolve()) if self._source_root is not None else None

    def _corpus_root_key(self) -> str | None:
        return (
            str(self.justificante_corpus_root.expanduser().resolve())
            if self.justificante_corpus_root is not None
            else None
        )

    def _source_evidence_key(self) -> SourceEvidenceFingerprint:
        return self._source_evidence_fingerprint

    def _cached_modelo_failures(self, modelo: ModeloDefinition) -> tuple[str, ...]:
        cache_key = (
            id(modelo),
            id(self._legal),
            id(self._sources),
            id(self._facts),
            id(self._runtime),
            self._supported_filing_years,
            self._source_root_key(),
            self._corpus_root_key(),
            self._source_evidence_key(),
        )
        cached = MODELO_VALIDATION_CACHE.get(cache_key)
        if (
            cached is not None
            and cached[0] is modelo
            and cached[1] is self._legal
            and cached[2] is self._sources
            and cached[3] is self._facts
            and cached[4] is self._runtime
        ):
            return cached[5]
        failures = tuple(self._validate_modelo(modelo, validate_catalogues=True))
        MODELO_VALIDATION_CACHE[cache_key] = (
            modelo,
            self._legal,
            self._sources,
            self._facts,
            self._runtime,
            failures,
        )
        return failures

    def _validate_catalogues(self) -> tuple[str, ...]:
        if self._catalogue_failures is not None:
            return self._catalogue_failures
        source_root_key = self._source_root_key()
        cache_key = (
            id(self._legal),
            id(self._sources),
            id(self._facts),
            id(self._runtime),
            source_root_key,
            self._source_evidence_key(),
        )
        cached = CATALOGUE_FAILURE_CACHE.get(cache_key)
        if (
            cached is not None
            and cached[0] is self._legal
            and cached[1] is self._sources
            and cached[2] is self._facts
            and cached[3] is self._runtime
        ):
            self._catalogue_failures = cached[4]
            return self._catalogue_failures

        failures = self._runtime_catalogue_failures()
        if self._source_root is not None:
            failures.extend(self._source_root_catalogue_failures())
        # Deliberately NOT behind the source-root guard above: epoch uniqueness is a
        # property of the declarations themselves, so it holds whether or not the
        # bundled files are reachable for hashing. Gating it on the root would make
        # the check disappear in exactly the configurations that skip file
        # verification.
        failures.extend(self._declared_catalogue_failures())
        self._catalogue_failures = tuple(failures)
        CATALOGUE_FAILURE_CACHE[cache_key] = (
            self._legal,
            self._sources,
            self._facts,
            self._runtime,
            self._catalogue_failures,
        )
        return self._catalogue_failures

    def _runtime_catalogue_failures(self) -> list[str]:
        return missing_refs(
            "runtime catalogues",
            "published authority",
            runtime_legal_reference_ids(self._runtime),
            self._legal,
            "legal",
        )

    def _source_root_catalogue_failures(self) -> list[str]:
        source_root = self._source_root
        if source_root is None:
            return []
        failures: list[str] = []
        failures.extend(self._runtime_citation_grounding_failures(source_root))
        try:
            verify_legal_catalogue_grounding(self._legal, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
        try:
            manifest_catalogue = compile_record_design_manifest_catalogue(source_root, self._sources)
            if manifest_catalogue is not None:
                catalogue, record_design_sources = manifest_catalogue
                verify_catalogue_identity_bindings(catalogue, record_design_sources)
            verify_source_catalogue(source_root, self._sources)
            verify_manual_annotation_catalogue(source_root, self._sources)
        except RegistryValidationError as exc:
            failures.append(str(exc))
        return failures

    def _runtime_citation_grounding_failures(self, source_root: Path) -> list[str]:
        failures: list[str] = []
        for category, regulation in self._runtime.iva_regulations.items():
            for citation in regulation.citations:
                if citation.grounding != "verified":
                    continue
                reference = self._legal.get(citation.legal_reference)
                if reference is None:
                    continue
                if not legal_reference_quotes_corpus(
                    reference,
                    citation.quoted_text,
                    source_root=source_root,
                ):
                    failures.append(
                        f"runtime IVA regulation {category!r} citation {citation.legal_reference!r} "
                        "claims verified grounding, but its quotation does not occur in the anchored corpus text"
                    )
        return failures

    def _declared_catalogue_failures(self) -> list[str]:
        failures: list[str] = []
        failures.extend(validate_record_design_epoch_uniqueness(self._sources))
        failures.extend(validate_record_design_epoch_window(self._sources))
        # Accumulating rather than raising through verify_source_catalogue: that
        # path stops at the first bad source and dedupes by file, so a cohort of
        # unbacked claims would surface as one message naming one of them. Each
        # claim is its own declaration and each is named.
        failures.extend(validate_layout_authority_content(self._sources, source_root=self._source_root))
        failures.extend(validate_suppression_notice_content(self._sources, source_root=self._source_root))
        failures.extend(
            governed_fact_catalogue_failures(
                self._facts,
                legal_ref_ids=self._legal,
                source_ref_ids=self._sources,
                legal_refs=self._legal,
                source_refs=self._sources,
                source_root=self._source_root,
            ),
        )
        failures.extend(retired_fact_provider_closure_failures(self._facts, source_refs=self._sources))
        return failures

    def _validate_modelo(self, modelo: ModeloDefinition, *, validate_catalogues: bool) -> list[str]:
        failures: list[str] = []
        if validate_catalogues:
            failures.extend(self._validate_catalogues())
        failures.extend(iva_binding_cash_accounting_vocabulary_failures(modelo, self._facts))
        failures.extend(missing_refs("modelo", modelo.id, modelo.legal_refs, self._legal, "legal"))
        failures.extend(missing_refs("modelo", modelo.id, modelo.source_refs, self._sources, "source"))
        failures.extend(
            self._evidence.require_any_source_tier(
                "modelo", modelo.id, modelo.source_refs, REGISTRY_SOURCE_GROUNDING_TIERS
            )
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
        failures.extend(inherited_family_pairing_failures(modelo))
        return failures

    def _registry_cache_key(
        self,
        modelo_tuple: tuple[ModeloDefinition, ...],
    ) -> tuple[tuple[int, ...], int, int, int, int, tuple[int, ...], str | None, str | None, SourceEvidenceFingerprint]:
        """Build the identity and environment key for a registry validation."""
        return (
            tuple(id(modelo) for modelo in modelo_tuple),
            id(self._legal),
            id(self._sources),
            id(self._facts),
            id(self._runtime),
            self._supported_filing_years,
            self._source_root_key(),
            self._corpus_root_key(),
            self._source_evidence_key(),
        )

    def _cached_registry_failures(
        self,
        modelo_tuple: tuple[ModeloDefinition, ...],
        cache_key: tuple[
            tuple[int, ...], int, int, int, int, tuple[int, ...], str | None, str | None, SourceEvidenceFingerprint
        ],
    ) -> tuple[str, ...] | None:
        """Return a cache hit only when both tuple and catalogue identities still match."""
        cached = REGISTRY_VALIDATION_CACHE.get(cache_key)
        if (
            cached is None
            or cached[0] != modelo_tuple
            or cached[1] is not self._legal
            or cached[2] is not self._sources
            or cached[3] is not self._facts
            or cached[4] is not self._runtime
        ):
            return None
        return cached[5]

    def _validate_registry_modelos(self, modelo_tuple: tuple[ModeloDefinition, ...]) -> list[str]:
        """Run catalogue and per-model checks in their established order."""
        failures: list[str] = list(self._validate_catalogues())
        for modelo in modelo_tuple:
            key = None if self._verdicts is None else self._verdicts.modelo_key(str(modelo.id))
            if key is not None and is_validated(key):
                continue
            modelo_failures = self._validate_modelo(modelo, validate_catalogues=False)
            failures.extend(modelo_failures)
            if key is not None and not modelo_failures:
                record_validated(key, subject=f"modelo {modelo.id}")
        return failures

    def _cache_registry_failures(
        self,
        cache_key: tuple[
            tuple[int, ...], int, int, int, int, tuple[int, ...], str | None, str | None, SourceEvidenceFingerprint
        ],
        modelo_tuple: tuple[ModeloDefinition, ...],
        failures: tuple[str, ...],
    ) -> None:
        """Persist a completed registry validation result under its exact key."""
        REGISTRY_VALIDATION_CACHE[cache_key] = (
            modelo_tuple,
            self._legal,
            self._sources,
            self._facts,
            self._runtime,
            failures,
        )

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph.

        Args:
            modelos: Iterable of
                :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
                instances to validate together before
                :func:`cadrumo.domain.calculations.registry.validate_registry_scope.validate_registry_scope`
                checks cross-model closure.
        """
        failure_tuple = self.registry_failures(modelos)
        if failure_tuple:
            raise RegistryValidationError(
                "registry validation failed:\n" + "\n".join(f" - {f}" for f in failure_tuple),
            )

    def registry_failures(self, modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
        """Return candidate findings without granting authority validity."""
        modelo_tuple = tuple(modelos)
        cache_key = self._registry_cache_key(modelo_tuple)
        cached_failures = self._cached_registry_failures(modelo_tuple, cache_key)
        if cached_failures is not None:
            return cached_failures

        try:
            failures = self._validate_registry_modelos(modelo_tuple)
            failures.extend(validate_registry_scope(modelo_tuple))
            failures.extend(validate_form_geometry(modelo_tuple))
            failures.extend(validate_household_row_owners(modelo_tuple))
        finally:
            # Source-text extraction is the validation's dominant cold cost;
            # persisting it here is what lets the next process skip it.
            flush_corpus_text_cache()
        failure_tuple = tuple(failures)
        self._cache_registry_failures(cache_key, modelo_tuple, failure_tuple)
        return failure_tuple

    def _validate_user_profile_contract(self, modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
        from cadrumo.domain.user_profile.registry_contract import validate_user_profile_registry_contract

        schema = self._user_profile_schema
        if schema is None:
            raise RegistryValidationError(
                "registry validation requires the profile schema captured in the compiler source set"
            )
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
            justificante_corpus_root=self.justificante_corpus_root,
            support=self._support,
        )
        for failure in validate_producer_inventory(prefix, revision):
            if failure not in failures:
                failures.append(failure)
        failures.extend(self._invoice_clave_failures(modelo, revision, prefix=prefix))
        failures.extend(self._ledger_selector_vocabulary_failures(revision, prefix=prefix))
        return failures

    def _ledger_selector_vocabulary_failures(self, revision: ModeloRevision, *, prefix: str) -> list[str]:
        """Validate ledger IVA and OSS/IOSS selector tokens against this candidate's facts on the revision's start."""
        if not any(binding.source in _DATED_LEDGER_SELECTOR_SOURCES for binding in revision.bindings):
            return []
        if self._support is None:
            return [f"{prefix}: ledger selector vocabularies require the candidate support envelope"]
        authority = CandidateFactAuthority(self._facts, self._support)
        return [
            f"{prefix}: {failure}"
            for failure in (
                *ledger_iva_revision_vocabulary_failures(revision, authority=authority),
                *ledger_oss_revision_vocabulary_failures(revision, authority=authority),
            )
        ]

    def _invoice_clave_failures(self, modelo: ModeloDefinition, revision: ModeloRevision, *, prefix: str) -> list[str]:
        """Validate selectors against this candidate's dated operation catalogue."""
        if modelo.id not in ("347", "349"):
            return []
        selectors = tuple(
            (binding.id, binding.provider.claves)
            for binding in revision.bindings
            if isinstance(binding.provider, InvoiceProviderBase) and binding.provider.claves
        )
        if not selectors:
            return []
        if self._support is None:
            return [f"{prefix}: invoice operation claves require the candidate support envelope"]
        authority = CandidateFactAuthority(self._facts, self._support)
        return [
            failure
            for point in _candidate_clave_dates(modelo.id, revision, authority)
            for failure in _candidate_clave_failures_at(modelo.id, selectors, point, authority, prefix)
        ]


_DATED_LEDGER_SELECTOR_SOURCES = frozenset(
    {BindingSourceKind.LEDGER_IVA_AGGREGATION, BindingSourceKind.LEDGER_OSS_AGGREGATION}
)
"""Binding families whose selector tokens are members of a dated registry vocabulary."""


def _candidate_clave_dates(
    modelo: str, revision: ModeloRevision, authority: CandidateFactAuthority
) -> tuple[date, ...]:
    """Cover the supported revision window and each fact start or end transition."""
    support = authority.supported_filing_years()
    floor = max(revision.valid_from, date(support.floor, 1, 1))
    ceiling = revision.valid_to or date.max
    if support.hard_ceiling is not None:
        ceiling = min(ceiling, date(support.hard_ceiling, 12, 31))
    if floor > ceiling:
        return ()
    points = {floor}
    fact = authority.catalogue.facts.get(f"m{modelo}-operation-clave-vocabulary")
    if fact is not None:
        for variant in fact.variants:
            points.update(point for point in _fact_transition_dates(variant) if floor <= point <= ceiling)
    return tuple(sorted(points))


def _fact_transition_dates(variant: GovernedFactVariant) -> tuple[date, ...]:
    """Return the coordinates where this variant starts or ceases to apply."""
    points = []
    if variant.valid_from is not None:
        points.append(variant.valid_from)
    if variant.valid_to is not None and variant.valid_to < date.max:
        points.append(variant.valid_to + timedelta(days=1))
    return tuple(points)


def _candidate_clave_failures_at(
    modelo: Literal["347", "349"],
    selectors: tuple[tuple[BindingId, tuple[str, ...]], ...],
    point: date,
    authority: CandidateFactAuthority,
    prefix: str,
) -> list[str]:
    """Compare one candidate fact window with every authored selector."""
    try:
        vocabulary = resolve_counterpart_operation_claves(modelo, effective_date=point, authority=authority)
    except RegistryValidationError as error:
        return [f"{prefix}: invoice operation clave catalogue at {point}: {error}"]
    return [
        f"{prefix}: binding {binding_id!r} selects unknown operation claves {sorted(unknown)} at {point}"
        for binding_id, claves in selectors
        if (unknown := set(claves) - vocabulary)
    ]


def runtime_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> frozenset[str]:
    """Return every legal identity carried by a published runtime table."""
    return frozenset(ref for refs in _runtime_legal_reference_groups(runtime) for ref in refs)


def _runtime_legal_reference_groups(runtime: RuntimeRegistryCatalogues) -> tuple[Iterator[str], ...]:
    return (
        _iva_regulation_legal_reference_ids(runtime),
        _place_of_supply_legal_reference_ids(runtime),
        _postal_territory_legal_reference_ids(runtime),
        _territory_carve_out_legal_reference_ids(runtime),
        _recargo_band_legal_reference_ids(runtime),
    )


def _iva_regulation_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> Iterator[str]:
    return (
        citation.legal_reference for regulation in runtime.iva_regulations.values() for citation in regulation.citations
    )


def _place_of_supply_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> Iterator[str]:
    return (ref for rule in runtime.iva_place_of_supply.values() for ref in rule.legal_references)


def _postal_territory_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> Iterator[str]:
    return (ref for territory in runtime.spanish_postal_territories.values() for ref in territory.legal_refs)


def _territory_carve_out_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> Iterator[str]:
    return (ref for carve_out in runtime.territory_carve_outs.values() for ref in carve_out.legal_refs)


def _recargo_band_legal_reference_ids(runtime: RuntimeRegistryCatalogues) -> Iterator[str]:
    return (band.legal_ref for band in runtime.recargo_bands.values())

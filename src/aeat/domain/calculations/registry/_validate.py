"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

from ._bindings import (
    validate_invoice_binding_definition,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding_definition,
    validate_ledger_renta_expense_aggregation_binding_definition,
)
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._schema import (
    CasillaDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DatedValue,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportRecordDefinition,
    ExtractionProfileDefinition,
    FormulaDefinition,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RelationDefinition,
    SourceCitation,
    SourceReference,
)
from ._sources import verify_source_catalogue
from ._text import normalise_corpus_text
from ._validate_application_links import validate_application_link_closure
from ._validate_cross_revision import _validate_cross_revision_casilla_consistency
from ._validate_formulas import validate_formula_dag, validate_formula_expression
from ._validate_relation_sources import (
    period_selectors_overlap,
    validate_previous_filing_binding_closure,
    validate_relation_closure,
)
from ._validate_revision_identity import (
    _collect_record_id_lists,
    _duplicates,
    _emit_casilla_identity_failures,
    _emit_combined_primary_id_failures,
    _emit_completeness_gate_failures,
    _emit_per_kind_duplicate_failures,
    _resolvable_casilla_references,
)
from ._validate_semantic_roles import (
    _emit_semantic_role_typo_twin_warnings,
    _validate_required_role_declarations,
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
)

if TYPE_CHECKING:
    from ...user_profile._schema import ProfileSchemaDefinition

_CatalogueCacheKey = tuple[int, int, str | None]
_CatalogueCacheValue = tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], tuple[str, ...]]
_ModeloValidationCacheKey = tuple[int, int, int, str | None]
_ModeloValidationCacheValue = tuple[
    ModeloDefinition,
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]
_RegistryValidationCacheKey = tuple[tuple[int, ...], int, int, str | None]
_RegistryValidationCacheValue = tuple[
    tuple[ModeloDefinition, ...],
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]
_SourceTextCacheKey = tuple[str, str, int, int]
_SourceTextCacheValue = tuple[Path, str]
_CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
_MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
_REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}
_NORMALISED_SOURCE_TEXT_CACHE: dict[_SourceTextCacheKey, _SourceTextCacheValue] = {}


@lru_cache(maxsize=4096)
def _normalise_required_text(text: str) -> str:
    return normalise_corpus_text(text)


def _is_layout_binding(binding: DataBindingDefinition) -> bool:
    """Layout-binding predicate, delegated to the typed manual_input shape.

    Layout bindings inject operator-typed values at fixed-width
    record-field coordinates. The shape gate's source of truth lives
    on :class:`_ManualInputSelector`; this predicate delegates to its
    canonical record-shape key set rather than re-implementing the
    check.
    """

    from ._bindings import is_layout_binding_selector

    return is_layout_binding_selector(binding.selector)


def _extract_pdf_text(path: Path) -> str:
    stat = path.stat()
    return _extract_pdf_text_cached(str(path.expanduser().resolve()), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_pdf_text_cached(path: str, byte_count: int, modified_ns: int) -> str:
    del byte_count, modified_ns
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - dependency is required by pyproject.
        raise OSError("pypdfium2 is required to validate manual PDF citations") from exc
    try:
        pdf = pdfium.PdfDocument(path)
        pages: list[str] = []
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    text_page = page.get_textpage()
                    try:
                        pages.append(text_page.get_text_range())
                    finally:
                        text_page.close()
                finally:
                    page.close()
        finally:
            pdf.close()
        return "\n".join(pages)
    except Exception as exc:
        raise OSError(f"could not extract text from manual PDF {path}") from exc


class RegistryValidator:
    """Validate legal/source closure and calculability for modelos."""

    def __init__(
        self,
        catalogues: RegistryCatalogues,
        *,
        source_root: Path | None = None,
        user_profile_schema: ProfileSchemaDefinition | None = None,
    ) -> None:
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._source_root = source_root
        self._user_profile_schema = user_profile_schema
        self._source_text_cache: dict[str, str] = {}
        self._catalogue_failures: tuple[str, ...] | None = None

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
        failures = self._cached_modelo_failures(modelo)
        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

    def _source_root_key(self) -> str | None:
        return str(self._source_root.expanduser().resolve()) if self._source_root is not None else None

    def _cached_modelo_failures(self, modelo: ModeloDefinition) -> tuple[str, ...]:
        cache_key = (id(modelo), id(self._legal), id(self._sources), self._source_root_key())
        cached = _MODELO_VALIDATION_CACHE.get(cache_key)
        if cached is not None and cached[0] is modelo and cached[1] is self._legal and cached[2] is self._sources:
            return cached[3]
        failures = tuple(self._validate_modelo(modelo, validate_catalogues=True))
        _MODELO_VALIDATION_CACHE[cache_key] = (modelo, self._legal, self._sources, failures)
        return failures

    def _validate_catalogues(self) -> tuple[str, ...]:
        if self._catalogue_failures is not None:
            return self._catalogue_failures
        source_root_key = self._source_root_key()
        cache_key = (id(self._legal), id(self._sources), source_root_key)
        cached = _CATALOGUE_FAILURE_CACHE.get(cache_key)
        if cached is not None and cached[0] is self._legal and cached[1] is self._sources:
            self._catalogue_failures = cached[2]
            return self._catalogue_failures

        failures: list[str] = []
        try:
            verify_legal_catalogue(self._legal, source_root=self._source_root)
        except RegistryValidationError as exc:
            failures.append(str(exc))
        if self._source_root is not None:
            try:
                verify_source_catalogue(self._source_root, self._sources)
            except RegistryValidationError as exc:
                failures.append(str(exc))
        self._catalogue_failures = tuple(failures)
        _CATALOGUE_FAILURE_CACHE[cache_key] = (self._legal, self._sources, self._catalogue_failures)
        return self._catalogue_failures

    def _validate_modelo(self, modelo: ModeloDefinition, *, validate_catalogues: bool) -> list[str]:
        failures: list[str] = []
        if validate_catalogues:
            failures.extend(self._validate_catalogues())
        failures.extend(self._missing_refs("modelo", modelo.id, modelo.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs("modelo", modelo.id, modelo.source_refs, self._sources, "source"))
        for revision in modelo.revisions.values():
            failures.extend(self._validate_revision(modelo, revision))
        failures.extend(self._validate_user_profile_contract((modelo,)))
        failures.extend(self._validate_revision_windows(modelo))
        failures.extend(self._validate_informative_class_invariant(modelo))
        return failures

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph."""

        modelo_tuple = tuple(modelos)
        cache_key = (
            tuple(id(modelo) for modelo in modelo_tuple),
            id(self._legal),
            id(self._sources),
            self._source_root_key(),
        )
        cached = _REGISTRY_VALIDATION_CACHE.get(cache_key)
        if cached is not None and cached[0] == modelo_tuple and cached[1] is self._legal and cached[2] is self._sources:
            if cached[3]:
                raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in cached[3]))
            return

        failures: list[str] = list(self._validate_catalogues())
        modelo_ids = [modelo.id for modelo in modelo_tuple]
        for duplicate in sorted(_duplicates(modelo_ids)):
            failures.append(f"registry: duplicate modelo id {duplicate!r}")

        modelos_by_id = {modelo.id: modelo for modelo in modelo_tuple}
        for modelo in modelo_tuple:
            failures.extend(self._validate_modelo(modelo, validate_catalogues=False))

        if len(modelos_by_id) == len(modelo_tuple):
            failures.extend(validate_relation_closure(modelo_tuple, modelos_by_id))
            failures.extend(validate_previous_filing_binding_closure(modelo_tuple, modelos_by_id))

        # Per-source selector-shape gate at registry-tree validation
        # level. Without this loop, callers that exercise
        # ``validate_registry`` directly (rather than going through
        # ``_build_validated_snapshot``) would skip the discriminator
        # check entirely.
        from ._bindings import validate_binding_selector_shape

        for modelo in modelo_tuple:
            for revision in modelo.revisions.values():
                prefix = f"modelo {modelo.id} revision {revision.id}"
                for binding in revision.bindings:
                    failures.extend(
                        f"{prefix}: {fail}"
                        for fail in validate_binding_selector_shape(binding)
                    )

        # Plan C semantic-role validation: walks every casilla across
        # the corpus and enforces intra-role data_type and constraints
        # consistency. Typo-twin warnings are emitted out-of-band.
        failures.extend(_validate_semantic_role_consistency(modelo_tuple))
        failures.extend(_validate_semantic_role_cardinality(modelo_tuple))
        # Hard-flip: required-role label patterns must declare the
        # canonical role on every matching casilla.
        failures.extend(_validate_required_role_declarations(modelo_tuple))
        # Cross-revision drift detection: casillas sharing an id across
        # revisions of a modelo must declare identical stable fields.
        failures.extend(_validate_cross_revision_casilla_consistency(modelo_tuple))
        _emit_semantic_role_typo_twin_warnings(modelo_tuple)

        if failures:
            _REGISTRY_VALIDATION_CACHE[cache_key] = (modelo_tuple, self._legal, self._sources, tuple(failures))
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))
        _REGISTRY_VALIDATION_CACHE[cache_key] = (modelo_tuple, self._legal, self._sources, ())

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
        failures: list[str] = []
        prefix = f"modelo {modelo.id} revision {revision.id}"
        failures.extend(self._missing_refs(prefix, "revision", revision.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs(prefix, "revision", revision.source_refs, self._sources, "source"))

        ids_by_kind = _collect_record_id_lists(revision)
        if not ids_by_kind["workbook parity reference"]:
            failures.append(f"{prefix}: revision must declare official workbook parity coverage")
        _emit_per_kind_duplicate_failures(failures, prefix, ids_by_kind)
        _emit_combined_primary_id_failures(failures, prefix, ids_by_kind)
        _emit_casilla_identity_failures(failures, prefix, revision)
        _emit_completeness_gate_failures(failures, prefix, revision)
        # The ``_validate_support_removal_decisions`` call below still
        # consumes the per-kind lists as kwargs; expose them as local
        # aliases so the existing signature shape stays unchanged.
        export_layout_ids = ids_by_kind["export layout"]
        extraction_profile_ids = ids_by_kind["extraction profile"]
        cross_reference_ids = ids_by_kind["cross-reference"]
        workbook_parity_ids = ids_by_kind["workbook parity reference"]
        verification_expectation_ids = ids_by_kind["verification expectation"]
        application_link_ids = ids_by_kind["application link"]
        deadline_window_ids = ids_by_kind["deadline window"]
        filing_schedule_ids = ids_by_kind["filing schedule"]

        casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}
        formula_by_id = {formula.id: formula for formula in revision.formulas}
        binding_by_id = {binding.id: binding for binding in revision.bindings}
        relation_by_id = {relation.id: relation for relation in revision.relations}
        parameter_by_id = {parameter.id: parameter for parameter in revision.parameters}
        provider_by_id = {provider.id: provider for provider in revision.algorithm_providers}
        algorithm_binding_by_id = {binding.id: binding for binding in revision.algorithm_bindings}
        export_layout_by_id = {layout.id: layout for layout in revision.export_layouts}
        extraction_profile_by_id = {profile.id: profile for profile in revision.extraction_profiles}
        cross_reference_by_id = {
            cross_reference.id: cross_reference for cross_reference in revision.live_cross_references
        }
        workbook_parity_by_id = {workbook.id: workbook for workbook in revision.workbook_parity_refs}
        verification_expectation_by_id = {
            expectation.id: expectation for expectation in revision.verification_expectations
        }
        application_link_by_id = {link.id: link for link in revision.application_links}
        deadline_window_by_id = {window.id: window for window in revision.deadline_windows}
        filing_schedule_by_id = {schedule.id: schedule for schedule in revision.filing_schedules}
        support_removal_decision_by_id = {decision.id: decision for decision in revision.support_removal_decisions}
        construct_by_id = {construct.id: construct for construct in revision.constructs}
        dependency_classification_by_id = {
            classification.id: classification for classification in revision.dependency_classifications
        }

        # Segment-aware casilla reference resolution: a reference resolves
        # against a casilla ``id`` or against an unambiguous bare
        # ``number``. For single-segment modelos (``id == number``,
        # every number unique) this set is exactly ``set(casilla_by_id)``.
        casillas = set(_resolvable_casilla_references(revision))
        formulas = {formula.id: formula for formula in revision.formulas}
        bindings = set(binding_by_id)
        relations = set(relation_by_id)
        parameters = set(parameter_by_id)
        providers = set(provider_by_id)
        resolvable_values = casillas | bindings | relations | parameters
        export_field_ids = {
            field.id for layout in revision.export_layouts for record in layout.records for field in record.fields
        }
        exported_casillas = {
            field.casilla
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.casilla is not None
        }

        self._validate_casilla_section(
            failures,
            prefix=prefix,
            revision=revision,
            formulas=formulas,
            bindings=bindings,
            export_field_ids=export_field_ids,
        )
        self._validate_formula_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            bindings=bindings,
            parameters=parameters,
            relations=relations,
        )
        self._validate_parameter_section(failures, prefix=prefix, revision=revision)
        self._validate_binding_section(failures, prefix=prefix, revision=revision)
        self._validate_relation_section(
            failures,
            prefix=prefix,
            revision=revision,
            bindings=bindings,
            binding_by_id=binding_by_id,
        )

        self._validate_dependency_classification_section(
            failures,
            prefix=prefix,
            revision=revision,
            construct_by_id=construct_by_id,
            relation_by_id=relation_by_id,
        )
        self._validate_filing_schedule_section(failures, prefix=prefix, revision=revision)
        self._validate_algorithm_provider_section(failures, prefix=prefix, revision=revision)
        self._validate_algorithm_binding_section(
            failures,
            prefix=prefix,
            revision=revision,
            providers=providers,
            casillas=casillas,
            resolvable_values=resolvable_values,
            parameters=parameters,
        )

        self._validate_export_layout_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            bindings=bindings,
            casilla_by_id=casilla_by_id,
        )
        self._validate_extraction_profile_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            exported_casillas=exported_casillas,
        )
        self._validate_cross_reference_section(failures, prefix=prefix, revision=revision)
        self._validate_workbook_parity_section(failures, prefix=prefix, revision=revision)
        self._validate_verification_expectation_section(
            failures, prefix=prefix, revision=revision, casillas=casillas
        )
        self._validate_application_link_section(failures, prefix=prefix, revision=revision)
        self._validate_deadline_window_section(failures, prefix=prefix, revision=revision)

        failures.extend(
            self._validate_support_removal_decisions(
                prefix,
                revision,
                export_layout_ids=export_layout_ids,
                extraction_profile_ids=extraction_profile_ids,
                cross_reference_ids=cross_reference_ids,
                workbook_parity_ids=workbook_parity_ids,
                verification_expectation_ids=verification_expectation_ids,
                application_link_ids=application_link_ids,
                deadline_window_ids=deadline_window_ids,
                filing_schedule_ids=filing_schedule_ids,
            )
        )
        failures.extend(validate_application_link_closure(prefix, revision, modelo_id=modelo.id))
        failures.extend(self._validate_reconciliation_total_closure(prefix, revision))
        failures.extend(
            self._validate_construct_closure(
                prefix,
                revision,
                member_objects={
                    "casilla": casilla_by_id,
                    "formula": formula_by_id,
                    "parameter": parameter_by_id,
                    "binding": binding_by_id,
                    "algorithm provider": provider_by_id,
                    "algorithm binding": algorithm_binding_by_id,
                    "relation": relation_by_id,
                    "export layout": export_layout_by_id,
                    "extraction profile": extraction_profile_by_id,
                    "cross-reference": cross_reference_by_id,
                    "workbook parity reference": workbook_parity_by_id,
                    "verification expectation": verification_expectation_by_id,
                    "application link": application_link_by_id,
                    "deadline window": deadline_window_by_id,
                    "filing schedule": filing_schedule_by_id,
                    "support removal decision": support_removal_decision_by_id,
                    "dependency classification": dependency_classification_by_id,
                },
            )
        )
        failures.extend(validate_formula_dag(prefix, revision))
        return failures

    def _validate_casilla_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        formulas: Mapping[str, FormulaDefinition],
        bindings: set[str],
        export_field_ids: set[str],
    ) -> None:
        for casilla in revision.casillas:
            failures.extend(
                self._missing_refs(prefix, f"casilla {casilla.id}", casilla.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"casilla {casilla.id}", casilla.source_refs, self._sources, "source")
            )
            if casilla.formula is not None and casilla.formula not in formulas:
                failures.append(f"{prefix}: casilla {casilla.id!r} references unknown formula {casilla.formula!r}")
            if (
                casilla.formula is not None
                and casilla.formula in formulas
                and formulas[casilla.formula].target != casilla.id
            ):
                failures.append(
                    f"{prefix}: casilla {casilla.id!r} references formula {casilla.formula!r} "
                    f"targeting {formulas[casilla.formula].target!r}"
                )
            if casilla.binding is not None and casilla.binding not in bindings:
                failures.append(f"{prefix}: casilla {casilla.id!r} references unknown binding {casilla.binding!r}")
            for export_ref in casilla.export_refs:
                if export_ref not in export_field_ids:
                    failures.append(f"{prefix}: casilla {casilla.id!r} references unknown export field {export_ref!r}")

    def _validate_formula_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        bindings: set[str],
        parameters: set[str],
        relations: set[str],
    ) -> None:
        for formula in revision.formulas:
            failures.extend(
                self._missing_refs(prefix, f"formula {formula.id}", formula.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"formula {formula.id}", formula.source_refs, self._sources, "source")
            )
            failures.extend(self._require_legal_authority_refs(prefix, f"formula {formula.id}", formula.legal_refs))
            failures.extend(
                self._require_source_tier(
                    prefix,
                    f"formula {formula.id}",
                    formula.source_refs,
                    "official_source_guidance",
                )
            )
            failures.extend(
                self._validate_source_citations(
                    prefix,
                    f"formula {formula.id}",
                    formula.source_refs,
                    formula.source_citations,
                    "official_source_guidance",
                )
            )
            if formula.target not in casillas:
                failures.append(f"{prefix}: formula {formula.id!r} targets unknown casilla {formula.target!r}")
            failures.extend(
                validate_formula_expression(
                    prefix,
                    formula.id,
                    formula.expression,
                    casillas=casillas,
                    bindings=bindings,
                    parameters=parameters,
                    relations=relations,
                )
            )

        for target in sorted(_duplicates([formula.target for formula in revision.formulas])):
            failures.append(f"{prefix}: duplicate formula target {target!r}")

    def _validate_parameter_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        for parameter in revision.parameters:
            failures.extend(
                self._missing_refs(prefix, f"parameter {parameter.id}", parameter.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"parameter {parameter.id}", parameter.source_refs, self._sources, "source")
            )
            failures.extend(
                self._require_legal_authority_refs(prefix, f"parameter {parameter.id}", parameter.legal_refs)
            )
            failures.extend(
                self._require_source_tier(
                    prefix,
                    f"parameter {parameter.id}",
                    parameter.source_refs,
                    "official_source_guidance",
                )
            )
            failures.extend(
                self._validate_source_citations(
                    prefix,
                    f"parameter {parameter.id}",
                    parameter.source_refs,
                    parameter.source_citations,
                    "official_source_guidance",
                )
            )
            failures.extend(self._validate_dated_values(prefix, parameter.id, parameter.values))

    def _validate_binding_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        # Run the discriminated-selector shape gate here so a
        # standalone ``validate_registry`` call surfaces the same
        # selector-shape errors as ``build_snapshot``. Without this,
        # CI tools that validate the registry without building a
        # snapshot silently skip the per-source shape gate.
        from ._bindings import validate_binding_selector_shape

        for binding in revision.bindings:
            failures.extend(
                f"{prefix}: {fail}" for fail in validate_binding_selector_shape(binding)
            )
        for binding in revision.bindings:
            failures.extend(
                self._missing_refs(prefix, f"binding {binding.id}", binding.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"binding {binding.id}", binding.source_refs, self._sources, "source")
            )
            failures.extend(self._require_legal_authority_refs(prefix, f"binding {binding.id}", binding.legal_refs))
            if _is_layout_binding(binding):
                failures.extend(
                    self._require_source_tier(
                        prefix,
                        f"binding {binding.id}",
                        binding.source_refs,
                        "layout_authority",
                    )
                )
            else:
                failures.extend(
                    self._require_source_tier(
                        prefix,
                        f"binding {binding.id}",
                        binding.source_refs,
                        "official_source_guidance",
                    )
                )
                failures.extend(
                    self._validate_source_citations(
                        prefix,
                        f"binding {binding.id}",
                        binding.source_refs,
                        binding.source_citations,
                        "official_source_guidance",
                    )
                )
            self._validate_per_source_binding(failures, prefix=prefix, binding=binding)

    @staticmethod
    def _validate_per_source_binding(
        failures: list[str],
        *,
        prefix: str,
        binding: DataBindingDefinition,
    ) -> None:
        """Run the per-source typed binding-definition validators."""
        source_validators = (
            ("invoice", validate_invoice_binding_definition),
            ("ledger_oss_aggregation", validate_ledger_oss_aggregation_binding_definition),
            ("ledger_iva_aggregation", validate_ledger_iva_aggregation_binding_definition),
            ("ledger_renta_expense_aggregation", validate_ledger_renta_expense_aggregation_binding_definition),
        )
        for source_name, validator in source_validators:
            if binding.source == source_name:
                try:
                    validator(binding)
                except RegistryValidationError as exc:
                    failures.append(f"{prefix}: {exc}")

    def _validate_relation_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        bindings: set[str],
        binding_by_id: Mapping[str, DataBindingDefinition],
    ) -> None:
        for relation in revision.relations:
            failures.extend(
                self._missing_refs(prefix, f"relation {relation.id}", relation.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"relation {relation.id}", relation.source_refs, self._sources, "source")
            )
            if relation.target_binding not in bindings:
                failures.append(
                    f"{prefix}: relation {relation.id!r} targets unknown binding {relation.target_binding!r}"
                )
            else:
                target_binding = binding_by_id[relation.target_binding]
                missing_legal_refs = sorted(set(relation.legal_refs).difference(target_binding.legal_refs))
                if missing_legal_refs:
                    failures.append(
                        f"{prefix}: relation {relation.id!r} target binding {relation.target_binding!r} "
                        f"does not include relation legal refs {missing_legal_refs!r}"
                    )
                missing_source_refs = sorted(set(relation.source_refs).difference(target_binding.source_refs))
                if missing_source_refs:
                    failures.append(
                        f"{prefix}: relation {relation.id!r} target binding {relation.target_binding!r} "
                        f"does not include relation source refs {missing_source_refs!r}"
                    )
            unknown_target_periods = sorted(set(relation.target_periods).difference(revision.period_selector.periods))
            if unknown_target_periods:
                failures.append(
                    f"{prefix}: relation {relation.id!r} targets periods outside revision selector "
                    f"{unknown_target_periods!r}"
                )

    def _validate_dependency_classification_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        construct_by_id: Mapping[str, ConstructDefinition],
        relation_by_id: Mapping[str, RelationDefinition],
    ) -> None:
        for classification in revision.dependency_classifications:
            self._validate_single_dependency_classification(
                failures,
                prefix=prefix,
                classification=classification,
                construct_by_id=construct_by_id,
                relation_by_id=relation_by_id,
            )

        for duplicate in sorted(_duplicates([item.source_modelo for item in revision.dependency_classifications])):
            failures.append(f"{prefix}: duplicate dependency classification source modelo {duplicate!r}")
        classifications_by_source = {
            classification.source_modelo: classification for classification in revision.dependency_classifications
        }
        relation_ids_by_source: dict[str, set[str]] = {}
        for relation in revision.relations:
            relation_ids_by_source.setdefault(relation.source_modelo, set()).add(relation.id)
        for source_modelo, relation_ids_for_source in sorted(relation_ids_by_source.items()):
            classification = classifications_by_source.get(source_modelo)
            if classification is None:
                failures.append(f"{prefix}: relation source modelo {source_modelo!r} has no dependency classification")
                continue
            if classification.treatment == "non_dependency":
                failures.append(
                    f"{prefix}: relation source modelo {source_modelo!r} cannot be classified as non_dependency"
                )
                continue
            missing_relation_refs = sorted(relation_ids_for_source.difference(classification.relation_refs))
            if missing_relation_refs:
                failures.append(
                    f"{prefix}: dependency classification {classification.id!r} does not cover relation refs "
                    f"{missing_relation_refs!r}"
                )

    def _validate_single_dependency_classification(
        self,
        failures: list[str],
        *,
        prefix: str,
        classification: DependencyClassificationDefinition,
        construct_by_id: Mapping[str, ConstructDefinition],
        relation_by_id: Mapping[str, RelationDefinition],
    ) -> None:
        owner = f"dependency classification {classification.id}"
        failures.extend(self._missing_refs(prefix, owner, classification.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs(prefix, owner, classification.source_refs, self._sources, "source"))
        for construct_id in classification.target_constructs:
            construct = construct_by_id.get(construct_id)
            if construct is None:
                failures.append(
                    f"{prefix}: {owner} references unknown construct {construct_id!r}"
                )
                continue
            if classification.id not in construct.dependency_classifications:
                failures.append(
                    f"{prefix}: {owner} targets construct {construct_id!r} but the construct does not list it"
                )
        for relation_id in classification.relation_refs:
            relation = relation_by_id.get(relation_id)
            if relation is None:
                failures.append(f"{prefix}: {owner} references unknown relation {relation_id!r}")
                continue
            if relation.source_modelo != classification.source_modelo:
                failures.append(
                    f"{prefix}: {owner} source_modelo {classification.source_modelo!r} does not match "
                    f"relation {relation_id!r} source_modelo {relation.source_modelo!r}"
                )
            missing_legal_refs = sorted(set(relation.legal_refs).difference(classification.legal_refs))
            if missing_legal_refs:
                failures.append(
                    f"{prefix}: {owner} relation {relation_id!r} "
                    f"does not include relation legal refs {missing_legal_refs!r}"
                )
            missing_source_refs = sorted(set(relation.source_refs).difference(classification.source_refs))
            if missing_source_refs:
                failures.append(
                    f"{prefix}: {owner} relation {relation_id!r} "
                    f"does not include relation source refs {missing_source_refs!r}"
                )

    def _validate_filing_schedule_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        selector_periods = set(revision.period_selector.periods)
        for schedule in revision.filing_schedules:
            failures.extend(
                self._missing_refs(prefix, f"filing schedule {schedule.id}", schedule.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(
                    prefix, f"filing schedule {schedule.id}", schedule.source_refs, self._sources, "source"
                )
            )
            unknown_periods = sorted(set(schedule.periods).difference(selector_periods))
            if unknown_periods:
                failures.append(
                    f"{prefix}: filing schedule {schedule.id!r} declares periods outside revision selector "
                    f"{unknown_periods!r}"
                )
            for condition in schedule.profile_conditions:
                condition_owner = f"filing schedule {schedule.id} condition {condition.field}"
                failures.extend(self._missing_refs(prefix, condition_owner, condition.legal_refs, self._legal, "legal"))
                failures.extend(
                    self._missing_refs(prefix, condition_owner, condition.source_refs, self._sources, "source")
                )

    def _validate_algorithm_provider_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        for provider in revision.algorithm_providers:
            owner = f"algorithm provider {provider.id}"
            failures.extend(self._missing_refs(prefix, owner, provider.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, provider.source_refs, self._sources, "source"))

    def _validate_algorithm_binding_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        providers: set[str],
        casillas: set[str],
        resolvable_values: set[str],
        parameters: set[str],
    ) -> None:
        for alg_binding in revision.algorithm_bindings:
            owner = f"algorithm binding {alg_binding.id}"
            failures.extend(self._missing_refs(prefix, owner, alg_binding.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, alg_binding.source_refs, self._sources, "source"))
            if alg_binding.provider not in providers:
                failures.append(f"{prefix}: {owner} references unknown provider {alg_binding.provider!r}")
            if alg_binding.target not in casillas:
                failures.append(f"{prefix}: {owner} targets unknown casilla {alg_binding.target!r}")
            for input_name, input_value in alg_binding.inputs.items():
                if input_value not in resolvable_values:
                    failures.append(
                        f"{prefix}: {owner} input {input_name!r} references unknown value {input_value!r}"
                    )
            for output_name, output_value in alg_binding.outputs.items():
                if output_value not in casillas:
                    failures.append(
                        f"{prefix}: {owner} output {output_name!r} references unknown casilla {output_value!r}"
                    )
            for constant in alg_binding.constants:
                if constant not in parameters:
                    failures.append(f"{prefix}: {owner} references unknown constant {constant!r}")

    def _validate_export_layout_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        bindings: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
    ) -> None:
        for layout in revision.export_layouts:
            owner = f"export {layout.id}"
            failures.extend(self._missing_refs(prefix, owner, layout.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, layout.source_refs, self._sources, "source"))
            failures.extend(self._require_source_tier(prefix, owner, layout.source_refs, "layout_authority"))
            for record in layout.records:
                self._validate_export_record(
                    failures,
                    prefix=prefix,
                    revision=revision,
                    record=record,
                    casillas=casillas,
                    bindings=bindings,
                    casilla_by_id=casilla_by_id,
                )

    def _validate_export_record(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        record: ExportRecordDefinition,
        casillas: set[str],
        bindings: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
    ) -> None:
        if record.binding_record is not None:
            self._validate_export_record_binding_link(
                failures, prefix=prefix, revision=revision, record=record
            )
        if (
            record.repeat == "binding_rows"
            and not any(field.kind == "binding" for field in record.fields)
            and record.binding_record is None
        ):
            failures.append(
                f"{prefix}: export record {record.id!r} repeats binding rows but has no binding fields"
            )
        if record.requires_positive_casilla is not None and record.requires_positive_casilla not in casillas:
            failures.append(
                f"{prefix}: export record {record.id!r} requires unknown positive casilla "
                f"{record.requires_positive_casilla!r}"
            )
        for field in record.fields:
            self._validate_export_field(
                failures,
                prefix=prefix,
                record=record,
                field=field,
                casillas=casillas,
                bindings=bindings,
                casilla_by_id=casilla_by_id,
            )

    def _validate_export_record_binding_link(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        record: ExportRecordDefinition,
    ) -> None:
        """Verify a binding-derived export record resolves to bindings with selector closure.

        ``record.binding_record`` must match at least one revision
        binding's ``selector["record"]``. Each matching binding must
        then either be a row-producer (aggregation.op == "rows", in
        which case byte coordinates come from explicit export field
        offsets) or declare ``offset`` / ``length`` / ``data_type``
        selectors directly.
        """
        matching_bindings = [
            binding for binding in revision.bindings if binding.selector.get("record") == record.binding_record
        ]
        if not matching_bindings:
            failures.append(
                f"{prefix}: export record {record.id!r} derives fields from unknown binding record "
                f"{record.binding_record!r}"
            )
        for binding in matching_bindings:
            if binding.aggregation is not None and binding.aggregation.get("op") == "rows":
                continue
            missing_selector_keys = sorted(
                key for key in ("offset", "length", "data_type") if key not in binding.selector
            )
            if missing_selector_keys:
                failures.append(
                    f"{prefix}: export record {record.id!r} binding {binding.id!r} lacks selector keys "
                    f"{missing_selector_keys!r}"
                )

    def _validate_export_field(
        self,
        failures: list[str],
        *,
        prefix: str,
        record: ExportRecordDefinition,
        field: ExportFieldDefinition,
        casillas: set[str],
        bindings: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
    ) -> None:
        owner = f"export field {field.id}"
        failures.extend(self._missing_refs(prefix, owner, field.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs(prefix, owner, field.source_refs, self._sources, "source"))
        if field.casilla is not None and field.casilla not in casillas:
            failures.append(f"{prefix}: export field {field.id!r} references unknown casilla {field.casilla!r}")
        if (
            field.casilla is not None
            and field.casilla in casilla_by_id
            and field.id not in casilla_by_id[field.casilla].export_refs
        ):
            failures.append(f"{prefix}: export field {field.id!r} is not declared by casilla {field.casilla!r}")
        if field.binding is not None and field.binding not in bindings:
            failures.append(f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}")
        if field.kind == "literal" and field.literal is not None and field.length is not None:
            literal_length = len(field.literal.encode(record.encoding))
            if literal_length > field.length:
                failures.append(
                    f"{prefix}: export field {field.id!r} literal length {literal_length} exceeds "
                    f"declared length {field.length}"
                )

    def _validate_extraction_profile_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        exported_casillas: set[str],
        casilla_by_id: dict[str, object] | None = None,
    ) -> None:
        for profile in revision.extraction_profiles:
            owner = f"extraction profile {profile.id}"
            failures.extend(self._missing_refs(prefix, owner, profile.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, profile.source_refs, self._sources, "source"))
            failures.extend(self._validate_dotted_callable(prefix, owner, profile.parser))
            target_casilla_ids = tuple(t.casilla_id for t in profile.target_casillas)
            for casilla_id in target_casilla_ids:
                if casilla_id not in casillas:
                    failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
            if profile.surface == "export_record" or "submitted_file" in profile.accepted_artefact_kinds:
                missing_exported_casillas = sorted(set(target_casilla_ids).difference(exported_casillas))
                if missing_exported_casillas:
                    failures.append(
                        f"{prefix}: export_record extraction profile {profile.id!r} targets casillas without "
                        f"export fields {missing_exported_casillas!r}"
                    )
            failures.extend(self._validate_extraction_profile_artefacts(prefix, profile))

    def _validate_cross_reference_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        oracle_bindings: dict[str, str] = {}
        for cross_reference in revision.live_cross_references:
            owner = f"cross-reference {cross_reference.id}"
            failures.extend(self._missing_refs(prefix, owner, cross_reference.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, cross_reference.source_refs, self._sources, "source"))
            failures.extend(
                self._require_source_tier(prefix, owner, cross_reference.source_refs, cross_reference.evidence_tier)
            )
            if cross_reference.oracle_id is not None:
                prior = oracle_bindings.get(cross_reference.oracle_id)
                if prior is not None:
                    failures.append(
                        f"{prefix}: cross-references {prior!r} and {cross_reference.id!r} "
                        f"both bind oracle_id {cross_reference.oracle_id!r}; "
                        f"each oracle id may be bound by at most one cross-reference per revision"
                    )
                else:
                    oracle_bindings[cross_reference.oracle_id] = cross_reference.id

    def _validate_workbook_parity_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        for workbook in revision.workbook_parity_refs:
            owner = f"workbook parity {workbook.id}"
            failures.extend(self._missing_refs(prefix, owner, workbook.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, workbook.source_refs, self._sources, "source"))
            if workbook.workbook_source not in self._sources:
                failures.append(
                    f"{prefix}: workbook parity {workbook.id!r} references unknown source {workbook.workbook_source!r}"
                )
                continue
            source = self._sources[workbook.workbook_source]
            if workbook.formula_coverage == "formula_form" and source.evidence_tier != "executable_parity_evidence":
                failures.append(
                    f"{prefix}: workbook parity {workbook.id!r} formula workbook requires "
                    "executable parity evidence source"
                )
            if workbook.formula_coverage != "formula_form" and source.evidence_tier == "executable_parity_evidence":
                failures.append(
                    f"{prefix}: workbook parity {workbook.id!r} non-formula workbook must not use "
                    "executable parity evidence source"
                )

    def _validate_verification_expectation_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
    ) -> None:
        for expectation in revision.verification_expectations:
            owner = f"verification expectation {expectation.id}"
            failures.extend(self._missing_refs(prefix, owner, expectation.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, expectation.source_refs, self._sources, "source"))
            for casilla_id in expectation.computed_casillas:
                if casilla_id not in casillas:
                    failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
            for total_kind, casilla_id in expectation.reconciliation_totals.items():
                if casilla_id not in casillas:
                    failures.append(
                        f"{prefix}: {owner} reconciliation total {total_kind!r} references unknown casilla "
                        f"{casilla_id!r}"
                    )
                if casilla_id not in expectation.computed_casillas:
                    failures.append(
                        f"{prefix}: {owner} reconciliation total {total_kind!r} must be one of computed_casillas"
                    )

    def _validate_application_link_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        for link in revision.application_links:
            owner = f"application link {link.id}"
            failures.extend(self._missing_refs(prefix, owner, link.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, link.source_refs, self._sources, "source"))

    def _validate_deadline_window_section(
        self,
        failures: list[str],
        *,
        prefix: str,
        revision: ModeloRevision,
    ) -> None:
        for window in revision.deadline_windows:
            owner = f"deadline window {window.id}"
            failures.extend(self._missing_refs(prefix, owner, window.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(prefix, owner, window.source_refs, self._sources, "source"))
            for condition in window.applicability_conditions:
                condition_owner = f"deadline condition for {window.id}"
                failures.extend(self._missing_refs(prefix, condition_owner, condition.legal_refs, self._legal, "legal"))
                failures.extend(
                    self._missing_refs(prefix, condition_owner, condition.source_refs, self._sources, "source")
                )

    @staticmethod
    def _missing_refs(
        scope: str,
        owner: str,
        refs: Iterable[str],
        catalogue: Mapping[str, LegalReference] | Mapping[str, SourceReference],
        ref_kind: str,
    ) -> list[str]:
        return [f"{scope}: {owner} references unknown {ref_kind} id {ref!r}" for ref in refs if ref not in catalogue]

    @staticmethod
    def _validate_revision_windows(modelo: ModeloDefinition) -> list[str]:
        failures: list[str] = []
        revisions = sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
        for index, current in enumerate(revisions[1:], start=1):
            previous = revisions[index - 1]
            previous_to = previous.valid_to
            if (
                previous_to is None or previous_to >= current.valid_from
            ) and period_selectors_overlap(previous.period_selector, current.period_selector):
                failures.append(
                    f"modelo {modelo.id}: revisions {previous.id!r} and {current.id!r} overlap on period selector"
                )
        return failures

    @staticmethod
    def _validate_informative_class_invariant(modelo: ModeloDefinition) -> list[str]:
        """Enforce that informative modelos carry no filing-grade computation artefacts.

        An informative modelo reports data but does not compute filing-grade amounts.
        Every revision must have empty ``formulas`` and empty ``relations``, and every
        casilla must be ``manual`` or ``informational``.  A ``filing`` or ``summary``
        modelo is not subject to this constraint.
        """
        if modelo.calculation_class != "informative":
            return []
        failures: list[str] = []
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            if revision.formulas:
                failures.append(
                    f"{prefix}: informative modelo must not declare calculation formulas (got {len(revision.formulas)})"
                )
            if revision.relations:
                failures.append(
                    f"{prefix}: informative modelo must not declare cross-model relations "
                    f"(got {len(revision.relations)})"
                )
            for casilla in revision.casillas:
                if casilla.input_kind not in {"informational", "manual"}:
                    failures.append(
                        f"{prefix}: informative modelo casilla {casilla.id!r} "
                        f"has input_kind={casilla.input_kind!r}; "
                        "only 'informational' and 'manual' are permitted"
                    )
        return failures

    @staticmethod
    def _validate_dated_values(scope: str, parameter_id: str, values: Iterable[DatedValue]) -> list[str]:
        failures: list[str] = []
        by_axis: dict[str, list[DatedValue]] = {}
        for value in values:
            axis = value.date_axis
            by_axis.setdefault(axis, []).append(value)
        for axis, axis_values in by_axis.items():
            ordered = sorted(axis_values, key=lambda item: item.valid_from)
            for index, current in enumerate(ordered[1:], start=1):
                previous = ordered[index - 1]
                previous_to = previous.valid_to
                if previous_to is None or previous_to >= current.valid_from:
                    failures.append(f"{scope}: parameter {parameter_id!r} has overlapping {axis} values")
        return failures

    @staticmethod
    def _validate_reconciliation_total_closure(scope: str, revision: ModeloRevision) -> list[str]:
        failures: list[str] = []
        declared: dict[str, str] = {}
        for expectation in revision.verification_expectations:
            for total_kind, casilla_id in expectation.reconciliation_totals.items():
                previous = declared.get(total_kind)
                if previous is not None and previous != casilla_id:
                    failures.append(
                        f"{scope}: reconciliation total {total_kind!r} is declared by multiple casillas "
                        f"{previous!r} and {casilla_id!r}"
                    )
                declared[total_kind] = casilla_id
        return failures

    def _validate_construct_closure(
        self,
        scope: str,
        revision: ModeloRevision,
        *,
        member_objects: Mapping[str, Mapping[str, object]],
    ) -> list[str]:
        failures: list[str] = []
        member_attrs = {
            "casilla": "casillas",
            "formula": "formulas",
            "parameter": "parameters",
            "binding": "bindings",
            "algorithm provider": "algorithm_providers",
            "algorithm binding": "algorithm_bindings",
            "relation": "relations",
            "export layout": "export_layouts",
            "extraction profile": "extraction_profiles",
            "cross-reference": "live_cross_references",
            "workbook parity reference": "workbook_parity_refs",
            "verification expectation": "verification_expectations",
            "application link": "application_links",
            "deadline window": "deadline_windows",
            "filing schedule": "filing_schedules",
            "support removal decision": "support_removal_decisions",
            "dependency classification": "dependency_classifications",
        }

        for construct in revision.constructs:
            owner = f"construct {construct.id}"
            failures.extend(self._missing_refs(scope, owner, construct.legal_refs, self._legal, "legal"))
            failures.extend(self._missing_refs(scope, owner, construct.source_refs, self._sources, "source"))
            construct_legal_refs = set(construct.legal_refs)
            construct_source_refs = set(construct.source_refs)
            for kind, attr in member_attrs.items():
                known = member_objects[kind]
                for member_id in getattr(construct, attr):
                    member = known.get(member_id)
                    if member is None:
                        failures.append(f"{scope}: construct {construct.id!r} references unknown {kind} {member_id!r}")
                        continue
                    member_legal_refs = set(getattr(member, "legal_refs", ()))
                    missing_legal = sorted(member_legal_refs.difference(construct_legal_refs))
                    if missing_legal:
                        failures.append(
                            f"{scope}: construct {construct.id!r} does not include legal refs "
                            f"{missing_legal!r} required by {kind} {member_id!r}"
                        )
                    member_source_refs = set(getattr(member, "source_refs", ()))
                    missing_sources = sorted(member_source_refs.difference(construct_source_refs))
                    if missing_sources:
                        failures.append(
                            f"{scope}: construct {construct.id!r} does not include source refs "
                            f"{missing_sources!r} required by {kind} {member_id!r}"
                        )

        return failures

    def _validate_support_removal_decisions(
        self,
        scope: str,
        revision: ModeloRevision,
        *,
        export_layout_ids: Iterable[str],
        extraction_profile_ids: Iterable[str],
        cross_reference_ids: Iterable[str],
        workbook_parity_ids: Iterable[str],
        verification_expectation_ids: Iterable[str],
        application_link_ids: Iterable[str],
        deadline_window_ids: Iterable[str],
        filing_schedule_ids: Iterable[str] = (),
    ) -> list[str]:
        failures: list[str] = []
        active_subjects = {
            "export_layout": set(export_layout_ids),
            "extraction_profile": set(extraction_profile_ids),
            "live_cross_reference": set(cross_reference_ids),
            "workbook_parity_ref": set(workbook_parity_ids),
            "verification_expectation": set(verification_expectation_ids),
            "application_link": set(application_link_ids),
            "deadline_window": set(deadline_window_ids),
            "filing_schedule": set(filing_schedule_ids),
        }
        for decision in revision.support_removal_decisions:
            failures.extend(
                self._missing_refs(
                    scope,
                    f"support removal decision {decision.id}",
                    decision.legal_refs,
                    self._legal,
                    "legal",
                )
            )
            failures.extend(
                self._missing_refs(
                    scope,
                    f"support removal decision {decision.id}",
                    decision.source_refs,
                    self._sources,
                    "source",
                )
            )
            active_ids = active_subjects.get(decision.subject_type)
            if active_ids is not None and decision.subject_id in active_ids:
                failures.append(
                    f"{scope}: support removal decision {decision.id!r} removes "
                    f"{decision.subject_type} {decision.subject_id!r} but it is still present"
                )
        return failures

    def _require_legal_authority_refs(self, scope: str, owner: str, refs: Iterable[str]) -> list[str]:
        failures: list[str] = []
        for ref in refs:
            legal = self._legal.get(ref)
            if legal is not None and legal.evidence_tier != "legal_authority":
                failures.append(f"{scope}: {owner} legal ref {ref!r} is not legal authority")
        return failures

    def _require_source_tier(
        self,
        scope: str,
        owner: str,
        refs: Iterable[str],
        required_tier: str,
    ) -> list[str]:
        if any(
            (source := self._sources.get(ref)) is not None and source.evidence_tier == required_tier for ref in refs
        ):
            return []
        return [f"{scope}: {owner} requires {required_tier} source evidence"]

    def _validate_source_citations(
        self,
        scope: str,
        owner: str,
        refs: Iterable[str],
        citations: Iterable[SourceCitation],
        required_tier: str,
    ) -> list[str]:
        failures: list[str] = []
        refs_set = set(refs)
        citations_tuple = tuple(citations)
        if not citations_tuple:
            return [f"{scope}: {owner} requires source citations"]
        for citation in citations_tuple:
            if citation.source_ref not in refs_set:
                failures.append(
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not listed in source_refs"
                )
                continue
            source = self._sources.get(citation.source_ref)
            if source is None:
                continue
            if source.evidence_tier != required_tier:
                failures.append(
                    f"{scope}: {owner} source citation {citation.source_ref!r} is not {required_tier} evidence"
                )
                continue
            if self._source_root is None:
                continue
            try:
                source_text = self._source_text(source)
            except OSError as exc:
                failures.append(f"{scope}: {owner} source citation {citation.source_ref!r} cannot be read: {exc}")
                continue
            for required in citation.required_text:
                if _normalise_required_text(required) not in source_text:
                    failures.append(
                        f"{scope}: {owner} source citation {citation.source_ref!r} missing text {required!r}"
                    )
        return failures

    @staticmethod
    def _validate_extraction_profile_artefacts(
        scope: str,
        profile: ExtractionProfileDefinition,
    ) -> list[str]:
        expected_by_surface = {
            "borrador_pdf": {"declaration_pdf"},
            "declaracion_pdf": {"declaration_pdf"},
            "justificante_pdf": {"justificante_pdf"},
            "export_record": {"submitted_file"},
            "official_workbook": {"official_workbook"},
        }
        expected = expected_by_surface[profile.surface]
        accepted = set(profile.accepted_artefact_kinds)
        failures: list[str] = []
        if accepted != expected:
            failures.append(
                f"{scope}: extraction profile {profile.id!r} accepts {sorted(accepted)!r}, "
                f"but surface {profile.surface!r} requires {sorted(expected)!r}"
            )
        if profile.surface == "justificante_pdf" and profile.target_casillas:
            failures.append(f"{scope}: extraction profile {profile.id!r} cannot use justificante PDFs as casilla data")
        return failures

    @staticmethod
    def _validate_dotted_callable(scope: str, owner: str, dotted_path: str) -> list[str]:
        module_name, separator, attribute = dotted_path.rpartition(".")
        if not separator or not module_name or not attribute:
            return [f"{scope}: {owner} parser {dotted_path!r} must be a dotted callable path"]
        try:
            module = import_module(module_name)
        except (ImportError, ValueError, SyntaxError) as exc:
            return [f"{scope}: {owner} parser {dotted_path!r} cannot import module {module_name!r}: {exc}"]
        try:
            resolved = getattr(module, attribute)
        except AttributeError as exc:
            return [f"{scope}: {owner} parser {dotted_path!r} does not resolve attribute {attribute!r}: {exc}"]
        if not callable(resolved):
            return [f"{scope}: {owner} parser {dotted_path!r} is not callable"]
        return []

    def _source_text(self, source: SourceReference) -> str:
        cached = self._source_text_cache.get(source.id)
        if cached is not None:
            return cached
        if self._source_root is None:
            return ""
        source_path = self._source_root / source.corpus_path
        stat = source_path.stat()
        source_key = (source.kind, str(source_path.expanduser().resolve()), stat.st_size, stat.st_mtime_ns)
        global_cached = _NORMALISED_SOURCE_TEXT_CACHE.get(source_key)
        if global_cached is not None and global_cached[0] == source_path:
            self._source_text_cache[source.id] = global_cached[1]
            return global_cached[1]
        if source.kind == "manual_pdf":
            text = _extract_pdf_text(source_path)
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        normalised = normalise_corpus_text(text)
        _NORMALISED_SOURCE_TEXT_CACHE[source_key] = (source_path, normalised)
        self._source_text_cache[source.id] = normalised
        return normalised

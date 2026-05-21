"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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
    DataBindingDefinition,
    FormulaDefinition,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
)
from ._sources import verify_source_catalogue
from ._validate_algorithms import validate_algorithm_binding_section, validate_algorithm_provider_section
from ._validate_application_links import validate_application_link_closure
from ._validate_constructs import validate_construct_closure, validate_support_removal_decisions
from ._validate_cross_revision import _validate_cross_revision_casilla_consistency
from ._validate_dependency_sections import (
    validate_dependency_classification_section,
    validate_filing_schedule_section,
    validate_relation_section,
)
from ._validate_evidence import EvidenceValidator
from ._validate_exports import validate_export_layout_section
from ._validate_extraction_profiles import validate_dotted_callable, validate_extraction_profile_artefacts
from ._validate_formulas import validate_formula_dag, validate_formula_expression
from ._validate_relation_sources import (
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
from ._validate_revision_rules import (
    validate_dated_values,
    validate_informative_class_invariant,
    validate_reconciliation_total_closure,
    validate_revision_windows,
)
from ._validate_semantic_roles import (
    _emit_semantic_role_typo_twin_warnings,
    _validate_required_role_declarations,
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
)
from ._validate_surfaces import (
    validate_application_link_section,
    validate_cross_reference_section,
    validate_deadline_window_section,
    validate_verification_expectation_section,
    validate_workbook_parity_section,
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
_CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
_MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
_REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}


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
        self._evidence = EvidenceValidator(
            legal_refs=self._legal,
            source_refs=self._sources,
            source_root=self._source_root,
        )
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
        failures.extend(validate_revision_windows(modelo))
        failures.extend(validate_informative_class_invariant(modelo))
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
        # The support-removal closure check below still
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
        validate_relation_section(
            failures,
            prefix=prefix,
            revision=revision,
            bindings=bindings,
            binding_by_id=binding_by_id,
            legal_refs=self._legal,
            source_refs=self._sources,
        )

        validate_dependency_classification_section(
            failures,
            prefix=prefix,
            revision=revision,
            construct_by_id=construct_by_id,
            relation_by_id=relation_by_id,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_filing_schedule_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_algorithm_provider_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_algorithm_binding_section(
            failures,
            prefix=prefix,
            revision=revision,
            providers=providers,
            casillas=casillas,
            resolvable_values=resolvable_values,
            parameters=parameters,
            legal_refs=self._legal,
            source_refs=self._sources,
        )

        validate_export_layout_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            bindings=bindings,
            casilla_by_id=casilla_by_id,
            legal_refs=self._legal,
            source_refs=self._sources,
            evidence=self._evidence,
        )
        self._validate_extraction_profile_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            exported_casillas=exported_casillas,
        )
        validate_cross_reference_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
            evidence=self._evidence,
        )
        validate_workbook_parity_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_verification_expectation_section(
            failures,
            prefix=prefix,
            revision=revision,
            casillas=casillas,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_application_link_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
        )
        validate_deadline_window_section(
            failures,
            prefix=prefix,
            revision=revision,
            legal_refs=self._legal,
            source_refs=self._sources,
        )

        failures.extend(
            validate_support_removal_decisions(
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
                legal_refs=self._legal,
                source_refs=self._sources,
            )
        )
        failures.extend(validate_application_link_closure(prefix, revision, modelo_id=modelo.id))
        failures.extend(validate_reconciliation_total_closure(prefix, revision))
        failures.extend(
            validate_construct_closure(
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
                legal_refs=self._legal,
                source_refs=self._sources,
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
            failures.extend(
                self._evidence.require_legal_authority_refs(prefix, f"formula {formula.id}", formula.legal_refs)
            )
            failures.extend(
                self._evidence.require_source_tier(
                    prefix,
                    f"formula {formula.id}",
                    formula.source_refs,
                    "official_source_guidance",
                )
            )
            failures.extend(
                self._evidence.validate_source_citations(
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
                self._evidence.require_legal_authority_refs(prefix, f"parameter {parameter.id}", parameter.legal_refs)
            )
            failures.extend(
                self._evidence.require_source_tier(
                    prefix,
                    f"parameter {parameter.id}",
                    parameter.source_refs,
                    "official_source_guidance",
                )
            )
            failures.extend(
                self._evidence.validate_source_citations(
                    prefix,
                    f"parameter {parameter.id}",
                    parameter.source_refs,
                    parameter.source_citations,
                    "official_source_guidance",
                )
            )
            failures.extend(validate_dated_values(prefix, parameter.id, parameter.values))

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
            failures.extend(
                self._evidence.require_legal_authority_refs(prefix, f"binding {binding.id}", binding.legal_refs)
            )
            if _is_layout_binding(binding):
                failures.extend(
                    self._evidence.require_source_tier(
                        prefix,
                        f"binding {binding.id}",
                        binding.source_refs,
                        "layout_authority",
                    )
                )
            else:
                failures.extend(
                    self._evidence.require_source_tier(
                        prefix,
                        f"binding {binding.id}",
                        binding.source_refs,
                        "official_source_guidance",
                    )
                )
                failures.extend(
                    self._evidence.validate_source_citations(
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
            failures.extend(validate_dotted_callable(prefix, owner, profile.parser))
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
            failures.extend(validate_extraction_profile_artefacts(prefix, profile))

    @staticmethod
    def _missing_refs(
        scope: str,
        owner: str,
        refs: Iterable[str],
        catalogue: Mapping[str, LegalReference] | Mapping[str, SourceReference],
        ref_kind: str,
    ) -> list[str]:
        return [f"{scope}: {owner} references unknown {ref_kind} id {ref!r}" for ref in refs if ref not in catalogue]

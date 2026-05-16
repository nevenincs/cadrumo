"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from graphlib import CycleError, TopologicalSorter
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
from ._runtime_graph import expression_casilla_refs
from ._schema import (
    DataBindingDefinition,
    DatedValue,
    ExtractionProfileDefinition,
    FormulaExpression,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
    RegistryCatalogues,
    RelationDefinition,
    SourceCitation,
    SourceReference,
)
from ._sources import verify_source_catalogue
from ._text import normalise_corpus_text

if TYPE_CHECKING:
    from ...user_profile._schema import ProfileSchemaDefinition
    from ._snapshot import RegistrySnapshot

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


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def _is_layout_binding(binding: DataBindingDefinition) -> bool:
    return {"record", "offset", "length", "data_type"}.issubset(binding.selector)


_COMMUNICATION_SURFACES = {"communication", "payer_delivery"}


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
            failures.extend(self._validate_relation_closure(modelo_tuple, modelos_by_id))
            failures.extend(self._validate_previous_filing_binding_closure(modelo_tuple, modelos_by_id))

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

        casilla_ids = [casilla.id for casilla in revision.casillas]
        formula_ids = [formula.id for formula in revision.formulas]
        binding_ids = [binding.id for binding in revision.bindings]
        relation_ids = [relation.id for relation in revision.relations]
        parameter_ids = [parameter.id for parameter in revision.parameters]
        provider_ids = [provider.id for provider in revision.algorithm_providers]
        algorithm_binding_ids = [binding.id for binding in revision.algorithm_bindings]
        export_layout_ids = [layout.id for layout in revision.export_layouts]
        extraction_profile_ids = [profile.id for profile in revision.extraction_profiles]
        cross_reference_ids = [cross_reference.id for cross_reference in revision.live_cross_references]
        workbook_parity_ids = [workbook.id for workbook in revision.workbook_parity_refs]
        verification_expectation_ids = [expectation.id for expectation in revision.verification_expectations]
        application_link_ids = [link.id for link in revision.application_links]
        deadline_window_ids = [window.id for window in revision.deadline_windows]
        filing_schedule_ids = [schedule.id for schedule in revision.filing_schedules]
        support_removal_decision_ids = [decision.id for decision in revision.support_removal_decisions]
        construct_ids = [construct.id for construct in revision.constructs]
        dependency_classification_ids = [classification.id for classification in revision.dependency_classifications]
        if not workbook_parity_ids:
            failures.append(f"{prefix}: revision must declare official workbook parity coverage")
        for kind, ids in (
            ("casilla", casilla_ids),
            ("formula", formula_ids),
            ("binding", binding_ids),
            ("relation", relation_ids),
            ("parameter", parameter_ids),
            ("algorithm provider", provider_ids),
            ("algorithm binding", algorithm_binding_ids),
            ("export layout", export_layout_ids),
            ("extraction profile", extraction_profile_ids),
            ("cross-reference", cross_reference_ids),
            ("workbook parity reference", workbook_parity_ids),
            ("verification expectation", verification_expectation_ids),
            ("application link", application_link_ids),
            ("deadline window", deadline_window_ids),
            ("filing schedule", filing_schedule_ids),
            ("support removal decision", support_removal_decision_ids),
            ("construct", construct_ids),
            ("dependency classification", dependency_classification_ids),
        ):
            for duplicate in sorted(_duplicates(ids)):
                failures.append(f"{prefix}: duplicate {kind} id {duplicate!r}")

        primary_ids = (
            casilla_ids
            + formula_ids
            + binding_ids
            + relation_ids
            + parameter_ids
            + algorithm_binding_ids
            + export_layout_ids
            + extraction_profile_ids
            + cross_reference_ids
            + workbook_parity_ids
            + verification_expectation_ids
            + application_link_ids
            + deadline_window_ids
            + filing_schedule_ids
            + support_removal_decision_ids
            + construct_ids
            + dependency_classification_ids
        )
        for duplicate in sorted(_duplicates(primary_ids)):
            failures.append(f"{prefix}: duplicate registry id {duplicate!r}")

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

        casillas = set(casilla_by_id)
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
                self._validate_formula_expression(
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
            if binding.source == "invoice":
                try:
                    validate_invoice_binding_definition(binding)
                except RegistryValidationError as exc:
                    failures.append(f"{prefix}: {exc}")
            if binding.source == "ledger_oss_aggregation":
                try:
                    validate_ledger_oss_aggregation_binding_definition(binding)
                except RegistryValidationError as exc:
                    failures.append(f"{prefix}: {exc}")
            if binding.source == "ledger_iva_aggregation":
                try:
                    validate_ledger_iva_aggregation_binding_definition(binding)
                except RegistryValidationError as exc:
                    failures.append(f"{prefix}: {exc}")
            if binding.source == "ledger_renta_expense_aggregation":
                try:
                    validate_ledger_renta_expense_aggregation_binding_definition(binding)
                except RegistryValidationError as exc:
                    failures.append(f"{prefix}: {exc}")

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

        for classification in revision.dependency_classifications:
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"dependency classification {classification.id}",
                    classification.legal_refs,
                    self._legal,
                    "legal",
                )
            )
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"dependency classification {classification.id}",
                    classification.source_refs,
                    self._sources,
                    "source",
                )
            )
            for construct_id in classification.target_constructs:
                construct = construct_by_id.get(construct_id)
                if construct is None:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} references unknown construct "
                        f"{construct_id!r}"
                    )
                    continue
                if classification.id not in construct.dependency_classifications:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} targets construct "
                        f"{construct_id!r} but the construct does not list it"
                    )
            for relation_id in classification.relation_refs:
                relation = relation_by_id.get(relation_id)
                if relation is None:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} references unknown relation "
                        f"{relation_id!r}"
                    )
                    continue
                if relation.source_modelo != classification.source_modelo:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} source_modelo "
                        f"{classification.source_modelo!r} does not match relation {relation_id!r} source_modelo "
                        f"{relation.source_modelo!r}"
                    )
                missing_legal_refs = sorted(set(relation.legal_refs).difference(classification.legal_refs))
                if missing_legal_refs:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} relation {relation_id!r} "
                        f"does not include relation legal refs {missing_legal_refs!r}"
                    )
                missing_source_refs = sorted(set(relation.source_refs).difference(classification.source_refs))
                if missing_source_refs:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} relation {relation_id!r} "
                        f"does not include relation source refs {missing_source_refs!r}"
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
                failures.extend(
                    self._missing_refs(
                        prefix,
                        f"filing schedule {schedule.id} condition {condition.field}",
                        condition.legal_refs,
                        self._legal,
                        "legal",
                    )
                )
                failures.extend(
                    self._missing_refs(
                        prefix,
                        f"filing schedule {schedule.id} condition {condition.field}",
                        condition.source_refs,
                        self._sources,
                        "source",
                    )
                )

        for provider in revision.algorithm_providers:
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"algorithm provider {provider.id}",
                    provider.legal_refs,
                    self._legal,
                    "legal",
                )
            )
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"algorithm provider {provider.id}",
                    provider.source_refs,
                    self._sources,
                    "source",
                )
            )

        for algorithm_binding in revision.algorithm_bindings:
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"algorithm binding {algorithm_binding.id}",
                    algorithm_binding.legal_refs,
                    self._legal,
                    "legal",
                )
            )
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"algorithm binding {algorithm_binding.id}",
                    algorithm_binding.source_refs,
                    self._sources,
                    "source",
                )
            )
            if algorithm_binding.provider not in providers:
                failures.append(
                    f"{prefix}: algorithm binding {algorithm_binding.id!r} references unknown provider "
                    f"{algorithm_binding.provider!r}"
                )
            if algorithm_binding.target not in casillas:
                failures.append(
                    f"{prefix}: algorithm binding {algorithm_binding.id!r} targets unknown casilla "
                    f"{algorithm_binding.target!r}"
                )
            for input_name, input_value in algorithm_binding.inputs.items():
                if input_value not in resolvable_values:
                    failures.append(
                        f"{prefix}: algorithm binding {algorithm_binding.id!r} input {input_name!r} "
                        f"references unknown value {input_value!r}"
                    )
            for output_name, output_value in algorithm_binding.outputs.items():
                if output_value not in casillas:
                    failures.append(
                        f"{prefix}: algorithm binding {algorithm_binding.id!r} output {output_name!r} "
                        f"references unknown casilla {output_value!r}"
                    )
            for constant in algorithm_binding.constants:
                if constant not in parameters:
                    failures.append(
                        f"{prefix}: algorithm binding {algorithm_binding.id!r} references unknown constant {constant!r}"
                    )

        for layout in revision.export_layouts:
            failures.extend(self._missing_refs(prefix, f"export {layout.id}", layout.legal_refs, self._legal, "legal"))
            failures.extend(
                self._missing_refs(prefix, f"export {layout.id}", layout.source_refs, self._sources, "source")
            )
            failures.extend(
                self._require_source_tier(prefix, f"export {layout.id}", layout.source_refs, "layout_authority")
            )
            for record in layout.records:
                if record.binding_record is not None:
                    matching_bindings = [
                        binding
                        for binding in revision.bindings
                        if binding.selector.get("record") == record.binding_record
                    ]
                    if not matching_bindings:
                        failures.append(
                            f"{prefix}: export record {record.id!r} derives fields from unknown binding record "
                            f"{record.binding_record!r}"
                        )
                    for binding in matching_bindings:
                        # Row-producer bindings (aggregation.op == "rows") source their
                        # byte coordinates from explicit export-field offsets, not from
                        # the binding selector itself.
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
                    failures.extend(
                        self._missing_refs(prefix, f"export field {field.id}", field.legal_refs, self._legal, "legal")
                    )
                    failures.extend(
                        self._missing_refs(
                            prefix, f"export field {field.id}", field.source_refs, self._sources, "source"
                        )
                    )
                    if field.casilla is not None and field.casilla not in casillas:
                        failures.append(
                            f"{prefix}: export field {field.id!r} references unknown casilla {field.casilla!r}"
                        )
                    if (
                        field.casilla is not None
                        and field.casilla in casilla_by_id
                        and field.id not in casilla_by_id[field.casilla].export_refs
                    ):
                        failures.append(
                            f"{prefix}: export field {field.id!r} is not declared by casilla {field.casilla!r}"
                        )
                    if field.binding is not None and field.binding not in bindings:
                        failures.append(
                            f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}"
                        )

        for profile in revision.extraction_profiles:
            failures.extend(
                self._missing_refs(prefix, f"extraction profile {profile.id}", profile.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(
                    prefix, f"extraction profile {profile.id}", profile.source_refs, self._sources, "source"
                )
            )
            failures.extend(self._validate_dotted_callable(prefix, f"extraction profile {profile.id}", profile.parser))
            for casilla_id in profile.target_casillas:
                if casilla_id not in casillas:
                    failures.append(
                        f"{prefix}: extraction profile {profile.id!r} references unknown casilla {casilla_id!r}"
                    )
            if profile.surface == "export_record" or "submitted_file" in profile.accepted_artefact_kinds:
                missing_exported_casillas = sorted(set(profile.target_casillas).difference(exported_casillas))
                if missing_exported_casillas:
                    failures.append(
                        f"{prefix}: export_record extraction profile {profile.id!r} targets casillas without "
                        f"export fields {missing_exported_casillas!r}"
                    )
            failures.extend(self._validate_extraction_profile_artefacts(prefix, profile))

        oracle_bindings: dict[str, str] = {}
        for cross_reference in revision.live_cross_references:
            failures.extend(
                self._missing_refs(
                    prefix, f"cross-reference {cross_reference.id}", cross_reference.legal_refs, self._legal, "legal"
                )
            )
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"cross-reference {cross_reference.id}",
                    cross_reference.source_refs,
                    self._sources,
                    "source",
                )
            )
            failures.extend(
                self._require_source_tier(
                    prefix,
                    f"cross-reference {cross_reference.id}",
                    cross_reference.source_refs,
                    cross_reference.evidence_tier,
                )
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

        for workbook in revision.workbook_parity_refs:
            failures.extend(
                self._missing_refs(prefix, f"workbook parity {workbook.id}", workbook.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(
                    prefix, f"workbook parity {workbook.id}", workbook.source_refs, self._sources, "source"
                )
            )
            if workbook.workbook_source not in self._sources:
                failures.append(
                    f"{prefix}: workbook parity {workbook.id!r} references unknown source {workbook.workbook_source!r}"
                )
            else:
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

        for expectation in revision.verification_expectations:
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"verification expectation {expectation.id}",
                    expectation.legal_refs,
                    self._legal,
                    "legal",
                )
            )
            failures.extend(
                self._missing_refs(
                    prefix,
                    f"verification expectation {expectation.id}",
                    expectation.source_refs,
                    self._sources,
                    "source",
                )
            )
            for casilla_id in expectation.computed_casillas:
                if casilla_id not in casillas:
                    failures.append(
                        f"{prefix}: verification expectation {expectation.id!r} references unknown casilla "
                        f"{casilla_id!r}"
                    )
            for total_kind, casilla_id in expectation.reconciliation_totals.items():
                if casilla_id not in casillas:
                    failures.append(
                        f"{prefix}: verification expectation {expectation.id!r} reconciliation total "
                        f"{total_kind!r} references unknown casilla {casilla_id!r}"
                    )
                if casilla_id not in expectation.computed_casillas:
                    failures.append(
                        f"{prefix}: verification expectation {expectation.id!r} reconciliation total "
                        f"{total_kind!r} must be one of computed_casillas"
                    )

        for link in revision.application_links:
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.source_refs, self._sources, "source")
            )

        for window in revision.deadline_windows:
            failures.extend(
                self._missing_refs(prefix, f"deadline window {window.id}", window.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"deadline window {window.id}", window.source_refs, self._sources, "source")
            )
            for condition in window.applicability_conditions:
                failures.extend(
                    self._missing_refs(
                        prefix,
                        f"deadline condition for {window.id}",
                        condition.legal_refs,
                        self._legal,
                        "legal",
                    )
                )
                failures.extend(
                    self._missing_refs(
                        prefix,
                        f"deadline condition for {window.id}",
                        condition.source_refs,
                        self._sources,
                        "source",
                    )
                )

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
        failures.extend(self._validate_application_link_closure(prefix, revision, modelo_id=modelo.id))
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
        failures.extend(self._validate_formula_dag(prefix, revision))
        return failures

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
            ) and RegistryValidator._period_selectors_overlap(previous.period_selector, current.period_selector):
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
    def _validate_relation_closure(
        modelos: Iterable[ModeloDefinition],
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        for modelo in modelos:
            for revision in modelo.revisions.values():
                prefix = f"modelo {modelo.id} revision {revision.id}"
                for relation in revision.relations:
                    failures.extend(
                        RegistryValidator._validate_single_relation(
                            relation,
                            revision=revision,
                            relation_scope=f"{prefix}: relation {relation.id!r}",
                            modelos_by_id=modelos_by_id,
                        )
                    )
        return failures

    @staticmethod
    def _validate_single_relation(
        relation: RelationDefinition,
        *,
        revision: ModeloRevision,
        relation_scope: str,
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        source_modelo = modelos_by_id.get(relation.source_modelo)
        if source_modelo is None:
            failures.append(f"{relation_scope} references unknown source modelo {relation.source_modelo!r}")
            return failures
        if not relation.source_periods:
            failures.append(f"{relation_scope} must declare source periods")
        if not relation.target_periods:
            failures.append(f"{relation_scope} must declare target periods")
        aggregation = relation.aggregation or {"op": "copy"}
        op = aggregation.get("op")
        if op not in {"copy", "sum"}:
            failures.append(f"{relation_scope} uses unsupported aggregation op {op!r}")
        source_revisions, selector_failures = RegistryValidator._select_relation_source_revisions(
            source_modelo,
            relation.source_revision_selector,
        )
        failures.extend(f"{relation_scope} {failure}" for failure in selector_failures)
        if not source_revisions:
            failures.append(
                f"{relation_scope} selector {dict(relation.source_revision_selector)!r} "
                f"matches no source revisions in modelo {source_modelo.id}"
            )
            return failures
        for source_revision in source_revisions:
            failures.extend(
                RegistryValidator._validate_relation_source_revision(
                    relation,
                    source_revision=source_revision,
                    relation_scope=relation_scope,
                )
            )
        failures.extend(
            RegistryValidator._validate_source_year_coverage(
                relation_scope,
                target_selector=revision.period_selector,
                source_revisions=source_revisions,
                source_periods=relation.source_periods,
                filing_year_delta=RegistryValidator._relation_filing_year_delta(
                    relation.source_revision_selector
                ),
                fixed_source_year=RegistryValidator._relation_fixed_source_year(
                    relation.source_revision_selector
                ),
            )
        )
        return failures

    @staticmethod
    def _validate_relation_source_revision(
        relation: RelationDefinition,
        *,
        source_revision: ModeloRevision,
        relation_scope: str,
    ) -> list[str]:
        failures: list[str] = []
        source_scope = f"{relation_scope} source revision {source_revision.id!r}"
        source_values = RegistryValidator._revision_output_ids(source_revision)
        if relation.source_output not in source_values:
            failures.append(f"{source_scope} has no source output {relation.source_output!r}")
        unknown_source_periods = sorted(
            set(relation.source_periods).difference(source_revision.period_selector.periods)
        )
        if unknown_source_periods:
            failures.append(
                f"{source_scope} does not support source periods {unknown_source_periods!r}"
            )
        return failures

    @staticmethod
    def _validate_previous_filing_binding_closure(
        modelos: Iterable[ModeloDefinition],
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        for modelo in modelos:
            for revision in modelo.revisions.values():
                prefix = f"modelo {modelo.id} revision {revision.id}"
                for binding in revision.bindings:
                    if binding.source != "previous_filing":
                        continue
                    failures.extend(
                        RegistryValidator._validate_previous_filing_binding(
                            binding,
                            binding_scope=f"{prefix}: binding {binding.id!r}",
                            modelos_by_id=modelos_by_id,
                        )
                    )
        return failures

    @staticmethod
    def _validate_previous_filing_binding(
        binding: DataBindingDefinition,
        *,
        binding_scope: str,
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        source_modelo_id = binding.selector.get("source_modelo")
        if not isinstance(source_modelo_id, str):
            failures.append(f"{binding_scope} must declare string selector source_modelo")
            return failures
        source_modelo = modelos_by_id.get(source_modelo_id)
        if source_modelo is None:
            failures.append(f"{binding_scope} references unknown source modelo {source_modelo_id!r}")
            return failures

        source_periods = RegistryValidator._binding_source_periods(binding)
        matching_revisions = tuple(
            source_revision
            for source_revision in source_modelo.revisions.values()
            if not source_periods
            or set(source_periods).issubset(set(source_revision.period_selector.periods))
        )
        if not matching_revisions:
            failures.append(
                f"{binding_scope} matches no source revisions in modelo {source_modelo.id} "
                f"for periods {source_periods!r}"
            )
            return failures

        source_outputs = RegistryValidator._binding_source_outputs(binding)
        if not source_outputs:
            return failures

        revision_outputs = set().union(
            *(
                RegistryValidator._revision_output_ids(source_revision)
                for source_revision in matching_revisions
            )
        )
        for source_output in source_outputs:
            if source_output not in revision_outputs:
                failures.append(
                    f"{binding_scope} source output {source_output!r} is not defined by any "
                    f"period-compatible {source_modelo.id} revision"
                )
        return failures

    @staticmethod
    def _binding_source_periods(binding: DataBindingDefinition) -> tuple[str, ...]:
        source_periods = binding.selector.get("source_periods")
        if isinstance(source_periods, tuple) and all(isinstance(period, str) for period in source_periods):
            return source_periods
        period = binding.selector.get("period")
        if isinstance(period, str):
            return (period,)
        return ()

    @staticmethod
    def _binding_source_outputs(binding: DataBindingDefinition) -> tuple[str, ...]:
        source_casillas = binding.selector.get("source_casillas")
        if isinstance(source_casillas, tuple) and all(isinstance(casilla, str) for casilla in source_casillas):
            return source_casillas
        source_output = binding.selector.get("source_output")
        if isinstance(source_output, str):
            return (source_output,)
        return ()

    @staticmethod
    def _revision_output_ids(revision: ModeloRevision) -> set[str]:
        outputs = {casilla.id for casilla in revision.casillas}
        outputs.update(binding.id for binding in revision.bindings)
        outputs.update(output for binding in revision.algorithm_bindings for output in binding.outputs.values())
        return outputs

    @staticmethod
    def _select_relation_source_revisions(
        modelo: ModeloDefinition,
        selector: Mapping[str, str | int],
    ) -> tuple[tuple[ModeloRevision, ...], list[str]]:
        allowed = {"revision", "revision_id", "year", "year_from", "year_to", "filing_year_delta"}
        failures = [f"selector uses unknown key {key!r}" for key in sorted(set(selector).difference(allowed))]
        revision_id = selector.get("revision_id", selector.get("revision"))
        year = selector.get("year")
        year_from = selector.get("year_from")
        year_to = selector.get("year_to")

        if revision_id is not None and not isinstance(revision_id, str):
            failures.append("selector revision_id must be a string")
        for key, value in (("year", year), ("year_from", year_from), ("year_to", year_to)):
            if value is not None and not isinstance(value, int):
                failures.append(f"selector {key} must be an integer")
        delta = selector.get("filing_year_delta")
        if delta is not None and not isinstance(delta, int):
            failures.append("selector filing_year_delta must be an integer")
        if year is not None and (year_from is not None or year_to is not None):
            failures.append("selector must use year or year_from/year_to, not both")
        if year_to is not None and year_from is None:
            failures.append("selector year_to requires year_from")
        if isinstance(year_from, int) and isinstance(year_to, int) and year_to < year_from:
            failures.append("selector year_to must be on or after year_from")

        selected: list[ModeloRevision] = []
        for revision in modelo.revisions.values():
            if isinstance(revision_id, str) and revision.id != revision_id:
                continue
            if isinstance(year, int) and not revision.period_selector.includes_year(year):
                continue
            if isinstance(year_from, int) and not RegistryValidator._revision_intersects_year_range(
                revision,
                year_from=year_from,
                year_to=year_to if isinstance(year_to, int) else None,
            ):
                continue
            selected.append(revision)
        return tuple(selected), failures

    @staticmethod
    def _relation_filing_year_delta(selector: Mapping[str, str | int]) -> int:
        if "year" in selector:
            return 0
        delta = selector.get("filing_year_delta", 0)
        if isinstance(delta, int):
            return delta
        return 0

    @staticmethod
    def _relation_fixed_source_year(selector: Mapping[str, str | int]) -> int | None:
        year = selector.get("year")
        if isinstance(year, int):
            return year
        return None

    @staticmethod
    def _validate_source_year_coverage(
        scope: str,
        *,
        target_selector: PeriodSelector,
        source_revisions: Iterable[ModeloRevision],
        source_periods: Iterable[str],
        filing_year_delta: int,
        fixed_source_year: int | None = None,
    ) -> list[str]:
        if fixed_source_year is None:
            required_intervals = tuple(
                (start + filing_year_delta, None if end is None else end + filing_year_delta)
                for start, end in RegistryValidator._selector_year_intervals(target_selector)
            )
        else:
            required_intervals = ((fixed_source_year, fixed_source_year),)
        source_period_set = set(source_periods)
        covered_intervals = tuple(
            interval
            for source_revision in source_revisions
            if not source_period_set or source_period_set.issubset(set(source_revision.period_selector.periods))
            for interval in RegistryValidator._selector_year_intervals(source_revision.period_selector)
        )
        failures: list[str] = []
        for start, end in required_intervals:
            if not RegistryValidator._interval_is_covered(start, end, covered_intervals):
                if end is None:
                    failures.append(f"{scope} lacks source revision year coverage from {start}")
                elif start == end:
                    failures.append(f"{scope} lacks source revision year coverage for {start}")
                else:
                    failures.append(f"{scope} lacks source revision year coverage for {start}-{end}")
        return failures

    @staticmethod
    def _selector_year_intervals(selector: PeriodSelector) -> tuple[tuple[int, int | None], ...]:
        if selector.years:
            return tuple((year, year) for year in sorted(selector.years))
        if selector.year_from is None:
            return ()
        return ((selector.year_from, selector.year_to),)

    @staticmethod
    def _interval_is_covered(
        start: int,
        end: int | None,
        intervals: Iterable[tuple[int, int | None]],
    ) -> bool:
        remaining_start = start
        for covered_start, covered_end in sorted(intervals, key=lambda item: item[0]):
            if covered_start > remaining_start:
                continue
            if covered_end is None:
                return True
            if covered_end < remaining_start:
                continue
            remaining_start = covered_end + 1
            if end is not None and remaining_start > end:
                return True
        return False if end is None else remaining_start > end

    @staticmethod
    def _revision_intersects_year_range(
        revision: ModeloRevision,
        *,
        year_from: int,
        year_to: int | None,
    ) -> bool:
        if revision.period_selector.years:
            return any(
                year >= year_from and (year_to is None or year <= year_to) for year in revision.period_selector.years
            )
        revision_from = revision.period_selector.year_from
        if revision_from is None:
            return False
        revision_to = revision.period_selector.year_to
        if revision_to is not None and revision_to < year_from:
            return False
        return not (year_to is not None and revision_from > year_to)

    @staticmethod
    def _period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
        if not set(left.periods).intersection(right.periods):
            return False
        return RegistryValidator._year_selectors_overlap(left, right)

    @staticmethod
    def _year_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
        if left.years and right.years:
            return bool(set(left.years).intersection(right.years))
        if left.years:
            return any(right.includes_year(year) for year in left.years)
        if right.years:
            return any(left.includes_year(year) for year in right.years)
        left_from = left.year_from
        right_from = right.year_from
        if left_from is None or right_from is None:
            return False
        left_to = left.year_to
        right_to = right.year_to
        if left_to is not None and left_to < right_from:
            return False
        return not (right_to is not None and right_to < left_from)

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
    def _validate_formula_dag(scope: str, revision: ModeloRevision) -> list[str]:
        formula_targets = {formula.target for formula in revision.formulas}
        sorter: TopologicalSorter[str] = TopologicalSorter()
        for formula in revision.formulas:
            dependencies = [
                casilla for casilla in expression_casilla_refs(formula.expression) if casilla in formula_targets
            ]
            sorter.add(formula.target, *dependencies)
        try:
            tuple(sorter.static_order())
        except CycleError as exc:
            return [f"{scope}: formula graph cycle: {exc}"]
        return []

    @staticmethod
    def _validate_application_link_closure(
        scope: str,
        revision: ModeloRevision,
        *,
        modelo_id: str,
    ) -> list[str]:
        surfaces = {link.surface for link in revision.application_links}
        communication_surfaces = surfaces.intersection(_COMMUNICATION_SURFACES)
        modelo_requires_communication = modelo_id == "145"
        failures = RegistryValidator._application_link_surface_failures(
            scope,
            revision,
            surfaces=surfaces,
            communication_surfaces=communication_surfaces,
            modelo_requires_communication=modelo_requires_communication,
        )
        if communication_surfaces or modelo_requires_communication:
            failures.extend(
                RegistryValidator._application_link_communication_failures(
                    scope,
                    revision,
                    surfaces=surfaces,
                )
            )
        return failures

    @staticmethod
    def _application_link_surface_failures(
        scope: str,
        revision: ModeloRevision,
        *,
        surfaces: set[str],
        communication_surfaces: set[str],
        modelo_requires_communication: bool,
    ) -> list[str]:
        failures: list[str] = []
        if revision.formulas and "calculation" not in surfaces:
            failures.append(f"{scope}: formulas require a calculation application link")
        if revision.extraction_profiles and "extractor" not in surfaces:
            failures.append(f"{scope}: extraction profiles require an extractor application link")
        if revision.export_layouts and "export" not in surfaces:
            failures.append(f"{scope}: export layouts require an export application link")
        if revision.verification_expectations and "verification" not in surfaces:
            failures.append(f"{scope}: verification expectations require a verification application link")
        casillas_have_lifecycle_link = "filing" in surfaces or (
            modelo_requires_communication and bool(communication_surfaces)
        )
        if revision.casillas and not casillas_have_lifecycle_link:
            failures.append(f"{scope}: casillas require a filing or communication application link")
        if communication_surfaces and not modelo_requires_communication:
            failures.append(f"{scope}: communication application links are only valid for Modelo 145")
        if revision.live_cross_references and "portal" not in surfaces:
            failures.append(f"{scope}: live/static cross-references require a portal application link")
        if revision.deadline_windows and "deadline" not in surfaces:
            failures.append(f"{scope}: deadline windows require a deadline application link")
        if modelo_requires_communication and not communication_surfaces:
            failures.append(f"{scope}: Modelo 145 requires a communication application link")
        return failures

    @staticmethod
    def _application_link_communication_failures(
        scope: str,
        revision: ModeloRevision,
        *,
        surfaces: set[str],
    ) -> list[str]:
        failures: list[str] = []
        if "filing" in surfaces:
            failures.append(f"{scope}: communication application links must not be combined with filing")
        if "deadline" in surfaces or revision.deadline_windows:
            failures.append(f"{scope}: communication application links must not declare deadline surfaces")
        if "portal" in surfaces or revision.live_cross_references:
            failures.append(f"{scope}: communication application links must not declare live or portal surfaces")
        if revision.filing_schedules:
            failures.append(f"{scope}: communication application links must not declare filing schedules")
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
        except AttributeError:
            return [f"{scope}: {owner} parser {dotted_path!r} does not resolve attribute {attribute!r}"]
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

    @classmethod
    def _validate_formula_expression(
        cls,
        scope: str,
        formula_id: str,
        expression: FormulaExpression,
        *,
        casillas: set[str],
        bindings: set[str],
        parameters: set[str],
        relations: set[str],
    ) -> list[str]:
        failures: list[str] = []
        if expression.casilla is not None and expression.casilla not in casillas:
            failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla!r}")
        if expression.binding is not None and expression.binding not in bindings:
            failures.append(f"{scope}: formula {formula_id!r} references unknown binding {expression.binding!r}")
        if expression.parameter is not None and expression.parameter not in parameters:
            failures.append(f"{scope}: formula {formula_id!r} references unknown parameter {expression.parameter!r}")
        if expression.dispatch_table:
            for key, dispatched in expression.dispatch_table.items():
                if dispatched not in parameters:
                    failures.append(
                        f"{scope}: formula {formula_id!r} dispatch_table[{key!r}] "
                        f"references unknown parameter {dispatched!r}"
                    )
        if expression.relation is not None and expression.relation not in relations:
            failures.append(f"{scope}: formula {formula_id!r} references unknown relation {expression.relation!r}")
        for arg in expression.args:
            failures.extend(
                cls._validate_formula_expression(
                    scope,
                    formula_id,
                    arg,
                    casillas=casillas,
                    bindings=bindings,
                    parameters=parameters,
                    relations=relations,
                )
            )
        return failures


def _check_all_id_references(snapshot: RegistrySnapshot) -> None:
    """Assert every typed-ID reference in the snapshot points at an existing entity.

    Walks all 21 typed-ID reference fields across the snapshot's revision and
    raises :class:`RegistryValidationError` listing every dangling reference.
    This is an existence gate only -- it does not alter any field types.

    For union fields declared as ``TypedId | str`` (where the bare-``str``
    arm is a legacy escape), the value is treated as a candidate typed-ID
    and checked regardless of which arm is active.
    """
    revision = snapshot.revision
    prefix = f"snapshot modelo {snapshot.modelo.id} revision {revision.id}"
    failures: list[str] = []

    casilla_ids: set[str] = {c.id for c in revision.casillas}
    formula_ids: set[str] = {f.id for f in revision.formulas}
    parameter_ids: set[str] = {p.id for p in revision.parameters}
    binding_ids: set[str] = {b.id for b in revision.bindings}
    relation_ids: set[str] = {r.id for r in revision.relations}
    export_layout_ids: set[str] = {lay.id for lay in revision.export_layouts}
    export_field_ids: set[str] = {
        field.id for lay in revision.export_layouts for rec in lay.records for field in rec.fields
    }
    extraction_profile_ids: set[str] = {p.id for p in revision.extraction_profiles}
    cross_reference_ids: set[str] = {cr.id for cr in revision.live_cross_references}
    workbook_parity_ids: set[str] = {w.id for w in revision.workbook_parity_refs}
    verification_expectation_ids: set[str] = {e.id for e in revision.verification_expectations}
    application_link_ids: set[str] = {lk.id for lk in revision.application_links}
    deadline_window_ids: set[str] = {dw.id for dw in revision.deadline_windows}
    support_removal_decision_ids: set[str] = {d.id for d in revision.support_removal_decisions}
    construct_ids: set[str] = {c.id for c in revision.constructs}
    dependency_classification_ids: set[str] = {dc.id for dc in revision.dependency_classifications}
    legal_ids: set[str] = set(snapshot.legal)
    source_ids: set[str] = set(snapshot.sources)

    def _chk(field_path: str, value: str, id_set: set[str]) -> None:
        if value not in id_set:
            failures.append(f"{prefix}: {field_path} references unknown id {value!r}")

    def _chk_opt(field_path: str, value: str | None, id_set: set[str]) -> None:
        if value is not None and value not in id_set:
            failures.append(f"{prefix}: {field_path} references unknown id {value!r}")

    def _chk_tuple(field_path: str, values: tuple[str, ...], id_set: set[str]) -> None:
        for value in values:
            if value not in id_set:
                failures.append(f"{prefix}: {field_path} references unknown id {value!r}")

    # ModeloDefinition top-level refs
    _chk_tuple("modelo.legal_refs", snapshot.modelo.legal_refs, legal_ids)
    _chk_tuple("modelo.source_refs", snapshot.modelo.source_refs, source_ids)

    # ModeloRevision top-level refs
    _chk_tuple("revision.legal_refs", revision.legal_refs, legal_ids)
    _chk_tuple("revision.source_refs", revision.source_refs, source_ids)

    # CasillaId references
    for casilla in revision.casillas:
        cp = f"casilla {casilla.id}"
        _chk_opt(f"{cp}.formula", casilla.formula, formula_ids)
        _chk_opt(f"{cp}.binding", casilla.binding, binding_ids)
        _chk_tuple(f"{cp}.export_refs", casilla.export_refs, export_field_ids)
        _chk_tuple(f"{cp}.legal_refs", casilla.legal_refs, legal_ids)
        _chk_tuple(f"{cp}.source_refs", casilla.source_refs, source_ids)
        if casilla.constraints is not None:
            _chk_tuple(f"{cp}.constraints.legal_refs", casilla.constraints.legal_refs, legal_ids)
            _chk_tuple(f"{cp}.constraints.source_refs", casilla.constraints.source_refs, source_ids)

    # FormulaId references
    for formula in revision.formulas:
        fp = f"formula {formula.id}"
        _chk(f"{fp}.target", formula.target, casilla_ids)
        _chk_tuple(f"{fp}.legal_refs", formula.legal_refs, legal_ids)
        _chk_tuple(f"{fp}.source_refs", formula.source_refs, source_ids)
        for citation in formula.source_citations:
            _chk(f"{fp}.source_citations.{citation.source_ref}", citation.source_ref, source_ids)

    # ParameterId references
    for parameter in revision.parameters:
        pp = f"parameter {parameter.id}"
        _chk_tuple(f"{pp}.legal_refs", parameter.legal_refs, legal_ids)
        _chk_tuple(f"{pp}.source_refs", parameter.source_refs, source_ids)
        for citation in parameter.source_citations:
            _chk(f"{pp}.source_citations.{citation.source_ref}", citation.source_ref, source_ids)

    # BindingId references
    for binding in revision.bindings:
        bp = f"binding {binding.id}"
        _chk_tuple(f"{bp}.legal_refs", binding.legal_refs, legal_ids)
        _chk_tuple(f"{bp}.source_refs", binding.source_refs, source_ids)
        for citation in binding.source_citations:
            _chk(f"{bp}.source_citations.{citation.source_ref}", citation.source_ref, source_ids)

    # RelationId references
    for relation in revision.relations:
        rp = f"relation {relation.id}"
        _chk(f"{rp}.target_binding", relation.target_binding, binding_ids)
        _chk_tuple(f"{rp}.legal_refs", relation.legal_refs, legal_ids)
        _chk_tuple(f"{rp}.source_refs", relation.source_refs, source_ids)
        # source_output is CasillaId | str; cross-model outputs are not in this
        # snapshot's casilla set -- checked at registry-validate time instead.

    # ExtractionProfileId references
    for profile in revision.extraction_profiles:
        ep = f"extraction_profile {profile.id}"
        _chk_tuple(f"{ep}.target_casillas", profile.target_casillas, casilla_ids)
        _chk_tuple(f"{ep}.legal_refs", profile.legal_refs, legal_ids)
        _chk_tuple(f"{ep}.source_refs", profile.source_refs, source_ids)

    # CrossReferenceId references
    for cross_ref in revision.live_cross_references:
        crp = f"cross_reference {cross_ref.id}"
        _chk_tuple(f"{crp}.legal_refs", cross_ref.legal_refs, legal_ids)
        _chk_tuple(f"{crp}.source_refs", cross_ref.source_refs, source_ids)
        for pred in cross_ref.applicability_predicates:
            _chk_tuple(f"{crp}.applicability_predicates.{pred.field}.legal_refs", pred.legal_refs, legal_ids)
            _chk_tuple(f"{crp}.applicability_predicates.{pred.field}.source_refs", pred.source_refs, source_ids)

    # WorkbookParityRefId references
    for workbook in revision.workbook_parity_refs:
        wp = f"workbook_parity_ref {workbook.id}"
        _chk(f"{wp}.workbook_source", workbook.workbook_source, source_ids)
        _chk_tuple(f"{wp}.legal_refs", workbook.legal_refs, legal_ids)
        _chk_tuple(f"{wp}.source_refs", workbook.source_refs, source_ids)

    # VerificationExpectationId references
    for expectation in revision.verification_expectations:
        vep = f"verification_expectation {expectation.id}"
        _chk_tuple(f"{vep}.computed_casillas", expectation.computed_casillas, casilla_ids)
        for total_kind, casilla_id in expectation.reconciliation_totals.items():
            _chk(f"{vep}.reconciliation_totals.{total_kind}", casilla_id, casilla_ids)
        _chk_tuple(f"{vep}.legal_refs", expectation.legal_refs, legal_ids)
        _chk_tuple(f"{vep}.source_refs", expectation.source_refs, source_ids)

    # ApplicationLinkId references
    for link in revision.application_links:
        lp = f"application_link {link.id}"
        _chk_tuple(f"{lp}.legal_refs", link.legal_refs, legal_ids)
        _chk_tuple(f"{lp}.source_refs", link.source_refs, source_ids)

    # DeadlineWindowId references
    for window in revision.deadline_windows:
        dwp = f"deadline_window {window.id}"
        _chk_tuple(f"{dwp}.legal_refs", window.legal_refs, legal_ids)
        _chk_tuple(f"{dwp}.source_refs", window.source_refs, source_ids)
        for condition in window.applicability_conditions:
            _chk_tuple(f"{dwp}.applicability_conditions.{condition.field}.legal_refs", condition.legal_refs, legal_ids)
            _chk_tuple(
                f"{dwp}.applicability_conditions.{condition.field}.source_refs", condition.source_refs, source_ids
            )

    # FilingScheduleId (str-keyed) references
    for schedule in revision.filing_schedules:
        fsp = f"filing_schedule {schedule.id}"
        _chk_tuple(f"{fsp}.legal_refs", schedule.legal_refs, legal_ids)
        _chk_tuple(f"{fsp}.source_refs", schedule.source_refs, source_ids)
        for condition in schedule.profile_conditions:
            _chk_tuple(f"{fsp}.profile_conditions.{condition.field}.legal_refs", condition.legal_refs, legal_ids)
            _chk_tuple(f"{fsp}.profile_conditions.{condition.field}.source_refs", condition.source_refs, source_ids)

    # SupportRemovalDecisionId references
    for decision in revision.support_removal_decisions:
        dp = f"support_removal_decision {decision.id}"
        _chk_tuple(f"{dp}.legal_refs", decision.legal_refs, legal_ids)
        _chk_tuple(f"{dp}.source_refs", decision.source_refs, source_ids)

    # ConstructId references
    for construct in revision.constructs:
        ctp = f"construct {construct.id}"
        _chk_tuple(f"{ctp}.casillas", construct.casillas, casilla_ids)
        _chk_tuple(f"{ctp}.formulas", construct.formulas, formula_ids)
        _chk_tuple(f"{ctp}.parameters", construct.parameters, parameter_ids)
        _chk_tuple(f"{ctp}.bindings", construct.bindings, binding_ids)
        _chk_tuple(f"{ctp}.relations", construct.relations, relation_ids)
        _chk_tuple(f"{ctp}.export_layouts", construct.export_layouts, export_layout_ids)
        _chk_tuple(f"{ctp}.extraction_profiles", construct.extraction_profiles, extraction_profile_ids)
        _chk_tuple(f"{ctp}.live_cross_references", construct.live_cross_references, cross_reference_ids)
        _chk_tuple(f"{ctp}.workbook_parity_refs", construct.workbook_parity_refs, workbook_parity_ids)
        _chk_tuple(
            f"{ctp}.verification_expectations", construct.verification_expectations, verification_expectation_ids
        )
        _chk_tuple(f"{ctp}.application_links", construct.application_links, application_link_ids)
        _chk_tuple(f"{ctp}.deadline_windows", construct.deadline_windows, deadline_window_ids)
        _chk_tuple(
            f"{ctp}.support_removal_decisions", construct.support_removal_decisions, support_removal_decision_ids
        )
        _chk_tuple(
            f"{ctp}.dependency_classifications", construct.dependency_classifications, dependency_classification_ids
        )
        _chk_tuple(f"{ctp}.legal_refs", construct.legal_refs, legal_ids)
        _chk_tuple(f"{ctp}.source_refs", construct.source_refs, source_ids)

    # DependencyClassificationId references
    for classification in revision.dependency_classifications:
        dcp = f"dependency_classification {classification.id}"
        _chk_tuple(f"{dcp}.target_constructs", classification.target_constructs, construct_ids)
        _chk_tuple(f"{dcp}.relation_refs", classification.relation_refs, relation_ids)
        _chk_tuple(f"{dcp}.legal_refs", classification.legal_refs, legal_ids)
        _chk_tuple(f"{dcp}.source_refs", classification.source_refs, source_ids)

    # AlgorithmProviderDefinition refs (id is str, not a typed alias)
    for provider in revision.algorithm_providers:
        avp = f"algorithm_provider {provider.id}"
        _chk_tuple(f"{avp}.legal_refs", provider.legal_refs, legal_ids)
        _chk_tuple(f"{avp}.source_refs", provider.source_refs, source_ids)

    # AlgorithmBindingDefinition refs (id is str, not a typed alias)
    provider_ids: set[str] = {p.id for p in revision.algorithm_providers}
    resolvable_ids = casilla_ids | binding_ids | parameter_ids | relation_ids
    for alg_binding in revision.algorithm_bindings:
        abp = f"algorithm_binding {alg_binding.id}"
        if alg_binding.provider not in provider_ids:
            failures.append(f"{prefix}: {abp}.provider references unknown id {alg_binding.provider!r}")
        # target is CasillaId | str; treat as CasillaId candidate.
        _chk(f"{abp}.target", alg_binding.target, casilla_ids)
        for input_name, input_id in alg_binding.inputs.items():
            if input_id not in resolvable_ids:
                failures.append(f"{prefix}: {abp}.inputs.{input_name} references unknown id {input_id!r}")
        for output_name, output_id in alg_binding.outputs.items():
            _chk(f"{abp}.outputs.{output_name}", output_id, casilla_ids)
        _chk_tuple(f"{abp}.constants", alg_binding.constants, parameter_ids)
        _chk_tuple(f"{abp}.legal_refs", alg_binding.legal_refs, legal_ids)
        _chk_tuple(f"{abp}.source_refs", alg_binding.source_refs, source_ids)

    # ExportLayoutId / RecordId / ExportFieldId references
    for layout in revision.export_layouts:
        lyp = f"export_layout {layout.id}"
        _chk_tuple(f"{lyp}.legal_refs", layout.legal_refs, legal_ids)
        _chk_tuple(f"{lyp}.source_refs", layout.source_refs, source_ids)
        if layout.dictionary_source_ref is not None:
            _chk(f"{lyp}.dictionary_source_ref", layout.dictionary_source_ref, source_ids)
        for record in layout.records:
            rcp = f"{lyp}.record {record.id}"
            _chk_opt(f"{rcp}.requires_positive_casilla", record.requires_positive_casilla, casilla_ids)
            for field in record.fields:
                efp = f"{rcp}.field {field.id}"
                _chk_opt(f"{efp}.casilla", field.casilla, casilla_ids)
                _chk_opt(f"{efp}.binding", field.binding, binding_ids)
                _chk_tuple(f"{efp}.legal_refs", field.legal_refs, legal_ids)
                _chk_tuple(f"{efp}.source_refs", field.source_refs, source_ids)

    # Cross-domain referential integrity: when the snapshot describes
    # modelo 100, every casilla mentioned in the renta first-slice
    # routing table MUST be a real casilla on the revision. A divergence
    # between the BOE-prescribed routing in
    # :mod:`aeat.domain.renta._first_slice_routing` and the modelo-100
    # registry casilla set is a snapshot-build error, not a silent
    # runtime KeyError when the renta validator runs.
    if snapshot.modelo.id == "100":
        from ...renta._first_slice_routing import first_slice_target_casillas

        missing_first_slice = first_slice_target_casillas() - casilla_ids
        if missing_first_slice:
            failures.append(
                f"{prefix}: renta first-slice routing targets casillas "
                f"{sorted(missing_first_slice)!r} that are absent from the modelo-100 revision"
            )

    # Per-source selector-shape validation: every binding whose source
    # appears in the discriminated selector registry must satisfy the
    # strict pydantic model declared for that source. Sources without
    # a registered typed selector are accepted unchanged — the
    # discriminator is incremental; new typed selectors land alongside
    # their handler updates and are registered in _BINDING_SELECTOR_REGISTRY.
    from ._bindings import validate_binding_selector_shape

    for binding in revision.bindings:
        failures.extend(
            f"{prefix}: {fail}" for fail in validate_binding_selector_shape(binding)
        )

    if failures:
        raise RegistryValidationError(
            "referential integrity check failed:\n" + "\n".join(f" - {f}" for f in sorted(failures))
        )

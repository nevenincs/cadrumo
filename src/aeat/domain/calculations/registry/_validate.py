"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

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
    SourceCitation,
    SourceReference,
)
from ._sources import verify_source_catalogue
from ._text import normalise_corpus_text


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


@lru_cache(maxsize=16)
def _extract_pdf_text(path: Path) -> str:
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
                    pages.append(page.get_textpage().get_text_range())
                finally:
                    page.close()
        finally:
            pdf.close()
        return "\n".join(pages)
    except Exception as exc:
        raise OSError(f"could not extract text from manual PDF {path}") from exc


class RegistryValidator:
    """Validate legal/source closure and calculability for modelos."""

    def __init__(self, catalogues: RegistryCatalogues, *, source_root: Path | None = None) -> None:
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._source_root = source_root
        self._source_text_cache: dict[str, str] = {}

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
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
        failures.extend(self._missing_refs("modelo", modelo.id, modelo.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs("modelo", modelo.id, modelo.source_refs, self._sources, "source"))
        for revision in modelo.revisions.values():
            failures.extend(self._validate_revision(modelo, revision))
        failures.extend(self._validate_revision_windows(modelo))
        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph."""

        modelo_tuple = tuple(modelos)
        failures: list[str] = []
        modelo_ids = [modelo.id for modelo in modelo_tuple]
        for duplicate in sorted(_duplicates(modelo_ids)):
            failures.append(f"registry: duplicate modelo id {duplicate!r}")

        modelos_by_id = {modelo.id: modelo for modelo in modelo_tuple}
        for modelo in modelo_tuple:
            try:
                self.validate_modelo(modelo)
            except RegistryValidationError as exc:
                failures.append(str(exc))

        if len(modelos_by_id) == len(modelo_tuple):
            failures.extend(self._validate_relation_closure(modelo_tuple, modelos_by_id))
            failures.extend(self._validate_previous_filing_binding_closure(modelo_tuple, modelos_by_id))

        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

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
                if construct_id not in construct_ids:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} references unknown construct "
                        f"{construct_id!r}"
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
                        missing_selector_keys = sorted(
                            key
                            for key in ("offset", "length", "data_type")
                            if key not in binding.selector
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
            for casilla_id in profile.target_casillas:
                if casilla_id not in casillas:
                    failures.append(
                        f"{prefix}: extraction profile {profile.id!r} references unknown casilla {casilla_id!r}"
                    )
            failures.extend(self._validate_extraction_profile_artefacts(prefix, profile))

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
        failures.extend(self._validate_application_link_closure(prefix, revision))
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
    def _validate_relation_closure(
        modelos: Iterable[ModeloDefinition],
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        for modelo in modelos:
            for revision in modelo.revisions.values():
                prefix = f"modelo {modelo.id} revision {revision.id}"
                for relation in revision.relations:
                    relation_scope = f"{prefix}: relation {relation.id!r}"
                    source_modelo = modelos_by_id.get(relation.source_modelo)
                    if source_modelo is None:
                        failures.append(f"{relation_scope} references unknown source modelo {relation.source_modelo!r}")
                        continue
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
                        continue
                    for source_revision in source_revisions:
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
                    binding_scope = f"{prefix}: binding {binding.id!r}"
                    source_modelo_id = binding.selector.get("source_modelo")
                    if not isinstance(source_modelo_id, str):
                        failures.append(f"{binding_scope} must declare string selector source_modelo")
                        continue
                    source_modelo = modelos_by_id.get(source_modelo_id)
                    if source_modelo is None:
                        failures.append(f"{binding_scope} references unknown source modelo {source_modelo_id!r}")
                        continue

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
                        continue

                    source_outputs = RegistryValidator._binding_source_outputs(binding)
                    if not source_outputs:
                        continue

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
        allowed = {"revision", "revision_id", "year", "year_from", "year_to"}
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
    def _validate_application_link_closure(scope: str, revision: ModeloRevision) -> list[str]:
        failures: list[str] = []
        surfaces = {link.surface for link in revision.application_links}
        if revision.formulas and "calculation" not in surfaces:
            failures.append(f"{scope}: formulas require a calculation application link")
        if revision.extraction_profiles and "extractor" not in surfaces:
            failures.append(f"{scope}: extraction profiles require an extractor application link")
        if revision.export_layouts and "export" not in surfaces:
            failures.append(f"{scope}: export layouts require an export application link")
        if revision.verification_expectations and "verification" not in surfaces:
            failures.append(f"{scope}: verification expectations require a verification application link")
        if revision.casillas and "filing" not in surfaces:
            failures.append(f"{scope}: filing-grade casillas require a filing application link")
        if revision.live_cross_references and "portal" not in surfaces:
            failures.append(f"{scope}: live/static cross-references require a portal application link")
        if revision.deadline_windows and "deadline" not in surfaces:
            failures.append(f"{scope}: deadline windows require a deadline application link")
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
                if normalise_corpus_text(required) not in source_text:
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

    def _source_text(self, source: SourceReference) -> str:
        cached = self._source_text_cache.get(source.id)
        if cached is not None:
            return cached
        if self._source_root is None:
            return ""
        source_path = self._source_root / source.corpus_path
        if source.kind == "manual_pdf":
            text = _extract_pdf_text(source_path)
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        normalised = normalise_corpus_text(text)
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

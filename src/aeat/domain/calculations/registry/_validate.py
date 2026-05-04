"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._runtime_graph import expression_casilla_refs
from ._schema import (
    DatedValue,
    FormulaExpression,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
    RegistryCatalogues,
    SourceReference,
)
from ._sources import verify_source_catalogue


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


class RegistryValidator:
    """Validate legal/source closure and calculability for modelos."""

    def __init__(self, catalogues: RegistryCatalogues, *, source_root: Path | None = None) -> None:
        self._legal = catalogues.legal
        self._sources = catalogues.sources
        self._source_root = source_root

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
        failures: list[str] = []
        try:
            verify_legal_catalogue(self._legal)
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
        extraction_profile_ids = [profile.id for profile in revision.extraction_profiles]
        cross_reference_ids = [cross_reference.id for cross_reference in revision.live_cross_references]
        workbook_parity_ids = [workbook.id for workbook in revision.workbook_parity_refs]
        verification_expectation_ids = [expectation.id for expectation in revision.verification_expectations]
        application_link_ids = [link.id for link in revision.application_links]
        for kind, ids in (
            ("casilla", casilla_ids),
            ("formula", formula_ids),
            ("binding", binding_ids),
            ("relation", relation_ids),
            ("parameter", parameter_ids),
            ("algorithm provider", provider_ids),
            ("algorithm binding", algorithm_binding_ids),
            ("extraction profile", extraction_profile_ids),
            ("cross-reference", cross_reference_ids),
            ("workbook parity reference", workbook_parity_ids),
            ("verification expectation", verification_expectation_ids),
            ("application link", application_link_ids),
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
            + extraction_profile_ids
            + cross_reference_ids
            + workbook_parity_ids
            + verification_expectation_ids
            + application_link_ids
        )
        for duplicate in sorted(_duplicates(primary_ids)):
            failures.append(f"{prefix}: duplicate registry id {duplicate!r}")

        casillas = set(casilla_ids)
        formulas = {formula.id: formula for formula in revision.formulas}
        bindings = set(binding_ids)
        relations = set(relation_ids)
        parameters = set(parameter_ids)
        providers = set(provider_ids)
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
            if formula.target not in casillas:
                failures.append(f"{prefix}: formula {formula.id!r} targets unknown casilla {formula.target!r}")
            failures.extend(
                self._validate_formula_expression(
                    prefix,
                    formula.id,
                    formula.expression,
                    casillas=casillas,
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
            failures.extend(self._validate_dated_values(prefix, parameter.id, parameter.values))

        for binding in revision.bindings:
            failures.extend(
                self._missing_refs(prefix, f"binding {binding.id}", binding.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"binding {binding.id}", binding.source_refs, self._sources, "source")
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
            for record in layout.records:
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

        for link in revision.application_links:
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.source_refs, self._sources, "source")
            )

        failures.extend(self._validate_application_link_closure(prefix, revision))
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
        return failures

    @classmethod
    def _validate_formula_expression(
        cls,
        scope: str,
        formula_id: str,
        expression: FormulaExpression,
        *,
        casillas: set[str],
        parameters: set[str],
        relations: set[str],
    ) -> list[str]:
        failures: list[str] = []
        if expression.casilla is not None and expression.casilla not in casillas:
            failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla!r}")
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
                    parameters=parameters,
                    relations=relations,
                )
            )
        return failures

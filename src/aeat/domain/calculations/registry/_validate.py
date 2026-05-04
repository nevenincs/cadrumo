"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._schema import DatedValue, LegalReference, ModeloDefinition, ModeloRevision, RegistryCatalogues, SourceReference
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
        for kind, ids in (
            ("casilla", casilla_ids),
            ("formula", formula_ids),
            ("binding", binding_ids),
            ("relation", relation_ids),
            ("parameter", parameter_ids),
            ("algorithm provider", provider_ids),
            ("algorithm binding", algorithm_binding_ids),
        ):
            for duplicate in sorted(_duplicates(ids)):
                failures.append(f"{prefix}: duplicate {kind} id {duplicate!r}")

        primary_ids = casilla_ids + formula_ids + binding_ids + relation_ids + parameter_ids + algorithm_binding_ids
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
            for arg in formula.args:
                if arg.casilla is not None and arg.casilla not in casillas:
                    failures.append(f"{prefix}: formula {formula.id!r} references unknown casilla {arg.casilla!r}")
                if arg.parameter is not None and arg.parameter not in parameters:
                    failures.append(f"{prefix}: formula {formula.id!r} references unknown parameter {arg.parameter!r}")
                if arg.relation is not None and arg.relation not in relations:
                    failures.append(f"{prefix}: formula {formula.id!r} references unknown relation {arg.relation!r}")

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
            if (previous_to is None or previous_to >= current.valid_from) and set(
                previous.period_selector.periods
            ).intersection(current.period_selector.periods):
                failures.append(
                    f"modelo {modelo.id}: revisions {previous.id!r} and {current.id!r} overlap on period selector"
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
    def _validate_formula_dag(scope: str, revision: ModeloRevision) -> list[str]:
        formula_targets = {formula.target for formula in revision.formulas}
        sorter: TopologicalSorter[str] = TopologicalSorter()
        for formula in revision.formulas:
            dependencies = [arg.casilla for arg in formula.args if arg.casilla in formula_targets]
            sorter.add(formula.target, *(dep for dep in dependencies if dep is not None))
        try:
            tuple(sorter.static_order())
        except CycleError as exc:
            return [f"{scope}: formula graph cycle: {exc}"]
        return []

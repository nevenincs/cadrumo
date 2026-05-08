"""Fail-fast validation for registry definitions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from graphlib import CycleError, TopologicalSorter
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._bindings import (
    validate_invoice_binding_definition,
    validate_ledger_iva_aggregation_binding_definition,
    validate_ledger_oss_aggregation_binding_definition,
)
from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._runtime_graph import expression_casilla_refs
from ._schema import (
    AlgorithmBindingDefinition,
    AlgorithmProviderDefinition,
    ApplicationLinkDefinition,
    CasillaDefinition,
    ConstructDefinition,
    DataBindingDefinition,
    DateAxis,
    DatedValue,
    DeadlineWindowDefinition,
    DependencyClassificationDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExtractionProfileDefinition,
    FilingScheduleDefinition,
    FormulaDefinition,
    FormulaExpression,
    LegalReference,
    LiveCrossReferenceDecision,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    PeriodSelector,
    RegistryCatalogues,
    RelationDefinition,
    SourceCitation,
    SourceReference,
    SupportRemovalDecisionDefinition,
    VerificationExpectationDefinition,
    WorkbookParityReference,
)
from ._sources import verify_source_catalogue
from ._text import normalise_corpus_text

if TYPE_CHECKING:
    from ...user_profile._schema import ProfileSchemaDefinition


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


@dataclass(frozen=True)
class _RevisionInventory:
    """Pre-computed indexes of every per-aspect collection on a revision.

    Centralises the by-id maps, id sets, and derived sets that
    :meth:`RegistryValidator._validate_revision` and its per-aspect
    delegates would otherwise re-derive from
    :class:`ModeloRevision` over and over. The fields mirror the
    aspect names declared on :class:`ModeloRevision` 1:1; new aspects
    must be added here.
    """

    casilla_by_id: Mapping[str, CasillaDefinition]
    formula_by_id: Mapping[str, FormulaDefinition]
    binding_by_id: Mapping[str, DataBindingDefinition]
    relation_by_id: Mapping[str, RelationDefinition]
    parameter_by_id: Mapping[str, ParameterDefinition]
    provider_by_id: Mapping[str, AlgorithmProviderDefinition]
    algorithm_binding_by_id: Mapping[str, AlgorithmBindingDefinition]
    export_layout_by_id: Mapping[str, ExportLayoutDefinition]
    extraction_profile_by_id: Mapping[str, ExtractionProfileDefinition]
    cross_reference_by_id: Mapping[str, LiveCrossReferenceDecision]
    workbook_parity_by_id: Mapping[str, WorkbookParityReference]
    verification_expectation_by_id: Mapping[str, VerificationExpectationDefinition]
    application_link_by_id: Mapping[str, ApplicationLinkDefinition]
    deadline_window_by_id: Mapping[str, DeadlineWindowDefinition]
    filing_schedule_by_id: Mapping[str, FilingScheduleDefinition]
    support_removal_decision_by_id: Mapping[str, SupportRemovalDecisionDefinition]
    construct_by_id: Mapping[str, ConstructDefinition]
    dependency_classification_by_id: Mapping[str, DependencyClassificationDefinition]
    export_field_ids: frozenset[str]
    exported_casillas: frozenset[str]


def _collect_revision_inventory(revision: ModeloRevision) -> _RevisionInventory:
    """Build a :class:`_RevisionInventory` from one revision in one pass."""
    return _RevisionInventory(
        casilla_by_id={c.id: c for c in revision.casillas},
        formula_by_id={f.id: f for f in revision.formulas},
        binding_by_id={b.id: b for b in revision.bindings},
        relation_by_id={r.id: r for r in revision.relations},
        parameter_by_id={p.id: p for p in revision.parameters},
        provider_by_id={p.id: p for p in revision.algorithm_providers},
        algorithm_binding_by_id={b.id: b for b in revision.algorithm_bindings},
        export_layout_by_id={layout.id: layout for layout in revision.export_layouts},
        extraction_profile_by_id={p.id: p for p in revision.extraction_profiles},
        cross_reference_by_id={x.id: x for x in revision.live_cross_references},
        workbook_parity_by_id={w.id: w for w in revision.workbook_parity_refs},
        verification_expectation_by_id={e.id: e for e in revision.verification_expectations},
        application_link_by_id={a.id: a for a in revision.application_links},
        deadline_window_by_id={w.id: w for w in revision.deadline_windows},
        filing_schedule_by_id={s.id: s for s in revision.filing_schedules},
        support_removal_decision_by_id={d.id: d for d in revision.support_removal_decisions},
        construct_by_id={c.id: c for c in revision.constructs},
        dependency_classification_by_id={c.id: c for c in revision.dependency_classifications},
        export_field_ids=frozenset(
            field.id
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
        ),
        exported_casillas=frozenset(
            field.casilla
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.casilla is not None
        ),
    )


# Stable order of aspects whose duplicate-id checks share identical
# wording; keeping the order in one place lets _validate_revision
# iterate the table without inlining 18 copies of the same loop.
_REVISION_ASPECT_LABELS: tuple[tuple[str, str], ...] = (
    ("casilla_by_id", "casilla"),
    ("formula_by_id", "formula"),
    ("binding_by_id", "binding"),
    ("relation_by_id", "relation"),
    ("parameter_by_id", "parameter"),
    ("provider_by_id", "algorithm provider"),
    ("algorithm_binding_by_id", "algorithm binding"),
    ("export_layout_by_id", "export layout"),
    ("extraction_profile_by_id", "extraction profile"),
    ("cross_reference_by_id", "cross-reference"),
    ("workbook_parity_by_id", "workbook parity reference"),
    ("verification_expectation_by_id", "verification expectation"),
    ("application_link_by_id", "application link"),
    ("deadline_window_by_id", "deadline window"),
    ("filing_schedule_by_id", "filing schedule"),
    ("support_removal_decision_by_id", "support removal decision"),
    ("construct_by_id", "construct"),
    ("dependency_classification_by_id", "dependency classification"),
)


def _aspect_id_lists(
    revision: ModeloRevision,
) -> tuple[tuple[str, list[str]], ...]:
    """Return (label, ids) pairs in the order :data:`_REVISION_ASPECT_LABELS` declares.

    The ids are taken from the live :class:`ModeloRevision` collections
    rather than from the inventory so that order-sensitive duplicate
    detection sees the same ordering as the source declaration.
    """
    return (
        ("casilla", [c.id for c in revision.casillas]),
        ("formula", [f.id for f in revision.formulas]),
        ("binding", [b.id for b in revision.bindings]),
        ("relation", [r.id for r in revision.relations]),
        ("parameter", [p.id for p in revision.parameters]),
        ("algorithm provider", [p.id for p in revision.algorithm_providers]),
        ("algorithm binding", [b.id for b in revision.algorithm_bindings]),
        ("export layout", [layout.id for layout in revision.export_layouts]),
        ("extraction profile", [p.id for p in revision.extraction_profiles]),
        ("cross-reference", [x.id for x in revision.live_cross_references]),
        ("workbook parity reference", [w.id for w in revision.workbook_parity_refs]),
        ("verification expectation", [e.id for e in revision.verification_expectations]),
        ("application link", [a.id for a in revision.application_links]),
        ("deadline window", [w.id for w in revision.deadline_windows]),
        ("filing schedule", [s.id for s in revision.filing_schedules]),
        ("support removal decision", [d.id for d in revision.support_removal_decisions]),
        ("construct", [c.id for c in revision.constructs]),
        ("dependency classification", [c.id for c in revision.dependency_classifications]),
    )


def _check_revision_id_uniqueness(prefix: str, revision: ModeloRevision) -> list[str]:
    """Return one failure per duplicate id (per-kind and across-kinds)."""
    failures: list[str] = []
    aspect_ids = _aspect_id_lists(revision)
    for kind, ids in aspect_ids:
        for duplicate in sorted(_duplicates(ids)):
            failures.append(f"{prefix}: duplicate {kind} id {duplicate!r}")

    primary_ids: list[str] = []
    for _, ids in aspect_ids:
        primary_ids.extend(ids)
    for duplicate in sorted(_duplicates(primary_ids)):
        failures.append(f"{prefix}: duplicate registry id {duplicate!r}")
    return failures


@lru_cache(maxsize=16)
def _extract_pdf_text(path: Path) -> str:
    try:
        pdfium: Any = import_module("pypdfium2")
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
        failures = self._validate_modelo(modelo, validate_catalogues=True)
        if failures:
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

    def _validate_catalogues(self) -> tuple[str, ...]:
        if self._catalogue_failures is not None:
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
        return failures

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and the cross-model relation graph."""

        modelo_tuple = tuple(modelos)
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
            raise RegistryValidationError("registry validation failed:\n" + "\n".join(f" - {f}" for f in failures))

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

        if not revision.workbook_parity_refs:
            failures.append(f"{prefix}: revision must declare official workbook parity coverage")
        failures.extend(_check_revision_id_uniqueness(prefix, revision))

        inventory = _collect_revision_inventory(revision)
        failures.extend(self._dispatch_per_aspect_validators(prefix, revision, inventory))
        failures.extend(self._dispatch_revision_closures(prefix, revision, inventory))
        return failures

    def _dispatch_per_aspect_validators(
        self,
        prefix: str,
        revision: ModeloRevision,
        inventory: _RevisionInventory,
    ) -> list[str]:
        """Run every per-aspect validator over ``revision`` in declared order."""
        casillas = set(inventory.casilla_by_id)
        formulas = inventory.formula_by_id
        bindings = set(inventory.binding_by_id)
        relations = set(inventory.relation_by_id)
        parameters = set(inventory.parameter_by_id)
        providers = set(inventory.provider_by_id)
        resolvable_values = casillas | bindings | relations | parameters

        failures: list[str] = []
        failures.extend(
            self._validate_revision_casillas(
                prefix, revision, casillas, formulas, bindings, set(inventory.export_field_ids)
            )
        )
        failures.extend(self._validate_revision_formulas(prefix, revision, casillas, bindings, parameters, relations))
        failures.extend(self._validate_revision_parameters(prefix, revision))
        failures.extend(self._validate_revision_bindings(prefix, revision))
        failures.extend(self._validate_revision_relations(prefix, revision, bindings, inventory.binding_by_id))
        failures.extend(
            self._validate_revision_dependency_classifications(
                prefix, revision, inventory.construct_by_id, inventory.relation_by_id
            )
        )
        failures.extend(self._validate_revision_filing_schedules(prefix, revision))
        failures.extend(self._validate_revision_algorithm_providers(prefix, revision))
        failures.extend(
            self._validate_revision_algorithm_bindings(
                prefix, revision, providers, casillas, resolvable_values, parameters
            )
        )
        failures.extend(
            self._validate_revision_export_layouts(prefix, revision, casillas, inventory.casilla_by_id, bindings)
        )
        failures.extend(
            self._validate_revision_extraction_profiles(prefix, revision, casillas, set(inventory.exported_casillas))
        )
        failures.extend(self._validate_revision_live_cross_references(prefix, revision))
        failures.extend(self._validate_revision_workbook_parity_refs(prefix, revision))
        failures.extend(self._validate_revision_verification_expectations(prefix, revision, casillas))
        failures.extend(self._validate_revision_application_links(prefix, revision))
        failures.extend(self._validate_revision_deadline_windows(prefix, revision))
        return failures

    def _dispatch_revision_closures(
        self,
        prefix: str,
        revision: ModeloRevision,
        inventory: _RevisionInventory,
    ) -> list[str]:
        """Run the cross-aspect closure validator with all the by-id maps."""
        return self._validate_revision_closures(
            prefix,
            revision,
            list(inventory.export_layout_by_id),
            list(inventory.extraction_profile_by_id),
            list(inventory.cross_reference_by_id),
            list(inventory.workbook_parity_by_id),
            list(inventory.verification_expectation_by_id),
            list(inventory.application_link_by_id),
            list(inventory.deadline_window_by_id),
            list(inventory.filing_schedule_by_id),
            inventory.casilla_by_id,
            inventory.formula_by_id,
            inventory.parameter_by_id,
            inventory.binding_by_id,
            inventory.provider_by_id,
            inventory.algorithm_binding_by_id,
            inventory.relation_by_id,
            inventory.export_layout_by_id,
            inventory.extraction_profile_by_id,
            inventory.cross_reference_by_id,
            inventory.workbook_parity_by_id,
            inventory.verification_expectation_by_id,
            inventory.application_link_by_id,
            inventory.deadline_window_by_id,
            inventory.filing_schedule_by_id,
            inventory.support_removal_decision_by_id,
            inventory.dependency_classification_by_id,
        )

    def _validate_revision_casillas(
        self,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        formulas: Mapping[str, FormulaDefinition],
        bindings: set[str],
        export_field_ids: set[str],
    ) -> list[str]:
        failures: list[str] = []
        for casilla in revision.casillas:
            failures.extend(
                self._missing_refs(prefix, f"casilla {casilla.id}", casilla.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"casilla {casilla.id}", casilla.source_refs, self._sources, "source")
            )
            failures.extend(RegistryValidator._validate_casilla_formula(prefix, casilla, formulas))
            failures.extend(RegistryValidator._validate_casilla_binding(prefix, casilla, bindings))
            failures.extend(RegistryValidator._validate_casilla_export_refs(prefix, casilla, export_field_ids))

        return failures

    @staticmethod
    def _validate_casilla_formula(
        prefix: str,
        casilla: CasillaDefinition,
        formulas: Mapping[str, FormulaDefinition],
    ) -> list[str]:
        if casilla.formula is None:
            return []
        formula = formulas.get(casilla.formula)
        if formula is None:
            return [f"{prefix}: casilla {casilla.id!r} references unknown formula {casilla.formula!r}"]
        if formula.target != casilla.id:
            return [
                f"{prefix}: casilla {casilla.id!r} references formula {casilla.formula!r} "
                f"targeting {formula.target!r}"
            ]
        return []

    @staticmethod
    def _validate_casilla_binding(
        prefix: str,
        casilla: CasillaDefinition,
        bindings: set[str],
    ) -> list[str]:
        if casilla.binding is not None and casilla.binding not in bindings:
            return [f"{prefix}: casilla {casilla.id!r} references unknown binding {casilla.binding!r}"]
        return []

    @staticmethod
    def _validate_casilla_export_refs(
        prefix: str,
        casilla: CasillaDefinition,
        export_field_ids: set[str],
    ) -> list[str]:
        return [
            f"{prefix}: casilla {casilla.id!r} references unknown export field {export_ref!r}"
            for export_ref in casilla.export_refs
            if export_ref not in export_field_ids
        ]

    def _validate_revision_formulas(
        self,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        bindings: set[str],
        parameters: set[str],
        relations: set[str],
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_parameters(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_bindings(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_relations(
        self,
        prefix: str,
        revision: ModeloRevision,
        bindings: set[str],
        binding_by_id: Mapping[str, DataBindingDefinition],
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_dependency_classifications(
        self,
        prefix: str,
        revision: ModeloRevision,
        construct_by_id: Mapping[str, ConstructDefinition],
        relation_by_id: Mapping[str, RelationDefinition],
    ) -> list[str]:
        failures: list[str] = []
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
            failures.extend(
                RegistryValidator._validate_classification_constructs(prefix, classification, construct_by_id)
            )
            failures.extend(
                RegistryValidator._validate_classification_relations(prefix, classification, relation_by_id)
            )
        failures.extend(RegistryValidator._validate_dependency_classification_source_coverage(prefix, revision))
        return failures

    @staticmethod
    def _validate_classification_constructs(
        prefix: str,
        classification: DependencyClassificationDefinition,
        construct_by_id: Mapping[str, ConstructDefinition],
    ) -> list[str]:
        failures: list[str] = []
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
        return failures

    @staticmethod
    def _validate_classification_relations(
        prefix: str,
        classification: DependencyClassificationDefinition,
        relation_by_id: Mapping[str, RelationDefinition],
    ) -> list[str]:
        failures: list[str] = []
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
            failures.extend(
                RegistryValidator._validate_classification_relation_authority(
                    prefix,
                    classification,
                    relation_id,
                    relation,
                )
            )
        return failures

    @staticmethod
    def _validate_classification_relation_authority(
        prefix: str,
        classification: DependencyClassificationDefinition,
        relation_id: str,
        relation: RelationDefinition,
    ) -> list[str]:
        failures: list[str] = []
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
        return failures

    @staticmethod
    def _validate_dependency_classification_source_coverage(
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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
        return failures

    def _validate_revision_filing_schedules(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_algorithm_providers(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_algorithm_bindings(
        self,
        prefix: str,
        revision: ModeloRevision,
        providers: set[str],
        casillas: set[str],
        resolvable_values: set[str],
        parameters: set[str],
    ) -> list[str]:
        failures: list[str] = []
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
            failures.extend(
                RegistryValidator._validate_algorithm_binding_provider_and_target(
                    prefix,
                    algorithm_binding,
                    providers,
                    casillas,
                )
            )
            failures.extend(
                RegistryValidator._validate_algorithm_binding_inputs(prefix, algorithm_binding, resolvable_values)
            )
            failures.extend(RegistryValidator._validate_algorithm_binding_outputs(prefix, algorithm_binding, casillas))
            failures.extend(
                RegistryValidator._validate_algorithm_binding_constants(prefix, algorithm_binding, parameters)
            )

        return failures

    @staticmethod
    def _validate_algorithm_binding_provider_and_target(
        prefix: str,
        algorithm_binding: AlgorithmBindingDefinition,
        providers: set[str],
        casillas: set[str],
    ) -> list[str]:
        failures: list[str] = []
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
        return failures

    @staticmethod
    def _validate_algorithm_binding_inputs(
        prefix: str,
        algorithm_binding: AlgorithmBindingDefinition,
        resolvable_values: set[str],
    ) -> list[str]:
        return [
            f"{prefix}: algorithm binding {algorithm_binding.id!r} input {input_name!r} "
            f"references unknown value {input_value!r}"
            for input_name, input_value in algorithm_binding.inputs.items()
            if input_value not in resolvable_values
        ]

    @staticmethod
    def _validate_algorithm_binding_outputs(
        prefix: str,
        algorithm_binding: AlgorithmBindingDefinition,
        casillas: set[str],
    ) -> list[str]:
        return [
            f"{prefix}: algorithm binding {algorithm_binding.id!r} output {output_name!r} "
            f"references unknown casilla {output_value!r}"
            for output_name, output_value in algorithm_binding.outputs.items()
            if output_value not in casillas
        ]

    @staticmethod
    def _validate_algorithm_binding_constants(
        prefix: str,
        algorithm_binding: AlgorithmBindingDefinition,
        parameters: set[str],
    ) -> list[str]:
        return [
            f"{prefix}: algorithm binding {algorithm_binding.id!r} references unknown constant {constant!r}"
            for constant in algorithm_binding.constants
            if constant not in parameters
        ]

    def _validate_revision_export_layouts(
        self,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
        bindings: set[str],
    ) -> list[str]:
        failures: list[str] = []
        for layout in revision.export_layouts:
            failures.extend(self._validate_export_layout_refs(prefix, layout))
            for record in layout.records:
                failures.extend(
                    self._validate_export_record(prefix, record, revision, casillas, casilla_by_id, bindings)
                )

        return failures

    def _validate_export_layout_refs(self, prefix: str, layout: ExportLayoutDefinition) -> list[str]:
        failures: list[str] = []
        failures.extend(self._missing_refs(prefix, f"export {layout.id}", layout.legal_refs, self._legal, "legal"))
        failures.extend(self._missing_refs(prefix, f"export {layout.id}", layout.source_refs, self._sources, "source"))
        failures.extend(
            self._require_source_tier(prefix, f"export {layout.id}", layout.source_refs, "layout_authority")
        )
        return failures

    def _validate_export_record(
        self,
        prefix: str,
        record: ExportRecordDefinition,
        revision: ModeloRevision,
        casillas: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
        bindings: set[str],
    ) -> list[str]:
        failures: list[str] = []
        failures.extend(self._validate_export_record_binding(prefix, record, revision))
        if (
            record.repeat == "binding_rows"
            and not any(field.kind == "binding" for field in record.fields)
            and record.binding_record is None
        ):
            failures.append(f"{prefix}: export record {record.id!r} repeats binding rows but has no binding fields")
        if record.requires_positive_casilla is not None and record.requires_positive_casilla not in casillas:
            failures.append(
                f"{prefix}: export record {record.id!r} requires unknown positive casilla "
                f"{record.requires_positive_casilla!r}"
            )
        for field in record.fields:
            failures.extend(self._validate_export_field(prefix, field, casillas, casilla_by_id, bindings))
        return failures

    @staticmethod
    def _validate_export_record_binding(
        prefix: str,
        record: ExportRecordDefinition,
        revision: ModeloRevision,
    ) -> list[str]:
        if record.binding_record is None:
            return []
        failures: list[str] = []
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
        return failures

    def _validate_export_field(
        self,
        prefix: str,
        field: ExportFieldDefinition,
        casillas: set[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
        bindings: set[str],
    ) -> list[str]:
        failures: list[str] = []
        failures.extend(self._missing_refs(prefix, f"export field {field.id}", field.legal_refs, self._legal, "legal"))
        failures.extend(
            self._missing_refs(prefix, f"export field {field.id}", field.source_refs, self._sources, "source")
        )
        failures.extend(RegistryValidator._validate_export_field_casilla(prefix, field, casillas))
        failures.extend(RegistryValidator._validate_export_field_reverse_ref(prefix, field, casilla_by_id))
        failures.extend(RegistryValidator._validate_export_field_binding(prefix, field, bindings))
        return failures

    @staticmethod
    def _validate_export_field_casilla(
        prefix: str,
        field: ExportFieldDefinition,
        casillas: set[str],
    ) -> list[str]:
        if field.casilla is not None and field.casilla not in casillas:
            return [f"{prefix}: export field {field.id!r} references unknown casilla {field.casilla!r}"]
        return []

    @staticmethod
    def _validate_export_field_reverse_ref(
        prefix: str,
        field: ExportFieldDefinition,
        casilla_by_id: Mapping[str, CasillaDefinition],
    ) -> list[str]:
        if (
            field.casilla is not None
            and field.casilla in casilla_by_id
            and field.id not in casilla_by_id[field.casilla].export_refs
        ):
            return [f"{prefix}: export field {field.id!r} is not declared by casilla {field.casilla!r}"]
        return []

    @staticmethod
    def _validate_export_field_binding(
        prefix: str,
        field: ExportFieldDefinition,
        bindings: set[str],
    ) -> list[str]:
        if field.binding is not None and field.binding not in bindings:
            return [f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}"]
        return []

    def _validate_revision_extraction_profiles(
        self,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
        exported_casillas: set[str],
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_live_cross_references(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_workbook_parity_refs(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_verification_expectations(
        self,
        prefix: str,
        revision: ModeloRevision,
        casillas: set[str],
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_application_links(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
        for link in revision.application_links:
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.legal_refs, self._legal, "legal")
            )
            failures.extend(
                self._missing_refs(prefix, f"application link {link.id}", link.source_refs, self._sources, "source")
            )

        return failures

    def _validate_revision_deadline_windows(
        self,
        prefix: str,
        revision: ModeloRevision,
    ) -> list[str]:
        failures: list[str] = []
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

        return failures

    def _validate_revision_closures(
        self,
        prefix: str,
        revision: ModeloRevision,
        export_layout_ids: list[str],
        extraction_profile_ids: list[str],
        cross_reference_ids: list[str],
        workbook_parity_ids: list[str],
        verification_expectation_ids: list[str],
        application_link_ids: list[str],
        deadline_window_ids: list[str],
        filing_schedule_ids: list[str],
        casilla_by_id: Mapping[str, CasillaDefinition],
        formula_by_id: Mapping[str, FormulaDefinition],
        parameter_by_id: Mapping[str, ParameterDefinition],
        binding_by_id: Mapping[str, DataBindingDefinition],
        provider_by_id: Mapping[str, AlgorithmProviderDefinition],
        algorithm_binding_by_id: Mapping[str, AlgorithmBindingDefinition],
        relation_by_id: Mapping[str, RelationDefinition],
        export_layout_by_id: Mapping[str, ExportLayoutDefinition],
        extraction_profile_by_id: Mapping[str, ExtractionProfileDefinition],
        cross_reference_by_id: Mapping[str, LiveCrossReferenceDecision],
        workbook_parity_by_id: Mapping[str, WorkbookParityReference],
        verification_expectation_by_id: Mapping[str, VerificationExpectationDefinition],
        application_link_by_id: Mapping[str, ApplicationLinkDefinition],
        deadline_window_by_id: Mapping[str, DeadlineWindowDefinition],
        filing_schedule_by_id: Mapping[str, FilingScheduleDefinition],
        support_removal_decision_by_id: Mapping[str, SupportRemovalDecisionDefinition],
        dependency_classification_by_id: Mapping[str, DependencyClassificationDefinition],
    ) -> list[str]:
        failures: list[str] = []
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
                    failures.extend(
                        RegistryValidator._validate_relation_closure_relation(
                            prefix,
                            revision.period_selector,
                            relation,
                            modelos_by_id,
                        )
                    )
        return failures

    @staticmethod
    def _validate_relation_closure_relation(
        prefix: str,
        target_selector: PeriodSelector,
        relation: RelationDefinition,
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        failures: list[str] = []
        relation_scope = f"{prefix}: relation {relation.id!r}"
        source_modelo = modelos_by_id.get(relation.source_modelo)
        if source_modelo is None:
            return [f"{relation_scope} references unknown source modelo {relation.source_modelo!r}"]
        failures.extend(RegistryValidator._validate_relation_period_shape(relation_scope, relation))
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
                RegistryValidator._validate_relation_source_revision(relation_scope, relation, source_revision)
            )
        failures.extend(
            RegistryValidator._validate_source_year_coverage(
                relation_scope,
                target_selector=target_selector,
                source_revisions=source_revisions,
                source_periods=relation.source_periods,
                filing_year_delta=RegistryValidator._relation_filing_year_delta(relation.source_revision_selector),
                fixed_source_year=RegistryValidator._relation_fixed_source_year(relation.source_revision_selector),
            )
        )
        return failures

    @staticmethod
    def _validate_relation_period_shape(scope: str, relation: RelationDefinition) -> list[str]:
        failures: list[str] = []
        if not relation.source_periods:
            failures.append(f"{scope} must declare source periods")
        if not relation.target_periods:
            failures.append(f"{scope} must declare target periods")
        aggregation = relation.aggregation or {"op": "copy"}
        op = aggregation.get("op")
        if op not in {"copy", "sum"}:
            failures.append(f"{scope} uses unsupported aggregation op {op!r}")
        return failures

    @staticmethod
    def _validate_relation_source_revision(
        relation_scope: str,
        relation: RelationDefinition,
        source_revision: ModeloRevision,
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
            failures.append(f"{source_scope} does not support source periods {unknown_source_periods!r}")
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
                        RegistryValidator._validate_previous_filing_binding(prefix, binding, modelos_by_id)
                    )
        return failures

    @staticmethod
    def _validate_previous_filing_binding(
        prefix: str,
        binding: DataBindingDefinition,
        modelos_by_id: Mapping[str, ModeloDefinition],
    ) -> list[str]:
        binding_scope = f"{prefix}: binding {binding.id!r}"
        source_modelo_id = binding.selector.get("source_modelo")
        if not isinstance(source_modelo_id, str):
            return [f"{binding_scope} must declare string selector source_modelo"]
        source_modelo = modelos_by_id.get(source_modelo_id)
        if source_modelo is None:
            return [f"{binding_scope} references unknown source modelo {source_modelo_id!r}"]
        source_periods = RegistryValidator._binding_source_periods(binding)
        matching_revisions = tuple(
            source_revision
            for source_revision in source_modelo.revisions.values()
            if not source_periods or set(source_periods).issubset(set(source_revision.period_selector.periods))
        )
        if not matching_revisions:
            return [
                f"{binding_scope} matches no source revisions in modelo {source_modelo.id} "
                f"for periods {source_periods!r}"
            ]
        return RegistryValidator._validate_previous_filing_outputs(
            binding_scope,
            binding,
            source_modelo,
            matching_revisions,
        )

    @staticmethod
    def _validate_previous_filing_outputs(
        binding_scope: str,
        binding: DataBindingDefinition,
        source_modelo: ModeloDefinition,
        matching_revisions: tuple[ModeloRevision, ...],
    ) -> list[str]:
        source_outputs = RegistryValidator._binding_source_outputs(binding)
        if not source_outputs:
            return []
        revision_outputs = set().union(
            *(RegistryValidator._revision_output_ids(source_revision) for source_revision in matching_revisions)
        )
        return [
            f"{binding_scope} source output {source_output!r} is not defined by any "
            f"period-compatible {source_modelo.id} revision"
            for source_output in source_outputs
            if source_output not in revision_outputs
        ]

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
        revision_id, year, year_from, year_to, failures = RegistryValidator._relation_source_selector_values(selector)
        selected = tuple(
            revision
            for revision in modelo.revisions.values()
            if RegistryValidator._relation_source_revision_matches(
                revision,
                revision_id=revision_id,
                year=year,
                year_from=year_from,
                year_to=year_to,
            )
        )
        return selected, failures

    @staticmethod
    def _relation_source_selector_values(
        selector: Mapping[str, str | int],
    ) -> tuple[str | None, int | None, int | None, int | None, list[str]]:
        allowed = {"revision", "revision_id", "year", "year_from", "year_to", "filing_year_delta"}
        failures = [f"selector uses unknown key {key!r}" for key in sorted(set(selector).difference(allowed))]
        raw_revision_id = selector.get("revision_id", selector.get("revision"))
        raw_year = selector.get("year")
        raw_year_from = selector.get("year_from")
        raw_year_to = selector.get("year_to")

        failures.extend(RegistryValidator._validate_relation_source_revision_id(raw_revision_id))
        failures.extend(
            RegistryValidator._validate_relation_source_year_types(
                raw_year=raw_year,
                raw_year_from=raw_year_from,
                raw_year_to=raw_year_to,
                raw_delta=selector.get("filing_year_delta"),
            )
        )
        failures.extend(
            RegistryValidator._validate_relation_source_year_shape(
                raw_year=raw_year,
                raw_year_from=raw_year_from,
                raw_year_to=raw_year_to,
            )
        )

        revision_id = raw_revision_id if isinstance(raw_revision_id, str) else None
        year = raw_year if isinstance(raw_year, int) else None
        year_from = raw_year_from if isinstance(raw_year_from, int) else None
        year_to = raw_year_to if isinstance(raw_year_to, int) else None
        return revision_id, year, year_from, year_to, failures

    @staticmethod
    def _validate_relation_source_revision_id(value: str | int | None) -> list[str]:
        if value is not None and not isinstance(value, str):
            return ["selector revision_id must be a string"]
        return []

    @staticmethod
    def _validate_relation_source_year_types(
        *,
        raw_year: str | int | None,
        raw_year_from: str | int | None,
        raw_year_to: str | int | None,
        raw_delta: str | int | None,
    ) -> list[str]:
        failures: list[str] = []
        for key, value in (("year", raw_year), ("year_from", raw_year_from), ("year_to", raw_year_to)):
            if value is not None and not isinstance(value, int):
                failures.append(f"selector {key} must be an integer")
        if raw_delta is not None and not isinstance(raw_delta, int):
            failures.append("selector filing_year_delta must be an integer")
        return failures

    @staticmethod
    def _validate_relation_source_year_shape(
        *,
        raw_year: str | int | None,
        raw_year_from: str | int | None,
        raw_year_to: str | int | None,
    ) -> list[str]:
        failures: list[str] = []
        if raw_year is not None:
            failures.extend(RegistryValidator._validate_relation_source_year_is_exclusive(raw_year_from, raw_year_to))
        failures.extend(RegistryValidator._validate_relation_source_year_to_has_start(raw_year_from, raw_year_to))
        failures.extend(RegistryValidator._validate_relation_source_year_order(raw_year_from, raw_year_to))
        return failures

    @staticmethod
    def _validate_relation_source_year_is_exclusive(
        raw_year_from: str | int | None,
        raw_year_to: str | int | None,
    ) -> list[str]:
        if raw_year_from is not None or raw_year_to is not None:
            return ["selector must use year or year_from/year_to, not both"]
        return []

    @staticmethod
    def _validate_relation_source_year_to_has_start(
        raw_year_from: str | int | None,
        raw_year_to: str | int | None,
    ) -> list[str]:
        if raw_year_to is not None and raw_year_from is None:
            return ["selector year_to requires year_from"]
        return []

    @staticmethod
    def _validate_relation_source_year_order(
        raw_year_from: str | int | None,
        raw_year_to: str | int | None,
    ) -> list[str]:
        if isinstance(raw_year_from, int) and isinstance(raw_year_to, int) and raw_year_to < raw_year_from:
            return ["selector year_to must be on or after year_from"]
        return []

    @staticmethod
    def _relation_source_revision_matches(
        revision: ModeloRevision,
        *,
        revision_id: str | None,
        year: int | None,
        year_from: int | None,
        year_to: int | None,
    ) -> bool:
        if revision_id is not None and revision.id != revision_id:
            return False
        if year is not None and not revision.period_selector.includes_year(year):
            return False
        if year_from is None:
            return True
        return RegistryValidator._revision_intersects_year_range(revision, year_from=year_from, year_to=year_to)

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
        by_axis: dict[DateAxis, list[DatedValue]] = {}
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
        surfaces = {link.surface for link in revision.application_links}
        required = (
            (revision.formulas, "calculation", "formulas require a calculation application link"),
            (revision.extraction_profiles, "extractor", "extraction profiles require an extractor application link"),
            (revision.export_layouts, "export", "export layouts require an export application link"),
            (
                revision.verification_expectations,
                "verification",
                "verification expectations require a verification application link",
            ),
            (revision.casillas, "filing", "filing-grade casillas require a filing application link"),
            (
                revision.live_cross_references,
                "portal",
                "live/static cross-references require a portal application link",
            ),
            (revision.deadline_windows, "deadline", "deadline windows require a deadline application link"),
        )
        return [f"{scope}: {message}" for items, surface, message in required if items and surface not in surfaces]

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

    @staticmethod
    def _validate_dotted_callable(scope: str, owner: str, dotted_path: str) -> list[str]:
        module_name, separator, attribute = dotted_path.rpartition(".")
        if not separator or not module_name or not attribute:
            return [f"{scope}: {owner} parser {dotted_path!r} must be a dotted callable path"]
        try:
            module = import_module(module_name)
        except Exception as exc:
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

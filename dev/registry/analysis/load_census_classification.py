"""Reviewed classification of every module a sanctioned registry load reaches.

The census in :mod:`dev.registry.load_census` derives WHICH modules must be
classified; this file records WHAT each one was classified as and WHY. Splitting
them is the point: the derived side can never be shortened by omission, and the
reviewed side is a diff a person reads.

Three classifications, and no fourth:

``live``
    The module's own code runs on the sanctioned load path -- ``sys.monitoring``
    recorded a function body starting inside it during
    ``ValidatedRegistryAuthority.load``, in the warm regime, the cold regime, or
    both. The owning entry point is the load itself.

``conditionally_reachable``
    A load imports the module, so its declarations execute on every load, but no
    callable of its own runs during the load window. Something else runs it, and
    the ``trigger`` field names that something. A trigger that names no concrete
    surface is not a classification; it is an unanswered question wearing one.

``dead``
    Nothing reaches it. There are no such modules at the revision this file was
    written, and the empty set is deliberate rather than unexamined -- two
    candidates surfaced and both survived review, for the reason recorded in
    :func:`dev.registry.load_census.unreferenced_modules`.

Two measurement facts shape almost every entry below and are easy to misread:

**Warm and cold are one path, not two populations.** A warm load executes 22 of
the registry's modules and 3 of its validators; a cold load executes 93 and 36;
the warm set is a strict subset. The difference is not reachability, it is the
persisted validation verdict and the compiled tree cache short-circuiting work
whose inputs are unchanged. A module in the cold-only group is live -- it runs
on any machine whose registry tree fingerprint moved.

**Not executing during a load is normally evidence of nothing.** The traced
window starts after imports, so a module that publishes types, constants or
cache objects and defines no callable of its own cannot appear in any execution
set. ``_validate_cache`` is the worked example: it publishes the three caches
``_validate`` binds at import, and would read as a never-executing validator to
any instrument that mistook the load trace for a reachability measurement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

REGISTRY_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry"

Classification = Literal["live", "conditionally_reachable", "dead"]


class ClassificationError(RuntimeError):
    """Raised when the reviewed table cannot resolve a module to one classification."""


@dataclass(frozen=True)
class ClassificationRule:
    """One reviewed decision covering one or more modules."""

    classification: Classification
    trigger: str
    reason: str
    members: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse a rule that covers nothing, or a conditional decision with no named trigger."""
        if not self.members and not self.prefixes:
            raise ClassificationError(f"rule {self.trigger!r} matches nothing")
        if self.classification == "conditionally_reachable" and not self.trigger.strip():
            raise ClassificationError("a conditionally reachable rule must name its trigger")


def _registry(*names: str) -> tuple[str, ...]:
    return tuple(f"{REGISTRY_PACKAGE}.{name}" for name in names)


RULES: Final[tuple[ClassificationRule, ...]] = (
    # ── the registry package ────────────────────────────────────────────────
    ClassificationRule(
        classification="live",
        trigger="any import of the registry package",
        reason=(
            "The facade body runs on import, and its PEP 562 __getattr__ is the only path to the "
            "lazily published oracle and live-parity modules. An AST import graph cannot see those "
            "edges, so the facade is also the reason the census reads the _LAZY_EXPORTS table."
        ),
        members=(REGISTRY_PACKAGE,),
    ),
    ClassificationRule(
        classification="live",
        trigger="ValidatedRegistryAuthority.load, both regimes",
        reason=(
            "Executes on every load. This is the resident load path: fingerprinting, the compiled "
            "and disk caches, the TOML compiler, verdict certification, and the M303 annual-orden "
            "parse chain that the coverage ADR records as roughly three quarters of each load."
        ),
        members=_registry(
            "authority",
            "_loader_internals",
            "_snapshot_internals",
            "bindings",
            "_compiled_cache",
            "convenio",
            "identity",
            "loader",
            "loader_cache",
            "loader_fingerprints",
            "_source_file_text",
            "m303_orden_census_artefact",
            "_m303_orden_constants",
            "_m303_orden_keys",
            "_m303_orden_legal",
            "m303_orden_manifest",
            "_m303_orden_projection_compiler",
            "m303_orden_projection_models",
            "_m303_orden_raw_models",
            "_m303_orden_source",
            "schema_base",
            "schema_references",
            "_source_evidence_fingerprint",
            "_supplementary_orden",
            "_toml_helpers",
            "_validate",
            "_validate_cross_revision_evolution",
            "_validate_evidence",
            "_validate_parameter_temporal",
            "_validate_producer_inventory",
            "_validate_projection_endpoints",
            "_validation_memoization",
            "_verdict_cache",
        ),
    ),
    ClassificationRule(
        classification="live",
        trigger="ValidatedRegistryAuthority.load, cold regime",
        reason=(
            "Executes whenever the registry tree fingerprint moves and the persisted validation "
            "verdict no longer certifies it -- schema compilation, binding families, and the "
            "build-time validators. Absent from a warm trace because the verdict short-circuits "
            "the work, not because anything is unreachable."
        ),
        members=_registry(
            "binding_aggregation",
            "binding_selector_utils",
            "bindings_previous_filing",
            "casilla_membership",
            "_citation_blocklist",
            "corpus_catalogue",
            "deadline_coordinate",
            "design_constant_bindings",
            "_cross_revision_divergence",
            "detail_record_bindings",
            "donativo_bindings",
            "export",
            "export_semantics",
            "export_value_policy",
            "fixed_width_codec",
            "_formula_operator_contracts",
            "gasto193_bindings",
            "invoice_bindings",
            "inventory_bindings",
            "irnr_ledger_bindings",
            "iva_wallet_relation_targets",
            "ledger_iva_bindings",
            "ledger_oss_bindings",
            "ledger_renta_gastos_estimacion_directa_bindings",
            "ledger_renta_gastos_pago_fraccionado_bindings",
            "ledger_renta_income_bindings",
            "ledger_impatriado_bindings",
            "legal",
            "manual_input_selector",
            "modelo_localization",
            "period_offset_math",
            "quantity_screen_enrolment",
            "record_design_coverage",
            "relations",
            "retenciones_bindings",
            "runtime_graph",
            "schema",
            "_schema_export_exemption",
            "schema_exports",
            "schema_extraction",
            "_schema_family_coverage",
            "schema_formula",
            "_schema_governance",
            "schema_input_kind",
            "schema_rounding",
            "schema_scalars",
            "schema_surfaces",
            "schema_verification",
            "_supported_filing_years",
            "_validate_applicability_section",
            "_validate_application_links",
            "_validate_authority_grade",
            "_validate_completeness",
            "_validate_constructs",
            "_validate_cross_revision",
            "_validate_dependency_sections",
            "_validate_export_exemption",
            "_validate_export_field_widths",
            "_validate_export_layout_coverage",
            "_validate_exports",
            "_validate_extraction_profiles",
            "_validate_formulas",
            "_validate_helpers",
            "_validate_label_artifacts",
            "_validate_layout_authority_content",
            "_validate_official_source_guidance_content",
            "_validate_orden_aplicabilidad",
            "_validate_previous_filing_sources",
            "_validate_previous_filing_year_coverage",
            "_validate_record_design_epochs",
            "_validate_record_sections",
            "validate_registry_scope",
            "_validate_relation_periods",
            "_validate_relation_sources",
            "_validate_revision_closure",
            "_validate_revision_context",
            "_validate_revision_id_window_agreement",
            "validate_revision_identity",
            "_validate_revision_rules",
            "_validate_revision_sections",
            "_validate_semantic_role_axes",
            "_validate_semantic_role_required",
            "_validate_semantic_role_typos",
            "_validate_semantic_roles",
            "_validate_source_casilla_ids",
            "_validate_surfaces",
            "_validate_valid_from_ejercicio_convention",
            "_validate_verification_predicates",
            "withholding296_bindings",
            "withholding_bindings",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="registry snapshot construction: build_snapshot and ValidatedRegistryAuthority.snapshot",
        reason=(
            "Runs when a snapshot is requested, not when the registry is loaded; observed by "
            "tracing build_snapshot across the bundled corpus, which reached 53 of 73 modelos. "
            "Four of these are validators the campaign brief carried as executing in neither "
            "regime -- they execute here, so the load trace was measuring the wrong entry point "
            "for them, and the snapshot-scoped reference check at _snapshot.py:328 is their home. "
            "One caveat belongs beside that: the operator-review gate in the filing-grade path "
            "refuses before reaching the check for every revision in the corpus, so only the "
            "inspection-grade path exercises it today."
        ),
        members=_registry(
            "errors",
            "period_selector_match",
            "snapshot",
            "temporal",
            "validate_cross_domain_snapshot",
            "_validate_reference_checker",
            "_validate_reference_sections",
            "validate_references",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "modelo obligation and applicability resolution: application.modelo, "
            "application.overview, the modelo discovery CLI"
        ),
        reason=(
            "Answers which modelos a taxpayer is obliged to file. Consumed through the facade by "
            "the application and CLI discovery surfaces; the sibling modules are reached from "
            "_applicability alone. These carry the 28 Python-resident rule literals the coverage "
            "ADR moves into the authoring tree."
        ),
        members=_registry(
            "applicability",
            "_applicability_labels",
            "applicability_modelo202",
            "applicability_payer_facts",
            "applicability_routes",
            "censo_modelos",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="casilla calculation execution: application.modelo calculation actions and source staging",
        reason=(
            "The formula runtime and its per-modelo evaluators run when a calculation is "
            "requested. The two per-modelo runtimes are reached from the generic runtime and are "
            "in scope for the embed classifier, which decides whether either encodes regulatory "
            "values rather than evaluation machinery."
        ),
        members=_registry(
            "formula_initial_values",
            "formula_runtime",
            "_formula_runtime_irnr",
            "_formula_runtime_m131",
            "formula_runtime_ops",
            "formula_text_inputs",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "M303 filing projection and evidence assembly: application.filing projection, "
            "application.modelo M303 filing evidence"
        ),
        reason=(
            "Per-modelo projections consumed by the filing surfaces. Named separately from the "
            "load path because they are the concrete instances of the per-modelo divergence the "
            "coverage ADR rules on, and a reader needs to find them by that description."
        ),
        members=_registry(
            "m303_differentiated_deduction_projection",
            "m303_exonerado_390_projection",
            "m303_orden_resolution",
            "m303_prorrata_activity_projection",
            "m303_regimen_simplificado_projection",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "live AEAT oracle replay: the sede checker adapters, and the live-parity "
            "catalogue assembled in dev.registry.maintenance"
        ),
        reason=(
            "The parity and oracle island. Its production consumers reach it through facade "
            "symbols, and the two checker oracles are registered into the catalogue only by the "
            "maintenance tool, so a module-level importer count reads zero for them and a naive "
            "reading calls the island dead. Every one of these backs the external-oracle "
            "grounding the no-silent-under-declaration rule requires."
        ),
        members=_registry(
            "checker_oracle_flow",
            "external_grounding",
            "live_parity",
            "remote_state_guard",
            "renta_web_open_oracle",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="registry conformance reporting: application.registry conformance and diff surfaces",
        reason=(
            "The inspection and coverage projections a conformance run reads. _coverage is the "
            "ungoverned second coverage authority the campaign reconciles; its position here -- "
            "imported by every load, executed by none -- is why its single-representative-year "
            "defect went unobserved."
        ),
        members=_registry(
            "static_inspection",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="registry discovery and scheduling queries: the modelo discovery CLI, and the deadline engine",
        reason=(
            "Query projections over the loaded authority. _schedules is consumed by the deadline "
            "engine, which is the scheduling surface the coverage ADR keeps readable even for a "
            "filing year production refuses to serve."
        ),
        members=_registry(
            "filed_state",
            "queries",
            "query_reports",
            "schedules",
            "support_matrix",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="export record rendering and the dev export-tree generator",
        reason=(
            "Record design and export parsing, reached from the filing export surfaces and from "
            "the dev generators that author the export fragments."
        ),
        members=_registry(
            "export_parse",
            "record_design",
            "record_design_schema",
            "record_spec",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "relation prefill and modelo work review: application.calculations relation "
            "prefill, application.modelo work review"
        ),
        reason=(
            "Cross-modelo handoff and relation folding, which run when a relation is resolved "
            "rather than when the registry loads."
        ),
        members=_registry(
            "handoffs",
            "observation_fold",
            "_relation_aggregation",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="ledger binding resolution during calculate",
        reason=(
            "Resolves ledger-sourced binding values. Reached from the binding families rather "
            "than from the facade, so the reference map reports no external consumer for them."
        ),
        members=_registry(
            "counterpart_bindings",
            "_ledger_binding_resolution",
            "_m347_threshold",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="declaration-only surfaces consumed at import by the load path and by facade consumers",
        reason=(
            "These publish typed ids, cache objects, tolerance constants and resolved-construct "
            "models. They define no callable the load window could record, so their absence from "
            "every execution set is a property of the instrument. _validate_cache is the sharpest "
            "case: _validate binds its three caches at import on every cold load."
        ),
        members=_registry(
            "ids",
            "verification_tolerance",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="cross-revision contiguity advisory raised during registry validation",
        reason=(
            "Reached from _validate_cross_revision_evolution, which runs on a cold load. The "
            "contiguity failure builders inside it fire only for a corpus with a contiguity "
            "divergence, which the bundled corpus does not currently present."
        ),
        members=_registry("_validate_cross_revision_contiguity"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "profile readiness and grounding surfaces: application.modelo readiness, "
            "application.user_profile preflight, the wizard legal zone"
        ),
        reason="Projects profile-grounded registry facts when an operator surface asks for them.",
        members=_registry("profile_grounding"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="rate-box partition advisory during filing export parity",
        reason="Partitions rate boxes for the export parity and rate-box advisory surfaces.",
        members=_registry("rate_box_partition"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="sede declaration addressing, and the dev workbook-parity generator",
        reason="Addresses a snapshot coordinate for the sede declaration adapter and the parity tooling.",
        members=_registry("snapshot_coordinate"),
    ),
    # ── everything outside the registry package ─────────────────────────────
    ClassificationRule(
        classification="live",
        trigger="ValidatedRegistryAuthority.load",
        reason=(
            "Non-registry modules whose own code runs during a load: settings and the storage "
            "taxonomy, the bundled-resource boundary, the observability recorder, the TOML and "
            "annual-orden readers, and the domain schema and repository surfaces the compiler "
            "builds against."
        ),
        members=(
            "cadrumo.core",
            "cadrumo.core.bucket_pointer",
            "cadrumo.core.bucket_pointer",
            "cadrumo.core.config_integration_fields",
            "cadrumo.core.config_state_root",
            "cadrumo.core.config_support",
            "cadrumo.core.storage_taxonomy",
            "cadrumo.core.storage_taxonomy_locations",
            "cadrumo.core.access_gate.authorization",
            "cadrumo.core.aggregation",
            "cadrumo.core.atomic_write",
            "cadrumo.core.classification",
            "cadrumo.core.config",
            "cadrumo.core.decimal.coercion",
            "cadrumo.core.errors.error_codes",
            "cadrumo.core.errors.hierarchy",
            "cadrumo.core.errors.not_found",
            "cadrumo.core.errors.registry",
            "cadrumo.core.errors.registry._adapters",
            "cadrumo.core.errors.registry._adapters_part1",
            "cadrumo.core.errors.registry._adapters_part2",
            "cadrumo.core.errors.registry._application",
            "cadrumo.core.errors.registry._application_part1",
            "cadrumo.core.errors.registry._application_part2",
            "cadrumo.core.errors.registry._core",
            "cadrumo.core.errors.registry._domain",
            "cadrumo.core.errors.registry._domain_part1",
            "cadrumo.core.errors.registry._domain_part2",
            "cadrumo.core.errors.registry._domain_part3",
            "cadrumo.core.errors.registry._entrypoints",
            "cadrumo.core.errors.severity",
            "cadrumo.core.hashing",
            "cadrumo.core.i18n.render",
            "cadrumo.core.identity._nif_iva",
            "cadrumo.core.json_contract",
            "cadrumo.core.logging",
            "cadrumo.core.observability.capture",
            "cadrumo.core.observability.context",
            "cadrumo.core.observability.errors",
            "cadrumo.core.observability.fingerprint",
            "cadrumo.core.observability.models",
            "cadrumo.core.observability.recorder",
            "cadrumo.core.observability.redaction_rules",
            "cadrumo.core.observability.sink",
            "cadrumo.core.observability.store",
            "cadrumo.core.output_rendering",
            "cadrumo.core.paths",
            "cadrumo.core.redaction",
            "cadrumo.core.resources.bundled_data",
            "cadrumo.core.text_fold",
            "cadrumo.domain.calculations",
            "cadrumo.domain.calculations.row_casilla",
            "cadrumo.domain.calculations.row_source_identity",
            "cadrumo.domain.calculations.export_field_kind",
            "cadrumo.domain.iva.regimen_simplificado_rows",
            "cadrumo.domain.iva.schema",
            "cadrumo.domain.justificante",
            "cadrumo.domain.justificante.errors",
            "cadrumo.domain.justificante._protocols",
            "cadrumo.domain.justificante.schema",
            "cadrumo.domain.manuals.errors",
            "cadrumo.domain.manuals._ids",
            "cadrumo.domain.manuals.loader",
            "cadrumo.domain.manuals.schema",
            "cadrumo.domain.modelos.calculation_revision",
            "cadrumo.domain.modelos.calculation_revision_aggregate",
            "cadrumo.domain.modelos.calculation_revision_amendment",
            "cadrumo.domain.modelos.calculation_revision_m303_evidence",
            "cadrumo.domain.modelos.calculation_revision_m303_handoff",
            "cadrumo.domain.modelos.codes",
            "cadrumo.domain.modelos.errors",
            "cadrumo.domain.modelos.filing_record",
            "cadrumo.domain.modelos.filing_text",
            "cadrumo.domain.modelos.ledger_filing_snapshot",
            "cadrumo.domain.modelos.row_models",
            "cadrumo.domain.modelos.work_unit",
            "cadrumo.domain.user_profile.errors",
            "cadrumo.domain.user_profile.loader",
            "cadrumo.domain.user_profile.registry_contract",
            "cadrumo.domain.user_profile.schema",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="registry snapshot construction: build_snapshot and ValidatedRegistryAuthority.snapshot",
        reason=(
            "Spending-category resolution and casilla-id typing run when a snapshot is built, "
            "traced alongside the registry members of the same trigger."
        ),
        members=("cadrumo.core.i18n._translatable",),
        prefixes=("cadrumo.domain.categories",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="any import of the cadrumo root package",
        reason="The root package facade; its body runs on import and it owns no load behaviour.",
        members=("cadrumo",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="the eager cadrumo.core facade: importing any core symbol imports the whole typed spine",
        reason=(
            "The catch-all for core. These are the enums, typed ids, settings fragments, error "
            "types and small helpers a registry load pulls in because the core facade is eager, "
            "not because the load runs them; each one's behaviour belongs to the surface that "
            "owns its concept. This rule is deliberately coarse: the repo-wide drift detector is "
            "the instrument that looks INSIDE these modules, and duplicating its job here would "
            "produce a second inventory to keep in step."
        ),
        prefixes=("cadrumo.core",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="bundled-resource repository requests and the validated modelo authority",
        reason=(
            "The resource repositories are constructed lazily and load their bundled material on "
            "first get; the registry load reaches only the path boundary among them."
        ),
        prefixes=("cadrumo.core.resources",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="typed refusal construction on any error path",
        reason=(
            "The error catalogue declares its types at import and constructs them only when "
            "something refuses. A load that succeeds runs none of it."
        ),
        prefixes=("cadrumo.core.errors",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="operator telemetry emission from the CLI envelope",
        reason="Telemetry records an operator action; a library-level registry load emits none.",
        prefixes=("cadrumo.core.telemetry",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="profile identity resolution and NIF handling",
        reason=(
            "Identity resolution runs for a profile-scoped operation. The registry load reaches "
            "only the NIF-IVA helper, which is classified live separately."
        ),
        prefixes=("cadrumo.core.identity",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="numeric, temporal, textual and locale conversion at the surfaces that parse or render values",
        reason=(
            "Conversion helpers invoked by the surfaces that read operator input or render "
            "output. The load path touches only the decimal coercion and catalogue rendering "
            "helpers, classified live separately."
        ),
        prefixes=(
            "cadrumo.core.decimal",
            "cadrumo.core.i18n",
            "cadrumo.core.parsing",
            "cadrumo.core.time",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="capability gating on CLI surfaces",
        reason="Gates a capability-bound operator surface; nothing in a registry load is gated.",
        prefixes=("cadrumo.core.access_gate",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="IVA classification and settlement during ledger aggregation and M303 calculation",
        reason=(
            "The IVA domain answers category, rate, place-of-supply and prorrata questions when "
            "a transaction or an M303 settlement is computed. The load reaches only its schema "
            "and the regimen-simplificado row models."
        ),
        prefixes=("cadrumo.domain.iva", "cadrumo.domain.iva_compensation"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="taxpayer profile and family-circumstance resolution during Renta calculation",
        reason=(
            "Descendant, family and work-months facts are resolved when a Renta calculation or a "
            "profile edit asks for them."
        ),
        prefixes=("cadrumo.domain.contribuyente",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="deadline and recargo scheduling: the deadline engine",
        reason=(
            "The scheduling surface the coverage ADR keeps readable even where filing refuses. "
            "It consumes the loaded authority; it does not participate in loading it."
        ),
        prefixes=("cadrumo.domain.deadlines",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="authenticated AEAT session establishment",
        reason="Auth domain types are resolved when a session is opened against the sede.",
        prefixes=("cadrumo.domain.auth",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="period parsing at the surfaces that accept a period token, and the domain error and identifier spine",
        reason=(
            "Small shared domain surfaces reached by the same eager-facade effect as core: the "
            "load imports them and runs none of them."
        ),
        members=(
            "cadrumo.domain.errors",
            "cadrumo.domain.identifiers",
            "cadrumo.domain.period",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "cross-domain snapshot check registration, installed by "
            "_snapshot._install_cross_domain_snapshot_checks, and Renta calculation"
        ),
        reason=(
            "The renta package registers its first-slice and retenciones routing-integrity "
            "checks into the registry validator by import side effect, and _snapshot imports it "
            "by NAME from a module-level tuple. No AST import graph can see that edge, so these "
            "modules are absent from the static closure while the snapshot path certainly "
            "reaches them; the census recovers them by reading the tuple. The import-linter "
            "contract sanctions this direction explicitly -- the registry never names renta."
        ),
        prefixes=("cadrumo.domain.renta",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="taxpayer profile load, edit and portable export surfaces",
        reason=(
            "The profile surfaces the load does not run. The members the load DOES run -- the "
            "schema, loader and registry contract -- are classified live by exact entry above, "
            "so this prefix covers the remainder."
        ),
        prefixes=("cadrumo.domain.user_profile",),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="bienes de inversion regularisation, and filing evidence assembly",
        reason=(
            "Investment-goods regularisation and filing-evidence records are built by the filing "
            "surfaces, not by the registry load."
        ),
        members=("cadrumo.domain.filing_evidence",),
    ),
    # ── modules the load-census refactor left unruled ───────────────────────
    # Each classification below is decided by measurement rather than reading:
    # a module is `live` when `sys.modules` holds it after the bundled authority
    # has loaded, and `conditionally_reachable` when it does not. The triggers
    # name the module-level importers the census reports, so a rule that stops
    # matching the tree is a rule whose importer moved.
    ClassificationRule(
        classification="live",
        trigger="record-design parsing, reached from record_design on every load",
        reason=(
            "The record-design parse chain split into a family of modules: the PDF orchestration "
            "and the row, state, visual and repair passes beneath it, the workbook reader and its "
            "header handling, the shared layout markers both readers use, and the source resolution "
            "all of them consult. Every one is imported at module level from within that chain and "
            "every one is in sys.modules after a bundled load."
        ),
        members=_registry(
            "record_design_layout_markers",
            "record_design_pdf_orchestration",
            "record_design_pdf_repairs",
            "record_design_pdf_rows",
            "record_design_pdf_state",
            "record_design_pdf_visual",
            "record_design_sources",
            "record_design_workbook",
            "record_design_workbook_headers",
        ),
    ),
    ClassificationRule(
        classification="live",
        trigger="binding compilation: bindings and the ledger, invoice and relation binding families",
        reason=(
            "Binding compilation runs on every load, and these carry the parts it was split into: "
            "the shared target resolution, the selector support the ledger binding families import, "
            "the invoice row materialisation, the modelo 303 annual summary bindings the record "
            "section validator also reaches, and the relation dependency resolution that handoffs "
            "and revision members both consult."
        ),
        members=_registry(
            "_invoice_row_materialization",
            "binding_targets",
            "ledger_binding_selector_support",
            "m303_regimen_simplificado_annual_summary_bindings",
            "relation_dependency",
        ),
    ),
    ClassificationRule(
        classification="live",
        trigger="revision schema validation, imported by the validator modules on every load",
        reason=(
            "The revision validators import these directly: the condition mode the deadline and "
            "verification schemas share, the deadline declarations four validators read, and the "
            "revision member resolution applicability and handoffs also use. Validation is not "
            "optional on a load, so none of the three is conditional."
        ),
        members=_registry("condition_mode", "schema_deadlines", "schema_revision_members"),
    ),
    ClassificationRule(
        classification="live",
        trigger="formula runtime dispatch for modelo 100",
        reason=(
            "Imported at module level by the formula runtime, which the load reaches. The modelo "
            "split is a division of that runtime rather than a per-modelo gate, so it loads "
            "whether or not a modelo 100 formula is evaluated."
        ),
        members=_registry("formula_runtime_m100"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="function-scoped imports only: withholding row building and calculation revision identity",
        reason=(
            "Neither is in sys.modules after a bundled load, and neither has any module-level "
            "importer. `_withholding_rows` is imported from inside "
            "resolve_withholding_binding_row_values, which is the standard break for the cycle it "
            "forms with withholding_bindings and cannot be hoisted without restoring that cycle. "
            "Both are reached only when the function holding the import runs."
        ),
        members=(*_registry("_withholding_rows"), "cadrumo.domain.modelos.calculation_revision_identity"),
    ),
)


def _resolve(module: str) -> ClassificationRule | None:
    exact = [rule for rule in RULES if module in rule.members]
    if len(exact) > 1:
        raise ClassificationError(f"{module} is claimed by {len(exact)} rules; a module carries exactly one")
    if exact:
        return exact[0]
    best: ClassificationRule | None = None
    best_length = -1
    for rule in RULES:
        for prefix in rule.prefixes:
            if module == prefix or module.startswith(prefix + "."):
                if len(prefix) == best_length:
                    raise ClassificationError(f"{module} matches two rules at prefix depth {len(prefix)}")
                if len(prefix) > best_length:
                    best, best_length = rule, len(prefix)
    return best


def classify_universe(universe: frozenset[str]) -> Mapping[str, ClassificationRule]:
    """Resolve every module in ``universe`` to its reviewed classification.

    An exact member entry wins over any prefix; among prefixes the longest wins,
    and an exact tie at the same depth is an error rather than a silent pick.

    Args:
        universe: The derived set the census must classify.

    Returns:
        Only the modules a rule covers. A module absent from the result is
        unclassified, which is what the gate refuses on.
    """
    resolved: dict[str, ClassificationRule] = {}
    for module in sorted(universe):
        rule = _resolve(module)
        if rule is not None:
            resolved[module] = rule
    return resolved


def stale_rules(universe: frozenset[str]) -> tuple[str, ...]:
    """Return entries that no longer describe anything in the tree.

    A reviewed decision about a module that has been renamed or deleted is not
    harmless: it makes the table look more considered than it is, and it hides
    the rename from the next reader.

    Args:
        universe: The derived set the census must classify.

    Returns:
        Human-readable descriptions of each stale member or prefix.
    """
    stale: list[str] = []
    for rule in RULES:
        for member in rule.members:
            if member not in universe:
                stale.append(f"member {member} (rule: {rule.trigger}) is not in the census universe")
        for prefix in rule.prefixes:
            if not any(module == prefix or module.startswith(prefix + ".") for module in universe):
                stale.append(f"prefix {prefix} (rule: {rule.trigger}) matches nothing in the census universe")
    return tuple(stale)

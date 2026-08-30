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
            "_authority",
            "_bindings",
            "_compiled_cache",
            "_convenio",
            "_identity",
            "_loader",
            "loader_cache",
            "loader_fingerprints",
            "_m303_orden_census_artefact",
            "_m303_orden_constants",
            "_m303_orden_keys",
            "_m303_orden_legal",
            "_m303_orden_manifest",
            "_m303_orden_projection_compiler",
            "_m303_orden_projection_models",
            "_m303_orden_raw_models",
            "_m303_orden_source",
            "_schema_base",
            "_schema_references",
            "_source_evidence_fingerprint",
            "_supplementary_orden",
            "_toml_helpers",
            "_validate",
            "_validate_evidence",
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
            "_binding_aggregation",
            "_binding_selector_utils",
            "_bindings_previous_filing",
            "_casilla_membership",
            "_citation_blocklist",
            "_corpus_catalogue",
            "_cross_revision_divergence",
            "_detail_record_bindings",
            "_donativo_bindings",
            "_export",
            "_export_semantics",
            "_export_value_policy",
            "_fixed_width_codec",
            "_formula_operator_contracts",
            "_gasto193_bindings",
            "_invoice_bindings",
            "_irnr_ledger_bindings",
            "_iva_wallet_relation_targets",
            "_ledger_bindings",
            "_ledger_impatriado_bindings",
            "_legal",
            "_modelo_localization",
            "_period_offset_math",
            "record_design_coverage",
            "_relations",
            "_retenciones_bindings",
            "_runtime_graph",
            "_schema",
            "_schema_export_exemption",
            "_schema_exports",
            "_schema_extraction",
            "_schema_family_coverage",
            "_schema_formula",
            "_schema_governance",
            "_schema_input_kind",
            "_schema_rounding",
            "_schema_scalars",
            "_schema_surfaces",
            "_schema_verification",
            "_validate_applicability_section",
            "_validate_application_links",
            "_validate_authority_grade",
            "_validate_completeness",
            "_validate_constructs",
            "_validate_cross_revision",
            "_validate_cross_revision_contiguity",
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
            "_validate_registry_scope",
            "_validate_relation_periods",
            "_validate_relation_sources",
            "_validate_revision_closure",
            "_validate_revision_context",
            "_validate_revision_id_window_agreement",
            "_validate_revision_identity",
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
            "_withholding296_bindings",
            "_withholding_bindings",
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
            "_errors",
            "_period_selector_match",
            "_snapshot",
            "_temporal",
            "validate_cross_domain_snapshot",
            "_validate_reference_checker",
            "_validate_reference_sections",
            "_validate_references",
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
            "_applicability",
            "_applicability_labels",
            "_applicability_modelo202",
            "_applicability_payer_facts",
            "_applicability_routes",
            "_censo_modelos",
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
            "_formula_initial_values",
            "_formula_runtime",
            "_formula_runtime_irnr",
            "_formula_runtime_m131",
            "_formula_runtime_ops",
            "_formula_text_inputs",
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
            "_m303_differentiated_deduction_projection",
            "_m303_exonerado_390_projection",
            "_m303_orden_resolution",
            "_m303_prorrata_activity_projection",
            "_m303_regimen_simplificado_projection",
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
            "_aeat_hosts",
            "_aeat_nif_iva_oracle",
            "_checker_oracle_flow",
            "_external_grounding",
            "_groi_oracle",
            "_live_parity",
            "_remote_state_guard",
            "_renta_web_open_oracle",
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
            "_classification_coherence",
            "_coverage",
            "_static_inspection",
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
            "_filed_state",
            "_queries",
            "_query_reports",
            "_schedules",
            "_support_matrix",
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
            "_export_parse",
            "_record_design",
            "record_design_schema",
            "_record_spec",
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
            "_handoff_paths",
            "_handoffs",
            "_observation_fold",
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
            "_ids",
            "_verification_tolerance",
        ),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger=(
            "registry gates that import through the facade: the construct-resolution gate "
            "and the relation handoff-path audit gate"
        ),
        reason=(
            "Reached only from the package's own tests, which import them as 'from .. import "
            "symbol'. Both surfaced as dead candidates on the module-level import graph and both "
            "are alive; recording the trigger here is what keeps a later reader from repeating "
            "that mistake."
        ),
        members=_registry("_constructs"),
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
        members=_registry("_profile_grounding"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="rate-box partition advisory during filing export parity",
        reason="Partitions rate boxes for the export parity and rate-box advisory surfaces.",
        members=_registry("_rate_box_partition"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="sede declaration addressing, and the dev workbook-parity generator",
        reason="Addresses a snapshot coordinate for the sede declaration adapter and the parity tooling.",
        members=_registry("_snapshot_coordinate"),
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
            "cadrumo.core._config_integration_fields",
            "cadrumo.core._config_state_root",
            "cadrumo.core._config_support",
            "cadrumo.core._storage_taxonomy",
            "cadrumo.core._storage_taxonomy_locations",
            "cadrumo.core.access_gate._authorization",
            "cadrumo.core.aggregation",
            "cadrumo.core.atomic_write",
            "cadrumo.core.classification",
            "cadrumo.core.config",
            "cadrumo.core.decimal._coerce",
            "cadrumo.core.errors",
            "cadrumo.core.errors._registry",
            "cadrumo.core.hashing",
            "cadrumo.core.i18n._render",
            "cadrumo.core.identity._nif_iva",
            "cadrumo.core.json_contract",
            "cadrumo.core.logging",
            "cadrumo.core.observability",
            "cadrumo.core.observability.capture",
            "cadrumo.core.observability.context",
            "cadrumo.core.observability.errors",
            "cadrumo.core.observability.fingerprint",
            "cadrumo.core.observability.golden",
            "cadrumo.core.observability.models",
            "cadrumo.core.observability.recorder",
            "cadrumo.core.observability.redaction_rules",
            "cadrumo.core.observability.replay",
            "cadrumo.core.observability.sink",
            "cadrumo.core.observability.store",
            "cadrumo.core.output_rendering",
            "cadrumo.core.paths",
            "cadrumo.core.redaction",
            "cadrumo.core.resources._boundary",
            "cadrumo.core.text_fold",
            "cadrumo.domain.calculations.export_field_kind",
            "cadrumo.domain.iva.regimen_simplificado_rows",
            "cadrumo.domain.iva.schema",
            "cadrumo.domain.justificante",
            "cadrumo.domain.justificante.errors",
            "cadrumo.domain.justificante._protocols",
            "cadrumo.domain.justificante._schema",
            "cadrumo.domain.manuals",
            "cadrumo.domain.manuals.errors",
            "cadrumo.domain.manuals.fetch",
            "cadrumo.domain.manuals._ids",
            "cadrumo.domain.manuals.loader",
            "cadrumo.domain.manuals.rule_id",
            "cadrumo.domain.manuals.schema",
            "cadrumo.domain.manuals.verify",
            "cadrumo.domain.modelos",
            "cadrumo.domain.modelos._calculation_repository",
            "cadrumo.domain.modelos._calculation_revision_aggregate",
            "cadrumo.domain.modelos._calculation_revision_amendment",
            "cadrumo.domain.modelos._calculation_revision_m303_evidence",
            "cadrumo.domain.modelos._calculation_revision_m303_handoff",
            "cadrumo.domain.modelos._codes",
            "cadrumo.domain.modelos._dt12_reduccion",
            "cadrumo.domain.modelos.errors",
            "cadrumo.domain.modelos._filing_record",
            "cadrumo.domain.modelos._filing_repository",
            "cadrumo.domain.modelos._iae_exemption",
            "cadrumo.domain.modelos._ledger_filing_snapshot",
            "cadrumo.domain.modelos._m232_row_materialisation",
            "cadrumo.domain.modelos._participation_index",
            "cadrumo.domain.modelos._protocols",
            "cadrumo.domain.modelos._repository",
            "cadrumo.domain.modelos._row_models",
            "cadrumo.domain.modelos._sal_reserva_especial",
            "cadrumo.domain.modelos._verification_report",
            "cadrumo.domain.modelos._verification_repository",
            "cadrumo.domain.modelos._work_unit",
            "cadrumo.domain.user_profile",
            "cadrumo.domain.user_profile.errors",
            "cadrumo.domain.user_profile.labels",
            "cadrumo.domain.user_profile.loader",
            "cadrumo.domain.user_profile.registry_contract",
            "cadrumo.domain.user_profile.schema",
            "cadrumo.domain.user_profile.values",
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
        prefixes=("cadrumo.domain.iva", "cadrumo.domain.iva_compensation", "cadrumo.domain.prorrata_register"),
    ),
    ClassificationRule(
        classification="conditionally_reachable",
        trigger="ledger transaction ingest, classification and querying",
        reason="The transactions domain runs for ledger operations, never for a registry load.",
        prefixes=("cadrumo.domain.transactions", "cadrumo.domain.invoices"),
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
            "cadrumo.domain",
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
        members=(
            "cadrumo.domain.bienes_inversion",
            "cadrumo.domain.filing_evidence",
        ),
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

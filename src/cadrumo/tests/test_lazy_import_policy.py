"""Lazy-import policy gate: sanctioned classes, allowlist, and count ratchet.

Production carries roughly 815 function-local relative imports. The idiom
spans very different intents: sanctioned lazy resource loaders and CLI
cold-start deferrals at one end, and first-party module-cycle breaks plus
cross-layer softening at the other, where a cycle "fixed" by deferring an
import is hidden from the import-TIME graph the layered-contract linter audits
rather than removed. This gate draws the policy line between the two.

Five sanctioned classes plus the core-authority protect list are recognised
STRUCTURALLY here, and never need an allowlist entry:

1. Core resource-repository deferred loaders -- a function-local first-party
   import under ``core/resources/`` (the resource-management deferral; the audit
   records that the core resource repos lazy-import their domain loaders).
2. CLI cold-start / PEP 562 package-boundary deferrals -- a function-local
   import anywhere under ``entrypoints/cli/`` (the cold-start budget enforced by
   ``test_lazy_command_tree.py``) or an import inside a package ``__getattr__``
   body (the PEP 562 boundary applied to the user-profile lazy import and
   its application-boundary-lazy-by-default successor).
3. ``TYPE_CHECKING`` blocks -- type-only, never executed at runtime.
4. Optional third-party dependency guards -- an import inside a
   ``try: ... except ImportError`` (or ``ModuleNotFoundError``) handler.
5. Adapter heavy third-party-import deferrals -- a heavy third-party import
   deferred inside an adapter method for startup cost. Third-party by
   definition, so a FIRST-PARTY import never satisfies this class; it is named
   in the taxonomy so an author who trips the gate sees the full sanctioned set.

Everything else -- a function-local FIRST-PARTY (``cadrumo.*``) import that is not
one of the five -- is UNSANCTIONED and MUST carry an allowlist entry recording
its runtime-graph edge (consumer module -> imported module), its unsanctioned
class, the reason, and the restructuring disposition. A new unsanctioned edge
fails the gate unless its entry is added in the same change, making the erosion
a reviewed decision rather than invisible debt.

The gate walks the production source with the real ``ast`` module (no mocks, no
stubs): it collects every function-local import, excludes the sanctioned classes
structurally, and checks the remainder against the declared allowlist. The
allowlist edge set and its per-class site-count ceilings ratchet -- an increase
requires editing the declaration in the same commit; a decrease (the
domain->adapters edges are deleted via the ports-inversion; cycles get
restructured) is free, because the discovered set is only ever asserted to be a
SUBSET of the declaration.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from functools import cache
from typing import NamedTuple, override

import pytest

from ._inventory import (
    SRC_CADRUMO,
    ast_for_path,
    production_python_files,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class SanctionedClass(StrEnum):
    """The five inherited import-deferral classes recognised structurally.

    Members are ordered by their sanctioning rationale below. The value
    is the operator-facing label surfaced in a gate failure so an author who
    trips an unsanctioned site sees the full sanctioned taxonomy to classify
    against.
    """

    CORE_RESOURCE_LOADER = "core resource-repository deferred loader (core/resources/)"
    CLI_COLDSTART_PEP562 = "CLI cold-start / PEP 562 package-boundary deferral (entrypoints/cli/ or __getattr__)"
    TYPE_CHECKING_BLOCK = "TYPE_CHECKING block"
    OPTIONAL_THIRDPARTY_GUARD = "optional third-party dependency guard (try/except ImportError)"
    ADAPTER_HEAVY_IMPORT = "adapter heavy third-party-import deferral"


FIVE_SANCTIONED_CLASSES: tuple[SanctionedClass, ...] = tuple(SanctionedClass)


class Disposition(StrEnum):
    """The restructuring disposition an unsanctioned edge is held under."""

    DELETE_VIA_PORTS_INVERSION = "delete via the ports-inversion work"
    RESTRUCTURE_CYCLE = "restructure the module-load cycle"
    KEEP_BOOTSTRAP = "keep -- accepted bootstrap machinery"
    PENDING_REVIEW = "pending restructure review"


class UnsanctionedClass(StrEnum):
    """Closed taxonomy of unsanctioned function-local first-party import edges.

    Each member fixes the reason and restructuring disposition shared by every
    edge recorded under it, so the typed allowlist entry (edge, class, reason,
    disposition) is complete from the edge plus its class.
    """

    ERROR_REGISTRY_BOOTSTRAP = "core error-registry deferred-bind queue for circular-import windows"
    NAMED_CYCLE_BREAK = "an explicitly-documented module-load cycle break"
    PORTS_INVERSION_PENDING = "domain module importing a persistence adapter -- the ports-inversion seam"
    DOMAIN_CYCLE_BREAK = "domain-internal deferred import breaking a module-load cycle"
    ADAPTER_INTERNAL_DEFERRAL = "adapter-internal first-party deferral (not a heavy third-party import)"
    CORE_INTERNAL_DEFERRAL = "core-internal deferred import outside the resource-loader surface"
    APPLICATION_DEFERRAL = "application-layer deferred import (cold-start or cycle break)"


# Reason + disposition metadata for each unsanctioned class. The reason names the
# origin; the disposition is the standing worklist verdict.
_CLASS_METADATA: dict[UnsanctionedClass, tuple[str, Disposition]] = {
    UnsanctionedClass.ERROR_REGISTRY_BOOTSTRAP: (
        "core/errors deferred-bind queue resolves error classes inside a "
        "circular-import window (a protected core-authority boundary).",
        Disposition.KEEP_BOOTSTRAP,
    ),
    UnsanctionedClass.NAMED_CYCLE_BREAK: (
        "application/overview/_coverage defers an import explicitly to break a module-load cycle.",
        Disposition.RESTRUCTURE_CYCLE,
    ),
    UnsanctionedClass.PORTS_INVERSION_PENDING: (
        "domain package binds a persistence adapter through a deferred import; "
        "the ports-inversion work deletes this seam per domain.",
        Disposition.DELETE_VIA_PORTS_INVERSION,
    ),
    UnsanctionedClass.DOMAIN_CYCLE_BREAK: (
        "domain-internal deferral softening a module-load cycle inside the domain layer.",
        Disposition.PENDING_REVIEW,
    ),
    UnsanctionedClass.ADAPTER_INTERNAL_DEFERRAL: (
        "adapter method defers a first-party import (a cross-adapter or "
        "domain/application reference), not a heavy third-party library.",
        Disposition.PENDING_REVIEW,
    ),
    UnsanctionedClass.CORE_INTERNAL_DEFERRAL: (
        "core module outside core/resources/ defers a first-party import.",
        Disposition.PENDING_REVIEW,
    ),
    UnsanctionedClass.APPLICATION_DEFERRAL: (
        "application-layer service defers a first-party import for cold-start cost or to break a module-load cycle.",
        Disposition.PENDING_REVIEW,
    ),
}


class ImportEdge(NamedTuple):
    """A runtime-graph edge: an cadrumo-relative consumer module importing another.

    Both names are cadrumo-relative dotted module paths (the leading ``cadrumo.`` is
    stripped); the empty string denotes the ``cadrumo`` package root.
    """

    consumer: str
    target: str


class _LocalImport(NamedTuple):
    """A discovered function-local import site with its resolution context."""

    relative_path: str
    lineno: int
    edge: ImportEdge


# Baseline allowlist: every current unsanctioned function-local first-party
# import EDGE, grouped by unsanctioned class. Generated once from the gate's own
# AST walk and asserted to be a SUPERSET of the live discovered set thereafter,
# so the ports-inversion edge removals never fight this declaration. To ADD a new edge, add
# it here in the same commit and raise the matching per-class ceiling below; to
# REMOVE one, deletion is free (the subset check still holds).
_ALLOWLIST: dict[UnsanctionedClass, frozenset[ImportEdge]] = {
    UnsanctionedClass.ERROR_REGISTRY_BOOTSTRAP: frozenset(
        {
            ImportEdge("core.errors", "core.errors._registry"),
            ImportEdge("core.errors._registry", "core.i18n"),
            ImportEdge("core.errors._registry", "core.json_contract"),
        }
    ),
    UnsanctionedClass.NAMED_CYCLE_BREAK: frozenset(
        {
            ImportEdge("application.overview._coverage", "application.modelo"),
        }
    ),
    UnsanctionedClass.PORTS_INVERSION_PENDING: frozenset(),
    UnsanctionedClass.DOMAIN_CYCLE_BREAK: frozenset(
        {
            ImportEdge("domain.calculations._export_field_kind", "domain.calculations.registry"),
            ImportEdge("domain.calculations.registry._corpus_catalogue", "core.config"),
            ImportEdge("domain.calculations.registry._corpus_catalogue", "domain.manuals"),
            ImportEdge("domain.calculations.registry._formula_runtime_ops", "core.resources"),
            ImportEdge("domain.calculations.registry._formula_runtime_ops", "domain.calculations.registry._authority"),
            ImportEdge("domain.calculations.registry._invoice_bindings", "domain.modelos"),
            ImportEdge("domain.calculations.registry._legal", "domain.manuals"),
            ImportEdge(
                "domain.calculations.registry._record_design_coverage", "domain.calculations.registry._record_design"
            ),
            ImportEdge("domain.calculations.registry._remote_state_guard", "core.config"),
            ImportEdge("domain.calculations.registry._schema", "domain.calculations.registry._binding_selector_utils"),
            ImportEdge("domain.calculations.registry._schema", "domain.calculations.registry._bindings"),
            ImportEdge("domain.calculations.registry._validate", "domain.user_profile"),
            ImportEdge(
                "domain.calculations.registry._validate_cross_domain_snapshot",
                "domain.calculations.registry._ledger_bindings",
            ),
            ImportEdge(
                "domain.calculations.registry._validate_reference_sections", "domain.calculations.registry._bindings"
            ),
            ImportEdge(
                "domain.calculations.registry._validate_registry_scope", "domain.calculations.registry._bindings"
            ),
            ImportEdge("domain.calculations.registry._workbook_parity", "core.config"),
            ImportEdge("domain.contribuyente.family", "core.i18n"),
            ImportEdge("domain.deadlines._engine", "core.resources"),
            ImportEdge("domain.deadlines._engine", "domain.calculations.registry"),
            ImportEdge("domain.deadlines._plazo", "core.resources"),
            ImportEdge("domain.deadlines._plazo", "domain.calculations.registry"),
            ImportEdge("domain.fincas._aggregates", "domain.fincas._models"),
            ImportEdge("domain.fincas._amortization_ledger", "domain.calculations.registry"),
            ImportEdge("domain.fincas._imputacion_parameters", "domain.calculations.registry"),
            ImportEdge("domain.fincas._tier_resolver", "domain.calculations.registry"),
            ImportEdge("domain.iva._invoice_classification", "domain.calculations.registry"),
            ImportEdge("domain.iva._invoice_classification", "domain.invoices"),
            ImportEdge("domain.iva._recargo_equivalencia", "domain.calculations.registry"),
            ImportEdge("domain.usage_ratios._service", "core.config"),
            ImportEdge("domain.usage_ratios._service", "core.locks"),
            ImportEdge("domain.user_profile._registry_contract", "domain.calculations.registry"),
        }
    ),
    UnsanctionedClass.ADAPTER_INTERNAL_DEFERRAL: frozenset(
        {
            # buckets event-history repository ports-inversion:
            # the concrete BucketEventHistoryRepository defers the storage-substrate
            # import from the persistence adapter (was domain._event_repository).
            ImportEdge("adapters.persistence.profile.buckets", "adapters.persistence.storage"),
            # filing amendment repository ports-inversion: the concrete
            # ModeloAmendmentRepository defers the storage-substrate import from the
            # persistence adapter (was domain.filing._complementaria_repository).
            ImportEdge("adapters.persistence.profile.filing_amendments", "adapters.persistence.storage"),
            # modelos_calculation catalogue repository ports-inversion:
            # the concrete CalculationRevisionCatalogueRepository defers the
            # storage-substrate import from the persistence adapter
            # (was domain.modelos._calculation_repository).
            ImportEdge("adapters.persistence.profile.modelos_calculation", "adapters.persistence.storage"),
            # transactions catalogue repository ports-inversion:
            # the concrete TransactionCatalogueRepository defers the storage-substrate
            # imports from the persistence adapter (was domain.transactions._repository).
            ImportEdge("adapters.persistence.profile.transactions", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.transactions", "adapters.persistence.storage.crypto"),
            ImportEdge("adapters.inbound.justificante._parser", "core.config"),
            ImportEdge(
                "adapters.inbound.justificante._parsers", "adapters.inbound.justificante._parsers._pdfplumber_backend"
            ),
            ImportEdge("adapters.outbound.aeat.auth._authenticator", "core"),
            ImportEdge("adapters.outbound.aeat.auth._authenticator", "core.auth_session_keys"),
            ImportEdge("adapters.outbound.aeat.auth._authenticator", "core.i18n"),
            ImportEdge("adapters.outbound.aeat.auth._authenticator", "core.redaction"),
            ImportEdge("adapters.outbound.aeat.auth._clave_movil", "core"),
            ImportEdge("adapters.outbound.aeat.auth._clave_movil", "core.auth_session_keys"),
            ImportEdge("adapters.outbound.aeat.browser._factory", "adapters.outbound.aeat.browser._errors"),
            ImportEdge("adapters.outbound.aeat.browser._factory", "core"),
            ImportEdge("adapters.outbound.aeat.browser.evasion", "core"),
            ImportEdge("adapters.outbound.aeat.sede._adapter_utils", "adapters.outbound.aeat.sede._browser_constants"),
            ImportEdge("adapters.outbound.aeat.sede._declarations", "adapters.outbound.aeat.sede._schema"),
            ImportEdge("adapters.outbound.aeat.sede._declarations", "core"),
            ImportEdge("adapters.outbound.aeat.sede._declarations_observations", "domain.calculations.registry"),
            ImportEdge("adapters.outbound.aeat.verify", "adapters.outbound.aeat.browser"),
            ImportEdge("adapters.outbound.aeat.verify", "core.config"),
            ImportEdge("adapters.outbound.google._oauth_flow", "application.user_profile"),
            ImportEdge("adapters.outbound.google._oauth_flow", "application.workflow"),
            ImportEdge("adapters.outbound.llm._client", "adapters.outbound.llm._providers.anthropic"),
            ImportEdge("adapters.outbound.llm._client", "core"),
            ImportEdge("adapters.outbound.llm._providers.anthropic", "core"),
            ImportEdge("adapters.outbound.storage._factory", "adapters.outbound.google"),
            ImportEdge("adapters.outbound.storage._factory", "adapters.outbound.storage._google_drive"),
            ImportEdge("adapters.outbound.storage._factory", "adapters.outbound.storage._local"),
            ImportEdge("adapters.outbound.storage._factory", "adapters.persistence.storage.bucket"),
            ImportEdge("adapters.persistence.profile.fincas", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.fincas", "adapters.persistence.storage.sql"),
            ImportEdge("adapters.persistence.profile.invoices", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.invoices", "core"),
            ImportEdge("adapters.persistence.profile.invoices", "core.config"),
            ImportEdge("adapters.persistence.profile.modelos_filing", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.modelos_work_units", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.modelos_verification_reports", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.participation_index", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.submission", "adapters.persistence.storage.sql"),
            ImportEdge("adapters.persistence.profile.usage_ratios", "adapters.persistence.storage"),
            ImportEdge("adapters.persistence.profile.usage_ratios", "adapters.persistence.storage.errors"),
            ImportEdge("adapters.persistence.profile.usage_ratios", "adapters.persistence.storage.runtime_repository"),
            ImportEdge("adapters.persistence.storage.blob_store._materialisation", "core.config"),
            ImportEdge("adapters.persistence.storage.envelope._repository_test_suite", "tests.secure_sql"),
            ImportEdge(
                "adapters.persistence.storage.master_key._bucket_session", "adapters.persistence.storage.sql.engine"
            ),
            ImportEdge("adapters.persistence.storage.master_key._kdf_params", "adapters.persistence.storage.bucket"),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key",
                "adapters.persistence.storage._namespace_registry",
            ),
            ImportEdge("adapters.persistence.storage.master_key._master_key", "adapters.persistence.storage.bucket"),
            ImportEdge("adapters.persistence.storage.master_key._master_key", "adapters.persistence.storage.crypto"),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key",
                "adapters.persistence.storage.master_key._active_session",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key",
                "adapters.persistence.storage.master_key._bucket_session",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key", "adapters.persistence.storage.master_key._errors"
            ),
            ImportEdge("adapters.persistence.storage.master_key._master_key", "core.config"),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_bucket_dek",
                "adapters.persistence.storage._namespace_registry",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_bucket_dek", "adapters.persistence.storage.bucket"
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_bucket_dek", "adapters.persistence.storage.errors"
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_bucket_dek",
                "adapters.persistence.storage.master_key._dek_wrap",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_ephemeral",
                "adapters.persistence.storage.master_key._active_session",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_ephemeral",
                "adapters.persistence.storage.master_key._bucket_session",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._master_key_ephemeral",
                "adapters.persistence.storage.master_key._errors",
            ),
            ImportEdge("adapters.persistence.storage.master_key._master_key_io", "core.config"),
            ImportEdge("adapters.persistence.storage.master_key._master_key_tax_id", "core.identity"),
            ImportEdge(
                "adapters.persistence.storage.master_key._recovery",
                "adapters.persistence.storage.master_key._master_key",
            ),
            ImportEdge(
                "adapters.persistence.storage.master_key._recovery_facade",
                "adapters.persistence.storage.master_key._master_key",
            ),
            ImportEdge("adapters.persistence.storage.runtime", "adapters.persistence.storage.bucket"),
            ImportEdge("adapters.persistence.storage.runtime", "adapters.persistence.storage.sql.secure_objects"),
            ImportEdge("adapters.persistence.storage.runtime", "core"),
            ImportEdge("adapters.persistence.storage.runtime", "core.i18n"),
            ImportEdge("adapters.persistence.storage.runtime_repository", "adapters.persistence.storage.sql.engine"),
            ImportEdge("adapters.persistence.storage.runtime_repository", "core"),
            ImportEdge("adapters.persistence.storage.secret_store._secret_store", "core.atomic_write"),
            ImportEdge("adapters.persistence.storage.sql.engine", "adapters.persistence.storage.sql._orm"),
            ImportEdge("adapters.persistence.storage.sql.secure_objects", "adapters.persistence.storage.errors"),
            ImportEdge("adapters.persistence.storage.sql.secure_objects", "adapters.persistence.storage.master_key"),
            ImportEdge("adapters.persistence.storage.sql.secure_objects", "adapters.persistence.storage.runtime"),
        }
    ),
    UnsanctionedClass.CORE_INTERNAL_DEFERRAL: frozenset(
        {
            ImportEdge("core._bucket_pointer_io", "core.atomic_write"),
            ImportEdge("core._bucket_pointer_io", "core.config"),
            ImportEdge("core._bucket_pointer_io", "core.errors"),
            ImportEdge("core._config_storage_route", "core.config"),
            ImportEdge("core.config", "core"),
            ImportEdge("core.config", "core.external_constants"),
            ImportEdge("core.config", "core.i18n"),
            ImportEdge("core.corpus_manifest", "core.atomic_write"),
            # Cycle-backed package/facade deferrals retained after the D9 follow-up lift:
            # `_bundle_signing` needs functions defined in `core.corpus_manifest.__init__`,
            # and `_http_sink` logging would cycle through logging -> config -> telemetry.
            ImportEdge("core.corpus_manifest._bundle_signing", "core.corpus_manifest"),
            ImportEdge("core.env_io", "core.atomic_write"),
            ImportEdge("core.json_contract", "core.observability"),
            ImportEdge("core.json_contract", "core.output_rendering"),
            ImportEdge("core.logging", "core.config"),
            # The former-product state-root refusal is rendered on the logging
            # and output-rendering cold paths; both defer the leaf error import
            # so help/version stay state-free (product-rename state boundary).
            ImportEdge("core.logging", "core._config_state_root"),
            ImportEdge("core.logging", "core.observability"),
            ImportEdge("core.observability._context", "core.config"),
            ImportEdge("core.observability._context", "core.observability._recorder"),
            ImportEdge("core.observability._fingerprint", "core.config"),
            ImportEdge("core.observability._redaction_rules", "core.classification"),
            ImportEdge("core.observability._redaction_rules", "core.redaction"),
            ImportEdge("core.observability._replay", "core.observability._capture"),
            ImportEdge("core.observability._replay", "core.observability._fingerprint"),
            ImportEdge("core.observability._replay", "core.observability._golden"),
            ImportEdge("core.observability._replay", "core.observability._store"),
            ImportEdge("core.observability._sink", "core.redaction"),
            ImportEdge("core.observability._store", "core.redaction"),
            ImportEdge("core.output_rendering", "core._config_state_root"),
            ImportEdge("core.output_rendering", "core.config"),
            ImportEdge("core.redaction", "core.errors"),
            ImportEdge("core.telemetry._http_sink", "core.logging"),
            ImportEdge("core.time._clock", "core.config"),
        }
    ),
    UnsanctionedClass.APPLICATION_DEFERRAL: frozenset(
        {
            # buckets event-history repository ports-inversion:
            # deferred consumers now reach the concrete repository at its
            # persistence-adapter home (was a domain.buckets deferral).
            ImportEdge("application.auth._operator", "adapters.persistence.profile.buckets"),
            ImportEdge("application.live._justificante", "adapters.persistence.profile.buckets"),
            ImportEdge("application.modelo._iva_wallet_seed", "adapters.persistence.profile.buckets"),
            ImportEdge("application.modelo._reconcile", "adapters.persistence.profile.buckets"),
            ImportEdge("application.user_profile._orchestration", "adapters.persistence.profile.buckets"),
            # modelos_calculation catalogue repository ports-inversion:
            # deferred consumers now reach the concrete repository at its
            # persistence-adapter home (was a domain.modelos deferral).
            ImportEdge("application.modelo._iva_wallet_seed", "adapters.persistence.profile.modelos_calculation"),
            ImportEdge("application.modelo._reconcile", "adapters.persistence.profile.modelos_calculation"),
            ImportEdge("application.user_profile._bundle", "adapters.persistence.profile.modelos_calculation"),
            # transactions catalogue repository ports-inversion: the
            # concrete TransactionCatalogueRepository moved to the persistence adapter,
            # so these deferred consumers now defer-import it from the adapter home.
            # The calculation-observation repository remains deferred because importing
            # application.calculations while application.filing initializes cycles through
            # aggregation -> user_profile -> workflow -> filing.
            ImportEdge("application.filing._review", "application.calculations"),
            ImportEdge("application.filing._review", "adapters.persistence.profile.transactions"),
            ImportEdge("application.review._adapters", "adapters.persistence.profile.transactions"),
            ImportEdge("application.user_profile._bundle", "adapters.persistence.profile.transactions"),
            ImportEdge("application.workflow._models", "adapters.persistence.profile.transactions"),
            ImportEdge("agent", "agent._skill_metadata"),
            ImportEdge("application.aggregation._source_profile", "application.modelo"),
            ImportEdge("application.aggregation._source_profile", "core.resources"),
            ImportEdge("application.auth", "adapters.outbound.aeat.auth"),
            ImportEdge("application.auth", "core.i18n"),
            ImportEdge("application.auth._acquisition_lock", "core"),
            ImportEdge("application.auth._apoderado", "core.config"),
            # certificate-source registry operator verbs mirror
            # the sibling `_operator` deferrals below for the same targets.
            ImportEdge("application.auth._certificate_sources_operator", "adapters.persistence.profile.buckets"),
            ImportEdge("application.auth._certificate_sources_operator", "adapters.persistence.storage"),
            ImportEdge("application.auth._certificate_sources_operator", "application.workflow"),
            ImportEdge("application.auth._certificate_sources_operator", "core"),
            ImportEdge("application.auth._certificate_sources_operator", "domain.buckets"),
            ImportEdge("application.auth._operator", "adapters.persistence.storage"),
            ImportEdge("application.auth._operator", "application.state_projection"),
            ImportEdge("application.auth._operator", "application.user_profile"),
            ImportEdge("application.auth._operator", "application.workflow"),
            ImportEdge("application.auth._operator", "core"),
            ImportEdge("application.auth._operator", "core.access_gate"),
            ImportEdge("application.auth._operator", "domain.buckets"),
            ImportEdge("application.auth._operator_probes", "adapters.outbound.aeat.auth"),
            ImportEdge("application.auth._operator_probes", "adapters.outbound.aeat.auth.certificate"),
            ImportEdge("application.auth._operator_probes", "application.user_profile"),
            ImportEdge("application.auth._operator_probes", "application.workflow"),
            ImportEdge("application.auth._operator_scope", "adapters.persistence.storage"),
            ImportEdge("application.auth._operator_scope", "application.user_profile"),
            ImportEdge("application.auth._operator_scope", "core"),
            ImportEdge("application.auth._operator_scope", "core.config"),
            ImportEdge("application.auth._sessions", "adapters.outbound.aeat.auth"),
            ImportEdge("application.auth._sessions", "adapters.outbound.aeat.browser"),
            ImportEdge("application.auth._sessions", "adapters.persistence.storage"),
            ImportEdge("application.auth._sessions", "application.user_profile"),
            ImportEdge("application.auth._sessions", "core"),
            ImportEdge("application.auth._sessions", "core.auth_session_keys"),
            ImportEdge("application.auth._sessions", "core.config"),
            ImportEdge("application.auth._sessions", "domain.user_profile"),
            ImportEdge("application.bucket_maintenance._service", "adapters.persistence.profile.modelos_filing"),
            ImportEdge("application.bucket_maintenance._service", "adapters.persistence.storage.bucket"),
            ImportEdge("application.bucket_maintenance._service", "adapters.persistence.storage.crypto"),
            ImportEdge("application.bucket_maintenance._service", "adapters.persistence.storage.master_key"),
            ImportEdge("application.bucket_maintenance._service", "adapters.persistence.storage.runtime_repository"),
            ImportEdge("application.bucket_maintenance._service", "application.workflow"),
            ImportEdge("application.bucket_maintenance._service", "core"),
            ImportEdge("application.bucket_maintenance._service", "core.config"),
            ImportEdge("application.bucket_maintenance._service", "domain.retention"),
            ImportEdge("application.bucket_maintenance._service", "domain.user_profile"),
            ImportEdge("application.calculations._binding_prefill", "application.modelo"),
            ImportEdge("application.calculations._iva_compensation_annual_partition", "core.resources"),
            ImportEdge(
                "application.calculations._iva_wallet_reconciliation", "application.calculations._binding_prefill"
            ),
            ImportEdge(
                "application.calculations._iva_wallet_reconciliation",
                "application.calculations._observations_repository",
            ),
            ImportEdge("application.calculations._m111_no_retenciones", "application.user_profile"),
            ImportEdge("application.calculations._m111_no_retenciones", "domain.user_profile"),
            ImportEdge("application.calculations._multi_year", "application.calculations._binding_prefill"),
            ImportEdge("application.calculations._multi_year", "application.calculations._relation_prefill"),
            ImportEdge("application.calculations._multi_year", "core.access_gate"),
            ImportEdge("application.calculations._multi_year", "core.resources"),
            ImportEdge(
                "application.calculations._relation_prefill", "application.calculations._cross_period_clean_state"
            ),
            ImportEdge("application.calculations._relation_prefill", "application.user_profile"),
            ImportEdge("application.calculations._relation_prefill", "core"),
            ImportEdge("application.calculations._relation_prefill", "core.resources"),
            ImportEdge("application.calculations._relation_prefill", "domain.calculations.registry"),
            ImportEdge("application.calculations._relation_prefill", "domain.deadlines"),
            ImportEdge("application.calculations._relation_prefill", "domain.user_profile"),
            ImportEdge("application.config_reset", "application.diagnostics"),
            ImportEdge("application.config_reset", "application.user_profile"),
            ImportEdge("application.config_reset", "application.workflow"),
            ImportEdge("application.corpus_search._embed_build", "application.corpus_search._errors"),
            ImportEdge("application.corpus_search._lexical_index", "application.corpus_search._errors"),
            ImportEdge("application.diagnostics", "adapters.outbound.aeat.browser"),
            ImportEdge("application.diagnostics", "adapters.persistence.storage"),
            ImportEdge("application.diagnostics", "adapters.persistence.storage.master_key"),
            ImportEdge("application.diagnostics", "application.repair_integrity"),
            ImportEdge("application.diagnostics", "application.user_profile"),
            ImportEdge("application.diagnostics", "application.wizard"),
            ImportEdge("application.diagnostics", "application.workflow"),
            ImportEdge("application.diagnostics", "core"),
            ImportEdge("application.diagnostics", "core.config"),
            ImportEdge("application.diagnostics", "domain.calculations.registry"),
            ImportEdge("application.evidence._service", "core.config"),
            ImportEdge("application.evidence._service", "domain.buckets"),
            ImportEdge("application.filing._complementaria", "application.filing"),
            ImportEdge("application.filing._import", "application.filing"),
            ImportEdge("application.filing._import", "domain.submission"),
            ImportEdge("application.filing._runtime_repository", "adapters.persistence.storage"),
            ImportEdge("application.filing.runtime", "application.wizard"),
            ImportEdge("application.filing.runtime", "application.workflow"),
            ImportEdge("application.inventory._service", "core.config"),
            ImportEdge("application.inventory._service", "domain.buckets"),
            ImportEdge("application.invoices._creation", "domain.invoices"),
            ImportEdge("application.ledger._actions_classification", "application.ledger._rule_repository"),
            ImportEdge("application.ledger._actions_classification", "domain.transactions"),
            ImportEdge("application.ledger._actions_common", "adapters.persistence.storage"),
            ImportEdge("application.ledger._actions_common", "application.ledger._evidence"),
            ImportEdge("application.ledger._actions_common", "core.config"),
            ImportEdge("application.ledger._actions_import", "adapters.inbound.financial.providers"),
            ImportEdge("application.ledger._business_operation_invoice", "core.config"),
            ImportEdge("application.ledger._business_operation_invoice", "domain.buckets"),
            ImportEdge("application.ledger._evidence", "core.config"),
            # Vision helper imports InvoiceDraft from this module; eagering it recreates
            # the evidence-draft <-> vision helper cycle.
            ImportEdge("application.ledger._evidence_draft", "application.ledger._evidence_draft_vision"),
            ImportEdge("application.ledger._evidence_input", "application.user_profile"),
            ImportEdge("application.ledger._evidence_input", "core"),
            ImportEdge("application.ledger._llm_classification", "adapters.outbound.llm"),
            ImportEdge("application.ledger._llm_classification", "application.provisioning"),
            ImportEdge("application.ledger._llm_classification", "application.user_profile"),
            ImportEdge("application.ledger._llm_classification", "core"),
            ImportEdge("application.ledger._llm_classification", "domain.transactions"),
            ImportEdge("application.ledger._preflight", "application.user_profile"),
            ImportEdge("application.ledger._review_projection", "adapters.persistence.storage"),
            ImportEdge("application.live", "adapters.outbound.aeat.sede"),
            ImportEdge("application.live", "application.live._expedientes"),
            ImportEdge("application.live", "application.live._notifications"),
            ImportEdge("application.live._errors", "adapters.outbound.aeat.auth"),
            ImportEdge("application.live._errors", "adapters.outbound.aeat.sede"),
            ImportEdge("application.live._filed_observation_persistence", "application.live._justificante"),
            ImportEdge("application.live._iva_remote_state", "adapters.persistence.storage"),
            ImportEdge("application.live._justificante", "adapters.inbound.justificante"),
            ImportEdge("application.live._justificante", "adapters.persistence.profile.justificante"),
            ImportEdge("application.live._justificante", "adapters.persistence.profile.modelos_filing"),
            ImportEdge("application.live._justificante", "application.modelo"),
            ImportEdge("application.live._justificante", "application.user_profile"),
            ImportEdge("application.live._justificante", "core.errors"),
            ImportEdge("application.live._justificante", "core.time"),
            ImportEdge("application.live._justificante", "domain.buckets"),
            ImportEdge("application.live._justificante", "domain.justificante"),
            ImportEdge("application.live._justificante", "domain.modelos"),
            ImportEdge("application.modelo._binding_readiness", "core.resources"),
            ImportEdge("application.modelo._binding_resolution", "application.aggregation"),
            ImportEdge("application.modelo._borrador_binding", "core.resources"),
            ImportEdge("application.modelo._calculate_input", "application.modelo._action_errors"),
            ImportEdge("application.modelo._calculate_input", "application.modelo._calculation_actions"),
            ImportEdge("application.modelo._calculate_input", "application.modelo._work_lifecycle"),
            ImportEdge("application.modelo._calculate_input", "application.user_profile"),
            ImportEdge("application.modelo._calculate_input", "application.workflow"),
            ImportEdge("application.modelo._calculate_input", "core.access_gate"),
            ImportEdge("application.modelo._calculate_input", "domain.calculations.registry"),
            ImportEdge("application.modelo._calculation_actions", "application.aggregation"),
            ImportEdge("application.modelo._calculation_actions", "application.calculations"),
            ImportEdge("application.modelo._calculation_actions", "application.invoices"),
            ImportEdge("application.modelo._calculation_actions", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._calculation_helpers", "domain.calculations.registry"),
            ImportEdge("application.modelo._calculation_preparation", "application.ledger"),
            ImportEdge("application.modelo._calculation_preparation", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._calculation_preparation", "application.user_profile"),
            ImportEdge("application.modelo._calculation_preparation", "domain.user_profile"),
            ImportEdge("application.modelo._export", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._export", "application.user_profile"),
            ImportEdge("application.modelo._export", "core"),
            ImportEdge("application.modelo._export", "domain.user_profile"),
            ImportEdge("application.modelo._filing_actions", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._iva_wallet_gate", "application.aggregation"),
            ImportEdge("application.modelo._iva_wallet_gate", "application.calculations"),
            ImportEdge("application.modelo._iva_wallet_gate", "application.user_profile"),
            ImportEdge("application.modelo._iva_wallet_gate", "core.parsing"),
            ImportEdge("application.modelo._iva_wallet_gate", "core.resources"),
            ImportEdge("application.modelo._iva_wallet_gate", "domain.user_profile"),
            ImportEdge("application.modelo._iva_wallet_seed", "adapters.persistence.profile.modelos_work_units"),
            ImportEdge("application.modelo._iva_wallet_seed", "application.calculations"),
            ImportEdge("application.modelo._iva_wallet_seed", "core.resources"),
            ImportEdge("application.modelo._iva_wallet_seed", "core.time"),
            ImportEdge("application.modelo._iva_wallet_seed", "domain.buckets"),
            ImportEdge("application.modelo._iva_wallet_seed", "domain.iva_compensation"),
            ImportEdge("application.modelo._m036_lifecycle", "application.live"),
            ImportEdge("application.modelo._minimo_descendientes_advisory", "application.user_profile"),
            ImportEdge("application.modelo._official_box_advisory", "application.modelo._verification_actions"),
            ImportEdge("application.modelo._profile_binding", "application.user_profile"),
            ImportEdge("application.modelo._projection", "core"),
            ImportEdge("application.modelo._quickfile", "application.state_projection"),
            ImportEdge("application.modelo._reconcile", "adapters.inbound.declaracion"),
            ImportEdge("application.modelo._reconcile", "adapters.inbound.justificante"),
            ImportEdge("application.modelo._reconcile", "adapters.persistence.profile.modelos_work_units"),
            ImportEdge("application.modelo._reconcile", "application.modelo._calculation_helpers"),
            ImportEdge("application.modelo._reconcile", "application.user_profile"),
            ImportEdge("application.modelo._reconcile", "application.workflow"),
            ImportEdge("application.modelo._reconcile", "domain.buckets"),
            ImportEdge("application.modelo._reconcile", "domain.calculations.registry"),
            ImportEdge("application.modelo._reconcile", "domain.justificante"),
            ImportEdge("application.modelo._reconcile", "domain.modelos"),
            ImportEdge("application.modelo._registry_helpers", "domain.calculations.registry"),
            ImportEdge("application.modelo._registry_resources", "core.resources"),
            ImportEdge("application.modelo._registry_resources", "domain.calculations.registry"),
            ImportEdge("application.modelo._taxation_comparison", "adapters.persistence.profile.modelos_work_units"),
            ImportEdge("application.modelo._taxation_comparison", "application.aggregation"),
            ImportEdge("application.modelo._taxation_comparison", "application.modelo._action_errors"),
            ImportEdge("application.modelo._taxation_comparison", "application.modelo._binding_resolution"),
            ImportEdge("application.modelo._taxation_comparison", "application.modelo._registry_resources"),
            ImportEdge("application.modelo._taxation_comparison", "application.modelo._work_addressing"),
            ImportEdge("application.modelo._taxation_comparison", "domain.calculations.registry"),
            ImportEdge("application.modelo._taxation_comparison", "domain.period"),
            ImportEdge("application.modelo._verification_actions", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._verification_actions", "domain.calculations.registry"),
            ImportEdge("application.modelo._verification_cross_period", "domain.calculations.registry"),
            ImportEdge("application.modelo._work_addressing", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._work_create_policy", "application.user_profile"),
            ImportEdge("application.modelo._work_create_policy", "application.workflow"),
            ImportEdge("application.modelo._work_create_policy", "domain.calculations.registry.applicability"),
            ImportEdge("application.modelo._work_create_policy", "domain.contribuyente"),
            ImportEdge("application.modelo._work_lifecycle", "application.modelo._profile_readiness_gate"),
            ImportEdge("application.modelo._work_plazo", "domain.deadlines"),
            ImportEdge("application.modelo._workflow_gate", "core.resources"),
            ImportEdge("application.overview", "application.state_projection"),
            ImportEdge("application.overview._calendar", "core.resources"),
            ImportEdge("application.overview._calendar", "domain.calculations.registry"),
            ImportEdge("application.overview._calendar_warnings", "core.resources"),
            ImportEdge("application.overview._explain", "core.resources"),
            ImportEdge("application.preflight", "application.auth"),
            ImportEdge("application.preflight", "domain.calculations.registry"),
            ImportEdge("application.preflight", "domain.portals"),
            ImportEdge("application.provisioning", "application.ledger"),
            ImportEdge("application.repair_integrity", "adapters.persistence.storage"),
            ImportEdge("application.review._adapters", "adapters.persistence.profile.filing_drafts"),
            ImportEdge("application.review._adapters", "adapters.persistence.profile.invoices"),
            ImportEdge("application.review._operator", "core"),
            ImportEdge("application.review._operator", "core.config"),
            ImportEdge("application.state_projection", "application"),
            ImportEdge("application.state_projection", "application.calculations"),
            ImportEdge("application.state_projection", "application.diagnostics"),
            ImportEdge("application.state_projection", "application.modelo"),
            ImportEdge("application.state_projection", "application.user_profile"),
            ImportEdge("application.state_projection", "application.workflow"),
            ImportEdge("application.state_projection", "core.config"),
            ImportEdge("application.state_projection", "core.resources"),
            ImportEdge("application.state_projection", "domain.calculations.registry"),
            ImportEdge("application.state_projection", "domain.deadlines"),
            ImportEdge("application.storage.calc_sheets._parity_harness", "adapters.outbound.google"),
            ImportEdge("application.storage_write_policy", "application.modelo"),
            ImportEdge("application.transactions._diagnostics", "core.i18n"),
            ImportEdge("application.user_profile._bundle", "adapters.persistence.profile.modelos_filing"),
            ImportEdge("application.user_profile._bundle", "adapters.persistence.profile.modelos_work_units"),
            ImportEdge("application.user_profile._bundle", "adapters.persistence.storage"),
            ImportEdge("application.user_profile._bundle", "application.modelo"),
            ImportEdge("application.user_profile._bundle", "application.user_profile._custody_carry"),
            ImportEdge("application.user_profile._bundle", "application.user_profile._orchestration"),
            ImportEdge("application.user_profile._bundle", "domain.modelos"),
            ImportEdge("application.user_profile._bundle", "domain.transactions"),
            ImportEdge("application.user_profile._bundle", "domain.user_profile"),
            ImportEdge("application.user_profile._capabilities", "adapters.persistence.storage"),
            ImportEdge("application.user_profile._capabilities", "application.workflow"),
            ImportEdge("application.user_profile._censo_sync", "adapters.outbound.aeat.sede"),
            ImportEdge("application.user_profile._censo_sync", "adapters.persistence.profile.usage_ratios"),
            ImportEdge("application.user_profile._censo_sync", "application.auth"),
            # censo vivienda-ratio read defers the profile repository/projection
            # imports alongside the sibling deferrals above (product-rename
            # state-boundary follow-up).
            ImportEdge("application.user_profile._censo_sync", "application.user_profile._projections"),
            ImportEdge("application.user_profile._censo_sync", "application.user_profile._repository"),
            ImportEdge("application.user_profile._censo_sync", "core.access_gate"),
            ImportEdge("application.user_profile._censo_sync", "core.config"),
            ImportEdge("application.user_profile._censo_sync", "domain.buckets"),
            ImportEdge("application.user_profile._censo_sync", "domain.usage_ratios"),
            ImportEdge("application.user_profile._censo_sync", "domain.user_profile"),
            ImportEdge("application.user_profile._custody", "adapters.persistence.storage.bucket"),
            ImportEdge("application.user_profile._custody", "core"),
            ImportEdge("application.user_profile._language_resolver", "adapters.persistence.storage.bucket"),
            ImportEdge("application.user_profile._language_resolver", "adapters.persistence.storage.master_key"),
            ImportEdge("application.user_profile._language_resolver", "application.user_profile._orchestration"),
            ImportEdge("application.user_profile._language_resolver", "application.workflow"),
            ImportEdge("application.user_profile._language_resolver", "core"),
            ImportEdge("application.user_profile._language_resolver", "core.config"),
            ImportEdge("application.user_profile._orchestration", "adapters.persistence.storage.errors"),
            ImportEdge("application.user_profile._orchestration", "adapters.persistence.storage.master_key"),
            ImportEdge("application.user_profile._orchestration", "adapters.persistence.storage.sql.engine"),
            ImportEdge("application.user_profile._orchestration", "application.user_profile._repository"),
            ImportEdge("application.user_profile._orchestration", "application.workflow"),
            ImportEdge("application.user_profile._orchestration", "core"),
            ImportEdge("application.user_profile._orchestration", "core.config"),
            ImportEdge("application.user_profile._orchestration", "domain.buckets"),
            ImportEdge("application.user_profile._profile_repository", "adapters.persistence.storage.sql.engine"),
            ImportEdge("application.user_profile._profile_repository", "application.user_profile._orchestration"),
            ImportEdge("application.user_profile._profile_repository", "application.workflow"),
            ImportEdge("application.user_profile._profile_repository", "core"),
            ImportEdge("application.user_profile._profile_repository", "domain.user_profile"),
            ImportEdge("application.user_profile._projections", "application.wizard"),
            ImportEdge("application.user_profile._repository", "adapters.persistence.storage"),
            ImportEdge("application.user_profile._repository", "adapters.persistence.storage.bucket"),
            ImportEdge("application.user_profile._repository", "core.config"),
            ImportEdge("application.verification._verify", "core.resources"),
            ImportEdge("application.wizard._commands", "application.user_profile"),
            ImportEdge("application.wizard._commands", "application.wizard._persistence"),
            ImportEdge("application.wizard._commands", "application.wizard._runner"),
            ImportEdge("application.wizard._commands", "application.workflow"),
            ImportEdge("application.wizard._commands", "core.click_context"),
            ImportEdge("application.wizard._commands", "core.config"),
            ImportEdge("application.wizard._commands", "core.errors"),
            ImportEdge("application.wizard._commands", "core.json_contract"),
            ImportEdge("application.wizard._commands", "core.output_rendering"),
            ImportEdge("application.wizard._commands", "domain.contribuyente"),
            ImportEdge("application.wizard._commands", "domain.deadlines"),
            ImportEdge("application.wizard._commands", "domain.user_profile"),
            ImportEdge("application.wizard._compiler", "application.wizard"),
            ImportEdge("application.wizard._compiler", "domain.contribuyente"),
            ImportEdge("application.wizard._persistence", "application.wizard._widgets"),
            ImportEdge("application.wizard._persistence", "domain.user_profile"),
            ImportEdge("application.workflow._adapters", "adapters.outbound.aeat.auth"),
            ImportEdge("application.workflow._adapters", "adapters.outbound.aeat.sede"),
            ImportEdge("application.workflow._models", "application.user_profile"),
            ImportEdge("application.workflow._models", "core.errors"),
            ImportEdge("application.workflow._models", "domain.transactions"),
            ImportEdge("application.workflow._models", "domain.user_profile"),
            ImportEdge("application.workflow._persistence", "core"),
            ImportEdge("application.workflow._persistence", "core.i18n"),
            ImportEdge("application.workflow._profile_bucket_scan", "core.config"),
            ImportEdge("application.workflow._resume", "application.modelo"),
            ImportEdge("entrypoints.mcp", "entrypoints.mcp._server"),
            ImportEdge("entrypoints.mcp._faithfulness", "core.i18n"),
            ImportEdge("entrypoints.mcp._input_schema", "entrypoints.cli"),
            ImportEdge("entrypoints.mcp._persona_scope", "core.i18n"),
            ImportEdge("entrypoints.mcp._resources", "application.corpus_search"),
            ImportEdge("entrypoints.mcp._server", "core.i18n"),
            ImportEdge("entrypoints.mcp._toolsets", "entrypoints.cli"),
            ImportEdge("entrypoints.mcp._tools", "entrypoints.cli"),
            ImportEdge("locales._fstring_registry", "application.wizard"),
            ImportEdge("locales._fstring_registry", "core.i18n"),
            ImportEdge("locales._fstring_registry", "domain.contribuyente"),
            ImportEdge("locales._fstring_registry", "domain.deadlines"),
            ImportEdge("locales.manager", "locales._ast_scanner"),
            ImportEdge("locales.manager", "locales._fstring_registry"),
        }
    ),
}


# Per-class SITE-count ceilings taken at the same baseline. A site is one
# physical import statement; several sites can share one edge (the same
# consumer->target pair reached from two functions). The ratchet asserts the
# live per-class site count is <= its ceiling: an increase fails until the
# ceiling is raised in the same commit; a decrease is free.
_SITE_CEILINGS: dict[UnsanctionedClass, int] = {
    UnsanctionedClass.ERROR_REGISTRY_BOOTSTRAP: 4,
    UnsanctionedClass.NAMED_CYCLE_BREAK: 1,
    UnsanctionedClass.PORTS_INVERSION_PENDING: 36,
    UnsanctionedClass.DOMAIN_CYCLE_BREAK: 51,
    UnsanctionedClass.ADAPTER_INTERNAL_DEFERRAL: 176,  # +6 filing-amendment repository deferral sites
    UnsanctionedClass.CORE_INTERNAL_DEFERRAL: 38,  # net +1 atomic_write bootstrap-cycle deferrals (_bucket_pointer_io, corpus_manifest; env_io net-zero, corpus_manifest's save_corpus_manifest site retired its own core.locks edge)
    UnsanctionedClass.APPLICATION_DEFERRAL: 520,  # +3 censo vivienda-ratio profile deferrals (was 517: +14 readiness relation-prefill)
}

# Ceiling on the total number of allowlisted edges. Editing the allowlist to add
# an edge must raise this in the same commit; removing edges may lower it freely.
# Re-baselined to 478 (register-item-D7 ledger reconciliation): 27 new
# function-local first-party import edges accumulated since the prior 451-edge
# baseline (the modelos_work_units/participation_index catalogue-repository
# consolidation, the corpus_search/mcp/user_profile deferrals introduced by
# intervening commits) were swept into their classified buckets in one pass.
_ALLOWLIST_EDGE_CEILING: int = 468  # retired certificate backend modules removed four deferral edges.


def _cadrumo_relative(dotted: str) -> str:
    """Strip the leading ``cadrumo.`` (or bare ``cadrumo``) from a dotted module name."""
    if dotted == "cadrumo":
        return ""
    if dotted.startswith("cadrumo."):
        return dotted[len("cadrumo.") :]
    return dotted


def _resolve_target(node: ast.Import | ast.ImportFrom, package_base: tuple[str, ...]) -> str | None:
    """Return the cadrumo-relative imported module for a first-party import, else None.

    ``package_base`` is the importing module's containing package, cadrumo-relative
    and split into components (for a package ``__init__`` this is the package
    itself; for a regular module it is its parent package). A ``from . import x``
    resolves against ``package_base``; each extra leading dot climbs one more
    package level, mirroring Python's own relative-import resolution. A
    ``from .. import name`` whose ``name`` is a submodule resolves to the
    package, not the submodule -- the import statement alone cannot distinguish a
    submodule from a re-exported symbol, so the coarser package edge is recorded.
    """
    if isinstance(node, ast.ImportFrom):
        if node.level:
            package = list(package_base)
            climb = node.level - 1
            if climb:
                package = package[:-climb] if climb <= len(package) else []
            target = package + ([node.module] if node.module else [])
            return ".".join(target)
        module = node.module or ""
        if module == "cadrumo" or module.startswith("cadrumo."):
            return _cadrumo_relative(module)
        return None
    for alias in node.names:
        if alias.name == "cadrumo" or alias.name.startswith("cadrumo."):
            return _cadrumo_relative(alias.name)
    return None


def _classify_unsanctioned(edge: ImportEdge) -> UnsanctionedClass:
    """Assign an unsanctioned edge to its class from consumer/target layers."""
    consumer, target = edge.consumer, edge.target
    consumer_layer = consumer.split(".", 1)[0]
    target_layer = target.split(".", 1)[0] if target else ""
    if consumer.startswith("core.errors"):
        return UnsanctionedClass.ERROR_REGISTRY_BOOTSTRAP
    if consumer == "application.overview._coverage":
        return UnsanctionedClass.NAMED_CYCLE_BREAK
    if consumer_layer == "domain" and target_layer == "adapters":
        return UnsanctionedClass.PORTS_INVERSION_PENDING
    if consumer_layer == "adapters":
        return UnsanctionedClass.ADAPTER_INTERNAL_DEFERRAL
    if consumer_layer == "domain":
        return UnsanctionedClass.DOMAIN_CYCLE_BREAK
    if consumer_layer == "core":
        return UnsanctionedClass.CORE_INTERNAL_DEFERRAL
    return UnsanctionedClass.APPLICATION_DEFERRAL


class _ScopeWalker(ast.NodeVisitor):
    """Collect function-local imports outside ``TYPE_CHECKING`` / import guards.

    Tracks nesting as it descends: whether we are inside any function body
    (``_func_depth``), inside a ``TYPE_CHECKING`` block, inside a ``try`` body
    whose handler catches an import error, and inside a package ``__getattr__``
    body. A first-party import is recorded only when it is function-local and
    neither type-only nor an optional-dependency guard; the PEP 562 and CLI
    cold-start exclusions are applied by the caller from the module path plus the
    ``__getattr__`` flag carried on each recorded site.
    """

    def __init__(self, edge_consumer: str, package_base: tuple[str, ...], is_package_init: bool) -> None:
        self._edge_consumer = edge_consumer
        self._package_base = package_base
        self._is_package_init = is_package_init
        self._func_depth = 0
        self._type_checking_depth = 0
        self._import_guard_depth = 0
        self._getattr_depth = 0
        self.sites: list[tuple[int, ImportEdge, bool]] = []

    def _visit_function_like(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_getattr = self._is_package_init and node.name == "__getattr__"
        self._func_depth += 1
        if is_getattr:
            self._getattr_depth += 1
        self.generic_visit(node)
        if is_getattr:
            self._getattr_depth -= 1
        self._func_depth -= 1

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_like(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_like(node)

    @override
    def visit_If(self, node: ast.If) -> None:
        is_type_checking = node.test is not None and "TYPE_CHECKING" in ast.unparse(node.test)
        if is_type_checking:
            self._type_checking_depth += 1
        for child in node.body:
            self.visit(child)
        if is_type_checking:
            self._type_checking_depth -= 1
        for child in node.orelse:
            self.visit(child)

    @override
    def visit_Try(self, node: ast.Try) -> None:
        guards_import = any(
            handler.type is not None
            and ("ImportError" in ast.unparse(handler.type) or "ModuleNotFoundError" in ast.unparse(handler.type))
            for handler in node.handlers
        )
        if guards_import:
            self._import_guard_depth += 1
        for child in node.body:
            self.visit(child)
        if guards_import:
            self._import_guard_depth -= 1
        for group in (node.handlers, node.orelse, node.finalbody):
            for child in group:
                self.visit(child)

    @override
    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    def _record(self, node: ast.Import | ast.ImportFrom) -> None:
        if self._func_depth == 0 or self._type_checking_depth or self._import_guard_depth:
            return
        target = _resolve_target(node, self._package_base)
        if target is None:
            return
        edge = ImportEdge(self._edge_consumer, target)
        self.sites.append((node.lineno, edge, self._getattr_depth > 0))


@cache
def _discover_unsanctioned_sites() -> tuple[_LocalImport, ...]:
    """Walk production with the real AST and return unsanctioned import sites.

    Sanctioned classes are removed structurally: ``TYPE_CHECKING`` blocks and
    import guards inside the walker; PEP 562 ``__getattr__`` bodies, the
    ``entrypoints/cli/`` cold-start subtree, and the ``core/resources/`` loader
    subtree here. What remains is the unsanctioned first-party surface the
    allowlist must cover.
    """
    discovered: list[_LocalImport] = []
    for path in production_python_files():
        tree = ast_for_path(path)
        if tree is None:
            continue
        parts = path.relative_to(SRC_CADRUMO).parts
        rel_parts = path.relative_to(SRC_CADRUMO).with_suffix("").parts
        is_init = path.name == "__init__.py"
        # Containing package = rel_parts[:-1] whether the file is a package
        # __init__ (drops "__init__") or a regular module (drops the module name).
        package_base = rel_parts[:-1]
        edge_consumer = ".".join(package_base) if is_init else ".".join(rel_parts)
        relative = repo_relative(path)
        is_cli = len(parts) >= 2 and parts[0] == "entrypoints" and parts[1] == "cli"
        is_core_resources = len(parts) >= 2 and parts[0] == "core" and parts[1] == "resources"
        walker = _ScopeWalker(edge_consumer, package_base, is_init)
        walker.visit(tree)
        for lineno, edge, in_getattr in walker.sites:
            if in_getattr or is_cli or is_core_resources:
                continue
            discovered.append(_LocalImport(relative, lineno, edge))
    return tuple(discovered)


def _allowlisted_edges() -> frozenset[ImportEdge]:
    return frozenset().union(*_ALLOWLIST.values())


def _format_five_classes() -> str:
    return "\n".join(f"    {index}. {member.value}" for index, member in enumerate(FIVE_SANCTIONED_CLASSES, start=1))


def test_declared_allowlist_is_internally_consistent() -> None:
    """Every unsanctioned class has metadata, an allowlist bucket, and a ceiling."""
    for member in UnsanctionedClass:
        assert member in _CLASS_METADATA, f"{member.name} missing reason/disposition metadata"
        assert member in _ALLOWLIST, f"{member.name} missing an allowlist bucket"
        assert member in _SITE_CEILINGS, f"{member.name} missing a site-count ceiling"
    declared_edges = sum(len(edges) for edges in _ALLOWLIST.values())
    assert declared_edges == _ALLOWLIST_EDGE_CEILING, (
        f"_ALLOWLIST holds {declared_edges} edges but _ALLOWLIST_EDGE_CEILING is "
        f"{_ALLOWLIST_EDGE_CEILING}; update the ceiling in the same commit as the edit."
    )
    seen: dict[ImportEdge, UnsanctionedClass] = {}
    for member, edges in _ALLOWLIST.items():
        for edge in edges:
            assert edge not in seen, f"{edge} filed under both {seen[edge].name} and {member.name}"
            seen[edge] = member


def test_every_allowlisted_edge_is_classified_where_filed() -> None:
    """Each allowlisted edge sits under the class its consumer/target imply.

    Guards against an edge being parked in the wrong bucket to borrow a gentler
    disposition; the classifier is the single source of an edge's class.
    """
    misfiled: list[str] = []
    for member, edges in _ALLOWLIST.items():
        for edge in edges:
            expected = _classify_unsanctioned(edge)
            if expected is not member:
                misfiled.append(
                    f"  {edge.consumer} -> {edge.target}: filed {member.name}, classifier says {expected.name}"
                )
    assert not misfiled, "Allowlisted edges filed under the wrong unsanctioned class:\n" + "\n".join(misfiled)


def test_no_unclassified_unsanctioned_import_site() -> None:
    """No production function-local first-party import escapes the sanctioned set or the allowlist.

    This is the policy gate: a function-local ``cadrumo.*`` import that is not one
    of the five sanctioned classes and whose runtime-graph edge is not declared
    in ``_ALLOWLIST`` fails here, naming the site path and the five sanctioned
    classes so the author can either restructure the import away or add a
    reviewed allowlist entry with its class, reason, and disposition.
    """
    allowlisted = _allowlisted_edges()
    violations = [site for site in _discover_unsanctioned_sites() if site.edge not in allowlisted]
    assert not violations, (
        "Unsanctioned function-local first-party import(s) with no allowlist entry.\n"
        "Each is neither one of the five sanctioned classes nor a declared allowlist edge:\n"
        + "\n".join(
            f"  {site.relative_path}:{site.lineno}  {site.edge.consumer} -> {site.edge.target}" for site in violations
        )
        + "\n\nThe five sanctioned classes (no allowlist entry needed) are:\n"
        + _format_five_classes()
        + "\n\nIf the import is genuinely none of these, restructure it away, or record its edge "
        "in _ALLOWLIST under its unsanctioned class and raise the ceiling in the same commit."
    )


def test_unsanctioned_site_count_ratchet() -> None:
    """Per-class site counts and the edge total stay at or below their baselines.

    Catches a new unsanctioned site added on an ALREADY-allowlisted edge (which
    slips past the edge-subset gate): the per-class site count rises above its
    ceiling and fails until the ceiling is raised in the same commit. Removing
    sites lowers the live count freely below the ceiling.
    """
    live_counts: dict[UnsanctionedClass, int] = dict.fromkeys(UnsanctionedClass, 0)
    for site in _discover_unsanctioned_sites():
        live_counts[_classify_unsanctioned(site.edge)] += 1

    breaches = [
        f"  {member.name}: {live_counts[member]} live sites > ceiling {_SITE_CEILINGS[member]}"
        for member in UnsanctionedClass
        if live_counts[member] > _SITE_CEILINGS[member]
    ]
    assert not breaches, (
        "Unsanctioned function-local import site count rose above its ceiling. Raise the "
        "ceiling in _SITE_CEILINGS in the same commit as the new import, or restructure it away:\n"
        + "\n".join(breaches)
    )

    live_edges = {site.edge for site in _discover_unsanctioned_sites()}
    assert len(live_edges) <= _ALLOWLIST_EDGE_CEILING, (
        f"{len(live_edges)} live unsanctioned edges exceed the declared ceiling "
        f"{_ALLOWLIST_EDGE_CEILING}; add the new edge(s) to _ALLOWLIST and raise the ceiling."
    )


def test_discovery_is_non_empty_and_reproduces_baseline() -> None:
    """The AST walk finds sites (the walk is wired) and stays within the baseline.

    A zero result would mean the discovery logic silently broke and every gate
    above would pass vacuously; this pins the walk to a real, non-empty surface.
    """
    sites = _discover_unsanctioned_sites()
    assert sites, "Discovery returned no function-local first-party imports -- the AST walk is broken."
    live_edges = {site.edge for site in sites}
    undeclared = live_edges - _allowlisted_edges()
    assert not undeclared, (
        "Discovered edges absent from the baseline allowlist (should be empty at the baseline):\n"
        + "\n".join(f"  {edge.consumer} -> {edge.target}" for edge in sorted(undeclared))
    )

"""Gate: a NEW deferred cross-layer import must be declared, not absorbed.

The layered contract in ``.importlinter`` analyses the import-time graph. The
graph the process actually executes is denser, because a function-local import
is invisible to a module-level layer check: moving an import inside a function
is the standard way to break an import cycle in this tree, and it is also the
standard way to make a layer violation stop being reported. The two are
indistinguishable at the declaration site, so a deferral that *hides* a cycle
and a deferral that *breaks* one look identical to every other gate.

This gate enumerates every production function-local import that runs against
the declared layer direction (``entrypoints > adapters > application > domain >
core``) and requires each to be declared here, so the set cannot grow silently:
an author who defers a new cross-layer import to quiet a contract must add a row
and say which kind of deferral it is.

**What this gate does NOT claim.** An inherited
:attr:`DeferredEdgeStatus.UNADJUDICATED` row remains present, running, and judged
by nobody; green does not promote it into architectural approval. Green means
the live graph and the checked declaration agree in both directions, every
reviewed demand load still carries its site-specific reason, and no stale row
can linger after its edge disappears.

Declarations are keyed by ``(path, enclosing function)`` rather than line
number, so ordinary edits above an entry do not invalidate it.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from pathlib import Path
from typing import Final

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Declared layer order, highest first. Mirrors the ``layers`` contract in
#: ``.importlinter``; an import reaching a HIGHER layer runs against it.
_LAYERS: tuple[str, ...] = ("entrypoints", "adapters", "application", "domain", "core")
_RANK = {name: index for index, name in enumerate(_LAYERS)}

_SRC_ROOT = Path(__file__).resolve().parents[1]


class DeferredEdgeStatus(StrEnum):
    """Why a deferred cross-layer import is present."""

    #: ``.importlinter`` names this shape in prose -- the ``core/resources/_repos``
    #: deferred loaders, which read registry-backed domain data lazily so importing
    #: ``core`` does not pull the registry parse. Documented, not merely tolerated.
    DOCUMENTED_LOADER = "documented-resource-loader"
    #: Inherited from the graph when this gate was written. NOT reviewed. Nobody has
    #: decided whether the deferral breaks a real cycle or hides one.
    UNADJUDICATED = "unadjudicated"
    #: Deferred on purpose, by someone who said why, to keep an expensive graph off
    #: a path that does not need it. Distinct from UNADJUDICATED: that status means
    #: nobody has looked, and recording a considered deferral under it would make
    #: the inventory claim less than it knows.
    DELIBERATE_DEMAND_LOAD = "deliberate-demand-load"


#: ``core/resources/_repos`` lazy loaders -- the one shape ``.importlinter`` documents.
_DOCUMENTED_LOADERS: frozenset[tuple[str, str]] = frozenset(
    {
        ("core/resources/_repos/apoderamientos.py", "_load"),
        ("core/resources/_repos/category_profiles.py", "_load"),
        ("core/resources/_repos/holiday_calendars.py", "_load"),
        ("core/resources/_repos/iva_catalogues.py", "_load"),
        ("core/resources/_repos/iva_rate_tables.py", "_load"),
        ("core/resources/_repos/manuals.py", "_load"),
        ("core/resources/_repos/manuals.py", "_part_is_a_known_volume"),
        ("core/resources/_repos/manuals.py", "catalogue"),
        ("core/resources/_repos/manuals.py", "find_rules"),
        ("core/resources/_repos/manuals.py", "iter_sections"),
        ("core/resources/_repos/recargo_bands.py", "_load"),
    },
)

#: Deliberate deferrals, each with the reason it exists.
#: Reviewed, unlike the inventory below.
_DELIBERATE_DEMAND_LOADS: dict[tuple[str, str], str] = {
    ("application/ledger/actions_common.py", "_default_calculation_repository"): (
        "the concrete calculation catalogue is needed only where a caller injected no "
        "repository; importing it at module scope put an application-to-adapter edge on "
        "every consumer of the ledger action layer"
    ),
    ("application/filing/persistence_wiring.py", "modelo_record_repository_for_application"): (
        "the application port remains importable without constructing or importing its encrypted "
        "persistence default until a caller actually requests that default"
    ),
    ("application/ledger/actions_common.py", "_commit_with_guarded_events"): (
        "the persistence-specific revision conflict is loaded only on the guarded commit path "
        "that catches it; ordinary ledger reads do not need the storage error hierarchy"
    ),
    ("application/ledger/actions_common.py", "resolve_attachment_store"): (
        "the concrete attachment-store resolver is needed only when the caller did not inject the application port"
    ),
    ("application/ledger/actions_common.py", "resolve_bucket_event_repository"): (
        "the secure-object runtime repository is needed only to build the permitted persistence "
        "default when no event repository was injected"
    ),
    ("application/modelo/calculation.py", "_calculation_owner_observation"): (
        "the concrete calculation catalogue is needed only when the caller omitted the repository "
        "port; injected calculation paths do not load persistence"
    ),
    ("application/modelo/taxation_comparison.py", "compare_taxation_for_work_address"): (
        "the work-unit catalogue is loaded only by the public-address convenience entry point; "
        "the comparison engine itself consumes an already-loaded catalogue"
    ),
    ("application/registry/filed_state.py", "_load_filed_observation"): (
        "the filed-observation store is required only while verifying an on-disk observation; "
        "registry command discovery does not load the outbound adapter graph"
    ),
    ("application/registry/filed_state.py", "verify_filed_state"): (
        "the filed-declaration converter is required only by verification; keeping it local avoids "
        "loading the outbound AEAT and authentication graph during registry command discovery"
    ),
}

#: Everything else the inventory found. Present and running; judged by nobody.
_UNADJUDICATED: frozenset[tuple[str, str]] = frozenset(
    {
        ("application/auth/operator_probes.py", "_classify_bundle_health"),
        ("application/auth/operator_probes.py", "live_auth_identity_kind"),
        ("application/auth/operator_probes.py", "probe_certificate_bundle"),
        ("application/auth/operator_probes.py", "_probe_clave_movil_identity"),
        ("application/auth/sessions.py", "_active_profile_auth_facts"),
        ("application/auth/sessions.py", "_build_provider"),
        ("application/auth/sessions.py", "require_verified_aeat_session"),
        ("application/diagnostic_models.py", "ensure_models_rebuilt"),
        ("application/diagnostics.py", "_is_missing_active_bucket_session"),
        ("application/diagnostics.py", "_ok_site_health_status"),
        ("application/diagnostics.py", "_probe_browser_connectivity"),
        ("application/diagnostics.py", "_probe_secure_objects_integrity"),
        ("application/diagnostics.py", "quarantine_unreadable_secure_objects"),
        ("application/filing/draft_review.py", "_load_transaction_catalogue"),
        ("application/filing/persistence_wiring.py", "secure_objects_for_application_filing_bucket"),
        ("application/invoices/catalogue_creation.py", "emit_catalogue_invoice_event"),
        ("application/ledger/actions_common.py", "purchase_invoice_evidence_records"),
        ("application/ledger/actions_import.py", "_resolve_financial_provider"),
        ("application/ledger/actions_import.py", "import_ledger_source"),
        ("application/ledger/batch_ingest.py", "_reads_without_a_model"),
        ("application/ledger/evidence_input.py", "_reject_unreadable_bytes"),
        ("application/ledger/evidence_input.py", "document_shape"),
        ("application/ledger/llm_classification.py", "_record_injected_classifier_run"),
        ("application/live/censo.py", "pull_censal_datos"),
        ("application/live/errors.py", "_classify_clave_movil_timeout"),
        ("application/live/errors.py", "_classify_sede_error"),
        ("application/live/errors.py", "classify_live_iva_acquisition_failure"),
        ("application/live/iva_remote_state.py", "_active_profile_storage_span"),
        ("application/live/justificante.py", "parse_capture_to_justificante"),
        ("application/live/justificante.py", "register_capture_as_filing_evidence"),
        ("application/live/justificante.py", "register_capture_justificante_metadata"),
        ("application/live/justificante.py", "stamp_capture_evidence_if_filed"),
        ("application/modelo/iva_wallet_seed.py", "_emit_iva_wallet_corrected_event"),
        ("application/modelo/iva_wallet_seed.py", "_emit_iva_wallet_override_event"),
        ("application/modelo/iva_wallet_seed.py", "_sealed_modelo_303_blocker_for_period"),
        ("application/modelo/m036_lifecycle.py", "_m036_declaration_repository"),
        ("application/modelo/m145_communication_records.py", "_m145_communication_record_repository"),
        ("application/modelo/taxation_comparison.py", "compare_taxation_for_work_unit"),
        ("application/repair_integrity.py", "_active_bucket_repair_repository"),
        ("application/repair_integrity.py", "_repo"),
        ("application/repair_integrity.py", "active_bucket_repair_session"),
        ("application/review/_adapters.py", "load_drafts"),
        ("application/review/_adapters.py", "load_invoices"),
        ("application/review/_adapters.py", "load_transactions"),
        ("application/storage/calc_sheets/parity_harness.py", "verify_modelo_parity"),
    },
)

PINNED_DEFERRED_CROSS_LAYER_IMPORTS: Final[dict[tuple[str, str], DeferredEdgeStatus]] = {
    **{pair: DeferredEdgeStatus.DOCUMENTED_LOADER for pair in _DOCUMENTED_LOADERS},
    **{pair: DeferredEdgeStatus.UNADJUDICATED for pair in _UNADJUDICATED},
    **{pair: DeferredEdgeStatus.DELIBERATE_DEMAND_LOAD for pair in _DELIBERATE_DEMAND_LOADS},
}
"""Live deferred cross-layer sites, checked for undeclared and stale drift below."""


def _enclosing_function(parents: dict[ast.AST, ast.AST], node: ast.AST) -> str | None:
    """Return the nearest enclosing function name, or ``None`` at module level."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            return current.name
        current = parents.get(current)
    return None


def _resolve_target_layer(relative: str, node: ast.ImportFrom) -> str | None:
    """Return the first-party layer ``node`` imports from, or ``None``."""
    if node.module is None:
        return None
    if node.level:
        base = relative.split("/")[:-1]
        ascend = node.level - 1
        if ascend:
            base = base[: len(base) - ascend]
        target = base + node.module.split(".")
    else:
        if not node.module.startswith("cadrumo"):
            return None
        target = node.module.split(".")[1:]
    return target[0] if target and target[0] in _RANK else None


def _production_modules() -> list[Path]:
    """Every production module under the layered packages."""
    found: list[Path] = []
    for path in scan_directory(_SRC_ROOT, pattern="*.py", recursive=True):
        relative = path.relative_to(_SRC_ROOT).as_posix()
        if "/tests/" in relative or relative.startswith("tests/") or "conftest" in relative:
            continue
        if relative.split("/")[0] in _RANK:
            found.append(path)
    return found


def deferred_cross_layer_edges() -> dict[tuple[str, str], set[str]]:
    """Map ``(path, enclosing function)`` to the higher layers it reaches."""
    edges: dict[tuple[str, str], set[str]] = {}
    for path in _production_modules():
        relative = path.relative_to(_SRC_ROOT).as_posix()
        own = relative.split("/")[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken module fails its own gate
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            function_name = _enclosing_function(parents, node)
            if function_name is None:
                continue
            target_layer = _resolve_target_layer(relative, node)
            if target_layer is None or target_layer == own:
                continue
            if _RANK[target_layer] < _RANK[own]:
                edges.setdefault((relative, function_name), set()).add(target_layer)
    return edges


def test_the_scanner_sees_a_real_corpus() -> None:
    """Anti-vacuity: every assertion below passes trivially over an empty scan."""
    modules = _production_modules()
    assert len(modules) > 500, (
        f"only {len(modules)} production modules found; the scanner is broken and the "
        "declaration assertions below would all pass over nothing"
    )
    assert deferred_cross_layer_edges(), (
        "the scanner found no deferred cross-layer edges at all. Either every one was "
        "genuinely removed -- in which case empty the declarations below -- or the "
        "detector stopped detecting."
    )


def test_no_undeclared_deferred_cross_layer_import() -> None:
    """A NEW function-local import against the layer direction must be declared.

    This is the assertion that bites. Deferring an import inside a function
    silences the module-level layer contract, so without this gate the runtime
    graph can accumulate cross-layer coupling indefinitely while every declared
    contract stays green.
    """
    undeclared = sorted(
        pair for pair in deferred_cross_layer_edges() if pair not in PINNED_DEFERRED_CROSS_LAYER_IMPORTS
    )
    assert not undeclared, (
        "function-local imports running against the declared layer direction, with no "
        "declaration here. Classify a genuine cycle break as UNADJUDICATED; give a reviewed "
        "demand load a site-specific DELIBERATE_DEMAND_LOAD reason; remove an import that only "
        f"quiets a layer contract: {undeclared}"
    )


def test_no_stale_declaration() -> None:
    """A declaration whose edge is gone must fail rather than linger.

    Without this an inventory only ever grows, and a later reader cannot tell a
    live row from one kept alive by nothing.
    """
    live = set(deferred_cross_layer_edges())
    stale = sorted(pair for pair in PINNED_DEFERRED_CROSS_LAYER_IMPORTS if pair not in live)
    assert not stale, f"declared deferred edges that no longer exist -- delete these rows: {stale}"


def test_deliberate_demand_loads_name_their_site_specific_reason() -> None:
    """A reviewed demand load is a reasoned declaration, not an allowlist row."""
    missing = sorted(pair for pair, reason in _DELIBERATE_DEMAND_LOADS.items() if not reason.strip())
    assert not missing, f"deliberate demand loads without a site-specific reason: {missing}"


def test_documented_loaders_stay_where_the_contract_says_they_are() -> None:
    """The one reviewed category must stay confined to the path that earns it.

    ``.importlinter`` documents the ``core/resources/_repos`` loaders specifically.
    A row drifting into that status from elsewhere would launder an unreviewed edge
    as a documented one.
    """
    misplaced = sorted(pair for pair in _DOCUMENTED_LOADERS if not pair[0].startswith("core/resources/_repos/"))
    assert not misplaced, f"rows claiming documented-loader status outside core/resources/_repos: {misplaced}"

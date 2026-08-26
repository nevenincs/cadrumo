"""Structural checks for the Import Linter ignore ledger.

See Also:
    :mod:`~tests._inventory`
        Provides the repository root anchor used to parse ``.importlinter``
        without depending on the current working directory.
    ``.importlinter``
        Layered architecture contract and ignore ledger ratcheted by these
        tests.

The layered import-boundary model and its sanctioned exception registry must
not drift unnoticed; this ratchet is what makes that drift visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from ._inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IMPORTLINTER = REPO_ROOT / ".importlinter"
_SOURCE_ROOT = REPO_ROOT / "src"

_CONTRACT_RE = re.compile(r"^\[importlinter:contract:(?P<contract>[^\]]+)\]$")
_IGNORE_EDGE_RE = re.compile(r"^\s*(?P<source>cadrumo\.[\w.*]+)\s*->\s*(?P<target>cadrumo\.[\w.*]+)\s*$")

_APPLICATION_SOURCE_WILDCARD_BASELINE = (
    3  # reconciled live ceiling for application edges targeting cadrumo.adapters.**; may only decrease
)

# Every PRODUCTION application module sanctioned to pin an application -> adapters
# ignore edge. This is the ledger's own documented intent -- "the exception ledger
# pins each existing application source module individually; full inversion remains
# deferred, but new source modules fail loudly" -- expressed as the property rather
# than proxied by a tally.
#
# A count could not express it. One already-sanctioned module pinning a second
# target grew the number without widening the boundary, so the honest response to a
# red run was indistinguishable from the dishonest one, and the number was raised
# rather than reconciled the day after it was introduced. Naming the modules makes
# the diff legible: a new entry is a new production module reaching adapters, and
# it has to be argued for rather than absorbed.
#
# The set may only SHRINK. Inversion removes entries; nothing legitimately adds one
# without a decision recorded alongside it.
_RECONCILED_APPLICATION_TO_ADAPTERS_SOURCES = frozenset(
    {
        "cadrumo.application.aggregation._impatriado_income_ledger",
        "cadrumo.application.aggregation._iva_ledger",
        "cadrumo.application.aggregation._modelo_bindings",
        "cadrumo.application.aggregation._observation_window",
        "cadrumo.application.aggregation._oss_ioss",
        "cadrumo.application.aggregation._percepciones_observations_repository",
        "cadrumo.application.aggregation._renta_gasto_ledger",
        "cadrumo.application.aggregation._renta_income_ledger",
        "cadrumo.application.aggregation._renta_ledger",
        "cadrumo.application.aggregation._retencion_observations_repository",
        "cadrumo.application.aggregation._withholding_source",
        "cadrumo.application.auth.certificate_secret_backend",
        "cadrumo.application.auth.diagnostics",
        "cadrumo.application.auth.operator_probes",
        "cadrumo.application.auth.operator_scope",
        "cadrumo.application.auth.sessions",
        "cadrumo.application.bienes_inversion",
        "cadrumo.application.bucket_maintenance._deletion_paths",
        "cadrumo.application.bucket_maintenance._service",
        "cadrumo.application.calculations._cross_period_clean_state",
        "cadrumo.application.calculations._iva_compensation_annual_partition",
        "cadrumo.application.calculations._iva_compensation_history",
        "cadrumo.application.calculations._multi_year",
        "cadrumo.application.calculations._observations_repository",
        "cadrumo.application.calculations._prorrata_regularizacion",
        "cadrumo.application.calculations._relation_prefill",
        "cadrumo.application.diagnostics",
        "cadrumo.application.diagnostics_run_health",
        "cadrumo.application.evidence._service",
        "cadrumo.application.filing._complementaria",
        "cadrumo.application.filing._history_repository",
        "cadrumo.application.filing._import",
        "cadrumo.application.filing._review",
        "cadrumo.application.filing._runtime_repository",
        "cadrumo.application.inventory._service",
        "cadrumo.application.invoices._bulk_import",
        "cadrumo.application.invoices._creation",
        "cadrumo.application.invoices._lifecycle",
        "cadrumo.application.invoices._linking",
        "cadrumo.application.invoices._queries",
        "cadrumo.application.invoices._reconciliation",
        "cadrumo.application.invoices._source_resolver",
        "cadrumo.application.invoices._wizard",
        "cadrumo.application.ledger.actions_common",
        "cadrumo.application.ledger.actions_import",
        "cadrumo.application.ledger.actions_lifecycle",
        "cadrumo.application.ledger.actions_split_merge",
        "cadrumo.application.ledger.aeat_record_projection",
        "cadrumo.application.ledger.batch_ingest",
        "cadrumo.application.ledger.confirmation_record",
        "cadrumo.application.ledger.counterparty_establishment",
        "cadrumo.application.ledger.evidence",
        "cadrumo.application.ledger.evidence_draft",
        "cadrumo.application.ledger.evidence_input",
        "cadrumo.application.ledger.evidence_textlayer",
        "cadrumo.application.ledger.extraction_draft_store",
        "cadrumo.application.ledger.llm_classification",
        "cadrumo.application.ledger.llm_diagnostics",
        "cadrumo.application.ledger.ratios",
        "cadrumo.application.ledger.review_projection",
        "cadrumo.application.live",
        "cadrumo.application.live.borrador_100",
        "cadrumo.application.live.deudas",
        "cadrumo.application.live.errors",
        "cadrumo.application.live.expedientes",
        "cadrumo.application.live.filed_capture_finalizer",
        "cadrumo.application.live.filed_data",
        "cadrumo.application.live.filed_data_capture",
        "cadrumo.application.live.filed_observation_persistence",
        "cadrumo.application.live.iva_remote_state",
        "cadrumo.application.live.justificante",
        "cadrumo.application.live.notifications",
        "cadrumo.application.live.session",
        "cadrumo.application.live.verify",
        "cadrumo.application.modelo._amendment_actions",
        "cadrumo.application.modelo._art109_activity_income",
        "cadrumo.application.modelo._borrador_binding",
        "cadrumo.application.modelo._calculate_input",
        "cadrumo.application.modelo._calculation_actions",
        "cadrumo.application.modelo._calculation_preparation",
        "cadrumo.application.modelo._export",
        "cadrumo.application.modelo.external_import_actions",
        "cadrumo.application.modelo._filing_actions",
        "cadrumo.application.modelo._history",
        "cadrumo.application.modelo._iva_wallet_gate",
        "cadrumo.application.modelo._iva_wallet_seed",
        "cadrumo.application.modelo._ledger_drift_gate",
        "cadrumo.application.modelo._m036_lifecycle",
        "cadrumo.application.modelo._m145_communication_records",
        "cadrumo.application.modelo._m349_ledger_guard",
        "cadrumo.application.modelo._participation_index_rebuild",
        "cadrumo.application.modelo._reconcile",
        "cadrumo.application.modelo._reconciliation_records",
        "cadrumo.application.modelo._review_package_keypair",
        "cadrumo.application.modelo._review_package_recipient_encryption",
        "cadrumo.application.modelo._review_package_recipient_registry",
        "cadrumo.application.modelo._review_package_signing",
        "cadrumo.application.modelo._revision_persistence",
        "cadrumo.application.modelo._selectors",
        "cadrumo.application.modelo._taxation_comparison",
        "cadrumo.application.modelo._verification_actions",
        "cadrumo.application.modelo._work_lifecycle",
        "cadrumo.application.modelo._workflow_gate",
        "cadrumo.application.operator_output._sandbox_notice",
        "cadrumo.application.prorrata_register",
        "cadrumo.application.registry",
        "cadrumo.application.repair_integrity",
        "cadrumo.application.review._adapters",
        "cadrumo.application.state_projection",
        "cadrumo.application.storage.calc_sheets._parity_harness",
        "cadrumo.application.user_profile.aggregate",
        "cadrumo.application.user_profile.bundle_encryption",
        "cadrumo.application.user_profile.capabilities",
        "cadrumo.application.user_profile.language_resolver",
        "cadrumo.application.user_profile.login_session",
        "cadrumo.application.user_profile.profile_repository",
        "cadrumo.application.user_profile.repository",
        "cadrumo.application.workflow.adapters",
        "cadrumo.application.workflow.events",
        "cadrumo.application.workflow.run_models",
        "cadrumo.application.workflow.state_models",
        "cadrumo.application.workflow.persistence",
        "cadrumo.application.workflow.profile_bucket_scan",
        "cadrumo.application.workflow.profile_health",
    },
)
# The sanctioned pairs below ARE the ceiling. A tally sat here too, and it
# could only ever have caught a sanctioned pair pinned twice -- duplicate noise,
# not a widened boundary -- while training every reader to raise the number on a
# red run. The pair set decides what may exist; the staleness assertion decides
# that each one still earns its place.
_SANCTIONED_DOMAIN_TO_ADAPTERS_TEST_PAIRS = frozenset(
    {
        ("cadrumo.domain.tests.**", "cadrumo.adapters.**"),
        ("cadrumo.domain.**.tests.**", "cadrumo.adapters.**"),
    },
)


@dataclass(frozen=True)
class IgnoreEdge:
    contract: str
    line_no: int
    source: str
    target: str


def _ignore_edges() -> tuple[IgnoreEdge, ...]:
    contract = ""
    edges: list[IgnoreEdge] = []
    for line_no, line in enumerate(_IMPORTLINTER.read_text(encoding="utf-8").splitlines(), start=1):
        contract_match = _CONTRACT_RE.match(line)
        if contract_match is not None:
            contract = contract_match.group("contract")
            continue
        edge_match = _IGNORE_EDGE_RE.match(line)
        if edge_match is None:
            continue
        edges.append(
            IgnoreEdge(
                contract=contract,
                line_no=line_no,
                source=edge_match.group("source"),
                target=edge_match.group("target"),
            ),
        )
    return tuple(edges)


@pytest.fixture(scope="module")
def ignore_edges() -> tuple[IgnoreEdge, ...]:
    """Return parsed Import Linter ignore edges once for this test module."""
    return _ignore_edges()


@pytest.fixture(scope="module")
def layered_edges(ignore_edges: tuple[IgnoreEdge, ...]) -> tuple[IgnoreEdge, ...]:
    """Return the parsed layered-contract ignore edges."""
    return tuple(edge for edge in ignore_edges if edge.contract == "layered")


def test_ignore_ledger_inventory_is_non_vacuous(
    ignore_edges: tuple[IgnoreEdge, ...],
    layered_edges: tuple[IgnoreEdge, ...],
) -> None:
    assert ignore_edges, "parsed ignore ledger is empty; parser/config prefix drift may have made ratchets vacuous"
    assert layered_edges, "parsed layered ledger is empty; contract-name/config drift may have made ratchets vacuous"


def _resolve_module_path(module: str) -> Path:
    wildcard_index = module.find(".*")
    if wildcard_index != -1:
        module = module[:wildcard_index]
    return _SOURCE_ROOT / Path(*module.split("."))


def _module_exists(module: str) -> bool:
    path = _resolve_module_path(module)
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def test_ignore_import_modules_resolve_on_disk(ignore_edges: tuple[IgnoreEdge, ...]) -> None:
    missing: list[str] = []
    for edge in ignore_edges:
        for module in (edge.source, edge.target):
            if not _module_exists(module):
                missing.append(f"line {edge.line_no}: {module}")

    assert missing == []


def _is_test_tier(source: str) -> bool:
    """Report whether an ignore-edge source is a test module or a conftest.

    The test tier crosses layers by roundtrip-discipline design and is carved out
    wholesale; only production sources carry ports-inversion debt. Counting the two
    together let a new fixture carve-out read as new production coupling.
    """
    return ".tests." in f"{source}." or source.endswith(".conftest")


def test_application_to_adapters_sources_are_reconciled(layered_edges: tuple[IgnoreEdge, ...]) -> None:
    """Only reconciled production application modules may pin an adapters edge.

    Replaces an edge-count ratchet. The count was raised the day after it landed,
    which is the failure the quality-gate rule names: a tally encodes a moment,
    trains everyone to update the constant, and then detects nothing. It also could
    not say WHICH coupling was new, so nobody could act on a red run.
    """
    application_adapter_edges = tuple(
        edge
        for edge in layered_edges
        if edge.source.startswith("cadrumo.application.") and edge.target.startswith("cadrumo.adapters")
    )
    blanket_edges = tuple(
        edge
        for edge in application_adapter_edges
        if edge.source == "cadrumo.application.**" and edge.target == "cadrumo.adapters.**"
    )
    source_wildcard_edges = tuple(edge for edge in application_adapter_edges if edge.target == "cadrumo.adapters.**")

    assert not blanket_edges
    assert len(source_wildcard_edges) <= _APPLICATION_SOURCE_WILDCARD_BASELINE

    production_sources = {edge.source for edge in application_adapter_edges if not _is_test_tier(edge.source)}

    unreconciled = sorted(production_sources - _RECONCILED_APPLICATION_TO_ADAPTERS_SOURCES)
    assert unreconciled == [], (
        "production application module(s) newly pin an application -> adapters ignore edge without being "
        "reconciled. Invert the coupling behind a port, or enroll the module in "
        "_RECONCILED_APPLICATION_TO_ADAPTERS_SOURCES with the decision recorded alongside it: "
        f"{unreconciled}"
    )


def test_reconciled_application_sources_all_answer_a_live_pin(layered_edges: tuple[IgnoreEdge, ...]) -> None:
    """A reconciled entry whose coupling is gone must be removed, not left standing.

    This is what keeps the enrolment from rotting into a rubber stamp. An entry that
    outlives its edge is a pre-approval sitting in the ledger, ready to launder the
    next pin from the same module without anyone re-deciding. Removing one is a
    one-line edit and always means the boundary got cleaner.
    """
    production_sources = {
        edge.source
        for edge in layered_edges
        if edge.source.startswith("cadrumo.application.")
        and edge.target.startswith("cadrumo.adapters")
        and not _is_test_tier(edge.source)
    }

    stale = sorted(_RECONCILED_APPLICATION_TO_ADAPTERS_SOURCES - production_sources)
    assert stale == [], (
        "reconciled application -> adapters source(s) no longer pin any edge; the coupling was removed, so "
        f"drop them from _RECONCILED_APPLICATION_TO_ADAPTERS_SOURCES and let the ratchet record the win: {stale}"
    )


def test_domain_to_adapters_pin_count_does_not_grow(layered_edges: tuple[IgnoreEdge, ...]) -> None:
    domain_adapter_edges = tuple(
        edge
        for edge in layered_edges
        if edge.source.startswith("cadrumo.domain.") and edge.target.startswith("cadrumo.adapters")
    )
    observed_pairs = {(edge.source, edge.target) for edge in domain_adapter_edges}
    unexpected_pairs = observed_pairs - _SANCTIONED_DOMAIN_TO_ADAPTERS_TEST_PAIRS

    assert not unexpected_pairs, f"unexpected layered domain -> adapters ignore pairs: {sorted(unexpected_pairs)}"

    stale_pairs = sorted(_SANCTIONED_DOMAIN_TO_ADAPTERS_TEST_PAIRS - observed_pairs)
    assert stale_pairs == [], (
        "sanctioned domain -> adapters pair(s) no longer pin any edge; the carve-out was removed, so "
        f"drop them from _SANCTIONED_DOMAIN_TO_ADAPTERS_TEST_PAIRS and let the ratchet record the win: {stale_pairs}"
    )
    assert domain_adapter_edges, "the domain -> adapters edge scan found nothing; the ledger parse collapsed"


def test_zero_production_domain_to_adapters_edges(ignore_edges: tuple[IgnoreEdge, ...]) -> None:
    """No production domain module may pin a domain -> adapters ignore edge.

    Every production domain repository now sits behind a Protocol port with its
    concrete class under ``adapters.persistence.profile``. Only test-file roundtrip / anti-tautology edges —
    which legitimately construct the concrete adapter to exercise the encrypted
    boundary — may remain. A production domain -> adapters edge reappearing here
    is an architecture regression and must fail loudly, not ratchet.
    """
    production_domain_adapter_edges = tuple(
        edge
        for edge in ignore_edges
        if edge.source.startswith("cadrumo.domain.")
        and edge.target.startswith("cadrumo.adapters")
        and ".tests." not in edge.source
        and not edge.source.endswith(".conftest")
    )

    assert production_domain_adapter_edges == (), (
        "production domain -> adapters ignore edges must be zero after the ports-inversion "
        f"seam closeout; found: {[f'line {e.line_no}: {e.source} -> {e.target}' for e in production_domain_adapter_edges]}"
    )

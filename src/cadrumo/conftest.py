"""Package-level pytest fixtures for every test under ``src/cadrumo/``.

Hosts the ``source_tree_ast`` session-scoped fixture that ratchet
inventories consume to amortise the AST parse cost across the suite.
The fixture lives at the package root because pytest's conftest discovery
walks up from each test file. Tests are distributed across domain-local
``tests/`` subtrees throughout ``src/cadrumo/``; a conftest inside
``src/cadrumo/tests/`` is invisible to sibling owner subtrees, while this
package-root conftest is their narrowest common visible owner.

Marker-contract and live-import gating are owned by the repo-root
``conftest.py`` so every collected test subtree reaches the same policy.
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

# Child conftests import command-line interface (CLI) and internationalization
# (`i18n`) modules while pytest is collecting tests. Those imports initialise
# logging, which resolves Settings before function-scoped fixtures can establish
# their own temporary storage roots. Set this Cadrumo root first so tests do not
# read a user's legacy product-state directory during collection. Overwritten
# (not `setdefault`) because this conftest is the authoritative source for its
# own process's root, regardless of what the repo-root conftest's permissive
# `setdefault` already set.
#
# Pure stdlib, deliberately NOT `apply_collection_storage_root(overwrite=True)`
# from `.tests`: importing ANY name from `cadrumo.tests` -- or from `.core`,
# as this module's own imports below now do only AFTER this line -- executes
# that package's `__init__.py` body first (Python always initialises a parent
# package before a submodule access completes), and both packages' import
# surfaces have, in practice, drifted to reach production modules carrying a
# module-level `get_logger(__name__)` call. Any such call fires
# `configure_logging()`, which binds its `RotatingFileHandler` exactly once
# per process -- if that binding happens before this line runs, it binds to
# the operator's real log rather than this process's isolated root, and
# nothing later in the process can re-bind it. Spelling the derivation out
# here (mirroring `_collection_storage_root.collection_storage_root`'s own
# `<gettempdir()>/cadrumo-pytest-<pid>`) removes the dependency on either
# package staying import-light for this one safety-critical line.
_COLLECTION_STORAGE_ROOT = Path(tempfile.gettempdir()) / f"cadrumo-pytest-{os.getpid()}"
os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(_COLLECTION_STORAGE_ROOT)
"""Process-private local-storage root set before child conftests import Cadrumo."""

# Safe to import cadrumo.* below this point: the storage-root env var any of
# these modules' own import surfaces might trigger a premature
# configure_logging() against is already set by the pure-stdlib lines above.
from .core.external_constants import UTF_8_ENCODING  # noqa: E402
from .tests import package_python_files, prime_ast_cache, register_collection_storage_root_cleanup  # noqa: E402
from .tests.env_scope import release_settings_storage_directories  # noqa: E402

# The other half of what apply_collection_storage_root(overwrite=True) used
# to do in one call: register the atexit cleanup and stale-sibling sweep for
# the root set above. Splitting the env-var write from this registration is
# exactly the point -- the write must happen before any cadrumo import, the
# registration is only safe (and only needed) after.
register_collection_storage_root_cleanup(_COLLECTION_STORAGE_ROOT)

_SRC_CADRUMO_ROOT: Path = Path(__file__).resolve().parent
"""Root of the ``src/cadrumo/`` source tree (the directory hosting this conftest)."""


@pytest.fixture(scope="session")
def source_tree_ast() -> Mapping[Path, ast.AST]:
    """Return a session-cached mapping of every ``src/cadrumo/`` ``.py`` file to its parsed AST.

    Walks ``src/cadrumo/`` once per pytest session via ``rglob("*.py")``, skips
    ``__pycache__`` directories, ``.venv`` parents, and the ``_data/``
    payload tree, reads each file as UTF-8 with ``errors='replace'`` (so
    a stray encoding cookie cannot raise), and parses it with the
    standard library ``ast`` module. Files that fail to parse with
    ``SyntaxError`` are silently skipped — the fixture is a best-effort
    cache, not a syntax gate; ratchets that need to surface unparseable
    files should fall back to their own per-test scan.

    Consumers retain their own filter predicates (e.g. ``test_*.py``
    only, or exclude certain subdirs). The fixture is the AST cache;
    the policy is per-test.

    Also primes the shared process-level AST cache
    (``tests._inventory.prime_ast_cache``) so a ratchet that calls
    ``ast_for_path(path)`` WITHOUT threading this fixture through its own
    helpers (the historical bypass pattern -- a ratchet imports only
    ``ast_for_path`` and re-parses independently) still reuses this parse
    instead of re-reading and re-parsing the file from disk.
    """
    cache: dict[Path, ast.AST] = {}
    for path in package_python_files():
        try:
            source = path.read_text(encoding=UTF_8_ENCODING, errors="replace")
        except OSError:
            continue
        try:
            cache[path] = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
    prime_ast_cache(cache)
    return cache


@pytest.fixture(scope="session", autouse=True)
def _skip_profile_kdf_grid_measurement() -> Iterator[None]:
    """Stop every profile registration re-benchmarking this host's KDF grid.

    ``calibrate_profile_kdf`` MEASURES the parameter grid to pick the strongest
    point inside the operator latency band: one supervised child per warmup and
    per sample. Profiled here, that is 16.1s of the 19.1s a registration costs,
    and it is repeated for every registration, on the same machine, for the same
    answer. Registration doors are reached from 102 direct call sites across 31
    test modules, besides the shared ``register_cli_profile``.

    The seam and its reasoning are the shipped function's own: measuring is
    "the right price for an operator's one-off enrolment and the wrong one for a
    host that enrols constantly". Declining adopts the FIXED fallback point,
    which that function also returns whenever the grid cannot be measured before
    its deadline, and which is STRONGER than the measured band's floor -- so
    every custody envelope a test opens is wrapped no more weakly than before.

    Session-scoped and outermost, which is what makes it survive: a nested
    ``override_settings`` setting other fields keeps this value (checked), so
    the many tests that override a storage root do not silently re-enable
    measurement.

    It cannot reach the calibration gate. ``calibrate_profile_kdf`` consults
    ``settings or load_settings()``, and
    ``custody/tests/test_kdf_supervision.py`` passes an explicitly constructed
    ``Settings``; ``override_settings`` does not reach a directly-constructed
    ``Settings`` (checked: ``load_settings()`` reads False here while
    ``Settings()`` still reads True). So the behaviour this skips is still
    proven, by the module that owns it.
    """
    from .core.config import override_settings

    with override_settings(cadrumo_profile_kdf_measure_calibration=False):
        yield


@pytest.fixture(scope="session", autouse=True)
def compose_runtime_ports() -> Iterator[None]:
    """Compose real persistence and authentication adapters for tests."""
    from .adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from .adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from .adapters.outbound.aeat.auth.session_store import build_session_store
    from .adapters.persistence.profile.extracted_document_cache import ExtractedDocumentCacheRepository
    from .adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from .adapters.persistence.profile.justificante import JustificanteRepository
    from .adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from .adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from .adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from .adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from .adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from .adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from .adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from .adapters.persistence.profile.usage_ratios import load_usage_ratios_with_censo_guard
    from .adapters.persistence.workflow import build_workflow_persistence_port
    from .application.auth.protocols import bind_session_store
    from .application.auth.providers import bind_auth_provider_selector
    from .application.ledger.extracted_document_cache import bind_extracted_document_cache_repository_factory
    from .application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from .application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from .application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from .application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from .application.ledger.usage_ratio_repository import bind_usage_ratio_censo_guard_loader
    from .application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from .application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from .application.modelo.justificante_repository import bind_justificante_repository_factory
    from .application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from .application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from .application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from .application.workflow.persistence import bind_workflow_persistence_port
    from .tests.profile_persistence import composed_profile_persistence_ports

    with (
        composed_profile_persistence_ports(),
        bind_workflow_persistence_port(build_workflow_persistence_port()),
        bind_extraction_draft_repository_factory(ExtractionDraftRepository),
        bind_extracted_document_cache_repository_factory(ExtractedDocumentCacheRepository),
        bind_transaction_participation_index_repository_factory(TransactionParticipationIndexRepository),
        bind_ledger_classification_rule_repository_factory(LedgerClassificationRuleRepository),
        bind_transaction_catalogue_repository_factory(TransactionCatalogueRepository),
        bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard),
        bind_calculation_revision_catalogue_repository_factory(CalculationRevisionCatalogueRepository),
        bind_modelo_record_catalogue_repository_factory(ModeloRecordCatalogueRepository),
        bind_justificante_repository_factory(JustificanteRepository),
        bind_work_unit_catalogue_repository_factory(WorkUnitCatalogueRepository),
        bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()),
        bind_modelo_reconciliation_persistence_factory(build_modelo_reconciliation_persistence),
        bind_auth_provider_selector(select_outbound_auth_provider),
        bind_session_store(build_session_store()),
    ):
        yield


@pytest.fixture(autouse=True)
def _evict_test_bound_bucket_session() -> Iterator[None]:
    """Evict a bucket session a test bound itself, so none crosses into the next test.

    pytest is an in-process, multi-invocation CLI host and was the last one
    without this boundary. ``config login`` binds through the deliberately
    unscoped ``bind_active_bucket_session`` -- correct for the shipped
    one-process-per-command shape, where the binding must outlive the function
    and process exit reclaims it. A host that runs many commands in one process
    carries that binding forward instead. An embedding transport evicts per
    request for this reason and the docs-sequence runner adopted the same
    primitive, so this is the third host adopting an existing boundary rather
    than a new policy.

    Left bound, an UNSEALED session outlives the test that opened it and stays
    bound while later tests provision their own buckets, so a subsequent profile
    read decrypts against the earlier bucket's DEK. The operator-visible result
    is ``registered_bucket present`` with ``profile_record unreadable`` -- the
    record exists, the key is wrong. Measured before this landed, one bucket
    stayed bound across sixteen consecutive tests, then a second took over for
    the rest of the module.

    Eviction is SELECTIVE, and that is the whole design. Several suites share
    one bucket runtime across a module on purpose (``filing/conftest.py`` pays
    the costly provisioning once per module; the ledger action support fixtures
    do the same), so closing whatever happens to be bound at teardown strands
    that shared session and fails every later test in the module -- measured, at
    roughly fifty tests. Comparing session IDENTITY across the test separates
    the two cases: a module-scoped session is the same object before and after
    and is left alone, while a session the test bound itself is a different
    object and is the one that leaks. The re-bind is required because
    ``close_active_bucket_session`` clears the binding outright rather than
    restoring the previous value, so a test that logs in underneath a
    module-scoped runtime would otherwise leave that runtime unbound.

    The boundary is per-TEST, not per-invocation: a persisted session
    legitimately survives across CLI invocations within one scenario, so
    evicting per invocation would break real login-then-act flows.

    Cost is nil for tests that never touch storage -- the ``sys.modules`` check
    returns before importing anything, so the AST ratchets pay nothing.
    """
    if "cadrumo.adapters.persistence.storage" not in sys.modules:
        yield
        return
    from .adapters.persistence.storage import current_active_bucket_session

    inherited = current_active_bucket_session()
    yield
    bound = current_active_bucket_session()
    if bound is None or bound is inherited:
        return
    from .adapters.persistence.storage import (
        bind_active_bucket_session,
        close_active_bucket_session,
    )

    close_active_bucket_session()
    if inherited is not None:
        bind_active_bucket_session(inherited)


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Clear the registry loader's in-process caches per pytest session (the #44 fix).

    The loader's cross-process ``/tmp`` ``cadrumo_registry_*.pkl`` disk pickle is
    keyed by file mtime and was historically shared across pytest-xdist worker
    processes, so a parallel ``-n`` run could serve a stale/transient compiled
    registry from one worker to another (the #44 isolation gap). The loader
    closes that race at the ROOT: the disk pickle is now read/written under
    pytest only for the package-bundled, read-only registry tree
    (``registry_disk_cache_enabled(is_bundled=...)``), which is never mutated
    mid-run; a mutable/synthetic root (a test's ``tmp_path`` registry) never
    gets a disk pickle under pytest at all, so no per-worker purge is needed to
    protect it.

    This fixture therefore clears only the per-process ``lru_cache`` and the
    1-second-TTL fingerprint cache at session start and end -- it does NOT
    purge the ``/tmp`` disk pickle. An earlier version of this fixture DID
    purge it unconditionally at session start; measured directly (two separate
    ``pytest`` invocations against the same bundled-tree content, each its own
    "session" exactly as an xdist worker's own session boundary is), that
    purge deleted the very pickle the bundled-root cache had just written,
    forcing every subsequent session/worker to independently recompile the
    bundled tree from scratch (8.6s-8.7s per invocation, zero cross-session
    reuse) -- silently defeating the cross-worker sharing the disk-cache fix
    exists to deliver. The disk-cache read path is already self-validating (a
    SHA-256 of the schema version plus every file's path/size/mtime), so a
    stale or incompatible pickle simply misses on its own; no defensive purge
    is needed for correctness, only for tidiness the temp directory does not
    require.
    """
    from cadrumo.domain.calculations.registry.loader_fingerprints import clear_fingerprint_cache

    from .domain.calculations.registry.loader import _load_registry_tree_cached

    def _reset() -> None:
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

    _reset()
    yield
    _reset()


@pytest.fixture(scope="session", autouse=True)
def _release_settings_storage_directories() -> Iterator[None]:
    """Drop the temporary storage roots ``env_scope`` mints, at session end.

    ``settings_without_env_file`` mints a temporary root whenever a caller
    supplies none and the environment carries none -- which is every call made
    inside ``isolated_aeat_env``, since that clears the storage-root variable.
    It has to hold the directory open, because the ``Settings`` it returns
    names that path.

    Nothing used to drop them and no sweep covered the prefix, so they
    accumulated: a runtime write census measured 457 in the operator's temp
    directory, the oldest three weeks old, one per call across every session
    ever run. Each is empty, so the cost is directory entries rather than
    bytes, and a byte-oriented look never saw it.

    Binding the lifetime here is what fixes it: the directories must outlive
    the call, and now they do not outlive the session. A worker killed rather
    than torn down still leaks, which no in-process finalizer can prevent --
    that residual is the reason the collection-time root carries a staleness
    sweep as well as an ``atexit`` hook.
    """
    yield
    release_settings_storage_directories()

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
from typing import TYPE_CHECKING

import pytest

from .core.storage_environment import TOOL_STORAGE_LOCATIONS, prepare_temporary_directory, tool_storage_environment

if "CADRUMO_TEST_RUN_SCRATCH" not in os.environ:
    _tool_environment = tool_storage_environment()
    for _native_variable, (_refinement_variable, _default_location) in TOOL_STORAGE_LOCATIONS.items():
        os.environ[_refinement_variable] = _tool_environment[_native_variable]
    os.environ.update(_tool_environment)
    sys.pycache_prefix = _tool_environment["PYTHONPYCACHEPREFIX"]

if TYPE_CHECKING:
    from .domain.calculations.registry.authority import PinnedAuthorityOperation

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
if "CADRUMO_TEST_RUN_SCRATCH" not in os.environ:
    # Standalone/installed pytest consumers may not load the repository conftest.
    # In that case establish the canonical temp root before child conftests import
    # application modules. Repository runs already have a narrower run scratch.
    _temporary_root = prepare_temporary_directory()
    os.environ.update({"TEMP": str(_temporary_root), "TMP": str(_temporary_root), "TMPDIR": str(_temporary_root)})
    tempfile.tempdir = str(_temporary_root)

_COLLECTION_STORAGE_ROOT = Path(tempfile.gettempdir()) / f"cadrumo-pytest-{os.getpid()}"
os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(_COLLECTION_STORAGE_ROOT)
"""Process-private local-storage root set before child conftests import Cadrumo."""


# The other half of what apply_collection_storage_root(overwrite=True) used
# to do in one call: register the atexit cleanup and stale-sibling sweep for
# the root set above. Splitting the env-var write from this registration is
# exactly the point -- the write must happen before any cadrumo import, the
# registration is only safe (and only needed) after.
def _register_collection_storage_root_cleanup() -> None:
    """Register cleanup only after the collection root is established."""
    from .tests.collection_storage_root import register_collection_storage_root_cleanup

    register_collection_storage_root_cleanup(_COLLECTION_STORAGE_ROOT)


_register_collection_storage_root_cleanup()

_SRC_CADRUMO_ROOT: Path = Path(__file__).resolve().parent
"""Root of the ``src/cadrumo/`` source tree (the directory hosting this conftest)."""


@pytest.fixture(scope="session")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease the published authority generation for the session, as runtime reads it.

    The lease is entered in a private context. Entered in the session's own
    context, it would leave the governed-fact scope set for every later test
    in the worker, so a test that forgot its lease passed or failed by the
    order it ran in. Tests that request this fixture get the scope from
    :func:`_scope_tests_that_request_the_operation`; a wider-scoped fixture
    that computes under it enters ``validating_governed_facts`` itself.
    """
    from .domain.calculations.registry.tests.authority_lease_support import private_authority_lease

    with private_authority_lease() as pinned:
        yield pinned


@pytest.fixture(autouse=True)
def _scope_tests_that_request_the_operation(request: pytest.FixtureRequest) -> Iterator[None]:
    """Scope governed facts to the session lease for exactly the tests that ask for it."""
    if "operation" not in request.fixturenames:
        yield
        return
    # A test's own parametrized ``operation`` argument also appears in
    # ``fixturenames``; ``scoped_when_requested`` tells the two apart.
    from .domain.calculations.registry.tests.authority_lease_support import scoped_when_requested

    with scoped_when_requested(request, "operation"):
        yield


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one published authority generation, scoping governed facts for the whole test.

    Deliberately not autouse: a module opts in with
    ``pytestmark = pytest.mark.usefixtures("authority_operation")``, so a command
    that forgets to take its own lease is still caught everywhere else.
    """
    from .domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.fixture(scope="session")
def source_tree_ast() -> Mapping[Path, ast.AST]:
    """Return a session mapping of every ``src/cadrumo/`` ``.py`` file to its parsed AST.

    Covers the package files outside ``__pycache__`` and the ``_data/`` payload
    tree, each read as UTF-8 with ``errors='replace'`` (so a stray encoding
    cookie cannot raise). Files that fail to parse with ``SyntaxError`` are not
    members -- the fixture is a cache, not a syntax gate; ratchets that need to
    surface unparseable files should fall back to their own per-test scan.

    Each module is parsed on first access, through the same process-level
    cache :func:`~cadrumo.tests.inventory.ast_for_path` reads, so a ratchet
    that never threads this fixture through its helpers still shares the parse.
    Parsing lazily is what lets a package-scoped gate run without first paying
    for every other module in the tree.

    Consumers retain their own filter predicates (e.g. ``test_*.py``
    only, or exclude certain subdirs). The fixture is the AST cache;
    the policy is per-test.
    """
    # Imported here, not at module scope: this module's imports must stay below the
    # storage-root env assignment above, and a function-local import keeps that
    # ordering constraint off the module surface entirely.
    from .tests.inventory import LazySourceTreeAst, package_python_files

    return LazySourceTreeAst(package_python_files())


@pytest.fixture(scope="module", autouse=True)
def _release_the_source_scan_caches_with_their_module() -> Iterator[None]:
    """Free the shared source-parse caches once the module that filled them ends.

    One parse per file, shared across a gate's own tests, is what keeps a
    tree-wide structural ratchet fast. Held for the whole process it also never
    shrank. Sampled per worker over this suite at eight workers: every worker
    settled at about 1.0 GB after collection and then climbed monotonically to
    between 2.1 and 3.5 GB, 23.1 GB in total, and the eleven steepest rises were
    each one tree-walking gate module -- up to 1.33 GB apiece, none of it ever
    returned. A host that has to hold all of it at once is the one that kills a
    worker mid-run, which reads as an unattributable crash in an unrelated test.

    The module boundary is the natural lifetime: file-grouped distribution runs
    every test of a gate consecutively, so the cache is hot exactly while its
    owner needs it and the next module starts from the files it reads itself.
    """
    yield
    from .tests.inventory import release_parsed_sources

    release_parsed_sources()


@pytest.fixture(scope="package", autouse=True)
def _skip_profile_kdf_grid_measurement() -> Iterator[None]:
    """Stop every profile registration re-benchmarking this host's KDF grid.

    ``calibrate_profile_kdf`` MEASURES the parameter grid to pick the strongest
    point inside the operator latency band: one supervised child per probe and
    per sample. Profiled here, that is 16.1s of the 19.1s a registration costs,
    and it is repeated for every registration, on the same machine, for the same
    answer. Registration doors are reached from 102 direct call sites across 31
    test modules, besides the shared ``register_cli_profile``.

    The seam and its reasoning are the shipped function's own: measuring is
    "the right price for an operator's one-off enrolment and the wrong one for a
    host that enrols constantly". Declining adopts the FIXED fallback point,
    which that function also returns whenever no point is confirmed before its
    deadline, and which is the floor a measured point never falls below -- so
    every custody envelope a test opens is wrapped at a strength production
    also accepts.

    Outermost for every test in this package, which is what makes it survive: a
    nested ``override_settings`` setting other fields keeps this value
    (checked), so the many tests that override a storage root do not silently
    re-enable measurement.

    Package-scoped, not session-scoped. An override is a frozen snapshot of
    every field, the storage root included, and a session-long one outlived
    this package: an xdist worker that went on to ``src/cadrumo_harness`` kept
    it, so the harness tests, which isolate themselves through the environment,
    silently ran against this package's collection root. Leaving the package
    now ends it.

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
    from .adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
    from .adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from .adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from .adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from .adapters.persistence.profile.justificante import JustificanteRepository
    from .adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from .adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from .adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from .adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from .adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from .adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from .adapters.persistence.profile.usage_ratios import (
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
        save_usage_ratios,
    )
    from .adapters.persistence.storage.profile_persistence_composition import (
        composed_profile_persistence_ports,
    )
    from .application.auth.protocols import bind_session_store
    from .application.auth.providers import bind_auth_provider_selector
    from .application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from .application.exchange_rate_provider import bind_exchange_rate_provider_factory
    from .application.ledger.confirmation_record import bind_confirmation_record_repository_factory
    from .application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from .application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from .application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from .application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from .application.ledger.usage_ratio_repository import (
        bind_usage_ratio_censo_guard_loader,
        bind_usage_ratio_profile_persistence,
    )
    from .application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from .application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from .application.modelo.justificante_repository import bind_justificante_repository_factory
    from .application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from .application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from .application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from .core.redaction.tax_identity_admission import bind_tax_identity_admission
    from .domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission
    from .entrypoints.adapter_composition import calculation_revision_catalogue_repository

    with (
        bind_tax_identity_admission(RegistryTaxIdentityAdmission()),
        composed_profile_persistence_ports(),
        bind_bucket_event_history_repository_factory(build_bucket_event_history_repository),
        bind_confirmation_record_repository_factory(ConfirmationRecordRepository),
        bind_extraction_draft_repository_factory(ExtractionDraftRepository),
        bind_transaction_participation_index_repository_factory(TransactionParticipationIndexRepository),
        bind_ledger_classification_rule_repository_factory(LedgerClassificationRuleRepository),
        bind_transaction_catalogue_repository_factory(TransactionCatalogueRepository),
        bind_usage_ratio_profile_persistence(loader=load_usage_ratios, saver=save_usage_ratios),
        bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard),
        bind_calculation_revision_catalogue_repository_factory(calculation_revision_catalogue_repository),
        bind_modelo_record_catalogue_repository_factory(ModeloRecordCatalogueRepository),
        bind_justificante_repository_factory(JustificanteRepository),
        bind_work_unit_catalogue_repository_factory(WorkUnitCatalogueRepository),
        bind_reconciliation_evidence_parser(InboundReconciliationEvidenceParser()),
        bind_modelo_reconciliation_persistence_factory(build_modelo_reconciliation_persistence),
        bind_auth_provider_selector(select_outbound_auth_provider),
        bind_session_store(build_session_store()),
        # Lane tests convert currency against recorded ECB answers; only an
        # aeat_live test binds the live provider.
        bind_exchange_rate_provider_factory(recorded_ecb_rate_provider),
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
    object and is the one that leaks. Restoring is required because
    ``close_active_bucket_session`` clears the binding outright rather than
    restoring the previous value, so a test that logs in underneath a
    module-scoped runtime would otherwise leave that runtime unbound.

    Restoring is per LAYER. A module-scoped runtime is usually visible only
    through a scoped override, and a plain re-bind of what the test saw
    published it process-wide, where it outlived its module and reached every
    later module in the worker as an "inherited" session nothing evicted.

    The boundary is per-TEST, not per-invocation: a persisted session
    legitimately survives across CLI invocations within one scenario, so
    evicting per invocation would break real login-then-act flows.

    Cost is nil for tests that never touch storage: the helper sits behind inert
    packages and reads the binding only once the active-session module is
    already loaded, so the AST ratchets import no storage code.
    """
    from .adapters.persistence.storage.master_key.tests.bucket_session_isolation import (
        evict_bucket_sessions_bound_since,
        observe_bucket_session_binding,
    )

    inherited = observe_bucket_session_binding()
    yield
    evict_bucket_sessions_bound_since(inherited)


@pytest.fixture(scope="module", autouse=True)
def _refuse_a_bucket_session_leaked_past_its_module() -> Iterator[None]:
    """Fail the module whose wider-scoped fixture left a bucket session bound.

    The per-test boundary above cannot see such a session: a module-scoped
    fixture binds it before any test's own observation, so every test reads it
    as inherited and leaves it alone. Unreported, it stayed bound for the rest
    of the xdist worker and surfaced only in a later, unrelated module that
    asserts no session is active. Checking at the module boundary names the
    fixture's own module instead, and the eviction keeps the next module clean.
    """
    from .adapters.persistence.storage.master_key.tests.bucket_session_isolation import (
        evict_bucket_sessions_bound_since,
        observe_bucket_session_binding,
    )

    before = observe_bucket_session_binding()
    yield
    leaked = evict_bucket_sessions_bound_since(before)
    if leaked:
        pytest.fail(
            f"{len(leaked)} bucket session(s) bound during this module outlived it; the module- or "
            "class-scoped fixture that opened them must close them in its teardown",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def _evict_test_bound_profile_record_session() -> Iterator[None]:
    """Close a record authority a test caused to be bound, so none crosses into the next test.

    A record session is process-wide and pinned to the authority generation it
    was opened under. Left bound, it answers the next test that reuses the same
    profile id under a different generation, which then refuses as a crossed
    generation boundary. A session derived from a live custody session is
    re-derived on the next read, so closing one a test introduced loses
    nothing; one the test inherited is left alone, as for bucket sessions.
    """
    if "cadrumo.application.user_profile.profile_record_repository" not in sys.modules:
        yield
        return
    from .application.user_profile.profile_record_repository import (
        active_profile_record_session,
        close_active_profile_record_session,
    )

    inherited = active_profile_record_session()
    yield
    bound = active_profile_record_session()
    if bound is not None and bound is not inherited:
        close_active_profile_record_session()


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
    from .tests.env_scope import release_settings_storage_directories

    release_settings_storage_directories()

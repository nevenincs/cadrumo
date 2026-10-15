"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every item
gathered through this root passes through the same enforcement surface. The
hook body lives in :mod:`cadrumo.tests.marker_hook`; this conftest is a thin
wrapper.

Also hosts the project-branded ``CADRUMO_PYTEST_WORKERS`` worker-count policy
(``pytest_xdist_auto_num_workers``), delegated to
:func:`cadrumo.tests.worker_count_hook.resolve_auto_num_workers`, so every
pytest invocation shape resolves ``-n auto`` through the same policy. See
that module's docstring for the hook-ordering contract this delegation
relies on.

The live-test opt-in is read exclusively through
:attr:`cadrumo.core.config.Settings.live_tests_enabled` (and its Google
companion), which reads only ``os.environ`` — production ``Settings``
carries no dotenv source of its own
(``Settings.settings_customise_sources`` never returns a dotenv source).
``env/.env`` is development/test-only configuration (an operator's local
live-test credentials), so this conftest bridges it into ``os.environ``
itself, before any Cadrumo import can resolve ``Settings``, via
:func:`cadrumo.tests.env_loader.bridge_env_file_into_environ`.
``os.environ.setdefault`` semantics keep a real ambient environment
variable authoritative over the dotfile — the file only fills gaps a
shell or CI environment left unset, and the bridge is a clean no-op when
``env/.env`` is absent. The single ``cadrumo.tests.live_gate`` gate
remains the only live-opt-in reader.

The import-light :mod:`cadrumo.core.storage_environment` module is the
canonical storage-path authority for this bootstrap. The checkout's source
path is seeded before importing it; its pure-stdlib implementation can then
load the development-only env bridge and resolve storage controls before
any runtime, logging, or settings import. This ordering lets ``env/.env``
storage refinements take effect while ensuring temporary directories,
shared caches, and the isolated test root are pinned before runtime imports.
Verified by instrumenting ``configure_logging`` to dump its first real
call stack: importing ``cadrumo.tests`` alone no longer triggers it, and
the residual triggers found only fire from session-scoped fixtures that
run after this line has already set the environment variable.

See ``src/cadrumo/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import gc
import os
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import pytest
from _pytest.unraisableexception import gc_collect_iterations_key

# The path authority is intentionally pure stdlib and import-light. Seed the
# checkout source path before importing it so standalone pytest uses the same
# canonical root as application and dev commands.
_REPOSITORY_ROOT = Path(__file__).resolve().parent
_SOURCE_ROOT = _REPOSITORY_ROOT / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from cadrumo.core.storage_environment import (  # noqa: E402
    TOOL_STORAGE_LOCATIONS,
    configured_storage_root,
    resolve_storage_path,
    storage_directory,
    tool_storage_environment,
)

# The tests package initializer is intentionally inert and env_loader is pure
# stdlib. Bridge storage controls before deriving or pinning any category path.
bridge_env_file_into_environ = import_module("cadrumo.tests.env_loader").bridge_env_file_into_environ
bridge_env_file_into_environ(Path(__file__).resolve().parent / "env" / ".env")

_BASE_STORAGE_ROOT = configured_storage_root()


def _pin_storage_override(name: str, default: str) -> Path:
    """Resolve and freeze a relative refinement before test isolation changes the local root."""
    resolved = storage_directory(name, default, root=_BASE_STORAGE_ROOT)
    os.environ[name] = str(resolved)
    return resolved


_pin_storage_override("CADRUMO_DEV_CACHE_ROOT", "development/cache")
_TEST_LOG_ROOT = _pin_storage_override("CADRUMO_TEST_LOG_ROOT", "development")
_pin_storage_override("CADRUMO_DOCS_BUILD_ROOT", "development/build/docs")
_TEMP_BASE = _pin_storage_override("CADRUMO_TEMP_DIR", "tmp")
# Browser binaries are provisioned assets shared by isolated test profiles.
# Pin both the product probe and direct Playwright starts before private roots
# replace the operator's storage root.
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(
    _pin_storage_override("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "components/playwright")
)
_SCRATCH_BASE = os.environ.get("CADRUMO_SCRATCH_BASE", "").strip()
if _SCRATCH_BASE:
    os.environ["CADRUMO_SCRATCH_BASE"] = str(storage_directory("CADRUMO_SCRATCH_BASE", "tmp", root=_BASE_STORAGE_ROOT))

# Relative cache/artifact refinements must remain anchored to the operator's
# root after Cadrumo tests install a process-private local state root.
for _storage_variable, _storage_default in (
    ("CADRUMO_ACTIONLINT_DIR", "development/tools/actionlint"),
    ("CADRUMO_DEV_ARTIFACTS_DIR", "development/artifacts"),
):
    os.environ[_storage_variable] = str(storage_directory(_storage_variable, _storage_default, root=_BASE_STORAGE_ROOT))
for _storage_variable in (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_RECORD_DESIGN_CACHE_DIR",
    "CADRUMO_CORPUS_TEXT_CACHE_DIR",
    "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
    "CADRUMO_RUNTIME_WHEEL_CACHE_DIR",
):
    if os.environ.get(_storage_variable, "").strip():
        os.environ[_storage_variable] = str(
            storage_directory(_storage_variable, "development", root=_BASE_STORAGE_ROOT)
        )
for _report_variable in ("CADRUMO_CI_REPORTS_DIR", "VAULTSPEC_CI_REPORTS"):
    _report_destination = os.environ.get(_report_variable, "").strip()
    if _report_destination:
        os.environ[_report_variable] = str(resolve_storage_path(_report_destination, root=_BASE_STORAGE_ROOT))

# Resolve external tool caches while the operator's configured root is still
# active, then preserve them when product tests install their private local
# storage root below. Cadrumo's refined environment variables are authoritative
# for the corresponding native-tool locations.
_TOOL_STORAGE_ENVIRONMENT = tool_storage_environment()
for _native_variable, (_refinement_variable, _default_location) in TOOL_STORAGE_LOCATIONS.items():
    os.environ[_refinement_variable] = _TOOL_STORAGE_ENVIRONMENT[_native_variable]
os.environ.update(_TOOL_STORAGE_ENVIRONMENT)
sys.pycache_prefix = _TOOL_STORAGE_ENVIRONMENT["PYTHONPYCACHEPREFIX"]

# Python and stdlib temp files start under Cadrumo's configured temporary root.
# The run logger narrows TEMP/TMP/TMPDIR to its own scratch immediately below.
_TEMP_BASE.mkdir(parents=True, exist_ok=True)
os.environ.update({"TEMP": str(_TEMP_BASE), "TMP": str(_TEMP_BASE), "TMPDIR": str(_TEMP_BASE)})
tempfile.tempdir = str(_TEMP_BASE)

# Importing the dev logger is safe before Cadrumo runtime imports. Its run and
# scratch outputs now resolve under the configured storage root.
from dev.test_runs import logging as _run_logging  # noqa: E402

_run_logging.prepare_environment(_TEST_LOG_ROOT)
# A configured product log path stays authoritative. Relative values were
# resolved against the original root before test isolation; only a blank value
# falls through to the per-run product-log default.
if os.environ.get("CADRUMO_LOG_DIR", "").strip():
    os.environ["CADRUMO_LOG_DIR"] = str(
        storage_directory("CADRUMO_LOG_DIR", "development/logs", root=_BASE_STORAGE_ROOT)
    )
else:
    os.environ.pop("CADRUMO_LOG_DIR", None)

# Keep collection-time product data process-private under this run's scratch.
# This value is set before importing any module that may resolve Settings.
_PURE_STDLIB_COLLECTION_ROOT = Path(tempfile.gettempdir()) / f"cadrumo-pytest-{os.getpid()}"
os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(_PURE_STDLIB_COLLECTION_ROOT))

_PURE_STDLIB_AUTHORITY_ROOT = Path(__file__).resolve().parent / ".authority"
"""This checkout's published authority, kept outside the packaged tree.

Mirrors ``dev._paths.DEFAULT_AUTHORITY_ROOT`` exactly. That module seeds the
same variable for every ``python -m dev.*`` entry point, but it is private to
``dev`` and nothing this conftest already imports reaches it, so the value is
spelled out here in pure stdlib for the same reason the collection storage root
above is: a test run must not depend on a transitive import to find its
authority. The two definitions cross-reference each other so a future edit to
one is not made deaf to the other.

A real ambient value stays authoritative, so a run pointed at another authority
tree -- a release verification against staged bytes, say -- is not overridden by
the checkout's own. A BLANK one does not count as ambient: ``Settings`` carries
``env_ignore_empty``, so an empty variable exported by a shell profile reads as
unset there and would resolve the PACKAGED location, while ``dev._paths`` seeds
the checkout's own for every other entry point. Testing the value rather than
its mere presence is what keeps pytest and the dev tooling on one answer.
"""
if not os.environ.get("CADRUMO_AUTHORITY_ROOT", "").strip():
    os.environ["CADRUMO_AUTHORITY_ROOT"] = str(_PURE_STDLIB_AUTHORITY_ROOT)

_collection_storage_root = import_module("cadrumo.tests.collection_storage_root")
collection_storage_root = _collection_storage_root.collection_storage_root
register_collection_storage_root_cleanup = _collection_storage_root.register_collection_storage_root_cleanup

# The collection-policy, reporting, timeout and worker-count hooks load by their
# public package path, after the storage-root and env bridging above; a
# top-of-file import statement would run before those lines.
deselection_hook = import_module("cadrumo.tests.deselection_hook")
fixture_resolution_hook = import_module("cadrumo.tests.fixture_resolution_hook")
lost_test_hook = import_module("cadrumo.tests.lost_test_hook")
marker_hook = import_module("cadrumo.tests.marker_hook")
worker_count_hook = import_module("cadrumo.tests.worker_count_hook")
temporary_env = import_module("cadrumo.tests.env").temporary_env

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact
    from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
    from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import CliWorldProvider
    from cadrumo.tests.cli_fixture_ports import CliInvocation, FreshCliInvocation

# Loaded as a plugin, not inlined here: this module's own `pytest_configure` is
# `trylast`, and the JUnit option has to be set before the junitxml plugin reads
# it. Unset `VAULTSPEC_CI_REPORTS` - every local run - and it does nothing,
# which is what keeps this repository's zero-artifact posture intact.
pytest_plugins = ("dev.ci_reports", "cadrumo.tests.pytest_plugin")


@pytest.fixture(scope="session")
def run_cadrumo_cli() -> Callable[..., Any]:
    """Invoke the public AEAT app through a session-owned Typer runner."""
    from typer.testing import CliRunner

    from cadrumo_runtime.host.frontend.cli.app import aeat_cli_app

    runner = CliRunner()
    app = aeat_cli_app()

    def invoke(args: Sequence[str], **kwargs: Any) -> Any:
        return runner.invoke(app, list(args), **kwargs)

    return invoke


@pytest.fixture(scope="module")
def module_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[int | None, bytes]:
    """Inject one real TUI host execution into product-owned startup assertions."""
    from cadrumo_runtime.host.tests.frontend.tui.module_execution import run_tui_module

    return run_tui_module(tmp_path_factory.mktemp("tui-module"))


@pytest.fixture(scope="session")
def fresh_cli() -> FreshCliInvocation:
    """Inject real console process composition into product-owned assertions."""
    from cadrumo_runtime.host.tests.frontend.cli.fresh_process import run_fresh_cli

    return run_fresh_cli


@pytest.fixture(scope="session")
def cli_world_provider() -> Iterator[CliWorldProvider]:
    """Enroll runtime-owned setup for tax-owned assertion fixtures."""
    from cadrumo.adapters.persistence.profile.tests.published_authority_support import (
        release_published_authority_operation,
    )
    from cadrumo_runtime.host.tests.frontend.cli.world_provider import RuntimeCliWorldProvider

    try:
        yield RuntimeCliWorldProvider()
    finally:
        release_published_authority_operation()


@pytest.fixture(scope="session")
def invoke_cli(run_cadrumo_cli: CliInvocation) -> CliInvocation:
    """Inject joined operator invocation into tax CLI assertions."""
    from cadrumo_runtime.host.tests.frontend.cli.cli_runner import bind_public_cli_runner, invoke_cached_cli

    def invoke(args: Sequence[str], **kwargs: Any) -> Any:
        with bind_public_cli_runner(run_cadrumo_cli):
            return invoke_cached_cli(args, **kwargs)

    return invoke


@pytest.fixture
def cli_runtime_lifetime(run_cadrumo_cli: CliInvocation) -> Iterator[None]:
    """Own implicit runtime joins until requesting fixture teardown."""
    from cadrumo_runtime.host.tests.frontend.cli.cli_runner import bind_public_cli_runner, operator_runtime_scope

    with operator_runtime_scope(), bind_public_cli_runner(run_cadrumo_cli):
        yield


@pytest.fixture(scope="package", autouse=True)
def _skip_profile_kdf_grid_measurement() -> Iterator[None]:
    """Keep package test registration on the production-accepted fixed KDF floor."""
    from cadrumo.core.config import override_settings

    with override_settings(cadrumo_profile_kdf_measure_calibration=False):
        yield


@pytest.fixture(scope="session", autouse=True)
def _release_settings_storage_directories() -> Iterator[None]:
    """Drop temporary storage roots created by isolated settings at session end."""
    yield
    from cadrumo.tests.env_scope import release_settings_storage_directories

    release_settings_storage_directories()


@pytest.fixture(scope="session", autouse=True)
def _keep_the_installation_google_client_out_of_tests(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Keep tests from inheriting the publisher's installed Google OAuth client."""
    from cadrumo.core import config_google
    from cadrumo.core.config import reset_settings_cache

    absent = tmp_path_factory.mktemp("installation-google-client") / "oauth_client.json"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config_google, "installation_client_source", lambda: absent)
        patch.delenv("CADRUMO_GOOGLE_OAUTH_CLIENT_JSON", raising=False)
        reset_settings_cache()
        yield
        reset_settings_cache()


# These product-backed fixtures live at the repository test-host boundary.
# ``cadrumo.tests.pytest_plugin`` remains core-only shared support, so the
# package does not acquire an application dependency through its test helpers.


@pytest.fixture(scope="session")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease the published authority generation for the session, as runtime reads it.

    The lease is entered in a private context. Entered in the session's own
    context, it would leave the governed-fact scope set for every later test
    in the worker, so a test that forgot its lease passed or failed by the
    order it ran in. Tests that request this fixture get the scope from
    ``_scope_tests_that_request_the_operation``; a wider-scoped fixture that
    computes under it enters ``validating_governed_facts`` itself.
    """
    from cadrumo.domain.calculations.registry.tests.authority_lease_support import private_authority_lease

    with private_authority_lease() as pinned:
        yield pinned


@pytest.fixture(autouse=True)
def _scope_tests_that_request_the_operation(request: pytest.FixtureRequest) -> Iterator[None]:
    """Scope governed facts to the session lease for exactly the tests that ask for it."""
    if "operation" not in request.fixturenames:
        yield
        return
    from cadrumo.domain.calculations.registry.tests.authority_lease_support import scoped_when_requested

    with scoped_when_requested(request, "operation"):
        yield


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one published authority generation, scoping governed facts for the whole test.

    Deliberately not autouse: a module opts in with
    ``pytestmark = pytest.mark.usefixtures("authority_operation")``, so a command
    that forgets to take its own lease is still caught everywhere else.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.fixture(scope="session", autouse=True)
def compose_runtime_ports() -> Iterator[None]:
    """Compose real persistence and authentication adapters for tests."""
    from cadrumo.adapters.inbound.reconciliation_parser import InboundReconciliationEvidenceParser
    from cadrumo.adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from cadrumo.adapters.outbound.aeat.auth.session_store import build_session_store
    from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
    from cadrumo.adapters.persistence.profile.buckets import build_bucket_event_history_repository
    from cadrumo.adapters.persistence.profile.confirmation_records import ConfirmationRecordRepository
    from cadrumo.adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
    from cadrumo.adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from cadrumo.adapters.persistence.profile.modelo_reconciliation import build_modelo_reconciliation_persistence
    from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from cadrumo.adapters.persistence.profile.usage_ratios import (
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
        save_usage_ratios,
    )
    from cadrumo.adapters.persistence.storage.profile_persistence_composition import (
        composed_profile_persistence_ports,
    )
    from cadrumo.application.auth.protocols import bind_session_store
    from cadrumo.application.auth.providers import bind_auth_provider_selector
    from cadrumo.application.bucket_event_repository import bind_bucket_event_history_repository_factory
    from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
    from cadrumo.application.ledger.confirmation_record_repository import bind_confirmation_record_repository_factory
    from cadrumo.application.ledger.extraction_draft_repository import bind_extraction_draft_repository_factory
    from cadrumo.application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from cadrumo.application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from cadrumo.application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from cadrumo.application.ledger.usage_ratio_repository import (
        bind_usage_ratio_censo_guard_loader,
        bind_usage_ratio_profile_persistence,
    )
    from cadrumo.application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from cadrumo.application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from cadrumo.application.modelo.justificante_repository import bind_justificante_repository_factory
    from cadrumo.application.modelo.reconciliation_parsing import bind_reconciliation_evidence_parser
    from cadrumo.application.modelo.reconciliation_records import bind_modelo_reconciliation_persistence_factory
    from cadrumo.application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from cadrumo.core.redaction.tax_identity_admission import bind_tax_identity_admission
    from cadrumo.domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission
    from cadrumo.entrypoints.adapter_composition import calculation_revision_catalogue_repository

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
        bind_exchange_rate_provider_factory(recorded_ecb_rate_provider),
    ):
        yield


@pytest.fixture
def overview_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Provide the profile-backed storage lifecycle required by overview CLI tests."""
    from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
    from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root

    profile_id = "11111111-1111-4111-8111-111111111111"
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(profile_id):
        register_minimal_profile(profile_id=profile_id)
        yield


@pytest.fixture(autouse=True)
def _evict_test_bound_bucket_session() -> Iterator[None]:
    """Evict a bucket session a test bound itself, preserving inherited sessions."""
    from cadrumo.adapters.persistence.storage.master_key.tests.bucket_session_isolation import (
        evict_bucket_sessions_bound_since,
        observe_bucket_session_binding,
    )

    inherited = observe_bucket_session_binding()
    yield
    evict_bucket_sessions_bound_since(inherited)


@pytest.fixture(scope="module", autouse=True)
def _refuse_a_bucket_session_leaked_past_its_module() -> Iterator[None]:
    """Refuse and evict a bucket session that escaped its owning test module."""
    from cadrumo.adapters.persistence.storage.master_key.tests.bucket_session_isolation import (
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
    """Close a profile record authority a test introduced, leaving inherited state intact."""
    if "cadrumo.application.user_profile.profile_record_repository" not in sys.modules:
        yield
        return
    from cadrumo.application.user_profile.profile_record_repository import (
        active_profile_record_session,
        close_active_profile_record_session,
    )

    inherited = active_profile_record_session()
    yield
    bound = active_profile_record_session()
    if bound is not None and bound is not inherited:
        close_active_profile_record_session()


register_collection_storage_root_cleanup(collection_storage_root())

# A publish into the checkout's live authority during the run would swap the
# generation under every session-scoped lease, so the run reads the generation
# current at start. xdist workers inherit the frozen root and skip this.
if Path(os.environ["CADRUMO_AUTHORITY_ROOT"].strip()).resolve() == _PURE_STDLIB_AUTHORITY_ROOT:
    _frozen_authority_root = import_module("cadrumo.tests.authority_run_snapshot").freeze_authority_root(
        _PURE_STDLIB_AUTHORITY_ROOT,
        _collection_storage_root.authority_snapshot_root(),
    )
    if _frozen_authority_root is not None:
        os.environ["CADRUMO_AUTHORITY_ROOT"] = str(_frozen_authority_root)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Create and announce this pytest invocation's durable run log."""
    marker_hook.reset_held_serials()
    marker_hook.reset_marker_violations()
    # The hold must see the SELECTED items, which this module's own
    # collection hook cannot: it runs first, on purpose, so the taxonomy
    # contract reaches tests this lane would never execute.
    config.pluginmanager.register(marker_hook.SerialHoldPlugin(), "cadrumo-serial-hold")
    fixture_resolution_hook.reset_refused_requests()
    # The unraisable-exception plugin forces full gc passes at session end to
    # flush __del__ errors. Over this suite's post-collection heap those passes
    # cost seconds per process (per xdist worker); reference counting already
    # runs finalisers promptly on CPython, so the sweep is skipped, as pytester
    # itself does.
    config.stash[gc_collect_iterations_key] = 0
    _run_logging.configure(config)


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int | None, str]) -> None:
    """Record the test identity before execution begins."""
    del location
    _run_logging.log_start(nodeid)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Persist each test verdict and immediate failure detail."""
    _run_logging.log_report(report)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Persist collection failures immediately."""
    _run_logging.log_collection_report(report)


def pytest_internalerror(excrepr: object, excinfo: object) -> None:
    """Persist pytest internal errors that have no test or collection report."""
    del excinfo
    _run_logging.log_internal_error(excrepr)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Fail incomplete serial runs, mis-marked collections and unresolved fixture requests, then finalize metadata."""
    del exitstatus
    marker_hook.fail_session_on_held_serials(session)
    marker_hook.fail_session_on_marker_violations(session)
    fixture_resolution_hook.fail_session_on_refused_requests(session)
    _run_logging.finish(session.config, session.exitstatus)


def pytest_testnodedown(node: object, error: object | None) -> None:
    """Collect serial holds, marker violations and refused fixture requests from an xdist worker."""
    del error
    marker_hook.record_held_from_node(node)
    marker_hook.record_marker_violations_from_node(node)
    fixture_resolution_hook.record_refused_from_node(node)


_SHARED_AUTHORITY_MODULE = "cadrumo.domain.calculations.registry.authority"
"""The module that owns the process-shared registry authority reader."""


def _release_shared_registry_authority() -> None:
    """Close the process-shared registry authority, if this process opened it.

    The shared owner holds the frozen generation's database open until
    interpreter teardown, which comes after the exit cleanup that removes the
    snapshot and the run's scratch around it. Windows refuses to delete a file a
    live connection holds, so a run that read the registry left both behind.
    A process that never imported the owning module holds nothing, and nothing
    is imported for it here.

    A release refused because an operation still holds a lease is logged by the
    release and restated on stderr here, never raised: the session's verdict is
    already decided, and the run log records which file then kept the scratch.
    """
    if _SHARED_AUTHORITY_MODULE not in sys.modules:
        return
    from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority

    if not release_bundled_indexed_authority():
        sys.stderr.write("the shared registry authority stayed open at session end: an operation still holds it\n")


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    """Release the shared registry authority, then restate the run-log location last.

    The release happens on a controller only, and only here: every session
    fixture and lease has ended by now and xdist has torn its workers down, so
    the frozen snapshot is no longer read by anything in the run.
    """
    if not hasattr(config, "workerinput"):
        _release_shared_registry_authority()
    _run_logging.restate(config)


@pytest.fixture
def publish_authority_artifact(tmp_path: Path) -> Callable[[AuthorityArtifact], AuthorityDescriptor]:
    """Publish real synthetic artifacts only within the requesting test's root."""
    from dev.registry.pipeline.authority_publication import install_validated_authority_database

    def publish(artifact: AuthorityArtifact) -> AuthorityDescriptor:
        return install_validated_authority_database(artifact, destination=tmp_path, require_current=lambda: None)

    return publish


@pytest.fixture(scope="session", autouse=True)
def _configure_logging_at_the_host_boundary() -> None:
    """Configure logging once, as every host does at its process boundary.

    Left unconfigured, the first warning a test emits installs the configuration
    mid-test, and ``dictConfig`` then replaces the root handlers -- including the
    one ``caplog`` attached for that test, which loses the very record it waited
    for.
    """
    from cadrumo.core.logging import configure_logging

    configure_logging()


@pytest.fixture(scope="session")
def _resident_service_environment() -> Iterator[None]:
    """Give resident-service child processes one isolated singleton scope."""
    with TemporaryDirectory(prefix="vaultspec-rag-pytest-") as root_text:
        root = Path(root_text)
        status_dir = root / "status"
        qdrant_dir = root / "qdrant"
        status_dir.mkdir()
        qdrant_dir.mkdir()
        with temporary_env(
            _VAULTSPEC_RAG_PYTEST_SINGLETON_ROOT=str(root),
            _VAULTSPEC_RAG_PYTEST_SINGLETON_ACTIVE="1",
            VAULTSPEC_RAG_STATUS_DIR=str(status_dir),
            VAULTSPEC_RAG_QDRANT_STORAGE_DIR=str(qdrant_dir),
        ):
            yield


@pytest.fixture(autouse=True)
def _inherit_resident_service_environment(request: pytest.FixtureRequest) -> None:
    """Activate the shared singleton scope only for resident-service tests."""
    if request.node.get_closest_marker("resident_service") is not None:
        request.getfixturevalue("_resident_service_environment")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the repository-wide collection-policy contracts."""
    # First, before the marker contract holds serial items back and before
    # marker selection deselects anything: a dead test must be refused even in
    # a lane that would never execute it.
    fixture_resolution_hook.apply(config, items)
    marker_hook.apply(config, items)
    marker_hook.apply_banned_live_import_policy(items)
    # Recorded here, before selection removes anything, so the empty-selection
    # banner can name the markers these tests actually carry instead of
    # guessing a lane that may be just as empty.
    deselection_hook.record_collected_markers(config, items)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Take everything collection built out of the cyclic collector's reach.

    By the end of collection a process holds every imported module, class,
    fixture definition and collected item, and almost all of it lives for the
    rest of the session. Every full collection during the run re-traversed that
    whole population and freed nothing from it. Frozen, it is skipped; objects
    the tests create afterwards are collected exactly as before. Measured on
    the registry and calculation suites (2398 tests, four workers): 13 to 18
    percent of wall time.
    """
    del session
    gc.collect()
    gc.freeze()


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the repository-owned xdist auto-width resolver."""
    return worker_count_hook.resolve_auto_num_workers(config)


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Delegate to the deselection, held-serial, marker-violation, unresolved-fixture and lost-test reporters."""
    deselection_hook.apply(terminalreporter, exitstatus, config)
    marker_hook.report_held_serials(terminalreporter)
    marker_hook.report_marker_violations(terminalreporter)
    fixture_resolution_hook.report_refused_requests(terminalreporter)
    lost_test_hook.apply(terminalreporter, exitstatus, config)

"""Every browser and local AI consumer refuses with its setup before any effect.

A feature that needs the browser or the local AI must say so when the
component is not ready: the refusal carries the setup probe's verdict, the
verdict names ``operator.provision.browser`` or ``operator.provision.local_ai``,
and nothing was sent to the runtime or launched first. This gate holds that
for the whole consumer set, and finds the set in the source rather than in a
list that could go stale.

Local AI rows:

- Discovery. A dispatch unit is a top-level class or function under
  ``src/cadrumo`` that builds an ``LLMRequest`` or a ``ProviderRequest``, plus
  every top-level definition of the same module that names one. A consumer
  site is a top-level definition in another module that names a dispatch unit
  outside an annotation. The discovered sites must equal the rows of
  ``_LOCAL_AI_CONSUMERS``: a new site without a row fails, and so does a row
  whose site is gone.
- Roles. Every ``ModelRole`` has at least one driven consumer, and a unit that
  names its role in its request is driven under that role at every site.
- Behaviour. Each row's drivers call the composed site against a real
  loopback runtime that answers its inventory with no models and records
  every request it is sent. The outcome must carry a verdict whose action is
  ``operator.provision.local_ai`` and whose ``role`` fact is the driven role,
  and the runtime must have received no request.

Local AI operation rows:

- Coverage. Each consumer row names the registered operations whose
  composition reaches its site, or is listed in ``_UNWRAPPED_CONSUMERS`` with
  the reason none does. Every named operation must be registered and have a
  row in ``_OPERATION_ROWS``, and every row must be named by a consumer.
- Behaviour. Each operation row settles its operation through the production
  registry and the real supervisor, journal and encrypted operand store, in an
  enrolled profile, against the same empty runtime. What a client in another
  process reads of it, the recorded error detail of a stopped operation or the
  public result of a successful one, must carry the consumer's verdict naming
  ``operator.provision.local_ai`` for the driven role, with no request sent.
  An operation that swallows the refusal into its result, or stops without
  publishing its detail, fails here.

Browser rows:

- Launch. Every production function that constructs a ``BrowserSession`` or
  launches Chromium calls ``require_browser_ready`` earlier in its own body.
- Operations. Every call to an operation definition builder (``build_*definition``
  or ``build_*definitions``) or to ``AuthOperationPorts`` that hands it a browser
  resource also hands it a preflight whose first call is
  ``require_browser_ready``, or ``require_browser_ready`` itself.
- Behaviour. Every discovered launch site and gated preflight is driven with an
  empty browsers root and must raise ``BrowserNotReadyError`` whose verdict
  action is ``operator.provision.browser``.

Where it stops:

- The local AI transport (``llm.client``), consumer admission's fitness
  measurement (``llm.role_fitness``) and setup's launch check
  (``browser_runtime.launch_check``) dispatch or launch on purpose and are
  exempt by name; an exemption that no longer matches a discovered site fails.
- Setup's runtime traffic (pull, load, keep-alive under
  ``application.provisioning_*``) does not build a request and is not a
  consumer. ``src/cadrumo_agent_service`` and the desktop are not scanned.
- A dispatch reached only through ``self`` attributes, a dynamic import or a
  value read from a mapping is not discovered.
- A behavioural row proves the refusal for the empty-inventory runtime and the
  empty browsers root. It does not prove the order inside an operation
  executor: that its registered preflight runs before credentials load is
  covered by the operation tests for the capture, identity-check and sign-in
  executors, not here.
- A browser resource that reaches an operation only inside a composed port,
  rather than as an argument of its definition builder, is outside the
  operations row.
- Which registered operation reaches a local AI consumer is declared on the
  consumer row, not discovered: a new operation composed over an existing
  consumer passes until someone names it there. Each operation is settled
  through one lane per row, against an absent model only; a runtime that does
  not answer, or a refusal raised only on another lane, is covered by the
  consumer rows and the operations' own settlement tests.
- Browser operations are held to their preflight here, not to what they
  publish: that a live capture or sign-in refusal publishes its verdict is
  covered by those operations' own settlement tests.

Each structural row and each assertion helper is run once more against an
isolated fixture that carries the defect it exists to catch.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import importlib
import os
import re
import traceback
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from typing import override
from uuid import UUID, uuid4

import httpx
import pytest
from PIL import Image
from pydantic import BaseModel

from ...adapters.outbound.aeat.browser.errors import (
    BrowserNotReadyError,
    BrowserNotUsableError,
    BrowserPreconditionCondition,
    browser_no_action_verdict,
)
from ...adapters.outbound.aeat.browser.factory import (
    create_browser_session,
    opened_browser_page,
    shared_playwright_runtime,
)
from ...adapters.outbound.aeat.browser.profile import Profile
from ...adapters.outbound.aeat.browser.session import BrowserSession
from ...adapters.outbound.llm.evidence_draft_text import default_extraction_authority_values
from ...adapters.outbound.llm.statement_reading import LocalStatementReader
from ...adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposal
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import _repositories
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.ledger.column_roles import ColumnRoleReaderUnavailable, column_role_mapping_resolver
from ...application.ledger.document_transcription import DocumentTranscription
from ...application.ledger.evidence_textlayer import text_layer_transcriber_identity
from ...application.ledger.import_ports import LedgerImportReaderUnavailableError
from ...application.ledger.invoice_draft_extraction_ports import InvoiceDraftReaderUnavailableError, VisionImage
from ...application.ledger.llm_classification_ports import EvidenceImage
from ...application.ledger.read_access import resolve_ledger_read_access
from ...application.ledger.statement_reading import statement_reader_factory
from ...application.local_reader import probe_local_reader
from ...application.operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ...application.operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ...application.operations.contract_manifest import OperationContractManifestV1
from ...application.operations.models import CredentialFreeOperationRequest, OperationRequest
from ...application.operations.operation_definition import build_single_phase_definition
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationPublicDefinitionRegistrationV1, OperationRegistry
from ...application.operations.subject_reference import OperationSubjectReferenceV1
from ...application.operations.supervisor import OperationSupervisor
from ...application.operator_actions.models import PreconditionVerdict
from ...application.provisioning_browser import BROWSER_PROVISION_ACTION_ID
from ...application.provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from ...core.config import Settings, load_settings, override_settings
from ...core.errors.hierarchy import TerminalPreconditionErrorMixin
from ...core.image_media_type import ImageMediaType
from ...core.model_catalogue import ModelRole, candidates_for_role, default_model_runtime_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.operator_action_enums import NoRecoveryOutcome
from ...core.tabular import normalize_tabular_bytes
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.llm import PromptSpec
from ...domain.transactions.models import Transaction
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...tests.llm_vision_evidence_support import png_image
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ..adapter_composition import build_ledger_evidence_ports, profile_adapter_composition
from ..invoice_intake_operation_composition import build_invoice_intake_ports
from ..ledger_evidence_extraction_composition import invoice_draft_extraction_ports
from ..ledger_llm_composition import compose_ledger_llm
from .dependency_operation_gating_support import (
    OperationSettler,
    SettledOperation,
    operation_runtime,
    published_verdicts,
    read_published,
    runtime_holding_nothing,
    settle_classify_review,
    settle_evidence_batch,
    settle_evidence_confirm,
    settle_evidence_extract,
    settle_invoice_import,
    settle_ledger_import,
    settle_ledger_import_pdf,
    settle_split_review,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _restore_playwright_browsers_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo the browser root the Playwright start points the whole process at, for later tests on this worker."""
    current = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if current is None:
        monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    else:
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", current)


_PACKAGE = "cadrumo"
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]

_BUCKET_ID = "5e9f1c3a-7b2d-4c6e-9a8b-1d2e3f4a5b6c"

# -- Source discovery ------------------------------------------------------------


@dataclass(frozen=True)
class _Module:
    """One production module: its tree and what each local name refers to."""

    name: str
    tree: ast.Module
    aliases: Mapping[str, str]
    definitions: Mapping[str, ast.stmt]


def _is_production(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return (
        "tests" not in parts
        and "__pycache__" not in parts
        and not path.name.startswith("test_")
        and path.name != "conftest.py"
    )


def _module_name(path: Path, root: Path, package: str) -> str:
    parts = [package, *path.relative_to(root).with_suffix("").parts]
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _import_aliases(tree: ast.Module, module: str, *, is_package: bool) -> dict[str, str]:
    """Map every name the module imports, anywhere in it, to the dotted origin it names."""
    package = module.split(".") if is_package else module.split(".")[:-1]
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package[: len(package) - (node.level - 1)]
                base = ".".join([*base_parts, *([] if node.module is None else [node.module])])
            else:
                base = node.module or ""
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{base}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # ``import a.b`` binds ``a``; ``import a.b as c`` binds ``c`` to ``a.b``.
                if alias.asname is None:
                    top = alias.name.split(".")[0]
                    aliases[top] = top
                else:
                    aliases[alias.asname] = alias.name
    return aliases


def _load_modules(root: Path, package: str) -> dict[str, _Module]:
    modules: dict[str, _Module] = {}
    for path in sorted(root.rglob("*.py")):
        if not _is_production(path, root):
            continue
        name = _module_name(path, root, package)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions: dict[str, ast.stmt] = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        }
        aliases = _import_aliases(tree, name, is_package=path.name == "__init__.py")
        aliases.update({local: f"{name}.{local}" for local in definitions})
        modules[name] = _Module(name=name, tree=tree, aliases=aliases, definitions=definitions)
    return modules


class _References(ast.NodeVisitor):
    """Collect the dotted origins a node names, leaving annotations out."""

    def __init__(self, aliases: Mapping[str, str]) -> None:
        self._aliases = aliases
        self.found: set[str] = set()

    @override
    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and (origin := self._aliases.get(node.id)) is not None:
            self.found.add(origin)

    @override
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and (base := self._aliases.get(node.value.id)) is not None:
            self.found.add(f"{base}.{node.attr}")
        self.generic_visit(node)

    @override
    def visit_arg(self, node: ast.arg) -> None:
        return

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        for statement in node.body:
            self.visit(statement)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)


def _references(module: _Module, node: ast.AST) -> set[str]:
    collector = _References(module.aliases)
    collector.visit(node)
    return collector.found


def _owner(origin: str) -> str:
    return origin.rsplit(".", 1)[0]


# -- Local AI discovery ------------------------------------------------------------

_REQUEST_TYPES = frozenset(
    {
        "cadrumo.adapters.outbound.llm.models.LLMRequest",
        "cadrumo.adapters.outbound.llm.providers.base.ProviderRequest",
    }
)
_MODEL_ROLE = "cadrumo.core.model_catalogue.ModelRole"

#: Modules that dispatch to the local AI on purpose, and why that is not a feature consuming it.
_EXEMPT_DISPATCH_MODULES: Mapping[str, str] = {
    "cadrumo.adapters.outbound.llm.client": "the transport every consumer dispatches through",
    "cadrumo.adapters.outbound.llm.role_fitness": "consumer admission's fitness measurement of an installed model",
}


def _literal_roles(module: _Module, node: ast.AST) -> set[ModelRole]:
    """Return the roles a node's requests name with ``model_role=ModelRole.X``."""
    roles: set[ModelRole] = set()
    for keyword in (item for item in ast.walk(node) if isinstance(item, ast.keyword)):
        value = keyword.value
        if (
            keyword.arg == "model_role"
            and isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and module.aliases.get(value.value.id) == _MODEL_ROLE
        ):
            roles.add(ModelRole[value.attr])
    return roles


def _dispatch_units(modules: Mapping[str, _Module]) -> dict[str, frozenset[ModelRole]]:
    """Return every dispatch unit and the roles its requests name, directly or through a unit it calls."""
    units: dict[str, frozenset[ModelRole]] = {}
    for module in modules.values():
        names = {name: _references(module, node) for name, node in module.definitions.items()}
        members = {name for name, found in names.items() if found & _REQUEST_TYPES}
        roles = {name: _literal_roles(module, module.definitions[name]) for name in members}
        changed = True
        while changed:
            changed = False
            for name, found in names.items():
                reached = {member for member in members if f"{module.name}.{member}" in found and member != name}
                if not reached:
                    continue
                inherited = set().union(*(roles[member] for member in reached))
                if name not in members:
                    members.add(name)
                    roles[name] = _literal_roles(module, module.definitions[name]) | inherited
                    changed = True
                elif not inherited <= roles[name]:
                    roles[name] |= inherited
                    changed = True
        units.update({f"{module.name}.{name}": frozenset(roles[name]) for name in members})
    return units


def _consumer_sites(modules: Mapping[str, _Module], units: Mapping[str, object]) -> dict[str, frozenset[str]]:
    """Return every definition outside a unit's own module that names it, with the units it names."""
    sites: dict[str, frozenset[str]] = {}
    for module in modules.values():
        scopes: list[tuple[str, Sequence[ast.stmt]]] = [
            (f"{module.name}.{name}", [node]) for name, node in module.definitions.items()
        ]
        scopes.append(
            (
                f"{module.name}.<module>",
                [node for node in module.tree.body if node not in module.definitions.values()],
            )
        )
        for site, nodes in scopes:
            named = set().union(*(_references(module, node) for node in nodes)) if nodes else set()
            reached = frozenset(unit for unit in named if unit in units and _owner(unit) != module.name)
            if reached:
                sites[site] = reached
    return sites


def _local_ai_discovery(
    modules: Mapping[str, _Module],
) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[ModelRole]], list[str]]:
    """Return the consumer sites, the unit roles and any stale exemption."""
    units = _dispatch_units(modules)
    stale = [
        f"{module} is exempt ({reason}) but builds no request any more"
        for module, reason in _EXEMPT_DISPATCH_MODULES.items()
        if not any(_owner(unit) == module for unit in units)
    ]
    counted = {unit: roles for unit, roles in units.items() if _owner(unit) not in _EXEMPT_DISPATCH_MODULES}
    return _consumer_sites(modules, counted), counted, stale


# -- Browser discovery -------------------------------------------------------------

_BROWSER_SESSION = "cadrumo.adapters.outbound.aeat.browser.session.BrowserSession"
_BROWSER_READY = "cadrumo.adapters.outbound.aeat.browser.session.require_browser_ready"
_BROWSER_RESOURCES = frozenset(
    {
        "cadrumo.adapters.outbound.aeat.browser.factory.BrowserRuntimeResourceScope",
        "cadrumo.adapters.outbound.aeat.browser.factory.default_browser_session_factory",
        "cadrumo.adapters.outbound.aeat.browser.factory.create_browser_session",
    }
)
_LAUNCH_ATTRIBUTES = frozenset({"launch", "launch_persistent_context"})
_DEFINITION_BUILDER = re.compile(r"^(build_\w*definitions?|AuthOperationPorts)$")

#: Launches that are setup's own measurement of the browser, not a feature using it.
_EXEMPT_BROWSER_STARTS: Mapping[str, str] = {
    "cadrumo.adapters.outbound.browser_runtime.launch_check.launch_headless_browser": (
        "setup's full check launches the revision-exact executable it verifies"
    ),
}

type _Function = ast.FunctionDef | ast.AsyncFunctionDef


def _functions(module: _Module) -> Iterator[tuple[str, _Function]]:
    """Yield every function and method of a module under its dotted qualified name."""

    def walk(prefix: str, body: Sequence[ast.stmt]) -> Iterator[tuple[str, _Function]]:
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                yield f"{prefix}.{node.name}", node
                yield from walk(f"{prefix}.{node.name}", node.body)
            elif isinstance(node, ast.ClassDef):
                yield from walk(f"{prefix}.{node.name}", node.body)

    yield from walk(module.name, module.tree.body)


def _own_calls(function: _Function) -> list[ast.Call]:
    """Return the calls in a function's own body, in source order, leaving nested definitions out."""
    calls: list[ast.Call] = []
    pending: list[ast.AST] = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            continue
        if isinstance(node, ast.Call):
            calls.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def _callee(module: _Module, call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return module.aliases.get(func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base = module.aliases.get(func.value.id)
        return None if base is None else f"{base}.{func.attr}"
    return None


def _starts_browser(module: _Module, call: ast.Call) -> bool:
    func = call.func
    launches = (
        isinstance(func, ast.Attribute)
        and func.attr in _LAUNCH_ATTRIBUTES
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "chromium"
    )
    return launches or _callee(module, call) == _BROWSER_SESSION


def _browser_start_sites(modules: Mapping[str, _Module]) -> dict[str, str | None]:
    """Return every function that starts a browser, with why it is ungated or ``None`` when it checks first."""
    sites: dict[str, str | None] = {}
    for module in modules.values():
        for qualified, function in _functions(module):
            calls = _own_calls(function)
            starts = [call for call in calls if _starts_browser(module, call)]
            if not starts:
                continue
            checks = [call for call in calls if _callee(module, call) == _BROWSER_READY]
            if not checks:
                sites[qualified] = f"line {starts[0].lineno} starts a browser and nothing checks it is set up"
            elif (checks[0].lineno, checks[0].col_offset) > (starts[0].lineno, starts[0].col_offset):
                sites[qualified] = (
                    f"line {starts[0].lineno} starts a browser before the check on line {checks[0].lineno}"
                )
            else:
                sites[qualified] = None
    return sites


def _top_level_functions(modules: Mapping[str, _Module]) -> dict[str, tuple[_Module, _Function]]:
    return {
        f"{module.name}.{name}": (module, node)
        for module in modules.values()
        for name, node in module.definitions.items()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _checks_browser_first(origin: str, functions: Mapping[str, tuple[_Module, _Function]]) -> bool:
    if origin == _BROWSER_READY:
        return True
    found = functions.get(origin)
    if found is None:
        return False
    module, function = found
    calls = _own_calls(function)
    return bool(calls) and _callee(module, calls[0]) == _BROWSER_READY


def _preflight_origins(module: _Module, call: ast.Call) -> set[str]:
    """Return the functions a builder call hands over as callables, unwrapping ``functools.partial``."""
    origins: set[str] = set()
    for argument in (*call.args, *(keyword.value for keyword in call.keywords)):
        handed = argument
        if isinstance(argument, ast.Call) and _callee(module, argument) == "functools.partial" and argument.args:
            handed = argument.args[0]
        if isinstance(handed, ast.Name) and (origin := module.aliases.get(handed.id)) is not None:
            origins.add(origin)
    return origins


def _operation_browser_preflights(modules: Mapping[str, _Module]) -> tuple[frozenset[str], list[str]]:
    """Return the gated preflights handed to browser operations, and every builder call that has none."""
    functions = _top_level_functions(modules)
    gated: set[str] = set()
    problems: list[str] = []
    for module in modules.values():
        for call in (node for node in ast.walk(module.tree) if isinstance(node, ast.Call)):
            func = call.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if not _DEFINITION_BUILDER.match(name):
                continue
            handed = set().union(
                *(_references(module, argument) for argument in (*call.args, *(k.value for k in call.keywords)))
            )
            if not handed & _BROWSER_RESOURCES:
                continue
            checked = {
                origin for origin in _preflight_origins(module, call) if _checks_browser_first(origin, functions)
            }
            if checked:
                gated |= checked
            else:
                problems.append(
                    f"{module.name}:{call.lineno} {name}() is handed a browser and no preflight that checks it first"
                )
    return frozenset(gated), problems


# -- Shared runtime and outcomes -------------------------------------------------


def _operator_named_model(role: ModelRole) -> str:
    """Return a catalogued model for ``role`` other than its default, as an operator would name one.

    The catalogue's own choice is sized to the free memory measured now, and on
    a busy host it refuses with a verdict setup cannot repair; a named model is
    honoured, so the rows of the selected roles do not depend on what else is
    running.
    """
    return next(
        candidate.runtime_id
        for candidate in candidates_for_role(role)
        if candidate.runtime_id != default_model_runtime_id(role)
    )


_OPERATOR_MAPPING_MODEL = _operator_named_model(ModelRole.COLUMN_ROLE_MAPPING)
_OPERATOR_SUPPLY_NATURE_MODEL = _operator_named_model(ModelRole.SUPPLY_NATURE_PROPOSAL)


@dataclass(frozen=True)
class _Runtime:
    """A local AI runtime that holds no model, and what it was sent."""

    settings: Settings
    posts: list[str]


@contextmanager
def _runtime_holding_nothing(tmp_path: Path) -> Generator[_Runtime]:
    """Serve a real loopback runtime whose inventory is empty and that records every request it is sent."""
    posts: list[str] = []

    class _EmptyRuntime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            posts.append(self.path)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    with (
        serving_loopback(_EmptyRuntime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_mapping_model=_OPERATOR_MAPPING_MODEL,
            cadrumo_llm_ollama_supply_nature_model=_OPERATOR_SUPPLY_NATURE_MODEL,
            cadrumo_llm_cache_dir=tmp_path / "llm-cache",
            cadrumo_llm_usage_dir=tmp_path / "llm-usage",
            cadrumo_llm_run_record_dir=tmp_path / "llm-runs",
        ),
    ):
        yield _Runtime(settings=load_settings(), posts=posts)


def _outcome(run: Callable[[], object]) -> object:
    """Return what ``run`` returned or raised, so a refusal and a silent return are judged alike."""
    try:
        return run()
    except Exception as error:
        return error


def _verdict_of(outcome: object) -> PreconditionVerdict | None:
    if isinstance(outcome, PreconditionVerdict):
        return outcome
    if isinstance(outcome, InvoiceDraftReaderUnavailableError | ColumnRoleReaderUnavailable):
        return outcome.precondition_verdict
    if isinstance(outcome, SupplyNatureProposal):
        return outcome.reader_unavailable
    if isinstance(outcome, TerminalPreconditionErrorMixin):
        verdict = outcome.terminal_precondition_verdict
        return verdict if isinstance(verdict, PreconditionVerdict) else None
    return None


def _described(outcome: object) -> str:
    """Name an outcome; a raised error also names where it was raised, so a failing row points at its cause."""
    if not isinstance(outcome, BaseException):
        return type(outcome).__name__
    frames = traceback.extract_tb(outcome.__traceback__)
    where = "" if not frames else f" at {Path(frames[-1].filename).name}:{frames[-1].lineno}"
    return f"{type(outcome).__name__}{where}"


def _local_ai_gating_problems(outcome: object, posts: Sequence[str], role: ModelRole) -> list[str]:
    """Return why an outcome is not a local AI refusal for ``role`` made before any request."""
    problems: list[str] = []
    if posts:
        problems.append(f"sent {len(posts)} request(s) to the local AI before refusing: {sorted(set(posts))}")
    verdict = _verdict_of(outcome)
    if verdict is None:
        problems.append(f"ended in {_described(outcome)} carrying no verdict")
        return problems
    if verdict.action is None:
        problems.append(f"verdict {verdict.failed_condition_id} names no setup action")
    elif verdict.action.action_id != LOCAL_AI_PROVISION_ACTION_ID:
        problems.append(f"verdict names {verdict.action.action_id}, not {LOCAL_AI_PROVISION_ACTION_ID}")
    spoken = sorted({str(evidence.values.get("role")) for evidence in verdict.evidence})
    if role.value not in spoken:
        problems.append(f"verdict speaks for role {spoken}, not {role.value}")
    return problems


def _browser_refusal_problems(outcome: object) -> list[str]:
    """Return why an outcome is not a browser refusal that names the browser setup."""
    if not isinstance(outcome, BrowserNotReadyError):
        return [f"ended in {type(outcome).__name__}, not a refusal for a browser that is not set up"]
    verdict = outcome.terminal_precondition_verdict
    if verdict is None or verdict.action is None:
        return ["the refusal names no setup action"]
    if verdict.action.action_id != BROWSER_PROVISION_ACTION_ID:
        return [f"the refusal names {verdict.action.action_id}, not {BROWSER_PROVISION_ACTION_ID}"]
    return []


# -- Local AI consumer drivers -----------------------------------------------------

_HEADERS = ("fecha", "concepto", "importe")
_TABLE = b"fecha;concepto;importe\n2026-01-05;Cuota mensual;-12,50\n"


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="row-consumer-gating",
        booked_date=date(2026, 3, 1),
        value_date=date(2026, 3, 1),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Office SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )


def _transcription(text: str) -> DocumentTranscription:
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="a" * 64,
        transcriber=text_layer_transcriber_identity(),
    )


def _png_base64() -> str:
    return base64.b64encode(png_image()).decode("ascii")


def _scan_only_pdf() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (260, 160), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def _drive_ledger_text_classifier(runtime: _Runtime) -> object:
    ports = compose_ledger_llm(bucket_id=_BUCKET_ID, settings=runtime.settings).ports
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        transaction = _transaction()
    return ports.make_text_classifier(PromptSpec()).classify(transaction)


def _drive_ledger_vision_classifier(runtime: _Runtime) -> object:
    ports = compose_ledger_llm(bucket_id=_BUCKET_ID, settings=runtime.settings).ports
    image = EvidenceImage.from_base64(_png_base64(), ImageMediaType.PNG)
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        transaction = _transaction()
    return ports.make_vision_classifier(PromptSpec(), None).classify(transaction, evidence_images=(image,))


def _extraction_ports():
    return invoice_draft_extraction_ports(evidence_ports=build_ledger_evidence_ports(bucket_id=_BUCKET_ID))


def _drive_evidence_text_read(runtime: _Runtime) -> object:
    with bundled_indexed_authority().operation() as operation:
        values = default_extraction_authority_values(operation=operation)
        return _extraction_ports().read_text(
            _transcription("FACTURA 7 Base 10,00 IVA 2,10 Total 12,10"), runtime.settings, None, None, values
        )


def _drive_evidence_vision_read(runtime: _Runtime) -> object:
    image = VisionImage(base64_data=_png_base64(), media_type=ImageMediaType.PNG)
    return _extraction_ports().transcribe_vision((image,), "b" * 64, runtime.settings, None, None)


def _drive_evidence_supply_nature(runtime: _Runtime) -> object:
    return _extraction_ports().propose_supply_nature(
        _transcription("Licencia anual de software\nSoporte remoto"), runtime.settings
    )


def _drive_ledger_import_column_roles(runtime: _Runtime) -> object:
    del runtime
    with profile_adapter_composition():
        resolver = column_role_mapping_resolver()
        if resolver is None:
            raise LookupError("the composition bound no column-role resolver")
        return resolver(normalize_tabular_bytes(_TABLE))


def _never_commit(save: Callable[[], None]) -> None:
    del save
    raise AssertionError("a column mapping must not commit anything")


def _drive_invoice_book_column_roles(runtime: _Runtime) -> object:
    del runtime
    with bundled_indexed_authority().operation() as operation:
        ports = build_invoice_intake_ports(
            profile_id=UUID(_BUCKET_ID), operation=operation, commit=_never_commit, admit_provider=lambda: None
        )
        return ports.mapper(_HEADERS)


def _drive_statement_text_read(runtime: _Runtime) -> object:
    del runtime
    with profile_adapter_composition():
        factory = statement_reader_factory()
        if factory is None:
            raise LookupError("the composition bound no statement reader")
        return factory().propose_page(_transcription("05.03.2026 Cafeteria -4,50 EUR"))


def _drive_statement_scanned_page(runtime: _Runtime) -> object:
    del runtime
    with profile_adapter_composition():
        factory = statement_reader_factory()
        if factory is None:
            raise LookupError("the composition bound no statement reader")
        return factory().transcribe_scanned_pages(_scan_only_pdf(), page_numbers=(1,), source_content_sha256="c" * 64)


type _Driver = Callable[[_Runtime], object]


@dataclass(frozen=True)
class _LocalAiConsumer:
    """One consumer site: the dispatch units it names, one driver per role it reads with, and its operations.

    ``operations`` names every registered operation whose composition reaches
    the site; each must have an operation row. A site no operation reaches
    names none and has an entry in ``_UNWRAPPED_CONSUMERS`` saying why.
    """

    units: frozenset[str]
    drivers: Mapping[ModelRole, _Driver]
    operations: frozenset[str] = frozenset()


_LLM = "cadrumo.adapters.outbound.llm"

#: Every site that names a local AI dispatch unit, keyed by its qualified name.
_LOCAL_AI_CONSUMERS: Mapping[str, _LocalAiConsumer] = {
    "cadrumo.entrypoints.ledger_llm_composition.compose_ledger_llm": _LocalAiConsumer(
        units=frozenset(
            {
                f"{_LLM}.text_classifier.LocalTextLLMClassifier",
                f"{_LLM}.vision_classifier.LocalVisionLLMClassifier",
            }
        ),
        drivers={
            ModelRole.TEXT_EXTRACTION: _drive_ledger_text_classifier,
            ModelRole.VISION_TRANSCRIPTION: _drive_ledger_vision_classifier,
        },
        operations=frozenset({"ledger.classify.review", "ledger.split.review"}),
    ),
    "cadrumo.entrypoints.ledger_evidence_extraction_composition._invoice_read_text": _LocalAiConsumer(
        units=frozenset(
            {
                f"{_LLM}.evidence_draft_text.TextInvoiceFieldExtractor",
                f"{_LLM}.evidence_draft_text.extract_invoice_fields_from_text",
            }
        ),
        drivers={ModelRole.TEXT_EXTRACTION: _drive_evidence_text_read},
        operations=frozenset({"ledger.evidence.extract", "ledger.evidence.confirm", "ledger.evidence.batch"}),
    ),
    "cadrumo.entrypoints.ledger_evidence_extraction_composition._invoice_transcribe_vision": _LocalAiConsumer(
        units=frozenset(
            {
                f"{_LLM}.evidence_draft_vision.LocalVisionDocumentTranscriber",
                f"{_LLM}.evidence_draft_vision.transcribe_document_images",
            }
        ),
        drivers={ModelRole.VISION_TRANSCRIPTION: _drive_evidence_vision_read},
        operations=frozenset({"ledger.evidence.extract", "ledger.evidence.confirm", "ledger.evidence.batch"}),
    ),
    "cadrumo.entrypoints.ledger_evidence_extraction_composition._invoice_propose_supply_nature": _LocalAiConsumer(
        units=frozenset({f"{_LLM}.supply_nature_proposal.SupplyNatureProposer"}),
        drivers={ModelRole.SUPPLY_NATURE_PROPOSAL: _drive_evidence_supply_nature},
    ),
    "cadrumo.entrypoints.adapter_composition._resolve_column_roles": _LocalAiConsumer(
        units=frozenset({f"{_LLM}.column_role_mapping.resolve_column_roles"}),
        drivers={ModelRole.COLUMN_ROLE_MAPPING: _drive_ledger_import_column_roles},
        operations=frozenset({"ledger.import"}),
    ),
    "cadrumo.entrypoints.invoice_intake_operation_composition.build_invoice_intake_ports": _LocalAiConsumer(
        units=frozenset({f"{_LLM}.column_role_mapping.resolve_header_roles"}),
        drivers={ModelRole.COLUMN_ROLE_MAPPING: _drive_invoice_book_column_roles},
        operations=frozenset({"ledger.invoice.import"}),
    ),
    "cadrumo.entrypoints.adapter_composition._statement_reader": _LocalAiConsumer(
        units=frozenset({f"{_LLM}.statement_reading.LocalStatementReader"}),
        drivers={ModelRole.TEXT_EXTRACTION: _drive_statement_text_read},
        operations=frozenset({"ledger.import"}),
    ),
    f"{_LLM}.statement_reading.LocalStatementReader": _LocalAiConsumer(
        units=frozenset({f"{_LLM}.evidence_draft_vision.LocalVisionDocumentTranscriber"}),
        drivers={ModelRole.VISION_TRANSCRIPTION: _drive_statement_scanned_page},
        operations=frozenset({"ledger.import"}),
    ),
}

#: Consumer sites no registered operation reaches, and why.
_UNWRAPPED_CONSUMERS: Mapping[str, str] = {
    "cadrumo.entrypoints.ledger_evidence_extraction_composition._invoice_propose_supply_nature": (
        "advisory and asked for only on request, which no registered extraction makes; a missing reader "
        "leaves the person asked as before rather than refusing"
    ),
}


def _site_problems(discovered: Mapping[str, frozenset[str]], registered: Mapping[str, _LocalAiConsumer]) -> list[str]:
    problems = [
        f"{site} reaches {sorted(discovered[site])} and has no gated-consumer row"
        for site in sorted(discovered.keys() - registered.keys())
    ]
    problems += [
        f"{site} has a row but no longer reaches a local AI reader"
        for site in sorted(registered.keys() - discovered.keys())
    ]
    problems += [
        f"{site} reaches {sorted(discovered[site])}, its row names {sorted(registered[site].units)}"
        for site in sorted(discovered.keys() & registered.keys())
        if discovered[site] != registered[site].units
    ]
    return problems


def _role_problems(
    discovered: Mapping[str, frozenset[str]],
    unit_roles: Mapping[str, frozenset[ModelRole]],
    registered: Mapping[str, _LocalAiConsumer],
) -> list[str]:
    """Return every role no consumer is driven under, and every unit role its site does not drive."""
    driven = {role for consumer in registered.values() for role in consumer.drivers}
    problems = [f"no consumer is driven under {role.value}" for role in ModelRole if role not in driven]
    for site, units in sorted(discovered.items()):
        consumer = registered.get(site)
        if consumer is None:
            continue
        for unit in sorted(units):
            missing = unit_roles.get(unit, frozenset()) - consumer.drivers.keys()
            problems += [f"{site} reaches {unit}, which reads with {role.value}, undriven" for role in missing]
    return problems


# -- Operation rows ----------------------------------------------------------------


@dataclass(frozen=True)
class _OperationDrive:
    """One way to settle a registered operation with its consumer's model missing, and the role it reads with."""

    role: ModelRole
    settle: OperationSettler


#: Every registered operation a consumer row names, with one drive per reading lane it is settled through.
_OPERATION_ROWS: Mapping[str, tuple[_OperationDrive, ...]] = {
    "ledger.import": (
        _OperationDrive(ModelRole.COLUMN_ROLE_MAPPING, settle_ledger_import),
        _OperationDrive(ModelRole.TEXT_EXTRACTION, settle_ledger_import_pdf),
    ),
    "ledger.invoice.import": (_OperationDrive(ModelRole.COLUMN_ROLE_MAPPING, settle_invoice_import),),
    "ledger.evidence.extract": (_OperationDrive(ModelRole.VISION_TRANSCRIPTION, settle_evidence_extract),),
    "ledger.evidence.confirm": (_OperationDrive(ModelRole.VISION_TRANSCRIPTION, settle_evidence_confirm),),
    "ledger.evidence.batch": (_OperationDrive(ModelRole.TEXT_EXTRACTION, settle_evidence_batch),),
    "ledger.classify.review": (_OperationDrive(ModelRole.TEXT_EXTRACTION, settle_classify_review),),
    "ledger.split.review": (_OperationDrive(ModelRole.VISION_TRANSCRIPTION, settle_split_review),),
}

_SHIPPED_MANIFEST = _PACKAGE_ROOT / "_data" / "operations" / "contract_manifest.json"


def _registered_definition_ids() -> frozenset[str]:
    """Return the definitions the shipped manifest records; its own check holds it equal to the live registry."""
    manifest = OperationContractManifestV1.model_validate_json(_SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    return frozenset(manifest.entries)


def _operation_coverage_problems(
    consumers: Mapping[str, _LocalAiConsumer],
    unwrapped: Mapping[str, str],
    rows: Mapping[str, object],
    registered: frozenset[str],
) -> list[str]:
    """Return every named operation without a row or registration, every stale row, and every silent site."""
    named = {operation for consumer in consumers.values() for operation in consumer.operations}
    problems = [f"{operation} wraps a consumer and has no operation row" for operation in sorted(named - rows.keys())]
    problems += [f"{operation} has a row but no consumer row names it" for operation in sorted(rows.keys() - named)]
    problems += [f"{operation} is named but not a registered operation" for operation in sorted(named - registered)]
    for site, consumer in sorted(consumers.items()):
        if not consumer.operations and site not in unwrapped:
            problems.append(f"{site} names no operation and no reason that none reaches it")
        if consumer.operations and site in unwrapped:
            problems.append(f"{site} names operations and is also listed as unwrapped")
    problems += [
        f"{site} is listed as unwrapped but has no consumer row" for site in sorted(unwrapped.keys() - consumers.keys())
    ]
    return problems


def _operation_problems(settled: SettledOperation, posts: Sequence[str], role: ModelRole) -> list[str]:
    """Return why a settled operation does not let another process route its person to the local AI setup."""
    what = f"{settled.definition_id} settled {settled.condition.value}"
    if settled.published is None:
        return [f"{what} with no detail or result a client in another process can read"]
    verdicts = published_verdicts(settled.published)
    if not verdicts:
        return [f"{what} and its published {type(settled.published).__name__} carries no verdict"]
    attempts = [_local_ai_gating_problems(verdict, posts, role) for verdict in verdicts]
    return [] if any(not attempt for attempt in attempts) else [f"{what}: {problem}" for problem in attempts[0]]


# -- Browser drivers ---------------------------------------------------------------

_FIXTURE_PROFILE = Profile(name="consumer-gating")


def _resolve(origin: str) -> Callable[..., object]:
    module, name = origin.rsplit(".", 1)
    resolved = getattr(importlib.import_module(module), name)
    assert callable(resolved), origin
    return resolved


def _drive_create_browser_session(settings: Settings) -> object:
    return asyncio.run(create_browser_session(settings, _FIXTURE_PROFILE))


def _drive_opened_browser_page(settings: Settings) -> object:
    async def run() -> None:
        async with (
            shared_playwright_runtime() as playwright,
            opened_browser_page(playwright, settings, _FIXTURE_PROFILE),
        ):
            return

    return asyncio.run(run())


def _drive_browser_launch(settings: Settings) -> object:
    async def run() -> object:
        async with shared_playwright_runtime() as playwright:
            session = BrowserSession(playwright=playwright, settings=settings, profile=_FIXTURE_PROFILE)
            try:
                return await session.create_context()
            finally:
                await session.close()

    return asyncio.run(run())


_FACTORY = "cadrumo.adapters.outbound.aeat.browser.factory"

#: Every function that starts a browser, with the driver that starts it through its own entry.
_BROWSER_STARTS: Mapping[str, Callable[[Settings], object]] = {
    f"{_FACTORY}.create_browser_session": _drive_create_browser_session,
    f"{_FACTORY}.opened_browser_page": _drive_opened_browser_page,
    "cadrumo.adapters.outbound.aeat.browser.session.BrowserSession._launch_chromium": _drive_browser_launch,
}


def _drive_live_preflight(settings: Settings) -> object:
    del settings
    with bundled_indexed_authority().operation() as operation:
        return _resolve("cadrumo.entrypoints.live_state_composition.preflight_filed_history_provider")(
            uuid4(), operation
        )


def _drive_identity_check_preflight(settings: Settings) -> object:
    with bundled_indexed_authority().operation() as operation:
        return _resolve("cadrumo.entrypoints.operation_composition._verify_live_preflight")(
            settings, uuid4(), operation
        )


def _drive_sign_in_readiness(settings: Settings) -> object:
    return _resolve(_BROWSER_READY)(settings, profile_name=_FIXTURE_PROFILE.name)


#: Every preflight handed to a browser operation, with the driver that calls it as its executor does.
_BROWSER_PREFLIGHTS: Mapping[str, Callable[[Settings], object]] = {
    "cadrumo.entrypoints.live_state_composition.preflight_filed_history_provider": _drive_live_preflight,
    "cadrumo.entrypoints.operation_composition._verify_live_preflight": _drive_identity_check_preflight,
    _BROWSER_READY: _drive_sign_in_readiness,
}


@contextmanager
def _empty_browsers_root(tmp_path: Path) -> Generator[Settings]:
    with override_settings(cadrumo_playwright_browsers_dir=tmp_path / "browsers-empty") as settings:
        yield settings


# -- The production gate -----------------------------------------------------------


@pytest.fixture(scope="module")
def production() -> dict[str, _Module]:
    return _load_modules(_PACKAGE_ROOT, _PACKAGE)


def test_every_local_ai_consumer_has_a_gated_row(production: dict[str, _Module]) -> None:
    sites, unit_roles, stale = _local_ai_discovery(production)

    problems = (
        stale + _site_problems(sites, _LOCAL_AI_CONSUMERS) + _role_problems(sites, unit_roles, _LOCAL_AI_CONSUMERS)
    )
    assert not problems, "\n".join(problems)


_LOCAL_AI_DRIVES = [
    pytest.param(role, driver, id=f"{site.rsplit('.', 1)[-1]}-{role.value}")
    for site, consumer in _LOCAL_AI_CONSUMERS.items()
    for role, driver in consumer.drivers.items()
]


@pytest.mark.parametrize(("role", "driver"), _LOCAL_AI_DRIVES)
def test_a_local_ai_consumer_refuses_with_its_setup_before_any_request(
    tmp_path: Path, role: ModelRole, driver: _Driver
) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET_ID),
        _runtime_holding_nothing(tmp_path) as runtime,
    ):
        outcome = _outcome(lambda: driver(runtime))
        problems = _local_ai_gating_problems(outcome, runtime.posts, role)

    assert not problems, "\n".join(problems)


def test_every_operation_that_wraps_a_consumer_has_an_operation_row() -> None:
    problems = _operation_coverage_problems(
        _LOCAL_AI_CONSUMERS, _UNWRAPPED_CONSUMERS, _OPERATION_ROWS, _registered_definition_ids()
    )

    assert not problems, "\n".join(problems)


_OPERATION_DRIVES = [
    pytest.param(definition_id, drive, id=f"{definition_id}-{drive.role.value}")
    for definition_id, drives in _OPERATION_ROWS.items()
    for drive in drives
]


@pytest.mark.parametrize(("definition_id", "drive"), _OPERATION_DRIVES)
def test_an_operation_that_wraps_a_consumer_settles_with_its_setup_verdict_readable(
    tmp_path: Path, operation: PinnedAuthorityOperation, definition_id: str, drive: _OperationDrive
) -> None:
    del operation
    with operation_runtime(tmp_path) as runtime:
        settled = drive.settle(runtime)
        problems = _operation_problems(settled, runtime.posts, drive.role)

    assert settled.definition_id == definition_id
    assert not problems, "\n".join(problems)


def _row_problems(discovered: Iterable[str], rows: Iterable[str], *, what: str) -> list[str]:
    """Return every discovered site without a row, and every row whose site is gone."""
    found, registered = set(discovered), set(rows)
    return [f"{site} {what} and has no row" for site in sorted(found - registered)] + [
        f"{site} has a row but no longer {what}" for site in sorted(registered - found)
    ]


def _browser_start_problems(sites: Mapping[str, str | None]) -> list[str]:
    ungated = [
        f"{site}: {problem}"
        for site, problem in sorted(sites.items())
        if problem is not None and site not in _EXEMPT_BROWSER_STARTS
    ]
    return ungated + _row_problems(sites, (*_BROWSER_STARTS, *_EXEMPT_BROWSER_STARTS), what="starts a browser")


def test_every_browser_start_checks_the_browser_first(production: dict[str, _Module]) -> None:
    problems = _browser_start_problems(_browser_start_sites(production))

    assert not problems, "\n".join(problems)


def test_every_browser_operation_is_handed_a_preflight_that_checks_the_browser_first(
    production: dict[str, _Module],
) -> None:
    gated, problems = _operation_browser_preflights(production)

    problems += _row_problems(gated, _BROWSER_PREFLIGHTS, what="gates a browser operation")
    assert not problems, "\n".join(problems)


_BROWSER_DRIVES = [
    pytest.param(driver, id=origin.rsplit(".", 1)[-1])
    for origin, driver in {**_BROWSER_STARTS, **_BROWSER_PREFLIGHTS}.items()
]


@pytest.mark.parametrize("driver", _BROWSER_DRIVES)
def test_a_browser_consumer_refuses_with_the_browser_setup(
    tmp_path: Path, driver: Callable[[Settings], object]
) -> None:
    with _empty_browsers_root(tmp_path) as settings:
        problems = _browser_refusal_problems(_outcome(lambda: driver(settings)))

    assert not problems, "\n".join(problems)


# -- Falsifiers: each check run against the defect it exists to catch ----------


def _write_tree(root: Path, files: Mapping[str, str]) -> dict[str, _Module]:
    for relative, source in files.items():
        path = root / _PACKAGE / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source), encoding="utf-8")
    return _load_modules(root / _PACKAGE, _PACKAGE)


def test_discovery_finds_a_new_local_ai_consumer_that_has_no_row(tmp_path: Path) -> None:
    modules = _write_tree(
        tmp_path,
        {
            "core/model_catalogue.py": "class ModelRole:\n    TEXT_EXTRACTION = 'text_extraction'\n",
            "adapters/outbound/llm/models.py": "class LLMRequest:\n    pass\n",
            "adapters/outbound/llm/client.py": """
                from .providers.base import ProviderRequest
                def dispatch():
                    return ProviderRequest()
            """,
            "adapters/outbound/llm/role_fitness.py": """
                from .providers.base import ProviderRequest
                def probe():
                    return ProviderRequest()
            """,
            "adapters/outbound/llm/fixture_reader.py": """
                from ....core.model_catalogue import ModelRole
                from .models import LLMRequest

                class FixtureReader:
                    def read(self) -> LLMRequest:
                        return LLMRequest(model_role=ModelRole.TEXT_EXTRACTION)

                def read_with_fixture_reader():
                    return FixtureReader().read()
            """,
            "entrypoints/fixture_composition.py": """
                from ..adapters.outbound.llm.fixture_reader import FixtureReader, read_with_fixture_reader

                def compose():
                    return read_with_fixture_reader()

                def annotated_only(reader: FixtureReader) -> None:
                    return None
            """,
        },
    )

    sites, unit_roles, stale = _local_ai_discovery(modules)

    reader = "cadrumo.adapters.outbound.llm.fixture_reader"
    assert stale == []
    assert sites == {
        "cadrumo.entrypoints.fixture_composition.compose": frozenset({f"{reader}.read_with_fixture_reader"})
    }
    assert unit_roles[f"{reader}.read_with_fixture_reader"] == {ModelRole.TEXT_EXTRACTION}
    assert _site_problems(sites, {}) == [
        "cadrumo.entrypoints.fixture_composition.compose reaches "
        f"['{reader}.read_with_fixture_reader'] and has no gated-consumer row"
    ]
    # A row that drives the site under another role misses the role the unit reads with.
    vision_only = {
        "cadrumo.entrypoints.fixture_composition.compose": _LocalAiConsumer(
            units=frozenset({f"{reader}.read_with_fixture_reader"}),
            drivers={ModelRole.VISION_TRANSCRIPTION: _drive_evidence_vision_read},
        )
    }
    role_problems = _role_problems(sites, unit_roles, vision_only)
    assert any("reads with text_extraction, undriven" in problem for problem in role_problems)
    assert any("no consumer is driven under column_role_mapping" in problem for problem in role_problems)
    # A row whose site is gone, and a row naming other units than the site reaches, are both stale.
    assert _site_problems({}, vision_only) == [
        "cadrumo.entrypoints.fixture_composition.compose has a row but no longer reaches a local AI reader"
    ]
    other_units = {
        "cadrumo.entrypoints.fixture_composition.compose": _LocalAiConsumer(
            units=frozenset({f"{reader}.FixtureReader"}), drivers=vision_only[next(iter(vision_only))].drivers
        )
    }
    assert _site_problems(sites, other_units) == [
        f"cadrumo.entrypoints.fixture_composition.compose reaches ['{reader}.read_with_fixture_reader'], "
        f"its row names ['{reader}.FixtureReader']"
    ]


def test_a_browser_start_or_preflight_without_a_row_and_a_stale_row_are_reported() -> None:
    sites: dict[str, str | None] = {site: None for site in _BROWSER_STARTS}
    sites |= {site: "starts unchecked on purpose" for site in _EXEMPT_BROWSER_STARTS}
    sites["cadrumo.fixture.new_start"] = None
    del sites[f"{_FACTORY}.opened_browser_page"]

    assert _browser_start_problems(sites) == [
        "cadrumo.fixture.new_start starts a browser and has no row",
        f"{_FACTORY}.opened_browser_page has a row but no longer starts a browser",
    ]
    preflight_problems = _row_problems(
        {"cadrumo.fixture.new_preflight"}, _BROWSER_PREFLIGHTS, what="gates a browser operation"
    )
    assert "cadrumo.fixture.new_preflight gates a browser operation and has no row" in preflight_problems
    assert len(preflight_problems) == 1 + len(_BROWSER_PREFLIGHTS)


def test_discovery_reports_an_exemption_that_no_longer_dispatches(tmp_path: Path) -> None:
    modules = _write_tree(tmp_path, {"adapters/outbound/llm/client.py": "def dispatch():\n    return None\n"})

    _sites, _roles, stale = _local_ai_discovery(modules)

    assert any(problem.startswith("cadrumo.adapters.outbound.llm.client is exempt") for problem in stale)


def test_a_consumer_that_skips_the_check_or_names_no_action_is_reported(tmp_path: Path) -> None:
    with _runtime_holding_nothing(tmp_path) as runtime:
        chat_url = runtime.settings.cadrumo_llm_ollama_chat_url

        def skips_the_check() -> object:
            return httpx.post(chat_url, json={"model": "any", "messages": []}, timeout=5.0)

        def names_no_action() -> object:
            raise InvoiceDraftReaderUnavailableError(
                RuntimeError("reader"),
                precondition_verdict=provisioning_no_recovery_verdict(
                    ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
                    facts={"role": ModelRole.TEXT_EXTRACTION.value, "role_model_selected": False},
                ),
            )

        skipped = _local_ai_gating_problems(_outcome(skips_the_check), runtime.posts, ModelRole.TEXT_EXTRACTION)
        runtime.posts.clear()
        actionless = _local_ai_gating_problems(_outcome(names_no_action), runtime.posts, ModelRole.TEXT_EXTRACTION)
        text_verdict = probe_local_reader(ModelRole.TEXT_EXTRACTION, runtime.settings).precondition_verdict
        wrong_role = _local_ai_gating_problems(text_verdict, runtime.posts, ModelRole.VISION_TRANSCRIPTION)
        correct = _local_ai_gating_problems(text_verdict, runtime.posts, ModelRole.TEXT_EXTRACTION)

    assert any(problem.startswith("sent 1 request(s) to the local AI") for problem in skipped), skipped
    assert any("carrying no verdict" in problem for problem in skipped), skipped
    assert actionless == [
        f"verdict {ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value} names no setup action"
    ]
    assert wrong_role == ["verdict speaks for role ['text_extraction'], not vision_transcription"]
    assert correct == [], "the real probe's refusal is what a gated consumer returns"


_FIXTURE_SESSION = """
    class BrowserSession:
        pass

    def require_browser_ready(settings, *, profile_name):
        return None
"""


def test_a_browser_start_without_an_earlier_check_is_reported(tmp_path: Path) -> None:
    modules = _write_tree(
        tmp_path,
        {
            "adapters/outbound/aeat/browser/session.py": _FIXTURE_SESSION,
            "adapters/outbound/aeat/browser/fixture_factory.py": """
                from .session import BrowserSession, require_browser_ready

                def ungated(settings):
                    return BrowserSession()

                def checked_too_late(settings):
                    session = BrowserSession()
                    require_browser_ready(settings, profile_name="fixture")
                    return session

                def gated(settings):
                    require_browser_ready(settings, profile_name="fixture")
                    return BrowserSession()

                async def launches(playwright):
                    return await playwright.chromium.launch()
            """,
        },
    )

    sites = _browser_start_sites(modules)

    factory = "cadrumo.adapters.outbound.aeat.browser.fixture_factory"
    assert sites[f"{factory}.gated"] is None
    assert sites[f"{factory}.ungated"] == "line 5 starts a browser and nothing checks it is set up"
    assert sites[f"{factory}.checked_too_late"] == "line 8 starts a browser before the check on line 9"
    assert sites[f"{factory}.launches"] == "line 17 starts a browser and nothing checks it is set up"


def test_a_browser_operation_without_a_browser_first_preflight_is_reported(tmp_path: Path) -> None:
    modules = _write_tree(
        tmp_path,
        {
            "adapters/outbound/aeat/browser/session.py": _FIXTURE_SESSION,
            "adapters/outbound/aeat/browser/factory.py": "class BrowserRuntimeResourceScope:\n    pass\n",
            "entrypoints/fixture_operations.py": """
                from functools import partial

                from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope
                from ..adapters.outbound.aeat.browser.session import require_browser_ready

                def credentials_first(profile_id, operation):
                    load_credentials(profile_id)
                    require_browser_ready(None, profile_name=str(profile_id))

                def browser_first(profile_id, operation):
                    require_browser_ready(None, profile_name=str(profile_id))

                def compose():
                    build_capture_definition(BrowserRuntimeResourceScope, credentials_first)
                    build_capture_definition(BrowserRuntimeResourceScope)
                    build_capture_definition(BrowserRuntimeResourceScope, browser_first)
                    build_capture_definitions(BrowserRuntimeResourceScope, provider_preflight=partial(browser_first))
                    build_local_definition(credentials_first)
            """,
        },
    )

    gated, problems = _operation_browser_preflights(modules)

    assert gated == {"cadrumo.entrypoints.fixture_operations.browser_first"}
    assert problems == [
        "cadrumo.entrypoints.fixture_operations:15 build_capture_definition() is handed a browser and no "
        "preflight that checks it first",
        "cadrumo.entrypoints.fixture_operations:16 build_capture_definition() is handed a browser and no "
        "preflight that checks it first",
    ]


def test_a_browser_consumer_that_does_not_refuse_or_names_no_action_is_reported(tmp_path: Path) -> None:
    def names_no_action() -> object:
        raise BrowserNotUsableError(
            "fixture",
            translated_message="adapters.browser.errors.not_usable",
            precondition_verdict=browser_no_action_verdict(
                condition=BrowserPreconditionCondition.CONTEXT_CREATABLE,
                facts={"browser_context_creatable": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )

    with _empty_browsers_root(tmp_path) as settings:
        real = _browser_refusal_problems(_outcome(lambda: _drive_sign_in_readiness(settings)))

    assert _browser_refusal_problems(_outcome(lambda: None)) == [
        "ended in NoneType, not a refusal for a browser that is not set up"
    ]
    assert _browser_refusal_problems(_outcome(names_no_action)) == ["the refusal names no setup action"]
    assert real == [], "the real readiness check's refusal is what a gated consumer raises"


def test_an_operation_without_a_row_a_stale_row_and_a_silent_site_are_reported() -> None:
    unit = frozenset({f"{_LLM}.fixture.Reader"})
    consumers = {
        "cadrumo.fixture.wrapped": _LocalAiConsumer(
            units=unit, drivers={}, operations=frozenset({"fixture.read", "fixture.unregistered"})
        ),
        "cadrumo.fixture.silent": _LocalAiConsumer(units=unit, drivers={}),
        "cadrumo.fixture.contradictory": _LocalAiConsumer(
            units=unit, drivers={}, operations=frozenset({"fixture.read"})
        ),
    }
    unwrapped = {"cadrumo.fixture.contradictory": "fixture", "cadrumo.fixture.gone": "fixture"}
    rows = {"fixture.read": (), "fixture.stale": ()}

    problems = _operation_coverage_problems(consumers, unwrapped, rows, frozenset({"fixture.read", "fixture.stale"}))

    assert problems == [
        "fixture.unregistered wraps a consumer and has no operation row",
        "fixture.stale has a row but no consumer row names it",
        "fixture.unregistered is named but not a registered operation",
        "cadrumo.fixture.contradictory names operations and is also listed as unwrapped",
        "cadrumo.fixture.silent names no operation and no reason that none reaches it",
        "cadrumo.fixture.gone is listed as unwrapped but has no consumer row",
    ]


class _FixtureReadRequest(CredentialFreeOperationRequest):
    """A fixture operation's request: only the profile it reads for."""

    profile_id: UUID


class _FixtureReadResult(BaseModel):
    """A fixture operation's result: whether the page was read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    read: bool


def _read_one_statement_page() -> None:
    """Ask the real statement reader for one page; with no model it refuses with the setup verdict."""
    LocalStatementReader().propose_page(_transcription("05.03.2026 Cafeteria -4,50 EUR"))


class _FixtureReadExecutor:
    """Read one page through a gated consumer, swallowing its refusal into the result or letting it stop the run."""

    def __init__(self, *, swallow: bool) -> None:
        self._swallow = swallow

    async def execute(self, request: OperationRequest[_FixtureReadRequest], context: OperationExecutorContext) -> str:
        await context.events.phase(request.definition_id)
        try:
            await asyncio.to_thread(_read_one_statement_page)
        except LedgerImportReaderUnavailableError:
            if not self._swallow:
                await context.events.effect(OperationEffect.NONE)
                raise
            read = False
        else:
            read = True
        reference = await context.operands.put(_FixtureReadResult(read=read), written_at=datetime.now(UTC))
        await context.events.effect(OperationEffect.NONE)
        return reference


def _fixture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    assert isinstance(request.payload, _FixtureReadRequest)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def _settle_fixture_read(tmp_path: Path, *, swallow: bool, publish: bool) -> tuple[SettledOperation, list[str]]:
    """Settle the fixture operation through the real supervisor and read it back as another process does."""
    definition_id = "ledger.fixture-read"
    definition = build_single_phase_definition(
        definition_id=definition_id,
        request_type=_FixtureReadRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=_FixtureReadResult,
        executor_type=_FixtureReadExecutor,
        build=lambda: _FixtureReadExecutor(swallow=swallow),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        public_error_detail=publish,
    )
    registration = OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition, public_result_type=_FixtureReadResult, access_resolver=_fixture_access
    )
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    posts: list[str] = []
    with (
        isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET_ID) as profile,
        runtime_holding_nothing(posts),
        bundled_indexed_authority().operation() as operation,
    ):
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = OperationSupervisor(
            authority_operation=operation,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=2),
            cleanup_timeout=timedelta(minutes=1),
            response_token_factory=lambda: "3" * 64,
        )
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def settle() -> SettledOperation:
            operation_id = await supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(_BUCKET_ID),
                    payload=_FixtureReadRequest(profile_id=UUID(_BUCKET_ID)),
                ),
                operation_id="4" * 64,
            )
            terminal = await run_to_settlement(supervisor, operation_id)
            receipt = terminal.terminal_receipt
            assert receipt is not None
            return await read_published(
                service.resolve,
                registry,
                definition_id=definition_id,
                operation_id=operation_id,
                condition=receipt.condition,
                revision=terminal.revision,
                result_type=_FixtureReadResult,
            )

        settled = asyncio.run(settle())
    return settled, posts


def test_an_operation_that_swallows_or_withholds_a_consumer_refusal_is_reported(tmp_path: Path) -> None:
    swallowed, swallowed_posts = _settle_fixture_read(tmp_path / "swallowed", swallow=True, publish=True)
    withheld, withheld_posts = _settle_fixture_read(tmp_path / "withheld", swallow=False, publish=False)
    published, published_posts = _settle_fixture_read(tmp_path / "published", swallow=False, publish=True)

    assert _operation_problems(swallowed, swallowed_posts, ModelRole.TEXT_EXTRACTION) == [
        "ledger.fixture-read settled succeeded and its published _FixtureReadResult carries no verdict"
    ]
    assert _operation_problems(withheld, withheld_posts, ModelRole.TEXT_EXTRACTION) == [
        "ledger.fixture-read settled refused with no detail or result a client in another process can read"
    ]
    assert _operation_problems(published, published_posts, ModelRole.TEXT_EXTRACTION) == [], (
        "an operation that lets the real consumer's refusal stop it, and publishes it, is what a gated row settles as"
    )
    assert _operation_problems(published, published_posts, ModelRole.VISION_TRANSCRIPTION) == [
        "ledger.fixture-read settled refused: verdict speaks for role ['text_extraction'], not vision_transcription"
    ]

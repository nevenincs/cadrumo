"""How the terminal interface and MCP reach the work each command does.

A command reaches the other frontends in one of three ways. It submits a
registered operation, which every frontend can submit. It sends a runtime
request or an installation act, which the terminal interface can send. Or it
does its work in the command-line process, and the same application function
is served to the other frontends by a registered operation or an ``authority``
query. The first two are read from the handlers' source and recorded in the
command table. The third cannot be read from a handler that sends nothing, so
it is declared here, one row for each such command.

Some commands are the person's own act: they sign in or out, lock, administer
sessions or keys, take a secret, or do installation work that belongs to no
single profile. An agent works only inside the one profile the person signed
in to, so MCP serves none of them, and the terminal interface reaches them
through the installation acts and session requests the runtime serves. They
are declared here too, each with the reason it is the person's.

A command that also submits or sends has a row here when one of its modes does
its work in process: the row names what serves that mode, and the command is
read as reaching the other frontends in both ways.

A row also says what holds the command to its counterpart: the test that runs
both and compares the command's output with the counterpart's, or that no such
test exists. The declarations are checked against the live command tree, the
operation registry, the table of installation acts, the harness's tools and the
test files, in both directions, by the test beside this module. The agent's
command reference is rendered from them.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final

from ....application.operations.person_acts import PERSON_RUNTIME_REQUESTS, operation_is_persons_act
from ....application.operations.registry import OperationRegistry
from ....application.operator_surface.command_operations import CommandOperations
from ....application.runtime.installation_requests import InstallationAct
from .command_operation_derivation import PROFILE_ADMISSION_ACTION, CliPath

EXECUTE_TOOL: Final = "execute"
AUTHORITY_TOOL: Final = "authority"


@dataclass(frozen=True, slots=True)
class ToolRoute:
    """One MCP tool and what it is given to do one piece of work.

    ``selector`` is the operation an ``execute`` runs or the query an
    ``authority`` call names. A tool that does one thing has none.
    """

    tool: str
    selector: str | None = None


@dataclass(frozen=True, slots=True)
class Unproven:
    """The statement that no test holds a command's output to its counterpart's, and why."""

    reason: str


@dataclass(frozen=True, slots=True)
class Counterpart:
    """What serves one command's work to the other frontends, and what holds the two to one result.

    ``proof`` is a test the command's output is compared with the routes'
    output in: a path relative to the repository, then ``::`` and the name of
    one test function in that file. A pair no test compares says so with
    ``Unproven``, so the absence is data and not a silence.
    """

    routes: tuple[ToolRoute, ...]
    proof: str | Unproven


_NOT_COMPARED: Final = Unproven("no test runs the command and its counterpart and compares what they return")

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[5]
"""The checkout the declared proofs are spelled relative to."""


def _operation(proof: str | Unproven, *definition_ids: str) -> Counterpart:
    return Counterpart(tuple(ToolRoute(EXECUTE_TOOL, definition_id) for definition_id in definition_ids), proof)


def _query(proof: str | Unproven, *queries: str) -> Counterpart:
    return Counterpart(tuple(ToolRoute(AUTHORITY_TOOL, query) for query in queries), proof)


_RUNTIME_TESTS: Final = "src/cadrumo/entrypoints/runtime/tests"
_ENTRYPOINT_TESTS: Final = "src/cadrumo/entrypoints/tests"
_STORAGE_PROOF: Final = (
    f"{_RUNTIME_TESTS}/test_installation_storage.py::test_each_storage_command_prints_the_document_its_act_replies_with"
)
_REFERENCE_PROOF: Final = (
    f"{_ENTRYPOINT_TESTS}/test_reference_catalogue_parity.py::test_tool_report_equals_the_command_line_result"
)
_REPAIR_OPERATIONS: Final = f"{_ENTRYPOINT_TESTS}/test_diagnostics_repair_command_parity.py"
_PROVISION_PROOF: Final = (
    "src/cadrumo/entrypoints/cli/tests/test_provision_operation_parity.py"
    "::test_a_leaf_and_its_operation_return_the_same_result"
)
_PROVISION: Final = _operation(_PROVISION_PROOF, "local-reader.provision")

IN_PROCESS_COMMAND_COUNTERPARTS: Final[Mapping[CliPath, Counterpart]] = MappingProxyType(
    {
        # With a session open in the command-line process, the bare invocation prints the overview.
        (): _operation(_NOT_COMPARED, "overview.status"),
        ("app", "ledger", "categories"): _query(_REFERENCE_PROOF, "categories"),
        ("app", "live", "portals", "list"): _query(_REFERENCE_PROOF, "portals"),
        ("app", "live", "portals", "view"): _query(_REFERENCE_PROOF, "portal"),
        ("app", "modelo", "casilla"): _query(_REFERENCE_PROOF, "casilla"),
        ("app", "modelo", "casillas"): _query(_REFERENCE_PROOF, "casillas"),
        ("app", "modelo", "describe"): _query(_REFERENCE_PROOF, "describe"),
        ("app", "modelo", "formulas"): _query(_REFERENCE_PROOF, "formulas"),
        ("app", "modelo", "list"): _query(_REFERENCE_PROOF, "modelos"),
        ("app", "modelo", "support-matrix"): _query(_REFERENCE_PROOF, "support"),
        # ``--document-only`` verifies the file's own signature and submits nothing.
        ("config", "auth", "apoderado", "scopes", "list"): _query(_REFERENCE_PROOF, "apoderado_scopes"),
        ("config", "auth", "providers"): _query(_REFERENCE_PROOF, "auth_providers"),
        # The command parses the certificate itself before it submits the facts it read.
        ("config", "profile", "censo", "import"): _operation(
            f"{_ENTRYPOINT_TESTS}/test_censal_certificate_file_operation.py"
            "::test_the_shipped_parser_refuses_the_file_for_a_direct_client_as_it_does_for_the_command",
            "user-profile.censo-certificate-import",
        ),
        ("config", "provision", "browser"): _operation(_PROVISION_PROOF, "browser-runtime.provision"),
        ("config", "provision", "install"): _PROVISION,
        ("config", "provision", "load"): _PROVISION,
        ("config", "provision", "probe"): _operation(_PROVISION_PROOF, "local-reader.status"),
        ("config", "provision", "pull"): _PROVISION,
        ("config", "provision", "remove"): _PROVISION,
        ("config", "provision", "report"): _operation(_PROVISION_PROOF, "local-reader.report"),
        ("config", "provision", "setup"): _PROVISION,
        ("config", "provision", "start"): _PROVISION,
        ("config", "provision", "status"): _operation(_PROVISION_PROOF, "local-reader.status"),
        ("config", "provision", "verify"): _PROVISION,
        ("config", "repair", "connectivity"): _operation(
            f"{_REPAIR_OPERATIONS}::test_connectivity_prints_what_the_probe_operation_returns_for_the_same_observation",
            "diagnostics.connectivity.probe",
        ),
        ("config", "repair", "integrity", "objects"): _operation(
            f"{_REPAIR_OPERATIONS}::test_integrity_objects_prints_what_the_check_operation_returns",
            "diagnostics.secure-objects.check",
        ),
        ("config", "repair", "quarantine"): _operation(
            f"{_REPAIR_OPERATIONS}::test_quarantine_prints_what_the_quarantine_operation_returns",
            "diagnostics.secure-objects.quarantine",
        ),
        ("config", "repair", "reset-progress"): _operation(
            f"{_REPAIR_OPERATIONS}::test_reset_progress_prints_what_the_reset_operation_returns",
            "diagnostics.workflow-progress.reset",
        ),
    }
)
"""Each command that works in the command-line process, and what serves that work to the other frontends."""


@dataclass(frozen=True, slots=True)
class PersonAct:
    """A command whose work is the person's own act, which MCP does not serve.

    ``acts`` and ``operations`` name the installation acts and registered
    operations that serve the command's in-process work to the terminal
    interface; a command that sends its requests or submits its operations
    itself names none. ``proof`` is the test that compares the command's
    output with the counterpart's, as for a counterpart, or the statement
    that no test does.
    """

    reason: str
    acts: tuple[InstallationAct, ...] = ()
    operations: tuple[str, ...] = ()
    proof: str | Unproven = Unproven("no test runs the command and the terminal interface's act and compares them")


_SIGN_IN: Final = "it signs the person in or out, locks a session or reads the sign-in, which only the person does"
_SESSIONS: Final = "it lists or denies the profile's sessions and keys, which is the person's administration of access"
_KEYS: Final = "it requests, approves, declines, changes or lists an automation key, which only the person issues"
_TYPED_BY_THE_PERSON: Final = "it takes a password or another secret, which only the person types"
_INSTALLATION: Final = (
    "it does installation work that belongs to no single profile, outside the profile an agent works in"
)


def _installation(proof: str | Unproven, *acts: InstallationAct) -> PersonAct:
    return PersonAct(_INSTALLATION, acts=acts, proof=proof)


PERSON_ACT_COMMANDS: Final[Mapping[CliPath, PersonAct]] = MappingProxyType(
    {
        ("app", "modelo", "review-package", "verify"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_artefacts.py"
            "::test_a_genuine_package_verifies_clean_and_the_act_and_the_command_give_one_document",
            InstallationAct.REVIEW_PACKAGE_VERIFY,
        ),
        ("app", "modelo", "review-package", "verify-receipt"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_artefacts.py"
            "::test_a_receipt_holds_only_for_both_keys_and_the_package_it_was_made_for",
            InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT,
        ),
        ("app", "modelo", "review-package", "verify-signature"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_artefacts.py"
            "::test_a_signature_holds_for_its_signer_and_fails_for_any_other_key_or_a_changed_package",
            InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE,
        ),
        ("app", "modelo", "work", "report-verify"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_artefacts.py"
            "::test_a_summary_is_checked_by_its_own_bytes_and_the_act_and_the_command_give_one_document",
            InstallationAct.REPORT_VERIFY_DOCUMENT,
        ),
        ("config", "profile", "archive", "import"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_profiles.py"
            "::test_an_import_republishes_the_prepared_source_and_answers_what_the_command_prints",
            InstallationAct.ARCHIVE_IMPORT_PREPARE,
            InstallationAct.ARCHIVE_IMPORT,
        ),
        ("config", "profile", "archive", "inspect"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_profiles.py"
            "::test_the_inspect_act_reports_the_header_the_command_prints_and_refuses_what_is_no_archive",
            InstallationAct.ARCHIVE_INSPECT,
        ),
        ("config", "profile", "list"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_profiles.py"
            "::test_the_listing_act_answers_every_frontend_with_what_the_command_prints",
            InstallationAct.PROFILE_LIST,
        ),
        ("config", "profile", "recovery", "enable"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_profiles.py"
            "::test_enrolment_hands_out_a_code_that_resets_the_passphrase_and_answers_what_the_command_prints",
            InstallationAct.RECOVERY_ENROLL,
        ),
        ("config", "repair"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_repair.py"
            "::test_the_report_act_replies_with_the_diagnosis_the_command_prints",
            InstallationAct.REPAIR_REPORT,
        ),
        ("config", "repair", "logs"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_repair.py::test_the_logs_act_replies_with_the_tail_the_command_prints",
            InstallationAct.REPAIR_LOGS,
        ),
        ("config", "repair", "profile"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_repair.py"
            "::test_the_profile_act_on_a_healthy_root_inspects_the_named_record_and_clears_nothing",
            InstallationAct.REPAIR_PROFILE,
        ),
        ("config", "reset", "status"): _installation(
            f"{_RUNTIME_TESTS}/test_installation_reset.py"
            "::test_each_reset_act_replies_with_the_document_its_command_prints",
            InstallationAct.RESET_STATUS,
        ),
        ("config", "storage", "check"): _installation(_STORAGE_PROOF, InstallationAct.STORAGE_CHECK),
        ("config", "storage", "init"): _installation(_STORAGE_PROOF, InstallationAct.STORAGE_INIT),
        ("config", "storage", "list"): _installation(_STORAGE_PROOF, InstallationAct.STORAGE_INVENTORY),
        ("config", "storage", "reclaim"): _installation(_STORAGE_PROOF, InstallationAct.STORAGE_RECLAIM),
        ("config", "storage", "view"): _installation(_STORAGE_PROOF, InstallationAct.STORAGE_INVENTORY),
        ("config", "auth", "apoderado", "configure"): PersonAct(_TYPED_BY_THE_PERSON),
        ("config", "auth", "certificate", "secret", "set"): PersonAct(_TYPED_BY_THE_PERSON),
        ("config", "login"): PersonAct(_SIGN_IN),
        ("config", "logout"): PersonAct(_SIGN_IN),
        ("config", "passphrase", "change"): PersonAct(_TYPED_BY_THE_PERSON),
        ("config", "passphrase", "reset"): PersonAct(_TYPED_BY_THE_PERSON),
        ("config", "profile", "automation", "approve"): PersonAct(_KEYS),
        ("config", "profile", "automation", "change"): PersonAct(_KEYS),
        ("config", "profile", "automation", "create"): PersonAct(_KEYS),
        ("config", "profile", "automation", "decline"): PersonAct(_KEYS),
        ("config", "profile", "automation", "deny"): PersonAct(_SESSIONS),
        ("config", "profile", "automation", "inspect"): PersonAct(_KEYS),
        ("config", "profile", "automation", "list"): PersonAct(_KEYS),
        ("config", "profile", "delete"): PersonAct(_INSTALLATION),
        ("config", "profile", "lock"): PersonAct(_SIGN_IN),
        ("config", "profile", "recovery", "disable"): PersonAct(
            _TYPED_BY_THE_PERSON,
            operations=("user-profile.recovery.revoke",),
            proof=f"{_ENTRYPOINT_TESTS}/test_recovery_revoke_operation.py"
            "::test_revocation_proves_the_passphrase_removes_the_wrapper_and_prints_what_the_command_prints",
        ),
        ("config", "profile", "resume"): PersonAct(_TYPED_BY_THE_PERSON),
        ("config", "profile", "sessions"): PersonAct(_SESSIONS),
        ("config", "reset", "resume"): PersonAct(_INSTALLATION),
        ("config", "reset", "start"): PersonAct(_INSTALLATION),
        ("config", "sign-in-status"): PersonAct(_SIGN_IN),
    }
)
"""Each command whose work is the person's own act, with why; MCP serves none of them.

An agent works only inside the one profile the person signed in to or issued a
key for, and never authenticates, administers access or handles a secret. The
terminal interface reaches these commands' work through the installation acts
and session requests the runtime serves to it.
"""

_PRINTS_HELP: Final = "invoked bare, it prints the help of its group, which every frontend holds as text of its own"

COMMANDS_WITH_NO_WORK_TO_SHARE: Final[Mapping[CliPath, str]] = MappingProxyType(
    {
        ("app",): _PRINTS_HELP,
        ("app", "diagnostics"): _PRINTS_HELP,
        ("app", "tui"): "it starts the terminal interface itself",
        ("config",): _PRINTS_HELP,
    }
)
"""Each command that neither reaches the runtime nor does work another frontend could ask for, with the reason."""

_TYPED_READ: Final = (
    "a typed read of records the command line reads through the operation named beside it; "
    "the terminal interface and MCP submit it directly"
)
_FORM_WORKBENCH: Final = (
    "the form workbench, which the terminal interface and MCP drive one request at a time; "
    "the command line reads and edits a form through its work commands"
)
_KEY_PROPOSAL: Final = (
    "a proposal about an automation key, which the command line makes through the runtime's enrollment "
    "requests that its automation commands send; it is the person's act and no agent's"
)


@dataclass(frozen=True, slots=True)
class OperationWithoutCommand:
    """A registered operation no command submits and no command's in-process work is served by.

    ``command_line_operation`` names the operation through which the command
    line reaches the same records, where there is one. It is held to the
    registry and to the command table: a command submits it.
    """

    reason: str
    command_line_operation: str | None = None


OPERATIONS_WITHOUT_A_COMMAND: Final[Mapping[str, OperationWithoutCommand]] = MappingProxyType(
    {
        "ledger.evidence.query": OperationWithoutCommand(_TYPED_READ, "ledger.evidence.list"),
        "ledger.evidence.reader-readiness": OperationWithoutCommand(
            "the evidence screen's own readiness read; the command line reads the reader's state in process "
            "and the other frontends also through local-reader.status"
        ),
        "ledger.evidence.review.summary": OperationWithoutCommand(_TYPED_READ, "ledger.evidence.review.list"),
        "ledger.history.typed": OperationWithoutCommand(_TYPED_READ, "ledger.history"),
        "live.borrador.100.query": OperationWithoutCommand(_TYPED_READ, "live.borrador.100.read"),
        "modelo.036.query": OperationWithoutCommand(_TYPED_READ, "modelo.036.read"),
        "modelo.audit.query": OperationWithoutCommand(_TYPED_READ, "modelo.audit.read"),
        "modelo.bindings.resolve.typed": OperationWithoutCommand(_TYPED_READ, "modelo.bindings.resolve"),
        "modelo.edit.apply": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.apply_prerequisite": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.preflight": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.renew": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.history.timeline": OperationWithoutCommand(_TYPED_READ, "modelo.history"),
        "modelo.readiness.summary": OperationWithoutCommand(_TYPED_READ, "modelo.readiness"),
        "modelo.work.casilla_help": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.work.form": OperationWithoutCommand(_FORM_WORKBENCH),
        "profile.history.timeline": OperationWithoutCommand(_TYPED_READ, "profile.history"),
        "user-profile.automation-renew": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-request": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-rotate": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-scope": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.bundle-export": OperationWithoutCommand(
            "exports the profile's records as one portable bundle; no command asks for that bundle"
        ),
        "workbench.generation": OperationWithoutCommand(
            "the generation the terminal interface's workbench reads to know its projections are current"
        ),
    }
)
"""Every registered operation that only the terminal interface and MCP submit, with the reason."""

INSTALLATION_ACTS_WITHOUT_A_COMMAND: Final[Mapping[InstallationAct, str]] = MappingProxyType(
    dict[InstallationAct, str]()
)
"""Every installation act no command sends and no command's in-process work is served by, with the reason."""

OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER: Final[Mapping[str, str]] = MappingProxyType(
    {
        "export.google-sheets": (
            "production composes it with no access resolver, so the runtime refuses every submission of it "
            "as unavailable, whichever frontend submits it, the command line's spreadsheet push included"
        ),
    }
)
"""Every operation a command submits or serves that the runtime cannot admit, with the reason.

An operation with no access resolver is refused at admission for every
frontend alike, so it is equal on all three and is not a parity difference. It
is declared here so that it stays visible, and so that another operation
reaching the same state fails instead of passing unnoticed.
"""


class CommandReach(StrEnum):
    """One way a command's work reaches the terminal interface and MCP."""

    SUBMITS_OPERATION = "submits a registered operation"
    SENDS_RUNTIME_REQUEST = "sends a runtime request or an installation act"
    WORKS_IN_PROCESS = "works in process, with a declared counterpart"
    PERSON_ACT = "is the person's own act, which MCP does not serve"
    NO_WORK_TO_SHARE = "has no work to share"
    UNREACHED = "does work no other frontend can ask for"


_INSTALLATION_ACTIONS: Final = frozenset(act.value for act in InstallationAct)

PERSON_REQUESTS: Final = PERSON_RUNTIME_REQUESTS | _INSTALLATION_ACTIONS
"""Every request of the runtime's own door that is the person's act: the session and key requests and every act."""


def requests_beyond_admission(row: CommandOperations) -> frozenset[str]:
    """Name the runtime requests a command sends besides the one that admits it to a profile."""
    return frozenset(row.runtime_requests) - {PROFILE_ADMISSION_ACTION}


def command_reaches(
    row: CommandOperations,
    *,
    in_process: Mapping[CliPath, Counterpart] = IN_PROCESS_COMMAND_COUNTERPARTS,
    no_work: Mapping[CliPath, str] = COMMANDS_WITH_NO_WORK_TO_SHARE,
    person: Mapping[CliPath, PersonAct] = PERSON_ACT_COMMANDS,
) -> tuple[CommandReach, ...]:
    """Say every way one recorded command reaches the other frontends.

    A command is read in each way that applies, so a command that submits an
    operation in one mode and works in process in another is held to both. A
    command admitted to a profile has sent nothing about its work yet, so the
    admission request alone does not count as reaching the runtime. A command
    that reaches the other frontends in no way is ``UNREACHED``.
    """
    reaches: list[CommandReach] = []
    if row.operation_ids:
        reaches.append(CommandReach.SUBMITS_OPERATION)
    if requests_beyond_admission(row):
        reaches.append(CommandReach.SENDS_RUNTIME_REQUEST)
    served = in_process.get(row.cli_path)
    if served is not None and served.routes:
        reaches.append(CommandReach.WORKS_IN_PROCESS)
    if row.cli_path in no_work:
        reaches.append(CommandReach.NO_WORK_TO_SHARE)
    if row.cli_path in person:
        reaches.append(CommandReach.PERSON_ACT)
    return tuple(reaches) or (CommandReach.UNREACHED,)


def reach_of_every_command(rows: Iterable[CommandOperations]) -> dict[CommandReach, tuple[CliPath, ...]]:
    """Group every recorded command under each way it reaches the other frontends, keeping the empty groups."""
    grouped: dict[CommandReach, list[CliPath]] = {reach: [] for reach in CommandReach}
    for row in rows:
        for reach in command_reaches(row):
            grouped[reach].append(row.cli_path)
    return {reach: tuple(sorted(paths)) for reach, paths in grouped.items()}


def proof_finding(proof: str, *, root: Path = REPOSITORY_ROOT) -> str | None:
    """Say why a declared proof names no test, when it does not.

    A proof is a path relative to ``root``, ``::`` and the name of one test
    function defined at the top of that file.
    """
    path, separator, name = proof.partition("::")
    if not separator or not name or "[" in name or "::" in name:
        return "is not a file path, then '::' and the name of one test function"
    file = root / path
    if not file.is_file():
        return "names a file that does not exist"
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return "names a file that cannot be read as Python"
    tests = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
    }
    return None if name in tests else "names a test the file does not define"


def operations_without_an_access_resolver(registry: OperationRegistry, operation_ids: Iterable[str]) -> frozenset[str]:
    """Name the registered operations among ``operation_ids`` that the runtime cannot admit for want of a resolver."""
    return frozenset(
        operation_id
        for operation_id in operation_ids
        if registry.lookup_public_registration(operation_id).access_resolver is None
    )


def persons_operations(registry: OperationRegistry, operation_ids: Iterable[str]) -> frozenset[str]:
    """Name the registered operations among ``operation_ids`` that are the person's own act and not an agent's."""
    return frozenset(
        operation_id
        for operation_id in operation_ids
        if operation_is_persons_act(
            operation_id,
            ephemeral_secret_required=registry.lookup_public_contract(operation_id).ephemeral_secret_required,
        )
    )


def unproven_pairs() -> tuple[tuple[CliPath, Unproven], ...]:
    """List every declared pair that no test holds to one result, in command order."""
    declared = (*IN_PROCESS_COMMAND_COUNTERPARTS.items(), *PERSON_ACT_COMMANDS.items())
    return tuple(
        sorted(
            ((cli_path, pair.proof) for cli_path, pair in declared if isinstance(pair.proof, Unproven)),
            key=lambda entry: entry[0],
        )
    )


def other_frontend_routes(row: CommandOperations) -> tuple[ToolRoute, ...]:
    """Name every MCP tool route to a command's work besides executing the operations it submits.

    These are what serves the work it does in process, each once, in the order
    they are declared, which is the order a client calls them in. A command
    that is the person's own act has none: MCP serves no such work.
    """
    if row.cli_path in PERSON_ACT_COMMANDS:
        return ()
    in_process = IN_PROCESS_COMMAND_COUNTERPARTS.get(row.cli_path)
    return tuple(dict.fromkeys(() if in_process is None else in_process.routes))


__all__ = [
    "AUTHORITY_TOOL",
    "COMMANDS_WITH_NO_WORK_TO_SHARE",
    "EXECUTE_TOOL",
    "INSTALLATION_ACTS_WITHOUT_A_COMMAND",
    "IN_PROCESS_COMMAND_COUNTERPARTS",
    "OPERATIONS_WITHOUT_AN_ACCESS_RESOLVER",
    "OPERATIONS_WITHOUT_A_COMMAND",
    "PERSON_ACT_COMMANDS",
    "PERSON_REQUESTS",
    "REPOSITORY_ROOT",
    "CommandReach",
    "Counterpart",
    "OperationWithoutCommand",
    "PersonAct",
    "ToolRoute",
    "Unproven",
    "command_reaches",
    "operations_without_an_access_resolver",
    "other_frontend_routes",
    "persons_operations",
    "proof_finding",
    "reach_of_every_command",
    "requests_beyond_admission",
    "unproven_pairs",
]

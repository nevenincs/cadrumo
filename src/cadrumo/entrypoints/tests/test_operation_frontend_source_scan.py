"""No application or entrypoint code decides anything by comparing the submitting frontend.

Every registered operation is open to every frontend alike, and the same
request gets the same decision and the same effect on each. A comparison of a frontend with one named member is how
code would tell them apart, so this scan reads every production source under
the application and entrypoint tiers and fails on each such comparison, on
each ``match`` over a named frontend, and on each call of a function that
returns such a comparison.

The few places where naming a frontend is not a refusal are listed below,
each with its reason. A listed place that no longer compares a frontend fails
here too, so the list only shrinks.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

import pytest

from ...application.operations.registry import OperationFrontendProjection
from .test_operation_catalogue import _production_sources, _tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ENUM = OperationFrontendProjection.__name__
_MEMBERS = frozenset(member.name for member in OperationFrontendProjection)
_SCANNED_TIERS = ("src/cadrumo/application/", "src/cadrumo/entrypoints/")

_ALLOWED_FUNCTIONS: Mapping[tuple[str, str], str] = {
    (
        "src/cadrumo/application/operations/person_acts.py",
        "is_persons_frontend",
    ): "the one predicate naming the person's frontends, on which alone a person's act is taken",
    (
        "src/cadrumo/application/operations/execution_actor.py",
        "execution_actor_label",
    ): "derives the actor an agent's execution records from its session; it refuses nothing",
    (
        "src/cadrumo/application/operations/execution_actor.py",
        "<module>",
    ): "names the label prefix of each agent frontend, so a stored label is read as an agent's; it refuses nothing",
    (
        "src/cadrumo/application/ledger/invoice_evidence_extract_operation.py",
        "_resolve_extract_access",
    ): "the acknowledgement of an off-host read is the person's consent to send the document off this machine",
    (
        "src/cadrumo/entrypoints/runtime/profile_connection_admission.py",
        "ProfileConnectionAdmissionMixin._prepare",
    ): "the agent host is admitted only by resuming the person's stored sign-in, never by a key",
    (
        "src/cadrumo/entrypoints/runtime/profile_connection_attendance.py",
        "ProfileConnectionAttendanceMixin._attendance_ask",
    ): "attendance is the door of an MCP agent that follows the person's live sign-in; no other frontend asks",
    (
        "src/cadrumo/application/user_profile/operation_access_policy.py",
        "_surface_refuses",
    ): "a surface is the narrowing a person chose for one MCP connection, so a lease naming one is an MCP lease",
    (
        "src/cadrumo/entrypoints/runtime/profile_connection_admission.py",
        "ProfileConnectionAdmissionMixin._login_surface",
    ): "only an MCP connection is started on a named surface, so no other login may name one",
    (
        "src/cadrumo/entrypoints/runtime/operation_authority.py",
        "ProfileWorkerOperationAuthority.execution_caller",
    ): "keeps an execution attributed to the agent session that submitted it when another session re-enters it",
    (
        "src/cadrumo/application/user_profile/operation_access_policy.py",
        "_persons_act_refusal",
    ): (
        "refuses an agent an operation that needs a secret or administers keys, which are the person's acts "
        "under 2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr, constraints 1 and 2"
    ),
    (
        "src/cadrumo/entrypoints/runtime/profile_connection_person_acts.py",
        "ProfileConnectionPersonActMixin._require_persons_frontend",
    ): (
        "refuses an agent the requests that sign in, administer sessions, keys or the profile, or do installation "
        "work, which are the person's acts under 2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr"
    ),
}
"""Functions that name a frontend without refusing or changing an operation for it."""

_OWN_CLIENT_PACKAGES: Mapping[str, tuple[str, str]] = {
    "src/cadrumo/entrypoints/cli/": (
        OperationFrontendProjection.CLI.name,
        "the command line checks that the runtime client it was handed is its own",
    ),
    "src/cadrumo/entrypoints/tui/": (
        OperationFrontendProjection.TUI.name,
        "the terminal interface checks that the runtime client it was handed is its own",
    ),
}
"""A frontend's own package may compare a client's frontend with itself, and with no other."""


@dataclass(frozen=True, slots=True)
class _Site:
    path: str
    line: int
    owner: str
    members: frozenset[str]
    """The frontend members the site names, or those the predicate it calls compares."""
    what: str


def _named_members(node: ast.AST, aliases: Mapping[str, frozenset[str]]) -> frozenset[str]:
    """The frontend members an expression names, directly or through a name bound to them."""
    found: set[str] = set()
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == _ENUM
            and item.attr in _MEMBERS
        ):
            found.add(item.attr)
        elif isinstance(item, ast.Name) and item.id in aliases:
            found |= aliases[item.id]
    return frozenset(found)


def _frontend_aliases(module: ast.Module) -> Mapping[str, frozenset[str]]:
    """Every name, at any depth, bound to an expression that names frontend members.

    A set of frontends is usually bound to a name first and compared through
    it, so a binding is followed to a fixed point: a name bound to another
    such name carries its members too.
    """
    bindings: list[tuple[str, ast.expr]] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Assign):
            bindings.extend((target.id, node.value) for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            bindings.append((node.target.id, node.value))
    aliases: dict[str, frozenset[str]] = {}
    while True:
        grown = False
        for name, value in bindings:
            members = _named_members(value, aliases) | aliases.get(name, frozenset())
            if members and members != aliases.get(name):
                aliases[name] = members
                grown = True
        if not grown:
            return aliases


def _owned(module: ast.Module) -> Iterator[tuple[str, ast.AST]]:
    """Yield every node with the dotted name of the function or class that owns it."""

    def visit(node: ast.AST, owner: tuple[str, ...]) -> Iterator[tuple[str, ast.AST]]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            owner = (*owner, node.name)
        yield ".".join(owner) or "<module>", node
        for child in ast.iter_child_nodes(node):
            yield from visit(child, owner)

    yield from visit(module, ())


def _comparison_sites(path: str, module: ast.Module) -> list[_Site]:
    """Every comparison or ``match`` case in a module that names a frontend member."""
    aliases = _frontend_aliases(module)
    sites: list[_Site] = []
    for owner, node in _owned(module):
        if isinstance(node, ast.Compare):
            judged, what = node, "comparison"
        elif isinstance(node, ast.match_case):
            judged, what = node.pattern, "match case"
        else:
            continue
        members = _named_members(judged, aliases)
        if members:
            sites.append(_Site(path=path, line=judged.lineno, owner=owner, members=members, what=what))
    return sites


def _predicates(module: ast.Module, sites: list[_Site]) -> dict[str, frozenset[str]]:
    """The functions of a module that return a comparison naming a frontend, with the members compared."""
    compared = {site.line: site.members for site in sites if site.what == "comparison"}
    found: dict[str, frozenset[str]] = {}
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        returned = (item.value for item in ast.walk(node) if isinstance(item, ast.Return) and item.value is not None)
        lines = {part.lineno for value in returned for part in ast.walk(value) if isinstance(part, ast.Compare)}
        members = frozenset[str]().union(*(compared[line] for line in lines & compared.keys()))
        if members:
            found[node.name] = found.get(node.name, frozenset()) | members
    return found


def _call_sites(path: str, module: ast.Module, predicates: Mapping[str, frozenset[str]]) -> list[_Site]:
    sites: list[_Site] = []
    for owner, node in _owned(module):
        if not isinstance(node, ast.Call):
            continue
        called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        members = predicates.get(called) if isinstance(called, str) else None
        if members is not None:
            sites.append(_Site(path=path, line=node.lineno, owner=owner, members=members, what=f"call of {called}"))
    return sites


def _scanned_sources() -> tuple[str, ...]:
    return tuple(path for path in _production_sources() if path.startswith(_SCANNED_TIERS))


def _sites() -> list[_Site]:
    """Every comparison, and every call of a predicate from where its name can be reached.

    A private predicate is called only inside the module that defines it, so
    its name is not read as the same function anywhere else.
    """
    comparisons: dict[str, list[_Site]] = {}
    own: dict[str, dict[str, frozenset[str]]] = {}
    shared: dict[str, frozenset[str]] = {}
    for path in _scanned_sources():
        module = _tree().parsed(path)
        comparisons[path] = _comparison_sites(path, module)
        own[path] = _predicates(module, comparisons[path])
        for name, members in own[path].items():
            if not name.startswith("_"):
                shared[name] = shared.get(name, frozenset()) | members
    sites = [site for found in comparisons.values() for site in found]
    for path in _scanned_sources():
        sites.extend(_call_sites(path, _tree().parsed(path), {**shared, **own[path]}))
    return sites


def _allowed(site: _Site) -> bool:
    if any(site.path == path and site.owner.startswith(function) for path, function in _ALLOWED_FUNCTIONS):
        return True
    for prefix, (own, _reason) in _OWN_CLIENT_PACKAGES.items():
        if site.path.startswith(prefix):
            return site.members == {own}
    return False


def test_no_production_code_tells_the_frontends_apart() -> None:
    """A comparison with a named frontend outside the listed places is a frontend-specific decision."""
    sites = _sites()
    # The scan must reach the comparisons it judges, or it would pass on nothing.
    assert any(_allowed(site) for site in sites)
    offenders = sorted(f"{site.path}:{site.line} {site.owner}: {site.what}" for site in sites if not _allowed(site))
    assert not offenders, "code that decides by the submitting frontend:\n" + "\n".join(offenders)


def test_every_listed_place_still_names_a_frontend_and_states_its_reason() -> None:
    """A listed function that no longer compares a frontend leaves the list."""
    sites = _sites()
    stale = sorted(
        f"{path}::{function}"
        for path, function in _ALLOWED_FUNCTIONS
        if not any(site.path == path and site.owner.startswith(function) for site in sites)
    )
    assert not stale, f"listed as naming a frontend, but no longer does: {stale}"
    reasons = [*_ALLOWED_FUNCTIONS.values(), *(reason for _own, reason in _OWN_CLIENT_PACKAGES.values())]
    assert all(reason.strip() for reason in reasons)
    for prefix in _OWN_CLIENT_PACKAGES:
        assert any(site.path.startswith(prefix) for site in sites), prefix


def test_the_scan_reads_a_direct_comparison_a_bound_set_a_match_and_a_predicate_call() -> None:
    """Each way of telling the frontends apart is found, and a plain use of the enum is not."""
    source = (
        "from registry import OperationFrontendProjection\n"
        "_PERSON = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})\n"
        "_ALL = _PERSON | {OperationFrontendProjection.MCP}\n"
        "def is_agent(context):\n"
        "    return context.frontend is OperationFrontendProjection.MCP\n"
        "class Guard:\n"
        "    def refuse(self, context):\n"
        "        if context.frontend not in _PERSON:\n"
        "            raise ValueError\n"
        "        if context.frontend in _ALL and is_agent(context):\n"
        "            raise ValueError\n"
        "        match context.frontend:\n"
        "            case OperationFrontendProjection.TUI:\n"
        "                raise ValueError\n"
        "def open_client():\n"
        "    return connect(frontend=OperationFrontendProjection.CLI)\n"
    )
    module = ast.parse(source)
    comparisons = _comparison_sites("synthetic.py", module)
    predicates = _predicates(module, comparisons)
    calls = _call_sites("synthetic.py", module, predicates)

    assert [(site.line, site.owner, sorted(site.members), site.what) for site in comparisons] == [
        (5, "is_agent", ["MCP"], "comparison"),
        (8, "Guard.refuse", ["CLI", "TUI"], "comparison"),
        (10, "Guard.refuse", ["CLI", "MCP", "TUI"], "comparison"),
        (13, "Guard.refuse", ["TUI"], "match case"),
    ]
    assert predicates == {"is_agent": frozenset({"MCP"})}
    assert [(site.line, site.owner, site.what) for site in calls] == [(10, "Guard.refuse", "call of is_agent")]

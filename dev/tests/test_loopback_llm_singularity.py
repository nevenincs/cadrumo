"""Loopback-singularity gate: one home for the inference-endpoint plumbing.

Every suite that dispatches at a real inference endpoint needs a REAL socket,
so each of them correctly stood up a ``ThreadingHTTPServer`` on loopback. What
none of them should own is the same bind-thread-shutdown plumbing and the same
reply-envelope literals, and for a long time more than a dozen modules did:
one grew a ``join`` timeout the others lacked, several spelled the same Ollama
envelope with different token counts for no reason a reader could recover.

The hazard this gate pins is the SECOND half of that consolidation rather than
the first. A shared home was introduced and seven suites were moved onto it
while at least nine kept their copy -- and a half-closed duplication is harder
to see than an untouched one, because a reader who finds
:mod:`cadrumo.tests.loopback_llm` reasonably concludes it is the single home
and never looks for the remainder. One of the survivors was itself a second
shared home serving a whole package, which is the shape that hides best. No
gate reported any of this; the tree was green throughout.

Scoped by a positive property, never by naming exceptions
---------------------------------------------------------
A gate that exempted the non-inference loopback servers by PATH would encode
the moment it was written and then detect nothing, so scope is derived from
what a module DOES: a module is in scope when a non-docstring string literal in
it names an LLM runtime or vendor wire path or usage counter
(:data:`LLM_WIRE_MARKERS`). The telemetry sinks, the Drive media servers, the
AEAT browser boundary and the docs static-site server name none of them, so
they fall outside on the property itself -- and a NEW loopback inference server
anywhere in the tree falls inside it on the day it is written, wherever its
author puts it.

The canonical home is likewise located by derivation rather than by path: it is
whichever module declares :class:`~cadrumo.tests.loopback_llm.SilentLoopbackHandler`,
and rule 0 asserts exactly one module does. A rename or relocation of the home
therefore re-anchors the gate instead of silently emptying it.

Three rules, recomputed from the real ``ast`` module every run, with NO stored
baseline and NO per-violation allowlist:

0. Exactly one module declares the loopback handler base, and that module also
   declares the serving context manager.
1. No in-scope module outside the home subclasses
   :class:`~http.server.BaseHTTPRequestHandler` directly. Callers subclass the
   home's handler, which is what carries the silenced access log.
2. No in-scope module outside the home constructs a
   :class:`~http.server.ThreadingHTTPServer`. The bind, the serve thread and
   the bounded shutdown join belong to the home's context manager; rule 2 is
   the load-bearing one, because an author who remembered to subclass the
   handler can still hand-copy the twelve lines of plumbing beneath it.

Both rules resolve import aliases through
:func:`~cadrumo.tests.inventory.import_binding_map`, so ``from http.server
import BaseHTTPRequestHandler as _H`` and a dotted ``http.server.ThreadingHTTPServer``
are caught alongside the bare spellings.

Residual limits, stated rather than papered over
------------------------------------------------
A handler class reached through a first-party re-export of
``BaseHTTPRequestHandler``, or a server class built by ``type()`` or resolved
through ``importlib``, binds no name this walk can resolve. No module in this
tree does either; rule 0 is the backstop, since such a rival would still have
to declare its own serving surface to be usable.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.tests import (
    ast_for_path,
    import_binding_map,
    package_ast_items,
    repo_relative,
    resolve_dotted_origin,
)

from ._project_inventory import project_test_control_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


HANDLER_BASE_ORIGIN = "http.server.BaseHTTPRequestHandler"
"""The stdlib handler base a caller must NOT subclass directly."""

SERVER_ORIGIN = "http.server.ThreadingHTTPServer"
"""The stdlib server a caller must NOT construct; the home's context manager owns it."""

CANONICAL_HANDLER_NAME = "SilentLoopbackHandler"
"""The home's handler base. The module declaring it IS the home, by derivation."""

CANONICAL_SERVER_CONTEXT_NAME = "serving_loopback"
"""The home's serving context manager, which owns the bind/serve/shutdown plumbing."""

LLM_WIRE_MARKERS = frozenset(
    {
        "/api/chat",
        "/api/generate",
        "/api/tags",
        "/api/ps",
        "/api/pull",
        "/api/delete",
        "chat/completions",
        "prompt_eval_count",
        "eval_count",
        "prompt_tokens",
        "completion_tokens",
    },
)
"""Wire paths and usage counters that only an LLM runtime or vendor protocol names.

Membership in a module's non-docstring string literals is what puts that module
in scope. Deliberately the protocol's OWN vocabulary rather than a list of
files: a module speaking this wire is in scope wherever it lives, and a module
speaking a different one is out of scope without being named.
"""


def _docstring_constant_ids(tree: ast.AST) -> frozenset[int]:
    """Return the identities of string constants serving as docstrings.

    A module whose prose happens to mention a wire path is not speaking that
    wire, and pulling documentation into scope would make the gate fire on
    modules that merely describe the protocol.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            found.add(id(first.value))
    return frozenset(found)


def llm_wire_markers(tree: ast.AST) -> frozenset[str]:
    """Return the wire markers this module names in real (non-docstring) string literals."""
    docstrings = _docstring_constant_ids(tree)
    hits: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in docstrings:
            continue
        hits.update(marker for marker in LLM_WIRE_MARKERS if marker in node.value)
    return frozenset(hits)


def declares_canonical_handler(tree: ast.AST) -> bool:
    """Whether this module declares the home's handler base."""
    return any(isinstance(node, ast.ClassDef) and node.name == CANONICAL_HANDLER_NAME for node in ast.walk(tree))


def declares_canonical_server_context(tree: ast.AST) -> bool:
    """Whether this module declares the home's serving context manager."""
    return any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == CANONICAL_SERVER_CONTEXT_NAME
        for node in ast.walk(tree)
    )


def rival_handler_class_violations(
    display_path: str,
    tree: ast.AST,
    *,
    is_canonical: bool,
) -> list[str]:
    """Return rule-1 violations: a direct stdlib handler subclass in an in-scope module."""
    if is_canonical or not llm_wire_markers(tree):
        return []
    bindings = import_binding_map(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if resolve_dotted_origin(ast.unparse(base), bindings) != HANDLER_BASE_ORIGIN:
                continue
            violations.append(
                f"{display_path}:{node.lineno}: class {node.name!r} subclasses {HANDLER_BASE_ORIGIN} "
                f"while its module speaks an LLM wire protocol; subclass {CANONICAL_HANDLER_NAME} "
                f"so the silenced access log and the reply writers come from the one home",
            )
    return violations


def rival_server_construction_violations(
    display_path: str,
    tree: ast.AST,
    *,
    is_canonical: bool,
) -> list[str]:
    """Return rule-2 violations: hand-built serving plumbing in an in-scope module."""
    if is_canonical or not llm_wire_markers(tree):
        return []
    bindings = import_binding_map(tree)
    return [
        f"{display_path}:{node.lineno}: constructs {SERVER_ORIGIN} while its module speaks an LLM "
        f"wire protocol; the bind, the serve thread and the bounded shutdown join belong to "
        f"{CANONICAL_SERVER_CONTEXT_NAME}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and resolve_dotted_origin(ast.unparse(node.func), bindings) == SERVER_ORIGIN
    ]


def scanned_modules(cache: Mapping[Path, ast.AST] | None = None) -> tuple[tuple[Path, ast.AST], ...]:
    """Return every module this gate walks: the package tree plus project-level test support.

    Production modules are included alongside tests deliberately. A loopback
    inference server has no business in production code, and a gate that
    scanned only tests would report green on one.
    """
    items = list(package_ast_items(cache))
    for path in project_test_control_modules():
        tree = ast_for_path(path, cache)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def _canonical_paths(modules: tuple[tuple[Path, ast.AST], ...]) -> tuple[Path, ...]:
    return tuple(path for path, tree in modules if declares_canonical_handler(tree))


def test_exactly_one_module_declares_the_loopback_handler_base(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 0, and the anchor every other rule keys off.

    Both failure directions matter. Zero declarations means the home was
    renamed or deleted and rules 1 and 2 would exempt nothing while enforcing
    nothing either; two means the duplication this gate exists to prevent has
    already happened at the level of the home itself.
    """
    modules = scanned_modules(source_tree_ast)
    homes = _canonical_paths(modules)

    assert len(homes) == 1, (
        f"expected exactly one module to declare {CANONICAL_HANDLER_NAME}; got "
        f"{[repo_relative(path) for path in homes]}"
    )
    home_tree = next(tree for path, tree in modules if path == homes[0])
    assert declares_canonical_server_context(home_tree), (
        f"{repo_relative(homes[0])} declares {CANONICAL_HANDLER_NAME} but not "
        f"{CANONICAL_SERVER_CONTEXT_NAME}; the handler and the serving plumbing must share one home, "
        "or a caller has to hand-build the server anyway"
    )


def test_no_module_speaking_an_llm_wire_subclasses_the_stdlib_handler(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 1: an in-scope loopback endpoint subclasses the home's handler, not the stdlib base."""
    modules = scanned_modules(source_tree_ast)
    homes = frozenset(_canonical_paths(modules))
    violations = [
        violation
        for path, tree in modules
        for violation in rival_handler_class_violations(repo_relative(path), tree, is_canonical=path in homes)
    ]

    assert violations == [], "loopback inference endpoints must subclass the shared home's handler:\n" + "\n".join(
        violations
    )


def test_no_module_speaking_an_llm_wire_builds_its_own_server(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Rule 2: the bind-thread-shutdown plumbing exists once.

    The rule that actually closes the duplication. Rule 1 catches an author who
    copied the handler; this one catches the author who subclassed correctly
    and then hand-copied the twelve lines underneath it, which is the copy that
    drifted last time.
    """
    modules = scanned_modules(source_tree_ast)
    homes = frozenset(_canonical_paths(modules))
    violations = [
        violation
        for path, tree in modules
        for violation in rival_server_construction_violations(repo_relative(path), tree, is_canonical=path in homes)
    ]

    assert violations == [], "the loopback serving plumbing belongs to the shared home:\n" + "\n".join(violations)


def test_the_home_itself_trips_both_detectors_when_scanned_as_a_rival(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Anti-vacuity: prove the detectors describe shapes that really exist here.

    Scans the real home with ``is_canonical=False``. It must trip BOTH rules,
    because it genuinely subclasses the stdlib handler and genuinely constructs
    the server -- that is what being the home means. Were either detector
    describing a shape this codebase does not contain (a renamed stdlib symbol,
    a resolver that stopped resolving), the rules above would report green over
    the whole tree while matching nothing at all.
    """
    modules = scanned_modules(source_tree_ast)
    home_path = _canonical_paths(modules)[0]
    home_tree = next(tree for path, tree in modules if path == home_path)
    display = repo_relative(home_path)

    assert rival_handler_class_violations(display, home_tree, is_canonical=False), (
        f"{display} must subclass {HANDLER_BASE_ORIGIN}; rule 1 matches nothing real otherwise"
    )
    assert rival_server_construction_violations(display, home_tree, is_canonical=False), (
        f"{display} must construct {SERVER_ORIGIN}; rule 2 matches nothing real otherwise"
    )


def test_the_scope_filter_both_admits_live_callers_and_excludes_other_protocols(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Anti-vacuity for the scope property, in both directions.

    A scope filter that admitted nothing would make rules 1 and 2 pass over an
    empty population under every mutation, and one that admitted everything
    would drag the telemetry, Drive and browser loopback servers in and force
    the next author to weaken the gate. Both directions are asserted as
    properties rather than tallies, so adding or retiring a suite never edits a
    constant here.
    """
    modules = scanned_modules(source_tree_ast)
    homes = frozenset(_canonical_paths(modules))

    in_scope_callers = [
        repo_relative(path)
        for path, tree in modules
        if path not in homes and llm_wire_markers(tree) and _subclasses_canonical_handler(tree)
    ]
    assert in_scope_callers, (
        "no module outside the home both speaks an LLM wire and subclasses the home's handler; "
        "the scope filter is selecting an empty population, so rules 1 and 2 enforce nothing"
    )

    out_of_scope_servers = [
        repo_relative(path)
        for path, tree in modules
        if path not in homes and not llm_wire_markers(tree) and _declares_a_stdlib_handler(tree)
    ]
    assert out_of_scope_servers, (
        "every loopback handler in the tree is marker-bearing, so this gate has not been shown to "
        "discriminate; if the non-inference servers really are gone, narrow the claim rather than "
        "leaving an undemonstrated filter in place"
    )


def _subclasses_canonical_handler(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.ClassDef)
        and any(ast.unparse(base).endswith(CANONICAL_HANDLER_NAME) for base in node.bases)
        for node in ast.walk(tree)
    )


def _declares_a_stdlib_handler(tree: ast.AST) -> bool:
    bindings = import_binding_map(tree)
    return any(
        isinstance(node, ast.ClassDef)
        and any(resolve_dotted_origin(ast.unparse(base), bindings) == HANDLER_BASE_ORIGIN for base in node.bases)
        for node in ast.walk(tree)
    )


# --------------------------------------------------------------------------
# Discrimination: each detector is fed the drift it exists to catch, plus the
# live shapes it must NOT flag. A structural gate that cannot fail pins a false
# green, which is the failure mode this gate exists to undo.
# --------------------------------------------------------------------------

_HAND_COPIED_ENDPOINT = """
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Endpoint(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", "0")))
        body = json.dumps({"message": {"content": "x"}, "prompt_eval_count": 12}).encode("utf-8")
        self.send_response(200)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{server.server_port}/api/chat"
"""

_ALIASED_HAND_COPIED_ENDPOINT = """
import http.server as _hs
from http.server import BaseHTTPRequestHandler as _Base


class _Endpoint(_Base):
    def do_POST(self):
        self.wfile.write(b"{}")


def serve():
    return _hs.ThreadingHTTPServer(("127.0.0.1", 0), _Endpoint)


ENDPOINT_PATH = "/v1/chat/completions"
"""

_TELEMETRY_SHAPE = """
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _RecordingTelemetryEndpoint(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(204)
        self.end_headers()


def serve():
    return ThreadingHTTPServer(("127.0.0.1", 0), _RecordingTelemetryEndpoint)
"""

_COMPLIANT_CALLER = """
from http import HTTPStatus

from ...tests.loopback_llm import SilentLoopbackHandler, ollama_chat_reply, serving_loopback, write_json_response


class _Endpoint(SilentLoopbackHandler):
    def do_POST(self):
        write_json_response(self, ollama_chat_reply("x"), status=HTTPStatus.OK)


def serve():
    return serving_loopback(_Endpoint, path="/api/chat")
"""

_PROSE_ONLY_MENTION = '''
"""A module documenting the /api/chat contract without speaking it.

It also mentions prompt_eval_count, purely descriptively.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _SomeOtherHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)


def serve():
    return ThreadingHTTPServer(("127.0.0.1", 0), _SomeOtherHandler)
'''


def test_both_rules_fire_on_a_hand_copied_inference_endpoint() -> None:
    """The exact drift the consolidation removed, reintroduced verbatim."""
    tree = ast.parse(_HAND_COPIED_ENDPOINT)
    display = "src/cadrumo/llm/tests/test_drifted.py"

    handler = rival_handler_class_violations(display, tree, is_canonical=False)
    server = rival_server_construction_violations(display, tree, is_canonical=False)

    assert len(handler) == 1, handler
    assert "_Endpoint" in handler[0]
    assert CANONICAL_HANDLER_NAME in handler[0]
    assert len(server) == 1, server
    assert CANONICAL_SERVER_CONTEXT_NAME in server[0]


def test_both_rules_survive_an_aliased_import_spelling() -> None:
    """Anti-tautology proof for the alias resolution.

    A gate keyed on the literal spellings ``BaseHTTPRequestHandler`` and
    ``ThreadingHTTPServer`` walks straight past ``as _Base`` and past a dotted
    ``http.server.ThreadingHTTPServer``, and the rename costs an author one
    line. Resolving the binding removes the escape.
    """
    tree = ast.parse(_ALIASED_HAND_COPIED_ENDPOINT)
    display = "src/cadrumo/llm/tests/test_aliased.py"

    assert len(rival_handler_class_violations(display, tree, is_canonical=False)) == 1
    assert len(rival_server_construction_violations(display, tree, is_canonical=False)) == 1


def test_neither_rule_fires_on_a_loopback_server_for_another_protocol() -> None:
    """The telemetry sink shape: a real loopback server that is none of this gate's business."""
    tree = ast.parse(_TELEMETRY_SHAPE)
    display = "src/cadrumo/core/telemetry/tests/test_http_sink.py"

    assert rival_handler_class_violations(display, tree, is_canonical=False) == []
    assert rival_server_construction_violations(display, tree, is_canonical=False) == []


def test_neither_rule_fires_on_a_compliant_caller() -> None:
    """The live shape every migrated suite now has must stay green."""
    tree = ast.parse(_COMPLIANT_CALLER)
    display = "src/cadrumo/llm/tests/test_client.py"

    assert llm_wire_markers(tree), "the compliant caller must still be IN scope, or this proves nothing"
    assert rival_handler_class_violations(display, tree, is_canonical=False) == []
    assert rival_server_construction_violations(display, tree, is_canonical=False) == []


def test_a_docstring_mention_does_not_drag_a_module_into_scope() -> None:
    """Describing the protocol is not speaking it.

    Without the docstring exclusion this gate would fire on any module whose
    prose names a wire path -- including its own -- and the next author would
    reasonably weaken it rather than rewrite the documentation.
    """
    tree = ast.parse(_PROSE_ONLY_MENTION)
    display = "src/cadrumo/application/tests/test_prose.py"

    assert llm_wire_markers(tree) == frozenset()
    assert rival_handler_class_violations(display, tree, is_canonical=False) == []
    assert rival_server_construction_violations(display, tree, is_canonical=False) == []


def test_the_canonical_exemption_is_the_only_thing_that_silences_the_rules() -> None:
    """``is_canonical`` must be the sole escape, and it must really silence both rules.

    Guard on the proof above: if the exemption did nothing, the anti-vacuity
    test that scans the home as a rival would pass for the wrong reason and the
    real rules would be failing on the home every run.
    """
    tree = ast.parse(_HAND_COPIED_ENDPOINT)
    display = "src/cadrumo/tests/loopback_llm.py"

    assert rival_handler_class_violations(display, tree, is_canonical=True) == []
    assert rival_server_construction_violations(display, tree, is_canonical=True) == []

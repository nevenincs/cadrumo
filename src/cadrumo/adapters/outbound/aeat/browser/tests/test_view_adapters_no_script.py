"""Static proof that the Sede view's screencast and input adapters evaluate no script.

The adapters reach the page only through the CDP methods they name. A scanner
reads each module's syntax tree and reports every route to script evaluation:
a Playwright evaluation or injection method, a dynamic attribute lookup, the
``eval`` family of builtins, a CDP method outside the module's allow-list, and
a CDP method name that is not a literal. The scanner is proven on isolated
defective sources before it is trusted on the real modules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from .. import screencast, view_input

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: Playwright methods that run or inject script on a page, frame, locator or context.
_SCRIPT_METHODS: Final[frozenset[str]] = frozenset(
    {
        "evaluate",
        "evaluate_all",
        "evaluate_handle",
        "evaluate_on_selector",
        "evaluate_on_selector_all",
        "add_init_script",
        "add_script_tag",
        "expose_function",
        "expose_binding",
        "wait_for_function",
    }
)
_SCRIPT_BUILTINS: Final[frozenset[str]] = frozenset({"eval", "exec", "compile"})
_CDP_METHOD_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Za-z]*\.[a-z][A-Za-z]*$")
#: Calls whose first argument names a CDP method or event.
_CDP_CALLS: Final[frozenset[str]] = frozenset({"send", "on"})

_SCREENCAST_METHODS: Final[frozenset[str]] = frozenset(
    {"Page.startScreencast", "Page.stopScreencast", "Page.screencastFrameAck", "Page.screencastFrame"}
)
_INPUT_METHODS: Final[frozenset[str]] = frozenset(
    {"Input.dispatchMouseEvent", "Input.dispatchKeyEvent", "Input.insertText", "Page.getNavigationHistory"}
)


def _script_findings(source: str, allowed_cdp_methods: frozenset[str]) -> list[str]:
    """Return one finding per route to script evaluation in ``source``."""
    findings: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in _SCRIPT_METHODS:
            findings.append(f"line {node.lineno}: attribute {node.attr}")
        elif isinstance(node, ast.Name) and node.id in _SCRIPT_BUILTINS:
            findings.append(f"line {node.lineno}: builtin {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _SCRIPT_METHODS:
                findings.append(f"line {node.lineno}: method name {node.value}")
            elif _CDP_METHOD_NAME.match(node.value) and node.value not in allowed_cdp_methods:
                findings.append(f"line {node.lineno}: CDP method {node.value}")
        elif isinstance(node, ast.Call):
            findings.extend(_call_findings(node))
    return findings


def _call_findings(call: ast.Call) -> list[str]:
    function = call.func
    if isinstance(function, ast.Name) and function.id in {"getattr", "setattr", "__import__"}:
        return [f"line {call.lineno}: dynamic {function.id}"]
    if isinstance(function, ast.Attribute) and function.attr in _CDP_CALLS and call.args:
        method = call.args[0]
        # A literal, or the one forwarding parameter named ``method`` whose callers pass literals.
        literal = isinstance(method, ast.Constant) and isinstance(method.value, str)
        forwarded = isinstance(method, ast.Name) and method.id == "method"
        if not (literal or forwarded):
            return [f"line {call.lineno}: CDP method name is not a literal"]
    return []


def _source(module: object) -> str:
    path = getattr(module, "__file__", None)
    assert isinstance(path, str)
    return Path(path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("async def f(page):\n    await page.evaluate('1')\n", "attribute evaluate"),
        ("async def f(page):\n    await page.locator('a').evaluate_all('x')\n", "attribute evaluate_all"),
        ("async def f(page):\n    await page.main_frame.evaluate_handle('x')\n", "attribute evaluate_handle"),
        ("async def f(page):\n    await page.add_init_script('x')\n", "attribute add_init_script"),
        ("async def f(page):\n    await page.add_script_tag(content='x')\n", "attribute add_script_tag"),
        ("async def f(page):\n    await page.expose_function('f', g)\n", "attribute expose_function"),
        ("async def f(page):\n    await page.wait_for_function('x')\n", "attribute wait_for_function"),
        ("async def f(session):\n    await session.send('Runtime.evaluate', {})\n", "CDP method Runtime.evaluate"),
        ("async def f(session):\n    await session.send('Runtime.callFunctionOn', {})\n", "CDP method Runtime"),
        (
            "async def f(session):\n    await session.send('Page.addScriptToEvaluateOnNewDocument', {})\n",
            "CDP method Page.addScriptToEvaluateOnNewDocument",
        ),
        ("async def f(session):\n    await session.send('Debugger.evaluateOnCallFrame', {})\n", "CDP method Debugger"),
        ("async def f(session, name):\n    await session.send(f'Runtime.{name}', {})\n", "not a literal"),
        ("async def f(session, name):\n    await session.send(name, {})\n", "not a literal"),
        ("async def f(session):\n    await session.send('Runtime.' + 'evaluate', {})\n", "not a literal"),
        ("def f(page):\n    return getattr(page, 'eval' + 'uate')\n", "dynamic getattr"),
        ("def f(page):\n    return getattr(page, 'evaluate')\n", "dynamic getattr"),
        ("def f():\n    return eval('1')\n", "builtin eval"),
        ("def f():\n    exec('x = 1')\n", "builtin exec"),
        ("def f():\n    return compile('1', 'x', 'eval')\n", "builtin compile"),
        ("def f():\n    return 'evaluate'\n", "method name evaluate"),
    ],
)
def test_screencast_and_input_scanner_detects_each_route_to_script_evaluation(source: str, expected: str) -> None:
    findings = _script_findings(source, _SCREENCAST_METHODS | _INPUT_METHODS)

    assert any(expected in finding for finding in findings), findings


def test_screencast_and_input_scanner_accepts_the_allowed_cdp_methods() -> None:
    source = (
        "async def f(session, method):\n"
        "    await session.send('Input.insertText', {'text': 'x'})\n"
        "    await session.send(method, {})\n"
        "    session.on('Page.screencastFrame', f)\n"
    )

    assert _script_findings(source, _SCREENCAST_METHODS | _INPUT_METHODS) == []


def test_screencast_adapter_evaluates_no_script_and_names_only_its_cdp_methods() -> None:
    assert _script_findings(_source(screencast), _SCREENCAST_METHODS) == []


def test_input_adapter_evaluates_no_script_and_names_only_its_cdp_methods() -> None:
    assert _script_findings(_source(view_input), _INPUT_METHODS) == []


def test_screencast_and_input_adapters_name_every_cdp_method_they_are_allowed() -> None:
    # The allow-lists are exact: a method listed but never named would let a later edit use it unreviewed.
    for module, allowed in ((screencast, _SCREENCAST_METHODS), (view_input, _INPUT_METHODS)):
        named = {
            node.value
            for node in ast.walk(ast.parse(_source(module)))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _CDP_METHOD_NAME.match(node.value)
        }
        assert named == allowed

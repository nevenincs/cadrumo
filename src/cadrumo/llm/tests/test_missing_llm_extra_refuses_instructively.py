"""Every guarded inference entry point preserves the typed optional-extra refusal.

The inference boundary is a claim about what the product SAYS when an operator
reaches a model-bearing surface without having opted into the model-bearing
dependencies: one :class:`~core.MissingOptionalExtraError` carrying registered
machine facts, never a raw ``ModuleNotFoundError`` and never a
surface that quietly runs anyway. This module proves that at the source level,
for every entry point that carries the guard.

**Why the absent state has to be constructed rather than installed.** The dev
and CI environment installs the extra's requirements so the rest of the suite
runs, so the probe reads PRESENT here and every guard is a no-op in-process. A
meta-path finder in a fresh interpreter constructs the absent state faithfully:
the block is installed before any product module is imported, and it RAISES
rather than returning ``None``, so resolution fails exactly as it would against
a genuinely absent distribution. No mock, no patched guard, no monkeypatched
probe -- the real refusal path, reached the real way.

**The blocked module is the one the registry probes**, read from
:data:`~core.LLM_EXTRA` rather than written out here. Blocking a name the
registry does not probe would construct some other absent package's state and
prove nothing about this extra; reading it means a future repoint of the probe
retargets this test with no edit.

**The driven inventory is checked against the guards, not merely asserted.** A
hand-kept list is a completeness claim over a set this module's own author
chose, so the guarded definitions are re-derived from the package source and
the inventory must cover them. A guard added to a new entry point fails here
until it is driven.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ...core import LLM_EXTRA

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

#: The import name :data:`~core.LLM_EXTRA` is registered under. Blocking THIS
#: name is what makes the constructed state correspond to the registered extra
#: rather than to some other absent package.
_PROBE_IMPORT_NAME = LLM_EXTRA.import_name

#: Every guarded entry point, named with a construction that reaches its guard.
#: Each call is deliberately minimal: the guard is the first statement of the
#: callable, so nothing here needs to be a usable argument -- only to evaluate,
#: so the guarded body is entered at all. Arguments are core-only literals, so
#: a driver failure cannot masquerade as a surface outcome.
_GUARDED_SURFACES: tuple[tuple[str, str], ...] = (
    ("rasterise_pdf_pages_to_base64_png", "rasterise_pdf_pages_to_base64_png(b'%PDF-1.4\\n')"),
    ("LocalVisionDocumentTranscriber", "LocalVisionDocumentTranscriber()"),
    ("TextInvoiceFieldExtractor", "TextInvoiceFieldExtractor()"),
    ("LocalTextLLMClassifier", "LocalTextLLMClassifier(spec=None)"),
    ("LocalVisionLLMClassifier", "LocalVisionLLMClassifier(spec=None)"),
    ("SemanticColumnRoleMapper", "SemanticColumnRoleMapper()"),
)


def _guarded_definition_names() -> frozenset[str]:
    """Re-derive the guarded, exported definition names from the package source.

    Structural throughout: a guard inside a branch or a nested helper attributes
    to the OUTERMOST enclosing definition -- the callable an operator can name --
    and a docstring mentioning the guard cannot change the answer.
    """
    package = Path(__file__).resolve().parents[1]
    exported = frozenset(__import__("cadrumo.llm", fromlist=["__all__"]).__all__)
    symbol = "LLM_EXTRA"
    derived: set[str] = set()
    for path in sorted(package.rglob("*.py")):
        if "tests" in path.relative_to(package).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "require_optional_extra"
                and any(isinstance(arg, ast.Name) and arg.id == symbol for arg in child.args)
                for child in ast.walk(node)
            ):
                derived.add(node.name)
    return frozenset(derived) & exported


def _drive_surfaces(*, block: bool) -> list[dict[str, str]]:
    """Drive every guarded surface in a fresh interpreter, optionally without the probe module.

    ``block`` parameterises the control rather than duplicating the runner, so
    the blocked and unblocked runs differ in exactly one respect and nothing
    else can explain a difference between them.
    """
    surfaces = json.dumps([{"name": name, "call": call} for name, call in _GUARDED_SURFACES])
    code = textwrap.dedent(
        f"""
        import json, os, sys
        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = "en"

        class _Blocked:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == {_PROBE_IMPORT_NAME!r}:
                    raise ModuleNotFoundError(f"No module named {{fullname!r}}", name=fullname)
                return None

        if {block!r}:
            # Purge any warm cache first, so the block governs the product's own
            # resolution rather than being satisfied from sys.modules.
            for name in [n for n in sys.modules if n.split(".")[0] == {_PROBE_IMPORT_NAME!r}]:
                del sys.modules[name]
            sys.meta_path.insert(0, _Blocked())

        from cadrumo.core import MissingOptionalExtraError
        from cadrumo.llm import (
            LocalTextLLMClassifier,
            LocalVisionDocumentTranscriber,
            LocalVisionLLMClassifier,
            SemanticColumnRoleMapper,
            TextInvoiceFieldExtractor,
            rasterise_pdf_pages_to_base64_png,
        )

        outcomes = []
        for surface in json.loads({surfaces!r}):
            try:
                eval(surface["call"])
            except MissingOptionalExtraError as exc:
                outcomes.append(
                    {{
                        "name": surface["name"],
                        "outcome": "refused",
                        "extra": exc.extra.extra,
                        "import_name": exc.extra.import_name,
                        "feature": exc.extra.feature,
                    }}
                )
            except ModuleNotFoundError as exc:
                outcomes.append({{"name": surface["name"], "outcome": "module-not-found", "hint": str(exc)}})
            except BaseException as exc:
                outcomes.append(
                    {{"name": surface["name"], "outcome": "other", "hint": f"{{type(exc).__name__}}: {{exc}}"}}
                )
            else:
                outcomes.append({{"name": surface["name"], "outcome": "succeeded", "hint": ""}})

        print("SURFACE_OUTCOMES:" + json.dumps(outcomes))
        """,
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    marker = "SURFACE_OUTCOMES:"
    line = next((row for row in completed.stdout.splitlines() if row.startswith(marker)), None)
    assert line is not None, f"the surface driver produced no outcomes: {completed.stdout!r} {completed.stderr}"
    parsed: list[dict[str, str]] = json.loads(line[len(marker) :])
    assert parsed, "the driver returned an empty outcome set, so every assertion over it holds vacuously"
    return parsed


def test_the_driven_inventory_covers_every_guarded_entry_point() -> None:
    """A guard added to a new entry point must be driven, not silently uncovered.

    The direction is the point: a derived surface this module never drives is a
    hole in the completeness claim below and fails here. The reverse is not a
    failure -- a driven name carrying no guard of its own would simply be extra
    coverage -- but the derived set must never be empty, since an empty set
    would make every assertion below vacuously true.
    """
    derived = _guarded_definition_names()
    assert derived, "no production require_optional_extra(LLM_EXTRA) guard was found; the claims below are vacuous"
    driven = {name for name, _call in _GUARDED_SURFACES}
    assert not derived - driven, (
        f"these entry points carry the llm guard but this module never drives them: {sorted(derived - driven)!r}"
    )


def test_every_guarded_surface_preserves_the_registered_extra_facts() -> None:
    """With the probe absent, each entry point raises the typed refusal unchanged.

    The two outcomes that must never appear are a ``ModuleNotFoundError`` -- the
    raw deep-stack failure the guard exists to convert -- and a successful call,
    which is a model-bearing surface running without the model-bearing
    dependencies.
    """
    outcomes = _drive_surfaces(block=True)

    driven = {entry["name"] for entry in outcomes}
    assert driven == {name for name, _call in _GUARDED_SURFACES}, f"the driver did not reach every surface: {driven!r}"
    expected = {
        "outcome": "refused",
        "extra": LLM_EXTRA.extra,
        "import_name": LLM_EXTRA.import_name,
        "feature": LLM_EXTRA.feature,
    }
    wrong = [entry for entry in outcomes if {key: entry.get(key) for key in expected} != expected]
    assert not wrong, (
        f"these guarded surfaces did not preserve the registered extra facts: {wrong!r}. A 'module-not-found' "
        "outcome is the raw failure the guard exists to convert; a 'succeeded' outcome is a model-bearing "
        "surface running without the model-bearing dependencies."
    )


def test_no_surface_refuses_when_the_probe_module_is_present() -> None:
    """Positive control: the block is what causes the refusal.

    Without this, the refusals above are equally consistent with guards wired to
    fire unconditionally, or with a child interpreter that cannot import the
    product at all -- both of which would satisfy every assertion there. What is
    asserted is narrow and deliberate: only that the EXTRA refusal is absent. A
    surface driven with a deliberately empty argument is expected to fail on its
    own terms, and demanding success would be asserting the feature works rather
    than that the gate opened.
    """
    outcomes = _drive_surfaces(block=False)

    refused = [entry for entry in outcomes if entry["outcome"] in {"refused", "module-not-found"}]
    assert not refused, (
        f"these surfaces reported the llm extra as missing while its probe module {_PROBE_IMPORT_NAME!r} was "
        f"importable: {refused!r}. Every refusal the blocked run observes would then be evidence of nothing."
    )

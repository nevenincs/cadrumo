"""The invoice router holds no label-regex reader.

The deletion gate for the Spanish-label regex family that used to read a PDF's
text layer into an :class:`~application.ledger.evidence_draft.InvoiceDraft`. It recovered only
what its patterns anticipated, and on an unfamiliar layout it did not decline --
it grounded whichever labelled line happened to match, which is fabrication with
a printed anchor behind it. The semantic transcribe-extract-ground chain replaced
it, and a deletion is only real if re-introduction reddens.

Two properties, and the second is what makes the first trustworthy:

**Scoped.** The check binds to ``evidence_draft.py`` alone. Two working AEAT
parsers legitimately carry their own compiled label patterns -- the justificante
extractor and the declaracion parser read fixed AEAT-published layouts, where a
pattern is the correct instrument and no model belongs. A tree-wide sweep for
compiled regexes would demand their deletion, so the scope is a decision rather
than an oversight.

**Detecting.** A scoped gate is indistinguishable from a broken one when the
scoped file is clean, so the same checker is run against those two parsers and
must report their patterns. That is the positive control: it proves the checker
sees what it is pointed at, and therefore that the router's empty result is a
fact about the router rather than about the checker.

The walk is over the parsed AST, never the source text. A text scan cannot
distinguish a call from the same characters inside a docstring -- this module's
own prose names the deleted symbols repeatedly and would trip such a scan -- and
a windowed slice silently stops detecting once the region it measures outgrows
the window.

See Also:
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`
        The router this gate binds to.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        Acquisition stage that replaced the text-layer regex primitive.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeIs

import pytest

from .. import evidence_draft as evidence_draft_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = Path(__file__).resolve().parents[3]
_ROUTER = _SRC_ROOT / "application" / "ledger" / "evidence_draft.py"

# Working AEAT parsers, aimed at fixed published layouts. Deliberately NOT swept
# by this gate; they serve as its positive control.
_AEAT_LAYOUT_PARSERS = (
    _SRC_ROOT / "adapters" / "inbound" / "justificante" / "_extract.py",
    _SRC_ROOT / "adapters" / "inbound" / "declaracion" / "_parser.py",
)


def _compiled_patterns(module_path: Path) -> tuple[str, ...]:
    """Return a label for every ``re.compile`` call in *module_path*.

    Reports the assignment target where the compiled pattern is bound to a name
    and the source line otherwise, so a failure names the site rather than only
    the count. Both the ``re.compile`` attribute form and a bare ``compile``
    imported from ``re`` are recognised, because the second is the obvious way a
    re-introduction would slip a module-level ``import re`` check.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    bare_compile_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "re"
        for alias in node.names
        if alias.name == "compile"
    }

    def _is_compile_call(node: ast.AST) -> TypeIs[ast.Call]:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "compile":
            return isinstance(func.value, ast.Name) and func.value.id == "re"
        return isinstance(func, ast.Name) and func.id in bare_compile_names

    bound: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_compile_call(node.value):
            target = node.targets[0]
            if isinstance(target, ast.Name):
                bound[node.value.lineno] = target.id

    return tuple(bound.get(node.lineno, f"line {node.lineno}") for node in ast.walk(tree) if _is_compile_call(node))


def _imports_re(module_path: Path) -> bool:
    """Whether *module_path* imports the ``re`` module at all."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "re" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "re":
            return True
    return False


def test_the_router_compiles_no_patterns() -> None:
    """A re-introduced label pattern in the router reddens here."""
    found = _compiled_patterns(_ROUTER)

    assert found == (), (
        f"{_ROUTER.name} compiles {len(found)} regex pattern(s) ({', '.join(found)}); "
        "a text-native document is read by the semantic chain, not by label patterns"
    )


def test_the_router_does_not_import_re() -> None:
    """The import is the precondition; removing it closes the indirect routes.

    A pattern reached through a helper, an alias or a comprehension would evade a
    call-shape check while still needing this import, so the two assertions
    together are harder to slip past than either alone.
    """
    assert not _imports_re(_ROUTER), f"{_ROUTER.name} imports `re`, which no reading path there needs"


def test_the_deleted_primitive_is_gone_from_its_defining_module() -> None:
    """A deleted reader has no residual defining-module attribute."""
    assert "extract_invoice_fields" not in vars(evidence_draft_module)

    with pytest.raises(AttributeError):
        _ = getattr(evidence_draft_module, "extract_invoice_fields")  # noqa: B009 -- probing for absence, not access


@pytest.mark.parametrize("parser_path", _AEAT_LAYOUT_PARSERS, ids=lambda path: path.parent.name)
def test_the_checker_detects_the_patterns_it_is_not_pointed_at(parser_path: Path) -> None:
    """Positive control: the AEAT layout parsers keep their patterns, and are seen.

    Without this, a checker that silently detected nothing would pass the two
    assertions above forever. Asserting these files DO report patterns proves the
    detector works, and asserting that the gate above still passes proves the
    scope is a choice.
    """
    assert _compiled_patterns(parser_path), (
        f"{parser_path.name} reports no compiled pattern, so this gate's detector is not proven to detect anything"
    )

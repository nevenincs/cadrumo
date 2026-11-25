#!/usr/bin/env python
"""Tests for the semantic duplication detectors and the dispatch that names them.

``dev.audit.semantic_duplication`` ships seven detectors behind a ``_DETECTORS``
dispatch table and a ``run`` driver, and nothing reached any of them. Its sibling
``dev.audit.duplication`` measures COPY-PASTE through jscpd, is wired to
``just audit-dead-weight``, and carries two test modules. This one has no public
justfile recipe, no workflow lane, and is composed by neither ``advisory`` nor
``report``; its semantic driver is deliberately outside the public Just surface.
The only test references it had were the private ``_load_modules`` helper and the
``Candidate`` type, so every detector and the dispatch keying them were undriven.

The module's own docstring says why it exists: jscpd matches token sequences, so
"a concept implemented twice in different syntax is invisible to it, and that is
exactly the duplication this project's rules treat as a blocker".

These drive the public ``run`` over constructed trees, so a dispatch key that stops
resolving, or a detector that stops firing, is a red test rather than a capability
that quietly reports nothing.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from ..semantic_duplication import DETECTORS, run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHARED = tuple(f"cadrumo.{name}_dep" for name in ("alpha", "beta", "gamma", "delta", "epsilon"))
_DISJOINT = tuple(f"cadrumo.{name}_dep" for name in ("zeta", "eta", "theta", "iota", "kappa"))


def _module(package: Path, name: str, imports: tuple[str, ...]) -> None:
    """Write a module whose only content is its first-party import set."""
    lines = [f"from {target} import thing" for target in imports]
    (package / name).write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def test_every_dispatch_key_runs_the_detector_it_names(tmp_path: Path) -> None:
    """The dispatch is the only route to the detectors, so it must resolve entire.

    ``run`` looks each requested name up in ``_DETECTORS`` and calls the result. A
    key that lost its callable would raise ``KeyError`` for that name alone, which
    is invisible while nothing asks for every name at once.
    """
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "solo.py", _SHARED)

    for name in sorted(DETECTORS):
        assert run((package,), [name]) is not None

    assert sorted(DETECTORS) == [
        "call_fingerprint",
        "duplicated_derivation",
        "enum_subset",
        "field_set",
        "import_overlap",
        "package_overlap",
        "scarce_literal",
    ]


def test_two_modules_reaching_for_the_same_collaborators_are_reported(tmp_path: Path) -> None:
    """The positive case: identical first-party import sets, and no edge between them."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "left.py", _SHARED)
    _module(package, "right.py", _SHARED)

    found = run((package,), ["import_overlap"])

    assert [candidate.sites for candidate in found] == [("cadrumo/left.py", "cadrumo/right.py")]
    assert found[0].fingerprint == "jaccard=1.00"


def test_modules_sharing_no_collaborator_are_not_reported(tmp_path: Path) -> None:
    """Sibling blindness: a detector that fired on anything would be worthless.

    Same module count, same import count, same shape -- only the overlap differs, so
    a green here is about the Jaccard floor and not about the corpus being small.
    """
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "left.py", _SHARED)
    _module(package, "right.py", _DISJOINT)

    assert run((package,), ["import_overlap"]) == []


def test_a_corpus_with_no_production_module_refuses_rather_than_reporting_clean(tmp_path: Path) -> None:
    """Every detector would report clean over nothing, so the load refuses first.

    Coverage showed all three of this module's refusals unexercised: they were
    added, proved once by hand, and never pinned. A refusal nothing drives is
    indistinguishable from one that has stopped firing.
    """
    with pytest.raises(SystemExit, match=r"no production modules found under"):
        run((tmp_path,), list(DETECTORS))


def test_an_unparsable_module_refuses_rather_than_shortening_the_corpus(tmp_path: Path) -> None:
    """A module that does not parse would leave the corpus short by exactly it."""
    (tmp_path / "bad.py").write_text("def (:" + chr(10), encoding="utf-8")

    with pytest.raises(SystemExit, match=r"could not be parsed, so the duplication corpus"):
        run((tmp_path,), list(DETECTORS))


def test_an_unreadable_module_refuses_for_its_own_reason(tmp_path: Path) -> None:
    """The read failure is refused separately from the parse failure.

    The module raises the two for distinct reasons precisely so a caller matching
    on one cause cannot be satisfied by the other, so this asserts the read
    wording and would fail if the two refusals were merged. The unreadable module
    is a DIRECTORY named ``*.py``: rglob lists it and ``read_text`` raises, which
    needs no symlink privilege.
    """
    (tmp_path / "ok.py").write_text("x = 1" + chr(10), encoding="utf-8")
    (tmp_path / "broken.py").mkdir()

    with pytest.raises(SystemExit, match=r"could not be read, so the duplication corpus"):
        run((tmp_path,), list(DETECTORS))


def test_a_concept_restated_in_another_package_collides_across_roots(tmp_path: Path) -> None:
    """The roots form one corpus, so a copy living in a second package is still a pair.

    Each site carries its package, so two packages' same-named modules stay distinct.
    """
    product = tmp_path / "src" / "cadrumo"
    runtime = tmp_path / "src" / "cadrumo_runtime"
    product.mkdir(parents=True)
    runtime.mkdir()
    _module(product, "guard.py", _SHARED)
    _module(runtime, "guard.py", _SHARED)

    found = run((product, runtime), ["import_overlap"])

    assert [candidate.sites for candidate in found] == [("cadrumo/guard.py", "cadrumo_runtime/guard.py")]


def test_a_root_with_no_production_module_refuses_beside_a_populated_one(tmp_path: Path) -> None:
    """A lost package must not shrink the corpus while the others still load."""
    product = tmp_path / "cadrumo"
    product.mkdir()
    _module(product, "solo.py", _SHARED)

    assert run((product,), ["import_overlap"]) == []
    with pytest.raises(SystemExit, match=r"no production modules found under .*cadrumo_mcp"):
        run((product, tmp_path / "cadrumo_mcp"), ["import_overlap"])


def test_module_entry_point_runs_every_detector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Running the module as a script reaches ``main`` with all helpers defined.

    The entry guard once preceded a helper definition, so the script crashed with a
    ``NameError`` that importing the module never exposed.
    """
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    _module(package, "one.py", _SHARED)
    _module(package, "two.py", _SHARED)
    monkeypatch.setattr("sys.argv", ["semantic_duplication", "--root", str(package), "--json"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("dev.audit.semantic_duplication", run_name="__main__")

    assert raised.value.code == 0
    assert capsys.readouterr().out.lstrip().startswith("[")


_ENUM = """from enum import StrEnum


class Effect(StrEnum):
    NONE = "none"
    UPDATED = "updated"
    PARTIAL = "partial"


class Stage(StrEnum):
    NONE = "none"
    UPDATED = "updated"
"""


def _source(package: Path, name: str, source: str) -> None:
    """Write one module's source verbatim."""
    (package / name).write_text(source, encoding="utf-8")


@pytest.fixture
def package(tmp_path: Path) -> Path:
    """Return a package already declaring two closed enums with overlapping member names."""
    root = tmp_path / "cadrumo"
    root.mkdir()
    _source(root, "enums.py", _ENUM)
    return root


def test_standard_library_imports_are_not_shared_collaborators(tmp_path: Path) -> None:
    """Two modules agreeing only on ``typing``-style imports have no collaborator in common."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    external = ("typing", "dataclasses", "pathlib", "json", "collections")
    _module(package, "left.py", external)
    _module(package, "right.py", external)

    assert run((package,), ["import_overlap"]) == []


def test_one_relative_spelling_in_two_packages_names_two_modules(tmp_path: Path) -> None:
    """``.contracts`` under two packages must not count as one shared dependency."""
    relative = tuple(f".{name}" for name in ("contracts", "errors", "models", "ports", "results"))
    for name in ("left", "right"):
        package = tmp_path / "cadrumo" / name
        package.mkdir(parents=True)
        _module(package, "impl.py", relative)

    assert run((tmp_path / "cadrumo",), ["import_overlap"]) == []


def test_relative_and_absolute_imports_of_one_module_are_one_dependency(tmp_path: Path) -> None:
    """The real positive that resolving imports must keep: two spellings, one collaborator set."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    names = ("contracts", "errors", "models", "ports", "results")
    _module(package, "left.py", tuple(f".{name}" for name in names))
    _module(package, "right.py", tuple(f"cadrumo.{name}" for name in names))

    found = run((package,), ["import_overlap"])

    assert [candidate.sites for candidate in found] == [("cadrumo/left.py", "cadrumo/right.py")]


def test_a_short_stem_inside_an_import_name_is_not_an_edge(tmp_path: Path) -> None:
    """Only a whole module name proves an edge; ``io`` must not match ``cadrumo.alpha_io_dep``."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    imports = tuple(f"cadrumo.{name}_io_dep" for name in ("alpha", "beta", "gamma", "delta", "epsilon"))
    _module(package, "io.py", imports)
    _module(package, "other.py", imports)

    assert len(run((package,), ["import_overlap"])) == 1


def test_a_module_importing_the_other_is_a_layering_not_a_copy(tmp_path: Path) -> None:
    """The no-edge condition still holds once it compares whole names."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "lower.py", _SHARED)
    _module(package, "upper.py", (*_SHARED, "cadrumo.lower"))

    assert run((package,), ["import_overlap"]) == []


def test_one_partition_gathered_in_two_modules_is_reported(package: Path) -> None:
    """A collection and a boolean chain draw the same line, whatever the syntax."""
    _source(package, "a.py", "from .enums import Effect\nSETTLED = frozenset({Effect.NONE, Effect.UPDATED})\n")
    _source(
        package, "b.py", "from . import enums\nok = lambda e: e is enums.Effect.NONE or e is enums.Effect.UPDATED\n"
    )

    found = run((package,), ["enum_subset"])

    assert [(c.fingerprint, c.sites) for c in found] == [
        ("Effect{NONE, UPDATED}", ("cadrumo/a.py", "cadrumo/b.py")),
    ]


def test_members_merely_mentioned_apart_are_no_partition(package: Path) -> None:
    """Two returns naming two members state no shared line through the enum."""
    source = "from .enums import Effect\ndef f(x):\n    if x:\n        return Effect.NONE\n    return Effect.UPDATED\n"
    _source(package, "a.py", source)
    _source(package, "b.py", source)

    assert run((package,), ["enum_subset"]) == []


def test_a_subset_is_whole_only_against_the_declared_members(package: Path) -> None:
    """Naming two of three members partitions, even if no module ever names the third."""
    source = "from .enums import Effect, Stage\nA = {Effect.NONE, Effect.UPDATED}\nB = {Stage.NONE, Stage.UPDATED}\n"
    _source(package, "a.py", source)
    _source(package, "b.py", source)

    found = run((package,), ["enum_subset"])

    assert [c.fingerprint for c in found] == ["Effect{NONE, UPDATED}"]


def test_inverse_derivations_and_other_enums_do_not_collide(package: Path) -> None:
    """Opposite arms and same-named members of another enum are different rules."""
    template = "from .enums import Effect, Stage\nv = lambda {0}: {1} if {0} else {2}\n"
    _source(package, "a.py", template.format("c", "Effect.UPDATED", "Effect.NONE"))
    _source(package, "b.py", template.format("c", "Effect.NONE", "Effect.UPDATED"))
    _source(package, "c.py", template.format("c", "Stage.UPDATED", "Stage.NONE"))
    assert run((package,), ["duplicated_derivation"]) == []

    _source(package, "d.py", template.format("wrote", "Effect.UPDATED", "Effect.NONE"))
    found = run((package,), ["duplicated_derivation"])
    assert [c.sites for c in found] == [("cadrumo/a.py:2", "cadrumo/d.py:2")]


def test_a_constant_namespace_is_not_a_closed_value(package: Path) -> None:
    """Upper-case attributes of something that is no enum carry no closed-value meaning."""
    source = "v = lambda c: settings.ALPHA if c else settings.BETA\n"
    _source(package, "a.py", source)
    _source(package, "b.py", source)

    assert run((package,), ["duplicated_derivation"]) == []


def test_scarce_literals_must_meet_in_one_scope_on_both_sides(package: Path) -> None:
    """A pair is a rule only where both values are stated together."""
    together = "def rate():\n    return (0.21, 0.105)\n"
    apart = "def a():\n    return 0.21\n\n\ndef b():\n    return 0.105\n"
    _source(package, "a.py", together)
    _source(package, "b.py", apart)
    assert run((package,), ["scarce_literal"]) == []

    _source(package, "c.py", "RATES = {'general': 0.21, 'reduced': 0.105}\n")
    found = run((package,), ["scarce_literal"])
    assert [c.sites for c in found] == [("cadrumo/a.py", "cadrumo/c.py")]
    assert found[0].fingerprint == "0.105 + 0.21"


def test_documentation_is_neither_a_literal_nor_behaviour(package: Path) -> None:
    """Shared docstrings are no shared rule, and differing ones must not hide a copy."""
    documented = 'def f():\n    """Shared words."""\n    """More shared words."""\n    return 0.21\n'
    _source(package, "a.py", documented)
    _source(package, "b.py", documented)
    assert run((package,), ["scarce_literal"]) == []

    body = "    return first(1, 2) + second(3) + third(4) + fourth(5) + fifth(6)\n"
    _source(package, "c.py", f'def one():\n    """First wording."""\n{body}')
    _source(package, "d.py", f'def two():\n    """Second wording."""\n{body}')
    assert [c.sites for c in run((package,), ["call_fingerprint"])] == [("cadrumo/c.py:1 one", "cadrumo/d.py:1 two")]


def test_one_set_in_either_order_is_one_derivation(package: Path) -> None:
    """Set order carries no meaning, unlike the arms of a ternary."""
    template = "from .enums import Effect\nv = lambda e: e in {{Effect.{}, Effect.{}}}\n"
    _source(package, "a.py", template.format("NONE", "UPDATED"))
    _source(package, "b.py", template.format("UPDATED", "NONE"))

    assert [c.sites for c in run((package,), ["duplicated_derivation"])] == [("cadrumo/a.py:2", "cadrumo/b.py:2")]


def test_a_negated_condition_is_a_different_derivation(package: Path) -> None:
    """``not`` swaps which arm a condition selects, so it must reach the fingerprint."""
    template = "from .enums import Effect\nv = lambda c: Effect.NONE if {}c else Effect.UPDATED\n"
    _source(package, "a.py", template.format(""))
    _source(package, "b.py", template.format("not "))

    assert run((package,), ["duplicated_derivation"]) == []


def test_a_callee_keyword_is_part_of_what_a_function_does(package: Path) -> None:
    """Keywords tell apart otherwise equal calls and lift a short real copy over the floor."""
    template = "def {}(x):\n    return build(x, kind=x, source=x, {}=x, order=x)\n"
    _source(package, "a.py", template.format("one", "reason"))
    _source(package, "b.py", template.format("two", "reason"))
    _source(package, "c.py", template.format("three", "casilla"))

    found = run((package,), ["call_fingerprint"])

    assert [c.sites for c in found] == [("cadrumo/a.py:1 one", "cadrumo/b.py:1 two")]

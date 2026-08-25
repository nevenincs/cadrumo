"""Gate the derivation the uninstall step's completeness claim rests on.

The uninstall step asserts that EVERY guarded surface returns to the instructive
refusal once the extra is removed. That is a completeness claim, and it is only
worth the name if the set it quantifies over comes from the production guard
rather than from a list the lane's own author kept. These tests run the
derivation against the real tree and against synthetic trees that exercise the
shapes a text-matching implementation would get wrong.

The full lane needs a built cohort and two real venvs, so it cannot run here.
What CAN run here is the part the claim actually rests on, and that is what
these gates hold.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..smoke_absent_llm import (
    _EXTRA,
    _INFERENCE_SURFACES,
    _assert_the_driver_reaches_every_guarded_surface,
    _exported_names,
    _guard_symbol_for_the_extra,
    _guarded_surfaces_from_production_guards,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_guard_symbol_comes_from_the_registry_not_a_literal() -> None:
    """A renamed registry record must fail here rather than yield an empty guarded set."""
    assert _guard_symbol_for_the_extra(REPO_ROOT) == f"{_EXTRA.upper()}_EXTRA"


def test_the_live_tree_yields_a_populated_guarded_set() -> None:
    """The populated-set guard: an empty denominator makes every claim below vacuous."""
    symbol = _guard_symbol_for_the_extra(REPO_ROOT)
    reachable, _internal = _guarded_surfaces_from_production_guards(REPO_ROOT, symbol)
    assert reachable, "the derivation found no guarded surface, so the completeness claim is empty"


def test_the_derived_set_is_a_subset_of_what_the_lane_drives() -> None:
    """The live coverage relation the lane asserts, checked without building a cohort."""
    symbol = _guard_symbol_for_the_extra(REPO_ROOT)
    reachable, internal = _guarded_surfaces_from_production_guards(REPO_ROOT, symbol)
    _assert_the_driver_reaches_every_guarded_surface(reachable, internal)
    assert reachable <= {name for name, _call in _INFERENCE_SURFACES}


def _synthetic_package(root: Path, *modules: tuple[str, str], exports: tuple[str, ...]) -> Path:
    """Materialise a minimal ``src/cadrumo/llm`` tree for the derivation to walk."""
    package = root / "src" / "cadrumo" / "llm"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(f"__all__ = {list(exports)!r}\n", encoding="utf-8")
    for name, body in modules:
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_a_guard_nested_inside_a_branch_is_still_attributed_to_its_public_callable(tmp_path: Path) -> None:
    """A structural walk finds a guard a line-oriented scan of the def body would miss."""
    _synthetic_package(
        tmp_path,
        (
            "_impl.py",
            "def public_surface(flag):\n"
            "    if flag:\n"
            "        for _ in range(1):\n"
            "            try:\n"
            "                require_optional_extra(LLM_EXTRA)\n"
            "            except Exception:\n"
            "                raise\n"
            "    return 1\n",
        ),
        exports=("public_surface",),
    )
    reachable, internal = _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")
    assert reachable == {"public_surface"}
    assert internal == frozenset()


def test_a_guard_in_a_nested_helper_attributes_to_the_outermost_public_definition(tmp_path: Path) -> None:
    """The operator names the outer callable, so that is the surface the claim is about."""
    _synthetic_package(
        tmp_path,
        (
            "_impl.py",
            "def public_surface():\n"
            "    def _inner():\n"
            "        require_optional_extra(LLM_EXTRA)\n"
            "    return _inner()\n",
        ),
        exports=("public_surface",),
    )
    reachable, internal = _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")
    assert reachable == {"public_surface"}
    # The nested helper must not surface as a second, unexported guarded
    # definition. Attributing to it as well would report a private closure the
    # lane cannot drive, and the driver-coverage check would then look like it
    # was capping its denominator when the outer callable already covers it.
    assert internal == frozenset(), "the guard must attribute to the outermost definition only"


def test_a_guard_naming_a_different_extra_is_not_enrolled(tmp_path: Path) -> None:
    """The set is keyed on THIS extra; another extra's guard is another lane's claim."""
    _synthetic_package(
        tmp_path,
        (
            "_impl.py",
            "def ours():\n    require_optional_extra(LLM_EXTRA)\n\n"
            "def theirs():\n    require_optional_extra(ANTHROPIC_EXTRA)\n",
        ),
        exports=("ours", "theirs"),
    )
    reachable, _internal = _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")
    assert reachable == {"ours"}


def test_prose_mentioning_the_guard_does_not_enrol_a_surface(tmp_path: Path) -> None:
    """The failure mode a text scan has here repeatedly: a docstring is not a call."""
    _synthetic_package(
        tmp_path,
        (
            "_impl.py",
            "def guarded():\n    require_optional_extra(LLM_EXTRA)\n\n"
            "def documented():\n"
            '    """Callers reach this after require_optional_extra(LLM_EXTRA) has run."""\n'
            "    marker = 'require_optional_extra(LLM_EXTRA)'\n"
            "    return marker\n",
        ),
        exports=("guarded", "documented"),
    )
    reachable, _internal = _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")
    assert reachable == {"guarded"}, "a mention in prose or a string literal is not a production guard"


def test_a_guarded_definition_the_package_does_not_export_is_reported_not_dropped(tmp_path: Path) -> None:
    """Silently discarding it would cap the denominator the completeness claim quantifies over."""
    _synthetic_package(
        tmp_path,
        ("_impl.py", "def _internal():\n    require_optional_extra(LLM_EXTRA)\n"),
        exports=("something_else",),
    )
    reachable, internal = _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")
    assert reachable == frozenset()
    assert internal == {"_internal"}


def test_a_tree_with_no_production_guard_refuses_rather_than_claiming_completeness(tmp_path: Path) -> None:
    """An empty set makes every downstream assertion vacuously true, so it must fail loudly."""
    _synthetic_package(tmp_path, ("_impl.py", "def plain():\n    return 1\n"), exports=("plain",))
    with pytest.raises(SystemExit, match="empty"):
        _guarded_surfaces_from_production_guards(tmp_path, "LLM_EXTRA")


def test_a_guarded_surface_the_driver_never_reaches_fails_the_coverage_check() -> None:
    """The direction that matters: an unreached guarded surface is a hole, not a note."""
    with pytest.raises(SystemExit, match="never drives them"):
        _assert_the_driver_reaches_every_guarded_surface(frozenset({"a_surface_no_driver_names"}), frozenset())


def test_the_guarded_set_is_read_from_a_literal_all(tmp_path: Path) -> None:
    """The export set is structural too; a package without a literal ``__all__`` refuses."""
    package = tmp_path / "src" / "cadrumo" / "llm"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("__all__ = sorted(dir())\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no literal __all__"):
        _exported_names(package / "__init__.py")

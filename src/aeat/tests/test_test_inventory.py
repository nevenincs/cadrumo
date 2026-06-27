"""Tests for the shared production-test inventory helper."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import (
    FIXTURES_DIR,
    REPO_ROOT,
    SRC_AEAT,
    aeat_relative,
    ast_for_path,
    bare_utf8_literal_violations,
    cast_call_linenos,
    cast_rationale_violations,
    discover_test_modules,
    has_marker_on_line_or_adjacent_comment_block,
    module_name,
    non_test_package_python_files,
    non_test_python_files_under,
    package_ast_items,
    package_python_files,
    production_ast_items,
    production_python_files,
    qualified_name,
    regex_line_hits,
    repo_path,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_discover_test_modules_returns_real_source_tests_and_excludes_fixtures() -> None:
    """Inventory discovery includes source tests and excludes fixture payloads."""
    modules = discover_test_modules()

    assert Path(__file__).resolve() in modules
    assert repo_path("src/aeat/tests/test_marker_integrity.py") in modules
    assert all(not path.is_relative_to(FIXTURES_DIR) for path in modules)


def test_repo_relative_uses_posix_paths() -> None:
    """Repository-relative rendering is stable on Windows and POSIX."""
    assert repo_relative(Path(__file__).resolve()) == "src/aeat/tests/test_test_inventory.py"


def test_aeat_relative_uses_posix_package_paths() -> None:
    """Package-relative rendering is stable on Windows and POSIX."""
    assert aeat_relative(Path(__file__).resolve()) == "tests/test_test_inventory.py"


def test_repo_path_roundtrips_repo_relative() -> None:
    """A rendered relative path resolves back under the repository root."""
    current = Path(__file__).resolve()
    relative = repo_relative(current)

    assert repo_path(relative) == current
    assert repo_path(relative).is_relative_to(REPO_ROOT)


def test_production_python_files_excludes_tests_conftest_and_data() -> None:
    """Production source inventory has one shared scan surface."""
    files = production_python_files()

    assert repo_path("src/aeat/core/config.py") in files
    assert repo_path("src/aeat/conftest.py") not in files
    assert all("tests" not in path.relative_to(repo_path("src/aeat")).parts for path in files)
    assert all("_data" not in path.relative_to(repo_path("src/aeat")).parts for path in files)


def test_package_python_files_includes_tests_but_excludes_data_by_default() -> None:
    """Package inventory keeps tests in scope while excluding bundled data helpers."""
    files = package_python_files()

    assert Path(__file__).resolve() in files
    assert repo_path("src/aeat/core/config.py") in files
    assert all("_data" not in path.relative_to(repo_path("src/aeat")).parts for path in files)


def test_non_test_package_python_files_excludes_test_tree_and_scan_excludes() -> None:
    """Non-test package inventory keeps conftest by default and honors rel excludes."""
    files = non_test_package_python_files(include_data=True, scan_excludes={"core/config.py"})

    assert repo_path("src/aeat/core/config.py") not in files
    assert repo_path("src/aeat/conftest.py") in files
    assert all(not path.name.startswith("test_") for path in files)
    assert all("tests" not in path.relative_to(SRC_AEAT).parts for path in files)


def test_non_test_python_files_under_handles_direct_files_and_package_dirs() -> None:
    """Scoped non-test inventory supports file and directory inputs."""
    config_path = repo_path("src/aeat/core/config.py")
    tests_dir = repo_path("src/aeat/tests")

    assert non_test_python_files_under(config_path) == (config_path,)
    assert non_test_python_files_under(tests_dir) == ()
    assert config_path in non_test_python_files_under(repo_path("src/aeat/core"))


def test_production_ast_items_filters_cache_to_production_package_files(tmp_path: Path) -> None:
    """Production AST iteration shares the production-file surface."""
    config_path = repo_path("src/aeat/core/config.py")
    config_tree = ast_for_path(config_path)
    assert config_tree is not None
    test_tree = ast.parse("def test_example(): pass")
    external_path = tmp_path / "external.py"
    external_tree = ast.parse("value = 1")

    assert production_ast_items(
        {
            config_path: config_tree,
            Path(__file__).resolve(): test_tree,
            external_path: external_tree,
        },
    ) == ((config_path, config_tree),)


def test_package_ast_items_reuses_cache_for_test_modules(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Package AST iteration includes test modules and reuses cached trees."""
    current = Path(__file__).resolve()
    current_tree = source_tree_ast[current]

    items = dict(package_ast_items(source_tree_ast))

    assert items[current] is current_tree
    assert repo_path("src/aeat/core/config.py") in items


def test_module_name_renders_importable_aeat_modules() -> None:
    """Module-name rendering handles ordinary modules and package initializers."""
    assert module_name(repo_path("src/aeat/core/config.py")) == "aeat.core.config"
    assert module_name(repo_path("src/aeat/application/__init__.py")) == "aeat.application"


def test_ast_for_path_prefers_supplied_cache(tmp_path: Path) -> None:
    """AST lookup reuses the caller's cache before touching the file."""
    path = tmp_path / "module.py"
    path.write_text("BROKEN =", encoding="utf-8")
    cached = ast.parse("value = 1", filename=str(path))

    assert ast_for_path(path, {path: cached}) is cached


def test_ast_for_path_falls_back_to_real_parse(tmp_path: Path) -> None:
    """AST lookup parses a real source file when no cache entry exists."""
    path = tmp_path / "module.py"
    path.write_text("value = 1\n", encoding="utf-8")

    tree = ast_for_path(path)

    assert isinstance(tree, ast.Module)
    assert isinstance(tree.body[0], ast.Assign)


def test_ast_for_path_returns_none_for_unparseable_source(tmp_path: Path) -> None:
    """Invalid Python source is reported as absent rather than hidden by a fake tree."""
    path = tmp_path / "module.py"
    path.write_text("value =", encoding="utf-8")

    assert ast_for_path(path) is None


def test_qualified_name_renders_call_name_attribute_chains() -> None:
    """Qualified-name rendering handles the AST shapes guard tests scan."""
    call_expr = ast.parse("pytest.mark.skipif(True)").body[0].value
    assert isinstance(call_expr, ast.Call)

    assert qualified_name(call_expr) == "pytest.mark.skipif"
    assert qualified_name(call_expr.func) == "pytest.mark.skipif"
    assert qualified_name(ast.parse("name").body[0].value) == "name"


def test_cast_call_linenos_detects_real_cast_shapes() -> None:
    """Cast-call discovery detects supported AST shapes without text matching."""
    tree = ast.parse(
        "\n".join(
            [
                "value = cast(str, raw)",
                "other = typing.cast(int, raw)",
                "third = t.cast(float, raw)",
                "ignored = helper.cast(raw)",
            ],
        ),
    )

    assert list(cast_call_linenos(tree)) == [1, 2, 3]


def test_marker_lookup_accepts_same_line_and_leading_comment_block() -> None:
    """Marker lookup follows only the adjacent blank/comment block."""
    assert has_marker_on_line_or_adjacent_comment_block(
        ["# CAST-RATIONALE-TEST: documented", "", "value = cast(str, raw)"],
        3,
        "CAST-RATIONALE-",
    )
    assert has_marker_on_line_or_adjacent_comment_block(
        ["value = cast(str, raw)  # CAST-RATIONALE-TEST"],
        1,
        "CAST-RATIONALE-",
    )
    assert not has_marker_on_line_or_adjacent_comment_block(
        ["# CAST-RATIONALE-TEST: too far", "other = 1", "value = cast(str, raw)"],
        3,
        "CAST-RATIONALE-",
    )


def test_cast_rationale_violations_ignore_out_of_tree_cache_entries(tmp_path: Path) -> None:
    """Cast-rationale inventory only evaluates package production files."""
    path = tmp_path / "external.py"
    path.write_text("value = cast(str, raw)\n", encoding="utf-8")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert cast_rationale_violations({path: tree}) == []


def test_regex_line_hits_reports_repo_relative_matches_and_skips_comments(tmp_path: Path) -> None:
    """Regex scan helper reports real source lines while ignoring comment-only hits."""
    path = tmp_path / "module.py"
    path.write_text('# token\nvalue = "token"\n', encoding="utf-8")

    assert regex_line_hits([path], re.compile("token")) == [f"{path.as_posix()}:2: 'token'"]


def test_regex_line_hits_can_include_comment_lines(tmp_path: Path) -> None:
    """Callers can opt into comment-line matches for textual inventory tests."""
    path = tmp_path / "module.py"
    path.write_text("# token\n", encoding="utf-8")

    assert regex_line_hits([path], re.compile("token"), skip_comment_lines=False) == [
        f"{path.as_posix()}:1: 'token'",
    ]


def test_bare_utf8_literal_violations_ignore_hash_protocol_lines(tmp_path: Path) -> None:
    """UTF-8 inventory reports text I/O literals while preserving hash-protocol escapes."""
    path = tmp_path / "module.py"
    path.write_text(
        "\n".join(
            [
                'payload = path.read_text(encoding="utf-8")',
                'digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()',
                'body = data.decode("utf-8")',
            ],
        ),
        encoding="utf-8",
    )

    assert bare_utf8_literal_violations(path) == [
        (1, 'payload = path.read_text(encoding="utf-8")'),
        (3, 'body = data.decode("utf-8")'),
    ]

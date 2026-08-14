"""Real-filesystem checks for the fixture-census authority."""

from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import pytest

from ..fixture_census import FixtureCensusError, _read_trees, census, iter_source_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_source(root: Path, relative_path: str, source: str) -> None:
    """Write one Python source file into a real miniature repository tree."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")


def _write_complete_fixture_tree(root: Path) -> None:
    """Create one fixture topology spanning every required census source root."""
    _write_source(
        root,
        "conftest.py",
        """
        import pytest as pt

        @pt.fixture
        def root_dependency():
            return "root"

        @pt.fixture
        def declared_dependency():
            return "declared"

        @pt.mark.usefixtures("declared_dependency")
        @pt.fixture(name="root_public", scope="session", autouse=True, params=("case",))
        def root_guard(root_dependency, request):
            return f"{root_dependency}:{request.param}"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/provider.py",
        """
        from pytest import fixture as fx

        @fx
        def shared():
            return "shared"

        @fx(autouse=True)
        def conftest_autouse():
            return "automatic"

        def test_provider_consumer(shared):
            assert shared == "shared"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/nested/conftest.py",
        """
        from cadrumo.provider import conftest_autouse, shared as inherited_shared
        """,
    )
    _write_source(
        root,
        "src/cadrumo/nested/test_descendant.py",
        """
        import pytest

        @pytest.mark.usefixtures("inherited_shared")
        def test_inherited_usefixtures():
            pass

        def test_inherited_static_request(request):
            request.getfixturevalue("inherited_shared")

        def test_inherited_autouse_reach():
            pass
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_usage.py",
        """
        from cadrumo.provider import shared as imported_shared

        def test_imported_consumer(imported_shared):
            assert imported_shared == "shared"

        def test_dynamic_consumer(request):
            selected_name = "shared"
            request.getfixturevalue(selected_name)
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_root_scope.py",
        """
        def test_root_scope(root_public):
            assert root_public == "root:case"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/_data/ignored.py",
        """
        def deliberately_unparseable(
        """,
    )
    _write_source(
        root,
        "dev/quality/test_dev_fixture.py",
        """
        import pytest_asyncio

        @pytest_asyncio.fixture(scope="module")
        def development_resource():
            return "development"

        def test_development_resource(development_resource):
            assert development_resource == "development"
        """,
    )
    _write_source(
        root,
        "packaging/test_packaging_fixture.py",
        """
        import pytest

        @pytest.fixture
        def packaging_resource():
            return "packaging"

        def test_packaging_resource(packaging_resource):
            assert packaging_resource == "packaging"
        """,
    )


def test_census_records_fixture_identity_constraints_and_topology(tmp_path: Path) -> None:
    """A complete tree retains fixture constraints instead of collapsing them to names."""
    root = tmp_path / "fixture-tree"
    _write_complete_fixture_tree(root)

    result = census(root)
    records = {record.effective_name: record for record in result.fixtures}

    assert {"conftest.py", "src/cadrumo/provider.py"}.issubset(result.sources)
    assert any(path.startswith("dev/") for path in result.sources)
    assert any(path.startswith("packaging/") for path in result.sources)
    assert not any(path.startswith("src/cadrumo/_data/") for path in result.sources)
    assert "ignored" not in records

    root_public = records["root_public"]
    assert root_public.path == "conftest.py"
    assert (root_public.line, root_public.column, root_public.qualname) == (13, 0, "root_guard")
    assert root_public.function_name == "root_guard"
    assert root_public.owner_kind == "conftest"
    assert root_public.decorator.callee == "pytest.fixture"
    assert root_public.decorator.form == "call"
    assert root_public.decorator.expression == (
        "pt.fixture(name='root_public', scope='session', autouse=True, params=('case',))"
    )
    assert root_public.decorator.scope == "session"
    assert root_public.decorator.scope_expression == "'session'"
    assert root_public.decorator.autouse is True
    assert root_public.decorator.autouse_expression == "True"
    assert root_public.decorator.name_expression == "'root_public'"
    assert root_public.decorator.params_expression == "('case',)"
    assert root_public.decorator.keyword_arguments == (
        ("autouse", "True"),
        ("name", "'root_public'"),
        ("params", "('case',)"),
        ("scope", "'session'"),
    )
    assert root_public.dependencies == ("root_dependency", "request", "declared_dependency")
    assert [
        (parameter.name, parameter.kind, parameter.annotation, parameter.default)
        for parameter in root_public.parameters
    ] == [
        ("root_dependency", "positional", None, None),
        ("request", "positional", None, None),
    ]
    assert root_public.body_ast_format == "python-ast-dump-v1"
    assert "Return(value=JoinedStr(" in root_public.normalized_body
    assert len(root_public.normalized_body_sha256) == 64
    assert (
        "src/cadrumo/test_root_scope.py",
        "test_root_scope",
        "autouse",
    ) in {(row.path, row.qualname, row.via) for row in root_public.autouse_reach}

    shared = records["shared"]
    assert shared.path == "src/cadrumo/provider.py"
    assert (shared.line, shared.column, shared.qualname) == (4, 0, "shared")
    assert shared.decorator.callee == "pytest.fixture"
    assert shared.decorator.form == "bare"
    assert shared.decorator.scope == "function"
    assert shared.decorator.autouse is False
    assert {
        (binding.path, binding.line, binding.provider_module, binding.provider_name, binding.bound_name)
        for binding in shared.imported_bindings
    } >= {
        ("src/cadrumo/test_usage.py", 1, "cadrumo.provider", "shared", "imported_shared"),
        ("src/cadrumo/nested/conftest.py", 1, "cadrumo.provider", "shared", "inherited_shared"),
    }
    assert {
        (consumer.path, consumer.line, consumer.qualname, consumer.kind, consumer.via) for consumer in shared.consumers
    } >= {
        ("src/cadrumo/provider.py", 11, "test_provider_consumer", "test", "parameter"),
        ("src/cadrumo/test_usage.py", 3, "test_imported_consumer", "test", "imported-parameter"),
        (
            "src/cadrumo/nested/test_descendant.py",
            4,
            "test_inherited_usefixtures",
            "test",
            "imported-usefixtures",
        ),
        (
            "src/cadrumo/nested/test_descendant.py",
            7,
            "test_inherited_static_request",
            "test",
            "imported-getfixturevalue",
        ),
    }

    conftest_autouse = records["conftest_autouse"]
    assert conftest_autouse.decorator.autouse is True
    assert (
        "src/cadrumo/nested/test_descendant.py",
        10,
        "test_inherited_autouse_reach",
        "test",
        "imported-autouse",
    ) in {
        (consumer.path, consumer.line, consumer.qualname, consumer.kind, consumer.via)
        for consumer in conftest_autouse.autouse_reach
    }

    development_resource = records["development_resource"]
    assert development_resource.path == "dev/quality/test_dev_fixture.py"
    assert development_resource.decorator.callee == "pytest_asyncio.fixture"
    assert development_resource.decorator.scope == "module"

    packaging_resource = records["packaging_resource"]
    assert packaging_resource.path == "packaging/test_packaging_fixture.py"
    assert packaging_resource.decorator.callee == "pytest.fixture"
    assert packaging_resource.decorator.form == "bare"

    assert [
        (request.path, request.line, request.qualname, request.expression)
        for request in result.dynamic_fixture_requests
    ] == [
        ("src/cadrumo/test_usage.py", 8, "test_dynamic_consumer", "selected_name"),
    ]


def test_real_tree_source_universe_retains_each_required_root() -> None:
    """The live tree smoke proves the census starts from every maintained root."""
    repository_root = Path(__file__).resolve().parents[3]
    sources = iter_source_files(repository_root)
    relative_sources = {path.relative_to(repository_root).as_posix() for path in sources}

    assert "conftest.py" in relative_sources
    assert any(path.startswith("src/") for path in relative_sources)
    assert any(path.startswith("dev/") for path in relative_sources)
    assert any(path.startswith("packaging/") for path in relative_sources)
    assert not any(path.startswith("src/cadrumo/_data/") for path in relative_sources)


@pytest.mark.parametrize("missing_root", ("src", "dev", "packaging"))
def test_census_refuses_when_a_required_source_root_is_missing(tmp_path: Path, missing_root: str) -> None:
    """Missing a governed root is an incomplete fixture universe, never an empty one."""
    root = tmp_path / "missing-root"
    _write_source(root, "conftest.py", "pass\n")
    for source_root in ("src", "dev", "packaging"):
        if source_root != missing_root:
            (root / source_root).mkdir(parents=True)

    with pytest.raises(FixtureCensusError, match=rf"requires source root '{missing_root}'"):
        census(root)


def test_census_refuses_when_root_conftest_is_missing(tmp_path: Path) -> None:
    """The root configuration is part of the census universe and cannot disappear."""
    root = tmp_path / "missing-conftest"
    for source_root in ("src", "dev", "packaging"):
        (root / source_root).mkdir(parents=True)

    with pytest.raises(FixtureCensusError, match=re.escape("requires 'conftest.py'")):
        census(root)


def test_census_refuses_unparseable_included_python(tmp_path: Path) -> None:
    """An included syntax failure cannot yield a partial fixture report."""
    root = tmp_path / "unparseable"
    _write_source(root, "conftest.py", "pass\n")
    for source_root in ("src", "dev", "packaging"):
        (root / source_root).mkdir(parents=True)
    _write_source(root, "src/cadrumo/broken.py", "def incomplete(\n")

    with pytest.raises(
        FixtureCensusError,
        match=re.escape("unparseable included Python src/cadrumo/broken.py"),
    ):
        census(root)


def test_source_reader_refuses_an_unreadable_filesystem_entry(tmp_path: Path) -> None:
    """Reader failures aggregate as a census error instead of skipping the source."""
    unreadable_source = tmp_path / "unreadable.py"
    unreadable_source.mkdir()

    with pytest.raises(
        FixtureCensusError,
        match=re.escape("unreadable included Python unreadable.py"),
    ):
        _read_trees((unreadable_source,), tmp_path)

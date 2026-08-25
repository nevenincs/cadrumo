"""Real-filesystem checks for the fixture-census authority."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from textwrap import dedent

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT
from ..fixture_census import FixtureCensusError, _read_trees, census, iter_source_files
from ..fixture_ownership import (
    FixtureOwnershipError,
    build_manifest,
    check_manifest,
    fixture_id,
    parse_manifest,
    validate_manifest,
    write_manifest,
)

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


def _write_repeated_fixture_tree(root: Path, *, second_body: str) -> None:
    """Create two same-name fixtures whose body relationship is caller-controlled."""
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/first.py",
        """
        import pytest

        @pytest.fixture
        def shared_resource():
            return "first"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/second.py",
        f"""
        import pytest

        @pytest.fixture
        def shared_resource():
            {second_body}
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)


def test_fixture_body_digest_ignores_leading_docstrings(tmp_path: Path) -> None:
    """Fixture prose cannot split otherwise identical executable bodies."""
    root = tmp_path / "fixture-docstrings"
    _write_source(root, "conftest.py", "pass\n")
    for module_name, docstring in (("first", "first prose"), ("second", "second prose")):
        _write_source(
            root,
            f"src/cadrumo/{module_name}.py",
            f'''
            import pytest

            @pytest.fixture
            def shared_resource():
                """{docstring}"""
                return "same"
            ''',
        )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)
    payload = build_manifest(result)

    assert len({record.normalized_body_sha256 for record in result.fixtures}) == 1
    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}


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


def test_class_level_usefixtures_counts_as_a_consumer_of_the_named_fixture(tmp_path: Path) -> None:
    """A class mark reaches every test it holds, including nested classes.

    Reading only function decorators made these requests invisible, so a
    fixture requested ONLY through a class mark reported zero consumers. That
    is not a quiet undercount: zero consumers reads as dead code, and the
    fixture it was found on is live in two suites. The unmarked function is
    asserted too, because a walk that attributed the mark to everything in the
    module would satisfy the first assertion and be just as wrong.
    """
    root = tmp_path / "class-usefixtures"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/test_class_mark.py",
        """
        import pytest

        @pytest.fixture
        def widget():
            return 1

        @pytest.mark.usefixtures("widget")
        class TestOuter:
            def test_inside(self):
                pass

            class TestInner:
                def test_nested(self):
                    pass

        def test_outside():
            pass
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    (record,) = census(root).fixtures

    assert {consumer.qualname for consumer in record.consumers} == {
        "TestOuter.test_inside",
        "TestOuter.TestInner.test_nested",
    }
    assert all(consumer.via == "usefixtures" for consumer in record.consumers)


def test_imported_effective_name_fixture_preserves_binding_and_reach(tmp_path: Path) -> None:
    """Imports resolve Python symbols while pytest retains explicit fixture names."""
    root = tmp_path / "effective-name-import"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/provider.py",
        """
        import pytest

        @pytest.fixture(name="public_resource", autouse=True)
        def implementation():
            return "resource"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_consumer.py",
        """
        from cadrumo.provider import implementation as imported_implementation

        def test_explicit(public_resource):
            assert public_resource == "resource"

        def test_autouse_reach():
            pass
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    (record,) = census(root).fixtures

    assert [(binding.provider_name, binding.bound_name, binding.path) for binding in record.imported_bindings] == [
        ("implementation", "public_resource", "src/cadrumo/test_consumer.py")
    ]
    assert ("test_explicit", "imported-parameter") in {
        (consumer.qualname, consumer.via) for consumer in record.consumers
    }
    assert {consumer.qualname for consumer in record.autouse_reach} == {
        "test_autouse_reach",
        "test_explicit",
    }


def test_real_tree_source_universe_retains_each_required_root() -> None:
    """The live tree smoke proves the census starts from every maintained root."""
    repository_root = REPO_ROOT
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


def test_ownership_manifest_refuses_unclassified_repeated_fixtures(tmp_path: Path) -> None:
    """A repeated family needs an explicit semantic disposition before rendering."""
    root = tmp_path / "unclassified"
    _write_repeated_fixture_tree(root, second_body='return "second"')

    result = census(root)

    with pytest.raises(FixtureOwnershipError, match="unclassified repeated fixtures"):
        build_manifest(result, repeated_dispositions={})


def test_ownership_manifest_accepts_explicitly_adjudicated_divergent_family(tmp_path: Path) -> None:
    """A reviewed same-name family with different bodies remains valid and visible."""
    root = tmp_path / "divergent"
    _write_repeated_fixture_tree(root, second_body='return "second"')
    result = census(root)
    dispositions = {fixture_id(record): "retained-divergent" for record in result.fixtures}

    payload = build_manifest(result, repeated_dispositions=dispositions)

    validate_manifest(result, payload)
    assert payload["manifest"]["retained_divergent_count"] == 2


def test_ownership_manifest_rejects_proven_substitutable_duplicate(tmp_path: Path) -> None:
    """An explicitly substitutable equal fixture family keeps the gate red."""
    root = tmp_path / "substitutable"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    result = census(root)
    dispositions = {fixture_id(record): "substitutable-duplicate" for record in result.fixtures}
    payload = build_manifest(result, repeated_dispositions=dispositions)

    with pytest.raises(FixtureOwnershipError, match="substitutable duplicate fixtures remain"):
        validate_manifest(result, payload)


def test_ownership_manifest_rejects_clone_relabelled_divergent(tmp_path: Path) -> None:
    """A bare divergent label cannot shield an exact unproven clone pair."""
    root = tmp_path / "clone-relabelled-divergent"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    result = census(root)
    dispositions = {fixture_id(record): "retained-divergent" for record in result.fixtures}

    with pytest.raises(FixtureOwnershipError, match="has no evidence"):
        build_manifest(result, repeated_dispositions=dispositions)


def test_ownership_manifest_rejects_identical_local_consumer_clones(tmp_path: Path) -> None:
    """Different local consumer paths are drift evidence, not semantic divergence."""
    root = tmp_path / "local-consumer-clones"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    for module_name, test_name in (("first", "test_first"), ("second", "test_second")):
        _write_source(
            root,
            f"src/cadrumo/{module_name}.py",
            f"""
            import pytest

            @pytest.fixture
            def shared_resource():
                return "first"

            def {test_name}(shared_resource):
                assert shared_resource == "first"
            """,
        )

    payload = build_manifest(census(root))

    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}
    with pytest.raises(FixtureOwnershipError, match="substitutable duplicate fixtures remain"):
        validate_manifest(census(root), payload)


def test_repeated_group_nominates_one_independent_canonical_owner(tmp_path: Path) -> None:
    """Repeated declarations share one nominated owner instead of self-owning each row."""
    root = tmp_path / "canonical-owner"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    result = census(root)
    payload = build_manifest(result)
    rows = payload["fixture"]
    fixture_ids = {row["id"] for row in rows}
    canonical_owners = {row["owner"] for row in rows}

    assert len(canonical_owners) == 1
    assert canonical_owners <= fixture_ids
    assert any(row["owner"] != row["id"] for row in rows)
    assert len({row["ownership_group_id"] for row in rows}) == 1
    assert all(row["ownership_group_member_count"] == 2 for row in rows)

    tampered = {
        "manifest": dict(payload["manifest"]),
        "fixture": [dict(row) for row in rows],
    }
    tampered["fixture"][1]["owner"] = tampered["fixture"][1]["id"]
    with pytest.raises(FixtureOwnershipError, match="does not exactly match"):
        validate_manifest(result, tampered)


def test_import_paths_do_not_prove_fixture_divergence(tmp_path: Path) -> None:
    """Import aliases are preserved topology, not a semantic clone distinction."""
    root = tmp_path / "imported-clones"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    _write_source(
        root,
        "src/cadrumo/test_first.py",
        """
        from cadrumo.first import shared_resource as first_alias

        def test_first(first_alias):
            assert first_alias == "first"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_second.py",
        """
        from cadrumo.second import shared_resource as second_alias

        def test_second(second_alias):
            assert second_alias == "first"
        """,
    )

    result = census(root)
    payload = build_manifest(result)

    assert {
        (binding.provider_name, binding.bound_name)
        for record in result.fixtures
        for binding in record.imported_bindings
    } == {("shared_resource", "first_alias"), ("shared_resource", "second_alias")}
    assert {(consumer.qualname, consumer.via) for record in result.fixtures for consumer in record.consumers} == {
        ("test_first", "imported-parameter"),
        ("test_second", "imported-parameter"),
    }
    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}


def test_decorator_alias_and_keyword_order_do_not_change_fixture_constraints(tmp_path: Path) -> None:
    """Decorator spelling is drift evidence, never semantic lifecycle evidence."""
    root = tmp_path / "decorator-spelling"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/first.py",
        """
        import pytest

        @pytest.fixture(scope="module", autouse=True)
        def shared_resource():
            return "same"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/second.py",
        """
        from pytest import fixture as fx

        @fx(autouse=True, scope="module")
        def shared_resource():
            return "same"
        """,
    )
    _write_source(
        root,
        "src/cadrumo/third.py",
        """
        import pytest_asyncio

        @pytest_asyncio.fixture(autouse=True, scope="module")
        def shared_resource():
            return "same"
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)
    payload = build_manifest(result)

    assert {record.decorator.expression for record in result.fixtures} == {
        "fx(autouse=True, scope='module')",
        "pytest.fixture(scope='module', autouse=True)",
        "pytest_asyncio.fixture(autouse=True, scope='module')",
    }
    assert len({row["constraints_sha256"] for row in payload["fixture"]}) == 1
    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}


def test_class_local_import_shadows_do_not_prove_semantic_divergence(tmp_path: Path) -> None:
    """Distinct lexical class reach is topology and cannot retain identical fixtures."""
    root = tmp_path / "class-overrides"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/providers.py",
        """
        import pytest

        @pytest.fixture(autouse=True)
        def first_state():
            return "first"

        @pytest.fixture(autouse=True)
        def second_state():
            return "second"
        """,
    )
    for module_name, class_name, fixture_name in (
        ("first", "TestFirst", "first_state"),
        ("second", "TestSecond", "second_state"),
    ):
        _write_source(
            root,
            f"src/cadrumo/test_{module_name}.py",
            f"""
            from pathlib import Path
            import pytest
            from cadrumo.providers import {fixture_name}

            class {class_name}:
                @pytest.fixture(autouse=True)
                def {fixture_name}(self, tmp_path: Path):
                    yield tmp_path
            """,
        )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    payload = build_manifest(census(root))
    class_rows = [row for row in payload["fixture"] if "Test" in str(row["id"])]

    assert len(class_rows) == 2
    assert {row["disposition"] for row in class_rows} == {"substitutable-duplicate"}
    assert {row["divergence_kind"] for row in class_rows} == {""}


def test_class_local_clones_without_import_shadows_remain_substitutable(tmp_path: Path) -> None:
    """Class placement alone cannot shield identical unrelated fixture bodies."""
    root = tmp_path / "unshadowed-class-clones"
    _write_source(root, "conftest.py", "pass\n")
    for module_name, class_name, fixture_name in (
        ("first", "TestFirst", "first_state"),
        ("second", "TestSecond", "second_state"),
    ):
        _write_source(
            root,
            f"src/cadrumo/test_{module_name}.py",
            f"""
            import pytest

            class {class_name}:
                @pytest.fixture
                def {fixture_name}(self):
                    return "same"
            """,
        )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    payload = build_manifest(census(root))

    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}


@pytest.mark.parametrize("second_docstring", ("second documentation", "first documentation"))
def test_owner_global_helper_docstrings_do_not_prove_divergence(
    tmp_path: Path,
    second_docstring: str,
) -> None:
    """Helper prose and formatting cannot distinguish executable fixture owners."""
    root = tmp_path / "helper-docstrings"
    _write_source(root, "conftest.py", "pass\n")
    for relative_root in ("dev", "packaging"):
        (root / relative_root).mkdir(parents=True)
    for module_name, docstring in (
        ("first", "first documentation"),
        ("second", second_docstring),
    ):
        _write_source(
            root,
            f"src/cadrumo/{module_name}.py",
            f'''\
            import pytest

            def _value() -> str:
                """{docstring}"""
                return "same"

            @pytest.fixture
            def shared_resource():
                return _value()
            ''',
        )

    payload = build_manifest(census(root))

    assert {row["disposition"] for row in payload["fixture"]} == {"substitutable-duplicate"}


def test_owner_global_recursion_detects_executable_helper_difference(tmp_path: Path) -> None:
    """A referenced helper's executable value is substantive owner-global evidence."""
    root = tmp_path / "helper-semantics"
    _write_source(root, "conftest.py", "pass\n")
    for relative_root in ("dev", "packaging"):
        (root / relative_root).mkdir(parents=True)
    for module_name, value in (("first", "first"), ("second", "second")):
        _write_source(
            root,
            f"src/cadrumo/{module_name}.py",
            f'''\
            import pytest

            VALUE = "{value}"

            def _value():
                return VALUE

            @pytest.fixture
            def shared_resource():
                return _value()
            ''',
        )

    payload = build_manifest(census(root))

    assert {row["disposition"] for row in payload["fixture"]} == {"retained-divergent"}
    assert {row["divergence_kind"] for row in payload["fixture"]} == {"owner-global"}


def test_ownership_manifest_rejects_live_fixture_drift(tmp_path: Path) -> None:
    """A newly added fixture is unclassified until semantic review refreshes ownership."""
    root = tmp_path / "drift"
    _write_source(root, "conftest.py", "pass\n")
    for source_root in ("src", "dev", "packaging"):
        (root / source_root).mkdir(parents=True)
    initial = census(root)
    payload = build_manifest(initial, repeated_dispositions={})
    _write_source(
        root,
        "src/cadrumo/test_new_fixture.py",
        """
        import pytest

        @pytest.fixture
        def newly_unclassified():
            return object()
        """,
    )

    with pytest.raises(FixtureOwnershipError, match="does not exactly match"):
        validate_manifest(census(root), payload)


def test_ownership_manifest_rejects_direct_consumer_topology_drift(tmp_path: Path) -> None:
    """A new direct consumer changes canonical row topology and invalidates ownership."""
    root = tmp_path / "consumer-drift"
    _write_repeated_fixture_tree(root, second_body='return "second"')
    initial = census(root)
    dispositions = {fixture_id(record): "retained-divergent" for record in initial.fixtures}
    payload = build_manifest(initial, repeated_dispositions=dispositions)
    _write_source(
        root,
        "src/cadrumo/first.py",
        """
        import pytest

        @pytest.fixture
        def shared_resource():
            return "first"

        def test_shared_resource(shared_resource):
            assert shared_resource == "first"
        """,
    )

    with pytest.raises(FixtureOwnershipError, match="does not exactly match"):
        validate_manifest(census(root), payload)


def test_stable_writer_writes_and_checks_one_real_tree(tmp_path: Path) -> None:
    """The supported writer and checker share the guarded production generator."""
    root = tmp_path / "stable-write"
    manifest_path = tmp_path / "fixture-ownership.toml"
    _write_repeated_fixture_tree(root, second_body='return "second"')
    manifest_path.write_bytes(b"previous manifest\n")

    written = write_manifest(root, manifest_path)

    assert parse_manifest(manifest_path) == written
    assert check_manifest(root, manifest_path) == written
    assert not scan_directory(tmp_path, pattern=".fixture-ownership.toml.*.tmp")


def test_stable_writer_refuses_substitutes_and_preserves_existing_bytes(tmp_path: Path) -> None:
    """Substitutable declarations fail before atomic replacement starts."""
    root = tmp_path / "substitute-write"
    manifest_path = tmp_path / "fixture-ownership.toml"
    _write_repeated_fixture_tree(root, second_body='return "first"')
    previous = b"trusted previous manifest\n"
    manifest_path.write_bytes(previous)

    with pytest.raises(FixtureOwnershipError, match="substitutable duplicate fixtures remain"):
        write_manifest(root, manifest_path)

    assert manifest_path.read_bytes() == previous
    assert not scan_directory(tmp_path, pattern=".fixture-ownership.toml.*.tmp")


def test_stable_writer_refuses_source_mutation_during_evidence_reads(tmp_path: Path) -> None:
    """Concurrent real-file mutation cannot produce a mixed census/global snapshot."""
    root = tmp_path / "moving-write"
    manifest_path = tmp_path / "fixture-ownership.toml"
    _write_repeated_fixture_tree(root, second_body='return "second"')
    for index in range(200):
        _write_source(root, f"dev/padding_{index}.py", f"VALUE = {index}\n")
    moving = root / "dev/moving.py"
    moving.write_text("VALUE = 0\n", encoding="utf-8")
    previous = b"trusted previous manifest\n"
    manifest_path.write_bytes(previous)
    stop = threading.Event()

    def mutate_source() -> None:
        revision = 1
        while not stop.is_set():
            moving.write_text(f"VALUE = {revision}\n", encoding="utf-8")
            revision += 1

    worker = threading.Thread(target=mutate_source)
    worker.start()
    try:
        with pytest.raises(FixtureOwnershipError, match="source universe changed") as error_info:
            write_manifest(root, manifest_path)
    finally:
        stop.set()
        worker.join()

    diagnostic = str(error_info.value)
    match = re.search(
        r'\{"after_sha256":"([0-9a-f]{64})","before_sha256":"([0-9a-f]{64})",'
        r'"path":"dev/moving\.py","status":"changed"\}',
        diagnostic,
    )
    assert match is not None, diagnostic
    assert match.group(1) != match.group(2)
    assert "VALUE =" not in diagnostic
    assert manifest_path.read_bytes() == previous
    assert not scan_directory(tmp_path, pattern=".fixture-ownership.toml.*.tmp")


def test_census_reports_resolved_and_unresolved_factory_fixture_candidates(tmp_path: Path) -> None:
    """A factory-returned closure bound at module level is a real fixture the census must see.

    ``bucket_scoped_runtime_profile_fixture`` in the live tree returns a
    nested ``@pytest.fixture`` closure that a consuming test module binds to
    a bare module-level name.  That call assignment carries no decorator of
    its own, so the decorator-only walk that produces ``result.fixtures``
    cannot see it -- it must be reported through a separate, honest channel.
    """
    root = tmp_path / "factory-fixture"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/factory.py",
        """
        import pytest

        def bucket_scoped_runtime_profile_fixture(bucket_id):
            @pytest.fixture(name="_runtime_profile", autouse=True)
            def _bucket_scoped_runtime_profile():
                return bucket_id
            return _bucket_scoped_runtime_profile
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_consumer.py",
        """
        from cadrumo.factory import bucket_scoped_runtime_profile_fixture

        _runtime_profile = bucket_scoped_runtime_profile_fixture("bucket-a")
        _opaque = some_unresolvable_call()

        def test_uses_runtime_profile():
            pass
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)

    # The nested closure itself is still a real decorated fixture def, seen
    # exactly once regardless of the new candidate channel.
    assert result.fixture_count == 1

    # Only the binding provably produced by a factory is a candidate, so the
    # population is what its name claims. The opaque call is a plain value
    # construction as far as this walk can tell.
    (resolved,) = result.factory_fixture_candidates
    assert resolved.bound_name == "_runtime_profile"
    assert resolved.path == "src/cadrumo/test_consumer.py"
    assert resolved.callee_expression == "bucket_scoped_runtime_profile_fixture"
    assert resolved.resolved_factory == "src/cadrumo/factory.py:3:bucket_scoped_runtime_profile_fixture"

    # The unfollowable callee is still reported, as the bound on this walk:
    # a factory reached that way would be invisible, and the count says so.
    assert result.unresolved_call_assignment_count == 1


def test_import_binding_matcher_excludes_a_nested_closure_sharing_a_literal_name(tmp_path: Path) -> None:
    """An import can only bind the module-level def, never a same-named nested closure.

    ``provider.py`` declares two ``@pytest.fixture`` functions literally named
    ``shared_resource``: one at module level, one nested inside a factory. A
    consumer importing ``shared_resource`` from the module gets the
    module-level def, per ordinary Python import semantics -- the nested
    closure is not a module attribute and cannot be imported by that name.
    """
    root = tmp_path / "nested-name-collision"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/provider.py",
        """
        import pytest

        @pytest.fixture
        def shared_resource():
            return "module-level"

        def build_shared_resource_fixture():
            @pytest.fixture
            def shared_resource():
                return "nested-closure"
            return shared_resource
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_consumer.py",
        """
        from cadrumo.provider import shared_resource

        def test_consumes_shared_resource(shared_resource):
            assert shared_resource == "module-level"
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)
    records = {record.qualname: record for record in result.fixtures}

    module_level = records["shared_resource"]
    nested_closure = records["build_shared_resource_fixture.shared_resource"]

    assert {(binding.path, binding.bound_name) for binding in module_level.imported_bindings} == {
        ("src/cadrumo/test_consumer.py", "shared_resource")
    }
    assert nested_closure.imported_bindings == ()
    assert ("test_consumes_shared_resource", "imported-parameter") in {
        (consumer.qualname, consumer.via) for consumer in module_level.consumers
    }
    assert nested_closure.consumers == ()


def test_live_fixture_ownership_manifest_is_complete_and_has_no_substitutable_duplicate() -> None:
    """The checked manifest exactly classifies the stable production census."""
    repository_root = REPO_ROOT
    check_manifest(repository_root)


def _write_factory_binding_tree(root: Path, *, first_argument: str, second_argument: str) -> None:
    """Create one factory and two module-level bindings of it, arguments caller-controlled."""
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/factory.py",
        """
        import pytest

        def make_thing_fixture(label):
            @pytest.fixture
            def _thing():
                return label
            return _thing
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_first.py",
        f"""
        from cadrumo.factory import make_thing_fixture

        _thing = make_thing_fixture("{first_argument}")

        def test_first(_thing):
            assert _thing
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_second.py",
        f"""
        from cadrumo.factory import make_thing_fixture

        _thing = make_thing_fixture("{second_argument}")

        def test_second(_thing):
            assert _thing
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)


def test_factory_bound_fixture_appears_as_a_classified_manifest_row(tmp_path: Path) -> None:
    """A binding the decorator-only walk cannot see still reaches a real disposition."""
    root = tmp_path / "factory-single-binding"
    _write_source(root, "conftest.py", "pass\n")
    _write_source(
        root,
        "src/cadrumo/factory.py",
        """
        import pytest

        def make_thing_fixture(label):
            @pytest.fixture
            def _thing():
                return label
            return _thing
        """,
    )
    _write_source(
        root,
        "src/cadrumo/test_consumer.py",
        """
        from cadrumo.factory import make_thing_fixture

        _thing = make_thing_fixture("solo")

        def test_uses_thing(_thing):
            assert _thing == "solo"
        """,
    )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)
    (candidate,) = result.factory_fixture_candidates
    binding_id = f"{candidate.path}:{candidate.line}:{candidate.bound_name}"

    payload = build_manifest(result)

    rows_by_id = {row["id"]: row for row in payload["fixture"]}
    assert binding_id in rows_by_id
    row = rows_by_id[binding_id]
    assert row["disposition"] in {"retained-current-owner", "retained-divergent", "substitutable-duplicate"}
    assert row["effective_name"] == "_thing"
    assert row["scope"] == "function"
    assert row["autouse"] is False
    validate_manifest(result, payload)


def test_factory_bindings_with_different_arguments_are_not_substitutable_duplicates(tmp_path: Path) -> None:
    """Two produced fixtures of the same factory with different inputs are distinct fixtures."""
    root = tmp_path / "factory-divergent-arguments"
    _write_factory_binding_tree(root, first_argument="alpha", second_argument="beta")

    result = census(root)
    payload = build_manifest(result)

    binding_ids = {
        f"{candidate.path}:{candidate.line}:{candidate.bound_name}" for candidate in result.factory_fixture_candidates
    }
    assert len(binding_ids) == 2
    binding_rows = [row for row in payload["fixture"] if row["id"] in binding_ids]
    assert len(binding_rows) == 2
    assert {row["disposition"] for row in binding_rows} == {"retained-divergent"}
    assert {row["divergence_kind"] for row in binding_rows} == {"body"}
    assert len({row["body_sha256"] for row in binding_rows}) == 2
    validate_manifest(result, payload)


def test_factory_bindings_with_identical_arguments_are_flagged_substitutable(tmp_path: Path) -> None:
    """Two produced fixtures of the same factory with the same input really are interchangeable."""
    root = tmp_path / "factory-identical-arguments"
    _write_factory_binding_tree(root, first_argument="shared", second_argument="shared")

    result = census(root)
    payload = build_manifest(result)

    binding_ids = {
        f"{candidate.path}:{candidate.line}:{candidate.bound_name}" for candidate in result.factory_fixture_candidates
    }
    assert len(binding_ids) == 2
    binding_rows = [row for row in payload["fixture"] if row["id"] in binding_ids]
    assert len(binding_rows) == 2
    assert {row["disposition"] for row in binding_rows} == {"substitutable-duplicate"}
    assert len({row["body_sha256"] for row in binding_rows}) == 1
    with pytest.raises(FixtureOwnershipError, match="substitutable duplicate fixtures remain"):
        validate_manifest(result, payload)


def test_census_reports_one_body_reached_through_several_names(tmp_path: Path) -> None:
    """A behaviour copied under a fresh name each time must still be countable.

    This is the duplication a name-keyed comparison cannot express: grouping by
    name asks "is this name declared twice", and a renamed copy answers no every
    time, while a search for any one of those names returns a single site and
    reads as unique. Keying on the body inverts the question.
    """
    root = tmp_path / "aliased-behaviour"
    _write_source(root, "conftest.py", "pass\n")
    for module_name, fixture_name in (
        ("first", "isolated_backend"),
        ("second", "active_runtime"),
        ("third", "bucket"),
    ):
        _write_source(
            root,
            f"src/cadrumo/{module_name}.py",
            f"""
            import pytest

            @pytest.fixture
            def {fixture_name}():
                return "same behaviour"
            """,
        )
    (root / "dev").mkdir(parents=True)
    (root / "packaging").mkdir(parents=True)

    result = census(root)

    assert result.aliased_behaviour_count == 1
    (behaviour,) = result.aliased_behaviours
    assert behaviour.effective_names == ("active_runtime", "bucket", "isolated_backend")
    assert len(behaviour.sites) == 3


def test_census_does_not_report_a_repeated_name_as_an_aliased_behaviour(tmp_path: Path) -> None:
    """The discriminating control: same name twice is duplication, not aliasing.

    Without this, the detector above would pass just as well if it reported
    every repeated body regardless of naming -- which would drown the aliasing
    signal in the ordinary same-name duplication the manifest already handles.
    """
    root = tmp_path / "repeated-name"
    _write_repeated_fixture_tree(root, second_body='return "first"')

    result = census(root)

    assert len(result.fixtures) == 2
    assert len({record.normalized_body_sha256 for record in result.fixtures}) == 1
    assert result.aliased_behaviour_count == 0

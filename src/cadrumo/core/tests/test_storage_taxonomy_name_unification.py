"""The bucket layout has exactly one name per directory.

Two names -- the bucket container and the per-bucket database directory -- were
re-typed as inline literals in core modules because the constants declaring them
lived in the adapter layer, which core cannot import without inverting the
hexagonal direction. The duplication was a symptom of the names sitting in the
wrong layer, so no tidying could remove it. Now that the names live in core,
these modules read the declaration and the copies are gone.

The state-root cases below cover the injection seam the resolver already
provides: it takes its whole platform context as an argument, so a test hands
over a synthetic one rather than mutating the ambient process around the call.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._config_state_root import (
    BUCKET_DB_DIRNAME,
    BUCKETS_DIRNAME,
    PRODUCT_DATABASE_FILENAME,
    FormerProductStateError,
    StateRootInputs,
    refuse_former_product_database,
    resolve_state_root,
)
from .._config_storage_route import classify_storage_route_for_settings
from .._storage_taxonomy import StorageCategory, storage_location
from ..config import Settings, StorageRouteKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROUTE_MODULE = Path(__file__).resolve().parent.parent / "_config_storage_route.py"
_STATE_ROOT_MODULE = Path(__file__).resolve().parent.parent / "_config_state_root.py"


def test_the_core_constants_are_the_taxonomy_not_a_second_copy() -> None:
    """A copy that merely agrees today is still a copy."""
    assert storage_location(StorageCategory.BUCKETS).subpath == BUCKETS_DIRNAME
    assert storage_location(StorageCategory.BUCKET_DATABASE).subpath == BUCKET_DB_DIRNAME


def _string_literals(module: Path) -> set[str]:
    """Return every string constant in ``module`` that is not a docstring."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstrings
    }


@pytest.mark.parametrize("module", [_ROUTE_MODULE, _STATE_ROOT_MODULE], ids=["storage_route", "state_root"])
def test_no_core_module_re_types_a_governed_layout_name(module: Path) -> None:
    """The literals are deleted, not merely pinned.

    An AST walk rather than a text scan, because both names appear in prose here
    -- including in this file's own explanation of why they must not appear as
    code. A text scanner would have to special-case that; this cannot produce
    the error at all.
    """
    literals = _string_literals(module)
    assert literals, "the module must contain some string constants, or this asserts nothing"
    for governed in (BUCKETS_DIRNAME, BUCKET_DB_DIRNAME):
        assert governed not in literals, (
            f"{module.name} re-types the governed layout name {governed!r}; read the taxonomy instead"
        )


def test_the_route_classifier_still_recognises_a_bucket_database(tmp_path: Path) -> None:
    """Positive control: deleting the literals must not delete the recognition.

    A classifier that stopped matching would not raise -- it returns an empty
    bucket id, and the caller reads that as "not a bucket route". The failure
    would be silent, so it is asserted directly.
    """
    root = tmp_path / "state"
    database = root / BUCKETS_DIRNAME / "primary" / BUCKET_DB_DIRNAME / PRODUCT_DATABASE_FILENAME
    database.parent.mkdir(parents=True)
    settings = Settings(cadrumo_local_storage_root=root, cadrumo_active_profile="primary")

    classification = classify_storage_route_for_settings(settings)

    assert classification.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert classification.bucket_id == "primary"


def test_the_retired_database_refusal_still_finds_the_bucket_tree(tmp_path: Path) -> None:
    """The refusal walks the same governed layout it always did."""
    root = tmp_path / "state"
    retired = root / BUCKETS_DIRNAME / "primary" / BUCKET_DB_DIRNAME / "aeat.db"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(b"not opened")

    with pytest.raises(FormerProductStateError):
        refuse_former_product_database(root, bucket_id="primary")


def _synthetic_inputs(home: Path) -> StateRootInputs:
    return StateRootInputs(platform="linux", environ={"XDG_DATA_HOME": str(home / "share")}, home=home)


def test_root_resolution_is_a_pure_function_of_its_supplied_inputs(tmp_path: Path) -> None:
    """The platform context is passed in, not read from the ambient process.

    This is the dependency-injection seam the resolver already has, and it is
    the one a test should reach for: a synthetic platform is constructed and
    handed over, rather than simulated by mutating ``os.environ`` and
    ``sys.platform`` around the call.
    """
    resolution = resolve_state_root(_synthetic_inputs(tmp_path))

    assert resolution.storage_root == tmp_path / "share" / "cadrumo" / "storage"
    assert resolution.platform_user_data_root == tmp_path / "share" / "cadrumo"


def test_the_resolver_reads_nothing_beyond_what_it_was_given(tmp_path: Path) -> None:
    """Positive control: two different contexts must produce two different roots.

    Without this, a resolver that ignored its argument and read the ambient
    process would satisfy the assertion above on any machine whose real
    platform happened to match.
    """
    first = resolve_state_root(_synthetic_inputs(tmp_path / "first"))
    second = resolve_state_root(_synthetic_inputs(tmp_path / "second"))

    assert first.storage_root != second.storage_root

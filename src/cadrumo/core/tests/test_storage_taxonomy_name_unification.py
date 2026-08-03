"""The bucket layout has one name, and the platform context has one seam.

Two names -- the bucket container and the per-bucket database directory -- were
re-typed as inline literals in core modules because the constants declaring them
lived in the adapter layer, which core cannot import without inverting the
hexagonal direction. The duplication was a symptom of the names sitting in the
wrong layer, so no tidying could remove it. Now that the names live in core,
these modules read the declaration and the copies are gone.

The state-root seam is the companion fix: resolution was already a pure function
of its inputs, but nothing above it could supply them, so a test could pin a
synthetic platform only by mutating the ambient process.
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
    current_state_root_inputs,
    default_storage_root,
    override_state_root_inputs,
    refuse_former_product_database,
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


def test_the_seam_pins_the_platform_context_without_touching_the_process(tmp_path: Path) -> None:
    """A synthetic platform is supplied, not simulated by mutating the process."""
    inputs = _synthetic_inputs(tmp_path)

    with override_state_root_inputs(inputs) as pinned:
        assert pinned is inputs
        assert current_state_root_inputs() is inputs
        assert default_storage_root() == tmp_path / "share" / "cadrumo" / "storage"


def test_omitting_the_seam_changes_nothing(tmp_path: Path) -> None:
    """The seam defaults to live capture, so production behaviour is untouched.

    Asserted by exiting the block: the pinned context must not survive it, or
    every later resolution in the process would silently read a test's platform.
    """
    live_before = default_storage_root()

    with override_state_root_inputs(_synthetic_inputs(tmp_path)):
        assert default_storage_root() != live_before

    assert default_storage_root() == live_before
    assert current_state_root_inputs().platform, "live capture must resume outside the block"

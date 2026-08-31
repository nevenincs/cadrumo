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

The journal-repository case is a different flavor of the same duplication.
``application/journal_repository.py`` is not blocked by the hexagonal
direction -- application may import core freely -- so its ``"buckets"``
literal was plain drift rather than a layering symptom, found once the new
directory-agreement gate made every hand-typed layout name suspect. Included
here because the fix and the property this gate proves are identical, whether
the literal's origin was a layering constraint or an oversight.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

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
from ..storage_taxonomy import StorageCategory, storage_location
from ..config import Settings, StorageRouteKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cadrumo.db", "buckets", "db"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``root / "cadrumo.db"`` and ``root / "buckets" / "primary" / "db" / "cadrumo.db"``
in ``test_the_database_url_resolves_to_its_pre_migration_shape`` are the
independent on-disk-shape oracle for the pre-migration URL join; see that
test's own docstring for why re-deriving them from the accessor would let the
accessor and the validator drift together undetected.
"""

_ROUTE_MODULE = Path(__file__).resolve().parent.parent / "_config_storage_route.py"
_STATE_ROOT_MODULE = Path(__file__).resolve().parent.parent / "_config_state_root.py"
_SETTINGS_MODULE = Path(__file__).resolve().parent.parent / "config.py"
_MASTER_KEY_MODULE = (
    Path(__file__).resolve().parents[2] / "adapters" / "persistence" / "storage" / "master_key" / "_master_key.py"
)
_JOURNAL_REPOSITORY_MODULE = Path(__file__).resolve().parents[2] / "application" / "journal_repository.py"


def test_the_core_constants_are_the_taxonomy_not_a_second_copy() -> None:
    """A copy that merely agrees today is still a copy."""
    assert storage_location(StorageCategory.BUCKETS).subpath == BUCKETS_DIRNAME
    assert storage_location(StorageCategory.BUCKET_DATABASE).subpath == BUCKET_DB_DIRNAME
    assert storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath == PRODUCT_DATABASE_FILENAME


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


@pytest.mark.parametrize(
    "module",
    [_ROUTE_MODULE, _STATE_ROOT_MODULE, _SETTINGS_MODULE, _MASTER_KEY_MODULE, _JOURNAL_REPOSITORY_MODULE],
    ids=["storage_route", "state_root", "settings", "master_key", "journal_repository"],
)
def test_no_production_module_re_types_a_governed_layout_name(module: Path) -> None:
    """The literals are deleted, not merely pinned.

    An AST walk rather than a text scan, because both names appear in prose here
    -- including in this file's own explanation of why they must not appear as
    code. A text scanner would have to special-case that; this cannot produce
    the error at all.
    """
    literals = _string_literals(module)
    assert literals, "the module must contain some string constants, or this asserts nothing"
    for governed in (BUCKETS_DIRNAME, BUCKET_DB_DIRNAME, PRODUCT_DATABASE_FILENAME):
        assert governed not in literals, (
            f"{module.name} re-types the governed layout name {governed!r}; read the taxonomy instead"
        )


def test_the_database_url_resolves_to_its_pre_migration_shape(tmp_path: Path) -> None:
    """The cold-start and per-bucket database URLs are byte-identical to the old hand-built join.

    Both branches of ``Settings._resolve_database_url_for_active_profile`` used
    to join ``cadrumo_local_storage_root`` by hand; this asserts the resolved
    URL against that literal on-disk shape directly -- not against the
    accessor re-applied -- so a member whose subpath silently drifted from
    what the validator used to build would red here even if the accessor and
    the validator drifted together.
    """
    root = tmp_path / "state"

    fallback_settings = Settings(cadrumo_local_storage_root=root)
    expected_fallback = root / "cadrumo.db"
    assert fallback_settings.cadrumo_database_url == f"sqlite:///{expected_fallback.as_posix()}"

    bucket_settings = Settings(cadrumo_local_storage_root=root, cadrumo_active_profile="primary")
    expected_bucket = root / "buckets" / "primary" / "db" / "cadrumo.db"
    assert bucket_settings.cadrumo_database_url == f"sqlite:///{expected_bucket.as_posix()}"


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

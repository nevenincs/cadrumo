"""Tests for the per-bucket directory provisioning surface.

This module uses the taxonomy accessor and bare on-disk literals side by side,
and the split is deliberate.

The **literals** (``"buckets"`` in the layout assertions and in the
occupied-path setup) are the independent oracle. ``bucket_paths`` resolves
through ``storage_location(StorageCategory.BUCKETS)``, so expressing the
expected side through the same accessor would move both sides of the assertion
together -- asserting the accessor equals itself, passing unconditionally, and
defending nothing. The occupied-path case additionally needs the real name to
collide with what production actually creates; a resolved value would still
collide today, but the point of that test is the collision, not the lookup.

The **accessor** calls feed the structural gate below the governed name set it
must not find re-typed in the implementation module. That is a question about
the source, answered from the declaration; the assertions above are a question
about the filesystem, answered from a literal.

A change to a declared subpath **should** red the literal assertions. Do not
migrate them to the accessor.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from ......core.errors.error_codes import ERROR_REGISTRY, build_error_envelope
from ......core.storage_taxonomy import StorageCategory
from ......core.storage_taxonomy_locations import storage_location
from ......tests.bucket_layout import provision_bucket_directory
from ..directory_layout import (
    BucketPaths,
    bucket_paths,
)
from ..errors import BucketAlreadyPresentError, BucketPathTooLongError, BucketValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets", "db", "blobs"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

_LAYOUT_MODULE = Path(__file__).resolve().parent.parent / "directory_layout.py"


def test_provision_creates_two_subdirectories(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    assert paths.bucket_dir == tmp_path / "buckets" / "alpha"
    for subdir, dirname in (
        (paths.db_dir, "db"),
        (paths.blobs_dir, "blobs"),
    ):
        assert subdir == paths.bucket_dir / dirname
        assert subdir.is_dir()


def test_provision_is_fail_closed_on_existing_bucket(tmp_path: Path) -> None:
    provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    assert excinfo.value.bucket_id == "alpha"
    assert excinfo.value.context == {"bucket_id": "alpha"}
    assert str(tmp_path) not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, FileExistsError)


def test_existing_bucket_error_envelope_is_localized_and_redacted(tmp_path: Path) -> None:
    provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "REFUSED_STORAGE_BUCKET_ALREADY_PRESENT"
    assert envelope.message
    assert envelope.context == {"bucket_id": "alpha"}
    assert str(tmp_path) not in envelope.model_dump_json()


def test_buckets_parent_file_collision_is_typed_and_redacted(tmp_path: Path) -> None:
    (tmp_path / "buckets").write_text("not a directory")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    assert excinfo.value.bucket_id == "alpha"
    assert str(tmp_path) not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, FileExistsError)
    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "REFUSED_STORAGE_BUCKET_ALREADY_PRESENT"
    assert str(tmp_path) not in envelope.model_dump_json()


def test_provision_rejects_empty_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="non-empty"):
        provision_bucket_directory(tmp_path, "")


def test_provision_rejects_path_separator_in_bucket_id(tmp_path: Path) -> None:
    for bucket_id in ("a/b", "a\\b"):
        with pytest.raises(BucketValidationError, match="path separator"):
            provision_bucket_directory(tmp_path, bucket_id)


def test_bucket_paths_rejects_a_dot_segment(tmp_path: Path) -> None:
    """DISCRIMINATING: a dot segment carries no separator, so the sibling check passes it.

    ``".."`` is the one that matters. It is not a bucket, and joining it
    resolves ABOVE ``buckets/`` onto the storage root, which is a tree this
    function is not meant to hand anyone paths over.
    """
    for bucket_id in ("..", ".", "..."):
        with pytest.raises(BucketValidationError, match="dot segment"):
            bucket_paths(tmp_path, bucket_id)
        with pytest.raises(BucketValidationError, match="dot segment"):
            provision_bucket_directory(tmp_path, bucket_id)


def test_the_dot_segment_refusal_is_what_keeps_the_join_inside_buckets(tmp_path: Path) -> None:
    """ANTI-VACUITY: pins the escape the refusal prevents, so it cannot be dropped quietly.

    Asserting only that ``".."`` raises says nothing about WHY it must. This
    states the consequence directly: every accepted id resolves underneath
    ``buckets/``, and ``".."`` is excluded from that set precisely because it
    would not.
    """
    buckets_dir = (bucket_paths(tmp_path, "alpha").bucket_dir).parent

    assert bucket_paths(tmp_path, "alpha").bucket_dir.resolve().parent == buckets_dir.resolve()
    # What the refused id would have produced, had it been accepted.
    assert (buckets_dir / "..").resolve() == tmp_path.resolve()
    assert buckets_dir.resolve() != tmp_path.resolve()


def test_a_system_scoped_bucket_id_still_resolves(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the refusal must not have widened onto legitimate ids.

    Not every bucket id is a UUID -- ``system``, ``unsecured`` and
    ``diagnostic-probe`` are real ids in the tree. A guard that refused those
    too would pass the assertions above while breaking the surfaces that use
    them, so the accepting direction is pinned as well.
    """
    for bucket_id in ("system", "unsecured", "diagnostic-probe", "a.b", "..alpha"):
        assert bucket_paths(tmp_path, bucket_id).bucket_dir.name == bucket_id


def test_bucket_paths_is_pure_no_filesystem_side_effects(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    for path in (paths.bucket_dir, paths.db_dir, paths.blobs_dir):
        assert not path.exists()
    assert isinstance(paths, BucketPaths)


def test_bucket_paths_record_is_strict_frozen(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    with pytest.raises(ValidationError):
        paths.__class__.model_validate({**paths.model_dump(), "stowaway": True})


def test_bucket_paths_record_is_immutable(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    with pytest.raises(ValidationError):
        paths.bucket_id = "other"


def test_two_buckets_share_buckets_parent(tmp_path: Path) -> None:
    alpha = provision_bucket_directory(tmp_path, "alpha")
    beta = provision_bucket_directory(tmp_path, "beta")

    assert alpha.bucket_dir.parent == beta.bucket_dir.parent
    assert alpha.bucket_dir.parent == tmp_path / "buckets"


# ── WIN-003 — Windows MAX_PATH (long-path) classification ────────────────────


def test_bucket_path_too_long_error_is_registered_in_error_registry() -> None:
    """BucketPathTooLongError must have a bound ErrorCode in ERROR_REGISTRY."""
    assert "ERROR_STORAGE_BUCKET_PATH_TOO_LONG" in ERROR_REGISTRY


def test_bucket_path_too_long_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a valid, redacted envelope for the new error."""
    err = BucketPathTooLongError(bucket_id="alpha", path="C:\\deep\\buckets\\alpha")
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_STORAGE_BUCKET_PATH_TOO_LONG"
    assert envelope.retryable is False
    assert envelope.context == {"bucket_id": "alpha", "path": "C:\\deep\\buckets\\alpha"}


def test_provision_still_raises_already_present_for_a_real_file_collision(tmp_path: Path) -> None:
    """A genuine FileExistsError collision is NOT misclassified as a long-path failure.

    Regression guard for the new ``except OSError`` branch added alongside
    ``FileExistsError`` handling in :func:`provision_bucket_directory`:
    confirms a real, unrelated collision (the already-fail-closed path)
    still raises :class:`BucketAlreadyPresentError`, never
    :class:`BucketPathTooLongError`.
    """
    provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")
    assert not isinstance(excinfo.value, BucketPathTooLongError)


def _string_literals(module: Path) -> set[str]:
    """Return every string constant in ``module`` that is not a docstring."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
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


def test_no_bare_directory_name_literal_survives_in_the_layout_module() -> None:
    """The bucket/db/blobs directory names are read from the taxonomy, never re-typed.

    An AST walk rather than a text scan, matching the shape of the core
    name-unification gate (``test_storage_taxonomy_name_unification.py``): a
    text scanner would have to special-case this test's own explanation of
    the governed names, which an AST walk cannot produce the error from at
    all.
    """
    literals = _string_literals(_LAYOUT_MODULE)
    assert literals, "the module must contain some string constants, or this asserts nothing"
    governed = (
        storage_location(StorageCategory.BUCKETS).subpath,
        storage_location(StorageCategory.BUCKET_DATABASE).subpath,
        storage_location(StorageCategory.BUCKET_BLOBS).subpath,
    )
    for name in governed:
        assert name not in literals, (
            f"directory_layout.py re-types the governed layout name {name!r}; read the taxonomy instead"
        )

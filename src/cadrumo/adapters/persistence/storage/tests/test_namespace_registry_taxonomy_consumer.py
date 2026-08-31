"""The namespace registry consumes the core storage taxonomy; it is not a second authority.

The bucket and keystore filesystem names were declared here, in the adapter
layer. Core could not import them without inverting the hexagonal direction, so
the core modules needing the same two names re-typed them as inline literals
instead -- unpinned against these declarations, and unfixable where they sat.
The duplication was a symptom of the names living in the wrong layer.

The declaration now lives in core and this module reads it. An adapter
depending on core is the legal direction, so nothing here introduces an upward
import; what it removes is the reason the copies existed.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.storage_taxonomy import StorageCategory, StorageScope
from .....core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location
from .._storage_path_definitions import (
    BUCKET_BLOBS_DIRNAME,
    BUCKET_DATABASE_FILENAME,
    BUCKET_DB_DIRNAME,
    BUCKET_LOCK_FILENAME,
    BUCKET_MANIFEST_FILENAME,
    BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME,
    BUCKETS_DIRNAME,
    KEYSTORE_DIRNAME,
    LOGIN_THROTTLE_FILENAME,
    PROFILE_COMMIT_FILENAME,
    PROFILE_CUSTODY_DIRNAME,
    PROFILE_DATA_DIRNAME,
    PROFILE_PASSWORD_ENVELOPE_FILENAME,
    PROFILE_RECOVERY_ENVELOPE_FILENAME,
    PROFILE_SESSION_FILENAME,
    PROFILE_SESSION_RETIREMENT_FILENAME,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_DEFINITIONS_MODULE = Path(__file__).resolve().parent.parent / "_storage_path_definitions.py"
_REGISTRY_MODULE = Path(__file__).resolve().parent.parent / "_secure_object_namespaces.py"

#: Each exported constant beside the taxonomy member that declares it.
_BOUND_CONSTANTS = (
    (BUCKETS_DIRNAME, StorageCategory.BUCKETS),
    (BUCKET_DB_DIRNAME, StorageCategory.BUCKET_DATABASE),
    (BUCKET_DATABASE_FILENAME, StorageCategory.BUCKET_DATABASE_FILE),
    (BUCKET_BLOBS_DIRNAME, StorageCategory.BUCKET_BLOBS),
    (BUCKET_MANIFEST_FILENAME, StorageCategory.BUCKET_MANIFEST),
    (BUCKET_LOCK_FILENAME, StorageCategory.BUCKET_LOCK),
    (BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME, StorageCategory.BUCKET_OUTPUT_LANGUAGE_HINT),
    (KEYSTORE_DIRNAME, StorageCategory.BUCKET_KEYSTORE),
    (PROFILE_SESSION_FILENAME, StorageCategory.KEYSTORE_PROFILE_SESSION),
    (PROFILE_SESSION_RETIREMENT_FILENAME, StorageCategory.KEYSTORE_PROFILE_SESSION_RETIREMENT),
    (LOGIN_THROTTLE_FILENAME, StorageCategory.KEYSTORE_LOGIN_THROTTLE),
    (PROFILE_CUSTODY_DIRNAME, StorageCategory.PROFILE_CAPSULE_CUSTODY),
    (PROFILE_PASSWORD_ENVELOPE_FILENAME, StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE),
    (PROFILE_RECOVERY_ENVELOPE_FILENAME, StorageCategory.PROFILE_CAPSULE_RECOVERY_ENVELOPE),
    (PROFILE_DATA_DIRNAME, StorageCategory.PROFILE_CAPSULE_DATA),
    (PROFILE_COMMIT_FILENAME, StorageCategory.PROFILE_CAPSULE_COMMIT),
)


@pytest.mark.parametrize(("constant", "category"), _BOUND_CONSTANTS, ids=lambda value: getattr(value, "value", None))
def test_each_exported_name_is_its_taxonomy_member(constant: str, category: StorageCategory) -> None:
    """A constant that merely agrees with the declaration today is still a copy."""
    assert constant == storage_location(category).subpath


def test_every_scoped_taxonomy_member_is_exported_here() -> None:
    """Both directions: a member added to the layout must surface as a constant.

    Without this, a new per-bucket file could be declared in core and quietly
    fail to reach the storage callers that resolve names through this module --
    the taxonomy would describe a layout nobody provisions.
    """
    scoped = {location.category for location in STORAGE_TAXONOMY.values() if location.scope is not StorageScope.ROOT}
    assert scoped, "the fixed layout must be declared, or this asserts nothing"
    assert scoped == {category for _constant, category in _BOUND_CONSTANTS if category in scoped}


def test_the_layout_names_are_resolved_not_re_typed() -> None:
    """The literals are deleted, not merely pinned.

    An AST walk over string constants rather than a text scan, because every one
    of these names appears legitimately in prose -- in this module's own comment
    explaining why they must not appear as code. A text scanner would need a
    special case for that; this cannot produce the error at all.
    """
    tree = ast.parse(_DEFINITIONS_MODULE.read_text(encoding="utf-8"))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstrings
    }
    assert literals, "the module must contain some string constants, or this asserts nothing"

    governed = {constant for constant, _category in _BOUND_CONSTANTS}
    assert not (governed & literals), (
        f"_storage_path_definitions.py re-types governed layout names {sorted(governed & literals)}; "
        "read the taxonomy instead"
    )


def test_the_literal_probe_still_sees_the_names_it_is_not_governing() -> None:
    """Positive control for the scan above.

    The secure-object namespace keys are logical database keys rather than
    filesystem paths, so they keep their own declarations here and must still
    read as literals. Without this, an AST walk that silently returned nothing
    would satisfy the assertion above while proving no deletion at all.
    """
    tree = ast.parse(_REGISTRY_MODULE.read_text(encoding="utf-8"))
    literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}

    assert "catalogue" in literals, "the scan must still observe the ungoverned namespace keys"


def test_moving_the_declaration_inward_introduced_no_upward_import() -> None:
    """Core must not reach back into adapters to declare what it now owns.

    Stated as an assertion rather than trusted as obvious, because the whole
    reason the duplicate literals existed was this layering wall. Closing them
    by having core import the adapter constants would have been the one change
    that made the fix worse than the defect it removed -- and it would have
    looked, in a diff, almost exactly like the change that was made.
    """
    declaration = _DEFINITIONS_MODULE.parents[3] / "core" / "storage_taxonomy.py"
    assert declaration.is_file(), f"the core declaration must be where this test looks: {declaration}"

    tree = ast.parse(declaration.read_text(encoding="utf-8"))
    reached = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None}

    assert not [module for module in reached if "adapters" in module], (
        f"the core taxonomy reaches into adapters: {sorted(reached)}"
    )

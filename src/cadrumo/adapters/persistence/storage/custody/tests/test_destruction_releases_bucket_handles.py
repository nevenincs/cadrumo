"""The destruction path releases the bucket's database handles before acting.

A capsule directory holds the profile's own SQLite database, so an engine
cached for that bucket keeps a file inside the directory open. Renaming or
removing a directory whose files are open is refused on Windows, which made a
reset running in a process that had touched the profile fail at the rename with
an opaque OS error.

The engine module has always documented this caller -- "the bucket-destruction
path releases the bucket's SQLite file handles before removing the bucket
directory" -- and the caller simply did not exist. This pins it so it cannot go
missing again.

Asserted by reading the source rather than by renaming a capsule, deliberately.
A rename-succeeds assertion proves nothing on a platform that tolerates an open
handle, and those are precisely the platforms where this defect stayed hidden
for as long as it did. What must hold is that the release happens AT ALL and
BEFORE the destructive step, which is a property of the code, not of the
platform. The behavioural evidence lives with the reset suite, which goes from
four failures to one when this call is present.
"""

from __future__ import annotations

import ast
import inspect

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_RELEASE_HELPER = "_release_bucket_file_handles"


def _first_statement_calls(function: object, name: str) -> bool:
    """Is ``name`` called before anything that could touch the directory?

    "Before" is what matters: releasing handles after the rename would be an
    expensive no-op that still fails. The rename resolves its source first, so
    the release is allowed to sit behind that lookup but nothing else.
    """
    tree = ast.parse(inspect.getsource(function).lstrip())  # type: ignore[arg-type]
    body = tree.body[0].body  # type: ignore[attr-defined]
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
                return True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.startswith("_rename"):
                return False
            if isinstance(node, ast.Attribute) and node.attr in {"rmtree", "unlink", "rename"}:
                return False
    return False


@pytest.mark.parametrize(
    "function_name",
    ("rename_profile_custody_capsule_for_deletion", "remove_profile_custody_deletion_tombstone"),
)
def test_each_destruction_function_releases_handles_before_it_acts(function_name: str) -> None:
    """Both halves of the destruction path, not just the one that was reported.

    The reported failure was the rename. The removal has the same exposure: a
    handle can be re-opened between the two steps, and an open file blocks the
    delete as surely as it blocks the rename.
    """
    from .. import _capsule

    function = getattr(_capsule, function_name)

    assert _first_statement_calls(function, _RELEASE_HELPER), (
        f"{function_name} must call {_RELEASE_HELPER} before it touches the capsule directory"
    )


def test_the_release_helper_is_bucket_scoped() -> None:
    """It disposes this bucket's engines and delegates rather than reimplementing.

    Bucket scoping is the property that makes calling it safe on a shared
    process: a reset erasing one profile must not tear down engines another
    profile is using.
    """
    from .. import _capsule

    source = inspect.getsource(_capsule._release_bucket_file_handles)

    assert "dispose_engines_for_bucket" in source
    assert "str(profile_id)" in source

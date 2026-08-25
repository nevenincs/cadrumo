"""The keystore joins refuse anything that is not a containable component.

``bucket_paths`` was hardened against a dot-segment ``bucket_id``; its twin
``keystore_path`` carried the SAME two checks -- empty and separator -- and the
same omission, so the escape simply moved to the tree holding key material.
``keystore_sidecar_path`` was worse: it validated its ``bucket_id`` through the
separation contract and joined its ``filename`` without looking at it.

Measured against real joins before the fix, with root ``C:/storage-root``:

    keystore_path('..')                    -> C:/storage-root
    sidecar(filename='../../secrets.json') -> C:/storage-root/secrets.json
    sidecar(filename='C:/evil.json')       -> C:/evil.json
    bucket_paths('D:x').bucket_dir         -> D:x

The last is the one that is not a traversal. ``"C:x"`` against a root already
on ``C:`` resolves to the component ``"x"``: the directory name no longer
equals the identifier that named it, so two distinct ids collide on one
directory. A containment check alone would call that safe.

The rule now has one home, :func:`validate_path_component`, because three
copies of it had already drifted into three different answers. These tests
pin the joins rather than the helper, so a caller that stops consulting it
fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..errors import BucketValidationError
from .._keystore_paths import keystore_path, keystore_sidecar_path
from .._layout import bucket_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: Values that are not one containable component, each spelled without a separator.
_NOT_A_COMPONENT = ("..", ".", "D:x", "C:x", "")


def test_keystore_path_refuses_a_non_component_bucket_id(tmp_path: Path) -> None:
    """DISCRIMINATING: the twin of the join already hardened, holding key material."""
    for bucket_id in _NOT_A_COMPONENT:
        with pytest.raises(BucketValidationError):
            keystore_path(tmp_path, bucket_id)


def test_the_sidecar_refuses_a_non_component_filename(tmp_path: Path) -> None:
    """DISCRIMINATING: the filename was joined unexamined.

    This is the join point for the persisted session record, the wrapped
    bucket DEK and the login-throttle cache.
    """
    for filename in ("../../secrets.json", "..", "C:/evil.json", "a/b.json", ""):
        with pytest.raises(BucketValidationError):
            keystore_sidecar_path(storage_root=tmp_path, bucket_id="alpha", filename=filename)


def test_a_refused_id_would_have_left_the_keystore_tree(tmp_path: Path) -> None:
    """ANTI-VACUITY: states the consequence, so the refusal cannot be dropped quietly.

    Asserting only that ``".."`` raises says nothing about why it must.
    """
    keystore_dir = keystore_path(tmp_path, "alpha").parent

    assert (keystore_dir / "..").resolve() == tmp_path.resolve()
    assert keystore_dir.resolve() != tmp_path.resolve()


def test_a_drive_qualified_id_would_have_renamed_the_bucket(tmp_path: Path) -> None:
    """ANTI-VACUITY: the non-traversal failure, which containment alone misses.

    ``"C:x"`` against a root on ``C:`` stays inside the tree and silently
    becomes ``"x"``. Pinning it here records that the rule is about identity
    as well as containment -- a future simplification to "does it stay under
    the root" would pass every other test in this module.
    """
    same_drive = Path("C:/storage-root/buckets") / "C:x"

    assert same_drive.name == "x", "premise: pathlib drops the same-drive qualifier"
    assert same_drive.name != "C:x"


def test_the_ordinary_ids_and_filenames_still_resolve(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the guard must not have widened onto what the tree really uses.

    ``system``, ``unsecured`` and ``diagnostic-probe`` are real bucket ids, and
    the sidecar filenames are dotted version markers. A validator refusing
    those would satisfy every assertion above while breaking the surfaces that
    depend on them.
    """
    for bucket_id in ("system", "unsecured", "diagnostic-probe", "a.b", "..alpha"):
        assert keystore_path(tmp_path, bucket_id).name == bucket_id
        assert bucket_paths(tmp_path, bucket_id).bucket_dir.name == bucket_id

    for filename in ("profile-session.v1.json", "login-throttle.v1.json", "wrapped-dek.bin"):
        resolved = keystore_sidecar_path(storage_root=tmp_path, bucket_id="alpha", filename=filename)
        assert resolved.name == filename
        assert resolved.parent == keystore_path(tmp_path, "alpha")

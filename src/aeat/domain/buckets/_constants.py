"""Storage-layer identifier re-exports for the bucket package.

The canonical alias definitions live in the profile package because
the profile-bucket lifecycle ADR mandates 1:1 cardinality between a
profile and its storage slice. This module re-exports the storage-
layer name (`BucketId`) under the bucket namespace so storage-layer
modules can import from a path that matches their concern.
"""

from __future__ import annotations

from ..profile._constants import BucketId

__all__ = ["BucketId"]

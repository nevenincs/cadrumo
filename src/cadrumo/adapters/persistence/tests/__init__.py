"""Test-only support for persistence adapter suites.

Carries the runtime-profile fixture factories for tests in *other* packages, so
a cross-package consumer resolves here rather than reaching into a private
submodule. Suites inside this package import the submodule directly.
"""

from .runtime_profile_fixture import (
    bucket_scoped_runtime_profile_fixture,
    default_bucket_runtime_profile_fixture,
)

__all__ = [
    "bucket_scoped_runtime_profile_fixture",
    "default_bucket_runtime_profile_fixture",
]

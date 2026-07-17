"""Public-surface gate for the portable bundle symbols.

The `BucketMaintenanceService` composition pattern requires the bundle
serialiser and deserialiser to be re-exported from the application
package `__all__` before the export / import maintenance verbs can
compose them. This test pins the contract surface so a future refactor
cannot silently retract a re-export and force the service to dot into
the private `_bundle` submodule again.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_application_package_reexports_callable_symbols() -> None:
    from ... import user_profile as package

    symbols = (
        "serialize_profile_bundle",
        "deserialize_profile_bundle",
        "rename_profile",
        "delete_profile_with_lifecycle_span",
        "remove_profile_bucket_directory",
    )
    for symbol in symbols:
        assert symbol in package.__all__, symbol
        assert callable(getattr(package, symbol)), symbol


def test_application_package_reexports_orchestration_full_surface() -> None:
    """Every public symbol declared in _orchestration.__all__ is reachable via the package.

    Closes the gap that left several orchestration symbols (e.g.
    build_lifecycle_service, profile_storage_session) without a
    top-level re-export, forcing consumers to dot into the private
    submodule.
    """
    from ... import user_profile as package
    from .. import _orchestration

    missing = sorted(name for name in _orchestration.__all__ if name not in package.__all__)
    assert not missing, (
        f"orchestration symbols missing from package __all__: {missing!r}. "
        f"Promote them via the lazy __getattr__ block and add to __all__."
    )


def test_application_package_reexports_domain_profile_records() -> None:
    """The package manifest exposes the domain profile records it lazy-resolves."""
    from ....domain import user_profile as domain_package
    from ... import user_profile as package

    for name in ("UserProfileFact", "UserProfileFactValue", "UserProfileRecord", "UserProfileStatus"):
        assert name in package.__all__
        assert getattr(package, name) is getattr(domain_package, name)


def test_domain_package_reexports_portable_export_record() -> None:
    """`cadrumo.domain.user_profile` exposes the portable-export domain record."""
    from ....domain import user_profile as package

    assert "UserProfilePortableExport" in package.__all__
    from pydantic import BaseModel

    assert issubclass(package.UserProfilePortableExport, BaseModel)

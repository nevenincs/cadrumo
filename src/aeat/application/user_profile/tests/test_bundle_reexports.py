"""Public-surface gate for the portable bundle symbols.

The `BucketMaintenanceService` composition-pattern contract
identifies the bundle serialiser
and deserialiser as preconditions whose re-export to the application
package `__all__` MUST land before the export / import maintenance
verbs can compose them. This test pins the contract surface so a future
refactor cannot silently retract a re-export and force the service
to dot into the private `_bundle` submodule again.

Companion to the codified rule slug
`service-imports-via-top-level-reexports`.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_application_package_reexports_bundle_serialiser() -> None:
    """`aeat.application.user_profile` exposes the bundle serialiser."""
    from ... import user_profile as package

    assert "serialize_profile_bundle" in package.__all__
    assert callable(package.serialize_profile_bundle)


def test_application_package_reexports_bundle_deserialiser() -> None:
    """`aeat.application.user_profile` exposes the bundle deserialiser."""
    from ... import user_profile as package

    assert "deserialize_profile_bundle" in package.__all__
    assert callable(package.deserialize_profile_bundle)


def test_application_package_reexports_supported_bundle_schema_versions() -> None:
    """The frozen set of accepted bundle schema versions is package-visible."""
    from ... import user_profile as package

    assert "SUPPORTED_BUNDLE_SCHEMA_VERSIONS" in package.__all__
    supported = package.SUPPORTED_BUNDLE_SCHEMA_VERSIONS
    assert isinstance(supported, frozenset)
    assert supported, "supported bundle schema version set must not be empty"


def test_application_package_reexports_rename_orchestration() -> None:
    """`rename_profile` is the top-level coordinator for the cross-store relabel."""
    from ... import user_profile as package

    assert "rename_profile" in package.__all__
    assert callable(package.rename_profile)


def test_application_package_reexports_delete_orchestration() -> None:
    """`delete_profile_with_lifecycle_span` is the top-level soft-tombstone coordinator."""
    from ... import user_profile as package

    assert "delete_profile_with_lifecycle_span" in package.__all__
    assert callable(package.delete_profile_with_lifecycle_span)


def test_application_package_reexports_bucket_directory_removal() -> None:
    """`remove_profile_bucket_directory` is the top-level hard-erase primitive."""
    from ... import user_profile as package

    assert "remove_profile_bucket_directory" in package.__all__
    assert callable(package.remove_profile_bucket_directory)


def test_application_package_reexports_orchestration_full_surface() -> None:
    """Every public symbol declared in _orchestration.__all__ is reachable via the package.

    Closes the gap that left several orchestration symbols (e.g.
    build_lifecycle_service, profile_storage_session) without a
    top-level re-export, forcing consumers to dot into the private
    submodule. Codified by service-imports-via-top-level-reexports.
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
    """`aeat.domain.user_profile` exposes the portable-export domain record."""
    from ....domain import user_profile as package

    assert "UserProfilePortableExport" in package.__all__
    from pydantic import BaseModel

    assert issubclass(package.UserProfilePortableExport, BaseModel)

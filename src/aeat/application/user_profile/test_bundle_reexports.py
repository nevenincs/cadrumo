"""Public-surface gate for the portable bundle symbols.

The `BucketMaintenanceService` composition-pattern ADR
(`2026-06-03-cli-workflow-redesign-adr`) names the bundle serialiser
and deserialiser as preconditions whose re-export to the application
package `__all__` MUST land before the export / import maintenance
verbs can compose them. This test pins the surface so a future
refactor cannot silently retract a re-export and force the service
to dot into the private `_bundle` submodule again.

Companion to the codified rule slug
`service-imports-via-top-level-reexports`.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_application_package_reexports_bundle_serialiser() -> None:
    """`aeat.application.user_profile` exposes the bundle serialiser."""
    import aeat.application.user_profile as package

    assert "serialize_profile_bundle" in package.__all__
    assert callable(package.serialize_profile_bundle)


def test_application_package_reexports_bundle_deserialiser() -> None:
    """`aeat.application.user_profile` exposes the bundle deserialiser."""
    import aeat.application.user_profile as package

    assert "deserialize_profile_bundle" in package.__all__
    assert callable(package.deserialize_profile_bundle)


def test_application_package_reexports_supported_bundle_schema_versions() -> None:
    """The frozen set of accepted bundle schema versions is package-visible."""
    import aeat.application.user_profile as package

    assert "SUPPORTED_BUNDLE_SCHEMA_VERSIONS" in package.__all__
    supported = package.SUPPORTED_BUNDLE_SCHEMA_VERSIONS
    assert isinstance(supported, frozenset)
    assert supported, "supported bundle schema version set must not be empty"


def test_domain_package_reexports_portable_export_record() -> None:
    """`aeat.domain.user_profile` exposes the portable-export domain record."""
    import aeat.domain.user_profile as package

    assert "UserProfilePortableExport" in package.__all__
    from pydantic import BaseModel

    assert issubclass(package.UserProfilePortableExport, BaseModel)

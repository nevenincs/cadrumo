"""Public facade for the central user-profile schema contract.

The package exposes strict Pydantic schema records, live value records, the
schema loader, and the registry-selector coverage report for the schema-driven
user-profile backend. The primary runtime aggregate is
:class:`UserProfileRecord`: TOML owns schema metadata and selector namespaces,
while live profile facts and immutable snapshots are stored by the persistence
layer.
:func:`new_profile_id` mints the immutable UUID identity used as the profile
and bucket id; ``display_name`` is the mutable operator label and is not a
storage key. Active-bucket selection, pointer files, and storage sessions live
in the application/workflow layers, not in these schema records.

The :class:`UserProfilePortableExport` re-export is resolved on demand
through a module-level ``__getattr__`` (PEP 562). The portable-export
bundle composes four heavy domain types
:class:`domain.modelos.CalculationRevision`,
:class:`domain.modelos.WorkUnit`,
:class:`domain.transactions.Transaction`, and
:class:`domain.modelos.ModeloRecord`) whose imports cascade into the
calculation registry; eagerly re-exporting it at this boundary would drag the
full registry into every consumer that touches the package surface, including
the state-free CLI surfaces enforced by
:mod:`entrypoints.cli.test_lazy_command_tree`. :class:`CarriedSecureObject`
and :class:`CoverageManifest` are declared in the same
``_portable_export`` module and share the same lazy-resolution path so
importing either does not trigger the same cascade. Every other
re-export (errors, value records, schema records, loader,
registry-contract) stays eager because each is genuinely lightweight
and every consumer pays for it unconditionally.

See Also:
    :class:`UserProfileRecord`
        Canonical runtime aggregate carrying profile facts and lifecycle state.
    :class:`UserProfilePortableExport`
        Lazy-resolved cross-bucket bundle payload that includes profile,
        work-unit, ledger, calculation, and filing history.
    :func:`validate_user_profile_registry_contract`
        Registry-selector coverage check binding schema paths to modelo
        calculation requirements.
    :func:`new_profile_id`
        Identity authority for UUID-backed profile and bucket ids.
    :mod:`application.user_profile`
        Application facade for lifecycle services, Censo sync, preflight,
        projections, custody, and portable-bundle serialisation.
    :mod:`application.workflow`
        Active-profile pointer and bucket-manifest readers that resolve the
        current storage slice before application services load records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import (
    ProfileAlreadyExistsError,
    ProfileBucketMismatchError,
    ProfileExportError,
    ProfileNotFoundError,
    ProfilePreflightMissingError,
    ProfileSchemaValidationError,
    ProfileSnapshotHashMismatchError,
    ProfileSnapshotNotFoundError,
    StoredProfileDriftError,
    UserProfileError,
    UserProfileSchemaLoadError,
    UserProfileValidationError,
)
from ._labels import (
    profile_field_label,
    profile_field_label_key,
    profile_schema_locale_keys,
    profile_section_title,
    profile_section_title_key,
)
from ._loader import load_user_profile_schema
from ._registry_contract import (
    UserProfileRegistryContractIssue,
    UserProfileRegistryContractReport,
    UserProfileSelectorIndex,
    build_user_profile_selector_index,
    profile_binding_selectors,
    validate_user_profile_registry_contract,
)
from ._schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ._values import (
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    UserProfileSnapshot,
    UserProfileStatus,
    declared_provenance_sources,
    new_profile_id,
    new_profile_snapshot_id,
    utc_now,
)

if TYPE_CHECKING:
    from ._portable_export import CarriedSecureObject, CoverageManifest, UserProfilePortableExport


def __getattr__(name: str):
    """Resolve heavy re-exports on demand to keep the boundary lazy.

    The portable-export bundle's domain-type composition cascades into
    the calculation registry; routing the symbol through ``__getattr__``
    defers that cost to first-use rather than module-import.
    :class:`CarriedSecureObject` and :class:`CoverageManifest` are declared
    in the same ``_portable_export`` module, so they share the same
    lazy-resolution rationale.
    """
    if name == "UserProfilePortableExport":
        from ._portable_export import UserProfilePortableExport

        globals()[name] = UserProfilePortableExport
        return UserProfilePortableExport
    if name in ("CarriedSecureObject", "CoverageManifest"):
        from . import _portable_export

        value = getattr(_portable_export, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CarriedSecureObject",
    "CoverageManifest",
    "ProfileAlreadyExistsError",
    "ProfileBucketMismatchError",
    "ProfileExportError",
    "ProfileFieldDefinition",
    "ProfileFieldType",
    "ProfileNotFoundError",
    "ProfilePreflightMissingError",
    "ProfileRemovePolicy",
    "ProfileSchemaDefinition",
    "ProfileSchemaValidationError",
    "ProfileSectionDefinition",
    "ProfileSnapshotHashMismatchError",
    "ProfileSnapshotNotFoundError",
    "ProfileSnapshotPolicy",
    "StoredProfileDriftError",
    "UserProfileError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfilePortableExport",
    "UserProfileRecord",
    "UserProfileRegistryContractIssue",
    "UserProfileRegistryContractReport",
    "UserProfileSchemaLoadError",
    "UserProfileSelectorIndex",
    "UserProfileSnapshot",
    "UserProfileStatus",
    "UserProfileValidationError",
    "build_user_profile_selector_index",
    "declared_provenance_sources",
    "load_user_profile_schema",
    "new_profile_id",
    "new_profile_snapshot_id",
    "profile_binding_selectors",
    "profile_field_label",
    "profile_field_label_key",
    "profile_schema_locale_keys",
    "profile_section_title",
    "profile_section_title_key",
    "utc_now",
    "validate_user_profile_registry_contract",
]

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
:mod:`entrypoints.cli.tests.test_lazy_command_tree`. :class:`CarriedSecureObject`
and :class:`CoverageManifest` are declared in the same
``_portable_export`` module and share the same lazy-resolution path so
importing either does not trigger the same cascade.

The registry-contract re-exports resolve lazily for the same reason. This
docstring previously stated they stayed eager "because each is genuinely
lightweight"; that was measurably untrue -- ``_registry_contract`` reaches the
calculation registry and cost roughly a second of import on its own, which
every consumer of a plain exception class from this package paid. The claim
outlived the code it described and is corrected here rather than deleted, since
it is the reason the eager import survived beside a ``__getattr__`` written to
avoid exactly it.

The remaining re-exports (errors, value records, schema records, loader) stay
eager because each is genuinely lightweight and every consumer needs them.

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

from typing import TYPE_CHECKING, Final

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
    UserProfileNotFoundError,
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
from ._schema import (
    NUMERIC_PROFILE_FIELD_TYPES,
    ProfileDerivedSelectorDefinition,
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
    ProfileValueRefusal,
    ProfileValueRefusalKind,
    boolean_value_refusal,
    date_value_refusal,
    derived_selector_for_path,
    email_value_refusal,
    enum_value_refusal,
    numeric_value_refusal,
    profile_value_refusal,
)
from ._values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    UserProfileSnapshot,
    declared_provenance_sources,
    new_profile_id,
    new_profile_snapshot_id,
    section_field_key,
    utc_now,
)

if TYPE_CHECKING:
    from ._portable_export import CarriedSecureObject, CoverageManifest, UserProfilePortableExport
    from ._registry_contract import profile_binding_selectors


#: Names ``_registry_contract`` owns, resolved on first use. Kept as an explicit
#: set so a symbol added there without being listed here fails loudly at the
#: attribute lookup rather than silently reintroducing the eager import.
_REGISTRY_CONTRACT_EXPORTS: Final[frozenset[str]] = frozenset(
    {
        "UserProfileRegistryContractIssue",
        "UserProfileRegistryContractReport",
        "UserProfileSelectorIndex",
        "build_user_profile_selector_index",
        "profile_binding_selectors",
        "validate_user_profile_registry_contract",
    },
)


def __getattr__(name: str):
    """Resolve heavy re-exports on demand to keep the boundary lazy.

    The portable-export bundle's domain-type composition cascades into
    the calculation registry; routing the symbol through ``__getattr__``
    defers that cost to first-use rather than module-import.
    :class:`CarriedSecureObject` and :class:`CoverageManifest` are declared
    in the same ``_portable_export`` module, so they share the same
    lazy-resolution rationale.

    The registry-contract symbols are deferred for exactly that reason and
    were previously imported eagerly a few lines above, which cancelled the
    deferral: this package exports plain exception classes that callers reach
    for constantly, and every one of those imports paid a full registry
    compile. Measured at roughly one second per interpreter, charged to every
    xdist worker and every subprocess that imports the CLI.
    """
    if name in _REGISTRY_CONTRACT_EXPORTS:
        from . import _registry_contract

        value = getattr(_registry_contract, name)
        globals()[name] = value
        return value
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
    "NUMERIC_PROFILE_FIELD_TYPES",
    "CarriedSecureObject",
    "CoverageManifest",
    "ProfileAlreadyExistsError",
    "ProfileBucketMismatchError",
    "ProfileDerivedSelectorDefinition",
    "ProfileExportError",
    "ProfileFieldDefinition",
    "ProfileFieldType",
    "ProfileNotFoundError",
    "ProfilePreflightMissingError",
    "ProfileRemovePolicy",
    "ProfileSchemaDefinition",
    "ProfileSchemaValidationError",
    "ProfileSectionDefinition",
    "ProfileSetupState",
    "ProfileSnapshotHashMismatchError",
    "ProfileSnapshotNotFoundError",
    "ProfileSnapshotPolicy",
    "ProfileValueRefusal",
    "ProfileValueRefusalKind",
    "StoredProfileDriftError",
    "UserProfileError",
    "UserProfileFact",
    "UserProfileFactValue",
    "UserProfileNotFoundError",
    "UserProfilePortableExport",
    "UserProfileRecord",
    "UserProfileRegistryContractIssue",
    "UserProfileRegistryContractReport",
    "UserProfileSchemaLoadError",
    "UserProfileSelectorIndex",
    "UserProfileSnapshot",
    "UserProfileValidationError",
    "boolean_value_refusal",
    "build_user_profile_selector_index",
    "date_value_refusal",
    "declared_provenance_sources",
    "derived_selector_for_path",
    "email_value_refusal",
    "enum_value_refusal",
    "load_user_profile_schema",
    "new_profile_id",
    "new_profile_snapshot_id",
    "numeric_value_refusal",
    "profile_binding_selectors",
    "profile_field_label",
    "profile_field_label_key",
    "profile_schema_locale_keys",
    "profile_section_title",
    "profile_section_title_key",
    "profile_value_refusal",
    "section_field_key",
    "utc_now",
    "validate_user_profile_registry_contract",
]

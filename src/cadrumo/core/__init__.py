"""Core cross-cutting infrastructure shared by every Cadrumo layer.

The core layer is the innermost package in the hexagonal architecture. It
exports typed primitives, configuration-adjacent helpers, parsing utilities,
and layer-neutral policies that domain, application, adapter, and entrypoint
modules can import without depending outward.

The public facade groups stable surfaces. Immutable modelling primitives
include :data:`STRICT_FROZEN_CONFIG`, :class:`CasillaId`, :class:`Modelo`,
:class:`Period`, :class:`StandardPeriodCode`, ``PeriodKind``,
:class:`TaxDomain`, :class:`RefundElection`, :class:`ResultDisposition`,
:class:`RevisionReviewStatus` with its derived
:data:`REVIEWED_REVISION_REVIEW_STATUSES` companion set, and
the lazily resolved :class:`BindingSourceKind` registry-source taxonomy.
Obligation-coverage mappings expose :data:`OUT_OF_SCOPE_OBLIGATIONS` and
:data:`UNMODELED_OBLIGATIONS`, the codified AEAT modelo sets the overview
coverage report reads to distinguish product-scope exclusions from
registry gaps. Active-bucket context uses the plaintext :class:`BucketPointer` value object
plus :func:`pointer_path`, :func:`read_pointer`, :func:`capture_pointer`,
:func:`restore_pointer`, :func:`clear_pointer`, :func:`write_pointer`,
:func:`exclusive_file_lock`,
:func:`resolve_active_bucket_id`, :func:`require_active_bucket_id`, and
:func:`resolve_repository_bucket_id`. :func:`pid_is_alive` is the shared
cross-platform PID-liveness probe consumed by every crash-recoverable
lockfile (bucket lockfile, auth-acquisition lock). TOML and option utilities expose
:func:`read_toml`, :func:`parse_toml_text`, :func:`freeze_toml`,
:class:`OptionalExtra`, and :func:`require_optional_extra`. Filing-result
helpers expose the codified :class:`ResultDisposition` mapping and its
casilla/refund predicates. Service and operator-adjacent primitives include
:class:`ServiceCapability`, :class:`LedgerSortField`,
:class:`LedgerSortOrder`, :data:`IBAN_SHAPE_RE`, and :func:`iban_mod_97`. The
closed :class:`GoogleCredentialSourceKind` taxonomy governs which mechanism
:mod:`adapters.outbound.google` uses to obtain Google API credentials.

``BindingSourceKind``, ``BucketPointer``, and the active-bucket IO helpers are
resolved through ``__getattr__`` so storage, config, and aggregation callers
can import the public core facade without recreating the cycles those helpers
break internally.

Major subpackages remain the specialised homes for broader contracts:
:mod:`core.config` owns :class:`core.config.Settings` and storage route
classification, :mod:`core.errors` owns the error taxonomy and registry,
:mod:`core.money` and :mod:`core.decimal` own Decimal primitives,
:mod:`core.time` owns clocks, :mod:`core.identity` owns NIF/NIE/bucket/profile
identifiers, :mod:`core.access_gate` owns live-read and write-refusal gating,
:mod:`core.redaction` owns safe output, and :mod:`core.classification` owns
sensitivity policy.

See Also:
    :class:`Period`: Canonical filing year plus registry period-code value used
        across registry, deadline, and workflow boundaries.
    :class:`BucketPointer`: Typed value for the plaintext
        ``active-profile`` pointer file.
    :func:`resolve_active_bucket_id`: Central active-bucket precedence resolver
        for storage and CLI startup paths.
    :func:`read_toml`: Shared committed-TOML loader with caller-owned error
        wrapping.
    :class:`ResultDisposition`: Codified fichero result-disposition
        code set grounded in bundled AEAT diseños.
    :class:`BindingSourceKind`: Canonical registry binding-source taxonomy
        resolved lazily from :mod:`core.aggregation`.
    :class:`ConceptLifecycle`: Terminology Handbook concept lifecycle, shared
        by the shipped terminology search and the unshipped authoring tooling.
    :class:`ExternalOracleCorpus`: Bundled AEAT-authoritative oracle corpus that
        supplies an expected casilla value for independent reconciliation.
    :class:`ExportLayoutFormat`: Wire shape a registry export layout declares,
        closing the value set every export consumer used to re-spell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._aeat_csv import (
    AEAT_CSV_MAX_LENGTH,
    AEAT_CSV_MIN_LENGTH,
    AEAT_CSV_PATTERN,
    is_aeat_csv,
)
from ._amendment_kind_regime import (
    AmendmentKindRegime,
    AmendmentLiabilityDirection,
    classify_amendment_liability_direction,
    modelo_has_codified_amendment_regime,
    permitted_amendment_kind_values,
    resolve_amendment_kind_regime,
)
from ._auth_provider import AuthProviderDescription, AuthProviderKind
from ._capabilities import ServiceCapability
from ._casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ._concept_lifecycle import ConceptLifecycle
from ._config_state_root import (
    FormerProductStateError,
    StateRootInputs,
    live_state_root_inputs,
    platform_user_data_root,
)
from ._credentials import (
    LENGTH_ALONE_IS_STRONG,
    LENGTH_FAIR_FLOOR,
    NIST_PASSPHRASE_MIN_LENGTH,
    PassphraseStrength,
    assess_passphrase_strength,
    character_class_count,
)
from ._export_layout_format import ExportLayoutFormat
from ._external_oracle_corpus import ExternalOracleCorpus
from ._fts_query import fts_or_group
from ._google_credential_source import GoogleCredentialSourceKind
from ._hex import HEX_PATTERN_16, HEX_PATTERN_64, HEX_PATTERN_128, Hex16Str, Hex64Str
from ._iban import IBAN_SHAPE_RE, iban_mod_97
from ._invoice_link import LinkInconsistencyDirection
from ._irnr import (
    FETCH_GATED_M210_TIPO_RENTA_CODES,
    M210_TIPO_RENTA_CODE_PROJECTION,
    OFFICIAL_M210_TIPO_RENTA_CODES,
    ConvenioOverrideKind,
    M210GrossIncomeSourceMode,
    M210PayerMode,
    OfficialTipoRentaCode,
    TipoRentaGroundingTier,
    TipoRentaIrnr,
    project_m210_tipo_renta_code,
)
from ._ledger_sort import LedgerSortField, LedgerSortOrder
from ._modelo import NON_REGISTRY_MODELOS, OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo
from ._models import STRICT_FROZEN_CONFIG
from ._optional_extras import (
    ANTHROPIC_EXTRA,
    BROWSER_EXTRA,
    GOOGLE_EXTRA,
    OFX_EXTRA,
    OPTIONAL_EXTRAS,
    MissingOptionalExtraError,
    OptionalExtra,
    optional_extra_available,
    optional_extra_for_module,
    require_optional_extra,
)
from ._period import (
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
    RegistrySelectorPeriodCode,
    StandardPeriodCode,
    accepted_period_codes,
    accepted_period_patterns,
)
from ._post_filing_event import (
    ACTIONABLE_POST_FILING_EVENT_KINDS,
    PostFilingEventKind,
    classify_post_filing_event_kind,
    post_filing_event_is_actionable,
)
from ._profile_session import ProfileSessionRefusalReason
from ._prorrata_exclusions import (
    ART_104_TRES_AUTO_DERIVED_EXCLUSIONS,
    ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS,
    Art104TresExclusion,
)
from ._prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ._refund_election import RefundElection
from ._rescate_type import RescateType
from ._result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
)
from ._revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from ._tax_domain import TaxDomain
from ._toml import freeze_toml, freeze_toml_value, parse_toml_text, read_toml, to_str_keyed_dict
from .compatibility_lifecycle import (
    COMPATIBILITY_REGIME,
    PERSISTED_FORMATS,
    RELEASED_FORMAT_FLOORS,
    CompatibilityRegime,
    PersistedFormatClass,
    expected_floor,
    lineage_obligations,
    misclassified_floor_keys,
    stale_persisted_format_declarations,
    undeclared_persisted_formats,
    unfloored_durable_formats,
    unknown_floor_keys,
)
from .corpus_text import CorpusAnchorResolutionError, normalise_corpus_text, resolve_anchored_extracted_unit
from .external_constants import M347_THRESHOLD_EUR
from .manual_corpus_sidecar import (
    MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX,
    MANUAL_CORPUS_TEXT_SCHEMA_VERSION,
    MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
    ManualCorpusTextSidecar,
)
from .product_identity import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    IdentityReferent,
    ProductIdentity,
    normalise_product_identity_references,
)
from .secure_object_write import (
    ABSENT_SECURE_OBJECT_REVISION_ID,
    DEFAULT_WRITE_PROVENANCE,
    SecureObjectWrite,
)

if TYPE_CHECKING:
    # Static bindings for the lazily-exposed surface below. At runtime these
    # resolve through ``__getattr__`` (cycle-safe); the type checker reads the
    # real callable signatures here.
    from ._bucket_pointer import BucketPointer
    from ._bucket_pointer_io import (
        capture_pointer,
        clear_pointer,
        pointer_path,
        read_pointer,
        require_active_bucket_id,
        resolve_active_bucket_id,
        resolve_repository_bucket_id,
        restore_pointer,
        write_pointer,
    )
    from ._foreign_asset_obligation import (
        FOREIGN_ASSET_CLASS_OBLIGATION_GROUP,
        MODELO_720_FOREIGN_ASSET_CLASS_CODES,
        ForeignAssetObligationGroup,
        foreign_asset_obligation_group,
    )
    from ._fsync import fsync_parent_dir
    from ._pid_liveness import pid_is_alive
    from .aggregation import BindingSourceKind, IntracomOperationType
    from .locks import exclusive_file_lock

__all__: list[str] = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "ACTIONABLE_POST_FILING_EVENT_KINDS",
    "AEAT_AUTHORITY_SHORT_NAME",
    "AEAT_CSV_MAX_LENGTH",
    "AEAT_CSV_MIN_LENGTH",
    "AEAT_CSV_PATTERN",
    "ANTHROPIC_EXTRA",
    "ART_104_TRES_AUTO_DERIVED_EXCLUSIONS",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS",
    "BROWSER_EXTRA",
    "COMPATIBILITY_REGIME",
    "DEFAULT_WRITE_PROVENANCE",
    "FETCH_GATED_M210_TIPO_RENTA_CODES",
    "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP",
    "GOOGLE_EXTRA",
    "HEX_PATTERN_16",
    "HEX_PATTERN_64",
    "HEX_PATTERN_128",
    "IBAN_SHAPE_RE",
    "LENGTH_ALONE_IS_STRONG",
    "LENGTH_FAIR_FLOOR",
    "M210_TIPO_RENTA_CODE_PROJECTION",
    "M347_THRESHOLD_EUR",
    "MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX",
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION",
    "MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
    "NIST_PASSPHRASE_MIN_LENGTH",
    "NON_REGISTRY_MODELOS",
    "OFFICIAL_M210_TIPO_RENTA_CODES",
    "OFX_EXTRA",
    "OPTIONAL_EXTRAS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "PERSISTED_FORMATS",
    "PRODUCT_IDENTITY",
    "RELEASED_FORMAT_FLOORS",
    "REVIEWED_REVISION_REVIEW_STATUSES",
    "STRICT_FROZEN_CONFIG",
    "UNMODELED_OBLIGATIONS",
    "AmendmentKindRegime",
    "AmendmentLiabilityDirection",
    "Art104TresExclusion",
    "AuthProviderDescription",
    "AuthProviderKind",
    "BindingSourceKind",
    "BucketPointer",
    "CasillaId",
    "CompatibilityRegime",
    "ConceptLifecycle",
    "ConvenioOverrideKind",
    "CorpusAnchorResolutionError",
    "ExportLayoutFormat",
    "ExternalOracleCorpus",
    "ForeignAssetObligationGroup",
    "FormerProductStateError",
    "GoogleCredentialSourceKind",
    "Hex16Str",
    "Hex64Str",
    "IdentityReferent",
    "IntracomOperationType",
    "LedgerSortField",
    "LedgerSortOrder",
    "LinkInconsistencyDirection",
    "M210GrossIncomeSourceMode",
    "M210PayerMode",
    "ManualCorpusTextSidecar",
    "MissingOptionalExtraError",
    "Modelo",
    "OfficialTipoRentaCode",
    "OptionalExtra",
    "PassphraseStrength",
    "Period",
    "PeriodError",
    "PeriodKind",
    "PersistedFormatClass",
    "PostFilingEventKind",
    "ProductIdentity",
    "ProfileSessionRefusalReason",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "RefundElection",
    "RegistryPeriodCode",
    "RegistrySelectorPeriodCode",
    "RescateType",
    "ResultDisposition",
    "RevisionReviewStatus",
    "SectorDiferenciadoLetra",
    "SecureObjectWrite",
    "ServiceCapability",
    "StandardPeriodCode",
    "StateRootInputs",
    "TaxDomain",
    "TipoRentaGroundingTier",
    "TipoRentaIrnr",
    "accepted_period_codes",
    "accepted_period_patterns",
    "assess_passphrase_strength",
    "capture_pointer",
    "character_class_count",
    "classify_amendment_liability_direction",
    "classify_post_filing_event_kind",
    "clear_pointer",
    "derive_result_disposition",
    "exclusive_file_lock",
    "expected_floor",
    "foreign_asset_obligation_group",
    "freeze_toml",
    "freeze_toml_value",
    "fsync_parent_dir",
    "fts_or_group",
    "iban_mod_97",
    "is_aeat_csv",
    "lineage_obligations",
    "live_state_root_inputs",
    "misclassified_floor_keys",
    "modelo_has_codified_amendment_regime",
    "modelo_has_codified_disposition",
    "normalise_corpus_text",
    "normalise_product_identity_references",
    "optional_extra_available",
    "optional_extra_for_module",
    "parse_toml_text",
    "permitted_amendment_kind_values",
    "pid_is_alive",
    "platform_user_data_root",
    "pointer_path",
    "post_filing_event_is_actionable",
    "project_m210_tipo_renta_code",
    "read_pointer",
    "read_toml",
    "require_active_bucket_id",
    "require_optional_extra",
    "resolve_active_bucket_id",
    "resolve_amendment_kind_regime",
    "resolve_anchored_extracted_unit",
    "resolve_repository_bucket_id",
    "restore_pointer",
    "result_disposition_casilla_ids",
    "result_disposition_is_refund",
    "stale_persisted_format_declarations",
    "to_str_keyed_dict",
    "undeclared_persisted_formats",
    "unfloored_durable_formats",
    "unknown_floor_keys",
    "validated_casilla_id",
    "validated_casilla_id_map",
    "write_pointer",
]


def __getattr__(name: str) -> object:
    if name == "BindingSourceKind":
        from .aggregation import BindingSourceKind

        return BindingSourceKind
    if name == "IntracomOperationType":
        from .aggregation import IntracomOperationType

        return IntracomOperationType
    if name == "exclusive_file_lock":
        from .locks import exclusive_file_lock

        return exclusive_file_lock
    if name == "fsync_parent_dir":
        from ._fsync import fsync_parent_dir

        return fsync_parent_dir
    if name == "pid_is_alive":
        from ._pid_liveness import pid_is_alive

        return pid_is_alive
    if name in (
        "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP",
        "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
        "ForeignAssetObligationGroup",
        "foreign_asset_obligation_group",
    ):
        from . import _foreign_asset_obligation

        return getattr(_foreign_asset_obligation, name)
    if name == "BucketPointer":
        from ._bucket_pointer import BucketPointer

        return BucketPointer
    if name in (
        "capture_pointer",
        "clear_pointer",
        "pointer_path",
        "read_pointer",
        "resolve_active_bucket_id",
        "resolve_repository_bucket_id",
        "require_active_bucket_id",
        "restore_pointer",
        "write_pointer",
    ):
        from . import _bucket_pointer_io

        return getattr(_bucket_pointer_io, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

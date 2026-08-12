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
lockfile (bucket lockfile, auth-acquisition lock), and :func:`unlink_lockfile`
is the matching shared removal primitive those same locks use to survive the
Windows sharing violation a waiter's open handle causes. TOML and option utilities expose
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
    :class:`ExportExemptionReason`: Why a manifest casilla files no slot on the
        official record, so exemption from the completeness gate is declared
        data rather than an unexplained absence.
    :class:`DeclaracionIdioma`: Languages AEAT's declaration ``Aux/Idioma``
        element accepts, which are not the application's own output languages.
    :class:`CasillaValueKind`: How an observed casilla value is meant to be read,
        so a reader asks what a value IS instead of attempting a conversion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._action_argument_resolution import ActionArgumentResolution
from ._aeat_csv import (
    AEAT_CSV_MAX_LENGTH,
    AEAT_CSV_MIN_LENGTH,
    AEAT_CSV_PATTERN,
    is_aeat_csv,
    normalise_aeat_csv,
)
from ._amendment_kind_regime import (
    AmendmentKindRegime,
    AmendmentLiabilityDirection,
    classify_amendment_liability_direction,
    modelo_has_codified_amendment_regime,
    permitted_amendment_kind_values,
    resolve_amendment_kind_regime,
)
from ._auth_provider import AuthProviderDescription, AuthProviderKind, ClaveMovilRoute
from ._capabilities import ServiceCapability
from ._casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ._casilla_value_kind import CasillaValueKind
from ._classifier_input_source import ClassifierInputSource, CounterpartyTaxablePersonStatus
from ._concept_lifecycle import ConceptLifecycle
from ._concepto_ingreso import (
    INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE,
    ConceptoIngreso,
)
from ._config_state_root import (
    FormerProductStateError,
    StateRootInputs,
    live_state_root_inputs,
    platform_user_data_root,
)
from ._confirmation_gate import ConfirmationBlockReason, FindingResolutionAction, ReviewAdvisoryKind
from ._corpus_sidecar import render_corpus_sidecar_text
from ._credentials import (
    LENGTH_ALONE_IS_STRONG,
    LENGTH_FAIR_FLOOR,
    NIST_PASSPHRASE_MIN_LENGTH,
    PassphraseStrength,
    assess_passphrase_strength,
    character_class_count,
)
from ._declaracion_idioma import DeclaracionIdioma
from ._descendant_relacion import (
    ART_58_2_ENTITLING_RELACIONES,
    ART_81_1_MATERNIDAD_RELACIONES,
    DescendantRelacion,
)
from ._deuda_direccion import DeudaDireccion
from ._document_shape import (
    AEAT_RECORD_BATCH_SHAPES,
    PDF_CONTAINER_SHAPES,
    STRUCTURED_DOCUMENT_SHAPES,
    DocumentShape,
)
from ._draft_discrepancy import DraftDiscrepancyKind
from ._export_exemption_reason import ExportExemptionReason
from ._export_layout_format import ExportLayoutFormat
from ._external_oracle_corpus import ExternalOracleCorpus
from ._field_grounding import FieldGroundingOutcome
from ._field_origin import FieldOrigin
from ._field_role import FieldRole
from ._filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ._filing_producer_key import FilingProducerKey
from ._filing_projection_ref import (
    FilingProjectionRef,
    M303DifferentiatedDeductionProjectionField,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
    compile_filing_projection_ref,
    filing_projection_ref_casilla_id,
)
from ._fts_query import fts_or_group
from ._google_credential_source import GoogleCredentialSourceKind
from ._hardware import (
    HARDWARE_TIER_CAPABLE_FLOOR_BYTES,
    HARDWARE_TIER_MODEST_FLOOR_BYTES,
    AcceleratorKind,
    ContentionCause,
    HardwareTier,
    hardware_tier_for_free_bytes,
)
from ._hex import HEX_PATTERN_16, HEX_PATTERN_64, HEX_PATTERN_128, Hex16Str, Hex64Str
from ._iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ._image_media_type import ImageMediaType, detect_image_media_type
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
from ._iva_category_resolution import IvaCategoryOutcome
from ._iva_compensation_provenance import IvaCompensationStateProvenance
from ._iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ._ledger_sort import LedgerSortField, LedgerSortOrder
from ._model_catalogue import (
    ANTHROPIC_COMMERCIAL_TERMS,
    APACHE_2_0,
    DEFAULT_MODEL_BY_RUNTIME_AND_ROLE,
    MODEL_CATALOGUE,
    QWEN_RESEARCH,
    DeploymentLicencePosture,
    LicenceVerification,
    ModelCandidate,
    ModelLicence,
    ModelRole,
    ModelRuntime,
    ModelSelectionAdvisory,
    candidates_for_role,
    default_model_runtime_id,
    model_candidate,
)
from ._modelo import NON_REGISTRY_MODELOS, OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo
from ._modelo_232_codigos import MetodoValoracion, TipoOperacionVinculada, TipoVinculacion
from ._models import STRICT_FROZEN_CONFIG
from ._notificacion_estado_servicio import (
    NotificacionEstadoServicio,
    resolve_notificacion_estado_servicio,
)
from ._objeto_tributario import ObjetoTributario
from ._observed_header_fact import ObservedHeaderFact
from ._operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ._operator_progress import OperatorProgress
from ._optional_extras import (
    ANTHROPIC_EXTRA,
    BROWSER_EXTRA,
    GOOGLE_EXTRA,
    LLM_EXTRA,
    OFX_EXTRA,
    OPTIONAL_EXTRAS,
    MissingOptionalExtraError,
    OptionalExtra,
    optional_extra_available,
    optional_extra_for_module,
    require_optional_extra,
)
from ._orden_anual_html import (
    OrdenAnualHtmlParseError,
    OrdenAnualIvaActivityTable,
    OrdenAnualIvaModule,
    extract_orden_anual_iva_tables,
    orden_anual_iva_activity_anchors,
    orden_anual_iva_table_text,
)
from ._payment_election import PaymentElection
from ._period import (
    FilingPeriodCode,
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
    RegistrySelectorPeriodCode,
    StandardPeriodCode,
    accepted_filing_period_codes,
    accepted_filing_period_patterns,
    accepted_period_codes,
    accepted_period_patterns,
    is_administrative_period_token,
    registry_period_kind,
)
from ._post_filing_event import (
    ACTIONABLE_POST_FILING_EVENT_KINDS,
    PostFilingEventKind,
    classify_post_filing_event_kind,
    post_filing_event_is_actionable,
)
from ._precondition_action_invariants import (
    PreconditionActionIdentity,
    PreconditionEvidence,
    PreconditionOutcomeInvariant,
)
from ._prior_domiciliation_election import PriorDomiciliationElection
from ._profile_session import ProfileSessionRefusalReason
from ._prorrata_exclusions import (
    ART_104_TRES_AUTO_DERIVED_EXCLUSIONS,
    ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS,
    Art104TresExclusion,
)
from ._prorrata_register import (
    ProrrataActivityRowType,
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ._provenance_stamp import (
    LOCAL_TRANSPORT_LABEL,
    build_provenance_stamp,
    provenance_stamp_transport,
    provenance_transport_label,
)
from ._refund_election import RefundElection
from ._register_scoping_signal import RegisterScopingSignal
from ._renta_declaracion_type import RentaDeclaracionType
from ._rescate_type import RescateType
from ._result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
    result_disposition_requires_bank_account,
)
from ._revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from ._spanish_stemming import (
    SpanishStemmer,
    spanish_stemmer,
    spanish_word_tokens,
    stem_spanish_terms,
    stem_spanish_text,
)
from ._storage_taxonomy import (
    EXTERNAL_PATH_SETTINGS_FIELDS,
    FINGERPRINT_EXCLUDED_STORAGE_FIELDS,
    ROOT_DERIVED_STORAGE_FIELDS,
    STORAGE_FIELD_CATEGORIES,
    STORAGE_ROOT_SETTINGS_FIELD,
    STORAGE_TAXONOMY,
    ExternalPathDeclaration,
    ExternalPathRole,
    FingerprintParticipation,
    StorageArea,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageLocation,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
    bucket_scoped_storage_path,
    storage_location,
    storage_path,
    storage_tree_targets,
)
from ._sync_surface import SyncSurface
from ._tax_domain import TaxDomain
from ._tipos_actividad import (
    IAE_SUBJECT_TIPOS_ACTIVIDAD,
    NON_IAE_SUBJECT_TIPOS_ACTIVIDAD,
    TipoActividad,
)
from ._toml import freeze_toml, freeze_toml_value, parse_toml_text, read_toml, to_str_keyed_dict
from ._type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
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
from .prose_elision import PROSE_ELISION_MARKER, ElidedProse, elide_to_cap, elided_prose
from .secure_object_write import (
    ABSENT_SECURE_OBJECT_REVISION_ID,
    DEFAULT_WRITE_PROVENANCE,
    SecureObjectWrite,
)
from .text_fold import fold_diacritics, fold_printed_phrase, unicode_compose

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
    from ._link_safety import is_link_like
    from ._lockfile_unlink import LOCKFILE_UNLINK_RETRY_SECONDS, unlink_lockfile
    from ._pid_liveness import pid_is_alive
    from .aggregation import (
        OBSERVATION_BACKED_BINDING_SOURCE_KINDS,
        AggregationCaptureKind,
        BindingSourceKind,
        IntracomOperationType,
    )
    from .locks import exclusive_file_lock

__all__: list[str] = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "ACTIONABLE_POST_FILING_EVENT_KINDS",
    "AEAT_AUTHORITY_SHORT_NAME",
    "AEAT_CSV_MAX_LENGTH",
    "AEAT_CSV_MIN_LENGTH",
    "AEAT_CSV_PATTERN",
    "AEAT_RECORD_BATCH_SHAPES",
    "ANTHROPIC_COMMERCIAL_TERMS",
    "ANTHROPIC_EXTRA",
    "APACHE_2_0",
    "ART_58_2_ENTITLING_RELACIONES",
    "ART_81_1_MATERNIDAD_RELACIONES",
    "ART_104_TRES_AUTO_DERIVED_EXCLUSIONS",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS",
    "BROWSER_EXTRA",
    "COMPATIBILITY_REGIME",
    "DEFAULT_MODEL_BY_RUNTIME_AND_ROLE",
    "DEFAULT_WRITE_PROVENANCE",
    "EXTERNAL_PATH_SETTINGS_FIELDS",
    "FETCH_GATED_M210_TIPO_RENTA_CODES",
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS",
    "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP",
    "GOOGLE_EXTRA",
    "HARDWARE_TIER_CAPABLE_FLOOR_BYTES",
    "HARDWARE_TIER_MODEST_FLOOR_BYTES",
    "HEX_PATTERN_16",
    "HEX_PATTERN_64",
    "HEX_PATTERN_128",
    "IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "IBAN_SHAPE_RE",
    "INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE",
    "LENGTH_ALONE_IS_STRONG",
    "LENGTH_FAIR_FLOOR",
    "LLM_EXTRA",
    "LOCAL_TRANSPORT_LABEL",
    "LOCKFILE_UNLINK_RETRY_SECONDS",
    "M210_TIPO_RENTA_CODE_PROJECTION",
    "M347_THRESHOLD_EUR",
    "MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX",
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION",
    "MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES",
    "MODEL_CATALOGUE",
    "NIST_PASSPHRASE_MIN_LENGTH",
    "NON_IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "NON_REGISTRY_MODELOS",
    "OBJECT_TUPLE_ADAPTER",
    "OBSERVATION_BACKED_BINDING_SOURCE_KINDS",
    "OFFICIAL_M210_TIPO_RENTA_CODES",
    "OFX_EXTRA",
    "OPTIONAL_EXTRAS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "PDF_CONTAINER_SHAPES",
    "PERSISTED_FORMATS",
    "PRODUCT_IDENTITY",
    "PROSE_ELISION_MARKER",
    "QWEN_RESEARCH",
    "RELEASED_FORMAT_FLOORS",
    "REVIEWED_REVISION_REVIEW_STATUSES",
    "ROOT_DERIVED_STORAGE_FIELDS",
    "STORAGE_FIELD_CATEGORIES",
    "STORAGE_ROOT_SETTINGS_FIELD",
    "STORAGE_TAXONOMY",
    "STRICT_FROZEN_CONFIG",
    "STRUCTURED_DOCUMENT_SHAPES",
    "STR_KEYED_MAPPING_ADAPTER",
    "UNMODELED_OBLIGATIONS",
    "AcceleratorKind",
    "ActionArgumentResolution",
    "ActionArgumentSource",
    "ActionArgumentStatus",
    "ActionConditionality",
    "ActionEvidenceProvenance",
    "AggregationCaptureKind",
    "AmendmentKindRegime",
    "AmendmentLiabilityDirection",
    "Art104TresExclusion",
    "AuthProviderDescription",
    "AuthProviderKind",
    "BindingSourceKind",
    "BucketPointer",
    "CasillaId",
    "CasillaValueKind",
    "ClassifierInputSource",
    "ClaveMovilRoute",
    "CompatibilityRegime",
    "ConceptLifecycle",
    "ConceptoIngreso",
    "ConfirmationBlockReason",
    "ContentionCause",
    "ConvenioOverrideKind",
    "CorpusAnchorResolutionError",
    "CounterpartyTaxablePersonStatus",
    "DeclaracionIdioma",
    "DeploymentLicencePosture",
    "DescendantRelacion",
    "DeudaDireccion",
    "DocumentShape",
    "DraftDiscrepancyKind",
    "ElidedProse",
    "ExportExemptionReason",
    "ExportLayoutFormat",
    "ExternalOracleCorpus",
    "ExternalPathDeclaration",
    "ExternalPathRole",
    "FieldGroundingOutcome",
    "FieldOrigin",
    "FieldRole",
    "FiledHistoryDiscoverySignal",
    "FilingPeriodCode",
    "FilingProducerKey",
    "FilingProjectionRef",
    "FindingResolutionAction",
    "FingerprintParticipation",
    "ForeignAssetObligationGroup",
    "FormerProductStateError",
    "GoogleCredentialSourceKind",
    "HardwareTier",
    "Hex16Str",
    "Hex64Str",
    "IdentityReferent",
    "ImageMediaType",
    "IntracomOperationType",
    "IvaCategoryOutcome",
    "IvaCompensationStateProvenance",
    "IvaDeductionEvidenceAuthority",
    "IvaDeductionFactKind",
    "LedgerSortField",
    "LedgerSortOrder",
    "LicenceVerification",
    "LinkInconsistencyDirection",
    "M210GrossIncomeSourceMode",
    "M210PayerMode",
    "M303DifferentiatedDeductionProjectionField",
    "M303DifferentiatedDeductionProjectionRef",
    "M303Exonerado390ActivityField",
    "M303Exonerado390ActivityProjectionRef",
    "M303Exonerado390OperacionesTercerosProjectionRef",
    "M303ProrrataActivityProjectionField",
    "M303ProrrataActivityProjectionRef",
    "M303RegimenSimplificadoActivityField",
    "M303RegimenSimplificadoActivityProjectionRef",
    "M303RegimenSimplificadoCohort",
    "M303RegimenSimplificadoFactProjectionRef",
    "M303RegimenSimplificadoModuleProjectionRef",
    "M303RegimenSimplificadoModuleValue",
    "ManualCorpusTextSidecar",
    "MetodoValoracion",
    "MissingOptionalExtraError",
    "ModelCandidate",
    "ModelLicence",
    "ModelRole",
    "ModelRuntime",
    "ModelSelectionAdvisory",
    "Modelo",
    "NoRecoveryOutcome",
    "NotificacionEstadoServicio",
    "ObjetoTributario",
    "ObservedHeaderFact",
    "OfficialTipoRentaCode",
    "OperatorProgress",
    "OptionalExtra",
    "OrdenAnualHtmlParseError",
    "OrdenAnualIvaActivityTable",
    "OrdenAnualIvaModule",
    "PassphraseStrength",
    "PaymentElection",
    "Period",
    "PeriodError",
    "PeriodKind",
    "PersistedFormatClass",
    "PostFilingEventKind",
    "PreconditionActionIdentity",
    "PreconditionEvidence",
    "PreconditionOutcomeInvariant",
    "PriorDomiciliationElection",
    "ProductIdentity",
    "ProfileSessionRefusalReason",
    "ProrrataActivityRowType",
    "ProrrataEspecialTransitionKind",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "RefundElection",
    "RegisterScopingSignal",
    "RegistryPeriodCode",
    "RegistrySelectorPeriodCode",
    "RentaDeclaracionType",
    "RescateType",
    "ResultDisposition",
    "ReviewAdvisoryKind",
    "RevisionReviewStatus",
    "SectorDiferenciadoLetra",
    "SecureObjectWrite",
    "ServiceCapability",
    "SpanishStemmer",
    "StandardPeriodCode",
    "StateRootInputs",
    "StorageArea",
    "StorageCategory",
    "StorageGrouping",
    "StorageLifecycle",
    "StorageLocation",
    "StorageNodeKind",
    "StorageOverridePolicy",
    "StorageScope",
    "SyncSurface",
    "TaxDomain",
    "TipoActividad",
    "TipoOperacionVinculada",
    "TipoRentaGroundingTier",
    "TipoRentaIrnr",
    "TipoVinculacion",
    "accepted_filing_period_codes",
    "accepted_filing_period_patterns",
    "accepted_period_codes",
    "accepted_period_patterns",
    "assess_passphrase_strength",
    "bucket_scoped_storage_path",
    "build_provenance_stamp",
    "candidates_for_role",
    "capture_pointer",
    "character_class_count",
    "classify_amendment_liability_direction",
    "classify_post_filing_event_kind",
    "clear_pointer",
    "compile_filing_projection_ref",
    "default_model_runtime_id",
    "derive_result_disposition",
    "detect_image_media_type",
    "elide_to_cap",
    "elided_prose",
    "exclusive_file_lock",
    "expected_floor",
    "extract_orden_anual_iva_tables",
    "filing_projection_ref_casilla_id",
    "fold_diacritics",
    "fold_printed_phrase",
    "foreign_asset_obligation_group",
    "freeze_toml",
    "freeze_toml_value",
    "fsync_parent_dir",
    "fts_or_group",
    "hardware_tier_for_free_bytes",
    "iban_mod_97",
    "is_administrative_period_token",
    "is_aeat_csv",
    "is_link_like",
    "lineage_obligations",
    "live_state_root_inputs",
    "misclassified_floor_keys",
    "model_candidate",
    "modelo_has_codified_amendment_regime",
    "modelo_has_codified_disposition",
    "normalise_aeat_csv",
    "normalise_corpus_text",
    "normalise_iban",
    "normalise_product_identity_references",
    "optional_extra_available",
    "optional_extra_for_module",
    "orden_anual_iva_activity_anchors",
    "orden_anual_iva_table_text",
    "parse_toml_text",
    "permitted_amendment_kind_values",
    "pid_is_alive",
    "platform_user_data_root",
    "pointer_path",
    "post_filing_event_is_actionable",
    "project_m210_tipo_renta_code",
    "provenance_stamp_transport",
    "provenance_transport_label",
    "read_pointer",
    "read_toml",
    "registry_period_kind",
    "render_corpus_sidecar_text",
    "require_active_bucket_id",
    "require_optional_extra",
    "resolve_active_bucket_id",
    "resolve_amendment_kind_regime",
    "resolve_anchored_extracted_unit",
    "resolve_notificacion_estado_servicio",
    "resolve_repository_bucket_id",
    "restore_pointer",
    "result_disposition_casilla_ids",
    "result_disposition_is_refund",
    "result_disposition_requires_bank_account",
    "spanish_stemmer",
    "spanish_word_tokens",
    "stale_persisted_format_declarations",
    "stem_spanish_terms",
    "stem_spanish_text",
    "storage_location",
    "storage_path",
    "storage_tree_targets",
    "to_str_keyed_dict",
    "undeclared_persisted_formats",
    "unfloored_durable_formats",
    "unicode_compose",
    "unknown_floor_keys",
    "unlink_lockfile",
    "validated_casilla_id",
    "validated_casilla_id_map",
    "write_pointer",
]


def __getattr__(name: str) -> object:
    if name == "OBSERVATION_BACKED_BINDING_SOURCE_KINDS":
        from .aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS

        return OBSERVATION_BACKED_BINDING_SOURCE_KINDS
    if name == "AggregationCaptureKind":
        from .aggregation import AggregationCaptureKind

        return AggregationCaptureKind
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
    if name == "is_link_like":
        from ._link_safety import is_link_like

        return is_link_like
    if name == "pid_is_alive":
        from ._pid_liveness import pid_is_alive

        return pid_is_alive
    if name in ("LOCKFILE_UNLINK_RETRY_SECONDS", "unlink_lockfile"):
        from . import _lockfile_unlink

        return getattr(_lockfile_unlink, name)
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

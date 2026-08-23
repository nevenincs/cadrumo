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
:data:`REVIEWED_REVISION_REVIEW_STATUSES` companion set,
:class:`RegistryAuthorityGrade` with its fail-closed
:data:`UNDECLARED_REGISTRY_AUTHORITY_GRADE` floor, and
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
:class:`OptionalExtra`, and :func:`require_optional_extra`. Directory
listing goes through :func:`scan_directory` (sorted and materialised) and
:func:`iter_directory` (lazy, for early-exit callers), narrowed by
:class:`DirectoryEntryKind` — the one ``os.scandir`` walk every layer shares
instead of reaching for ``Path.glob``. Filing-result
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

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._action_argument_resolution import ActionArgumentResolution
    from ._address_components import (
        FOREIGN_ADDRESS_COMPONENTS,
        FOREIGN_ADDRESS_INFIX,
        SPANISH_ADDRESS_COMPONENTS,
        SPANISH_ADDRESS_INFIXES,
    )
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
    from ._authority_grade import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
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
    from ._capabilities import ServiceCapability
    from ._casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
    from ._casilla_value_kind import CasillaValueKind
    from ._classifier_input_source import ClassifierInputSource, CounterpartyTaxablePersonStatus
    from ._concept_lifecycle import ConceptLifecycle
    from ._concepto_ingreso import (
        INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE,
        ConceptoIngreso,
    )
    from ._config_support import LLMProvider
    from ._config_state_root import (
        FormerProductStateError,
        StateRootInputs,
        live_state_root_inputs,
        platform_user_data_root,
    )
    from ._confirmation_gate import (
        OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON,
        ConfirmationBlockReason,
        FindingResolutionAction,
        ReviewAdvisoryKind,
    )
    from ._corpus_sidecar import render_corpus_sidecar_text
    from ._credentials import (
        LENGTH_ALONE_IS_STRONG,
        LENGTH_FAIR_FLOOR,
        PROFILE_PASSWORD_MAX_SCALARS,
        PROFILE_PASSWORD_MAX_UTF8_BYTES,
        PROFILE_PASSWORD_MIN_SCALARS,
        PassphraseStrength,
        ProfilePasswordAssessment,
        ProfilePasswordRefusalReason,
        assess_passphrase_strength,
        assess_profile_password,
    )
    from ._declaracion_idioma import DeclaracionIdioma
    from ._descendant_relacion import (
        ART_58_2_ENTITLING_RELACIONES,
        ART_81_1_MATERNIDAD_RELACIONES,
        DescendantRelacion,
    )
    from ._deuda_direccion import DeudaDireccion
    from ._directory_scan import DirectoryEntryKind, iter_directory, scan_directory
    from ._document_shape import (
        AEAT_RECORD_BATCH_SHAPES,
        PDF_CONTAINER_SHAPES,
        STRUCTURED_DOCUMENT_SHAPES,
        DocumentShape,
    )
    from ._draft_discrepancy import DraftDiscrepancyKind
    from ._estado_casilla_oficial import EstadoCasillaOficial
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
        M303RegimenSimplificadoFact,
        M303RegimenSimplificadoFactProjectionRef,
        M303RegimenSimplificadoModuleProjectionRef,
        M303RegimenSimplificadoModuleValue,
        compile_filing_projection_ref,
        filing_projection_ref_casilla_id,
        hydrate_filing_projection_ref,
    )
    from ._foreign_asset_obligation import (
        FOREIGN_ASSET_CLASS_OBLIGATION_GROUP,
        MODELO_720_FOREIGN_ASSET_CLASS_CODES,
        ForeignAssetObligationGroup,
        M720AssetClassCode,
        foreign_asset_obligation_group,
    )
    from ._fsync import fsync_parent_dir
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
    from ._legal_review import REVIEWED_LEGAL_STATUSES, LegalReviewStatus
    from ._link_safety import is_link_like
    from ._lockfile_unlink import LOCKFILE_UNLINK_RETRY_SECONDS, unlink_lockfile
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
    from ._modelo_work_progress_state import ModeloWorkProgressState
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
        OperatorActionAxis,
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
        OrdenAnualIvaAgriculturalIndex,
        OrdenAnualIvaAgriculturalIngresoACuenta,
        OrdenAnualIvaAuthority,
        OrdenAnualIvaAuthorityUnit,
        OrdenAnualIvaDifficultJustification,
        OrdenAnualIvaIngresoACuenta,
        OrdenAnualIvaLorca2022Reduction,
        OrdenAnualIvaModule,
        OrdenAnualIvaSeasonalIndex,
        extract_orden_anual_iva_authority,
        extract_orden_anual_iva_tables,
        orden_anual_iva_activity_anchors,
        orden_anual_iva_authority_units,
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
        hydrate_scenario_filing_period,
        is_administrative_period_token,
        registry_period_kind,
    )
    from ._pid_liveness import pid_is_alive
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
    from ._profile_session import ProfileRecordUnavailability, ProfileSessionRefusalReason
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
    from ._record_design_epoch import (
        RECORD_DESIGN_EPOCH_PATTERN,
        RECORD_DESIGN_EPOCH_RE,
        record_design_epoch_year,
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
    from ._schema_family_disposition import (
        UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS,
        RegistrySchemaFamilyDisposition,
    )
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
    from .aggregation import (
        OBSERVATION_BACKED_BINDING_SOURCE_KINDS,
        AggregationCaptureKind,
        BindingSourceKind,
        CalculationSourceLineageRole,
        IntracomOperationType,
    )
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
    from .corpus_text import (
        CorpusAnchorResolutionError,
        CorpusRedactionMark,
        corpus_redaction_marks,
        extracted_unit_count,
        normalise_corpus_text,
        resolve_anchored_extracted_unit,
    )
    from .external_constants import M347_THRESHOLD_EUR, OutputLanguage
    from .hashing import content_hash_hex, sha256_hex
    from .locks import exclusive_file_lock
    from .manual_corpus_sidecar import (
        MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX,
        MANUAL_CORPUS_TEXT_SCHEMA_VERSION,
        MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
        ManualCorpusTextSidecar,
    )
    from .operations import (
        OperationCancellation,
        OperationClosePolicy,
        OperationDeadline,
        OperationDurability,
        OperationEffect,
        OperationEventKind,
        OperationInteractionKind,
        OperationLifecycle,
        OperationTerminalCondition,
    )
    from .output_rendering import OutputFormat
    from .product_identity import (
        AEAT_AUTHORITY_SHORT_NAME,
        PRODUCT_IDENTITY,
        AeatProductSoftwareEvidence,
        AeatProductSoftwareIdentity,
        AeatProgramIdentifier,
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
    "FOREIGN_ADDRESS_COMPONENTS",
    "FOREIGN_ADDRESS_INFIX",
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
    "NON_IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "NON_REGISTRY_MODELOS",
    "OBJECT_TUPLE_ADAPTER",
    "OBSERVATION_BACKED_BINDING_SOURCE_KINDS",
    "OFFICIAL_M210_TIPO_RENTA_CODES",
    "OFX_EXTRA",
    "OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON",
    "OPTIONAL_EXTRAS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "PDF_CONTAINER_SHAPES",
    "PERSISTED_FORMATS",
    "PRODUCT_IDENTITY",
    "PROFILE_PASSWORD_MAX_SCALARS",
    "PROFILE_PASSWORD_MAX_UTF8_BYTES",
    "PROFILE_PASSWORD_MIN_SCALARS",
    "PROSE_ELISION_MARKER",
    "QWEN_RESEARCH",
    "RECORD_DESIGN_EPOCH_PATTERN",
    "RECORD_DESIGN_EPOCH_RE",
    "RELEASED_FORMAT_FLOORS",
    "REVIEWED_LEGAL_STATUSES",
    "REVIEWED_REVISION_REVIEW_STATUSES",
    "ROOT_DERIVED_STORAGE_FIELDS",
    "SPANISH_ADDRESS_COMPONENTS",
    "SPANISH_ADDRESS_INFIXES",
    "STORAGE_FIELD_CATEGORIES",
    "STORAGE_ROOT_SETTINGS_FIELD",
    "STORAGE_TAXONOMY",
    "STRICT_FROZEN_CONFIG",
    "STRUCTURED_DOCUMENT_SHAPES",
    "STR_KEYED_MAPPING_ADAPTER",
    "UNDECLARED_REGISTRY_AUTHORITY_GRADE",
    "UNMODELED_OBLIGATIONS",
    "UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS",
    "AcceleratorKind",
    "ActionArgumentResolution",
    "ActionArgumentSource",
    "ActionArgumentStatus",
    "ActionConditionality",
    "ActionEvidenceProvenance",
    "AeatProductSoftwareEvidence",
    "AeatProductSoftwareIdentity",
    "AeatProgramIdentifier",
    "AggregationCaptureKind",
    "AmendmentKindRegime",
    "AmendmentLiabilityDirection",
    "Art104TresExclusion",
    "AuthProviderDescription",
    "AuthProviderKind",
    "BindingSourceKind",
    "BucketPointer",
    "CalculationSourceLineageRole",
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
    "CorpusRedactionMark",
    "CounterpartyTaxablePersonStatus",
    "DeclaracionIdioma",
    "DeploymentLicencePosture",
    "DescendantRelacion",
    "DeudaDireccion",
    "DirectoryEntryKind",
    "DocumentShape",
    "DraftDiscrepancyKind",
    "ElidedProse",
    "EstadoCasillaOficial",
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
    "LLMProvider",
    "LedgerSortField",
    "LedgerSortOrder",
    "LegalReviewStatus",
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
    "M303RegimenSimplificadoFact",
    "M303RegimenSimplificadoFactProjectionRef",
    "M303RegimenSimplificadoModuleProjectionRef",
    "M303RegimenSimplificadoModuleValue",
    "M720AssetClassCode",
    "ManualCorpusTextSidecar",
    "MetodoValoracion",
    "MissingOptionalExtraError",
    "ModelCandidate",
    "ModelLicence",
    "ModelRole",
    "ModelRuntime",
    "ModelSelectionAdvisory",
    "Modelo",
    "ModeloCalculationRouteId",
    "ModeloWorkProgressState",
    "NoRecoveryOutcome",
    "NotificacionEstadoServicio",
    "ObjetoTributario",
    "ObservedHeaderFact",
    "OfficialTipoRentaCode",
    "OperationCancellation",
    "OperationClosePolicy",
    "OperationDeadline",
    "OperationDurability",
    "OperationEffect",
    "OperationEventKind",
    "OperationInteractionKind",
    "OperationLifecycle",
    "OperationTerminalCondition",
    "OperatorActionAxis",
    "OperatorProgress",
    "OptionalExtra",
    "OrdenAnualHtmlParseError",
    "OrdenAnualIvaActivityTable",
    "OrdenAnualIvaAgriculturalIndex",
    "OrdenAnualIvaAgriculturalIngresoACuenta",
    "OrdenAnualIvaAuthority",
    "OrdenAnualIvaAuthorityUnit",
    "OrdenAnualIvaDifficultJustification",
    "OrdenAnualIvaIngresoACuenta",
    "OrdenAnualIvaLorca2022Reduction",
    "OrdenAnualIvaModule",
    "OrdenAnualIvaSeasonalIndex",
    "OutputFormat",
    "OutputLanguage",
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
    "ProfilePasswordAssessment",
    "ProfilePasswordRefusalReason",
    "ProfileRecordUnavailability",
    "ProfileSessionRefusalReason",
    "ProrrataActivityRowType",
    "ProrrataEspecialTransitionKind",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "RefundElection",
    "RegisterScopingSignal",
    "RegistryAuthorityGrade",
    "RegistryPeriodCode",
    "RegistrySchemaFamilyDisposition",
    "RegistrySelectorPeriodCode",
    "RentaDeclaracionType",
    "RescateType",
    "ResultDisposition",
    "ReviewAdvisoryKind",
    "RevisionReviewStatus",
    "SectorDiferenciadoLetra",
    "SecureObjectWrite",
    "ServiceCapability",
    "SourceConnectivityCandidateId",
    "SourceConnectivityCandidateIdentity",
    "SourceConnectivityCensusRow",
    "SourceConnectivityConnectedProof",
    "SourceConnectivityConnectionIdentity",
    "SourceConnectivityDisposition",
    "SourceConnectivityEncryptedRevisionProof",
    "SourceConnectivityExecutableEvidence",
    "SourceConnectivityExecutableEvidenceRole",
    "SourceConnectivityExpiryPosture",
    "SourceConnectivityFollowUp",
    "SourceConnectivityGrounding",
    "SourceConnectivityGroundingLocatorKind",
    "SourceConnectivityOperatorReachabilityProof",
    "SourceConnectivityProofAuthority",
    "SourceConnectivityResolverOwnershipProof",
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
    "assess_profile_password",
    "bucket_scoped_storage_path",
    "build_provenance_stamp",
    "candidates_for_role",
    "capture_pointer",
    "classify_amendment_liability_direction",
    "classify_post_filing_event_kind",
    "clear_pointer",
    "compile_filing_projection_ref",
    "content_hash_hex",
    "corpus_redaction_marks",
    "default_model_runtime_id",
    "derive_result_disposition",
    "detect_image_media_type",
    "elide_to_cap",
    "elided_prose",
    "exclusive_file_lock",
    "expected_floor",
    "extract_orden_anual_iva_authority",
    "extract_orden_anual_iva_tables",
    "extracted_unit_count",
    "filing_projection_ref_casilla_id",
    "fold_diacritics",
    "fold_printed_phrase",
    "foreign_asset_obligation_group",
    "freeze_toml",
    "freeze_toml_value",
    "fsync_parent_dir",
    "fts_or_group",
    "hardware_tier_for_free_bytes",
    "hydrate_filing_projection_ref",
    "hydrate_scenario_filing_period",
    "iban_mod_97",
    "is_administrative_period_token",
    "is_aeat_csv",
    "is_link_like",
    "iter_directory",
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
    "orden_anual_iva_authority_units",
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
    "record_design_epoch_year",
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
    "scan_directory",
    "sha256_hex",
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


# Name -> the one submodule that owns it. This facade re-exports 342 names
# across 89 submodules, and binding them eagerly cost 0.379 s for whichever
# single name the caller actually wanted. Every process in the tree imports
# this package, and the supervised key-derivation child pays it to perform one
# Argon2id hash.
#
# It replaces five hand-written resolver chains that covered 25 of the names
# through bespoke if-ladders and re-ran the import machinery on every attribute
# access. One table is now the sole mechanism, and the resolved value is written
# into module globals, so only the first access to a name goes through this hook.
#
# Ownership is unchanged: every name still has exactly one canonical home in
# this package's ``__all__``, and consumers still import it from here. Only
# WHEN the owning submodule executes has moved.
_LAZY_EXPORTS: dict[str, str] = {
    "ABSENT_SECURE_OBJECT_REVISION_ID": ".secure_object_write",
    "ACTIONABLE_POST_FILING_EVENT_KINDS": "._post_filing_event",
    "AEAT_AUTHORITY_SHORT_NAME": ".product_identity",
    "AEAT_CSV_MAX_LENGTH": "._aeat_csv",
    "AEAT_CSV_MIN_LENGTH": "._aeat_csv",
    "AEAT_CSV_PATTERN": "._aeat_csv",
    "AEAT_RECORD_BATCH_SHAPES": "._document_shape",
    "ANTHROPIC_COMMERCIAL_TERMS": "._model_catalogue",
    "ANTHROPIC_EXTRA": "._optional_extras",
    "APACHE_2_0": "._model_catalogue",
    "ART_104_TRES_AUTO_DERIVED_EXCLUSIONS": "._prorrata_exclusions",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS": "._prorrata_exclusions",
    "ART_58_2_ENTITLING_RELACIONES": "._descendant_relacion",
    "ART_81_1_MATERNIDAD_RELACIONES": "._descendant_relacion",
    "AcceleratorKind": "._hardware",
    "ActionArgumentResolution": "._action_argument_resolution",
    "ActionArgumentSource": "._operator_action_enums",
    "ActionArgumentStatus": "._operator_action_enums",
    "ActionConditionality": "._operator_action_enums",
    "ActionEvidenceProvenance": "._operator_action_enums",
    "AeatProductSoftwareEvidence": ".product_identity",
    "AeatProductSoftwareIdentity": ".product_identity",
    "AeatProgramIdentifier": ".product_identity",
    "AggregationCaptureKind": ".aggregation",
    "AmendmentKindRegime": "._amendment_kind_regime",
    "AmendmentLiabilityDirection": "._amendment_kind_regime",
    "Art104TresExclusion": "._prorrata_exclusions",
    "AuthProviderDescription": "._auth_provider",
    "AuthProviderKind": "._auth_provider",
    "BROWSER_EXTRA": "._optional_extras",
    "BindingSourceKind": ".aggregation",
    "CalculationSourceLineageRole": ".aggregation",
    "BucketPointer": "._bucket_pointer",
    "COMPATIBILITY_REGIME": ".compatibility_lifecycle",
    "CasillaId": "._casilla_id",
    "CasillaValueKind": "._casilla_value_kind",
    "ClassifierInputSource": "._classifier_input_source",
    "ClaveMovilRoute": "._auth_provider",
    "CompatibilityRegime": ".compatibility_lifecycle",
    "ConceptLifecycle": "._concept_lifecycle",
    "ConceptoIngreso": "._concepto_ingreso",
    "ConfirmationBlockReason": "._confirmation_gate",
    "ContentionCause": "._hardware",
    "ConvenioOverrideKind": "._irnr",
    "CorpusAnchorResolutionError": ".corpus_text",
    "CorpusRedactionMark": ".corpus_text",
    "CounterpartyTaxablePersonStatus": "._classifier_input_source",
    "DEFAULT_MODEL_BY_RUNTIME_AND_ROLE": "._model_catalogue",
    "DEFAULT_WRITE_PROVENANCE": ".secure_object_write",
    "DeclaracionIdioma": "._declaracion_idioma",
    "DeploymentLicencePosture": "._model_catalogue",
    "DescendantRelacion": "._descendant_relacion",
    "DeudaDireccion": "._deuda_direccion",
    "DirectoryEntryKind": "._directory_scan",
    "DocumentShape": "._document_shape",
    "DraftDiscrepancyKind": "._draft_discrepancy",
    "EXTERNAL_PATH_SETTINGS_FIELDS": "._storage_taxonomy",
    "ElidedProse": ".prose_elision",
    "EstadoCasillaOficial": "._estado_casilla_oficial",
    "ExportExemptionReason": "._export_exemption_reason",
    "ExportLayoutFormat": "._export_layout_format",
    "ExternalOracleCorpus": "._external_oracle_corpus",
    "ExternalPathDeclaration": "._storage_taxonomy",
    "ExternalPathRole": "._storage_taxonomy",
    "FETCH_GATED_M210_TIPO_RENTA_CODES": "._irnr",
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS": "._storage_taxonomy",
    "FOREIGN_ASSET_CLASS_OBLIGATION_GROUP": "._foreign_asset_obligation",
    "FieldGroundingOutcome": "._field_grounding",
    "FieldOrigin": "._field_origin",
    "FieldRole": "._field_role",
    "FiledHistoryDiscoverySignal": "._filed_history_discovery_signal",
    "FilingPeriodCode": "._period",
    "FilingProducerKey": "._filing_producer_key",
    "FilingProjectionRef": "._filing_projection_ref",
    "FindingResolutionAction": "._confirmation_gate",
    "FingerprintParticipation": "._storage_taxonomy",
    "ForeignAssetObligationGroup": "._foreign_asset_obligation",
    "FormerProductStateError": "._config_state_root",
    "GOOGLE_EXTRA": "._optional_extras",
    "GoogleCredentialSourceKind": "._google_credential_source",
    "HARDWARE_TIER_CAPABLE_FLOOR_BYTES": "._hardware",
    "HARDWARE_TIER_MODEST_FLOOR_BYTES": "._hardware",
    "HEX_PATTERN_128": "._hex",
    "HEX_PATTERN_16": "._hex",
    "HEX_PATTERN_64": "._hex",
    "HardwareTier": "._hardware",
    "Hex16Str": "._hex",
    "Hex64Str": "._hex",
    "IAE_SUBJECT_TIPOS_ACTIVIDAD": "._tipos_actividad",
    "IBAN_SHAPE_RE": "._iban",
    "INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE": "._concepto_ingreso",
    "IdentityReferent": ".product_identity",
    "ImageMediaType": "._image_media_type",
    "IntracomOperationType": ".aggregation",
    "IvaCategoryOutcome": "._iva_category_resolution",
    "IvaCompensationStateProvenance": "._iva_compensation_provenance",
    "IvaDeductionEvidenceAuthority": "._iva_deduction_fact",
    "IvaDeductionFactKind": "._iva_deduction_fact",
    "LENGTH_ALONE_IS_STRONG": "._credentials",
    "LENGTH_FAIR_FLOOR": "._credentials",
    "LLM_EXTRA": "._optional_extras",
    "LLMProvider": "._config_support",
    "LOCAL_TRANSPORT_LABEL": "._provenance_stamp",
    "LOCKFILE_UNLINK_RETRY_SECONDS": "._lockfile_unlink",
    "LedgerSortField": "._ledger_sort",
    "LedgerSortOrder": "._ledger_sort",
    "LegalReviewStatus": "._legal_review",
    "LicenceVerification": "._model_catalogue",
    "LinkInconsistencyDirection": "._invoice_link",
    "M210GrossIncomeSourceMode": "._irnr",
    "M210PayerMode": "._irnr",
    "M210_TIPO_RENTA_CODE_PROJECTION": "._irnr",
    "M303DifferentiatedDeductionProjectionField": "._filing_projection_ref",
    "M303DifferentiatedDeductionProjectionRef": "._filing_projection_ref",
    "M303Exonerado390ActivityField": "._filing_projection_ref",
    "M303Exonerado390ActivityProjectionRef": "._filing_projection_ref",
    "M303Exonerado390OperacionesTercerosProjectionRef": "._filing_projection_ref",
    "M303ProrrataActivityProjectionField": "._filing_projection_ref",
    "M303ProrrataActivityProjectionRef": "._filing_projection_ref",
    "M303RegimenSimplificadoActivityField": "._filing_projection_ref",
    "M303RegimenSimplificadoActivityProjectionRef": "._filing_projection_ref",
    "M303RegimenSimplificadoCohort": "._filing_projection_ref",
    "M303RegimenSimplificadoFact": "._filing_projection_ref",
    "M303RegimenSimplificadoFactProjectionRef": "._filing_projection_ref",
    "M303RegimenSimplificadoModuleProjectionRef": "._filing_projection_ref",
    "M303RegimenSimplificadoModuleValue": "._filing_projection_ref",
    "M347_THRESHOLD_EUR": ".external_constants",
    "OutputLanguage": ".external_constants",
    "OutputFormat": ".output_rendering",
    "M720AssetClassCode": "._foreign_asset_obligation",
    "MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX": ".manual_corpus_sidecar",
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION": ".manual_corpus_sidecar",
    "MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX": ".manual_corpus_sidecar",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES": "._foreign_asset_obligation",
    "MODEL_CATALOGUE": "._model_catalogue",
    "ManualCorpusTextSidecar": ".manual_corpus_sidecar",
    "MetodoValoracion": "._modelo_232_codigos",
    "MissingOptionalExtraError": "._optional_extras",
    "ModelCandidate": "._model_catalogue",
    "ModelLicence": "._model_catalogue",
    "ModelRole": "._model_catalogue",
    "ModelRuntime": "._model_catalogue",
    "ModelSelectionAdvisory": "._model_catalogue",
    "Modelo": "._modelo",
    "ModeloCalculationRouteId": "._calculation_route",
    "ModeloWorkProgressState": "._modelo_work_progress_state",
    "PROFILE_PASSWORD_MAX_SCALARS": "._credentials",
    "PROFILE_PASSWORD_MAX_UTF8_BYTES": "._credentials",
    "PROFILE_PASSWORD_MIN_SCALARS": "._credentials",
    "NON_IAE_SUBJECT_TIPOS_ACTIVIDAD": "._tipos_actividad",
    "NON_REGISTRY_MODELOS": "._modelo",
    "NoRecoveryOutcome": "._operator_action_enums",
    "NotificacionEstadoServicio": "._notificacion_estado_servicio",
    "OBJECT_TUPLE_ADAPTER": "._type_adapters",
    "OBSERVATION_BACKED_BINDING_SOURCE_KINDS": ".aggregation",
    "OFFICIAL_M210_TIPO_RENTA_CODES": "._irnr",
    "OFX_EXTRA": "._optional_extras",
    "OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON": "._confirmation_gate",
    "OPTIONAL_EXTRAS": "._optional_extras",
    "OUT_OF_SCOPE_OBLIGATIONS": "._modelo",
    "ObjetoTributario": "._objeto_tributario",
    "ObservedHeaderFact": "._observed_header_fact",
    "OfficialTipoRentaCode": "._irnr",
    "OperationCancellation": ".operations",
    "OperationClosePolicy": ".operations",
    "OperationDeadline": ".operations",
    "OperationDurability": ".operations",
    "OperationEffect": ".operations",
    "OperationEventKind": ".operations",
    "OperationInteractionKind": ".operations",
    "OperationLifecycle": ".operations",
    "OperationTerminalCondition": ".operations",
    "OperatorActionAxis": "._operator_action_enums",
    "OperatorProgress": "._operator_progress",
    "OptionalExtra": "._optional_extras",
    "OrdenAnualHtmlParseError": "._orden_anual_html",
    "OrdenAnualIvaActivityTable": "._orden_anual_html",
    "OrdenAnualIvaAgriculturalIndex": "._orden_anual_html",
    "OrdenAnualIvaAgriculturalIngresoACuenta": "._orden_anual_html",
    "OrdenAnualIvaAuthority": "._orden_anual_html",
    "OrdenAnualIvaAuthorityUnit": "._orden_anual_html",
    "OrdenAnualIvaDifficultJustification": "._orden_anual_html",
    "OrdenAnualIvaIngresoACuenta": "._orden_anual_html",
    "OrdenAnualIvaLorca2022Reduction": "._orden_anual_html",
    "OrdenAnualIvaModule": "._orden_anual_html",
    "OrdenAnualIvaSeasonalIndex": "._orden_anual_html",
    "PDF_CONTAINER_SHAPES": "._document_shape",
    "PERSISTED_FORMATS": ".compatibility_lifecycle",
    "PRODUCT_IDENTITY": ".product_identity",
    "PROSE_ELISION_MARKER": ".prose_elision",
    "PassphraseStrength": "._credentials",
    "ProfilePasswordAssessment": "._credentials",
    "ProfilePasswordRefusalReason": "._credentials",
    "PaymentElection": "._payment_election",
    "Period": "._period",
    "PeriodError": "._period",
    "PeriodKind": "._period",
    "PersistedFormatClass": ".compatibility_lifecycle",
    "PostFilingEventKind": "._post_filing_event",
    "PreconditionActionIdentity": "._precondition_action_invariants",
    "PreconditionEvidence": "._precondition_action_invariants",
    "PreconditionOutcomeInvariant": "._precondition_action_invariants",
    "PriorDomiciliationElection": "._prior_domiciliation_election",
    "ProductIdentity": ".product_identity",
    "ProfileRecordUnavailability": "._profile_session",
    "ProfileSessionRefusalReason": "._profile_session",
    "ProrrataActivityRowType": "._prorrata_register",
    "ProrrataEspecialTransitionKind": "._prorrata_register",
    "ProrrataProvisionalProvenance": "._prorrata_register",
    "ProrrataRegisterRegime": "._prorrata_register",
    "QWEN_RESEARCH": "._model_catalogue",
    "FOREIGN_ADDRESS_COMPONENTS": "._address_components",
    "FOREIGN_ADDRESS_INFIX": "._address_components",
    "SPANISH_ADDRESS_COMPONENTS": "._address_components",
    "SPANISH_ADDRESS_INFIXES": "._address_components",
    "RECORD_DESIGN_EPOCH_PATTERN": "._record_design_epoch",
    "RECORD_DESIGN_EPOCH_RE": "._record_design_epoch",
    "RELEASED_FORMAT_FLOORS": ".compatibility_lifecycle",
    "REVIEWED_LEGAL_STATUSES": "._legal_review",
    "REVIEWED_REVISION_REVIEW_STATUSES": "._revision_review",
    "ROOT_DERIVED_STORAGE_FIELDS": "._storage_taxonomy",
    "RefundElection": "._refund_election",
    "RegisterScopingSignal": "._register_scoping_signal",
    "RegistryAuthorityGrade": "._authority_grade",
    "RegistryPeriodCode": "._period",
    "RegistrySchemaFamilyDisposition": "._schema_family_disposition",
    "RegistrySelectorPeriodCode": "._period",
    "RentaDeclaracionType": "._renta_declaracion_type",
    "RescateType": "._rescate_type",
    "ResultDisposition": "._result_disposition",
    "ReviewAdvisoryKind": "._confirmation_gate",
    "RevisionReviewStatus": "._revision_review",
    "STORAGE_FIELD_CATEGORIES": "._storage_taxonomy",
    "STORAGE_ROOT_SETTINGS_FIELD": "._storage_taxonomy",
    "STORAGE_TAXONOMY": "._storage_taxonomy",
    "STRICT_FROZEN_CONFIG": "._models",
    "STRUCTURED_DOCUMENT_SHAPES": "._document_shape",
    "STR_KEYED_MAPPING_ADAPTER": "._type_adapters",
    "SectorDiferenciadoLetra": "._prorrata_register",
    "SecureObjectWrite": ".secure_object_write",
    "ServiceCapability": "._capabilities",
    "SourceConnectivityCandidateId": ".source_connectivity",
    "SourceConnectivityCandidateIdentity": ".source_connectivity",
    "SourceConnectivityCensusRow": ".source_connectivity",
    "SourceConnectivityConnectedProof": ".source_connectivity",
    "SourceConnectivityConnectionIdentity": ".source_connectivity",
    "SourceConnectivityDisposition": ".source_connectivity",
    "SourceConnectivityEncryptedRevisionProof": ".source_connectivity",
    "SourceConnectivityExecutableEvidence": ".source_connectivity",
    "SourceConnectivityExecutableEvidenceRole": ".source_connectivity",
    "SourceConnectivityExpiryPosture": ".source_connectivity",
    "SourceConnectivityFollowUp": ".source_connectivity",
    "SourceConnectivityGrounding": ".source_connectivity",
    "SourceConnectivityGroundingLocatorKind": ".source_connectivity",
    "SourceConnectivityOperatorReachabilityProof": ".source_connectivity",
    "SourceConnectivityProofAuthority": ".source_connectivity",
    "SourceConnectivityResolverOwnershipProof": ".source_connectivity",
    "SpanishStemmer": "._spanish_stemming",
    "StandardPeriodCode": "._period",
    "StateRootInputs": "._config_state_root",
    "StorageArea": "._storage_taxonomy",
    "StorageCategory": "._storage_taxonomy",
    "StorageGrouping": "._storage_taxonomy",
    "StorageLifecycle": "._storage_taxonomy",
    "StorageLocation": "._storage_taxonomy",
    "StorageNodeKind": "._storage_taxonomy",
    "StorageOverridePolicy": "._storage_taxonomy",
    "StorageScope": "._storage_taxonomy",
    "SyncSurface": "._sync_surface",
    "TaxDomain": "._tax_domain",
    "TipoActividad": "._tipos_actividad",
    "TipoOperacionVinculada": "._modelo_232_codigos",
    "TipoRentaGroundingTier": "._irnr",
    "TipoRentaIrnr": "._irnr",
    "TipoVinculacion": "._modelo_232_codigos",
    "UNDECLARED_REGISTRY_AUTHORITY_GRADE": "._authority_grade",
    "UNMODELED_OBLIGATIONS": "._modelo",
    "UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS": "._schema_family_disposition",
    "record_design_epoch_year": "._record_design_epoch",
    "accepted_filing_period_codes": "._period",
    "accepted_filing_period_patterns": "._period",
    "accepted_period_codes": "._period",
    "accepted_period_patterns": "._period",
    "assess_passphrase_strength": "._credentials",
    "assess_profile_password": "._credentials",
    "bucket_scoped_storage_path": "._storage_taxonomy",
    "build_provenance_stamp": "._provenance_stamp",
    "candidates_for_role": "._model_catalogue",
    "capture_pointer": "._bucket_pointer_io",
    "classify_amendment_liability_direction": "._amendment_kind_regime",
    "classify_post_filing_event_kind": "._post_filing_event",
    "clear_pointer": "._bucket_pointer_io",
    "compile_filing_projection_ref": "._filing_projection_ref",
    "content_hash_hex": ".hashing",
    "corpus_redaction_marks": ".corpus_text",
    "default_model_runtime_id": "._model_catalogue",
    "derive_result_disposition": "._result_disposition",
    "detect_image_media_type": "._image_media_type",
    "elide_to_cap": ".prose_elision",
    "elided_prose": ".prose_elision",
    "exclusive_file_lock": ".locks",
    "expected_floor": ".compatibility_lifecycle",
    "extract_orden_anual_iva_authority": "._orden_anual_html",
    "extract_orden_anual_iva_tables": "._orden_anual_html",
    "extracted_unit_count": ".corpus_text",
    "filing_projection_ref_casilla_id": "._filing_projection_ref",
    "fold_diacritics": ".text_fold",
    "fold_printed_phrase": ".text_fold",
    "foreign_asset_obligation_group": "._foreign_asset_obligation",
    "freeze_toml": "._toml",
    "freeze_toml_value": "._toml",
    "fsync_parent_dir": "._fsync",
    "fts_or_group": "._fts_query",
    "hardware_tier_for_free_bytes": "._hardware",
    "hydrate_filing_projection_ref": "._filing_projection_ref",
    "hydrate_scenario_filing_period": "._period",
    "iban_mod_97": "._iban",
    "is_administrative_period_token": "._period",
    "is_aeat_csv": "._aeat_csv",
    "is_link_like": "._link_safety",
    "iter_directory": "._directory_scan",
    "lineage_obligations": ".compatibility_lifecycle",
    "live_state_root_inputs": "._config_state_root",
    "misclassified_floor_keys": ".compatibility_lifecycle",
    "model_candidate": "._model_catalogue",
    "modelo_has_codified_amendment_regime": "._amendment_kind_regime",
    "modelo_has_codified_disposition": "._result_disposition",
    "normalise_aeat_csv": "._aeat_csv",
    "normalise_corpus_text": ".corpus_text",
    "normalise_iban": "._iban",
    "normalise_product_identity_references": ".product_identity",
    "optional_extra_available": "._optional_extras",
    "optional_extra_for_module": "._optional_extras",
    "orden_anual_iva_activity_anchors": "._orden_anual_html",
    "orden_anual_iva_authority_units": "._orden_anual_html",
    "orden_anual_iva_table_text": "._orden_anual_html",
    "parse_toml_text": "._toml",
    "permitted_amendment_kind_values": "._amendment_kind_regime",
    "pid_is_alive": "._pid_liveness",
    "platform_user_data_root": "._config_state_root",
    "pointer_path": "._bucket_pointer_io",
    "post_filing_event_is_actionable": "._post_filing_event",
    "project_m210_tipo_renta_code": "._irnr",
    "provenance_stamp_transport": "._provenance_stamp",
    "provenance_transport_label": "._provenance_stamp",
    "read_pointer": "._bucket_pointer_io",
    "read_toml": "._toml",
    "registry_period_kind": "._period",
    "render_corpus_sidecar_text": "._corpus_sidecar",
    "require_active_bucket_id": "._bucket_pointer_io",
    "require_optional_extra": "._optional_extras",
    "resolve_active_bucket_id": "._bucket_pointer_io",
    "resolve_amendment_kind_regime": "._amendment_kind_regime",
    "resolve_anchored_extracted_unit": ".corpus_text",
    "resolve_notificacion_estado_servicio": "._notificacion_estado_servicio",
    "resolve_repository_bucket_id": "._bucket_pointer_io",
    "restore_pointer": "._bucket_pointer_io",
    "result_disposition_casilla_ids": "._result_disposition",
    "result_disposition_is_refund": "._result_disposition",
    "result_disposition_requires_bank_account": "._result_disposition",
    "scan_directory": "._directory_scan",
    "sha256_hex": ".hashing",
    "spanish_stemmer": "._spanish_stemming",
    "spanish_word_tokens": "._spanish_stemming",
    "stale_persisted_format_declarations": ".compatibility_lifecycle",
    "stem_spanish_terms": "._spanish_stemming",
    "stem_spanish_text": "._spanish_stemming",
    "storage_location": "._storage_taxonomy",
    "storage_path": "._storage_taxonomy",
    "storage_tree_targets": "._storage_taxonomy",
    "to_str_keyed_dict": "._toml",
    "undeclared_persisted_formats": ".compatibility_lifecycle",
    "unfloored_durable_formats": ".compatibility_lifecycle",
    "unicode_compose": ".text_fold",
    "unknown_floor_keys": ".compatibility_lifecycle",
    "unlink_lockfile": "._lockfile_unlink",
    "validated_casilla_id": "._casilla_id",
    "validated_casilla_id_map": "._casilla_id",
    "write_pointer": "._bucket_pointer_io",
}


# Every loader target is a closed literal from the map above.  The attribute
# name selects one of these pre-bound loaders; it never becomes an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one public name by importing only the submodule that owns it."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_name)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_name!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))

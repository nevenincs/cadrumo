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
registry gaps. :func:`pid_is_alive` is the shared
cross-platform PID-liveness probe consumed by every crash-recoverable
lockfile (bucket lockfile, auth-acquisition lock), and :func:`unlink_lockfile`
is the matching shared removal primitive those same locks use to survive the
Windows sharing violation a waiter's open handle causes. TOML and option utilities expose
:func:`read_toml`, :func:`parse_toml_text`, :func:`freeze_toml`,
:class:`OptionalExtra`, and :func:`require_optional_extra`. Directory
listing goes through :func:`~cadrumo.core.directory_scan.scan_directory` (sorted
and materialised) and :func:`~cadrumo.core.directory_scan.iter_directory` (lazy,
for early-exit callers), narrowed by
:class:`~cadrumo.core.directory_scan.DirectoryEntryKind` — the one ``os.scandir`` walk every layer shares
instead of reaching for ``Path.glob``. Filing-result
helpers expose the codified :class:`ResultDisposition` mapping and its
casilla/refund predicates. Service and operator-adjacent primitives include
:class:`ServiceCapability`, :class:`LedgerSortField`,
:class:`LedgerSortOrder`, :data:`IBAN_SHAPE_RE`, and :func:`iban_mod_97`. The
closed :class:`GoogleCredentialSourceKind` taxonomy governs which mechanism
:mod:`adapters.outbound.google` uses to obtain Google API credentials.

``BindingSourceKind`` is resolved through ``__getattr__`` so callers can
import the public core facade without eagerly paying for registry taxonomy.

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
    from .action_argument_resolution import ActionArgumentResolution
    from .aeat_csv import (
        AEAT_CSV_MAX_LENGTH,
        AEAT_CSV_MIN_LENGTH,
        AEAT_CSV_PATTERN,
        is_aeat_csv,
        normalise_aeat_csv,
    )
    from .amendment_kind_regime import (
        AmendmentLiabilityDirection,
        classify_amendment_liability_direction,
        permitted_amendment_kind_values,
        resolve_amendment_kind_regime,
    )
    from .auth_provider import AuthProviderDescription, AuthProviderKind, ClaveMovilRoute
    from .authority_grade import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
    from .calculation_route import ModeloCalculationRouteId
    from .capabilities import ServiceCapability
    from .casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
    from .casilla_value_kind import CasillaValueKind
    from .classifier_input_source import ClassifierInputSource, CounterpartyTaxablePersonStatus
    from .concept_lifecycle import ConceptLifecycle
    from .concepto_ingreso import (
        INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE,
        INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE,
        ConceptoIngreso,
    )
    from .config_state_root import (
        FormerProductStateError,
        StateRootInputs,
        live_state_root_inputs,
        platform_user_data_root,
    )
    from .config_support import LLMProvider
    from .confirmation_gate import (
        ConfirmationBlockReason,
        FindingResolutionAction,
        ReviewAdvisoryKind,
    )
    from .corpus_sidecar import render_corpus_sidecar_text
    from .declaracion_idioma import DeclaracionIdioma
    from .descendant_relacion import (
        ART_58_2_ENTITLING_RELACIONES,
        ART_81_1_MATERNIDAD_RELACIONES,
        DescendantRelacion,
    )
    from .deuda_direccion import DeudaDireccion
    from .document_shape import (
        AEAT_RECORD_BATCH_SHAPES,
        PDF_CONTAINER_SHAPES,
        STRUCTURED_DOCUMENT_SHAPES,
        DocumentShape,
    )
    from .draft_discrepancy import DraftDiscrepancyKind
    from ._estado_casilla_oficial import EstadoCasillaOficial
    from ._export_exemption_reason import ExportExemptionReason
    from ._export_layout_format import ExportLayoutFormat
    from ._external_oracle_corpus import ExternalOracleCorpus
    from .field_grounding import FieldGroundingOutcome
    from .field_origin import FieldOrigin
    from ._field_role import FieldRole
    from ._filed_history_discovery_signal import FiledHistoryDiscoverySignal
    from .filing_producer_key import FilingProducerKey
    from .filing_projection_ref import (
        M303_MESA_FACTS,
        M303_REPEATING_FACTS,
        FilingProjectionRef,
        M296AnexoCertificadoField,
        M296AnexoCertificadoProjectionRef,
        M296AnexoPagoField,
        M296AnexoPagoProjectionRef,
        M296PerceptorField,
        M296PerceptorInteresesField,
        M296PerceptorInteresesProjectionRef,
        M296PerceptorProjectionRef,
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
        M390ActivityField,
        M390DifferentiatedDeductionProjectionField,
        M390ProrrataActivityProjectionField,
        M390RegimenSimplificadoActivityField,
        M390RegimenSimplificadoCohort,
        M390RegimenSimplificadoModuleValue,
        M390RepresentativeField,
        M390RepresentativeKind,
        compile_filing_projection_ref,
        filing_projection_ref_casilla_id,
        hydrate_filing_projection_ref,
    )
    from ._foreign_asset_obligation import (
        MODELO_720_FOREIGN_ASSET_CLASS_CODES,
        ForeignAssetObligationGroup,
        M720AssetClassCode,
        foreign_asset_obligation_group,
        obligation_groups_established_by_legal_refs,
    )
    from ._fsync import fsync_parent_dir
    from ._fts_query import fts_or_group
    from ._google_credential_source import GoogleCredentialSourceKind
    from ._hardware import (
        AcceleratorKind,
        ContentionCause,
        HardwareTier,
        hardware_tier_for_free_bytes,
    )
    from .hex import HEX_PATTERN_16, HEX_PATTERN_64, HEX_PATTERN_128, Hex16Str, Hex64Str
    from ._iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
    from ._image_media_type import ImageMediaType, detect_image_media_type
    from ._invoice_link import LinkInconsistencyDirection
    from .irnr import (
        FETCH_GATED_M210_TIPO_RENTA_CODES,
        M210_TIPO_RENTA_CODE_PROJECTION,
        OFFICIAL_M210_TIPO_RENTA_CODES,
        ConvenioOverrideKind,
        M210GrossIncomeSourceMode,
        M210PayerMode,
        TipoRentaGroundingTier,
        TipoRentaIrnr,
        project_m210_tipo_renta_code,
    )
    from ._iva_category_resolution import IvaCategoryOutcome
    from .iva_compensation_provenance import IvaCompensationStateProvenance
    from .iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
    from ._ledger_sort import LedgerSortField, LedgerSortOrder
    from ._legal_review import REVIEWED_LEGAL_STATUSES, LegalReviewStatus
    from ._link_safety import is_link_like
    from ._lockfile_unlink import LOCKFILE_UNLINK_RETRY_SECONDS, unlink_lockfile
    from .model_catalogue import (
        DEFAULT_MODEL_BY_RUNTIME_AND_ROLE,
        MODEL_CATALOGUE,
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
    from .modelo import NON_REGISTRY_MODELOS, OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo
    from ._modelo_232_codigos import MetodoValoracion, TipoOperacionVinculada, TipoVinculacion
    from ._modelo_work_progress_state import ModeloWorkProgressState
    from .models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    from ._notificacion_estado_servicio import (
        NotificacionEstadoServicio,
        resolve_notificacion_estado_servicio,
    )
    from ._objeto_tributario import ObjetoTributario
    from ._observed_header_fact import ObservedHeaderFact
    from .operator_action_enums import (
        ActionArgumentSource,
        ActionArgumentStatus,
        ActionConditionality,
        ActionEvidenceProvenance,
        NoRecoveryOutcome,
        OperatorActionAxis,
    )
    from ._operator_progress import OperatorProgress
    from .optional_extras import (
        ANTHROPIC_EXTRA,
        BROWSER_EXTRA,
        GOOGLE_EXTRA,
        LLM_EXTRA,
        OFX_EXTRA,
        OPTIONAL_EXTRAS,
        MissingOptionalExtraError,
        OptionalExtra,
        optional_extra_available,
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
    from .payment_election import PaymentElection
    from .period import (
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
    from .prior_domiciliation_election import PriorDomiciliationElection
    from ._profile_session import ProfileRecordUnavailability, ProfileSessionRefusalReason
    from ._prorrata_exclusions import (
        ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS,
        Art104TresExclusion,
    )
    from .prorrata_register import (
        ProrrataActivityRowType,
        ProrrataEspecialTransitionKind,
        ProrrataProvisionalProvenance,
        ProrrataRegisterRegime,
        SectorDiferenciadoLetra,
        regime_apportions_deduction,
    )
    from .provenance_stamp import (
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
    from .result_disposition import (
        ResultDisposition,
        derive_result_disposition,
        modelo_has_codified_disposition,
        result_disposition_casilla_ids,
        result_disposition_is_refund,
        result_disposition_requires_bank_account,
    )
    from .revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
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
    from .storage_taxonomy import (
        EXTERNAL_PATH_SETTINGS_FIELDS,
        FINGERPRINT_EXCLUDED_STORAGE_FIELDS,
        ROOT_DERIVED_STORAGE_FIELDS,
        STORAGE_FIELD_CATEGORIES,
        STORAGE_ROOT_SETTINGS_FIELD,
        STORAGE_TAXONOMY,
        ExternalPathRole,
        FingerprintParticipation,
        StorageArea,
        StorageCategory,
        StorageCustodyProfile,
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
    from .toml import freeze_toml, read_toml, to_str_keyed_dict
    from .type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
    from .aggregation import (
        OBSERVATION_BACKED_BINDING_SOURCE_KINDS,
        AggregationCaptureKind,
        BindingAggregationOp,
        BindingSourceKind,
        CalculationSourceLineageRole,
        IntracomOperationType,
        ThirdPartyDeclarationRole,
        TravelAgencyMediationType,
    )
    from .compatibility_lifecycle import (
        COMPATIBILITY_REGIME,
        PERSISTED_FORMATS,
        RELEASED_FORMAT_FLOORS,
        PersistedFormatClass,
        expected_floor,
        lineage_obligations,
        stale_persisted_format_declarations,
        undeclared_persisted_formats,
    )
    from .corpus_text import (
        CorpusAnchorResolutionError,
        corpus_redaction_marks,
        extracted_unit_count,
        normalise_corpus_text,
        resolve_anchored_extracted_unit,
    )
    from .external_constants import M347_CLAVE_C_THRESHOLD_EUR, M347_THRESHOLD_EUR, OutputLanguage
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
        PRODUCT_IDENTITY,
        AeatProductSoftwareEvidence,
        AeatProductSoftwareIdentity,
        normalise_product_identity_references,
    )
    from .prose_elision import PROSE_ELISION_MARKER, ElidedProse, elide_to_cap, elided_prose
    from .secure_object_write import (
        ABSENT_SECURE_OBJECT_REVISION_ID,
        DEFAULT_WRITE_PROVENANCE,
        SecureObjectWrite,
    )
    from .source_connectivity import (
        SourceConnectivityCandidateId,
        SourceConnectivityCandidateIdentity,
        SourceConnectivityCensusRow,
        SourceConnectivityConnectedProof,
        SourceConnectivityConnectionIdentity,
        SourceConnectivityDisposition,
        SourceConnectivityEncryptedRevisionProof,
        SourceConnectivityExecutableEvidence,
        SourceConnectivityExecutableEvidenceRole,
        SourceConnectivityExpiryPosture,
        SourceConnectivityFollowUp,
        SourceConnectivityGrounding,
        SourceConnectivityGroundingLocatorKind,
        SourceConnectivityOperatorReachabilityProof,
        SourceConnectivityProofAuthority,
        SourceConnectivityProofFailureCause,
        SourceConnectivityResolverOwnershipProof,
    )
    from .storage_materialization import STORAGE_ROOT_MODE, ensure_storage_tree
    from .text_fold import fold_diacritics, fold_printed_phrase, unicode_compose


__all__: list[str] = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "ACTIONABLE_POST_FILING_EVENT_KINDS",
    "AEAT_CSV_MAX_LENGTH",
    "AEAT_CSV_MIN_LENGTH",
    "AEAT_CSV_PATTERN",
    "AEAT_RECORD_BATCH_SHAPES",
    "ANTHROPIC_EXTRA",
    "ART_58_2_ENTITLING_RELACIONES",
    "ART_81_1_MATERNIDAD_RELACIONES",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS",
    "BROWSER_EXTRA",
    "COMPATIBILITY_REGIME",
    "DEFAULT_MODEL_BY_RUNTIME_AND_ROLE",
    "DEFAULT_WRITE_PROVENANCE",
    "EXTERNAL_PATH_SETTINGS_FIELDS",
    "FETCH_GATED_M210_TIPO_RENTA_CODES",
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS",
    "GOOGLE_EXTRA",
    "HEX_PATTERN_16",
    "HEX_PATTERN_64",
    "HEX_PATTERN_128",
    "IAE_SUBJECT_TIPOS_ACTIVIDAD",
    "IBAN_SHAPE_RE",
    "INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE",
    "INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE",
    "LLM_EXTRA",
    "LOCAL_TRANSPORT_LABEL",
    "LOCKFILE_UNLINK_RETRY_SECONDS",
    "M210_TIPO_RENTA_CODE_PROJECTION",
    "M303_MESA_FACTS",
    "M303_REPEATING_FACTS",
    "M347_CLAVE_C_THRESHOLD_EUR",
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
    "OPTIONAL_EXTRAS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "PDF_CONTAINER_SHAPES",
    "PERSISTED_FORMATS",
    "PRODUCT_IDENTITY",
    "PROSE_ELISION_MARKER",
    "RECORD_DESIGN_EPOCH_PATTERN",
    "RECORD_DESIGN_EPOCH_RE",
    "RELEASED_FORMAT_FLOORS",
    "REVIEWED_LEGAL_STATUSES",
    "REVIEWED_REVISION_REVIEW_STATUSES",
    "ROOT_DERIVED_STORAGE_FIELDS",
    "STORAGE_FIELD_CATEGORIES",
    "STORAGE_ROOT_MODE",
    "STORAGE_ROOT_SETTINGS_FIELD",
    "STORAGE_TAXONOMY",
    "STRICT_FROZEN_CONFIG",
    "STRICT_FROZEN_HIDDEN_INPUT_CONFIG",
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
    "AggregationCaptureKind",
    "AmendmentLiabilityDirection",
    "Art104TresExclusion",
    "AuthProviderDescription",
    "AuthProviderKind",
    "BindingAggregationOp",
    "BindingSourceKind",
    "CalculationSourceLineageRole",
    "CasillaId",
    "CasillaValueKind",
    "ClassifierInputSource",
    "ClaveMovilRoute",
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
    "EstadoCasillaOficial",
    "ExportExemptionReason",
    "ExportLayoutFormat",
    "ExternalOracleCorpus",
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
    "M296AnexoCertificadoField",
    "M296AnexoCertificadoProjectionRef",
    "M296AnexoPagoField",
    "M296AnexoPagoProjectionRef",
    "M296PerceptorField",
    "M296PerceptorInteresesField",
    "M296PerceptorInteresesProjectionRef",
    "M296PerceptorProjectionRef",
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
    "M390ActivityField",
    "M390DifferentiatedDeductionProjectionField",
    "M390ProrrataActivityProjectionField",
    "M390RegimenSimplificadoActivityField",
    "M390RegimenSimplificadoCohort",
    "M390RegimenSimplificadoModuleValue",
    "M390RepresentativeField",
    "M390RepresentativeKind",
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
    "SourceConnectivityProofFailureCause",
    "SourceConnectivityResolverOwnershipProof",
    "SpanishStemmer",
    "StandardPeriodCode",
    "StateRootInputs",
    "StorageArea",
    "StorageCategory",
    "StorageCustodyProfile",
    "StorageGrouping",
    "StorageLifecycle",
    "StorageLocation",
    "StorageNodeKind",
    "StorageOverridePolicy",
    "StorageScope",
    "SyncSurface",
    "TaxDomain",
    "ThirdPartyDeclarationRole",
    "TipoActividad",
    "TipoOperacionVinculada",
    "TipoRentaGroundingTier",
    "TipoRentaIrnr",
    "TipoVinculacion",
    "TravelAgencyMediationType",
    "accepted_filing_period_codes",
    "accepted_filing_period_patterns",
    "accepted_period_codes",
    "bucket_scoped_storage_path",
    "build_provenance_stamp",
    "candidates_for_role",
    "classify_amendment_liability_direction",
    "classify_post_filing_event_kind",
    "compile_filing_projection_ref",
    "content_hash_hex",
    "corpus_redaction_marks",
    "default_model_runtime_id",
    "derive_result_disposition",
    "detect_image_media_type",
    "elide_to_cap",
    "elided_prose",
    "ensure_storage_tree",
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
    "fsync_parent_dir",
    "fts_or_group",
    "hardware_tier_for_free_bytes",
    "hydrate_filing_projection_ref",
    "hydrate_scenario_filing_period",
    "iban_mod_97",
    "is_administrative_period_token",
    "is_aeat_csv",
    "is_link_like",
    "lineage_obligations",
    "live_state_root_inputs",
    "model_candidate",
    "modelo_has_codified_disposition",
    "normalise_aeat_csv",
    "normalise_corpus_text",
    "normalise_iban",
    "normalise_product_identity_references",
    "obligation_groups_established_by_legal_refs",
    "optional_extra_available",
    "orden_anual_iva_activity_anchors",
    "orden_anual_iva_authority_units",
    "orden_anual_iva_table_text",
    "permitted_amendment_kind_values",
    "pid_is_alive",
    "platform_user_data_root",
    "post_filing_event_is_actionable",
    "project_m210_tipo_renta_code",
    "provenance_stamp_transport",
    "provenance_transport_label",
    "read_toml",
    "record_design_epoch_year",
    "regime_apportions_deduction",
    "registry_period_kind",
    "render_corpus_sidecar_text",
    "require_optional_extra",
    "resolve_amendment_kind_regime",
    "resolve_anchored_extracted_unit",
    "resolve_notificacion_estado_servicio",
    "result_disposition_casilla_ids",
    "result_disposition_is_refund",
    "result_disposition_requires_bank_account",
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
    "unicode_compose",
    "unlink_lockfile",
    "validated_casilla_id",
    "validated_casilla_id_map",
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
    "AEAT_CSV_MAX_LENGTH": ".aeat_csv",
    "AEAT_CSV_MIN_LENGTH": ".aeat_csv",
    "AEAT_CSV_PATTERN": ".aeat_csv",
    "AEAT_RECORD_BATCH_SHAPES": ".document_shape",
    "ANTHROPIC_EXTRA": ".optional_extras",
    "ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS": "._prorrata_exclusions",
    "ART_58_2_ENTITLING_RELACIONES": ".descendant_relacion",
    "ART_81_1_MATERNIDAD_RELACIONES": ".descendant_relacion",
    "AcceleratorKind": "._hardware",
    "ActionArgumentResolution": ".action_argument_resolution",
    "ActionArgumentSource": ".operator_action_enums",
    "ActionArgumentStatus": ".operator_action_enums",
    "ActionConditionality": ".operator_action_enums",
    "ActionEvidenceProvenance": ".operator_action_enums",
    "AeatProductSoftwareEvidence": ".product_identity",
    "AeatProductSoftwareIdentity": ".product_identity",
    "AggregationCaptureKind": ".aggregation",
    "AmendmentLiabilityDirection": ".amendment_kind_regime",
    "Art104TresExclusion": "._prorrata_exclusions",
    "AuthProviderDescription": ".auth_provider",
    "AuthProviderKind": ".auth_provider",
    "BROWSER_EXTRA": ".optional_extras",
    "BindingAggregationOp": ".aggregation",
    "BindingSourceKind": ".aggregation",
    "CalculationSourceLineageRole": ".aggregation",
    "COMPATIBILITY_REGIME": ".compatibility_lifecycle",
    "CasillaId": ".casilla_id",
    "CasillaValueKind": ".casilla_value_kind",
    "ClassifierInputSource": ".classifier_input_source",
    "ClaveMovilRoute": ".auth_provider",
    "ConceptLifecycle": ".concept_lifecycle",
    "ConceptoIngreso": ".concepto_ingreso",
    "ConfirmationBlockReason": ".confirmation_gate",
    "ContentionCause": "._hardware",
    "ConvenioOverrideKind": ".irnr",
    "CorpusAnchorResolutionError": ".corpus_text",
    "CounterpartyTaxablePersonStatus": ".classifier_input_source",
    "DEFAULT_MODEL_BY_RUNTIME_AND_ROLE": ".model_catalogue",
    "DEFAULT_WRITE_PROVENANCE": ".secure_object_write",
    "DeclaracionIdioma": ".declaracion_idioma",
    "DeploymentLicencePosture": ".model_catalogue",
    "DescendantRelacion": ".descendant_relacion",
    "DeudaDireccion": ".deuda_direccion",
    "DocumentShape": ".document_shape",
    "DraftDiscrepancyKind": ".draft_discrepancy",
    "EXTERNAL_PATH_SETTINGS_FIELDS": ".storage_taxonomy",
    "ElidedProse": ".prose_elision",
    "EstadoCasillaOficial": "._estado_casilla_oficial",
    "ExportExemptionReason": "._export_exemption_reason",
    "ExportLayoutFormat": "._export_layout_format",
    "ExternalOracleCorpus": "._external_oracle_corpus",
    "ExternalPathRole": ".storage_taxonomy",
    "FETCH_GATED_M210_TIPO_RENTA_CODES": ".irnr",
    "FINGERPRINT_EXCLUDED_STORAGE_FIELDS": ".storage_taxonomy",
    "FieldGroundingOutcome": ".field_grounding",
    "FieldOrigin": ".field_origin",
    "FieldRole": "._field_role",
    "FiledHistoryDiscoverySignal": "._filed_history_discovery_signal",
    "FilingPeriodCode": ".period",
    "FilingProducerKey": ".filing_producer_key",
    "FilingProjectionRef": ".filing_projection_ref",
    "FindingResolutionAction": ".confirmation_gate",
    "FingerprintParticipation": ".storage_taxonomy",
    "ForeignAssetObligationGroup": "._foreign_asset_obligation",
    "FormerProductStateError": ".config_state_root",
    "GOOGLE_EXTRA": ".optional_extras",
    "GoogleCredentialSourceKind": "._google_credential_source",
    "HEX_PATTERN_128": ".hex",
    "HEX_PATTERN_16": ".hex",
    "HEX_PATTERN_64": ".hex",
    "HardwareTier": "._hardware",
    "Hex16Str": ".hex",
    "Hex64Str": ".hex",
    "IAE_SUBJECT_TIPOS_ACTIVIDAD": "._tipos_actividad",
    "IBAN_SHAPE_RE": "._iban",
    "INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE": ".concepto_ingreso",
    "INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE": ".concepto_ingreso",
    "ImageMediaType": "._image_media_type",
    "IntracomOperationType": ".aggregation",
    "IvaCategoryOutcome": "._iva_category_resolution",
    "IvaCompensationStateProvenance": ".iva_compensation_provenance",
    "IvaDeductionEvidenceAuthority": ".iva_deduction_fact",
    "IvaDeductionFactKind": ".iva_deduction_fact",
    "LLM_EXTRA": ".optional_extras",
    "LLMProvider": ".config_support",
    "LOCAL_TRANSPORT_LABEL": ".provenance_stamp",
    "LOCKFILE_UNLINK_RETRY_SECONDS": "._lockfile_unlink",
    "LedgerSortField": "._ledger_sort",
    "LedgerSortOrder": "._ledger_sort",
    "LegalReviewStatus": "._legal_review",
    "LicenceVerification": ".model_catalogue",
    "LinkInconsistencyDirection": "._invoice_link",
    "M210GrossIncomeSourceMode": ".irnr",
    "M210PayerMode": ".irnr",
    "M210_TIPO_RENTA_CODE_PROJECTION": ".irnr",
    "M296AnexoCertificadoField": ".filing_projection_ref",
    "M296AnexoCertificadoProjectionRef": ".filing_projection_ref",
    "M296AnexoPagoField": ".filing_projection_ref",
    "M296AnexoPagoProjectionRef": ".filing_projection_ref",
    "M296PerceptorField": ".filing_projection_ref",
    "M296PerceptorInteresesField": ".filing_projection_ref",
    "M296PerceptorInteresesProjectionRef": ".filing_projection_ref",
    "M296PerceptorProjectionRef": ".filing_projection_ref",
    "M303DifferentiatedDeductionProjectionField": ".filing_projection_ref",
    "M303DifferentiatedDeductionProjectionRef": ".filing_projection_ref",
    "M303Exonerado390ActivityField": ".filing_projection_ref",
    "M303Exonerado390ActivityProjectionRef": ".filing_projection_ref",
    "M303Exonerado390OperacionesTercerosProjectionRef": ".filing_projection_ref",
    "M303ProrrataActivityProjectionField": ".filing_projection_ref",
    "M303ProrrataActivityProjectionRef": ".filing_projection_ref",
    "M303RegimenSimplificadoActivityField": ".filing_projection_ref",
    "M303RegimenSimplificadoActivityProjectionRef": ".filing_projection_ref",
    "M303RegimenSimplificadoCohort": ".filing_projection_ref",
    "M303RegimenSimplificadoFact": ".filing_projection_ref",
    "M303RegimenSimplificadoFactProjectionRef": ".filing_projection_ref",
    "M303RegimenSimplificadoModuleProjectionRef": ".filing_projection_ref",
    "M303RegimenSimplificadoModuleValue": ".filing_projection_ref",
    "M303_MESA_FACTS": ".filing_projection_ref",
    "M303_REPEATING_FACTS": ".filing_projection_ref",
    "M390ActivityField": ".filing_projection_ref",
    "M390DifferentiatedDeductionProjectionField": ".filing_projection_ref",
    "M390ProrrataActivityProjectionField": ".filing_projection_ref",
    "M390RegimenSimplificadoActivityField": ".filing_projection_ref",
    "M390RegimenSimplificadoCohort": ".filing_projection_ref",
    "M390RegimenSimplificadoModuleValue": ".filing_projection_ref",
    "M390RepresentativeField": ".filing_projection_ref",
    "M390RepresentativeKind": ".filing_projection_ref",
    "M347_CLAVE_C_THRESHOLD_EUR": ".external_constants",
    "M347_THRESHOLD_EUR": ".external_constants",
    "OutputLanguage": ".external_constants",
    "OutputFormat": ".output_rendering",
    "M720AssetClassCode": "._foreign_asset_obligation",
    "MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX": ".manual_corpus_sidecar",
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION": ".manual_corpus_sidecar",
    "MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX": ".manual_corpus_sidecar",
    "MODELO_720_FOREIGN_ASSET_CLASS_CODES": "._foreign_asset_obligation",
    "MODEL_CATALOGUE": ".model_catalogue",
    "ManualCorpusTextSidecar": ".manual_corpus_sidecar",
    "MetodoValoracion": "._modelo_232_codigos",
    "MissingOptionalExtraError": ".optional_extras",
    "ModelCandidate": ".model_catalogue",
    "ModelLicence": ".model_catalogue",
    "ModelRole": ".model_catalogue",
    "ModelRuntime": ".model_catalogue",
    "ModelSelectionAdvisory": ".model_catalogue",
    "Modelo": ".modelo",
    "ModeloCalculationRouteId": ".calculation_route",
    "ModeloWorkProgressState": "._modelo_work_progress_state",
    "NON_IAE_SUBJECT_TIPOS_ACTIVIDAD": "._tipos_actividad",
    "NON_REGISTRY_MODELOS": ".modelo",
    "NoRecoveryOutcome": ".operator_action_enums",
    "NotificacionEstadoServicio": "._notificacion_estado_servicio",
    "OBJECT_TUPLE_ADAPTER": ".type_adapters",
    "OBSERVATION_BACKED_BINDING_SOURCE_KINDS": ".aggregation",
    "OFFICIAL_M210_TIPO_RENTA_CODES": ".irnr",
    "OFX_EXTRA": ".optional_extras",
    "OPTIONAL_EXTRAS": ".optional_extras",
    "OUT_OF_SCOPE_OBLIGATIONS": ".modelo",
    "ObjetoTributario": "._objeto_tributario",
    "ObservedHeaderFact": "._observed_header_fact",
    "OperationCancellation": ".operations",
    "OperationClosePolicy": ".operations",
    "OperationDeadline": ".operations",
    "OperationDurability": ".operations",
    "OperationEffect": ".operations",
    "OperationEventKind": ".operations",
    "OperationInteractionKind": ".operations",
    "OperationLifecycle": ".operations",
    "OperationTerminalCondition": ".operations",
    "OperatorActionAxis": ".operator_action_enums",
    "OperatorProgress": "._operator_progress",
    "OptionalExtra": ".optional_extras",
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
    "PDF_CONTAINER_SHAPES": ".document_shape",
    "PERSISTED_FORMATS": ".compatibility_lifecycle",
    "PRODUCT_IDENTITY": ".product_identity",
    "PROSE_ELISION_MARKER": ".prose_elision",
    "PaymentElection": ".payment_election",
    "Period": ".period",
    "PeriodError": ".period",
    "PeriodKind": ".period",
    "PersistedFormatClass": ".compatibility_lifecycle",
    "PostFilingEventKind": "._post_filing_event",
    "PreconditionActionIdentity": "._precondition_action_invariants",
    "PreconditionEvidence": "._precondition_action_invariants",
    "PreconditionOutcomeInvariant": "._precondition_action_invariants",
    "PriorDomiciliationElection": ".prior_domiciliation_election",
    "ProfileRecordUnavailability": "._profile_session",
    "ProfileSessionRefusalReason": "._profile_session",
    "ProrrataActivityRowType": ".prorrata_register",
    "ProrrataEspecialTransitionKind": ".prorrata_register",
    "ProrrataProvisionalProvenance": ".prorrata_register",
    "ProrrataRegisterRegime": ".prorrata_register",
    "regime_apportions_deduction": ".prorrata_register",
    "RECORD_DESIGN_EPOCH_PATTERN": "._record_design_epoch",
    "RECORD_DESIGN_EPOCH_RE": "._record_design_epoch",
    "RELEASED_FORMAT_FLOORS": ".compatibility_lifecycle",
    "REVIEWED_LEGAL_STATUSES": "._legal_review",
    "REVIEWED_REVISION_REVIEW_STATUSES": ".revision_review",
    "ROOT_DERIVED_STORAGE_FIELDS": ".storage_taxonomy",
    "RefundElection": "._refund_election",
    "RegisterScopingSignal": "._register_scoping_signal",
    "RegistryAuthorityGrade": ".authority_grade",
    "RegistryPeriodCode": ".period",
    "RegistrySchemaFamilyDisposition": "._schema_family_disposition",
    "RegistrySelectorPeriodCode": ".period",
    "RentaDeclaracionType": "._renta_declaracion_type",
    "RescateType": "._rescate_type",
    "ResultDisposition": ".result_disposition",
    "ReviewAdvisoryKind": ".confirmation_gate",
    "RevisionReviewStatus": ".revision_review",
    "STORAGE_FIELD_CATEGORIES": ".storage_taxonomy",
    "STORAGE_ROOT_MODE": ".storage_materialization",
    "STORAGE_ROOT_SETTINGS_FIELD": ".storage_taxonomy",
    "STORAGE_TAXONOMY": ".storage_taxonomy",
    "STRICT_FROZEN_CONFIG": ".models",
    "STRICT_FROZEN_HIDDEN_INPUT_CONFIG": ".models",
    "STRUCTURED_DOCUMENT_SHAPES": ".document_shape",
    "STR_KEYED_MAPPING_ADAPTER": ".type_adapters",
    "SectorDiferenciadoLetra": ".prorrata_register",
    "SecureObjectWrite": ".secure_object_write",
    "ServiceCapability": ".capabilities",
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
    "SourceConnectivityProofFailureCause": ".source_connectivity",
    "SourceConnectivityResolverOwnershipProof": ".source_connectivity",
    "SpanishStemmer": "._spanish_stemming",
    "StandardPeriodCode": ".period",
    "StateRootInputs": ".config_state_root",
    "StorageArea": ".storage_taxonomy",
    "StorageCategory": ".storage_taxonomy",
    "StorageCustodyProfile": ".storage_taxonomy",
    "StorageGrouping": ".storage_taxonomy",
    "StorageLifecycle": ".storage_taxonomy",
    "StorageLocation": ".storage_taxonomy",
    "StorageNodeKind": ".storage_taxonomy",
    "StorageOverridePolicy": ".storage_taxonomy",
    "StorageScope": ".storage_taxonomy",
    "SyncSurface": "._sync_surface",
    "TaxDomain": "._tax_domain",
    "ThirdPartyDeclarationRole": ".aggregation",
    "TipoActividad": "._tipos_actividad",
    "TipoOperacionVinculada": "._modelo_232_codigos",
    "TipoRentaGroundingTier": ".irnr",
    "TipoRentaIrnr": ".irnr",
    "TipoVinculacion": "._modelo_232_codigos",
    "TravelAgencyMediationType": ".aggregation",
    "UNDECLARED_REGISTRY_AUTHORITY_GRADE": ".authority_grade",
    "UNMODELED_OBLIGATIONS": ".modelo",
    "UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS": "._schema_family_disposition",
    "record_design_epoch_year": "._record_design_epoch",
    "accepted_filing_period_codes": ".period",
    "accepted_filing_period_patterns": ".period",
    "accepted_period_codes": ".period",
    "bucket_scoped_storage_path": ".storage_taxonomy",
    "build_provenance_stamp": ".provenance_stamp",
    "candidates_for_role": ".model_catalogue",
    "classify_amendment_liability_direction": ".amendment_kind_regime",
    "classify_post_filing_event_kind": "._post_filing_event",
    "compile_filing_projection_ref": ".filing_projection_ref",
    "content_hash_hex": ".hashing",
    "corpus_redaction_marks": ".corpus_text",
    "default_model_runtime_id": ".model_catalogue",
    "derive_result_disposition": ".result_disposition",
    "detect_image_media_type": "._image_media_type",
    "elide_to_cap": ".prose_elision",
    "elided_prose": ".prose_elision",
    "exclusive_file_lock": ".locks",
    "expected_floor": ".compatibility_lifecycle",
    "extract_orden_anual_iva_authority": "._orden_anual_html",
    "extract_orden_anual_iva_tables": "._orden_anual_html",
    "extracted_unit_count": ".corpus_text",
    "filing_projection_ref_casilla_id": ".filing_projection_ref",
    "fold_diacritics": ".text_fold",
    "fold_printed_phrase": ".text_fold",
    "foreign_asset_obligation_group": "._foreign_asset_obligation",
    "obligation_groups_established_by_legal_refs": "._foreign_asset_obligation",
    "freeze_toml": ".toml",
    "fsync_parent_dir": "._fsync",
    "fts_or_group": "._fts_query",
    "hardware_tier_for_free_bytes": "._hardware",
    "hydrate_filing_projection_ref": ".filing_projection_ref",
    "hydrate_scenario_filing_period": ".period",
    "iban_mod_97": "._iban",
    "is_administrative_period_token": ".period",
    "is_aeat_csv": ".aeat_csv",
    "is_link_like": "._link_safety",
    "lineage_obligations": ".compatibility_lifecycle",
    "live_state_root_inputs": ".config_state_root",
    "model_candidate": ".model_catalogue",
    "modelo_has_codified_disposition": ".result_disposition",
    "normalise_aeat_csv": ".aeat_csv",
    "normalise_corpus_text": ".corpus_text",
    "normalise_iban": "._iban",
    "normalise_product_identity_references": ".product_identity",
    "optional_extra_available": ".optional_extras",
    "orden_anual_iva_activity_anchors": "._orden_anual_html",
    "orden_anual_iva_authority_units": "._orden_anual_html",
    "orden_anual_iva_table_text": "._orden_anual_html",
    "permitted_amendment_kind_values": ".amendment_kind_regime",
    "pid_is_alive": "._pid_liveness",
    "platform_user_data_root": ".config_state_root",
    "post_filing_event_is_actionable": "._post_filing_event",
    "project_m210_tipo_renta_code": ".irnr",
    "provenance_stamp_transport": ".provenance_stamp",
    "provenance_transport_label": ".provenance_stamp",
    "read_toml": ".toml",
    "registry_period_kind": ".period",
    "render_corpus_sidecar_text": ".corpus_sidecar",
    "require_optional_extra": ".optional_extras",
    "resolve_amendment_kind_regime": ".amendment_kind_regime",
    "resolve_anchored_extracted_unit": ".corpus_text",
    "resolve_notificacion_estado_servicio": "._notificacion_estado_servicio",
    "result_disposition_casilla_ids": ".result_disposition",
    "result_disposition_is_refund": ".result_disposition",
    "result_disposition_requires_bank_account": ".result_disposition",
    "sha256_hex": ".hashing",
    "spanish_stemmer": "._spanish_stemming",
    "spanish_word_tokens": "._spanish_stemming",
    "stale_persisted_format_declarations": ".compatibility_lifecycle",
    "stem_spanish_terms": "._spanish_stemming",
    "stem_spanish_text": "._spanish_stemming",
    "storage_location": ".storage_taxonomy",
    "storage_path": ".storage_taxonomy",
    "ensure_storage_tree": ".storage_materialization",
    "storage_tree_targets": ".storage_taxonomy",
    "to_str_keyed_dict": ".toml",
    "undeclared_persisted_formats": ".compatibility_lifecycle",
    "unicode_compose": ".text_fold",
    "unlink_lockfile": "._lockfile_unlink",
    "validated_casilla_id": ".casilla_id",
    "validated_casilla_id_map": ".casilla_id",
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

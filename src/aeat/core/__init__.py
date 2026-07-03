"""Core cross-cutting infrastructure shared by every ``aeat`` layer.

The core layer is the innermost package in the hexagonal architecture. It
exports typed primitives, configuration-adjacent helpers, parsing utilities,
and layer-neutral policies that domain, application, adapter, and entrypoint
modules can import without depending outward.

The public facade groups four stable surfaces. Immutable modelling primitives
include :data:`STRICT_FROZEN_CONFIG`, :class:`CasillaId`, :class:`Modelo`,
:class:`Period`, :class:`StandardPeriodCode`, ``PeriodKind``,
:class:`TaxDomain`, :class:`RefundElection`, :class:`ResultDisposition`, and
the lazily resolved :class:`BindingSourceKind` registry-source taxonomy.
Obligation-coverage mappings expose :data:`OUT_OF_SCOPE_OBLIGATIONS` and
:data:`UNMODELED_OBLIGATIONS`, the codified AEAT modelo sets the overview
coverage report reads to distinguish product-scope exclusions from
registry gaps. Active-bucket context uses the plaintext :class:`BucketPointer` value object
plus :func:`pointer_path`, :func:`read_pointer`, :func:`write_pointer`,
:func:`resolve_active_bucket_id`, :func:`require_active_bucket_id`, and
:func:`resolve_repository_bucket_id`. TOML and option utilities expose
:func:`read_toml`, :func:`parse_toml_text`, :func:`freeze_toml`,
:class:`OptionalExtra`, and :func:`require_optional_extra`. Filing-result
helpers expose the codified :class:`ResultDisposition` mapping and its
casilla/refund predicates. Service and operator-adjacent primitives include
:class:`ServiceCapability`, :class:`LedgerSortField`,
:class:`LedgerSortOrder`, :data:`IBAN_SHAPE_RE`, and :func:`iban_mod_97`.

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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._amendment_kind_regime import (
    AmendmentKindRegime,
    AmendmentLiabilityDirection,
    classify_amendment_liability_direction,
    modelo_has_codified_amendment_regime,
    permitted_amendment_kind_values,
    resolve_amendment_kind_regime,
)
from ._capabilities import ServiceCapability
from ._casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ._iban import IBAN_SHAPE_RE, iban_mod_97
from ._irnr import ConvenioOverrideKind, TipoRentaIrnr
from ._ledger_sort import LedgerSortField, LedgerSortOrder
from ._modelo import NON_REGISTRY_MODELOS, OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo
from ._models import STRICT_FROZEN_CONFIG
from ._optional_extras import (
    ANTHROPIC_EXTRA,
    BROWSER_EXTRA,
    GOOGLE_EXTRA,
    OPTIONAL_EXTRAS,
    MissingOptionalExtraError,
    OptionalExtra,
    optional_extra_available,
    require_optional_extra,
)
from ._period import (
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
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
from ._refund_election import RefundElection
from ._rescate_type import RescateType
from ._result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
)
from ._tax_domain import TaxDomain
from ._toml import freeze_toml, freeze_toml_value, parse_toml_text, read_toml, to_str_keyed_dict
from .secure_object_write import DEFAULT_WRITE_PROVENANCE, SecureObjectWrite

if TYPE_CHECKING:
    # Static bindings for the lazily-exposed surface below. At runtime these
    # resolve through ``__getattr__`` (cycle-safe); the type checker reads the
    # real callable signatures here.
    from ._bucket_pointer import BucketPointer
    from ._bucket_pointer_io import (
        pointer_path,
        read_pointer,
        require_active_bucket_id,
        resolve_active_bucket_id,
        resolve_repository_bucket_id,
        write_pointer,
    )
    from .aggregation import BindingSourceKind, IntracomOperationType

__all__: list[str] = [
    "ACTIONABLE_POST_FILING_EVENT_KINDS",
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "DEFAULT_WRITE_PROVENANCE",
    "GOOGLE_EXTRA",
    "IBAN_SHAPE_RE",
    "NON_REGISTRY_MODELOS",
    "OPTIONAL_EXTRAS",
    "OUT_OF_SCOPE_OBLIGATIONS",
    "STRICT_FROZEN_CONFIG",
    "UNMODELED_OBLIGATIONS",
    "AmendmentKindRegime",
    "AmendmentLiabilityDirection",
    "BindingSourceKind",
    "BucketPointer",
    "CasillaId",
    "ConvenioOverrideKind",
    "IntracomOperationType",
    "LedgerSortField",
    "LedgerSortOrder",
    "MissingOptionalExtraError",
    "Modelo",
    "OptionalExtra",
    "Period",
    "PeriodError",
    "PeriodKind",
    "PostFilingEventKind",
    "RefundElection",
    "RegistryPeriodCode",
    "RescateType",
    "ResultDisposition",
    "SecureObjectWrite",
    "ServiceCapability",
    "StandardPeriodCode",
    "TaxDomain",
    "TipoRentaIrnr",
    "accepted_period_codes",
    "accepted_period_patterns",
    "classify_amendment_liability_direction",
    "classify_post_filing_event_kind",
    "derive_result_disposition",
    "freeze_toml",
    "freeze_toml_value",
    "iban_mod_97",
    "modelo_has_codified_amendment_regime",
    "modelo_has_codified_disposition",
    "optional_extra_available",
    "parse_toml_text",
    "permitted_amendment_kind_values",
    "pointer_path",
    "post_filing_event_is_actionable",
    "read_pointer",
    "read_toml",
    "require_active_bucket_id",
    "require_optional_extra",
    "resolve_active_bucket_id",
    "resolve_amendment_kind_regime",
    "resolve_repository_bucket_id",
    "result_disposition_casilla_ids",
    "result_disposition_is_refund",
    "to_str_keyed_dict",
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
    if name == "BucketPointer":
        from ._bucket_pointer import BucketPointer

        return BucketPointer
    if name in (
        "pointer_path",
        "read_pointer",
        "resolve_active_bucket_id",
        "resolve_repository_bucket_id",
        "require_active_bucket_id",
        "write_pointer",
    ):
        from . import _bucket_pointer_io

        return getattr(_bucket_pointer_io, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

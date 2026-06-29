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
Active-bucket context uses the plaintext :class:`BucketPointer` value object
plus :func:`pointer_path`, :func:`read_pointer`, :func:`write_pointer`,
:func:`resolve_active_bucket_id`, :func:`require_active_bucket_id`, and
:func:`resolve_repository_bucket_id`. TOML and option utilities expose
:func:`read_toml`, :func:`parse_toml_text`, :func:`freeze_toml`,
:class:`OptionalExtra`, and :func:`require_optional_extra`. Filing-result
helpers expose the codified :class:`ResultDisposition` mapping and its
casilla/refund predicates.

``BindingSourceKind``, ``BucketPointer``, and the active-bucket IO helpers are
resolved through ``__getattr__`` so storage, config, and aggregation callers
can import the public core facade without recreating the cycles those helpers
break internally.

Major subpackages remain the specialised homes for broader contracts:
:mod:`aeat.core.config` owns settings, :mod:`aeat.core.errors` owns the error
taxonomy and registry, :mod:`aeat.core.money` and :mod:`aeat.core.decimal` own
Decimal primitives, :mod:`aeat.core.time` owns clocks, :mod:`aeat.core.identity`
owns NIF/NIE/bucket/profile identifiers, :mod:`aeat.core.access_gate` owns
live-read and write-refusal gating, :mod:`aeat.core.redaction` owns safe output,
and :mod:`aeat.core.classification` owns sensitivity policy.

See Also:
    :class:`aeat.core.Period`: Canonical filing year plus registry period-code
        value used across registry, deadline, and workflow boundaries.
    :class:`aeat.core.BucketPointer`: Typed value for the plaintext
        ``active-profile`` pointer file.
    :func:`aeat.core.resolve_active_bucket_id`: Central active-bucket
        precedence resolver for storage and CLI startup paths.
    :func:`aeat.core.read_toml`: Shared committed-TOML loader with
        caller-owned error wrapping.
    :class:`aeat.core.ResultDisposition`: Codified fichero result-disposition
        code set grounded in bundled AEAT diseños.
    :class:`aeat.core.BindingSourceKind`: Canonical registry binding-source
        taxonomy resolved lazily from :mod:`aeat.core.aggregation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._capabilities import ServiceCapability
from ._casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ._iban import IBAN_SHAPE_RE, iban_mod_97
from ._ledger_sort import LedgerSortField, LedgerSortOrder
from ._modelo import NON_REGISTRY_MODELOS, Modelo
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
from ._refund_election import RefundElection
from ._result_disposition import (
    ResultDisposition,
    derive_result_disposition,
    modelo_has_codified_disposition,
    result_disposition_casilla_ids,
    result_disposition_is_refund,
)
from ._tax_domain import TaxDomain
from ._toml import freeze_toml, freeze_toml_value, parse_toml_text, read_toml, to_str_keyed_dict

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
    from .aggregation import BindingSourceKind

__all__: list[str] = [
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "IBAN_SHAPE_RE",
    "NON_REGISTRY_MODELOS",
    "OPTIONAL_EXTRAS",
    "STRICT_FROZEN_CONFIG",
    "BindingSourceKind",
    "BucketPointer",
    "CasillaId",
    "LedgerSortField",
    "LedgerSortOrder",
    "MissingOptionalExtraError",
    "Modelo",
    "OptionalExtra",
    "Period",
    "PeriodError",
    "PeriodKind",
    "RefundElection",
    "RegistryPeriodCode",
    "ResultDisposition",
    "ServiceCapability",
    "StandardPeriodCode",
    "TaxDomain",
    "accepted_period_codes",
    "accepted_period_patterns",
    "derive_result_disposition",
    "freeze_toml",
    "freeze_toml_value",
    "iban_mod_97",
    "modelo_has_codified_disposition",
    "optional_extra_available",
    "parse_toml_text",
    "pointer_path",
    "read_pointer",
    "read_toml",
    "require_active_bucket_id",
    "require_optional_extra",
    "resolve_active_bucket_id",
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

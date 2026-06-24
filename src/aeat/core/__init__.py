"""Core cross-cutting infrastructure shared by every ``aeat`` layer.

The core layer holds the typed primitives, configuration, and boundary
utilities that the domain, application, adapter, and entrypoint layers all
build on, while depending on none of them — the innermost ring of the
hexagonal architecture.

Direct exports:

* :data:`STRICT_FROZEN_CONFIG` — the frozen-strict pydantic ``ConfigDict``
  shared by immutable boundary models.
* :class:`StandardPeriodCode` — the closed set of AEAT filing-period tokens.
* :class:`Modelo` — the closed set of AEAT modelo identifier codes.
* :class:`AggregationSourceKind` — provenance kinds for aggregated ledger
  values, resolved lazily to avoid an import cycle.
* :class:`BindingSourceKind` — the single canonical closed set of registry
  binding ``source`` tokens, resolved lazily to avoid an import cycle.

Major subpackages: :mod:`aeat.core.config` (the central settings surface),
:mod:`aeat.core.errors` (the error taxonomy and registry),
:mod:`aeat.core.money` and :mod:`aeat.core.decimal` (Decimal primitives),
:mod:`aeat.core.time` (clock helpers), :mod:`aeat.core.identity`
(NIF / NIE parsing), :mod:`aeat.core.access_gate` (live-read and
write-refusal gating), :mod:`aeat.core.redaction` (output redaction),
:mod:`aeat.core.classification` (sensitivity policy), and
:mod:`aeat.core.observability` (run-trace logging).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._capabilities import ServiceCapability
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
    from .aggregation import AggregationSourceKind, BindingSourceKind

__all__: list[str] = [
    "ANTHROPIC_EXTRA",
    "BROWSER_EXTRA",
    "GOOGLE_EXTRA",
    "NON_REGISTRY_MODELOS",
    "OPTIONAL_EXTRAS",
    "STRICT_FROZEN_CONFIG",
    "AggregationSourceKind",
    "BindingSourceKind",
    "BucketPointer",
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
    "result_disposition_is_refund",
    "to_str_keyed_dict",
    "write_pointer",
]


def __getattr__(name: str) -> object:
    if name == "AggregationSourceKind":
        from .aggregation import AggregationSourceKind

        return AggregationSourceKind
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

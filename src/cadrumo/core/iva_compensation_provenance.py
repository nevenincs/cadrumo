"""Closed provenance taxonomy for Modelo 303 IVA compensation period states.

Names the five supplying paths that can construct an
:class:`~domain.iva_compensation.IvaCompensationPeriodState`, one member each,
with no catch-all: a future supplying path is added here rather than absorbed
into an approximate member.

The member decides whether the row may carry an AEAT expediente. Exactly one
path -- :data:`~IvaCompensationStateProvenance.AEAT_CAPTURE` -- receives an
identifier AEAT issued; the other four previously minted a synthetic marker
into the same field (``manual-seed``, ``manual-correction``, ``local-...``,
``obs-...``), which made an operator-supplied string structurally
indistinguishable from an AEAT-issued one. The model constrains the pair, so
that impersonation is no longer expressible.

**This is deliberately NOT**
:class:`~application.calculations.ObservationSourceKind`, and the two coexist.
That enum classifies the origin of a persisted calculation OBSERVATION and
carries ``is_official_aeat``, the predicate deciding filing-grade authority. A
compensation period state is not an observation -- it is a derived per-period
row -- and it must never confer filing authority. Two further asymmetries make
the taxonomies non-substitutable in both directions:
:data:`~IvaCompensationStateProvenance.CASILLA_RECONSTRUCTION` builds a state
from casilla values with no observation behind it at all, and this enum splits
an operator seed from an operator correction where the observation taxonomy has
a single ``OPERATOR_MANUAL``. Merging them would destroy the second distinction
and import the officialness predicate onto a row that must not have one.
"""

from __future__ import annotations

from enum import StrEnum


class IvaCompensationStateProvenance(StrEnum):
    """Which supplying path constructed one IVA compensation period state.

    Consumed by
    :class:`~domain.iva_compensation.IvaCompensationPeriodState`, which
    requires it with no default: a default would let a new supplying path
    inherit a provenance it never declared.
    """

    AEAT_CAPTURE = "aeat_capture"
    """Read from an AEAT sede capture. The ONLY member carrying a real
    AEAT-issued expediente and a real AEAT-printed register status."""

    APP_FILING = "app_filing"
    """Projected from a locally filed Modelo 303 revision. Non-official: a
    locally filed value never establishes filing-grade cross-period readiness."""

    CASILLA_RECONSTRUCTION = "casilla_reconstruction"
    """Rebuilt from casilla observations by the annual partition. Computational
    scaffold that is never persisted and never surfaced to an operator."""

    OPERATOR_SEED = "operator_seed"
    """Declared by the operator as an opening carry-forward balance predating
    the local compensation history."""

    OPERATOR_CORRECTION = "operator_correction"
    """Declared by the operator as a correction to a previously seeded balance.
    Distinct from :data:`OPERATOR_SEED`; the retired ``status`` literal wrote
    the same token for both, so the two were indistinguishable on disk."""


__all__ = ["IvaCompensationStateProvenance"]

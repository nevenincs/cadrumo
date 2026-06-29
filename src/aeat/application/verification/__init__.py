"""Registry-backed verification of imported declaracion drafts.

This package compares an inbound
:class:`~aeat.adapters.inbound.declaracion.DeclaracionObservation` against the
registry expectations for the same modelo and :class:`~aeat.core.Period`.
:func:`verify_declaracion` loads a
:class:`~aeat.domain.calculations.registry.RegistrySnapshot`, calculates the
expected casilla values from extracted inputs and supplied
``BindingId`` values, and returns a local :class:`VerificationVerdict`.

This is not the persisted modelo work verification-report catalogue, and it is
not filed-state reconciliation. It does not contact AEAT, read live filed
records, or persist a :class:`aeat.domain.modelos.VerificationReport`; registry
filed-state comparison stays with
:func:`aeat.application.registry.verify_filed_state`.

See Also:
    :func:`verify_declaracion`
        Run local imported-declaration verification.
    :class:`VerificationVerdict`
        Frozen verdict containing status, coverage, expectation ids, and
        classified discrepancies.
    :class:`ClassifiedDiscrepancy`
        Per-casilla mismatch with :class:`DiscrepancyCause` classification.
    :class:`VerificationStatus`
        Closed operator-facing status returned by this verifier.
    :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
        Registry authority used to load the snapshot selected by modelo and
        period.
"""

from __future__ import annotations

from ._errors import VerificationError
from ._schema import (
    ClassifiedDiscrepancy,
    DiscrepancyCause,
    VerificationStatus,
    VerificationVerdict,
)
from ._verify import verify_declaracion

__all__ = [
    "ClassifiedDiscrepancy",
    "DiscrepancyCause",
    "VerificationError",
    "VerificationStatus",
    "VerificationVerdict",
    "verify_declaracion",
]

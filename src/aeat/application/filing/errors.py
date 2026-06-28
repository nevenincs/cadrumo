"""Application-layer errors for :mod:`aeat.application.filing`.

The domain filing package owns record, import, export, amendment, and builder
errors. This module adds the application-specific root used by persistence and
summary helpers while preserving the :class:`aeat.domain.filing.ModeloDraftError`
catch boundary.

See Also:
    :mod:`aeat.domain.filing._errors`
        Domain filing error hierarchy raised by draft, import, export, and
        amendment records.
    :mod:`aeat.application.filing._calculate`
        Calculation-summary surface that raises :class:`ModeloCalculateError`
        for invalid next-action invariants.
    :mod:`aeat.application.filing._runtime_repository`
        Runtime persistence helper that raises :class:`ModeloApplicationError`
        for filing-bucket resolution failures.
"""

from __future__ import annotations

from ...domain.filing import ModeloDraftError


class ModeloApplicationError(ModeloDraftError):
    """Base class for errors raised by the filing application layer.

    The class extends :class:`aeat.domain.filing.ModeloDraftError` so callers
    that catch the domain filing boundary still catch application-level filing
    failures.
    """


class ModeloCalculateError(ModeloApplicationError, ValueError):
    """Raised when calculation-summary invariants are refused.

    The :class:`ValueError` mixin keeps pydantic model validators and callers
    that expect validation-style failures aligned with
    :class:`ModeloApplicationError`.
    """

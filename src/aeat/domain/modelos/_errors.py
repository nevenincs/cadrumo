"""Error hierarchy for the modelo registry.

Every error raised from :mod:`aeat.domain.modelos` derives from
:class:`ModeloRegistryError`, which in turn derives from the project
root :class:`aeat.core.errors.AeatError`. Two concrete subclasses cover the
failure modes surfaced to external callers:

- :class:`UnknownModeloError` — raised by registry lookups on an
  unknown / unparseable code.
- :class:`RegistryIntegrityError` — raised at import time during
  registry assembly when a structural invariant is violated.
"""

from __future__ import annotations

from ...core.errors import AeatError


class ModeloRegistryError(AeatError):
    """Base class for every error raised from :mod:`aeat.domain.modelos`."""


class UnknownModeloError(ModeloRegistryError):
    """Raised by :func:`aeat.domain.modelos.get_modelo` on unknown codes.

    Attributes:
        modelo_code: The offending code as supplied by the caller.
    """

    def __init__(self, code: str) -> None:
        """Initialise with the offending modelo code string.

        Args:
            code: The unknown or unparseable modelo code string the
                caller supplied to :func:`aeat.domain.modelos.get_modelo`.
        """
        super().__init__(f"unknown modelo code: {code!r}")
        self.modelo_code = code


class RegistryIntegrityError(ModeloRegistryError):
    """Raised at import time when the registry fails a structural check.

    Signals that a modelo registry entry violates a cross-reference
    invariant (missing code, extra code, dangling ``caps_into``, or
    entry ``code`` not matching its dict key). Always raised from
    :func:`aeat.domain.modelos._registry._finalise_registry` and therefore
    never crosses a user call stack — it aborts package import.
    """

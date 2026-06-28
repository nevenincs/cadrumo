"""Top-level package for the AEAT (Agencia Estatal de Administración Tributaria) toolkit.

Exposes the ``__version__`` of the distribution. Subpackages provide the
layered architecture: :mod:`aeat.adapters` (inbound / outbound integrations),
:mod:`aeat.application` (use-cases), :mod:`aeat.domain` (pure rules),
:mod:`aeat.entrypoints` (CLI / scripts), and :mod:`aeat.core`
(cross-cutting infrastructure).

The ``pikepdf._core`` bridge logger is silenced via the ``loggers`` block in
:func:`aeat.core.logging.configure_logging` (dictConfig) rather than via a
bootstrap-time ``setLevel`` call here. This keeps all logger-level policy in
a single, auditable location.
"""

__version__ = "0.1.0"

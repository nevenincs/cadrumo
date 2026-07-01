"""Import-light root package for the AEAT toolkit.

The package root exposes only the distribution ``__version__``. Concrete
capabilities live behind layer facades: :mod:`aeat.core` for shared primitives
and runtime context, :mod:`aeat.domain` for business authorities,
:mod:`aeat.application` for use-case orchestration, :mod:`aeat.adapters` for
inbound, outbound, and persistence infrastructure, and :mod:`aeat.entrypoints`
for operator transports such as the Typer CLI.

Importing ``aeat`` must not configure logging, load registries, open storage, or
materialise browser/PDF integrations. The ``pikepdf._core`` bridge logger is
silenced via the ``loggers`` block in
:func:`aeat.core.logging.configure_logging` rather than by bootstrap-time side
effects here, keeping logger policy in one auditable location.

See Also:
    :mod:`aeat.core.resources`
        Bundled registry and corpus resource boundary used after a concrete
        capability imports the relevant layer.
    :mod:`aeat.core.logging`
        Central logging configuration surface kept out of package import
        side effects.
    :mod:`aeat.application.operator_surface`
        Backend-owned capability contract for operator and automation surfaces.
"""

__version__ = "0.1.0"
